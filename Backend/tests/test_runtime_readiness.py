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
