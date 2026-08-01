from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from scipy.sparse import load_npz

from app.core.config import settings
from app.project_paths.dataset_paths import (
    COLLABORATIVE_RECOMMENDER_MODELS_DIR,
    CONTENT_BASED_RECOMMENDER_MODELS_DIR,
    DATA_DIR,
    OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
    OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
    OFFLINE_DATASET_MANIFEST_PATH,
    OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
    RECOMMENDER_MODELS_DIR,
    TMP_DIR,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.builder import build_biased_matrix_factorization_model
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import ALGORITHM_ID as BIASED_ALGORITHM_ID
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.storage import (
    get_biased_matrix_factorization_variant_artifacts,
    load_biased_matrix_factorization_manifest,
    validate_biased_matrix_factorization_runtime_artifacts,
)
from app.recommenders.collaborative.algorithms.item_knn_cosine.builder import build_item_knn_cosine_model
from app.recommenders.collaborative.algorithms.item_knn_cosine.models import ALGORITHM_ID as ITEM_KNN_ALGORITHM_ID
from app.recommenders.collaborative.algorithms.item_knn_cosine.storage import (
    get_item_knn_cosine_variant_artifacts,
    load_item_knn_cosine_manifest,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.builder import build_popularity_baseline_model
from app.recommenders.collaborative.algorithms.popularity_baseline.models import ALGORITHM_ID as POPULARITY_ALGORITHM_ID, VARIANT_ID as POPULARITY_VARIANT_ID
from app.recommenders.collaborative.algorithms.popularity_baseline.storage import (
    get_popularity_baseline_artifacts,
    load_popularity_baseline_manifest,
    load_popularity_ranking,
)
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.builder import build_user_knn_pearson_shrinkage_model
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.models import ALGORITHM_ID as USER_KNN_ALGORITHM_ID, VARIANT_ID as USER_KNN_VARIANT_ID
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.storage import (
    get_user_knn_pearson_shrinkage_artifacts,
    load_user_knn_pearson_shrinkage_manifest,
)
from app.recommenders.collaborative.common.offline_context import build_collaborative_offline_context
from app.recommenders.content_based.build_content_index import build_content_index
from app.recommenders.content_based.constants import (
    CONTENT_FEATURE_METADATA_PATH,
    CONTENT_FEATURE_NAMES_PATH,
    MOVIE_CONTENT_FEATURES_PATH,
    MOVIE_CONTENT_INDEX_PATH,
    REQUIRED_COLUMNS,
)

from .profile import BIASED_VARIANT_ID, ITEM_KNN_VARIANT_ID, biased_config, item_knn_config, popularity_config, user_knn_config


ALGORITHM_ORDER = ("tfidf", "popularity", "item_knn", "user_knn", "biased")
PUBLIC_ALGORITHMS = (*ALGORITHM_ORDER, "all")


class RecommenderBuildError(RuntimeError):
    pass


class RecommenderBuildStageError(RecommenderBuildError):
    def __init__(self, algorithm: str, phase: str, cause: Exception) -> None:
        super().__init__(f"Recommender build failed: {algorithm}\nPhase: {phase}")
        self.algorithm, self.phase, self.cause = algorithm, phase, cause


class RecommenderPromotionError(RecommenderBuildError):
    pass


@dataclass(frozen=True)
class BuildPaths:
    data_root: Path
    public_movies: Path
    support_movies: Path
    ratings: Path
    manifest: Path
    models_root: Path
    content_root: Path
    collaborative_root: Path
    temp_root: Path


def default_paths() -> BuildPaths:
    return BuildPaths(
        DATA_DIR, OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
        OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
        OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH, OFFLINE_DATASET_MANIFEST_PATH,
        RECOMMENDER_MODELS_DIR, CONTENT_BASED_RECOMMENDER_MODELS_DIR,
        COLLABORATIVE_RECOMMENDER_MODELS_DIR, TMP_DIR,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild persisted recommender artifacts from offline_dataset.")
    parser.add_argument("--algorithm", choices=PUBLIC_ALGORITHMS, action="append", help="Algorithm to rebuild; repeatable. Defaults to all.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan and run read-only input preflight.")
    parser.add_argument("--yes", action="store_true", help="Confirm a real rebuild without prompting.")
    return parser


def select_algorithms(values: list[str] | None) -> tuple[str, ...]:
    selected = values or ["all"]
    if "all" in selected and len(selected) != 1:
        raise RecommenderBuildError("--algorithm all cannot be combined with another algorithm.")
    wanted = set(ALGORITHM_ORDER if selected == ["all"] else selected)
    return tuple(algorithm for algorithm in ALGORITHM_ORDER if algorithm in wanted)


def validate_runtime_profile(algorithms: tuple[str, ...] = ALGORITHM_ORDER) -> None:
    mismatches = []
    if "item_knn" in algorithms and ITEM_KNN_VARIANT_ID != settings.active_collaborative_model_variant:
        mismatches.append(f"item_knn expected runtime variant {settings.active_collaborative_model_variant!r}, profile builds {ITEM_KNN_VARIANT_ID!r}")
    if "biased" in algorithms and BIASED_VARIANT_ID != settings.biased_matrix_factorization_model_variant:
        mismatches.append(f"biased expected runtime variant {settings.biased_matrix_factorization_model_variant!r}, profile builds {BIASED_VARIANT_ID!r}")
    if mismatches:
        raise RecommenderBuildError("Runtime/profile variant mismatch; no artifacts were modified: " + "; ".join(mismatches))


def preflight(algorithms: tuple[str, ...], paths: BuildPaths) -> None:
    required = [(paths.public_movies, set(REQUIRED_COLUMNS), "public_movies.csv")]
    if any(algorithm in {"item_knn", "user_knn", "biased"} for algorithm in algorithms):
        required.extend([
            (paths.support_movies, {"movieId"}, "collaborative_support_movies.csv"),
            (paths.ratings, {"userId", "movieId", "rating"}, "collaborative_ratings.csv"),
        ])
    for path, headers, label in required:
        _validate_csv(path, headers, label)
    if paths.manifest.exists():
        try:
            json.loads(paths.manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RecommenderBuildError("offline_dataset manifest is unreadable.") from exc


def _validate_csv(path: Path, required_headers: set[str], label: str) -> None:
    try:
        if not path.is_file() or path.stat().st_size == 0:
            raise RecommenderBuildError(f"Required dataset input is missing, not a regular file, or empty: {label}.")
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            headers = set(reader.fieldnames or ())
            if not required_headers.issubset(headers):
                raise RecommenderBuildError(f"Required dataset input has missing CSV headers: {label}.")
            if next(reader, None) is None:
                raise RecommenderBuildError(f"Required dataset input has no data rows: {label}.")
    except RecommenderBuildError:
        raise
    except OSError as exc:
        raise RecommenderBuildError(f"Required dataset input could not be read: {label}.") from exc


def targets_for(algorithm: str, *, content_root: Path, collaborative_root: Path) -> Path:
    if algorithm == "tfidf":
        return content_root
    if algorithm == "popularity":
        return collaborative_root / POPULARITY_ALGORITHM_ID / POPULARITY_VARIANT_ID
    if algorithm == "item_knn":
        return collaborative_root / ITEM_KNN_ALGORITHM_ID / ITEM_KNN_VARIANT_ID
    if algorithm == "user_knn":
        return collaborative_root / USER_KNN_ALGORITHM_ID / USER_KNN_VARIANT_ID
    if algorithm == "biased":
        return collaborative_root / BIASED_ALGORITHM_ID / BIASED_VARIANT_ID
    raise ValueError(f"Unsupported algorithm: {algorithm}")


def _context(paths: BuildPaths, stage_collaborative_root: Path):
    return build_collaborative_offline_context(
        ratings_csv_path=paths.ratings, public_movies_csv_path=paths.public_movies,
        collaborative_support_movies_csv_path=paths.support_movies,
        collaborative_model_artifact_root=stage_collaborative_root,
        audit_output_root=paths.data_root / "recommender_build_audit_unused",
    )


def build_selected(algorithms: tuple[str, ...], paths: BuildPaths) -> None:
    validate_runtime_profile()
    preflight(algorithms, paths)
    paths.temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="recommender-build-", dir=paths.temp_root) as temporary:
        stage_models = Path(temporary) / "recommender_models"
        stage_content = stage_models / "content_based"
        stage_collaborative = stage_models / "collaborative"
        context = _context(paths, stage_collaborative)
        for algorithm in algorithms:
            try:
                if algorithm == "tfidf":
                    build_content_index(public_movies_path=paths.public_movies, output_dir=stage_content)
                elif algorithm == "popularity":
                    build_popularity_baseline_model(popularity_config(), offline_context=context)
                elif algorithm == "item_knn":
                    build_item_knn_cosine_model(item_knn_config(), offline_context=context)
                elif algorithm == "user_knn":
                    build_user_knn_pearson_shrinkage_model(user_knn_config(), offline_context=context)
                else:
                    build_biased_matrix_factorization_model(biased_config(), offline_context=context)
            except Exception as exc:
                raise RecommenderBuildStageError(algorithm, "build", exc) from exc
        for algorithm in algorithms:
            try:
                validate_staged(algorithm, stage_content, stage_collaborative)
            except Exception as exc:
                raise RecommenderBuildStageError(algorithm, "validation", exc) from exc
        try:
            promote(algorithms, stage_content, stage_collaborative, paths)
        except Exception as exc:
            raise RecommenderPromotionError("Recommender build failed: promotion\nPhase: promotion") from exc


def validate_staged(algorithm: str, content_root: Path, collaborative_root: Path) -> None:
    target = targets_for(algorithm, content_root=content_root, collaborative_root=collaborative_root)
    if algorithm == "tfidf":
        features = load_npz(target / MOVIE_CONTENT_FEATURES_PATH.name)
        movies = json.loads((target / MOVIE_CONTENT_INDEX_PATH.name).read_text(encoding="utf-8"))
        names = json.loads((target / CONTENT_FEATURE_NAMES_PATH.name).read_text(encoding="utf-8"))
        json.loads((target / CONTENT_FEATURE_METADATA_PATH.name).read_text(encoding="utf-8"))
        if features.shape != (len(movies), len(names)):
            raise RuntimeError("TF-IDF staged artifact dimensions are inconsistent.")
    elif algorithm == "popularity":
        manifest = load_popularity_baseline_manifest(artifact_root=collaborative_root)
        if manifest.get("algorithmId") != POPULARITY_ALGORITHM_ID or not load_popularity_ranking(artifact_root=collaborative_root):
            raise RuntimeError("Popularity staged artifact is invalid or empty.")
    elif algorithm == "item_knn":
        manifest = load_item_knn_cosine_manifest(ITEM_KNN_VARIANT_ID, artifact_root=collaborative_root)
        if manifest.get("algorithmId") != ITEM_KNN_ALGORITHM_ID or manifest.get("variantId") != ITEM_KNN_VARIANT_ID:
            raise RuntimeError("Item KNN staged manifest has an unexpected variant.")
        _sqlite_has_row(get_item_knn_cosine_variant_artifacts(ITEM_KNN_VARIANT_ID, artifact_root=collaborative_root).neighbors_sqlite_path)
    elif algorithm == "user_knn":
        manifest = load_user_knn_pearson_shrinkage_manifest(artifact_root=collaborative_root)
        artifacts = get_user_knn_pearson_shrinkage_artifacts(artifact_root=collaborative_root)
        if manifest.get("algorithmId") != USER_KNN_ALGORITHM_ID or not _csv_has_row(artifacts.user_stats_csv_path):
            raise RuntimeError("User KNN staged artifact is invalid or empty.")
        _sqlite_has_row(artifacts.ratings_sqlite_path)
    else:
        artifacts = get_biased_matrix_factorization_variant_artifacts(BIASED_VARIANT_ID, artifact_root=collaborative_root)
        manifest = load_biased_matrix_factorization_manifest(BIASED_VARIANT_ID, artifact_root=collaborative_root)
        if manifest.get("algorithmId") != BIASED_ALGORITHM_ID or manifest.get("variantId") != BIASED_VARIANT_ID:
            raise RuntimeError("Biased staged manifest has an unexpected variant.")
        validate_biased_matrix_factorization_runtime_artifacts(artifacts)


def _sqlite_has_row(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("Required SQLite artifact is missing or empty.")
    with sqlite3.connect(path) as connection:
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if not tables or not any(connection.execute(f'SELECT 1 FROM "{name}" LIMIT 1').fetchone() for (name,) in tables):
            raise RuntimeError("SQLite artifact has no rows.")


def _csv_has_row(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.reader(file)
            return next(reader, None) is not None and next(reader, None) is not None
    except OSError as exc:
        raise RuntimeError("CSV artifact is unreadable.") from exc


def promote(algorithms: tuple[str, ...], stage_content: Path, stage_collaborative: Path, paths: BuildPaths) -> None:
    backups: list[tuple[Path, Path | None]] = []
    backup_root = stage_content.parent.parent / "backups"
    try:
        for algorithm in algorithms:
            staged = targets_for(algorithm, content_root=stage_content, collaborative_root=stage_collaborative)
            production = targets_for(algorithm, content_root=paths.content_root, collaborative_root=paths.collaborative_root)
            production.parent.mkdir(parents=True, exist_ok=True)
            backup = backup_root / algorithm if production.exists() else None
            backups.append((production, backup))
            if backup is not None:
                backup.parent.mkdir(parents=True, exist_ok=True)
                os.replace(production, backup)
            os.replace(staged, production)
    except OSError as exc:
        for production, backup in reversed(backups):
            if production.exists():
                shutil.rmtree(production)
            if backup is not None and backup.exists():
                os.replace(backup, production)
        raise RuntimeError("Promotion failed; previous targets were restored.") from exc


def print_plan(algorithms: tuple[str, ...], paths: BuildPaths) -> None:
    print("Recommender build plan")
    print(f"Data root: {paths.data_root}")
    print("Selected algorithms: " + ", ".join(algorithms))
    print("Canonical order: " + ", ".join(ALGORITHM_ORDER))
    print("Inputs: public_movies.csv" + (", collaborative_support_movies.csv, collaborative_ratings.csv" if any(a != "tfidf" for a in algorithms) else ""))
    print(f"Runtime variants: item_knn={settings.active_collaborative_model_variant}, biased={settings.biased_matrix_factorization_model_variant}")
    for algorithm in algorithms:
        target = targets_for(algorithm, content_root=paths.content_root, collaborative_root=paths.collaborative_root)
        print(f"  {algorithm}: {target.name} ({'exists' if target.exists() else 'new'})")
    print("Current targets remain untouched until every staged build validates.")
    print("Restart the API service after successful promotion to reload artifacts.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        algorithms = select_algorithms(args.algorithm)
        paths = default_paths()
        print_plan(algorithms, paths)
        if args.dry_run:
            preflight(algorithms, paths)
            print("Dry run complete. Input preflight passed; no files were modified.")
            return 0
        if not args.yes:
            if not sys.stdin.isatty():
                raise RecommenderBuildError("Refusing a non-interactive rebuild without --yes.")
            if input("Rebuild selected recommender artifacts? [y/N] ").strip().lower() not in {"y", "yes"}:
                print("Cancelled. No artifacts were modified.")
                return 0
        build_selected(algorithms, paths)
        print("Recommender artifacts were rebuilt successfully.")
        print("Restart the API service so the running process reloads the new artifacts.")
        return 0
    except RecommenderBuildStageError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except RecommenderBuildError as exc:
        print(f"Recommender build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
