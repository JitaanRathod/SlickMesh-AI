"""Tests for the Phase 3 Command Line Interface."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from mock_data import MOCK_CONTRACT_C_DATA


def test_cli_mock_flag():
    """Verify that running CLI with --mock flag outputs valid Contract D JSON."""
    cli_path = Path(__file__).resolve().parent.parent / "cli.py"
    cmd = [sys.executable, str(cli_path), "--mock", "--pretty"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    data = json.loads(result.stdout)
    assert "spill_id" in data
    assert "ranked_vessels" in data
    assert len(data["ranked_vessels"]) == 2
    assert data["ranked_vessels"][0]["name"] == "MV Ocean Star"


def test_cli_file_input_output():
    """Verify CLI with -i and -o flags reads and writes files correctly."""
    cli_path = Path(__file__).resolve().parent.parent / "cli.py"
    with tempfile.TemporaryDirectory() as tmpdir:
        in_file = Path(tmpdir) / "input.json"
        out_file = Path(tmpdir) / "output.json"

        with open(in_file, "w", encoding="utf-8") as f:
            json.dump(MOCK_CONTRACT_C_DATA, f)

        cmd = [
            sys.executable, str(cli_path),
            "-i", str(in_file),
            "-o", str(out_file),
            "-s", "TEST-SPILL-99"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert out_file.exists()

        with open(out_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["spill_id"] == "TEST-SPILL-99"
        assert len(data["ranked_vessels"]) == 2
