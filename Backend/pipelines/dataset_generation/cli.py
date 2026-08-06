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
from .cleanup import DatasetCleanupError, DatasetPaths, apply_cleanup
from app.catalog.constants import PUBLIC_MIN_RUNTIME_MINUTES
from .run_movielens_32m_pipeline import (
    DatasetStageError,
    DatasetPipelineConfig,
    build_stage_command,
    run_pipeline,
    select_stages,
    stages_require_raw_source,
)
from .reconfigure_offline_dataset import (
    POLICIES,
    OfflineDatasetReconfigurationError,
    preview as preview_offline_reconfiguration,
    reconfigure as reconfigure_offline_dataset,
)


RECOMMENDED_VALUES = {
    "candidate_limit": 15000, "candidate_min_ratings": 100, "candidate_min_year": 1990,
    "candidate_max_year": None, "candidate_min_tags": 0, "max_tags_per_movie": 35, "public_limit": None,
    "collaborative_core_limit": 15000, "catalog_min_ratings": 100,
    "public_min_year": 2000, "collaborative_min_year": 1990, "family_only": True,
}
PRESETS = {"defaults": {}, "recommended": RECOMMENDED_VALUES, "custom": {}}
NUMERIC_FIELDS = (
    "candidate_limit", "candidate_min_ratings", "candidate_min_year", "candidate_max_year", "candidate_min_tags",
    "max_tags_per_movie", "public_limit", "collaborative_core_limit", "catalog_min_ratings",
    "public_min_year", "collaborative_min_year",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the portable MovieLens/TMDB offline dataset.")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Skip final confirmation.")
    parser.add_argument("--action", choices=("generate", "reconfigure", "validate", "cleanup"))
    parser.add_argument("--source", choices=("existing", "download", "zip", "reconfigure"))
    parser.add_argument("--public-audience-policy", choices=tuple(POLICIES))
    parser.add_argument("--zip-path", type=Path)
    parser.add_argument("--preset", choices=tuple(PRESETS), default="recommended")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start-at", choices=("candidates", "enrich", "catalog", "ratings", "export", "posters", "audit"))
    parser.add_argument("--stop-after", choices=("candidates", "enrich", "catalog", "ratings", "export", "posters", "audit"))
    for field in NUMERIC_FIELDS:
        parser.add_argument("--" + field.replace("_", "-"), type=int)
    audience = parser.add_mutually_exclusive_group()
    audience.add_argument("--family-only", dest="family_only", action="store_true", default=None)
    audience.add_argument("--no-family-only", dest="family_only", action="store_false")
    parser.add_argument("--display-language")
    tmdb = parser.add_mutually_exclusive_group()
    tmdb.add_argument("--resume-tmdb", action="store_true", default=None)
    tmdb.add_argument("--force-tmdb", action="store_true", default=None)
    parser.add_argument("--skip-posters", action="store_true")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--cleanup", choices=("none", "standard", "minimal"), default="none")
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
        if field == "candidate_min_tags":
            if value < 0: raise ValueError("candidate minimum tags must be zero or greater.")
        elif value is not None and value <= 0:
            raise ValueError(f"{field.replace('_', ' ')} must be greater than zero.")
    if config.candidate_max_year is not None and config.candidate_max_year < config.candidate_min_year:
        raise ValueError("candidate maximum year must not be before candidate minimum year.")
    select_stages(config)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.action == "validate":
            from .cleanup import validate_final_dataset
            validate_final_dataset(DatasetPaths(DATA_DIR))
            print(f"Dataset offline válido: {OFFLINE_DATASET_DIR}")
            return 0
        if args.action == "cleanup":
            if not args.yes and not args.dry_run:
                raise ValueError("La limpieza no interactiva requiere --yes.")
            removed, skipped = apply_cleanup(args.cleanup, DatasetPaths(DATA_DIR), dry_run=args.dry_run)
            _print_cleanup_summary(args.cleanup, DatasetPaths(DATA_DIR), removed, skipped)
            return 0
        plan_printed = False
        if args.non_interactive:
            config = resolve_config(args)
            _validate_non_interactive(args, config)
            source = "reconfigure" if (args.action == "reconfigure" or args.source == "reconfigure" or args.public_audience_policy) else (args.source or "existing")
            if source == "reconfigure":
                return _run_offline_reconfiguration(args)
            token = _resolve_token(config, interactive=False, dry_run=args.dry_run)
        else:
            config, source, zip_path = _interactive_configuration(args)
            args.zip_path = zip_path
            if source == "reconfigure":
                return _run_offline_reconfiguration(args)
            token = _resolve_token(config, interactive=True, dry_run=args.dry_run)
            _print_plan(config, source, args.zip_path, mode=getattr(args, "configuration_mode", None), cleanup=args.cleanup)
            plan_printed = True
            if not args.dry_run and not _ask_yes_no("Start generating the dataset with these settings?", default=False):
                print("Cancelled. No pipeline stages were run.")
                return 0
        if source == "reconfigure":
            return _run_offline_reconfiguration(args)
        if not plan_printed:
            _print_plan(config, source, args.zip_path, mode=args.preset, cleanup=args.cleanup)
        _print_cleanup_preview(args.cleanup, DatasetPaths(DATA_DIR))
        if args.dry_run:
            print("Dry run complete. No files were downloaded or modified.")
            return 0
        if token:
            os.environ["MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN"] = token
        stages = run_pipeline(config, source=source, zip_path=args.zip_path)
        print("Dataset pipeline completed: " + ", ".join(stages))
        removed, skipped = apply_cleanup(args.cleanup, DatasetPaths(DATA_DIR), skip_posters=config.skip_posters)
        _print_cleanup_summary(args.cleanup, DatasetPaths(DATA_DIR), removed, skipped)
        print(f"Offline dataset: {OFFLINE_DATASET_DIR}")
        print("Recommender models were not rebuilt.")
        return 0
    except DatasetStageError as exc:
        print(f"Dataset stage failed: {exc.stage}", file=sys.stderr)
        print("Completed intermediate outputs were retained; rerun with --start-at to resume.", file=sys.stderr)
        return 1
    except DatasetCleanupError as exc:
        print(f"Dataset generation completed, but cleanup failed: {exc}", file=sys.stderr)
        return 1
    except (MovieLensSourceError, OfflineDatasetReconfigurationError, ValueError) as exc:
        print(f"Dataset pipeline failed: {exc}", file=sys.stderr)
        print("Completed intermediate outputs were retained; rerun with --start-at to resume.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled. No further pipeline stages were run.", file=sys.stderr)
        return 130


