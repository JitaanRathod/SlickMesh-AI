# Phase 1 — Satellite SAR Oil-Spill Detection

**Owner:** Martin
**Independence:** This phase needs nothing from any other phase. It starts from a public
benchmark dataset and ends by writing a JSON file. Build and test it entirely alone.

## 1. Mission

Given a Sentinel-1 SAR image, produce a binary oil-slick candidate mask, turn it into a polygon
with area/centroid, attach a confidence score and a wind-based quality flag, and write it out in
the contract shape below.

## 2. The physics, briefly

SAR doesn't see oil chemically — it measures ocean-surface roughness. Wind creates small
capillary waves that scatter radar strongly (bright). An oil film damps those waves, so a slick
shows up as a *relatively dark* region against surrounding sea. The same darkening can be caused
by low wind, natural biogenic films, rain cells, current fronts, or ship wakes — which is why this
is fundamentally a look-alike discrimination problem, not just "find the dark blob."

## 3. Dataset

- **Primary:** Deep-SAR Oil Spill (SOS) — Sentinel-1A VV subset, 256×256 labelled patches
  (~3,354 train / 839 test in the commonly reported split). Zenodo record `8346860` region;
  prefer the **refined 2025 release** (Zenodo `15298010`) if the download is practical — it
  corrects a large fraction of noisy training/validation masks.
- **Fallback if disk/bandwidth is tight:** CSIRO Oil Spill dataset (image-level binary labels
  only — usable as a classification-only fallback, not for the polygon/geometry step).

Do **not** start from raw Sentinel-1 GRD scenes tonight — the preprocessing (calibration,
land-sea masking, patching) alone can eat the whole time budget. Use the pre-cropped benchmark.

## 4. Baseline model

```
256×256×1 VV input
   │
Encoder (conv + downsample) ── skip connections ── Decoder (upsample)
   │
256×256×1 sigmoid output (oil probability per pixel)
```

| Component | Choice |
|---|---|
| Architecture | Plain U-Net |
| Loss | 0.5 · BCE + 0.5 · Dice |
| Optimizer | Adam, lr = 1e-4 |
| Epochs | 20–30 |
| Metrics | IoU, Dice/F1, precision, recall — **never rely on pixel accuracy alone** (ocean dominates the image; a model that predicts all-background can score high on accuracy while missing the spill entirely) |

**Stretch model (only after the baseline works):** MobileNetV2-DeepLabV3+ — published work on
this exact dataset reports ~80–81% mIoU / ~89% F1 with substantially fewer parameters than an
Xception backbone. Don't attempt Transformer/ViT approaches tonight — good architecture, wrong
time budget.

## 5. Build plan (stop at any stage if time runs out — a good Stage 6 demo beats a broken Stage 9)

| # | Stage | Definition of done |
|---|---|---|
| 1 | Download SOS (or refined SOS) | Images + masks load in Python, filenames align |
| 2 | Dataset loader | A batch tensor visualises correctly (image + overlaid mask) |
| 3 | U-Net forward pass | Runs without shape errors on one batch |
| 4 | Training | Loss decreases; predicted masks visibly start forming slick-shaped regions |
| 5 | Evaluation | IoU / Dice / precision / recall computed on held-out test split |
| 6 | Demo visual | Side-by-side input / ground-truth / prediction panels for 6–10 examples, including at least one hard/look-alike case if available |
| 7 | Geometry extraction | Mask → connected components → polygon → area/centroid/bounding box |
| 8 | Wind quality flag | Rule-based flag from an external wind estimate (see below) |
| 9 | Contract output | Write the JSON in §7 for a chosen test example |
| 10 | Stretch: DeepLabV3+ comparison | Only if 1–9 are solid |

Suggested time split: 25% data/loader, 35% training/debugging, 15% evaluation, 10% geometry,
10% wind flag, 5% packaging.

## 6. Wind-based quality flag

Rough operational bands (not hard physical thresholds — treat as guidance):

| Wind speed | Situation | Flag |
|---|---|---|
| < 2–3 m/s | Sea too smooth; false-positive risk high | `"unreliable"` |
| 3–10 m/s | Favourable contrast regime | `"favorable"` |
| 10–15 m/s | Increasingly unreliable | `"high_wind_risk"` |
| > 15 m/s | Sea too rough; contrast likely lost | `"unreliable"` |

If a live wind value isn't wired up yet, hardcode a plausible value for the demo scene and label
it clearly as such internally — don't block on Phase 4's environmental feed. This phase does not
need Phase 4 to produce a valid output; the flag is a nice-to-have refinement.

## 7. Output contract (own this — no other phase can produce this shape)

```json
{
  "spill_id": "SPILL-001",
  "detected_at": "2026-08-25T06:00:00Z",
  "spill_detected": true,
  "confidence": 0.87,
  "area_km2": 3.2,
  "centroid": { "lat": 20.48, "lon": 67.52 },
  "polygon": [
    [67.15, 20.45],
    [67.45, 20.75],
    [67.90, 20.62],
    [67.70, 20.30],
    [67.35, 20.25]
  ],
  "quality_flag": "favorable",
  "notes": "candidate detection — not chemically confirmed"
}
```

Notes:
- `polygon` points are `[lon, lat]` (GeoJSON order).
- If working purely in the SOS benchmark's pixel space (no real geospatial georeferencing), it's
  fine to fabricate a plausible lat/lon box for the demo scene (e.g. somewhere in the Arabian Sea)
  — just say so internally; don't present benchmark pixel coordinates as if they were real-world
  georeferenced output.

## 8. Testing without any other phase

You can develop, train, evaluate, and produce a valid Contract A output using only the SOS
dataset's own test split. Nothing here requires AIS data, environmental data, or the dashboard to
exist. Validate the JSON by hand against §7 before calling this "done."

## 9. Risks

| Risk | Mitigation |
|---|---|
| Look-alikes → false positives | Show at least one hard/look-alike example honestly in the demo panel rather than only cherry-picked easy cases |
| Benchmark leakage (patches from the same scene split across train/test) | Acceptable for a prototype — state the limitation out loud, don't hide it |
| Domain shift to real, unseen scenes | Frame the system as a prototype/candidate detector throughout |

## 10. What NOT to claim

- Do not claim SAR proves the substance is petroleum.
- Do not claim benchmark IoU equals real-world accuracy.
- Do not claim a point-source location — only a polygon/area with an attached confidence.
