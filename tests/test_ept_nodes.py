from __future__ import annotations

import http.client
import io

import numpy as np
import pytest

from canopyguard.lidar import ept_nodes

CUBE = (0.0, 0.0, 1024.0, 1024.0)


def test_node_box_halves_the_cube_at_each_depth() -> None:
    assert ept_nodes.node_box(CUBE, "0-0-0-0") == CUBE
    assert ept_nodes.node_box(CUBE, "1-1-0-0") == (512.0, 0.0, 1024.0, 512.0)
    assert ept_nodes.node_box(CUBE, "3-2-5-1") == (256.0, 640.0, 384.0, 768.0)


def test_children_are_the_eight_sub_cubes() -> None:
    kids = ept_nodes.children("2-1-3-0")

    assert len(kids) == 8
    assert "3-2-6-0" in kids and "3-3-7-1" in kids


def test_resource_url_rejects_paths() -> None:
    with pytest.raises(ValueError, match="bare 3DEP project name"):
        ept_nodes.resource_url("a/b", "ept.json")
    assert ept_nodes.resource_url("PROJ", "ept-data", "0-0-0-0.laz").endswith(
        "/PROJ/ept-data/0-0-0-0.laz"
    )


def test_list_nodes_keeps_only_nodes_that_meet_a_tile_and_hold_points() -> None:
    hierarchy = {
        "0-0-0-0": 10,
        "1-0-0-0": 5,
        "1-1-1-0": 7,
        "2-0-0-0": 3,
        "2-1-1-0": 0,
    }
    tile = [(0.0, 0.0, 200.0, 200.0)]

    nodes = ept_nodes.list_nodes(CUBE, hierarchy, lambda keys: {}, tile, 5)

    assert sorted(key for key, _ in nodes) == ["0-0-0-0", "1-0-0-0", "2-0-0-0"]


def test_list_nodes_stops_at_the_depth_limit() -> None:
    hierarchy = {"0-0-0-0": 4, "1-0-0-0": 3, "2-0-0-0": 2}
    tile = [(0.0, 0.0, 100.0, 100.0)]

    nodes = ept_nodes.list_nodes(CUBE, hierarchy, lambda keys: {}, tile, 1)

    assert [key for key, _ in nodes] == ["0-0-0-0", "1-0-0-0"]


def test_list_nodes_fetches_subtrees_in_batches() -> None:
    hierarchy = {"0-0-0-0": 4, "1-0-0-0": -1}
    calls: list[list[str]] = []

    def fetch_subtrees(keys: list[str]) -> dict[str, int]:
        calls.append(list(keys))
        return {"1-0-0-0": 6, "2-0-0-0": 2}

    tile = [(0.0, 0.0, 100.0, 100.0)]
    nodes = ept_nodes.list_nodes(CUBE, hierarchy, fetch_subtrees, tile, 5)

    assert calls == [["1-0-0-0"]]
    assert dict(nodes) == {"0-0-0-0": 4, "1-0-0-0": 6, "2-0-0-0": 2}


def test_fetcher_retries_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = []

    def failing(url: str, timeout: float):
        attempts.append(url)
        raise OSError("boom")

    monkeypatch.setattr(ept_nodes.urllib.request, "urlopen", failing)
    monkeypatch.setattr(ept_nodes.time, "sleep", lambda seconds: None)

    with pytest.raises(OSError, match="boom"):
        ept_nodes.make_fetcher(1, 3)("https://example.test/x")
    assert len(attempts) == 3


def test_read_node_points_decodes_classes_and_flags() -> None:
    laspy = pytest.importorskip("laspy")
    header = laspy.LasHeader(point_format=6, version="1.4")
    header.scales = (0.01, 0.01, 0.01)
    header.offsets = (0.0, 0.0, 0.0)
    las = laspy.LasData(header)
    las.x = np.array([1.0, 2.0])
    las.y = np.array([3.0, 4.0])
    las.z = np.array([5.0, 6.0])
    las.classification = np.array([2, 7], dtype=np.uint8)
    las.classification_flags = np.array([0, 8], dtype=np.uint8)
    buffer = io.BytesIO()
    las.write(buffer)

    points = ept_nodes.read_node_points(buffer.getvalue())

    assert points["classification"].tolist() == [2, 7]
    assert points["flags"].tolist() == [0, 8]
    assert points["z"].tolist() == pytest.approx([5.0, 6.0])


def test_fetcher_retries_a_truncated_download(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = []

    class Response:
        def __init__(self, fail: bool) -> None:
            self.fail = fail

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def read(self) -> bytes:
            if self.fail:
                raise http.client.IncompleteRead(b"abc", 10)
            return b"whole"

    def urlopen(url: str, timeout: float) -> Response:
        attempts.append(url)
        return Response(fail=len(attempts) == 1)

    monkeypatch.setattr(ept_nodes.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(ept_nodes.time, "sleep", lambda seconds: None)

    assert ept_nodes.make_fetcher(1, 3)("https://example.test/x") == b"whole"
    assert len(attempts) == 2
