from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass

from .movielens_source import MovieLensSourceError, prepare_source


STAGE_ORDER = ("candidates", "enrich", "catalog", "ratings", "export", "posters", "audit")
SOURCE_PREPARATION_STAGES = {"candidates", "ratings"}


class DatasetStageError(RuntimeError):
    def __init__(self, stage: str, command: list[str], cause: BaseException) -> None:
        super().__init__(f"Dataset stage failed: {stage}")
        self.stage = stage
        self.command = command
        self.cause = cause


@dataclass(frozen=True)
class DatasetPipelineConfig:
    candidate_limit: int = 8000
    candidate_min_ratings: int = 100
    candidate_min_year: int = 1995
    candidate_max_year: int | None = None
    candidate_min_tags: int = 0
    max_tags_per_movie: int = 35
    public_limit: int | None = None
    collaborative_core_limit: int = 8000
    catalog_min_ratings: int = 100
    public_min_year: int = 2000
    public_min_runtime: int = 60
    collaborative_min_year: int = 1995
    family_only: bool = False
    display_language: str = "es-ES"
    resume_tmdb: bool = True
    force_tmdb: bool = False
    skip_posters: bool = False
    audit: bool = False
    start_at: str = "candidates"
    stop_after: str | None = None


def select_stages(config: DatasetPipelineConfig) -> list[str]:
    start = STAGE_ORDER.index(config.start_at)
    stop = STAGE_ORDER.index(config.stop_after) if config.stop_after else len(STAGE_ORDER) - 1
    if stop < start:
        raise ValueError("--stop-after must not be before --start-at.")
    stages = list(STAGE_ORDER[start : stop + 1])
    return [
        stage
        for stage in stages
        if not (stage == "posters" and config.skip_posters)
        and not (stage == "audit" and not config.audit)
    ]


def stages_require_raw_source(config: DatasetPipelineConfig) -> bool:
    return bool(SOURCE_PREPARATION_STAGES.intersection(select_stages(config)))


def build_stage_command(stage: str, config: DatasetPipelineConfig) -> list[str]:
    command = [sys.executable, "-m"]
    if stage == "candidates":
        command += [
            "pipelines.dataset_generation.build_movielens_32m_candidates", "--limit", str(config.candidate_limit),
            "--min-ratings", str(config.candidate_min_ratings), "--min-year", str(config.candidate_min_year),
            "--min-tags", str(config.candidate_min_tags),
            "--max-tags-per-movie", str(config.max_tags_per_movie),
        ]
        if config.candidate_max_year is not None:
            command += ["--max-year", str(config.candidate_max_year)]
    elif stage == "enrich":
        command += ["pipelines.dataset_generation.enrich_movielens_32m_with_tmdb", "--display-language", config.display_language]
        if config.force_tmdb:
            command.append("--force")
        elif config.resume_tmdb:
            command.append("--resume")
    elif stage == "catalog":
        command += [
            "pipelines.dataset_generation.build_demo_catalog_from_movielens_32m",
            "--collaborative-core-limit", str(config.collaborative_core_limit),
            "--min-ratings", str(config.catalog_min_ratings), "--public-min-year", str(config.public_min_year),
            "--public-min-runtime", str(config.public_min_runtime),
            "--collaborative-min-year", str(config.collaborative_min_year),
        ]
        if config.public_limit is not None:
            command += ["--public-limit", str(config.public_limit)]
        if config.family_only:
            command.append("--family-only")
    elif stage == "ratings":
        command.append("pipelines.dataset_generation.build_demo_ratings_from_movielens_32m")
    elif stage == "export":
        command.append("pipelines.dataset_generation.export_offline_dataset_from_movielens_32m")
    elif stage == "posters":
        command.append("pipelines.dataset_generation.download_offline_movie_posters")
    elif stage == "audit":
        command.append("pipelines.dataset_generation.audit_offline_dataset")
    else:
        raise ValueError(f"Unsupported stage: {stage}")
    return command


