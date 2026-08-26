let map;
let layersGroup;
let currentIncidentData = null;

// Compass direction helper
function degToCompass(num) {
  const val = Math.floor((num / 22.5) + 0.5);
  const arr = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  return arr[(val % 16)];
}

// Default presets for Indian Maritime Surveillance Zones
const locationPresets = {
  mumbai: {
    image: "s1_mumbai_high.png",
    current_u: 0.12,
    current_v: -0.15,
    wind_speed: 6.8,
    wind_dir: 240,
    backtrack: 18,
    name: "Arabian Sea (Mumbai High Oilfield)"
  },
  bob: {
    image: "s1_kg_basin.png",
    current_u: -0.25,
    current_v: 0.10,
    wind_speed: 8.2,
    wind_dir: 110,
    backtrack: 24,
    name: "Bay of Bengal (KG Deepwater Basin)"
  },
  default: {
    image: "s1_active.png",
    current_u: 0.18,
    current_v: 0.07,
    wind_speed: 5.4,
    wind_dir: 72,
    backtrack: 24,
    name: "Gulf of Khambhat (Alang Anchorage)"
  },
  dark_ship: {
    image: "s1_dark_ship.png",
    current_u: 0.15,
    current_v: -0.08,
    wind_speed: 7.2,
    wind_dir: 275,
    backtrack: 24,
    name: "Arabian Sea (AIS Blackout Scenario)"
  }
};

document.addEventListener("DOMContentLoaded", () => {
  initMap();
  initSliders();
  setupEventListeners();
  
  // Proactively fetch initial incident data on load
  fetchIncidentData("/api/mock-incident");
});

function initMap() {
  map = L.map("map", {
    zoomControl: true,
    attributionControl: false
  }).setView([20.48, 67.52], 7);
  
  // High-contrast clean dark carto tiles suitable for maritime tactical displays
  L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    maxZoom: 18,
    subdomains: "abcd"
  }).addTo(map);
  
  layersGroup = L.layerGroup().addTo(map);
}

function initSliders() {
  const updateLabels = () => {
    const ws = parseFloat(document.getElementById("wind-speed").value);
    const wd = parseInt(document.getElementById("wind-dir").value);
    const cu = parseFloat(document.getElementById("current-u").value);
    const cv = parseFloat(document.getElementById("current-v").value);
    const bt = parseInt(document.getElementById("backtrack-hours").value);

    document.getElementById("wind-speed-val").textContent = `${ws.toFixed(1)} m/s`;
    document.getElementById("wind-dir-val").textContent = `${wd}° (${degToCompass(wd)})`;
    document.getElementById("current-u-val").textContent = `${cu >= 0 ? '+' : ''}${cu.toFixed(2)} m/s`;
    document.getElementById("current-v-val").textContent = `${cv >= 0 ? '+' : ''}${cv.toFixed(2)} m/s`;
    document.getElementById("backtrack-hours-val").textContent = `${bt} hrs`;
  };

  ["wind-speed", "wind-dir", "current-u", "current-v", "backtrack-hours"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", updateLabels);
  });

  updateLabels();
}

function setupEventListeners() {
  // Run pipeline button
  const runBtn = document.getElementById("run-pipeline-btn");
  if (runBtn) runBtn.addEventListener("click", triggerPipeline);
  
  // Preset location dropdown
  const presetSelect = document.getElementById("sample-location");
  if (presetSelect) {
    presetSelect.addEventListener("change", (e) => {
      applyPreset(e.target.value);
    });
  }
  
  // Image switcher / upload trigger
  const uploadBox = document.getElementById("upload-box");
  const fileLabel = document.getElementById("selected-file-label");
  if (uploadBox && fileLabel) {
    uploadBox.addEventListener("click", () => {
      const currentImg = fileLabel.textContent;
      const scenes = ["s1_active.png", "s1_mumbai_high.png", "s1_kg_basin.png", "real_grande_america_spill.jpg"];
      let nextIndex = (scenes.indexOf(currentImg) + 1) % scenes.length;
      fileLabel.textContent = scenes[nextIndex];
    });
  }

  // Modal close events
  const closeBtn = document.getElementById("close-modal-btn");
  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  
  window.addEventListener("click", (e) => {
    const modal = document.getElementById("details-modal");
    if (e.target === modal) closeModal();
  });
}

