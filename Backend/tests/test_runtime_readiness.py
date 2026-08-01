import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


class RuntimeDataConfigurationTests(unittest.TestCase):
    def test_default_data_root_preserves_local_layout(self) -> None:
        output = _run_python(
            "from app.core.config import settings; print(settings.data_dir)",
            data_dir=None,
        )
        self.assertEqual(str(BACKEND_DIR / "data"), output.strip())

    def test_empty_data_root_allows_import_health_and_controlled_errors(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = _run_python(
                _http_probe_script(),
                data_dir=Path(temporary_directory),
            )

        responses = json.loads(output)
        self.assertEqual(200, responses["health"]["status"])
        self.assertEqual({"status": "ok"}, responses["health"]["body"])
        self.assertEqual(503, responses["ready"]["status"])
        self.assertEqual(503, responses["catalog"]["status"])
        self.assertEqual(503, responses["recommendations"]["status"])
        self.assertEqual(
            "runtime_data_unavailable",
            responses["ready"]["body"]["detail"]["code"],
        )
        self.assertEqual(
            "catalog_unavailable",
            responses["catalog"]["body"]["detail"]["code"],
        )

    def test_ready_succeeds_with_controlled_runtime_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            _write_ready_fixture(data_dir)
            output = _run_python(_http_probe_script(), data_dir=data_dir)

        responses = json.loads(output)
        self.assertEqual(200, responses["health"]["status"])
        self.assertEqual(200, responses["ready"]["status"])
        self.assertEqual({"status": "ready"}, responses["ready"]["body"])


def _run_python(source: str, *, data_dir: Path | None) -> str:
    environment = os.environ.copy()
    environment.pop("MOVIES_RECOMMENDER_DATA_DIR", None)
    if data_dir is not None:
        environment["MOVIES_RECOMMENDER_DATA_DIR"] = str(data_dir)
    completed = subprocess.run(
        [sys.executable, "-c", source],
        cwd=BACKEND_DIR,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _http_probe_script() -> str:
    return """
import json
from fastapi import HTTPException
from app.main import app
from app.api.routes.catalog_routes import get_catalog_status
from app.api.routes.health_routes import health_check, readiness_check
from app.api.routes.recommendation_routes import create_recommendations
from app.domain.recommendations.recommendation_schemas import RecommendationRequest

def invoke(callable_):
    try:
        return {"status": 200, "body": callable_()}
    except HTTPException as exc:
        return {"status": exc.status_code, "body": {"detail": exc.detail}}

responses = {
    "health": invoke(health_check),
    "ready": invoke(readiness_check),
    "catalog": invoke(get_catalog_status),
    "recommendations": invoke(
        lambda: create_recommendations(
            RecommendationRequest(strategy="content", ratings=[])
        )
    ),
}
print(json.dumps(responses))
"""


def _write_ready_fixture(data_dir: Path) -> None:
    csv_dir = data_dir / "offline_dataset" / "csv"
    csv_dir.mkdir(parents=True)
    (data_dir / "offline_dataset" / "images" / "posters").mkdir(parents=True)
    (data_dir / "offline_dataset" / "manifest.json").write_text("{}")
    for filename in (
        "public_movies.csv",
        "collaborative_support_movies.csv",
        "excluded_movies.csv",
        "movie_ratings_summary.csv",
        "collaborative_ratings.csv",
    ):
        (csv_dir / filename).write_text("")

    content_dir = data_dir / "recommender_models" / "content_based"
    content_dir.mkdir(parents=True)
    for filename in (
        "movie_content_features.npz",
        "movie_content_index.json",
        "content_feature_names.json",
        "content_feature_metadata.json",
    ):
        (content_dir / filename).write_text("")

    for algorithm in (
        "item_knn_cosine",
        "popularity_baseline",
        "user_knn_pearson_shrinkage",
        "biased_matrix_factorization",
    ):
        manifest_dir = (
            data_dir
            / "recommender_models"
            / "collaborative"
            / algorithm
            / "test"
        )
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "model_manifest.json").write_text("{}")
