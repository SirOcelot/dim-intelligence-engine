import argparse
from pathlib import Path
from .pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="DIM Intelligence Engine")
    parser.add_argument("--weapons", required=True)
    parser.add_argument("--armor", required=True)
    parser.add_argument("--loadouts", required=False)
    parser.add_argument("--use-bungie", action="store_true")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    run_pipeline(
        weapons=Path(args.weapons),
        armor=Path(args.armor),
        loadouts=Path(args.loadouts) if args.loadouts else None,
        output_dir=Path(args.output_dir),
        use_bungie=args.use_bungie
    )


if __name__ == "__main__":
    main()