def _validate_non_interactive(args: argparse.Namespace, config: DatasetPipelineConfig) -> None:
    reconfigure_requested = args.action == "reconfigure" or args.source == "reconfigure" or bool(args.public_audience_policy)
    if args.action == "generate" and reconfigure_requested:
        raise ValueError("Generation action cannot be combined with reconfiguration options.")
    if reconfigure_requested:
        if not args.public_audience_policy:
            raise ValueError("--source reconfigure requires --public-audience-policy.")
        if args.zip_path is not None:
            raise ValueError("--zip-path is not valid with --source reconfigure.")
        return
    if stages_require_raw_source(config) and not args.source:
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
    selected_action = _resolve_interactive_action(args)
    # Keep direct callers of the pre-action helper compatible: older tests and
    # integrations may supply a configuration-mode value as the first choice.
    legacy_mode = selected_action if selected_action in {"recommended", "custom"} else None
    action = "generate" if legacy_mode else selected_action
    args.configuration_action = action
    if action == "reconfigure":
        args.public_audience_policy = args.public_audience_policy or _ask_public_audience_policy()
        return DatasetPipelineConfig(), "reconfigure", None

    mode = legacy_mode or _ask_configuration_mode()
    args.configuration_mode = mode
    args.preset = "recommended"
    config = resolve_config(args)
    if mode == "custom":
        config = _ask_custom_config(config)
    else:
        _print_recommended_settings(config)
    source = "existing"
    zip_path = None
    if stages_require_raw_source(config):
        source = _ask_source("existing")
        raw_available = has_valid_extracted_files(paths.dataset_dir)
        print("MovieLens raw files: " + ("available" if raw_available else "missing or incomplete"))
        zip_path = Path(_ask_text("Path to MovieLens ZIP", required=True)) if source == "zip" else None
    config = replace(
        config,
        skip_posters=not _ask_explained_yes_no("Download missing movie posters?", "Poster files are displayed by the frontend and stored in the persistent data directory. Existing poster files are reused.", default=not args.skip_posters),
        audit=_ask_explained_yes_no("Generate a dataset quality report?", "This creates diagnostic files for inspecting the generated dataset. The report is not required to run the application.", default=args.audit),
    )
    if "enrich" in select_stages(config):
        resume = _ask_explained_yes_no("Reuse completed TMDB enrichment and continue from the last saved point?", "Recommended. This avoids repeating successful TMDB API requests after an interruption.", default=config.resume_tmdb)
        force = False if resume else _ask_explained_yes_no("Start TMDB enrichment again from the beginning?", "This repeats TMDB API requests and may take considerably longer.", default=False)
        config = replace(config, resume_tmdb=resume, force_tmdb=force)
    validate_config(config)
    args.cleanup = _ask_cleanup()
    _print_existing_output_summary()
    return config, source, zip_path


