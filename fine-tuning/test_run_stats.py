import argparse
import logging
import json
from pathlib import Path
from test_run import analyze_verdicts
import shutil

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s |   %(message)s",
    datefmt="%m-%d-%Y %H:%M:%S",
    level=logging.INFO,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output-path",
        required=True,
        type=str,
        help="The directory where predictions are saved and execution results will be saved.",
    )
    logger = logging.getLogger("MAIN")
    args = parser.parse_args()
    args.output_path = Path(args.output_path)

    verdicts_dir = args.output_path / "test_verdicts"
    verdict_paths = list(verdicts_dir.glob("*.json"))
    if len(verdict_paths) == 0:
        logger.info("No verdict files found! Aborting ...")
        return
    test_ds = json.loads((args.output_path / "splits" / "test.json").read_text())
    if len(verdict_paths) != len(test_ds):
        logger.info(f"Expected {len(test_ds)} verdict files, found {len(verdict_paths)}! Aborting ...")
        return

    logger.info(f"Analyzing {len(verdict_paths)} verdict files")
    verdicts = []
    for verdict_file in verdict_paths:
        verdicts.extend(json.loads(verdict_file.read_text()))
    verdicts = [(v["verdict"], v["id"], v["rank"]) for v in verdicts]
    verdict_df, plausible_rate = analyze_verdicts(verdicts)
    verdicts_file = args.output_path / "test_verdicts.json"
    verdict_df.to_json(verdicts_file, orient="records", indent=2)

    stats_file = args.output_path / "stats.json"
    stats = json.loads(stats_file.read_text())
    stats["test_results"]["plausible_rate"] = plausible_rate
    stats_file.write_text(json.dumps(stats, indent=2, sort_keys=False))


if __name__ == "__main__":
    main()
