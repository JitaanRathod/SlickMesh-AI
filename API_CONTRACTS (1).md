# API_CONTRACTS — Canonical JSON Schemas

Single source of truth for every JSON shape that crosses a phase boundary. Each `phaseN-*.md` file
embeds the specific schema(s) it needs inline — if you change something here, propagate it there
too (see `GUIDELINES.md` → "Contract change protocol"). GeoJSON coordinate order is used
throughout: **`[longitude, latitude]`**, except where a field is explicitly named `latitude`/
`longitude` as separate keys (Phase 2/3 vessel records), which follow AIS convention instead —
noted per schema below so nobody has to guess.

---

## A. Satellite Detection Output (Phase 1 → Integration)

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

- `polygon` coordinates are `[lon, lat]` pairs (GeoJSON order).
- `quality_flag` ∈ `{"favorable", "low_wind_risk", "high_wind_risk", "unreliable"}` — derived from
  wind speed at acquisition time; see Phase 1 doc §5.
- `confidence` is model probability, not a claim of certainty about substance.

## B. Environmental Data Output (Phase 4a → Phase 2, and → Integration)

```json
{
  "location": { "lat": 20.48, "lon": 67.52 },
  "timestamp": "2026-08-25T06:00:00Z",
  "current_u_ms": 0.18,
  "current_v_ms": 0.07,
  "wind_speed_ms": 5.4,
  "wind_direction_deg": 72,
  "source_model": "Copernicus Marine"
}
```

- `current_u_ms` = eastward sea-water velocity, `current_v_ms` = northward — matches Copernicus
  `uo`/`vo` variable names directly.
- `source_model` should be swapped to `"Open-Meteo"` if Phase 2 self-serves this instead of
  waiting on Phase 4 (see Phase 2 doc — this is the designed independence escape hatch).

## C. AIS / Backtracking Output (Phase 2 → Phase 3)

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
      "track": [
        [19.70, 66.40],
        [19.85, 66.70],
        [20.00, 66.90],
        [20.15, 67.10]
      ],
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

- `position`/`track` points here use **`[lat, lon]`** order (AIS/Leaflet convention) — deliberately
  different from Phase 1's GeoJSON polygon; each phase doc calls this out explicitly.
- This output carries **raw evidence only** — no combined score. Combining is Phase 3's job; don't
  duplicate that logic in Phase 2.

## D. Attribution Engine Output (Phase 3 → Phase 4b / dashboard)

```json
{
  "spill_id": "SPILL-001",
  "ranked_vessels": [
    {
      "mmsi": "419001234",
      "name": "MV Ocean Star",
      "vessel_type": "Tanker",
      "confidence": 79,
      "reason": "Passed within 3.2 nm of the backtracked source region 5 hours before detection.",
      "sub_scores": {
        "environmental_consistency": 0.9,
        "distance": 0.85,
        "time_consistency": 0.7,
        "track_continuity": 0.8,
        "heading": 0.75,
        "speed": 0.6,
        "vessel_type": 1.0
      }
    }
  ]
}
```

- `confidence` is 0–100, always presented downstream as "probable attribution," never proof.
- `ranked_vessels` must already be sorted descending by `confidence` — the dashboard should not
  have to re-sort.
- `reason` is a single human-readable sentence generated from the top 1–2 contributing sub-scores.

## E. Final Merged Incident JSON (Integration → Dashboard)

This is what Phase 4's dashboard actually renders. It's assembled by combining A + B + D (Phase 2's
raw evidence is not needed downstream once Phase 3 has consumed it, but keeping `track` per vessel
is still useful for map rendering).

```json
{
  "incident": {
    "id": "SPILL-001",
    "detected_at": "2026-08-25T06:00:00Z",
    "area_km2": 3.2,
    "confidence": 0.87,
    "polygon": [
      [67.15, 20.45],
      [67.45, 20.75],
      [67.90, 20.62],
      [67.70, 20.30],
      [67.35, 20.25]
    ]
  },
  "environment": {
    "current_u_ms": 0.18,
    "current_v_ms": 0.07,
    "wind_speed_ms": 5.4,
    "wind_direction_deg": 72,
    "source_model": "Copernicus Marine"
  },
  "source_region": {
    "latitude": 20.48,
    "longitude": 67.52,
    "radius_km": 22,
    "backtrack_hours": 24
  },
  "vessels": [
    {
      "name": "MV Ocean Star",
      "mmsi": "419001234",
      "type": "Tanker",
      "confidence": 79,
      "reason": "Passed within 3.2 nm of the backtracked source region 5 hours before detection.",
      "position": [67.10, 20.15],
      "track": [
        [67.10, 20.15],
        [66.90, 20.00],
        [66.70, 19.85]
      ]
    }
  ]
}
```

- `incident.polygon`, `vessels[].position`, and `vessels[].track` here use **`[lon, lat]`**
  (GeoJSON order) to match Leaflet's `L.polygon`/`L.polyline` expectations directly — this is the
  one place a coordinate-order conversion happens, and it happens once, in the integration step,
  not inside any individual phase's own code.
- This is the exact shape Phase 4's dashboard is built against from minute one (as a dummy file),
  so wiring in the real thing later is a one-line `fetch()` URL change.