def _ask_custom_config(config: DatasetPipelineConfig) -> DatasetPipelineConfig:
    values = asdict(config)
    for field in NUMERIC_FIELDS:
        values[field] = _ask_integer(field.replace("_", " "), values[field], optional=field in {"candidate_max_year", "public_limit"}, allow_zero=field == "candidate_min_tags")
    values["family_only"] = _ask_yes_no("Family-only mode?", default=bool(values["family_only"]))
    values["display_language"] = _ask_text("Display language", default=values["display_language"], required=True)
    values["start_at"] = _ask_choice("Start stage", ("candidates", "enrich", "catalog", "ratings", "export", "posters", "audit"), values["start_at"])
    values["stop_after"] = _ask_choice("Stop after stage (or none)", ("none", "candidates", "enrich", "catalog", "ratings", "export", "posters", "audit"), values["stop_after"] or "none")
    if values["stop_after"] == "none":
        values["stop_after"] = None
    return DatasetPipelineConfig(**values)


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


def _print_plan(config: DatasetPipelineConfig, source: str, zip_path: Path | None, *, mode: str | None = None, cleanup: str = "none") -> None:
    print("\nDataset installation summary")
    audience = "Family friendly only" if config.family_only else "Family friendly and teen"
    print(f"Persistent data directory: {DATA_DIR}\nConfiguration mode: {_preset_label(mode)}\nMovieLens source: {_source_label(source)}\nMaximum movies considered: {config.candidate_limit}\nMinimum ratings per movie: {config.candidate_min_ratings}\nRelease year range: {config.candidate_min_year} to {config.candidate_max_year or 'No upper limit'}\nMinimum distinct user tags: {config.candidate_min_tags}\nMaximum tags stored per movie: {config.max_tags_per_movie}\nCatalog minimum ratings: {config.catalog_min_ratings}\nPublic catalogue limit: {config.public_limit or 'All eligible movies'}\nPublic minimum year: {config.public_min_year}\nCollaborative minimum year: {config.collaborative_min_year}\nPublic audience policy: {audience}\nPublic minimum runtime: 70 minutes\nPublic documentaries: Excluded\nCollaborative core limit: {config.collaborative_core_limit}\nDisplay language: {config.display_language}\nDownload posters: {'No' if config.skip_posters else 'Yes'}\nGenerate audit: {'Yes' if config.audit else 'No'}\nTMDB behavior: {'Fresh enrichment' if config.force_tmdb else 'Resume completed enrichment'}\nCleanup mode: {_cleanup_label(cleanup)}\nCleanup effect: {_cleanup_effect(cleanup)}")