def run_pipeline(
    config: DatasetPipelineConfig,
    *,
    source: str = "existing",
    zip_path=None,
    dry_run: bool = False,
    runner=subprocess.run,
) -> list[str]:
    stages = select_stages(config)
    if not stages:
        return []
    if dry_run:
        return stages
    if stages_require_raw_source(config):
        prepare_source(source, zip_path=zip_path)
    for stage in stages:
        command = build_stage_command(stage, config)
        try:
            runner(command, check=True)
        except (subprocess.CalledProcessError, OSError) as exc:
            raise DatasetStageError(stage, command, exc) from exc
    return stages


def main() -> None:
    args = _parse_args()
    config = DatasetPipelineConfig(
        candidate_limit=args.candidate_limit, candidate_min_ratings=args.candidate_min_ratings,
        candidate_min_year=args.candidate_min_year, candidate_max_year=args.candidate_max_year, candidate_min_tags=args.candidate_min_tags,
        max_tags_per_movie=args.max_tags_per_movie, public_limit=args.public_limit,
        collaborative_core_limit=args.collaborative_core_limit, catalog_min_ratings=args.catalog_min_ratings,
        public_min_year=args.public_min_year, collaborative_min_year=args.collaborative_min_year,
        public_min_runtime=args.public_min_runtime,
        family_only=args.family_only, display_language=args.display_language,
        resume_tmdb=args.resume_tmdb, force_tmdb=args.force_tmdb,
        skip_posters=args.skip_posters, audit=args.audit, start_at=args.start_at, stop_after=args.stop_after,
    )
    try:
        stages = select_stages(config)
        _print_plan(config, stages)
        if args.dry_run:
            return
        run_pipeline(config, source="download" if args.download_raw_movielens else "existing")
    except DatasetStageError as exc:
        raise SystemExit(f"Dataset stage failed: {exc.stage}") from exc
    except (MovieLensSourceError, ValueError) as exc:
        raise SystemExit(f"Pipeline failed: {exc}") from exc


def _print_plan(config: DatasetPipelineConfig, stages: list[str]) -> None:
    print(f"Selected stages: {', '.join(stages) or 'none'}")
    for stage in stages:
        print(f"{stage}: {shlex.join(build_stage_command(stage, config))}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the MovieLens 32M offline dataset pipeline.")
    parser.add_argument("--candidate-limit", type=int, default=8000)
    parser.add_argument("--candidate-min-ratings", type=int, default=100)
    parser.add_argument("--candidate-min-year", type=int, default=1995)
    parser.add_argument("--candidate-max-year", type=int)
    parser.add_argument("--candidate-min-tags", type=int, default=0)
    parser.add_argument("--max-tags-per-movie", type=int, default=35)
    parser.add_argument("--download-raw-movielens", action="store_true")
    parser.add_argument("--public-limit", type=int)
    parser.add_argument("--collaborative-core-limit", type=int, default=8000)
    parser.add_argument("--catalog-min-ratings", type=int, default=100)
    parser.add_argument("--public-min-year", type=int, default=2000)
    parser.add_argument("--public-min-runtime", type=int, default=60)
    parser.add_argument("--collaborative-min-year", type=int, default=1995)
    parser.add_argument("--family-only", action="store_true")
    parser.add_argument("--display-language", default="es-ES")
    tmdb = parser.add_mutually_exclusive_group()
    tmdb.add_argument("--resume-tmdb", dest="resume_tmdb", action="store_true")
    tmdb.add_argument("--no-resume-tmdb", dest="resume_tmdb", action="store_false")
    tmdb.add_argument("--force-tmdb", action="store_true")
    parser.set_defaults(resume_tmdb=True)
    parser.add_argument("--skip-posters", action="store_true")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start-at", choices=STAGE_ORDER, default="candidates")
    parser.add_argument("--stop-after", choices=STAGE_ORDER)
    return parser.parse_args()


if __name__ == "__main__":
    main()
