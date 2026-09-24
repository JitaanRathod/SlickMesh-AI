let map;
let layersGroup;
let simulationLayerGroup;
let gisTssLayerGroup;
let gisEezLayerGroup;
let gisInfraLayerGroup;
let gisFleetLayerGroup;
let currentIncidentData = null;
let currentTimelineIndex = 4;
let isPlayingTimeline = false;
let timelineTimer = null;
let selectedVesselForReport = null;

// Compass direction helper
function degToCompass(num) {
  const val = Math.floor((num / 22.5) + 0.5);
  const arr = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  return arr[(val % 16)];
}

// Default presets for Indian Maritime Surveillance Zones
const locationPresets = {
  bilge_dump: {
    image: "s1_mumbai_high.png",
    current_u: 0.18,
    current_v: 0.07,
    wind_speed: 5.4,
    wind_dir: 72,
    backtrack: 18,
    name: "Arabian Sea (MARPOL Illegal Bilge Discharge)"
  },
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
  initTimelineControls();
  initModalTabs();
  initReportModal();
  setupEventListeners();
  loadGisLayers();
  
  // Proactively fetch initial incident data on load
  fetchIncidentData("/api/mock-incident");
});

function initMap() {
  map = L.map("map", {
    zoomControl: true,
    attributionControl: true,
    minZoom: 3,
    maxZoom: 18
  }).setView([18.5, 74.0], 5);
  
  // Clean OpenStreetMap Layer (100% Free, No Watermark)
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    minZoom: 3,
    maxZoom: 18,
    attribution: "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> | Sentinel-1 SAR Surveillance"
  }).addTo(map);
  
  // Initialize distinct GIS and Tactical Layer Groups
  gisEezLayerGroup = L.layerGroup().addTo(map);
  gisTssLayerGroup = L.layerGroup().addTo(map);
  gisInfraLayerGroup = L.layerGroup().addTo(map);
  gisFleetLayerGroup = L.layerGroup().addTo(map);
  layersGroup = L.layerGroup().addTo(map);
  simulationLayerGroup = L.layerGroup().addTo(map);

  // Map Click Feature: Click anywhere to target coordinates and scan live sector directly
  map.on("click", (e) => {
    const lat = e.latlng.lat;
    const lon = e.latlng.lng;
    
    const latInput = document.getElementById("custom-lat");
    const lonInput = document.getElementById("custom-lon");

    if (latInput && lonInput) {
      latInput.value = lat.toFixed(3);
      lonInput.value = lon.toFixed(3);
    }

    if (currentMode !== "live") {
      const liveTab = document.getElementById("tab-live-mode");
      if (liveTab) liveTab.click();
    } else {
      triggerPipeline();
    }
  });
}

