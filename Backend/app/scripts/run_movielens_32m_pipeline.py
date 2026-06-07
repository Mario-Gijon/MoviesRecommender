import argparse
import shlex
import subprocess
import sys
import time


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
            "  --candidate-limit 15000 \\\n"
            "  --candidate-min-ratings 100 \\\n"
            "  --candidate-min-year 1990 \\\n"
            "  --collaborative-core-limit 15000 \\\n"
            "  --public-min-year 2000 \\\n"
            "  --collaborative-min-year 1990 \\\n"
            "  --resume-tmdb \\\n"
            "  --audit\n\n"
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
            "  --collaborative-min-year 1990 \\\n"
            "  --audit\n\n"
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
    parser.add_argument("--max-tags-per-movie", type=int, default=10)

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
