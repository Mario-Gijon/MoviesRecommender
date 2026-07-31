import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.api.recommendation_errors import RecommendationHttpError
from app.api.routes.recommendation_routes import create_recommendations
from app.recommenders.collaborative.common.errors import (
    CollaborativeAlgorithmNotAvailableError,
    CollaborativeModelArtifactError,
    CollaborativeRecommendationError,
)
from app.recommenders.unified.models import (
    RecommendationRating,
    RecommendationServiceError,
    UnifiedRecommendationRequest,
)
from app.recommenders.unified.registry import RECOMMENDER_REGISTRY
from app.recommenders.unified.service import recommend_movies
from app.schemas.recommendation_schemas import RecommendationRequest
from app.schemas.request_id_schemas import is_valid_request_id


class RequestIdValidationTests(unittest.TestCase):
    def test_shared_request_id_rules(self) -> None:
        self.assertTrue(is_valid_request_id("request-1"))
        self.assertTrue(is_valid_request_id("  request-1  "))
        for value in (None, "", " \t", "x" * 129, 123):
            with self.subTest(value=value):
                self.assertFalse(is_valid_request_id(value))

    def test_request_schema_preserves_valid_id(self) -> None:
        request_id = "  exact frontend id  "
        request = RecommendationRequest.model_validate(
            {
                "requestId": request_id,
                "strategy": "collaborative",
                "algorithm": "popularity",
                "ratings": [],
                "limit": 1,
            }
        )
        self.assertEqual(request_id, request.requestId)

    def test_request_schema_rejects_invalid_ids(self) -> None:
        for value in ("", " \n", "x" * 129, 123):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    RecommendationRequest.model_validate(
                        {
                            "requestId": value,
                            "strategy": "collaborative",
                            "algorithm": "popularity",
                            "ratings": [],
                            "limit": 1,
                        }
                    )


class AdapterValidationTests(unittest.TestCase):
    def test_popularity_allows_empty_ratings(self) -> None:
        result = recommend_movies(
            UnifiedRecommendationRequest(
                strategy="collaborative",
                algorithm="popularity",
                ratings=[],
                limit=1,
            )
        )
        self.assertEqual(1, len(result.recommendations))

    def test_personalized_algorithms_require_a_rating(self) -> None:
        for algorithm in ("item_knn", "user_knn", "biased"):
            with self.subTest(algorithm=algorithm):
                with self.assertRaises(RecommendationServiceError) as raised:
                    recommend_movies(
                        UnifiedRecommendationRequest(
                            strategy="collaborative",
                            algorithm=algorithm,
                            ratings=[],
                            limit=1,
                        )
                    )
                self.assertEqual("insufficient_ratings", raised.exception.code)
                self.assertEqual(400, raised.exception.status_code)


class CollaborativeErrorTranslationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = RECOMMENDER_REGISTRY[
            ("collaborative", "item_knn")
        ]
        self.request = UnifiedRecommendationRequest(
            strategy="collaborative",
            algorithm="item_knn",
            ratings=[RecommendationRating(movie_id=1, rating=5)],
            limit=1,
        )

    def test_artifact_errors_become_safe_model_unavailable(self) -> None:
        errors = (
            CollaborativeModelArtifactError(
                code="artifact_missing",
                message="/private/model/path is missing",
            ),
            CollaborativeAlgorithmNotAvailableError(
                code="algorithm_missing",
                message="InternalClassName is unavailable",
            ),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with patch(
                    "app.recommenders.unified.registry."
                    "recommend_collaborative_movies",
                    side_effect=error,
                ):
                    with self.assertRaises(RecommendationServiceError) as raised:
                        self.adapter.recommend(self.request)
                translated = raised.exception
                self.assertEqual("model_unavailable", translated.code)
                self.assertEqual(503, translated.status_code)
                self.assertNotIn("/private", translated.message)
                self.assertEqual({}, translated.details)

    def test_generic_collaborative_domain_error_is_safe_4xx(self) -> None:
        error = CollaborativeRecommendationError(
            code="raw_internal_code",
            message="SELECT * FROM private_table",
        )
        with patch(
            "app.recommenders.unified.registry.recommend_collaborative_movies",
            side_effect=error,
        ):
            with self.assertRaises(RecommendationServiceError) as raised:
                self.adapter.recommend(self.request)
        translated = raised.exception
        self.assertEqual("invalid_recommendation_input", translated.code)
        self.assertEqual(400, translated.status_code)
        self.assertNotIn("SELECT", translated.message)

    def test_unexpected_errors_are_not_misclassified(self) -> None:
        with patch(
            "app.recommenders.unified.registry.recommend_collaborative_movies",
            side_effect=RuntimeError("unexpected implementation failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.adapter.recommend(self.request)


class CanonicalRouteErrorTests(unittest.TestCase):
    def test_unexpected_failure_is_sanitized_and_preserves_request_id(self) -> None:
        request = RecommendationRequest.model_validate(
            {
                "requestId": "unexpected-error-id",
                "strategy": "collaborative",
                "algorithm": "popularity",
                "ratings": [],
                "limit": 1,
            }
        )
        with patch(
            "app.api.routes.recommendation_routes.recommend_movies",
            side_effect=RuntimeError("/private/path must not leak"),
        ):
            with self.assertRaises(RecommendationHttpError) as raised:
                create_recommendations(request)
        error = raised.exception
        self.assertEqual("unexpected-error-id", error.request_id)
        self.assertEqual("internal_recommendation_error", error.code)
        self.assertEqual(500, error.status_code)
        self.assertNotIn("/private/path", error.message)
