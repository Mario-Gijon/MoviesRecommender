import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.readiness import RuntimeReadiness
from app.recommenders.collaborative.registry import (
    COLLABORATIVE_RECOMMENDER_FACTORIES,
)
from app.recommenders.unified.registry import RECOMMENDER_REGISTRY
from tests.http_test_client import LiveApiServer


BACKEND_DIR = Path(__file__).resolve().parents[1]
EXPECTED_COMBINATIONS = {
    ("content", "tfidf"),
    ("collaborative", "popularity"),
    ("collaborative", "item_knn"),
    ("collaborative", "user_knn"),
    ("collaborative", "biased"),
}


class RuntimeDataConfigurationTests(unittest.TestCase):
    def test_default_data_root_preserves_local_layout(self) -> None:
        result = _run_python(
            "from app.project_paths.dataset_paths import DATA_DIR; print(DATA_DIR)"
        )

        self.assertEqual(str(BACKEND_DIR / "data"), result.stdout.strip())

    def test_environment_controlled_data_root_updates_runtime_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            result = _run_python(
                "from app.project_paths.dataset_paths import "
                "DATA_DIR, OFFLINE_DATASET_DIR, RECOMMENDER_MODELS_DIR; "
                "print(DATA_DIR); print(OFFLINE_DATASET_DIR); print(RECOMMENDER_MODELS_DIR)",
                data_dir=temporary_dir,
            )

            self.assertEqual(
                [
                    temporary_dir,
                    str(Path(temporary_dir) / "offline_dataset"),
                    str(Path(temporary_dir) / "recommender_models"),
                ],
                result.stdout.splitlines(),
            )

    def test_empty_data_root_starts_http_api_with_controlled_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            server = LiveApiServer(
                environment={"MOVIES_RECOMMENDER_DATA_DIR": temporary_dir}
            )
            self.addCleanup(server.stop)
            server.start()

            health = server.request("GET", "/health")
            self.assertEqual(200, health.status)
            self.assertEqual({"status": "ok"}, health.body)

            readiness = server.request("GET", "/ready")
            self.assertEqual(503, readiness.status)
            self.assertEqual("runtime_data_unavailable", readiness.body["detail"]["code"])

            catalog = server.request("GET", "/catalog/status")
            self.assertEqual(503, catalog.status)
            self.assertEqual("catalog_unavailable", catalog.body["detail"]["code"])

            recommendation = server.request(
                "POST",
                "/recommendations",
                json_body={
                    "requestId": "empty-data-root",
                    "strategy": "collaborative",
                    "algorithm": "popularity",
                    "ratings": [],
                    "limit": 2,
                },
            )
            self.assertEqual(503, recommendation.status)
            self.assertEqual("empty-data-root", recommendation.body["requestId"])
            self.assertEqual(
                "model_unavailable",
                recommendation.body["error"]["code"],
            )

    def test_ready_can_succeed_with_controlled_readiness_fixture(self) -> None:
        from app.api.routes.health_routes import readiness_check

        with patch(
            "app.api.routes.health_routes.check_runtime_readiness",
            return_value=RuntimeReadiness(missing=()),
        ):
            self.assertEqual({"status": "ready"}, readiness_check())

    def test_readiness_accepts_runtime_only_recommender_artifacts(self) -> None:
        source = (
            "from app.core.readiness import check_runtime_readiness; "
            "from app.project_paths.dataset_paths import OFFLINE_DATASET_MANIFEST_PATH, "
            "OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH, "
            "OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH, "
            "OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH, "
            "OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH, "
            "OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH, OFFLINE_DATASET_POSTERS_DIR; "
            "from app.recommenders.content_based.constants import CONTENT_INDEX_REQUIRED_PATHS; "
            "from app.recommenders.collaborative.algorithms.popularity_baseline.storage import get_popularity_baseline_artifacts; "
            "from app.recommenders.collaborative.algorithms.item_knn_cosine.storage import get_item_knn_cosine_variant_artifacts; "
            "from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.storage import get_user_knn_pearson_shrinkage_artifacts; "
            "from app.recommenders.collaborative.algorithms.biased_matrix_factorization.storage import get_biased_matrix_factorization_variant_artifacts; "
            "from app.core.config import settings; "
            "offline=(OFFLINE_DATASET_MANIFEST_PATH, OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH, OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH, OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH, OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH, OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH); "
            "[(path.parent.mkdir(parents=True, exist_ok=True), path.write_text('fixture')) for path in offline]; "
            "OFFLINE_DATASET_POSTERS_DIR.mkdir(parents=True); "
            "[(path.parent.mkdir(parents=True, exist_ok=True), path.write_text('fixture')) for path in CONTENT_INDEX_REQUIRED_PATHS.values()]; "
            "popularity=get_popularity_baseline_artifacts(); item=get_item_knn_cosine_variant_artifacts(settings.active_collaborative_model_variant); user=get_user_knn_pearson_shrinkage_artifacts(); biased=get_biased_matrix_factorization_variant_artifacts(settings.biased_matrix_factorization_model_variant); "
            "runtime=(popularity.manifest_path, popularity.ranking_sqlite_path, item.manifest_path, item.neighbors_sqlite_path, user.manifest_path, user.ratings_sqlite_path, biased.manifest_path, biased.movie_factors_path, biased.movie_biases_path, biased.movie_index_path, biased.global_stats_path, biased.training_metrics_path); "
            "[(path.parent.mkdir(parents=True, exist_ok=True), path.write_text('fixture')) for path in runtime]; "
            "print(check_runtime_readiness().is_ready)"
        )
        with tempfile.TemporaryDirectory() as temporary_dir:
            result = _run_python(source, data_dir=temporary_dir)
            self.assertEqual("True", result.stdout.strip())

    def test_current_registry_combinations_remain_registered(self) -> None:
        self.assertEqual(EXPECTED_COMBINATIONS, set(RECOMMENDER_REGISTRY))
        self.assertEqual(
            {
                "popularity_baseline",
                "item_knn_cosine",
                "user_knn_pearson_shrinkage",
                "biased_matrix_factorization",
            },
            set(COLLABORATIVE_RECOMMENDER_FACTORIES),
        )


def _run_python(source: str, *, data_dir: str | None = None) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    if data_dir is not None:
        environment["MOVIES_RECOMMENDER_DATA_DIR"] = data_dir
    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=BACKEND_DIR,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
