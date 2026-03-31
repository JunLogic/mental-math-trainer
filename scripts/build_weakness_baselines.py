from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from app.services.baseline_pipeline import run_baseline_pipeline
from app.services.config import DATA_DIR
from app.services.storage import SQLiteStorage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build offline baseline models for the mental-math weakness detector.")
    parser.add_argument(
        "--database",
        type=Path,
        default=DATA_DIR / "leaderboard.db",
        help="Path to the SQLite database containing saved runs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for saved artefacts. Defaults to data/ml_artifacts/<timestamp>.",
    )
    parser.add_argument(
        "--use-full-features",
        action="store_true",
        help="Use the full offline feature surface instead of the core-only default.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.25,
        help="Fraction of rows reserved for test evaluation.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed for train/test splitting and baseline models.",
    )
    parser.add_argument(
        "--time-correct-only",
        action="store_true",
        help="Restrict the time-regression dataset to correct answered rows only.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DATA_DIR / "ml_artifacts" / timestamp

    storage = SQLiteStorage(args.database)
    storage.initialize()
    results = run_baseline_pipeline(
        storage=storage,
        output_dir=output_dir,
        use_full_features=args.use_full_features,
        test_size=args.test_size,
        random_seed=args.random_seed,
        time_correct_only=args.time_correct_only,
    )

    print(f"Artefacts saved to: {results['artifacts'].output_dir}")
    print(f"Dataset rows: {results['dataset_summary']['rows']}")
    print(f"Feature set: {results['dataset_summary']['feature_set']}")
    print(f"Answered rows: {results['dataset_summary']['answered_rows']}")
    print(f"Parse-succeeded rows: {results['dataset_summary']['parse_succeeded_rows']}")


if __name__ == "__main__":
    main()