def _print_recommended_settings(config: DatasetPipelineConfig) -> None:
    audience = "Family friendly only" if config.family_only else "Family friendly and teen"
    print("Recommended settings\nMaximum movies considered: " + str(config.candidate_limit) + "\nMinimum ratings required per movie: " + str(config.candidate_min_ratings) + f"\nRelease year range: {config.candidate_min_year} to {config.candidate_max_year or 'No upper limit'}\nMinimum distinct user tags: {config.candidate_min_tags}\nMaximum user tags stored per movie: {config.max_tags_per_movie}\nCatalog minimum ratings: {config.catalog_min_ratings}\nPublic catalogue limit: {config.public_limit or 'All eligible movies'}\nPublic minimum year: {config.public_min_year}\nCollaborative minimum year: {config.collaborative_min_year}\nPublic audience policy: {audience}\nCollaborative core size: {config.collaborative_core_limit}\nDisplay language: {config.display_language}\nThe movie count is a maximum; the final catalogue may contain fewer movies after filtering and TMDB validation. A minimum-tag value of 0 disables the tag requirement.")


def _print_cleanup_summary(mode: str, paths: DatasetPaths, removed: tuple[Path, ...], skipped: tuple[Path, ...]) -> None:
    print("\nCleanup mode: " + mode)
    print("Removed: " + (", ".join(str(path) for path in removed) if removed else "none"))
    print("Skipped: " + (", ".join(str(path) for path in skipped) if skipped else "none"))
    print("Preserved: " + ", ".join(str(path) for path in paths.preserved))


def _print_cleanup_preview(mode: str, paths: DatasetPaths) -> None:
    print("Cleanup mode: " + mode)
    print("Would remove: " + (", ".join(str(path) for path in paths.removable(mode)) or "nothing"))
    print("Always preserved: " + ", ".join(str(path) for path in paths.preserved))


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
        if value.isdigit() and 1 <= int(value) <= len(choices):
            value = choices[int(value) - 1]
        if value in choices:
            return value
        print("Choose one of: " + ", ".join(choices))


def _ask_configuration_mode() -> str:
    print("How would you like to configure the dataset?\n\n1. Recommended\n   Balanced settings suitable for most installations.\n   The exact values will be shown before continuing.\n\n2. Custom\n   Configure all dataset and pipeline parameters.")
    return _ask_choice("Configuration", ("recommended", "custom"), "recommended")


def _ask_source(default: str) -> str:
    print("Choose how MovieLens data will be obtained:\n\n1. Download automatically\n   Downloads the official MovieLens 32M archive.\n\n2. Reuse existing files\n   Uses valid files already stored in the persistent data directory.\n\n3. Import a local ZIP\n   Imports an existing MovieLens 32M ZIP from this computer.")
    return _ask_choice("MovieLens source", ("download", "existing", "zip"), default)


def _resolve_interactive_action(args: argparse.Namespace) -> str:
    """Resolve explicit automation flags before asking the interactive action."""
    if args.action:
        return args.action
    if args.source == "reconfigure" or args.public_audience_policy:
        return "reconfigure"
    if args.source in {"download", "existing", "zip"} or args.start_at or args.stop_after:
        return "generate"
    return _ask_action()


def _ask_action() -> str:
    print("What would you like to do?\n\n1. Generate or rebuild an offline dataset\n   Configures and runs the MovieLens dataset pipeline.\n\n2. Reconfigure an existing offline dataset\n   Changes the public audience policy without rebuilding the dataset.")
    return _ask_choice("Action", ("generate", "reconfigure"), "generate")


