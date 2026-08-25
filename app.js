let map;
let layersGroup;
let currentIncidentData = null;

// Default values for target locations to make the demo realistic
const locationPresets = {
  mumbai: {
    image: "s1_mumbai_offshore.png",
    current_u: 0.12,
    current_v: -0.15,
    wind_speed: 6.8,
    wind_dir: 240,
    backtrack: 18,
    name: "Arabian Sea (Mumbai Offshore)"
  },
  bob: {
    image: "s1_kg_basin.png",
    current_u: -0.25,
    current_v: 0.10,
    wind_speed: 8.2,
    wind_dir: 110,
    backtrack: 24,
    name: "Bay of Bengal (KG Basin)"
  },
  default: {
    image: "s1_active.png",
    current_u: 0.18,
    current_v: 0.07,
    wind_speed: 5.4,
    wind_dir: 72,
    backtrack: 24,
    name: "Alang Offshore"
  }
};

document.addEventListener("DOMContentLoaded", () => {
  initMap();
  initSliders();
  setupEventListeners();
  
  // Proactively fetch mock-incident on load to populate screen
  fetchIncidentData("api/mock-incident");
});

function initMap() {
  map = L.map("map").setView([20.48, 67.52], 7);
  
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors"
  }).addTo(map);
  
  layersGroup = L.layerGroup().addTo(map);
}

function initSliders() {
  const sliders = [
    { id: "wind-speed", valId: "wind-speed-val", suffix: " m/s" },
    { id: "wind-dir", valId: "wind-dir-val", suffix: "°" },
    { id: "current-u", valId: "current-u-val", suffix: " m/s" },
    { id: "current-v", valId: "current-v-val", suffix: " m/s" },
    { id: "backtrack-hours", valId: "backtrack-hours-val", suffix: " hrs" }
  ];
  
  sliders.forEach(slider => {
    const el = document.getElementById(slider.id);
    const valEl = document.getElementById(slider.valId);
    
    if (el && valEl) {
      el.addEventListener("input", (e) => {
        valEl.textContent = e.target.value + slider.suffix;
      });
    }
  });
}

function setupEventListeners() {
  // Run button
  const runBtn = document.getElementById("run-pipeline-btn");
  runBtn.addEventListener("click", triggerPipeline);
  
  // Preset selector
  const presetSelect = document.getElementById("sample-location");
  presetSelect.addEventListener("change", (e) => {
    applyPreset(e.target.value);
  });
  
  // File mock upload interaction
  const uploadBox = document.getElementById("upload-box");
  const fileLabel = document.getElementById("selected-file-label");
  uploadBox.addEventListener("click", () => {
    // Cycles between images for demo
    const currentImg = fileLabel.textContent;
    let nextImg = "s1_active.png";
    if (currentImg === "s1_active.png") {
      nextImg = "s1_mumbai_offshore.png";
    } else if (currentImg === "s1_mumbai_offshore.png") {
      nextImg = "s1_kg_basin.png";
    }
    fileLabel.textContent = nextImg;
  });

  // Modal close
  document.getElementById("close-modal-btn").addEventListener("click", closeModal);
  window.addEventListener("click", (e) => {
    const modal = document.getElementById("details-modal");
    if (e.target === modal) {
      closeModal();
    }
  });
}

function applyPreset(presetKey) {
  const preset = locationPresets[presetKey];
  if (!preset) return;
  
  // Update inputs
  document.getElementById("selected-file-label").textContent = preset.image;
  
  document.getElementById("wind-speed").value = preset.wind_speed;
  document.getElementById("wind-speed-val").textContent = preset.wind_speed + " m/s";
  
  document.getElementById("wind-dir").value = preset.wind_dir;
  document.getElementById("wind-dir-val").textContent = preset.wind_dir + "°";
  
  document.getElementById("current-u").value = preset.current_u;
  document.getElementById("current-u-val").textContent = preset.current_u + " m/s";
  
  document.getElementById("current-v").value = preset.current_v;
  document.getElementById("current-v-val").textContent = preset.current_v + " m/s";
  
  document.getElementById("backtrack-hours").value = preset.backtrack;
  document.getElementById("backtrack-hours-val").textContent = preset.backtrack + " hrs";
}

