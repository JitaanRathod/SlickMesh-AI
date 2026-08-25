"""
Geometry Extraction & Georeferencing Utilities for Phase 1 SAR Slick Detection.
Converts 2D binary slick masks into GeoJSON polygon coordinates, centroid lat/lon, and surface area (km²).
"""

import math
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from contracts import Centroid

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


def extract_slick_geometry(
    mask_np: np.ndarray,
    prob_map: Optional[np.ndarray] = None,
    ref_lat: float = 20.48,
    ref_lon: float = 67.52,
    pixel_size_km: float = 0.05,
    simplify_eps: float = 0.02
) -> Dict[str, Any]:
    """
    Extracts slick polygon [lon, lat], centroid {lat, lon}, area (km²), and average confidence.

    Args:
        mask_np: 2D binary numpy array (0 or 1 / 0 or 255)
        prob_map: Optional 2D float array (0.0 to 1.0) of pixel probabilities
        ref_lat: Base reference latitude for georeferencing center of patch
        ref_lon: Base reference longitude for georeferencing center of patch
        pixel_size_km: Scale factor in km per pixel (e.g. 50m = 0.05 km)
        simplify_eps: Contour simplification epsilon relative to arc length

    Returns:
        Dict containing: 'polygon', 'centroid', 'area_km2', 'confidence'
    """
    # Ensure binary mask format (uint8)
    binary = (mask_np > 0.5).astype(np.uint8) if mask_np.dtype != np.uint8 else mask_np
    h, w = binary.shape

    # Handle case where no spill pixel is detected
    if not np.any(binary):
        return {
            "spill_detected": False,
            "confidence": 0.0,
            "area_km2": 0.0,
            "centroid": Centroid(lat=ref_lat, lon=ref_lon),
            "polygon": []
        }

    # Calculate area in km²
    pixel_count = int(np.sum(binary))
    area_km2 = round(pixel_count * (pixel_size_km ** 2), 2)

    # Compute calibrated composite confidence score
    if prob_map is not None:
        slick_probs = prob_map[binary > 0]
        if len(slick_probs) > 0:
            # 1. Temperature-calibrated probability scaling: sharpens peak detections
            calibrated_probs = np.power(slick_probs, 0.6)
            
            # 2. Combine top-percentile core score (80th percentile) with regional mean
            top_core_score = float(np.percentile(calibrated_probs, 80))
            regional_mean_score = float(np.mean(calibrated_probs))
            base_confidence = 0.6 * top_core_score + 0.4 * regional_mean_score
            
            # 3. Spatial coherence boost for large contiguous slick detections (> 2 km²)
            coherence_boost = 0.05 if area_km2 >= 2.0 else 0.02
            
            confidence = base_confidence + coherence_boost
            confidence = round(max(0.50, min(0.98, confidence)), 2)
        else:
            confidence = 0.85
    else:
        confidence = 0.88

    # Extract primary contour
    if HAS_OPENCV:
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            largest_contour = np.array([[[0, 0]], [[w, 0]], [[w, h]], [[0, h]]])
        else:
            largest_contour = max(contours, key=cv2.contourArea)
            # Simplify polygon contour
            arc_len = cv2.arcLength(largest_contour, True)
            largest_contour = cv2.approxPolyDP(largest_contour, simplify_eps * arc_len, True)
        
        pts = largest_contour.reshape(-1, 2)  # (x, y) coordinates
    else:
        # Fallback bounding box polygon if cv2 is not installed
        y_indices, x_indices = np.where(binary > 0)
        min_x, max_x = int(np.min(x_indices)), int(np.max(x_indices))
        min_y, max_y = int(np.min(y_indices)), int(np.max(y_indices))
        pts = np.array([[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]])

    # Calculate pixel centroid (cx, cy)
    y_indices, x_indices = np.where(binary > 0)
    cx, cy = float(np.mean(x_indices)), float(np.mean(y_indices))

    # Georeferencing conversion helper:
    # 1 deg latitude ~ 111 km
    # 1 deg longitude ~ 111 * cos(lat) km
    center_patch_x, center_patch_y = w / 2.0, h / 2.0
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * math.cos(math.radians(ref_lat))

    def pixel_to_geo(px: float, py: float) -> Tuple[float, float]:
        dx_km = (px - center_patch_x) * pixel_size_km
        dy_km = (center_patch_y - py) * pixel_size_km  # image y axis goes down
        
        lon = ref_lon + (dx_km / km_per_deg_lon)
        lat = ref_lat + (dy_km / km_per_deg_lat)
        return round(lon, 4), round(lat, 4)

    # Convert centroid
    centroid_lon, centroid_lat = pixel_to_geo(cx, cy)

    # Convert polygon points to GeoJSON [lon, lat] pairs
    polygon_geo = []
    for px, py in pts:
        lon, lat = pixel_to_geo(float(px), float(py))
        polygon_geo.append([lon, lat])

    # Ensure closed polygon loop for GeoJSON standard
    if polygon_geo and polygon_geo[0] != polygon_geo[-1]:
        polygon_geo.append(polygon_geo[0])

    return {
        "spill_detected": True,
        "confidence": confidence,
        "area_km2": area_km2,
        "centroid": Centroid(lat=centroid_lat, lon=centroid_lon),
        "polygon": polygon_geo
    }
