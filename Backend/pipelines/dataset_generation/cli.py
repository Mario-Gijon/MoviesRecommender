from __future__ import annotations

import argparse
import getpass
import os
import shlex
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

from app.core.config import settings
from app.project_paths.dataset_paths import (
    DATA_DIR,
    ML_32M_CANDIDATES_PATH,
    ML_32M_DEMO_CATALOG_PATH,
    ML_32M_DEMO_RATINGS_PATH,
    ML_32M_TMDB_ENRICHED_PATH,
    OFFLINE_DATASET_AUDIT_DIR,
    OFFLINE_DATASET_DIR,
    OFFLINE_DATASET_MANIFEST_PATH,
    OFFLINE_DATASET_POSTERS_DIR,
)
from .movielens_source import MovieLensSourceError, default_paths, has_valid_extracted_files
from .run_movielens_32m_pipeline import (
    DatasetPipelineConfig,
    build_stage_command,
    run_pipeline,
    select_stages,
)


RECOMMENDED_VALUES = {
    "candidate_limit": 15000, "candidate_min_ratings": 100, "candidate_min_year": 1990,
    "candidate_max_year": None, "max_tags_per_movie": 35, "public_limit": None,
    "collaborative_core_limit": 15000, "catalog_min_ratings": 100,
    "public_min_year": 2000, "collaborative_min_year": 1990, "family_only": False,
}
PRESETS = {"defaults": {}, "recommended": RECOMMENDED_VALUES, "custom": {}}
NUMERIC_FIELDS = (
    "candidate_limit", "candidate_min_ratings", "candidate_min_year", "candidate_max_year",
    "max_tags_per_movie", "public_limit", "collaborative_core_limit", "catalog_min_ratings",
    "public_min_year", "collaborative_min_year",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the portable MovieLens/TMDB offline dataset.")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Skip final confirmation.")
    parser.add_argument("--source", choices=("existing", "download", "zip"))
    parser.add_argument("--zip-path", type=Path)
    parser.add_argument("--preset", choices=tuple(PRESETS), default="recommended")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start-at", choices=("candidates", "enrich", "catalog", "ratings", "export", "posters", "audit"))
    parser.add_argument("--stop-after", choices=("candidates", "enrich", "catalog", "ratings", "export", "posters", "audit"))
    for field in NUMERIC_FIELDS:
        parser.add_argument("--" + field.replace("_", "-"), type=int)
    parser.add_argument("--family-only", action="store_true", default=None)
    parser.add_argument("--display-language")
    tmdb = parser.add_mutually_exclusive_group()
    tmdb.add_argument("--resume-tmdb", action="store_true", default=None)
    tmdb.add_argument("--force-tmdb", action="store_true", default=None)
    parser.add_argument("--skip-posters", action="store_true")
    parser.add_argument("--audit", action="store_true")
    return parser


def resolve_config(args: argparse.Namespace) -> DatasetPipelineConfig:
    values = asdict(DatasetPipelineConfig())
    values.update(PRESETS[args.preset])
    for field in NUMERIC_FIELDS + ("display_language", "start_at", "stop_after"):
        value = getattr(args, field)
        if value is not None:
            values[field] = value
    if args.family_only is not None:
        values["family_only"] = args.family_only
    if args.resume_tmdb is not None:
        values["resume_tmdb"] = args.resume_tmdb
    if args.force_tmdb:
        values["force_tmdb"] = True
        values["resume_tmdb"] = False
    values["skip_posters"] = args.skip_posters
    values["audit"] = args.audit
    config = DatasetPipelineConfig(**values)
    validate_config(config)
    return config


