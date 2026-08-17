# Paper workflow

Use this workflow when preparing the CanopyGuard-AI manuscript.

## 1. Literature discovery

Use `firecrawl-research-papers` to collect recent papers on:

- Vegetation management near power lines.
- Remote sensing for canopy height and vegetation growth.
- Sentinel-2 vegetation time-series forecasting.
- GEDI or LiDAR canopy-height validation.
- Optimization for maintenance scheduling.

Every useful source must be entered in `reports/claims_log.md` before being used
as a claim in the manuscript.

## 2. Manuscript drafting

Use `research-paper-writer` to draft structure and formal sections. Keep the
argument grounded in project outputs. Do not invent metrics, baselines, datasets,
or citations.

Recommended first paper structure:

1. Abstract
2. Introduction
3. Related work
4. Study area and data
5. Methods
6. Experiments
7. Results
8. Discussion
9. Limitations
10. Conclusion

## 3. Text and document hygiene

Use `scripts/check_text_hygiene.py` before committing prose. This check is for
plain-text validity: invisible Unicode, smart punctuation, and characters that
make code, CSVs, diffs, or LaTeX harder to review.

Do not use tools or prompts that hide AI assistance, strip required provenance,
bypass journal disclosure policies, or make authorship misleading.

## 4. Submission discipline

- Every result must be reproducible from config and data versions.
- Every figure must have the script or notebook that produced it.
- Every claim must appear in `reports/claims_log.md`.
- AI assistance must be disclosed according to the target journal policy.
