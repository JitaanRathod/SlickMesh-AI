"""
download_danish.py — Download one day of Danish Maritime Authority AIS data for offline dev.

Downloads the zip, extracts the CSV into data/, and runs the cleaner to produce
data/ais_cleaned.parquet ready for trajectory_builder.py.

Usage:
  python scripts/download_danish.py
"""

import io
import logging
import urllib3
import warnings
import zipfile
from pathlib import Path

import requests

# The Danish Maritime Authority's web.ais.dk has a known SSL certificate
# hostname mismatch. We suppress the warning for this one download only.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# We import from parent package — run from phase2-ais-gis/ root
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DANISH_AIS_URL, DANISH_AIS_FILENAME, DATA_DIR
from src.ais_cleaner import clean_danish_csv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def download_and_extract() -> Path:
    csv_path = DATA_DIR / DANISH_AIS_FILENAME

    if csv_path.exists():
        logger.info("Danish AIS CSV already exists at %s — skipping download.", csv_path)
        return csv_path

    logger.info("Downloading Danish AIS dataset from %s …", DANISH_AIS_URL)
    response = requests.get(DANISH_AIS_URL, stream=True, timeout=120, verify=False)  # noqa: S501 — known AIS host SSL mismatch
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))
    downloaded = 0
    chunks = []
    for chunk in response.iter_content(chunk_size=1024 * 256):
        chunks.append(chunk)
        downloaded += len(chunk)
        if total:
            pct = downloaded / total * 100
            logger.info("  %.1f%%", pct)

    raw_zip = b"".join(chunks)
    logger.info("Download complete (%.1f MB). Extracting …", len(raw_zip) / 1e6)

    with zipfile.ZipFile(io.BytesIO(raw_zip)) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not csv_names:
            raise RuntimeError("No CSV found in the downloaded zip.")
        # Extract the first CSV (typically the only file in the archive)
        zf.extract(csv_names[0], DATA_DIR)
        extracted = DATA_DIR / csv_names[0]
        if extracted != csv_path:
            extracted.rename(csv_path)

    logger.info("Extracted to %s", csv_path)
    return csv_path


def main() -> None:
    csv_path = download_and_extract()
    logger.info("Running AIS cleaner on %s …", csv_path)
    df = clean_danish_csv(csv_path)
    logger.info("Done — %d clean AIS rows in Parquet.", len(df))


if __name__ == "__main__":
    main()
