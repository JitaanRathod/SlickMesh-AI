# Phase 4 — Environmental Data + Dashboard

**Owner:** Rudra (Person 4)
**Independence:** Two sub-parts, both independent of the other three phases. §A (environmental
research) is reference material anyone can consume later. §B (the dashboard) is built entirely
against a **dummy JSON file matching Contract E** — it never needs a real backend to be fully
demoable tonight.

---

## Part A — Environmental Data Sources

Environmental data answers one question: *"after release, where could wind and currents have
moved the oil?"* Needed: current direction/speed, wind speed/direction, waves, sea-surface
temperature, and a time+location to query them at.

### Source comparison

| Need | Primary | Backup |
|---|---|---|
| Ocean currents | Copernicus Marine (`uo`, `vo`, ~0.083°, hourly/daily/monthly, forecast updated daily) | NOAA ERDDAP |
| Wind | NOAA ERDDAP | Copernicus Marine wind product |
| Waves | NOAA ERDDAP | INCOIS |
| Indian coastal validation | INCOIS (buoys, HF radar, AVHRR SST — access varies by product, verify before promising direct download) | Copernicus Marine |
| SST | INCOIS or Copernicus | NOAA |

### Copernicus Marine access (primary source)

```bash
pip install copernicusmarine xarray netcdf4
copernicusmarine login
```

```python
import copernicusmarine
copernicusmarine.subset(
    dataset_id="VERIFY_DATASET_ID",   # confirm exact ID in the Copernicus portal before relying on it
    variables=["uo", "vo"],
    minimum_longitude=66.5, maximum_longitude=68.5,
    minimum_latitude=19.5, maximum_latitude=21.5,
    start_datetime="2026-08-25T00:00:00", end_datetime="2026-08-25T12:00:00",
    minimum_depth=0, maximum_depth=1,
    output_filename="copernicus_currents.nc",
)
```

⚠️ Dataset ID and exact variable names must be verified in the Copernicus portal before demo —
they change between products. If setup time runs short, Phase 2 (Jitaan) already has a documented
zero-setup fallback (Open-Meteo) — don't let this block the pipeline; feed real Copernicus data in
as a later swap (Contract B), not a prerequisite.

### Existing systems and where the gap is

| System | What it does | Gap we target |
|---|---|---|
| CleanSeaNet (EMSA) | Operational SAR + AIS + met/ocean fusion for European authorities | Not open, not India-focused, pipeline not public |
| Cerulean (SkyTruth) | Sentinel-1 U-Net + AIS candidate scoring by proximity/timing/alignment | Global tool, not tuned to Indian waters, not an open student dashboard |
| INCOIS | Indian Ocean environmental data provider | Not an end-to-end detection + attribution dashboard |

Our angle: `INCOIS environment data + Sentinel-1 oil mask + AIS vessel tracks + backtracking +
explainable dashboard`.

---

## Part B — Dashboard

### Output/Input contract — the dashboard's only dependency

Build entirely against this dummy file (`incident.json` — matches `API_CONTRACTS.md` §E exactly):

```json
{
  "incident": {
    "id": "SPILL-001", "detected_at": "2026-08-25T06:00:00Z",
    "area_km2": 3.2, "confidence": 0.87,
    "polygon": [[67.15,20.45],[67.45,20.75],[67.90,20.62],[67.70,20.30],[67.35,20.25]]
  },
  "environment": {
    "current_u_ms": 0.18, "current_v_ms": 0.07, "wind_speed_ms": 5.4,
    "wind_direction_deg": 72, "source_model": "Copernicus Marine"
  },
  "source_region": { "latitude": 20.48, "longitude": 67.52, "radius_km": 22, "backtrack_hours": 24 },
  "vessels": [
    {
      "name": "MV Ocean Star", "mmsi": "419001234", "type": "Tanker", "confidence": 86,
      "reason": "Passed near the backtracked source region",
      "position": [67.10, 20.15],
      "track": [[67.10,20.15],[66.90,20.00],[66.70,19.85]]
    }
  ]
}
```

### Tech choice: Leaflet

Free, no token, GeoJSON-native, sufficient for markers/polygons/polylines/popups — no reason to
reach for Mapbox or a heavier stack for a one-night prototype.

### File structure

```
phase4-dashboard/
├── index.html
├── style.css
└── app.js
```

### `index.html`

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SIH26143 Oil-Spill Dashboard</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>SIH26143 Oil-Spill Monitoring</h1>
    <p>Environmental Data + AIS Vessel Attribution</p>
  </header>
  <main>
    <section id="map"></section>
    <aside>
      <h2>Incident Summary</h2>
      <div class="card" id="incident-card"></div>
      <h2>Environmental Conditions</h2>
      <div class="card" id="env-card"></div>
      <h2>Ranked Candidate Vessels</h2>
      <div id="candidates"></div>
      <p class="warning">Attribution is probabilistic and does not prove legal responsibility.</p>
    </aside>
  </main>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="app.js"></script>
