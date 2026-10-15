"""Join unique LiDAR cell centers to the official 2013 Sonoma vegetation map."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer
from shapely import points
from shapely.geometry import shape
from shapely.ops import transform
from shapely.strtree import STRtree

from canopyguard.io import ensure_parent, project_root
from canopyguard.provenance import study_area_box, write_provenance


def broad_group(map_class: str, forest_lifeform: str) -> str:
    """Map source lifeform and dominant named class to five broad groups."""
    name = (map_class or "").lower()
    lifeform = (forest_lifeform or "").lower()
    if lifeform in {"conifer forest", "hardwood forest"}:
        return lifeform
    if lifeform in {"shrub", "riparian shrub", "non-native shrub"}:
        return "shrub"
    if lifeform in {"herbaceous", "herbaceous wetland"}:
        return "grass"
    if lifeform in {"mixed conifer-hardwood forest", "non-native forest"}:
        if name.startswith(("pseudotsuga", "sequoia", "pinus", "hesperocyparis")):
            return "conifer forest"
        if name.startswith(("quercus", "eucalyptus")):
            return "hardwood forest"
    if lifeform == "riparian forest" and name.startswith("populus"):
        return "hardwood forest"
    return "other"


def _query(session: requests.Session, url: str, params: dict) -> dict:
    response = session.get(url, params=params, timeout=120)
    response.raise_for_status()
    document = response.json()
    if "error" in document:
        raise ValueError(f"Sonoma map query failed: {document['error']}")
    return document


def fetch_polygons(url: str, bbox: dict, output: Path, page_size: int) -> int:
    """Save the complete spatial-query result, checking count and unique IDs."""
    envelope = ",".join(str(bbox[key]) for key in ("west", "south", "east", "north"))
    params = {
        "geometry": envelope,
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "OBJECTID,MAP_CLASS,LIFEFORM,LF_FOREST",
    }
    session = requests.Session()
    count = _query(session, url, {**params, "f": "json", "returnCountOnly": "true"})[
        "count"
    ]
    part = ensure_parent(output.with_suffix(output.suffix + ".part"))
    seen: set[int] = set()
    with part.open("w", encoding="utf-8") as stream:
        stream.write('{"type":"FeatureCollection","features":[')
        for offset in range(0, count, page_size):
            page = _query(
                session,
                url,
                {
                    **params,
                    "f": "geojson",
                    "orderByFields": "OBJECTID",
                    "resultOffset": offset,
                    "resultRecordCount": page_size,
                },
            )
            features = page.get("features", [])
            if not features:
                raise ValueError(f"Sonoma map returned no features at offset {offset}")
            for feature in features:
                object_id = int(feature["properties"]["OBJECTID"])
                if object_id in seen:
                    raise ValueError(f"Duplicate Sonoma OBJECTID {object_id}")
                if seen:
                    stream.write(",")
                json.dump(feature, stream, separators=(",", ":"))
                seen.add(object_id)
            print(f"Sonoma polygons: {len(seen):,}/{count:,}", flush=True)
        stream.write("]}")
    current_ids = set(
        _query(session, url, {**params, "f": "json", "returnIdsOnly": "true"})[
            "objectIds"
        ]
    )
    if seen != current_ids:
        raise ValueError(
            f"Sonoma map IDs changed: missing {len(current_ids - seen)}, "
            f"extra {len(seen - current_ids)}"
        )
    part.replace(output)
    return len(seen)


def _prepared_polygons(raw: Path, boundary_m: float):
    document = json.loads(raw.read_text(encoding="utf-8"))
    project = Transformer.from_crs(4326, 6339, always_xy=True).transform
    polygons, classes, groups, ids = [], [], [], []
    for feature in document["features"]:
        props = feature["properties"]
        geometry = transform(project, shape(feature["geometry"]))
        interior = geometry.buffer(-boundary_m) if boundary_m else geometry
        if interior.is_empty:
            continue
        name = props.get("MAP_CLASS") or "uncertain"
        polygons.append(interior)
        classes.append(name)
        groups.append(broad_group(name, props.get("LF_FOREST")))
        ids.append(int(props["OBJECTID"]))
    return polygons, np.array(classes), np.array(groups), np.array(ids)


def assign_types(
    x: np.ndarray,
    y: np.ndarray,
    polygons: list,
    classes: np.ndarray,
    groups: np.ndarray,
    polygon_ids: np.ndarray,
    *,
    chunk_size: int,
    pool_below_n: int,
) -> pd.DataFrame:
    """Assign one unambiguous interior polygon per cell and pool rare types."""
    if chunk_size < 1 or pool_below_n < 1:
        raise ValueError("Chunk size and pooling threshold must be positive")
    if len(x) != len(y):
        raise ValueError("Cell coordinates must have equal length")
    tree = STRtree(polygons)
    vegetation_type = np.full(len(x), "uncertain", dtype=object)
    broader_group = np.full(len(x), "other", dtype=object)
    source_id = np.full(len(x), -1, dtype=np.int64)
    for start in range(0, len(x), chunk_size):
        stop = min(start + chunk_size, len(x))
        matches = tree.query(points(x[start:stop], y[start:stop]), predicate="within")
        if matches.size == 0:
            continue
        counts = np.bincount(matches[0], minlength=stop - start)
        single = counts[matches[0]] == 1
        cell = start + matches[0, single]
        polygon = matches[1, single]
        vegetation_type[cell] = classes[polygon]
        broader_group[cell] = groups[polygon]
        source_id[cell] = polygon_ids[polygon]
    counts = pd.Series(vegetation_type).value_counts()
    model_group = vegetation_type.copy()
    small = np.array([counts.get(name, 0) < pool_below_n for name in model_group])
    model_group[small] = ["group:" + name for name in broader_group[small]]
    model_group[vegetation_type == "uncertain"] = "uncertain"
    return pd.DataFrame(
        {
            "vegetation_type": vegetation_type,
            "broader_group": broader_group,
            "model_group": model_group,
            "map_object_id": source_id,
            "uncertain": vegetation_type == "uncertain",
        }
    )


def build_vegetation_table(config: dict, study: dict) -> dict:
    """Download, join, and audit the official map against local label cells."""
    root = project_root()
    options = config["vegetation_join"]
    raw = root / options["raw_path"]
    if not raw.exists():
        fetch_polygons(
            options["source_url"],
            study["study_area"]["bbox"],
            raw,
            int(options["page_size"]),
        )
    with np.load(root / config["labels_path"], allow_pickle=False) as archive:
        cell_id, x, y = (archive[key] for key in ("cell_id", "x", "y"))
    polygons, classes, groups, ids = _prepared_polygons(
        raw, float(options["boundary_exclusion_m"])
    )
    table = assign_types(
        x,
        y,
        polygons,
        classes,
        groups,
        ids,
        chunk_size=int(options["chunk_size"]),
        pool_below_n=int(config["pool_to_physiognomic_group_below_n"]),
    )
    table.insert(0, "cell_id", cell_id)
    table.insert(1, "x", x)
    table.insert(2, "y", y)
    output = ensure_parent(root / options["output_path"])
    table.to_parquet(output, index=False)
    bbox = study_area_box(study)
    write_provenance(
        raw,
        source_url=options["source_url"],
        script_name="join_sonoma_veg.py",
        bbox_wgs84=bbox,
        crs="EPSG:4326",
        row_count=len(ids),
    )
    write_provenance(
        output,
        source_url=options["source_url"],
        script_name="join_sonoma_veg.py",
        bbox_wgs84=bbox,
        crs="EPSG:6339",
        row_count=len(table),
    )
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    counts = table["vegetation_type"].value_counts().to_dict()
    audit = {
        "source_url": options["source_url"],
        "raw_path": options["raw_path"],
        "raw_sha256": digest,
        "raw_file_modified_utc": datetime.fromtimestamp(
            raw.stat().st_mtime, UTC
        ).isoformat(),
        "join_generated_utc": datetime.now(UTC).isoformat(),
        "query_bbox": study["study_area"]["bbox"],
        "map_year": 2013,
        "label_crs": "EPSG:6339",
        "join_rule": "cell center inside one polygon after inward boundary buffer",
        "boundary_exclusion_m": options["boundary_exclusion_m"],
        "source_polygon_count": len(
            json.loads(raw.read_text(encoding="utf-8"))["features"]
        ),
        "usable_polygon_count": len(polygons),
        "cells": len(table),
        "uncertain_cells": int(table["uncertain"].sum()),
        "uncertain_fraction": float(table["uncertain"].mean()),
        "vegetation_type_counts": counts,
        "broader_group_counts": table["broader_group"].value_counts().to_dict(),
        "pooled_cells": int((table["model_group"] != table["vegetation_type"]).sum()),
    }
    ensure_parent(output.with_suffix(".provenance.json")).write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    return audit