def _ask_public_audience_policy() -> str:
    print("Select the public audience policy:\n\n1. Family friendly only\n   Public suitability categories: family_friendly\n\n2. Family friendly and teen\n   Public suitability categories: family_friendly, teen\n\n3. All classified categories\n   Public suitability categories: family_friendly, teen, adult_or_sensitive")
    return _ask_choice("Public audience policy", ("family_only", "family_and_teen", "all_classified"), "family_and_teen")


def _run_offline_reconfiguration(args: argparse.Namespace) -> int:
    policy = args.public_audience_policy
    if not policy:
        raise ValueError("A public audience policy is required for offline dataset reconfiguration.")
    summary = preview_offline_reconfiguration(OFFLINE_DATASET_DIR, policy)
    print("\nOffline dataset reconfiguration summary\n\n"
          f"Dataset directory: {summary.dataset_dir}\nCurrent policy: {summary.current_policy}\nNew policy: {summary.new_policy}\n\n"
          f"Minimum runtime policy: {PUBLIC_MIN_RUNTIME_MINUTES} minutes\nCurrent public movies: {summary.current_public_movies}\nNew public movies: {summary.new_public_movies}\nMoved to collaborative support: {summary.moved_to_support}\n"
          f"Current collaborative support movies: {summary.current_support_movies}\nNew collaborative support movies: {summary.new_support_movies}\nTotal collaborative catalogue: {summary.total_movies}\n\n"
          "Collaborative ratings: unchanged\nPosters: unchanged\nRecommender models: unchanged\nAudit: will be regenerated")
    if args.dry_run:
        print("Dry run complete. No files were modified.")
        return 0
    if not args.yes and not _ask_yes_no("Apply this reconfiguration?", default=False):
        print("Cancelled. No dataset files were modified.")
        return 0
    from . import audit_offline_dataset
    final = reconfigure_offline_dataset(OFFLINE_DATASET_DIR, policy, regenerate_audit=audit_offline_dataset.main)
    print(f"Offline dataset reconfigured: {final.new_public_movies} public, {final.new_support_movies} collaborative support.")
    print(f"Offline dataset: {final.dataset_dir}")
    return 0


def _ask_cleanup() -> str:
    print("Choose what should be removed after successful generation:\n\n1. Keep everything\n   Keeps final dataset files, posters, audit files, MovieLens source files and pipeline cache.\n   Uses the most disk space.\n\n2. Standard cleanup\n   Removes pipeline cache and downloaded MovieLens source files.\n   Keeps the final dataset, posters and dataset quality report.\n\n3. Minimal runtime files\n   Removes pipeline cache, downloaded MovieLens source files and dataset quality report.\n   Keeps only the final dataset files, manifest and posters required by the application.")
    return _ask_choice("Cleanup", ("none", "standard", "minimal"), "standard")


def _ask_explained_yes_no(question: str, explanation: str, *, default: bool) -> bool:
    print(explanation)
    return _ask_yes_no(question, default=default)


def _preset_label(value: str | None) -> str:
    return {"recommended": "Recommended", "custom": "Custom", "defaults": "Defaults"}.get(value or "recommended", "Recommended")


def _source_label(value: str) -> str:
    return {"download": "Download automatically", "existing": "Reuse existing files", "zip": "Import local ZIP", "reconfigure": "Reconfigure existing offline dataset"}.get(value, value)


def _cleanup_label(value: str) -> str:
    return {"none": "Keep everything", "standard": "Standard cleanup", "minimal": "Minimal runtime files"}.get(value, value)


def _cleanup_effect(value: str) -> str:
    return {"none": "Removes nothing", "standard": "Removes pipeline cache and raw MovieLens data", "minimal": "Removes pipeline cache, raw MovieLens data and offline audit files"}.get(value, "Removes nothing")


def _ask_integer(question: str, default: int | None, *, optional: bool, allow_zero: bool = False) -> int | None:
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
        if parsed > 0 or (allow_zero and parsed == 0):
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
