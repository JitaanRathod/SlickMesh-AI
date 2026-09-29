import sys
import os
from pathlib import Path

# Ensure root directory and phase subdirectories are on python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "phase1-satellite"))
sys.path.insert(0, str(ROOT_DIR / "phase2-ais-gis"))
sys.path.insert(0, str(ROOT_DIR / "phase3-attribution"))

from server import app
