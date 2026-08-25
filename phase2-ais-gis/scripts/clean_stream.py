"""
clean_stream.py — Rebuild clean Parquet strictly from the live raw AIS stream.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ais_cleaner import clean_ndjson_stream
from src.config import CLEANED_PARQUET

def main():
    if CLEANED_PARQUET.exists():
        CLEANED_PARQUET.unlink()
        print("Removed previous Parquet file.")
    df = clean_ndjson_stream()
    print(f"Successfully generated Parquet from live stream with {len(df)} records!")

if __name__ == "__main__":
    main()