function triggerPipeline() {
  const runBtn = document.getElementById("run-pipeline-btn");
  runBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing pipeline...';
  runBtn.disabled = true;
  
  const payload = {
    image_name: document.getElementById("selected-file-label").textContent,
    wind_speed: parseFloat(document.getElementById("wind-speed").value),
    wind_direction: parseFloat(document.getElementById("wind-dir").value),
    current_u: parseFloat(document.getElementById("current-u").value),
    current_v: parseFloat(document.getElementById("current-v").value),
    backtrack_hours: parseInt(document.getElementById("backtrack-hours").value)
  };
  
  fetch("/api/run-pipeline", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
  .then(res => {
    if (!res.ok) throw new Error("Pipeline computation failed.");
    return res.json();
  })
  .then(data => {
    renderIncident(data);
  })
  .catch(err => {
    alert(err.message + " Running local mock visualization instead.");
    fetchIncidentData("/api/mock-incident");
  })
  .finally(() => {
    runBtn.innerHTML = '<i class="fa-solid fa-play"></i> Run Spill Pipeline';
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
  
  // 1. Plot Spill Polygon
  const spillLatLng = data.incident.polygon.map(([lon, lat]) => [lat, lon]);
  const spillPoly = L.polygon(spillLatLng, {
    color: "#ef4444",
    fillColor: "#ef4444",
    fillOpacity: 0.45,
    weight: 3
  }).addTo(layersGroup);
  
  spillPoly.bindPopup(`
    <div style="color:#0f172a; font-family:'Inter', sans-serif;">
      <strong>Spill ID:</strong> ${data.incident.id}<br>
      <strong>Area:</strong> ${data.incident.area_km2} km²<br>
      <strong>Confidence:</strong> ${Math.round(data.incident.confidence * 100)}%<br>
      <strong>Detected:</strong> ${data.incident.detected_at}
    </div>
  `);
  
  // 2. Plot Backtracked Source region
  const sourceReg = data.source_region;
  const sourceCircle = L.circle([sourceReg.latitude, sourceReg.longitude], {
    radius: sourceReg.radius_km * 1000,
    color: "#f59e0b",
    weight: 2,
    dashArray: "6 6",
    fillColor: "#f59e0b",
    fillOpacity: 0.08
  }).addTo(layersGroup);
  
  sourceCircle.bindTooltip(`Probable backtracked origin (Uncertainty: ${sourceReg.radius_km}km)`);
  
  // 3. Update Text Details
  document.getElementById("incident-card").innerHTML = `
    <div><strong>Incident ID:</strong> ${data.incident.id}</div>
    <div><strong>Detected At:</strong> ${data.incident.detected_at}</div>
    <div><strong>Area:</strong> ${data.incident.area_km2} km²</div>
    <div><strong>Detection Confidence:</strong> <span style="color:var(--success);font-weight:bold;">${Math.round(data.incident.confidence * 100)}%</span></div>
  `;
  
  document.getElementById("env-card").innerHTML = `
    <div><strong>Wind:</strong> ${data.environment.wind_speed_ms} m/s at ${data.environment.wind_direction_deg}°</div>
    <div><strong>Current Vector (u, v):</strong> ${data.environment.current_u_ms}, ${data.environment.current_v_ms} m/s</div>
    <div><strong>Primary Model:</strong> ${data.environment.source_model}</div>
  `;
  
  // 4. Plot Vessels
  const candsContainer = document.getElementById("candidates");
  candsContainer.innerHTML = "";
  
  if (data.vessels.length === 0) {
    candsContainer.innerHTML = '<div class="empty-state">No candidate vessels matched coordinates</div>';
  }
  
  data.vessels.forEach((v, index) => {
    const isFirst = index === 0;
    const color = isFirst ? "#ef4444" : "#3b82f6"; // Flagged primary suspect is red, others blue
    
    // Draw vessel final/closest marker
    L.circleMarker([v.position[1], v.position[0]], {
      radius: isFirst ? 8 : 6,
      color: color,
      fillColor: color,
      fillOpacity: 1,
      weight: 2
    }).addTo(layersGroup).bindTooltip(`<b>${v.name}</b><br>MMSI: ${v.mmsi}`);
    
    // Draw Track
    const trackLatLngs = v.track.map(([lon, lat]) => [lat, lon]);
    const trackPoly = L.polyline(trackLatLngs, {
      color: color,
      weight: isFirst ? 4 : 2,
      dashArray: isFirst ? null : "4 4"
    }).addTo(layersGroup);
    
    // Add arrow heads / direction overlays (optional helper)
    trackPoly.bindPopup(`
      <div style="color:#0f172a; font-family:'Inter', sans-serif;">
        <strong>${v.name}</strong> (${v.type})<br>
        <strong>MMSI:</strong> ${v.mmsi}<br>
        <strong>Attribution:</strong> ${v.confidence}%<br>
        <p style="margin-top:5px; font-size:11px;">${v.reason}</p>
      </div>
    `);
    
    // Append Sidebar Card
    const cardEl = document.createElement("div");
    cardEl.className = `candidate-card ${isFirst ? "flagged" : ""}`;
    cardEl.innerHTML = `
      <div class="cand-header">
        <span class="cand-name">${v.name}</span>
        <span class="cand-conf">${v.confidence}%</span>
      </div>
      <div class="cand-desc">${v.reason}</div>
      <span class="view-details-link">Analyze details &rarr;</span>
    `;
    
    cardEl.addEventListener("click", () => showVesselDetails(v));
    candsContainer.appendChild(cardEl);
  });
  
  // Adjust Map view boundary to fit both spill and source corridor
  const bounds = L.featureGroup([spillPoly, sourceCircle]).getBounds();
  map.fitBounds(bounds.pad(0.2));
}

function showVesselDetails(vessel) {
  document.getElementById("modal-vessel-name").textContent = vessel.name;
  document.getElementById("modal-mmsi").textContent = vessel.mmsi;
  document.getElementById("modal-type").textContent = vessel.type;
  document.getElementById("modal-conf").textContent = vessel.confidence;
  document.getElementById("modal-reason-str").textContent = vessel.reason;
  
  const scoreContainer = document.getElementById("score-bars-container");
  scoreContainer.innerHTML = "";
  
  const labelMap = {
    distance: "Backtrack Proximity (Distance)",
    time_consistency: "Temporal Window Alignment",
    speed: "SOG / Speed Profile",
    heading: "Heading & Drift Angle",
    vessel_type: "Vessel Classification Multiplier",
    environmental_consistency: "Drift Corridor Intersection"
  };
  
  // Populate progress bars
  Object.keys(vessel.sub_scores).forEach(key => {
    if (key === "track_continuity") return; // Skip minor metric
    const scoreVal = vessel.sub_scores[key];
    const pct = Math.round(scoreVal * 100);
    const label = labelMap[key] || key;
    
    const row = document.createElement("div");
    row.className = "score-row";
    row.innerHTML = `
      <div class="score-lbl">
        <span>${label}</span>
        <strong>${pct}%</strong>
      </div>
      <div class="score-bar-bg">
        <div class="score-bar-fg" style="width: 0%"></div>
      </div>
    `;
    
    scoreContainer.appendChild(row);
    
    // Trigger animation frame for progress width
    setTimeout(() => {
      row.querySelector(".score-bar-fg").style.width = pct + "%";
    }, 50);
  });
  
  // Display Modal
  document.getElementById("details-modal").style.display = "flex";
}

function closeModal() {
  document.getElementById("details-modal").style.display = "none";
}
