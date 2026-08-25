# Phase 2 — AIS, Vessel Trajectories & Spill Backtracking

**Owner:** Jitaan
**Independence:** This phase needs only a spill **centroid (lat, lon)** and a **detection
timestamp**. It does not need Phase 1's actual model, Phase 3's scoring, or Phase 4's dashboard —
use the mock spill in §2 until real data is available.

## 1. Mission

Given a spill centroid + time: (a) reconstruct clean per-vessel AIS trajectories in the area, (b)
compute a reverse drift-based origin corridor, (c) shortlist candidate vessels with raw
spatial/temporal/motion evidence attached — **not** a combined score; that's Phase 3's job.

## 2. Mock input (use this until Phase 1 is ready)

```json
{ "spill_id": "SPILL-001", "centroid": { "lat": 20.48, "lon": 67.52 }, "detected_at": "2026-08-25T06:00:00Z" }
```

## 3. AIS fields that matter for this build

| Field | Why it matters |
|---|---|
| MMSI | Primary join key — groups raw messages into per-vessel trajectories |
| IMO | Secondary identity check (MMSI can occasionally be reassigned) |
| lat / lon | Core spatial signal |
| timestamp (UTC) | Core temporal signal |
| SOG (speed over ground) | Near-zero SOG near the spill = loitering signal; also needed for jump-filtering |
| COG (course over ground) | Checks whether a vessel's path plausibly intersects the spill |
| navigational status | Corroborating signal (e.g. unexpected stop) |
| vessel type | Tankers/cargo are the realistic suspect pool — used as a soft weighting later, not a hard filter |

Heading and rate-of-turn are secondary/nice-to-have — don't block on them.

## 4. Data sources

| Source | Role | Access |
|---|---|---|
| **AISstream.io** | Primary — live/near-real-time feed | Free API key, WebSocket `wss://stream.aisstream.io/v0/stream`, filter to a bounding box (Arabian Sea / Bay of Bengal / Indian coastline) |
| **Global Fishing Watch** | Secondary/cross-check, and source of realistic loitering/AIS-gap events | Free registered token, REST API |
| **Danish Maritime Authority historical AIS** | Dev/offline — wrong geography, but identical schema shape, instant download, no login | `web.ais.dk/aisdata/` — one day's CSV is enough for pipeline debugging |

**Practical order for tonight:**
1. Start an AISstream.io listener immediately, bounding-box filtered, writing raw JSON to
   disk/DB continuously — the earlier it starts, the more real Indian-Ocean data you'll have by
   demo time.
2. In parallel, build/debug the cleaning→trajectory pipeline against one day of Danish CSV data —
   it's instantly available and de-risks pipeline bugs before the live feed accumulates enough.
3. Use Global Fishing Watch as fallback/cross-check.

## 5. Trajectory reconstruction pipeline

```
Raw AIS messages
  → CLEAN (drop malformed rows, out-of-range coords, dedupe)
  → GROUP BY MMSI (+ IMO as secondary identity check)
  → SORT BY TIMESTAMP
  → FILTER IMPOSSIBLE JUMPS (implied speed vs realistic max ~40-50 kn, cross-check reported SOG)
  → HANDLE GAPS (interpolate if < 30-60 min; SPLIT into a new segment if longer — a long AIS
     silence near a spill is itself evidence, don't smooth over it)
  → SMOOTH SOG/COG only (never raw lat/lon)
  → build LineString per MMSI with parallel time index
  → CLIP to area of interest (Indian EEZ / Arabian Sea / Bay of Bengal)
```

Use `movingpandas` — it handles gap-splitting and trajectory objects out of the box; don't
hand-roll this if the library does it.

## 6. Matching vessels to the spill