def validate_config(config: DatasetPipelineConfig) -> None:
    for field in NUMERIC_FIELDS:
        value = getattr(config, field)
        if value is not None and value <= 0:
            raise ValueError(f"{field.replace('_', ' ')} must be greater than zero.")
    if config.candidate_max_year is not None and config.candidate_max_year < config.candidate_min_year:
        raise ValueError("candidate maximum year must not be before candidate minimum year.")
    select_stages(config)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.non_interactive:
            _validate_non_interactive(args)
            config = resolve_config(args)
            source = args.source
            token = _resolve_token(config, interactive=False, dry_run=args.dry_run)
        else:
            config, source, zip_path = _interactive_configuration(args)
            args.zip_path = zip_path
            token = _resolve_token(config, interactive=True, dry_run=args.dry_run)
            _print_plan(config, source, args.zip_path)
            if not args.dry_run and not _ask_yes_no("Run this dataset pipeline now?", default=False):
                print("Cancelled. No pipeline stages were run.")
                return 0
        _print_plan(config, source, args.zip_path)
        if args.dry_run:
            print("Dry run complete. No files were downloaded or modified.")
            return 0
        if token:
            os.environ["MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN"] = token
        stages = run_pipeline(config, source=source, zip_path=args.zip_path)
        print("Dataset pipeline completed: " + ", ".join(stages))
        print(f"Offline dataset: {OFFLINE_DATASET_DIR}")
        print("Recommender models were not rebuilt.")
        return 0
    except (MovieLensSourceError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Dataset pipeline failed: {exc}", file=sys.stderr)
        print("Completed intermediate outputs were retained; rerun with --start-at to resume.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled. No further pipeline stages were run.", file=sys.stderr)
        return 130


def _validate_non_interactive(args: argparse.Namespace) -> None:
    if not args.source:
        raise ValueError("--non-interactive requires --source.")
    if args.source == "zip" and args.zip_path is None:
        raise ValueError("--source zip requires --zip-path.")
    if args.source != "zip" and args.zip_path is not None:
        raise ValueError("--zip-path is only valid with --source zip.")
    if not args.dry_run and not args.yes:
        raise ValueError("Non-interactive execution that may replace outputs requires --yes.")


def _interactive_configuration(args: argparse.Namespace) -> tuple[DatasetPipelineConfig, str, Path | None]:
    paths = default_paths()
    print(f"Persistent data root: {DATA_DIR}")
    raw_available = has_valid_extracted_files(paths.dataset_dir)
    print("MovieLens raw files: " + ("available" if raw_available else "missing or incomplete"))
    source = _ask_choice("MovieLens source", ("existing", "download", "zip"), "existing" if raw_available else "download")
    zip_path = Path(_ask_text("Path to MovieLens ZIP", required=True)) if source == "zip" else None
    preset = _ask_choice("Parameter profile", ("recommended", "defaults", "custom"), args.preset)
    args.preset = preset
    config = resolve_config(args)
    if preset == "custom":
        config = _ask_custom_config(config)
    config = replace(
        config,
        skip_posters=not _ask_yes_no("Download missing posters?", default=not args.skip_posters),
        audit=_ask_yes_no("Generate offline audit?", default=args.audit),
    )
    if "enrich" in select_stages(config):
        resume = _ask_yes_no("Resume existing TMDB enrichment when possible?", default=config.resume_tmdb)
        force = False if resume else _ask_yes_no("Force a fresh TMDB enrichment?", default=False)
        config = replace(config, resume_tmdb=resume, force_tmdb=force)
    validate_config(config)
    _print_existing_output_summary()
    return config, source, zip_path


def _ask_custom_config(config: DatasetPipelineConfig) -> DatasetPipelineConfig:
    values = asdict(config)
    for field in NUMERIC_FIELDS:
        current = values[field]
        optional = field in {"candidate_max_year", "public_limit"}
        values[field] = _ask_integer(field.replace("_", " "), current, optional=optional)
    values["family_only"] = _ask_yes_no("Family-only mode?", default=bool(values["family_only"]))
    values["display_language"] = _ask_text("Display language", default=values["display_language"], required=True)
    values["start_at"] = _ask_choice("Start stage", ("candidates", "enrich", "catalog", "ratings", "export", "posters", "audit"), values["start_at"])
    values["stop_after"] = _ask_choice("Stop after stage (or none)", ("none", "candidates", "enrich", "catalog", "ratings", "export", "posters", "audit"), "none")
    if values["stop_after"] == "none":
        values["stop_after"] = None
    custom = DatasetPipelineConfig(**values)
    validate_config(custom)
    return custom


def _resolve_token(config: DatasetPipelineConfig, *, interactive: bool, dry_run: bool) -> str | None:
    if dry_run or "enrich" not in select_stages(config):
        return None
    token = settings.tmdb_bearer_token or os.environ.get("MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN")
    if token:
        return token
    if interactive:
        token = getpass.getpass("TMDB bearer token (input hidden): ").strip()
        if token:
            return token
    raise ValueError("TMDB enrichment requires MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN.")


def _print_plan(config: DatasetPipelineConfig, source: str, zip_path: Path | None) -> None:
    stages = select_stages(config)
    print("\nExecution summary")
    print(f"Data root: {DATA_DIR}")
    print(f"Source: {source}" + (f" ({zip_path})" if zip_path else ""))
    print("Stages: " + ", ".join(stages))
    print("Existing generated candidate, enrichment, catalog, ratings and offline CSV outputs may be regenerated.")
    print("Existing posters are reused unless a stage explicitly replaces them. Recommender models are never touched.")
    for stage in stages:
        print(f"  {stage}: {shlex.join(build_stage_command(stage, config))}")


def _print_existing_output_summary() -> None:
    outputs = (ML_32M_CANDIDATES_PATH, ML_32M_TMDB_ENRICHED_PATH, ML_32M_DEMO_CATALOG_PATH, ML_32M_DEMO_RATINGS_PATH, OFFLINE_DATASET_MANIFEST_PATH, OFFLINE_DATASET_POSTERS_DIR, OFFLINE_DATASET_AUDIT_DIR)
    existing = [path.name for path in outputs if path.exists()]
    print("Existing outputs detected: " + (", ".join(existing) if existing else "none"))


def _ask_yes_no(question: str, *, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        value = input(f"{question} [{suffix}] ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes", "s", "si", "sí"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please answer yes or no.")


def _ask_choice(question: str, choices: tuple[str, ...], default: str) -> str:
    while True:
        value = input(f"{question} ({'/'.join(choices)}) [{default}]: ").strip().lower() or default
        if value in choices:
            return value
        print("Choose one of: " + ", ".join(choices))


def _ask_integer(question: str, default: int | None, *, optional: bool) -> int | None:
    while True:
        value = input(f"{question} [{'' if default is None else default}]: ").strip()
        if not value:
            return default
        if optional and value.lower() in {"none", "null", "-"}:
            return None
        try:
            parsed = int(value)
        except ValueError:
            print("Enter a whole number.")
            continue
        if parsed > 0:
            return parsed
        print("Enter a number greater than zero.")


def _ask_text(question: str, *, default: str | None = None, required: bool) -> str:
    while True:
        value = input(f"{question}" + (f" [{default}]" if default else "") + ": ").strip() or (default or "")
        if value or not required:
            return value
        print("A value is required.")


if __name__ == "__main__":
    raise SystemExit(main())
