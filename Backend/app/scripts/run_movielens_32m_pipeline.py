import argparse
import shlex
import subprocess
import sys
import time
import urllib.request
import zipfile

from app.infrastructure.datasets.movielens_paths import (
    ML_32M_DATASET_DIR,
    ML_32M_EXTRACT_DIR,
    ML_32M_LINKS_CSV_PATH,
    ML_32M_MOVIES_CSV_PATH,
    ML_32M_RATINGS_CSV_PATH,
    ML_32M_TAGS_CSV_PATH,
    ML_32M_ZIP_PATH,
)


MOVIELENS_32M_URL = "https://files.grouplens.org/datasets/movielens/ml-32m.zip"
RAW_REQUIRED_STAGES = {"candidates", "ratings"}
REQUIRED_RAW_PATHS = [
    ML_32M_MOVIES_CSV_PATH,
    ML_32M_RATINGS_CSV_PATH,
    ML_32M_TAGS_CSV_PATH,
    ML_32M_LINKS_CSV_PATH,
]


STAGE_ORDER = [
    "candidates",
    "enrich",
    "catalog",
    "ratings",
    "export",
    "posters",
    "audit",
]


def main() -> None:
    args = _parse_args()
    selected_stages = _select_stages(args)

    if not selected_stages:
        print("No stages selected.")
        return

    print(f"Selected stages: {', '.join(selected_stages)}")

    if args.dry_run:
        for stage in selected_stages:
            command = _build_stage_command(stage, args)
            _print_stage_header(stage)
            print(f"Command: {_format_command(command)}")
        print(f"Dry run complete. Stages that would run: {', '.join(selected_stages)}")
        return

    _ensure_raw_movielens_dataset(args=args, selected_stages=selected_stages)

    started_at = time.time()
    executed_stages: list[str] = []

    for stage in selected_stages:
        command = _build_stage_command(stage, args)
        _print_stage_header(stage)
        print(f"Command: {_format_command(command)}")
        subprocess.run(command, check=True)
        executed_stages.append(stage)

    elapsed_seconds = round(time.time() - started_at, 2)
    print(f"Pipeline completed successfully. Executed stages: {', '.join(executed_stages)}")
    print(f"Elapsed seconds: {elapsed_seconds}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the MovieLens 32M offline dataset pipeline end to end.",
        epilog=(
            "Examples:\n\n"
            "1. Current broad dataset rebuild with collaborative support from 1990:\n\n"
            "python -m app.scripts.run_movielens_32m_pipeline \\\n"
            "  --download-raw-movielens \\\n"
            "  --candidate-limit 15000 \\\n"
            "  --candidate-min-ratings 100 \\\n"
            "  --candidate-min-year 1990 \\\n"
            "  --collaborative-core-limit 15000 \\\n"
            "  --public-min-year 2000 \\\n"
            "  --collaborative-min-year 1990\n\n"
            "2. Dry run:\n\n"
            "python -m app.scripts.run_movielens_32m_pipeline \\\n"
            "  --candidate-limit 15000 \\\n"
            "  --candidate-min-ratings 100 \\\n"
            "  --candidate-min-year 1990 \\\n"
            "  --collaborative-core-limit 15000 \\\n"
            "  --public-min-year 2000 \\\n"
            "  --collaborative-min-year 1990 \\\n"
            "  --dry-run\n\n"
            "3. Resume from catalog after enrichment:\n\n"
            "python -m app.scripts.run_movielens_32m_pipeline \\\n"
            "  --start-at catalog \\\n"
            "  --collaborative-core-limit 15000 \\\n"
            "  --public-min-year 2000 \\\n"
            "  --collaborative-min-year 1990\n\n"
            "4. Run only audit:\n\n"
            "python -m app.scripts.run_movielens_32m_pipeline \\\n"
            "  --start-at audit \\\n"
            "  --audit"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--candidate-limit", type=int, default=8000)
    parser.add_argument("--candidate-min-ratings", type=int, default=100)
    parser.add_argument("--candidate-min-year", type=int, default=1995)
    parser.add_argument("--candidate-max-year", type=int)
    parser.add_argument("--max-tags-per-movie", type=int, default=35)
    parser.add_argument("--download-raw-movielens", action="store_true")

    parser.set_defaults(resume_tmdb=True)
    parser.add_argument("--resume-tmdb", dest="resume_tmdb", action="store_true")
    parser.add_argument("--no-resume-tmdb", dest="resume_tmdb", action="store_false")

    parser.add_argument("--public-limit", type=int)
    parser.add_argument("--collaborative-core-limit", type=int, default=8000)
    parser.add_argument("--catalog-min-ratings", type=int, default=100)
    parser.add_argument("--public-min-year", type=int, default=2000)
    parser.add_argument("--collaborative-min-year", type=int, default=1995)
    parser.add_argument("--family-only", action="store_true")

    parser.add_argument("--skip-posters", action="store_true")
    parser.add_argument("--audit", action="store_true")

    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start-at", choices=STAGE_ORDER, default="candidates")
    parser.add_argument("--stop-after", choices=STAGE_ORDER)

    return parser.parse_args()


def _select_stages(args: argparse.Namespace) -> list[str]:
    start_index = STAGE_ORDER.index(args.start_at)
    stop_index = STAGE_ORDER.index(args.stop_after) if args.stop_after else len(STAGE_ORDER) - 1
    if stop_index < start_index:
        raise ValueError("--stop-after must not be before --start-at.")

    requested_stages = STAGE_ORDER[start_index : stop_index + 1]
    selected_stages: list[str] = []
    for stage in requested_stages:
        if stage == "posters" and args.skip_posters:
            continue
        if stage == "audit" and not args.audit:
            continue
        selected_stages.append(stage)
    return selected_stages


def _ensure_raw_movielens_dataset(*, args: argparse.Namespace, selected_stages: list[str]) -> None:
    if not any(stage in RAW_REQUIRED_STAGES for stage in selected_stages):
        return

    if _has_required_raw_files():
        return

    if not args.download_raw_movielens:
        missing_files_text = ", ".join(path.name for path in REQUIRED_RAW_PATHS if not path.exists())
        raise RuntimeError(
            "MovieLens 32M raw files are missing. "
            f"Expected files under {ML_32M_DATASET_DIR}: {missing_files_text}. "
            "Place the raw files manually or rerun with --download-raw-movielens."
        )

    _download_and_extract_raw_movielens()


def _has_required_raw_files() -> bool:
    return all(path.exists() for path in REQUIRED_RAW_PATHS)


def _download_and_extract_raw_movielens() -> None:
    print("MovieLens 32M raw files are missing.")
    print(f"Dataset URL: {MOVIELENS_32M_URL}")
    print(f"Zip path: {ML_32M_ZIP_PATH}")
    print(f"Dataset dir: {ML_32M_DATASET_DIR}")

    ML_32M_ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    ML_32M_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    if ML_32M_ZIP_PATH.exists():
        print("Zip already present. Reusing existing download.")
    else:
        print("Downloading MovieLens 32M zip...")
        urllib.request.urlretrieve(MOVIELENS_32M_URL, ML_32M_ZIP_PATH)
        print("Download completed.")

    if _has_required_raw_files():
        print("Required raw files already exist after zip check. Skipping extraction.")
        return

    print("Extracting MovieLens 32M zip...")
    with zipfile.ZipFile(ML_32M_ZIP_PATH, "r") as zip_file:
        zip_file.extractall(ML_32M_EXTRACT_DIR)
    print("Extraction completed.")

    if not _has_required_raw_files():
        missing_files_text = ", ".join(path.name for path in REQUIRED_RAW_PATHS if not path.exists())
        raise RuntimeError(
            "MovieLens 32M download finished but required raw files are still missing. "
            f"Expected under {ML_32M_DATASET_DIR}: {missing_files_text}."
        )

    print("Verified required MovieLens 32M raw files.")


def _build_stage_command(stage: str, args: argparse.Namespace) -> list[str]:
    command = [sys.executable]

    if stage == "candidates":
        command.extend(
            [
                "-m",
                "app.scripts.build_movielens_32m_candidates",
                "--limit",
                str(args.candidate_limit),
                "--min-ratings",
                str(args.candidate_min_ratings),
                "--min-year",
                str(args.candidate_min_year),
                "--max-tags-per-movie",
                str(args.max_tags_per_movie),
            ]
        )
        if args.candidate_max_year is not None:
            command.extend(["--max-year", str(args.candidate_max_year)])
        return command

    if stage == "enrich":
        command.extend(["-m", "app.scripts.enrich_movielens_32m_with_tmdb"])
        if args.resume_tmdb:
            command.append("--resume")
        return command

    if stage == "catalog":
        command.extend(
            [
                "-m",
                "app.scripts.build_demo_catalog_from_movielens_32m",
                "--collaborative-core-limit",
                str(args.collaborative_core_limit),
                "--min-ratings",
                str(args.catalog_min_ratings),
                "--public-min-year",
                str(args.public_min_year),
                "--collaborative-min-year",
                str(args.collaborative_min_year),
            ]
        )
        if args.public_limit is not None:
            command.extend(["--public-limit", str(args.public_limit)])
        if args.family_only:
            command.append("--family-only")
        return command

    if stage == "ratings":
        command.extend(["-m", "app.scripts.build_demo_ratings_from_movielens_32m"])
        return command

    if stage == "export":
        command.extend(["-m", "app.scripts.export_offline_dataset_from_movielens_32m"])
        return command

    if stage == "posters":
        command.extend(["-m", "app.scripts.download_offline_movie_posters"])
        return command

    if stage == "audit":
        command.extend(["-m", "app.scripts.audit_offline_dataset"])
        return command

    raise ValueError(f"Unsupported stage: {stage}")


def _print_stage_header(stage: str) -> None:
    print()
    print(f"=== Stage: {stage} ===")


def _format_command(command: list[str]) -> str:
    return shlex.join(command)


if __name__ == "__main__":
    main()
