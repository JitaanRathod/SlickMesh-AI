"""Command Line Interface for Phase 3 Attribution Engine."""

import argparse
import json
import sys
from pathlib import Path

# Ensure local imports work when called as a script
pkg_dir = Path(__file__).resolve().parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

try:
    from .models import BacktrackInput, AttributionOutput
    from .engine import AttributionEngine
    from .mock_data import MOCK_CONTRACT_C_DATA
    from .explainer import get_feature_drivers
except ImportError:
    from models import BacktrackInput, AttributionOutput
    from engine import AttributionEngine
    from mock_data import MOCK_CONTRACT_C_DATA
    from explainer import get_feature_drivers


def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase 3 - Attribution Engine (SIH26143)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        help="Path to Contract C JSON input file (from Phase 2 / Backtracking)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Path to write Contract D JSON output file (for Dashboard / Integration)"
    )
    parser.add_argument(
        "-s", "--spill-id",
        type=str,
        default="SPILL-001",
        help="Identifier for the oil spill incident"
    )
    parser.add_argument(
        "-m", "--mock",
        action="store_true",
        help="Run against built-in canonical Contract C mock data"
    )
    parser.add_argument(
        "--method",
        type=str,
        choices=["weighted", "bayesian"],
        default="weighted",
        help="Attribution scoring model to execute"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Format output JSON with 2-space indentation"
    )
    parser.add_argument(
        "-t", "--table",
        action="store_true",
        help="Display formatted ASCII ranking table in terminal (great for live demo)"
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Print detailed per-vessel feature driver breakdown"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.mock or not args.input:
        raw_data = MOCK_CONTRACT_C_DATA
    else:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
            sys.exit(1)
        with open(input_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

    # Initialize Attribution Engine
    engine = AttributionEngine()

    try:
        result = engine.process(
            raw_data,
            spill_id=args.spill_id,
            method=args.method
        )
    except Exception as e:
        print(f"Error executing attribution engine: {e}", file=sys.stderr)
        sys.exit(2)

    # If --table requested, print ASCII report
    if args.table:
        print(engine.render_ascii_table(result))
        if args.explain:
            print("\nDetailed Feature Driver Breakdown:")
            w_dict = engine.weights.as_dict()
            for v in result.ranked_vessels:
                drivers = get_feature_drivers(v.sub_scores.model_dump(), w_dict)
                print(f"  * {v.name} ({v.confidence}% confidence):")
                print(f"      Drivers: {', '.join(drivers['primary_drivers']) or 'None'}")
                print(f"      Reason: {v.reason}")
        return

    # Serialize to Contract D JSON dict
    output_dict = result.model_dump()
    json_str = json.dumps(output_dict, indent=2 if args.pretty else None)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"Attribution output successfully written to {args.output}")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