function applyPreset(presetKey) {
  const preset = locationPresets[presetKey] || locationPresets.default;
  
  document.getElementById("selected-file-label").textContent = preset.image;
  document.getElementById("wind-speed").value = preset.wind_speed;
  document.getElementById("wind-dir").value = preset.wind_dir;
  document.getElementById("current-u").value = preset.current_u;
  document.getElementById("current-v").value = preset.current_v;
  document.getElementById("backtrack-hours").value = preset.backtrack;

  // Re-trigger label updates
  const event = new Event("input");
  document.getElementById("wind-speed").dispatchEvent(event);
}

function triggerPipeline() {
  const runBtn = document.getElementById("run-pipeline-btn");
  runBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing Satellite & AIS Feeds...';
  runBtn.disabled = true;
  
  const payload = {
    image_name: document.getElementById("selected-file-label").textContent,
    wind_speed: parseFloat(document.getElementById("wind-speed").value),
    wind_direction: parseFloat(document.getElementById("wind-dir").value),
    current_u: parseFloat(document.getElementById("current-u").value),
    current_v: parseFloat(document.getElementById("current-v").value),
    backtrack_hours: parseInt(document.getElementById("backtrack-hours").value),
    target_region: document.getElementById("sample-location").value
  };
  
  fetch("/api/run-pipeline", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
  .then(res => {
    if (!res.ok) throw new Error("Pipeline computation failed on server.");
    return res.json();
  })
  .then(data => {
    renderIncident(data);
  })
  .catch(err => {
    console.warn(err.message + " Loading fallback local telemetry.");
    fetchIncidentData("/api/mock-incident");
  })
  .finally(() => {
    runBtn.innerHTML = '<i class="fa-solid fa-play"></i> Run Surveillance Pipeline';
    runBtn.disabled = false;
  });
}

function fetchIncidentData(url) {
  fetch(url)
    .then(r => r.json())
    .then(renderIncident)
    .catch(console.error);
}

function renderIncident(data) {
  currentIncidentData = data;
  layersGroup.clearLayers();
  
  const mapFeaturesToBound = [];

  // 1. Plot Detected Satellite Oil Slick Polygon (Red)
  if (data.incident && data.incident.polygon) {
    const spillLatLng = data.incident.polygon.map(([lon, lat]) => [lat, lon]);
    const spillPoly = L.polygon(spillLatLng, {
      color: "#dc2626",
      fillColor: "#ef4444",
      fillOpacity: 0.55,
      weight: 2.5
    }).addTo(layersGroup);
    
    spillPoly.bindPopup(`
      <div class="map-popup">
        <div class="popup-title"><i class="fa-solid fa-triangle-exclamation text-red"></i> Detected SAR Oil Slick</div>
        <table class="popup-table">
          <tr><td>Incident ID:</td><td><strong>${data.incident.id}</strong></td></tr>
          <tr><td>Slick Area:</td><td><strong>${data.incident.area_km2} km²</strong></td></tr>
          <tr><td>AI Confidence:</td><td><strong>${Math.round(data.incident.confidence * 100)}%</strong></td></tr>
          <tr><td>Timestamp:</td><td>${data.incident.detected_at}</td></tr>
        </table>
      </div>
    `);
    mapFeaturesToBound.push(spillPoly);
  }
  
  // 2. Plot Backtracked Origin Corridor (Yellow Dotted Uncertainty Circle)
  if (data.source_region) {
    const sourceReg = data.source_region;
    const sourceCircle = L.circle([sourceReg.latitude, sourceReg.longitude], {
      radius: sourceReg.radius_km * 1000,
      color: "#d97706",
      weight: 2,
      dashArray: "6, 6",
      fillColor: "#f59e0b",
      fillOpacity: 0.12
    }).addTo(layersGroup);
    
    sourceCircle.bindTooltip(
      `<strong>Estimated Origin Region</strong><br>Radius: ${sourceReg.radius_km} km (Backtracked ${sourceReg.backtrack_hours}h)`,
      { sticky: true }
    );
    mapFeaturesToBound.push(sourceCircle);
  }
  
  // 3. Update Incident Telemetry UI Card
  document.getElementById("incident-card").innerHTML = `
    <div class="telemetry-grid">
      <div class="tel-cell"><span class="tel-lbl">SPILL ID</span><span class="tel-val">${data.incident.id}</span></div>
      <div class="tel-cell"><span class="tel-lbl">SLICK EXTENT</span><span class="tel-val">${data.incident.area_km2} km²</span></div>
      <div class="tel-cell"><span class="tel-lbl">DETECTION CONFIDENCE</span><span class="tel-val text-green">${Math.round(data.incident.confidence * 100)}%</span></div>
      <div class="tel-cell"><span class="tel-lbl">ORIGIN UNCERTAINTY</span><span class="tel-val">${data.source_region.radius_km} km</span></div>
    </div>
  `;
  
  // 4. Update Environmental Metocean Feed UI Card
  const env = data.environment;
  document.getElementById("env-card").innerHTML = `
    <div class="telemetry-grid">
      <div class="tel-cell"><span class="tel-lbl">WIND SPEED / DIR</span><span class="tel-val">${env.wind_speed_ms} m/s @ ${env.wind_direction_deg}°</span></div>
      <div class="tel-cell"><span class="tel-lbl">DRIFT VECTOR (U, V)</span><span class="tel-val">${env.current_u_ms}, ${env.current_v_ms} m/s</span></div>
      <div class="tel-cell" style="grid-column: span 2;"><span class="tel-lbl">FEED PROVIDER</span><span class="tel-val text-cyan">${env.source_model}</span></div>
    </div>
  `;
  
  // 5. Plot ALL Candidate Vessels & Trajectories
  const candsContainer = document.getElementById("candidates");
  candsContainer.innerHTML = "";
  
  const vessels = data.vessels || [];
  document.getElementById("vessel-count-badge").textContent = `${vessels.length} vessels`;

  if (vessels.length === 0) {
    candsContainer.innerHTML = '<div class="empty-state">No candidate vessels traversed this sector</div>';
  }
  
  vessels.forEach((v, index) => {
    const isPrimary = index === 0;
    const color = isPrimary ? "#dc2626" : "#2563eb"; // Suspect #1 in Red, secondary in Navy/Blue
    const strokeWidth = isPrimary ? 3.5 : 2.0;
    const dashStyle = isPrimary ? null : "5, 5";
    
    // Draw vessel marker at closest/current position
    const vLat = v.position[1];
    const vLon = v.position[0];
    
    const vesselMarker = L.circleMarker([vLat, vLon], {
      radius: isPrimary ? 8 : 6,
      color: color,
      fillColor: isPrimary ? "#ef4444" : "#60a5fa",
      fillOpacity: 1,
      weight: 2
    }).addTo(layersGroup);
    
    vesselMarker.bindTooltip(
      `<strong>#${index + 1}: ${v.name}</strong> (${v.type})<br>Attribution Score: ${v.confidence}%`,
      { direction: "top" }
    );
    mapFeaturesToBound.push(vesselMarker);
    
    // Draw AIS Track Polyline
    if (v.track && v.track.length > 0) {
      const trackLatLngs = v.track.map(([lon, lat]) => [lat, lon]);
      const trackPoly = L.polyline(trackLatLngs, {
        color: color,
        weight: strokeWidth,
        dashArray: dashStyle,
        opacity: isPrimary ? 0.95 : 0.75
      }).addTo(layersGroup);
      
      trackPoly.bindPopup(`
        <div class="map-popup">
          <div class="popup-title"><strong>${v.name}</strong> (${v.type})</div>
          <table class="popup-table">
            <tr><td>MMSI:</td><td>${v.mmsi}</td></tr>
            <tr><td>Confidence:</td><td><strong style="color:${isPrimary ? '#dc2626' : '#2563eb'}">${v.confidence}%</strong></td></tr>
            <tr><td>Assessment:</td><td>${v.reason}</td></tr>
          </table>
        </div>
      `);
      mapFeaturesToBound.push(trackPoly);
    }
    
    // Append Ranked Candidate Card in Sidebar
    const cardEl = document.createElement("div");
    cardEl.className = `candidate-card ${isPrimary ? "primary-suspect" : ""}`;
    cardEl.innerHTML = `
      <div class="cand-top-row">
        <div class="cand-rank-name">
          <span class="rank-num">#${index + 1}</span>
          <span class="vessel-title">${v.name}</span>
        </div>
        <span class="cand-score-pill ${isPrimary ? 'pill-danger' : 'pill-info'}">${v.confidence}%</span>
      </div>
      <div class="cand-type-mmsi"><i class="fa-solid fa-ship"></i> ${v.type} • MMSI ${v.mmsi}</div>
      <div class="cand-reason-snippet">${v.reason}</div>
      <div class="cand-footer">
        <span class="view-analysis-btn"><i class="fa-solid fa-chart-simple"></i> View Evidence Breakdown &rarr;</span>
      </div>
    `;
    
    cardEl.addEventListener("click", () => showVesselDetails(v, index));
    candsContainer.appendChild(cardEl);
  });
  
  // 6. Dynamically fit map bounds to enclose ALL vessels, the spill, and the corridor!
  if (mapFeaturesToBound.length > 0) {
    const allBounds = L.featureGroup(mapFeaturesToBound).getBounds();
    map.fitBounds(allBounds.pad(0.18));
  }
}

function showVesselDetails(vessel, rankIndex) {
  document.getElementById("modal-vessel-name").textContent = vessel.name;
  document.getElementById("modal-type-mmsi").textContent = `${vessel.type} • MMSI: ${vessel.mmsi}`;
  document.getElementById("modal-conf").textContent = `${vessel.confidence}%`;
  
  const verdictEl = document.getElementById("modal-verdict");
  if (rankIndex === 0 && vessel.confidence >= 70) {
    verdictEl.textContent = "PRIMARY DISCHARGE SUSPECT";
    verdictEl.className = "conf-verdict verdict-danger";
  } else if (vessel.confidence >= 50) {
    verdictEl.textContent = "CORRIDOR PROXIMITY CANDIDATE";
    verdictEl.className = "conf-verdict verdict-warning";
  } else {
    verdictEl.textContent = "LOW PROBABILITY TRANSIT";
    verdictEl.className = "conf-verdict verdict-low";
  }

  document.getElementById("modal-reason-str").textContent = vessel.reason;
  
  const scoreContainer = document.getElementById("score-bars-container");
  scoreContainer.innerHTML = "";
  
  const labelMap = {
    environmental_consistency: "Metocean Drift Corridor Intersection",
    distance: "Backtrack Proximity (CPA Distance)",
    time_consistency: "Temporal Window Alignment",
    track_continuity: "AIS Signal Broadcast Continuity",
    heading: "Slick Alignment / Drift Delta Angle",
    speed: "SOG Speed Profile Consistency",
    vessel_type: "Vessel Risk & Cargo Classification"
  };
  
  if (vessel.sub_scores) {
    Object.keys(vessel.sub_scores).forEach(key => {
      const scoreVal = vessel.sub_scores[key];
      const pct = Math.round(scoreVal * 100);
      const label = labelMap[key] || key;
      
      const row = document.createElement("div");
      row.className = "score-row";
      row.innerHTML = `
        <div class="score-lbl">
          <span>${label}</span>
          <strong class="score-pct-val">${pct}%</strong>
        </div>
        <div class="score-track">
          <div class="score-fill" style="width: 0%"></div>
        </div>
      `;
      
      scoreContainer.appendChild(row);
      
      setTimeout(() => {
        const fillBar = row.querySelector(".score-fill");
        if (fillBar) fillBar.style.width = pct + "%";
      }, 50);
    });
  }
  
  document.getElementById("details-modal").style.display = "flex";
}

function closeModal() {
  document.getElementById("details-modal").style.display = "none";
}