Hard gates (exclude, don't just downrank):
- Must have ≥1 AIS point within a lookback window (6–24h) before detection time.

Raw evidence to compute and attach per surviving candidate (do **not** combine these into one
number — output them individually; Phase 3 owns the combining logic):

| Evidence field | How computed |
|---|---|
| `min_distance_nm` | Haversine distance, closest trajectory point to spill centroid |
| `intersects_source_region` | Does the vessel's LineString intersect the buffered origin corridor? |
| `hours_since_passage` | Elapsed time between closest approach and detection time |
| `heading_delta_deg` | Angle between vessel COG and bearing-to-spill-centroid at closest approach |
| `sog_at_closest_knots` | Speed at closest approach — near-zero is a loitering signal |
| `track_continuity` | `"continuous"` vs `"gapped"` — a long AIS gap can indicate deliberate shutoff |

## 7. Backtracking — reverse drift origin corridor

Full Lagrangian particle simulation (GNOME-style) is **out of scope tonight** — implement the
simplified single-vector version, which is the same first-order model GNOME itself is built on:

```
1. Take spill centroid + detection time T.
2. Pull average wind vector + average ocean-current vector at that location/time.
3. drift_vector = current_vector + windage_term   (windage ≈ 3% of wind speed, in wind direction)
4. Project this vector BACKWARD from the spill location over a lookback window (6-24h)
   → probable origin corridor (a buffered line, NOT a single point).
5. Feed the corridor back into §6 as `intersects_source_region`.
```

**Wind/current source — self-serve, no dependency on Phase 4:**
Open-Meteo's free Weather Forecast API (wind) and Marine Weather API (`ocean_current_velocity`,
`ocean_current_direction`) — no API key, JSON, good enough for this simplified model. If Phase 4's
Copernicus pipeline is ready and you'd rather use that feed, swap it in later (Contract B) — but
don't wait on it.

**Explicitly report-only, not coded:** full bidirectional forward+backward drift convergence
matching, time-varying fields over the whole window (use one averaged vector instead and say so),
oil weathering/evaporation effects. Document these as future work, cite GNOME and the MV Rak
(Mumbai, 2011) / MSC ELSA III (Kochi, 2025) precedents as validation that the underlying approach
is applicable to Indian waters.

## 8. GIS tooling

`geopandas` (containers + spatial joins), `shapely` (polygon/buffer/intersects geometry ops),
`pyproj` (WGS84 → projected CRS before any distance/buffer calc — haversine-on-raw-degrees is only
an approximation), `rasterio` (only if Phase 1 hands off a raster instead of a polygon),
`movingpandas` (trajectory objects, gap-splitting, stop/loiter detection).

## 9. Output contract (own this)

```json
{
  "source_region": {
    "latitude": 20.48,
    "longitude": 67.52,
    "radius_km": 22,
    "backtrack_hours": 24
  },
  "candidates": [
    {
      "mmsi": "419001234",
      "imo": "9123456",
      "name": "MV Ocean Star",
      "vessel_type": "Tanker",
      "position": { "latitude": 20.15, "longitude": 67.10 },
      "track": [[19.70, 66.40], [19.85, 66.70], [20.00, 66.90], [20.15, 67.10]],
      "evidence": {
        "min_distance_nm": 3.2,
        "hours_since_passage": 5.1,
        "heading_delta_deg": 12,
        "sog_at_closest_knots": 1.4,
        "intersects_source_region": true,
        "track_continuity": "continuous"
      }
    }
  ]
}
```

`position`/`track` use `[lat, lon]` order (AIS convention — note this differs from Phase 1's
GeoJSON polygon; the conversion happens once, in integration, not here).

## 10. Testing without any other phase

Run the whole pipeline against the mock spill in §2 and the Danish AIS dev dataset. You should be
able to produce a fully valid Contract C output with zero real Indian-Ocean data — swap in
AISstream.io's real feed only once it's had time to accumulate.

## 11. Time budget

Data cleaning/trajectory pipeline first (this is the foundation everything else sits on), matching
second, backtracking third — backtracking depends on having a working trajectory pipeline, not the
other way around.