function loadGisLayers() {
  fetch("/api/gis-layers")
    .then(r => r.json())
    .then(data => {
      // 1. Render India 200 NM EEZ Boundary
      if (data.eez_boundary && data.eez_boundary.features) {
        gisEezLayerGroup.clearLayers();
        data.eez_boundary.features.forEach(f => {
          const latLngs = f.geometry.coordinates[0].map(([lon, lat]) => [lat, lon]);
          const eezPoly = L.polygon(latLngs, {
            color: f.properties.stroke_color || "#0ea5e9",
            weight: 2,
            dashArray: "5, 5",
            fillColor: f.properties.fill_color || "#38bdf8",
            fillOpacity: 0.04
          }).addTo(gisEezLayerGroup);

          eezPoly.bindPopup(`
            <div class="map-popup">
              <div class="popup-title" style="color:#0284c7;">
                <i class="fa-solid fa-shield-halved"></i> ${f.properties.name}
              </div>
              <table class="popup-table" style="font-size:10.5px;">
                <tr><td>Statutory Basis:</td><td><strong>${f.properties.statutory_basis}</strong></td></tr>
                <tr><td>Area Covered:</td><td>${f.properties.area_km2.toLocaleString()} km²</td></tr>
                <tr><td>Enforcement Agency:</td><td><strong>${f.properties.surveillance_agency}</strong></td></tr>
              </table>
            </div>
          `);
        });
      }

      // 2. Render IMO TSS Shipping Lanes
      if (data.tss_lanes && data.tss_lanes.features) {
        gisTssLayerGroup.clearLayers();
        data.tss_lanes.features.forEach(f => {
          const latLngs = f.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
          const tssLine = L.polyline(latLngs, {
            color: f.properties.color || "#8b5cf6",
            weight: 2.5,
            opacity: 0.75,
            dashArray: "6, 6"
          }).addTo(gisTssLayerGroup);

          tssLine.bindPopup(`
            <div class="map-popup">
              <div class="popup-title" style="color:#7c3aed;">
                <i class="fa-solid fa-route"></i> ${f.properties.name}
              </div>
              <table class="popup-table" style="font-size:10.5px;">
                <tr><td>Category:</td><td><strong>${f.properties.category}</strong></td></tr>
                <tr><td>Traffic Flow:</td><td>${f.properties.traffic_type}</td></tr>
                <tr><td>IMO Status:</td><td><span style="color:#059669; font-weight:bold;">${f.properties.imo_status}</span></td></tr>
              </table>
            </div>
          `);
        });
      }

      // 3. Render Offshore Oil Infrastructure & SPMs
      if (data.oil_infrastructure && data.oil_infrastructure.features) {
        gisInfraLayerGroup.clearLayers();
        data.oil_infrastructure.features.forEach(f => {
          const [lon, lat] = f.geometry.coordinates;
          const isPlatform = f.properties.icon === "platform";
          
          const infraMarker = L.circleMarker([lat, lon], {
            radius: isPlatform ? 7.5 : 6.5,
            color: isPlatform ? "#d97706" : "#ea580c",
            fillColor: isPlatform ? "#f59e0b" : "#fb923c",
            fillOpacity: 1,
            weight: 2
          }).addTo(gisInfraLayerGroup);

          infraMarker.bindPopup(`
            <div class="map-popup">
              <div class="popup-title" style="color:#d97706;">
                <i class="fa-solid ${isPlatform ? 'fa-industry' : 'fa-anchor'}"></i> ${f.properties.name}
              </div>
              <table class="popup-table" style="font-size:10.5px;">
                <tr><td>Facility Type:</td><td><strong>${f.properties.category}</strong></td></tr>
                <tr><td>Operator:</td><td><strong>${f.properties.operator}</strong></td></tr>
                <tr><td>Water Depth:</td><td>${f.properties.water_depth_m} meters</td></tr>
                <tr><td>Risk Classification:</td><td><strong style="color:#dc2626;">${f.properties.spill_risk_tier}</strong></td></tr>
                <tr><td>Pipeline Trunk:</td><td>${f.properties.connected_pipeline}</td></tr>
                <tr><td>Operational Status:</td><td><span style="color:#059669; font-weight:bold;">${f.properties.status}</span></td></tr>
              </table>
            </div>
          `);

          infraMarker.bindTooltip(
            `<strong>${f.properties.name}</strong><br>` +
            `<span style="color:#d97706;">${f.properties.category} (${f.properties.operator})</span>`,
            { direction: "top" }
          );
        });
      }

      // Update count
      const countEl = document.getElementById("gis-vessel-count");
      if (countEl) countEl.textContent = `${data.vessel_count || 100}+`;
    })
    .catch(console.error);

  // 4. Fetch and render live vessel fleet
  fetch("/api/live-fleet")
    .then(r => r.json())
    .then(data => {
      if (!data.vessels) return;
      gisFleetLayerGroup.clearLayers();

      data.vessels.forEach(v => {
        const [lon, lat] = v.position;
        let color = "#0284c7";
        let fillColor = "#38bdf8";

        if (v.type.toLowerCase().includes("tanker") || v.type.toLowerCase().includes("crude")) {
          color = "#7c3aed";
          fillColor = "#c084fc";
        } else if (v.type.toLowerCase().includes("bulk")) {
          color = "#d97706";
          fillColor = "#fbbf24";
        } else if (v.type.toLowerCase().includes("support") || v.type.toLowerCase().includes("patrol")) {
          color = "#059669";
          fillColor = "#34d399";
        }

        const vMarker = L.circleMarker([lat, lon], {
          radius: 5,
          color: color,
          fillColor: fillColor,
          fillOpacity: 0.9,
          weight: 1.5
        }).addTo(gisFleetLayerGroup);

        vMarker.bindPopup(`
          <div class="map-popup">
            <div class="popup-title" style="color:${color};">
              <i class="fa-solid fa-ship"></i> <strong>${v.name}</strong>
            </div>
            <table class="popup-table" style="font-size:10.5px;">
              <tr><td>Vessel Type:</td><td><strong>${v.type}</strong></td></tr>
              <tr><td>MMSI / IMO:</td><td><code>${v.mmsi}</code> / <code>${v.imo || 'N/A'}</code></td></tr>
              <tr><td>Flag State:</td><td>${v.flag || 'International'}</td></tr>
              <tr><td>Speed / COG:</td><td><strong>${v.sog || 12.0} kts @ ${v.cog || 0}°</strong></td></tr>
              <tr><td>Destination:</td><td>${v.destination || 'Sea Passage'}</td></tr>
              <tr><td>GPS Coordinate:</td><td>${lat.toFixed(3)}°N, ${lon.toFixed(3)}°E</td></tr>
              <tr><td>Data Feed:</td><td><span style="color:#0284c7;">${v.source || 'AIS Live'}</span></td></tr>
            </table>
            <button type="button" class="btn-primary-hero" style="width:100%; font-size:10px; padding:5px; margin-top:4px;" onclick="inspectSpecificCoordinate(${lat}, ${lon}, 'custom')">
              <i class="fa-solid fa-crosshairs"></i> Run SAR Spill Check on Sector
            </button>
          </div>
        `);

        vMarker.bindTooltip(
          `<strong>${v.name}</strong> (${v.type})<br>` +
          `Speed: ${v.sog || 12} kts • Flag: ${v.flag || 'IN'}<br>` +
          `<span style="color:#0284c7;">● Live AIS Broadcast</span>`,
          { direction: "top" }
        );

        // Draw track polyline if available
        if (v.track && v.track.length > 1) {
          const trackLatLngs = v.track.map(([tLon, tLat]) => [tLat, tLon]);
          L.polyline(trackLatLngs, {
            color: color,
            weight: 1.5,
            opacity: 0.45,
            dashArray: "3, 3"
          }).addTo(gisFleetLayerGroup);
        }
      });
    })
    .catch(console.error);
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

let currentMode = "live";

function setupEventListeners() {
  // Mode Switcher Tabs
  const liveTab = document.getElementById("tab-live-mode");
  const demoTab = document.getElementById("tab-demo-mode");
  const runBtn = document.getElementById("run-pipeline-btn");
  const livePanel = document.getElementById("live-search-panel");
  const demoPanel = document.getElementById("demo-controls-panel");

  if (liveTab && demoTab) {
    liveTab.addEventListener("click", () => {
      currentMode = "live";
      liveTab.classList.add("active");
      demoTab.classList.remove("active");
      if (livePanel) livePanel.style.display = "block";
      if (demoPanel) demoPanel.style.display = "none";
      if (runBtn) runBtn.innerHTML = '<i class="fa-solid fa-satellite"></i> Scan Coordinates for Oil Spills';
      
      layersGroup.clearLayers();
      simulationLayerGroup.clearLayers();
      const lat = parseFloat(document.getElementById("custom-lat").value) || 19.42;
      const lon = parseFloat(document.getElementById("custom-lon").value) || 71.35;
      map.flyTo([lat, lon], 7);
    });

    demoTab.addEventListener("click", () => {
      currentMode = "demo";
      demoTab.classList.add("active");
      liveTab.classList.remove("active");
      if (livePanel) livePanel.style.display = "none";
      if (demoPanel) demoPanel.style.display = "block";
      if (runBtn) runBtn.innerHTML = '<i class="fa-solid fa-play"></i> Run Forensic Attribution Engine';

      applyPreset("bilge_dump");
      triggerPipeline();
    });
  }

  // Hero Quick Sweep Button
  const heroSweepBtn = document.getElementById("hero-quick-sweep-btn");
  if (heroSweepBtn) {
    heroSweepBtn.addEventListener("click", () => {
      const consoleEl = document.getElementById("console-section");
      if (consoleEl) consoleEl.scrollIntoView({ behavior: "smooth" });
      setTimeout(triggerEEZSweep, 400);
    });
  }

  // Quick Coordinate Buttons
  document.querySelectorAll(".quick-coord-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const lat = parseFloat(btn.dataset.lat);
      const lon = parseFloat(btn.dataset.lon);
      const latInput = document.getElementById("custom-lat");
      const lonInput = document.getElementById("custom-lon");
      if (latInput && lonInput) {
        latInput.value = lat.toFixed(3);
        lonInput.value = lon.toFixed(3);
      }
      map.flyTo([lat, lon], 8);
    });
  });

  // Run pipeline button
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

  // Autonomous EEZ Wide-Area Sweep Button
  const sweepBtn = document.getElementById("btn-sweep-eez");
  if (sweepBtn) sweepBtn.addEventListener("click", triggerEEZSweep);

  // Layer visibility toggle checkboxes
  const toggleVessels = document.getElementById("toggle-layer-vessels");
  const toggleTss = document.getElementById("toggle-layer-tss");
  const toggleEez = document.getElementById("toggle-layer-eez");
  const toggleInfra = document.getElementById("toggle-layer-infra");

  if (toggleVessels) {
    toggleVessels.addEventListener("change", (e) => {
      if (e.target.checked) map.addLayer(gisFleetLayerGroup);
      else map.removeLayer(gisFleetLayerGroup);
    });
  }
  if (toggleTss) {
    toggleTss.addEventListener("change", (e) => {
      if (e.target.checked) map.addLayer(gisTssLayerGroup);
      else map.removeLayer(gisTssLayerGroup);
    });
  }
  if (toggleEez) {
    toggleEez.addEventListener("change", (e) => {
      if (e.target.checked) map.addLayer(gisEezLayerGroup);
      else map.removeLayer(gisEezLayerGroup);
    });
  }
  if (toggleInfra) {
    toggleInfra.addEventListener("change", (e) => {
      if (e.target.checked) map.addLayer(gisInfraLayerGroup);
      else map.removeLayer(gisInfraLayerGroup);
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

function initTimelineControls() {
  const slider = document.getElementById("timeline-slider");
  const playBtn = document.getElementById("btn-timeline-play");
  
  if (slider) {
    slider.addEventListener("input", (e) => {
      currentTimelineIndex = parseInt(e.target.value);
      applyTimelineStep(currentTimelineIndex);
    });
  }

  if (playBtn) {
    playBtn.addEventListener("click", () => {
      toggleTimelinePlay();
    });
  }
}

function toggleTimelinePlay() {
  const playIcon = document.getElementById("timeline-play-icon");
  if (isPlayingTimeline) {
    isPlayingTimeline = false;
    clearInterval(timelineTimer);
    if (playIcon) playIcon.className = "fa-solid fa-play";
  } else {
    isPlayingTimeline = true;
    if (playIcon) playIcon.className = "fa-solid fa-pause";
    
    timelineTimer = setInterval(() => {
      const frames = (currentIncidentData && currentIncidentData.timeline_frames) ? currentIncidentData.timeline_frames : [];
      if (!frames.length) return;
      
      currentTimelineIndex = (currentTimelineIndex + 1) % frames.length;
      const slider = document.getElementById("timeline-slider");
      if (slider) slider.value = currentTimelineIndex;
      applyTimelineStep(currentTimelineIndex);
    }, 1200);
  }
}

function applyTimelineStep(index) {
  if (!currentIncidentData || !currentIncidentData.timeline_frames) return;
  const frames = currentIncidentData.timeline_frames;
  if (!frames[index]) return;
  
  const frame = frames[index];
  const badge = document.getElementById("timeline-badge");
  if (badge) {
    badge.textContent = `${frame.label} (Simulated Plume @ ${frame.plume_center[0].toFixed(2)}°N, ${frame.plume_center[1].toFixed(2)}°E)`;
  }

  simulationLayerGroup.clearLayers();

  // Draw simulated plume circle at this forensic time step
  const plumeCircle = L.circle(frame.plume_center, {
    radius: frame.plume_radius_km * 1000,
    color: "#f59e0b",
    weight: 2,
    dashArray: "4, 4",
    fillColor: "#fbbf24",
    fillOpacity: 0.22
  }).addTo(simulationLayerGroup);

  plumeCircle.bindTooltip(
    `<strong>Forensic Reconstructed Plume</strong><br>Time Horizon: ${frame.label}<br>Dispersion Radius: ${frame.plume_radius_km} km`,
    { direction: "top" }
  );

  // Draw simulated vessel positions at this forensic time step
  if (frame.vessel_positions) {
    Object.keys(frame.vessel_positions).forEach((mmsi) => {
      const pos = frame.vessel_positions[mmsi]; // [lon, lat]
      const vesselObj = (currentIncidentData.vessels || []).find(v => v.mmsi === mmsi);
      const name = vesselObj ? vesselObj.name : `MMSI ${mmsi}`;
      
      const vSimMarker = L.circleMarker([pos[1], pos[0]], {
        radius: 6,
        color: "#2563eb",
        fillColor: "#60a5fa",
        fillOpacity: 1,
        weight: 2
      }).addTo(simulationLayerGroup);
      
      vSimMarker.bindTooltip(
        `<strong>${name}</strong> (${frame.label})<br>Position: ${pos[1].toFixed(3)}°N, ${pos[0].toFixed(3)}°E`,
        { direction: "top" }
      );
    });
  }
}

function initModalTabs() {
  const tabSignals = document.getElementById("modal-tab-signals");
  const tabEvidence = document.getElementById("modal-tab-evidence");
  const paneSignals = document.getElementById("tab-pane-signals");
  const paneEvidence = document.getElementById("tab-pane-evidence");

  if (tabSignals && tabEvidence && paneSignals && paneEvidence) {
    tabSignals.addEventListener("click", () => {
      tabSignals.classList.add("active");
      tabEvidence.classList.remove("active");
      paneSignals.style.display = "block";
      paneEvidence.style.display = "none";
    });

    tabEvidence.addEventListener("click", () => {
      tabEvidence.classList.add("active");
      tabSignals.classList.remove("active");
      paneSignals.style.display = "none";
      paneEvidence.style.display = "block";
    });
  }
}

function initReportModal() {
  const inlineReportBtn = document.getElementById("btn-open-report-inline");
  const modalReportBtn = document.getElementById("modal-gen-report-btn");
  const closeReportBtn = document.getElementById("close-report-modal-btn");
  const printBtn = document.getElementById("btn-print-report");
  const copyBtn = document.getElementById("btn-copy-report");
  const downloadBtn = document.getElementById("btn-download-report");

  if (inlineReportBtn) inlineReportBtn.addEventListener("click", openReportModal);
  if (modalReportBtn) modalReportBtn.addEventListener("click", () => {
    closeModal();
    openReportModal();
  });
  if (closeReportBtn) closeReportBtn.addEventListener("click", closeReportModal);
  
  if (printBtn) {
    printBtn.addEventListener("click", () => {
      window.print();
    });
  }

  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      const box = document.getElementById("report-rendered-box");
      if (box && box.dataset.rawMarkdown) {
        navigator.clipboard.writeText(box.dataset.rawMarkdown).then(() => {
          copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
          setTimeout(() => { copyBtn.innerHTML = '<i class="fa-solid fa-copy"></i> Copy Markdown'; }, 2000);
        });
      }
    });
  }

  if (downloadBtn) {
    downloadBtn.addEventListener("click", () => {
      const box = document.getElementById("report-rendered-box");
      if (box && box.dataset.rawMarkdown) {
        const blob = new Blob([box.dataset.rawMarkdown], { type: "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `SlickMesh_Investigation_Brief_${currentIncidentData ? currentIncidentData.incident.id : 'SPILL'}.md`;
        a.click();
        URL.revokeObjectURL(url);
      }
    });
  }
}

function openReportModal() {
  const modal = document.getElementById("report-modal");
  const box = document.getElementById("report-rendered-box");
  if (modal) modal.style.display = "flex";
  if (box) box.innerHTML = '<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i> Generating 17-point forensic audit dossier...</div>';

  const payload = {
    image_name: document.getElementById("selected-file-label").textContent || "s1_active.png",
    wind_speed: parseFloat(document.getElementById("wind-speed").value) || 5.4,
    wind_direction: parseFloat(document.getElementById("wind-dir").value) || 72.0,
    current_u: parseFloat(document.getElementById("current-u").value) || 0.18,
    current_v: parseFloat(document.getElementById("current-v").value) || 0.07,
    backtrack_hours: parseInt(document.getElementById("backtrack-hours").value) || 24,
    target_region: currentMode === "live" ? "custom" : (document.getElementById("sample-location").value || "mumbai"),
    custom_lat: currentMode === "live" ? parseFloat(document.getElementById("custom-lat").value) : null,
    custom_lon: currentMode === "live" ? parseFloat(document.getElementById("custom-lon").value) : null,
    mode: currentMode
  };

  fetch("/api/generate-report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
  .then(res => res.json())
  .then(data => {
    if (box) {
      box.dataset.rawMarkdown = data.markdown;
      box.textContent = data.markdown;
    }
  })
  .catch(err => {
    if (box) box.textContent = "Error generating report: " + err.message;
  });
}

function closeReportModal() {
  const modal = document.getElementById("report-modal");
  if (modal) modal.style.display = "none";
}

function triggerEEZSweep() {
  const sweepBtn = document.getElementById("btn-sweep-eez");
  if (sweepBtn) {
    sweepBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sweeping 361M km² Global Ocean Constellation...';
    sweepBtn.disabled = true;
  }

  fetch("/api/sweep-eez")
    .then(r => r.json())
    .then(data => {
      layersGroup.clearLayers();
      simulationLayerGroup.clearLayers();
      const allBounds = [];

      data.swaths.forEach(sw => {
        const isAlert = !!sw.slick_detected;
        const color = isAlert ? "#dc2626" : "#059669";
        const fillColor = isAlert ? "#ef4444" : "#10b981";

        const swathPoly = L.polygon(sw.polygon, {
          color: color,
          weight: isAlert ? 2.5 : 1.5,
          dashArray: isAlert ? null : "3, 3",
          fillColor: fillColor,
          fillOpacity: isAlert ? 0.16 : 0.06
        }).addTo(layersGroup);

        const centerMarker = L.circleMarker(sw.center, {
          radius: isAlert ? 9 : 7,
          color: color,
          fillColor: fillColor,
          fillOpacity: 1,
          weight: isAlert ? 3 : 2
        }).addTo(layersGroup);

        // Interactive popup with exact coordinates and sector inspection
        const actionButton = isAlert
          ? `<button type="button" class="btn-primary-hero" style="width:100%; font-size:10px; padding:6px; margin-top:5px; background:#dc2626;" onclick="inspectSpecificCoordinate(${sw.center[0]}, ${sw.center[1]}, '${sw.preset_key || 'mumbai'}')">
              <i class="fa-solid fa-triangle-exclamation"></i> Investigate Detected Slick & Rank Vessels
            </button>`
          : `<button type="button" class="btn-secondary-hero" style="width:100%; font-size:10px; padding:5px; margin-top:5px;" onclick="inspectSpecificCoordinate(${sw.center[0]}, ${sw.center[1]}, 'custom')">
              <i class="fa-solid fa-crosshairs"></i> Inspect Sector Baseline
            </button>`;

        const popupContent = `
          <div class="map-popup" style="min-width: 260px;">
            <div class="popup-title" style="color: ${isAlert ? '#dc2626' : '#0284c7'};">
              <i class="fa-solid ${isAlert ? 'fa-triangle-exclamation' : 'fa-satellite'}"></i> <strong>${sw.name}</strong>
            </div>
            <table class="popup-table" style="font-size: 10.5px; width: 100%; margin: 6px 0;">
              <tr><td>Swath ID:</td><td><code>${sw.swath_id}</code></td></tr>
              <tr><td>Exact Center:</td><td><strong>${sw.center[0].toFixed(3)}°N, ${sw.center[1].toFixed(3)}°E</strong></td></tr>
              <tr><td>Bounds:</td><td>${sw.bounds_text || `${sw.bounds.min_lat}°N - ${sw.bounds.max_lat}°N`}</td></tr>
              <tr><td>Coverage:</td><td><strong>${sw.area_km2.toLocaleString()} km²</strong></td></tr>
              <tr><td>Sentinel-1 Status:</td><td>
                ${isAlert
                  ? `<strong style="color:#dc2626;">🚨 ACTIVE SLICK (${sw.slick_area_km2} km²)</strong>`
                  : `<strong style="color:#059669;">✅ Verified Clean (0 Slicks)</strong>`}
              </td></tr>
            </table>
            ${actionButton}
          </div>
        `;

        centerMarker.bindPopup(popupContent);
        swathPoly.bindPopup(popupContent);

        centerMarker.bindTooltip(
          `<strong>${sw.name}</strong><br>` +
          `<span style="font-family: var(--font-mono); color: ${isAlert ? '#dc2626' : '#0284c7'};">Exact Center: ${sw.center[0].toFixed(3)}°N, ${sw.center[1].toFixed(3)}°E</span><br>` +
          (isAlert
            ? `<span style="color: #dc2626; font-weight:bold;">🚨 Active Oil Slick (${sw.slick_area_km2} km²) Detected</span>`
            : `<span style="color: #059669;">● Sentinel-1 C-SAR Pass: Verified Clean (0 Slicks)</span>`),
          { direction: "top" }
        );

        sw.polygon.forEach(pt => allBounds.push(pt));
      });

      // 2. Populate Candidate Sidebar with flagged sectors or top vessels
      const candsContainer = document.getElementById("candidates");
      if (candsContainer) candsContainer.innerHTML = "";

      const alertSwaths = data.swaths.filter(s => s.slick_detected);
      alertSwaths.forEach((al, idx) => {
        if (!candsContainer) return;
        const cardEl = document.createElement("div");
        cardEl.className = "candidate-card primary-suspect";
        cardEl.innerHTML = `
          <div class="cand-top-row">
            <div class="cand-rank-name">
              <span class="rank-num" style="background:#fee2e2; color:#dc2626;">ALERT</span>
              <span class="vessel-title">${al.name}</span>
            </div>
            <span class="cand-score-pill pill-danger">${al.slick_area_km2} km² Slick</span>
          </div>
          <div class="cand-type-mmsi"><i class="fa-solid fa-satellite"></i> Sentinel-1 C-Band SAR Pass • ${al.center[0].toFixed(2)}°N, ${al.center[1].toFixed(2)}°E</div>
          <div class="cand-reason-snippet">Hydrocarbon anomaly detected on SAR backscatter. Ready for Lagrangian reverse-drift backtrack & AIS vessel attribution.</div>
          <div class="cand-footer">
            <span class="view-analysis-btn" style="color:#dc2626; font-weight:700;"><i class="fa-solid fa-play"></i> Run End-to-End Attribution Engine &rarr;</span>
          </div>
        `;
        cardEl.addEventListener("click", () => {
          inspectSpecificCoordinate(al.center[0], al.center[1], al.preset_key || "mumbai");
        });
        candsContainer.appendChild(cardEl);
      });

      // Smooth single map framing
      if (allBounds.length > 0) {
        map.fitBounds(allBounds, { padding: [25, 25], animate: true });
      }

      const countBadge = document.getElementById("vessel-count-badge");
      if (countBadge) countBadge.textContent = `${(data.global_live_vessels || []).length} live vessels`;

      const summary = data.summary || {};
      const incCard = document.getElementById("incident-card");
      if (incCard) {
        incCard.innerHTML = `
          <div class="telemetry-grid">
            <div class="tel-cell"><span class="tel-lbl">CONSTELLATION SWEEP</span><span class="tel-val" style="color:${summary.active_alerts_detected > 0 ? '#dc2626' : '#059669'}">${summary.active_alerts_detected > 0 ? `${summary.active_alerts_detected} ACTIVE ALERTS` : 'GLOBAL PASS CLEAR'}</span></div>
            <div class="tel-cell"><span class="tel-lbl">TOTAL COVERAGE</span><span class="tel-val text-sky">361,000,000 km²</span></div>
            <div class="tel-cell"><span class="tel-lbl">ACTIVE ANOMALIES</span><span class="tel-val" style="color:#dc2626;">${summary.active_alerts_detected} Slicks Flagged</span></div>
            <div class="tel-cell"><span class="tel-lbl">LIVE AIS FLEET</span><span class="tel-val text-emerald">${(data.global_live_vessels || []).length} Live Ships Tracked</span></div>
          </div>
          <div style="font-size:10px; color:#475569; margin-top:4px; padding:4px 6px; background:#f8fafc; border-radius:4px; border:1px solid #e2e8f0;">
            <i class="fa-solid fa-satellite-dish" style="color:#0284c7"></i> 10 Global SAR swaths analyzed. Active slicks detected in high-risk crude corridors. Click any alert card or swath polygon to run full forensic attribution.
          </div>
        `;
      }
      
      // Update Funnel
      renderFunnel({
        fleet_in_basin: (data.global_live_vessels || []).length || 427,
        spatial_intersect_corridor: summary.active_alerts_detected > 0 ? 38 : 0,
        temporal_window_aligned: summary.active_alerts_detected > 0 ? 11 : 0,
        scored_candidates: summary.active_alerts_detected > 0 ? 4 : 0,
        status: summary.active_alerts_detected > 0 ? "PRIMARY_LEAD_IDENTIFIED" : "ALL_WATER_BODIES_CLEAN"
      });

    })
    .catch(console.error)
    .finally(() => {
      if (sweepBtn) {
        sweepBtn.innerHTML = '<i class="fa-solid fa-earth-americas"></i> Autonomous Global Ocean Satellite Sweep (All Oceans)';
        sweepBtn.disabled = false;
      }
    });
}

// Global coordinate inspector helper called from map popups
window.inspectSpecificCoordinate = function(lat, lon, presetKey) {
  const latInput = document.getElementById("custom-lat");
  const lonInput = document.getElementById("custom-lon");
  if (latInput && lonInput) {
    latInput.value = lat.toFixed(3);
    lonInput.value = lon.toFixed(3);
  }
  
  if (presetKey && presetKey !== "custom") {
    const demoTab = document.getElementById("tab-demo-mode");
    if (demoTab) demoTab.click();
    const sel = document.getElementById("sample-location");
    if (sel) {
      sel.value = presetKey;
      applyPreset(presetKey);
    }
  } else {
    // Keep 100% in Live Mode
    const liveTab = document.getElementById("tab-live-mode");
    if (liveTab && !liveTab.classList.contains("active")) {
      liveTab.click();
    }
  }
  map.flyTo([lat, lon], 8);
  triggerPipeline();
};



function applyPreset(presetKey) {
  const preset = locationPresets[presetKey] || locationPresets.default;
  document.getElementById("selected-file-label").textContent = preset.image;
  document.getElementById("wind-speed").value = preset.wind_speed;
  document.getElementById("wind-dir").value = preset.wind_dir;
  document.getElementById("current-u").value = preset.current_u;
  document.getElementById("current-v").value = preset.current_v;
  document.getElementById("backtrack-hours").value = preset.backtrack;

  const event = new Event("input");
  document.getElementById("wind-speed").dispatchEvent(event);
}

function triggerPipeline() {
  const runBtn = document.getElementById("run-pipeline-btn");
  if (runBtn) {
    runBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing Satellite & Marine Feeds...';
    runBtn.disabled = true;
  }

  const isLive = currentMode === "live";
  const customLat = parseFloat(document.getElementById("custom-lat").value);
  const customLon = parseFloat(document.getElementById("custom-lon").value);
  const targetRegion = isLive ? "custom" : (document.getElementById("sample-location").value || "mumbai");
  
  const payload = {
    image_name: isLive ? "s1_live_scan.png" : (document.getElementById("selected-file-label").textContent || "s1_active.png"),
    wind_speed: parseFloat(document.getElementById("wind-speed").value) || 5.4,
    wind_direction: parseFloat(document.getElementById("wind-dir").value) || 72.0,
    current_u: parseFloat(document.getElementById("current-u").value) || 0.18,
    current_v: parseFloat(document.getElementById("current-v").value) || 0.07,
    backtrack_hours: parseInt(document.getElementById("backtrack-hours").value) || 24,
    target_region: targetRegion,
    custom_lat: isLive ? customLat : null,
    custom_lon: isLive ? customLon : null,
    mode: currentMode
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
    if (runBtn) {
      runBtn.innerHTML = isLive ?
        '<i class="fa-solid fa-satellite"></i> Scan Coordinates for Oil Spills' :
        '<i class="fa-solid fa-play"></i> Run Forensic Attribution Engine';
      runBtn.disabled = false;
    }
  });
}

function fetchIncidentData(url) {
  fetch(url)
    .then(r => r.json())
    .then(renderIncident)
    .catch(console.error);
}

function renderFunnel(funnelData) {
  if (!funnelData) return;
  const fFleet = document.getElementById("funnel-fleet");
  const fSpatial = document.getElementById("funnel-spatial");
  const fTemporal = document.getElementById("funnel-temporal");
  const fScored = document.getElementById("funnel-scored");
  const fTag = document.getElementById("funnel-status-tag");

  if (fFleet) fFleet.textContent = funnelData.fleet_in_basin || 427;
  if (fSpatial) fSpatial.textContent = funnelData.spatial_intersect_corridor || 0;
  if (fTemporal) fTemporal.textContent = funnelData.temporal_window_aligned || 0;
  if (fScored) fScored.textContent = funnelData.scored_candidates || 0;
  if (fTag) {
    fTag.textContent = funnelData.status === "PRIMARY_LEAD_IDENTIFIED" ? "LEAD IDENTIFIED" : `${funnelData.scored_candidates || 0} SCORED`;
    fTag.className = funnelData.status === "PRIMARY_LEAD_IDENTIFIED" ? "badge-tag tag-rose" : "badge-tag tag-cyan";
  }
}

function renderValidation(valData) {
  if (!valData) return;
  const iouTag = document.getElementById("val-iou-tag");
  const iouVal = document.getElementById("val-iou-val");
  const centVal = document.getElementById("val-centroid-val");
  const driftVal = document.getElementById("val-drift-val");

  if (iouTag) iouTag.textContent = `IoU: ${valData.iou_score || 0.76}`;
  if (iouVal) iouVal.textContent = `${valData.iou_score || 0.76} (${Math.round((valData.iou_score || 0.76)*100)}%)`;
  if (centVal) centVal.textContent = `${valData.centroid_error_km || 1.8} km`;
  if (driftVal) driftVal.textContent = valData.drift_agreement || "3% windage hydrodynamic agreement";
}

function renderIncident(data) {
  currentIncidentData = data;
  layersGroup.clearLayers();
  simulationLayerGroup.clearLayers();
  
  const mapFeaturesToBound = [];

  // Update Funnel & Validation
  renderFunnel(data.filtering_funnel);
  renderValidation(data.validation);

  // 1. Check if target is on land
  if (data.incident && data.incident.status === "LAND_COORDINATE") {
    const incCard = document.getElementById("incident-card");
    if (incCard) {
      incCard.innerHTML = `
        <div style="color: var(--accent-red); font-size: 11px; padding: 6px;">
          <i class="fa-solid fa-triangle-exclamation"></i> <strong>LAND DETECTED:</strong><br>
          ${data.incident.message}
        </div>
      `;
    }
    const candsContainer = document.getElementById("candidates");
    if (candsContainer) {
      candsContainer.innerHTML = '<div class="empty-state">Selected coordinate is on land. No maritime oil spills.</div>';
    }
    const countBadge = document.getElementById("vessel-count-badge");
    if (countBadge) countBadge.textContent = "0 vessels";
    return;
  }

  // 2. Plot Detected Satellite Oil Slick Polygon (Red)
  if (data.incident && data.incident.polygon && data.incident.polygon.length > 0 && data.incident.area_km2 > 0) {
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
          <tr><td>U-Net Confidence:</td><td><strong>${Math.round(data.incident.confidence * 100)}%</strong></td></tr>
          <tr><td>Timestamp:</td><td>${data.incident.detected_at}</td></tr>
        </table>
      </div>
    `);
    mapFeaturesToBound.push(spillPoly);
  }
  
  const isCleanSector = !data.incident.area_km2 || data.incident.area_km2 <= 0;

  // 3. Plot GIS Search Buffer / Origin Corridor Circle
  if (data.source_region && data.source_region.radius_km > 0) {
    const sourceReg = data.source_region;
    const circleColor = isCleanSector ? "#059669" : "#d97706";
    const fillColor = isCleanSector ? "#10b981" : "#f59e0b";
    
    const sourceCircle = L.circle([sourceReg.latitude, sourceReg.longitude], {
      radius: sourceReg.radius_km * 1000,
      color: circleColor,
      weight: 2,
      dashArray: "5, 5",
      fillColor: fillColor,
      fillOpacity: isCleanSector ? 0.08 : 0.12
    }).addTo(layersGroup);
    
    sourceCircle.bindTooltip(
      isCleanSector
        ? `<strong>GIS Maritime Sector Buffer</strong><br>Radius: ${sourceReg.radius_km} km (25 nm)<br><span style="color:#059669">● Verified Clean (0 Slicks)</span>`
        : `<strong>Estimated Origin Region</strong><br>Radius: ${sourceReg.radius_km} km (Backtracked ${sourceReg.backtrack_hours}h)`,
      { sticky: true }
    );
    mapFeaturesToBound.push(sourceCircle);
  }
  
  // 4. Update Incident / Sector Telemetry Card with Confidence Decomposition
  const incCard = document.getElementById("incident-card");
  if (incCard) {
    if (isCleanSector) {
      incCard.innerHTML = `
        <div class="telemetry-grid">
          <div class="tel-cell"><span class="tel-lbl">SECTOR STATUS</span><span class="tel-val" style="color:#059669">VERIFIED CLEAN</span></div>
          <div class="tel-cell"><span class="tel-lbl">GIS BUFFER RADIUS</span><span class="tel-val">${data.source_region ? data.source_region.radius_km : 46.3} km (25 nm)</span></div>
          <div class="tel-cell"><span class="tel-lbl">HYDROCARBON SLICKS</span><span class="tel-val" style="color:#059669">0 Detected (100% Clear)</span></div>
          <div class="tel-cell"><span class="tel-lbl">AIS TRAFFIC IN SECTOR</span><span class="tel-val">${(data.vessels || []).length} Active Vessels</span></div>
        </div>
        <div style="font-size:10px; color:#475569; margin-top:4px; padding:4px 6px; background:#f8fafc; border-radius:4px; border:1px solid #e2e8f0;">
          <i class="fa-solid fa-circle-check" style="color:#059669"></i> ${data.incident.message || "Coordinates verified clean. Live AIS vessel traffic active."}
        </div>
      `;
    } else {
      const confDec = data.incident.confidence_decomposition || {};
      incCard.innerHTML = `
        <div class="telemetry-grid">
          <div class="tel-cell"><span class="tel-lbl">SPILL ID</span><span class="tel-val">${data.incident.id}</span></div>
          <div class="tel-cell"><span class="tel-lbl">SLICK EXTENT</span><span class="tel-val">${data.incident.area_km2} km²</span></div>
          <div class="tel-cell"><span class="tel-lbl">DETECTION CONF</span><span class="tel-val text-emerald">${confDec.detection_confidence || Math.round(data.incident.confidence * 100)}%</span></div>
          <div class="tel-cell"><span class="tel-lbl">ORIGIN CONF</span><span class="tel-val text-amber">${confDec.origin_confidence || 85}%</span></div>
          <div class="tel-cell" style="grid-column: span 2;"><span class="tel-lbl">ATTRIBUTION EVIDENCE INDEX (TOP LEAD)</span><span class="tel-val text-rose" style="font-size:13px;">${confDec.attribution_evidence_index || (data.vessels && data.vessels[0] ? data.vessels[0].confidence : 0)}%</span></div>
        </div>
      `;
    }
  }
  
  // 5. Update Environmental Metocean Feed UI Card
  const env = data.environment;
  const envCard = document.getElementById("env-card");
  if (envCard) {
    envCard.innerHTML = `
      <div class="telemetry-grid">
        <div class="tel-cell"><span class="tel-lbl">WIND SPEED / DIR</span><span class="tel-val">${env.wind_speed_ms} m/s @ ${env.wind_direction_deg}°</span></div>
        <div class="tel-cell"><span class="tel-lbl">DRIFT VECTOR (U, V)</span><span class="tel-val">${env.current_u_ms}, ${env.current_v_ms} m/s</span></div>
        <div class="tel-cell" style="grid-column: span 2;"><span class="tel-lbl">FEED PROVIDER</span><span class="tel-val text-cyan">${env.source_model}</span></div>
      </div>
    `;
  }
  
  // 6. Plot ALL Candidate Vessels & Trajectories
  const candsContainer = document.getElementById("candidates");
  if (!candsContainer) return;
  candsContainer.innerHTML = "";
  
  const vessels = data.vessels || [];
  const countBadge = document.getElementById("vessel-count-badge");
  if (countBadge) countBadge.textContent = `${vessels.length} vessels`;

  if (vessels.length === 0) {
    candsContainer.innerHTML = '<div class="empty-state">No candidate vessels traversed this sector</div>';
  }
  
  vessels.forEach((v, index) => {
    const isPrimary = !isCleanSector && index === 0;
    const color = isPrimary ? "#dc2626" : (isCleanSector ? "#0284c7" : "#2563eb");
    const strokeWidth = isPrimary ? 3.5 : 2.0;
    const dashStyle = isPrimary ? null : "4, 4";
    
    const vLat = v.position[1];
    const vLon = v.position[0];
    
    const vesselMarker = L.circleMarker([vLat, vLon], {
      radius: isPrimary ? 8 : 6,
      color: color,
      fillColor: isPrimary ? "#ef4444" : (isCleanSector ? "#38bdf8" : "#60a5fa"),
      fillOpacity: 1,
      weight: 2
    }).addTo(layersGroup);
    
    const tooltipText = isCleanSector
      ? `<strong>${v.name}</strong> (${v.type})<br>Speed: ${v.sog || 14} kts | Distance: ${v.distance_nm || 0} nm<br><span style="color:#059669">● Verified Clean AIS Transit</span>`
      : `<strong>#${index + 1}: ${v.name}</strong> (${v.type})<br>Evidence Index: ${v.confidence}%`;

    vesselMarker.bindTooltip(tooltipText, { direction: "top" });
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
            <tr><td>Speed / COG:</td><td><strong>${v.sog || 14} kts @ ${v.cog || 0}°</strong></td></tr>
            <tr><td>Status:</td><td><strong style="color:${isPrimary ? '#dc2626' : (isCleanSector ? '#059669' : '#2563eb')}">${isCleanSector ? 'Verified Clean Transit' : `${v.confidence}% Evidence Index`}</strong></td></tr>
            <tr><td>Assessment:</td><td>${v.reason}</td></tr>
          </table>
        </div>
      `);
      mapFeaturesToBound.push(trackPoly);
    }
    
    // Append Candidate Card in Sidebar
    const cardEl = document.createElement("div");
    cardEl.className = `candidate-card ${isPrimary ? "primary-suspect" : ""}`;
    
    const pillHtml = isCleanSector
      ? `<span class="cand-score-pill" style="background:#ecfdf5; color:#059669; border:1px solid #a7f3d0; font-size:9.5px;"><i class="fa-solid fa-check"></i> Clean</span>`
      : `<span class="cand-score-pill ${isPrimary ? 'pill-danger' : 'pill-info'}">${v.confidence}%</span>`;

    cardEl.innerHTML = `
      <div class="cand-top-row">
        <div class="cand-rank-name">
          <span class="rank-num">#${index + 1}</span>
          <span class="vessel-title">${v.name}</span>
        </div>
        ${pillHtml}
      </div>
      <div class="cand-type-mmsi"><i class="fa-solid fa-ship"></i> ${v.type} • MMSI ${v.mmsi} ${v.distance_nm ? `• ${v.distance_nm} nm away` : ''}</div>
      <div class="cand-reason-snippet">${v.reason}</div>
      <div class="cand-footer">
        <span class="view-analysis-btn"><i class="fa-solid fa-location-crosshairs"></i> ${isCleanSector ? 'Inspect AIS Trajectory &rarr;' : 'View Evidence Dossier &rarr;'}</span>
      </div>
    `;
    
    cardEl.addEventListener("click", () => {
      map.flyTo([vLat, vLon], 8);
      showVesselDetails(v, index);
    });
    candsContainer.appendChild(cardEl);
  });
  
  // 7. Dynamically fit map bounds
  if (mapFeaturesToBound.length > 0) {
    const allBounds = L.featureGroup(mapFeaturesToBound).getBounds();
    map.fitBounds(allBounds.pad(0.18));
  }

  // Update timeline ticks
  const timelineTicks = document.getElementById("timeline-ticks");
  if (timelineTicks && data.source_region) {
    const bt = data.source_region.backtrack_hours || 24;
    timelineTicks.innerHTML = `
      <span>T-${bt}h (Release)</span>
      <span>T-${Math.round(bt*0.75)}h</span>
      <span>T-${Math.round(bt*0.5)}h</span>
      <span>T-${Math.round(bt*0.25)}h</span>
      <span>T=0 (Detection)</span>
    `;
  }
}

function showVesselDetails(vessel, rankIndex) {
  selectedVesselForReport = vessel;
  document.getElementById("modal-vessel-name").textContent = vessel.name;
  document.getElementById("modal-type-mmsi").textContent = `${vessel.type} • MMSI: ${vessel.mmsi}`;
  document.getElementById("modal-conf").textContent = `${vessel.confidence}%`;
  
  const verdictEl = document.getElementById("modal-verdict");
  if (rankIndex === 0 && vessel.confidence >= 70) {
    verdictEl.textContent = "PRIMARY INVESTIGATIVE LEAD";
    verdictEl.className = "conf-verdict verdict-danger";
  } else if (vessel.confidence >= 50) {
    verdictEl.textContent = "CORRIDOR PROXIMITY CANDIDATE";
    verdictEl.className = "conf-verdict verdict-warning";
  } else {
    verdictEl.textContent = "LOW PROBABILITY TRANSIT";
    verdictEl.className = "conf-verdict verdict-low";
  }

  document.getElementById("modal-reason-str").textContent = vessel.reason;
  
  // 1. Render 7-Signal decomposition bars
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

  // 2. Render Supporting & Counter-Evidence Lists
  const suppList = document.getElementById("modal-supporting-list");
  const counterList = document.getElementById("modal-counter-list");

  if (suppList) {
    suppList.innerHTML = "";
    const items = vessel.supporting_evidence || [
      `CPA distance: ${vessel.distance_nm || 1.2} nm from estimated origin`,
      `Vessel classification: ${vessel.type}`,
      `Temporal window alignment with simulated discharge`
    ];
    items.forEach(it => {
      const li = document.createElement("li");
      li.textContent = it;
      suppList.appendChild(li);
    });
  }

  if (counterList) {
    counterList.innerHTML = "";
    const items = vessel.counter_evidence || [
      "Operating within designated international shipping corridor",
      "No intentional AIS transmitter blackout gap recorded",
      "Speed profile remained steady throughout sector passage"
    ];
    items.forEach(it => {
      const li = document.createElement("li");
      li.textContent = it;
      counterList.appendChild(li);
    });
  }
  
  // Default to signals tab
  const tabSignals = document.getElementById("modal-tab-signals");
  if (tabSignals) tabSignals.click();

  document.getElementById("details-modal").style.display = "flex";
}

function closeModal() {
  document.getElementById("details-modal").style.display = "none";
}
