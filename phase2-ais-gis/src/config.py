"""
config.py — Central configuration for Phase 2 (AIS / GIS / Backtracking).

Edit AISSTREAM_API_KEY and LOOKBACK_HOURS if needed before running.
Everything else has sensible defaults for the Arabian Sea / Bay of Bengal AoI.
"""

# ---------------------------------------------------------------------------
# AIS data sources
# ---------------------------------------------------------------------------

# AISstream.io WebSocket endpoint + API key
# Get a free key at: https://aisstream.io/authenticate
AISSTREAM_API_KEY: str = "0a2e259c33beea0ea9d47e642362a0fc906d8118"
AISSTREAM_WS_URL: str = "wss://stream.aisstream.io/v0/stream"

# Bounding box for the AIS listener filter (Arabian Sea + Bay of Bengal + Indian coastline)
# Format: [[min_lat, min_lon], [max_lat, max_lon]]
BOUNDING_BOX: list[list[float]] = [[2.0, 55.0], [25.0, 100.0]]

# Danish AIS offline development dataset (one day of global AIS — wrong geography, correct schema)
# Using Figshare CDN mirror — more reliably accessible than web.ais.dk (which geo-restricts outside Denmark)
# Figshare DOI: https://doi.org/10.6084/m9.figshare.11577543
DANISH_AIS_URL: str = "https://figshare.com/ndownloader/files/21262940"
DANISH_AIS_FILENAME: str = "aisdk-2024-03-01.csv"

# ---------------------------------------------------------------------------
# Pipeline parameters
# ---------------------------------------------------------------------------

# Hard gate: only consider vessels with ≥1 AIS point within this window before detection
LOOKBACK_HOURS: int = 24

# Trajectory gap splitting: AIS silence longer than this → new segment (do NOT interpolate)
GAP_SPLIT_MINUTES: int = 60

# Jump filter: implied speed above this threshold → drop the point (knots)
MAX_REALISTIC_SPEED_KNOTS: float = 50.0

# Backtracking: windage fraction (3 % of wind speed, in wind direction — first-order approximation)
WINDAGE_FRACTION: float = 0.03

# Origin corridor buffer radius (km) — the backtracked LineString is expanded by this amount
CORRIDOR_BUFFER_KM: float = 10.0

# Search radius around spill centroid for initial candidate filter (nm)
CANDIDATE_SEARCH_RADIUS_NM: float = 100.0

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

RAW_STREAM_FILE = DATA_DIR / "raw_ais_stream.ndjson"
RAW_DANISH_CSV = DATA_DIR / DANISH_AIS_FILENAME
CLEANED_PARQUET = DATA_DIR / "ais_cleaned.parquet"
CONTRACT_C_FILE = OUTPUT_DIR / "contract_c.json"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
