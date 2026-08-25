"""
ais_listener.py — WebSocket listener for AISstream.io.

Streams live AIS messages filtered to the Arabian Sea / Bay of Bengal bounding box
and writes raw NDJSON lines to data/raw_ais_stream.ndjson continuously.

Run this IMMEDIATELY at the start of the hackathon — the longer it runs,
the more Indian-Ocean data you'll have accumulated by demo time.

Usage:
  python -m src.ais_listener                 # runs until Ctrl-C
  python -m src.ais_listener --dry-run       # connects, prints first 5 messages, exits

Requires:
  AISSTREAM_API_KEY set in src/config.py (get a free key at https://aisstream.io/authenticate)
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import websockets

from src.config import (
    AISSTREAM_API_KEY,
    AISSTREAM_WS_URL,
    BOUNDING_BOX,
    RAW_STREAM_FILE,
)

logger = logging.getLogger(__name__)

SUBSCRIBE_MSG = {
    "APIKey": AISSTREAM_API_KEY,
    "BoundingBoxes": [BOUNDING_BOX],
    "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
}


async def _stream_to_file(dry_run: bool = False) -> None:
    """Connect to AISstream.io and append incoming messages to NDJSON file."""
    if AISSTREAM_API_KEY.startswith("TODO"):
        logger.error(
            "AISSTREAM_API_KEY is not set. Edit src/config.py and add your key. "
            "Get a free key at https://aisstream.io/authenticate"
        )
        sys.exit(1)

    RAW_STREAM_FILE.parent.mkdir(parents=True, exist_ok=True)
    msg_count = 0
    logger.info("Connecting to AISstream.io …")

    async with websockets.connect(AISSTREAM_WS_URL) as ws:
        await ws.send(json.dumps(SUBSCRIBE_MSG))
        logger.info("Subscribed to bounding box %s", BOUNDING_BOX)
        logger.info("Writing to %s — press Ctrl-C to stop.", RAW_STREAM_FILE)

        with open(RAW_STREAM_FILE, "a") as f:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # Attach a receive timestamp so we know when this was logged
                msg["_received_utc"] = datetime.now(timezone.utc).isoformat()

                f.write(json.dumps(msg) + "\n")
                f.flush()
                msg_count += 1

                if msg_count % 100 == 0:
                    logger.info("%d messages received so far …", msg_count)

                if dry_run and msg_count >= 5:
                    logger.info("Dry-run: received %d messages. First message: %s", msg_count, msg)
                    break


def main() -> None:
    parser = argparse.ArgumentParser(description="AISstream.io live listener for Phase 2")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Connect, print first 5 messages, then exit without writing",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        asyncio.run(_stream_to_file(dry_run=args.dry_run))
    except KeyboardInterrupt:
        logger.info("Listener stopped by user.")


if __name__ == "__main__":
    main()