</body>
</html>
```

### `style.css`

```css
body { margin: 0; font-family: Arial, sans-serif; color: #172b4d; }
header { padding: 14px 20px; background: #0b2d4d; color: white; }
header h1 { margin: 0; font-size: 22px; }
header p { margin: 5px 0 0; }
main { display: grid; grid-template-columns: 1fr 350px; height: calc(100vh - 80px); }
#map { height: 100%; }
aside { padding: 16px; overflow-y: auto; background: white; box-shadow: -2px 0 8px #0002; }
.card, .candidate { padding: 12px; margin: 10px 0; border: 1px solid #dce3ec; border-radius: 8px; }
.candidate { border-left: 5px solid #2563eb; background: #f4f7fb; }
.flagged { border-left-color: #d92d20; }
.confidence { display: inline-block; margin-top: 6px; padding: 4px 8px; border-radius: 12px; background: #e6f4ea; color: #087443; }
.warning { color: #9b2c2c; font-size: 13px; }
@media (max-width: 800px) {
  main { display: block; height: auto; }
  #map { height: 60vh; }
  aside { height: auto; }
}
```

### `app.js` — fetches `incident.json`; this is the ONLY line to change when the real backend is ready

```javascript
fetch("incident.json")
  .then(r => r.json())
  .then(render);

function render(data) {
  const map = L.map("map").setView([data.source_region.latitude, data.source_region.longitude], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors"
  }).addTo(map);

  const spillLatLng = data.incident.polygon.map(([lon, lat]) => [lat, lon]);
  L.polygon(spillLatLng, { color: "#d92d20", fillColor: "#f04438", fillOpacity: 0.45, weight: 3 })
    .addTo(map)
    .bindPopup(`<b>Suspected oil spill</b><br>Area: ${data.incident.area_km2} km²<br>Confidence: ${Math.round(data.incident.confidence * 100)}%`);

  L.circle([data.source_region.latitude, data.source_region.longitude], {
    radius: data.source_region.radius_km * 1000, color: "#f79009", fill: false, dashArray: "8 8"
  }).addTo(map).bindTooltip("Probable backtracked source region");

  document.getElementById("incident-card").innerHTML = `
    <b>Status:</b> Suspected oil spill<br>
    <b>Area:</b> ${data.incident.area_km2} km²<br>
    <b>Detection confidence:</b> ${Math.round(data.incident.confidence * 100)}%`;

  document.getElementById("env-card").innerHTML = `
    <b>Wind:</b> ${data.environment.wind_speed_ms} m/s<br>
    <b>Current (u,v):</b> ${data.environment.current_u_ms}, ${data.environment.current_v_ms} m/s<br>
    <b>Source:</b> ${data.environment.source_model}`;

  const candidateBox = document.getElementById("candidates");
  data.vessels.forEach((v, i) => {
    const flagged = i === 0;
    const color = flagged ? "#d92d20" : "#2563eb";
    const track = v.track.map(([lon, lat]) => [lat, lon]);
    L.polyline(track, { color, weight: flagged ? 5 : 3 }).addTo(map)
      .bindPopup(`<b>${v.name}</b><br>Type: ${v.type}<br>MMSI: ${v.mmsi}<br>Confidence: ${v.confidence}%`);
    L.circleMarker([v.position[1], v.position[0]], { radius: flagged ? 9 : 6, color, fillColor: color, fillOpacity: 1 })
      .addTo(map).bindTooltip(v.name);
    candidateBox.innerHTML += `
      <div class="candidate ${flagged ? "flagged" : ""}">
        <b>${v.name}</b><br>Type: ${v.type}<br>MMSI: ${v.mmsi}<br>
        <span class="confidence">Confidence: ${v.confidence}%</span>
        <p>${v.reason}</p>
      </div>`;
  });

  map.fitBounds(L.polygon(spillLatLng).getBounds().pad(0.8));
}
```

### Run it

```bash
python -m http.server 8000
# open http://localhost:8000
```

### Handoff checklist for tomorrow evening

- [ ] Confirm the dashboard renders correctly from the dummy `incident.json` above with zero
      errors before touching real data.
- [ ] When Integration hands you a real assembled Contract E file/endpoint, change only the
      `fetch("incident.json")` URL in `app.js` — nothing else should need editing.
- [ ] Add a legend, a "why this vessel" popup, and colour polish only after the data path works —
      never before.

## Time budget

Tonight: dummy-data dashboard fully working end to end (this is the safest possible fallback —
protect it). Tomorrow morning: environmental source verification (confirm real dataset IDs).
Tomorrow afternoon: wire in real Contract E. Tomorrow evening: polish (legend, popups, colours)
only if the data path is solid.
