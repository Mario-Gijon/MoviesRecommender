import asyncio
import json
import unittest
from unittest.mock import patch

from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.requests import Request

from app.api.recommendation_errors import (
    RecommendationHttpError,
    recommendation_http_error_handler,
    recommendation_validation_error_handler,
)
from app.api.routes.catalog_routes import get_catalog_status
from app.api.routes.health_routes import health_check
from app.api.routes.recommendation_routes import (
    create_collaborative_recommendations,
    create_content_based_recommendations,
    create_recommendations,
)
from app.catalog.catalog_repository import catalog_repository
from app.main import app
from app.recommenders.unified.models import UnifiedRecommendationResult
from app.recommenders.unified.registry import RECOMMENDER_REGISTRY
from app.schemas.collaborative_recommendation_schemas import (
    CollaborativeRecommendationRequest,
)
from app.schemas.content_recommendation_schemas import (
    ContentBasedRecommendationRequest,
)
from app.schemas.recommendation_schemas import RecommendationRequest


REGISTERED_COMBINATIONS = (
    ("content", "tfidf"),
    ("collaborative", "popularity"),
    ("collaborative", "item_knn"),
    ("collaborative", "user_knn"),
    ("collaborative", "biased"),
)
RATING_VALUES = (5, 4, 2, 5, 1, 4, 2, 5, 1, 4, 2, 5)


class RecommendationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.movie_ids = [
            int(movie["movieId"])
            for movie in catalog_repository.get_featured_movies()[:12]
        ]
        cls.valid_responses: dict[tuple[str, str], dict] = {}
        for strategy, algorithm in REGISTERED_COMBINATIONS:
            rating_count = 3 if strategy == "content" else 12
            status, body = _submit_canonical(
                _canonical_payload(
                    strategy=strategy,
                    algorithm=algorithm,
                    movie_ids=cls.movie_ids[:rating_count],
                    request_id=f"valid-{strategy}-{algorithm}",
                )
            )
            if status != 200:
                raise AssertionError(
                    f"{strategy}/{algorithm} failed during test setup: {body}"
                )
            cls.valid_responses[(strategy, algorithm)] = body

    def test_every_real_registered_combination_is_covered(self) -> None:
        self.assertEqual(set(REGISTERED_COMBINATIONS), set(RECOMMENDER_REGISTRY))
        self.assertEqual(
            set(REGISTERED_COMBINATIONS),
            set(self.valid_responses),
        )

    def test_all_algorithms_return_the_same_contract(self) -> None:
        expected_top_level = {
            "requestId",
            "strategy",
            "algorithm",
            "recommendations",
            "meta",
        }
        expected_item = {
            "rank",
            "movie",
            "score",
            "matchPercentage",
            "explanation",
        }
        expected_explanation = {"summary", "reasons"}

        for combination, response in self.valid_responses.items():
            with self.subTest(combination=combination):
                self.assertEqual(expected_top_level, set(response))
                self.assertIsInstance(response["recommendations"], list)
                self.assertGreater(len(response["recommendations"]), 0)
                for item in response["recommendations"]:
                    self.assertEqual(expected_item, set(item))
                    self.assertEqual(expected_explanation, set(item["explanation"]))
                    self.assertIsInstance(item["score"], (int, float))
                    self.assertGreaterEqual(item["matchPercentage"], 0)
                    self.assertLessEqual(item["matchPercentage"], 100)
                    self.assertIsInstance(item["explanation"]["summary"], str)
                    self.assertIsInstance(item["explanation"]["reasons"], list)

    def test_request_id_rank_and_meta_invariants(self) -> None:
        for combination, response in self.valid_responses.items():
            with self.subTest(combination=combination):
                strategy, algorithm = combination
                self.assertEqual(
                    f"valid-{strategy}-{algorithm}",
                    response["requestId"],
                )
                self.assertEqual(strategy, response["strategy"])
                self.assertEqual(algorithm, response["algorithm"])
                self.assertEqual(
                    list(range(1, len(response["recommendations"]) + 1)),
                    [item["rank"] for item in response["recommendations"]],
                )
                self.assertEqual(
                    len(response["recommendations"]),
                    response["meta"]["count"],
                )
                self.assertEqual(2, response["meta"]["limit"])

    def test_missing_request_id_is_generated(self) -> None:
        payload = _canonical_payload(
            strategy="collaborative",
            algorithm="popularity",
            movie_ids=self.movie_ids[:1],
            request_id=None,
        )
        status, body = _submit_canonical(payload)
        self.assertEqual(200, status)
        self.assertIsInstance(body["requestId"], str)
        self.assertTrue(body["requestId"])
        self.assertTrue(body["requestId"].startswith("rec-"))

    def test_unsupported_strategy(self) -> None:
        self._assert_domain_error(
            strategy="hybrid",
            algorithm="tfidf",
            expected_code="unsupported_strategy",
        )

    def test_unsupported_algorithm(self) -> None:
        self._assert_domain_error(
            strategy="content",
            algorithm="missing",
            expected_code="unsupported_algorithm",
        )

    def test_unsupported_strategy_algorithm_combination(self) -> None:
        self._assert_domain_error(
            strategy="content",
            algorithm="popularity",
            expected_code="unsupported_strategy_algorithm_combination",
        )

    def test_empty_ratings(self) -> None:
        payload = _canonical_payload(
            strategy="collaborative",
            algorithm="popularity",
            movie_ids=[],
            request_id="empty-ratings",
        )
        self._assert_error(
            payload,
            expected_status=400,
            expected_code="empty_ratings",
        )

    def test_content_requires_three_non_neutral_ratings(self) -> None:
        payload = _canonical_payload(
            strategy="content",
            algorithm="tfidf",
            movie_ids=self.movie_ids[:2],
            request_id="too-few",
        )
        self._assert_error(
            payload,
            expected_status=400,
            expected_code="insufficient_ratings",
        )

    def test_duplicate_movie_rating(self) -> None:
        payload = _canonical_payload(
            strategy="collaborative",
            algorithm="popularity",
            movie_ids=[self.movie_ids[0], self.movie_ids[0]],
            request_id="duplicate",
        )
        self._assert_error(
            payload,
            expected_status=400,
            expected_code="duplicate_movie_rating",
        )

    def test_unknown_movie(self) -> None:
        payload = _canonical_payload(
            strategy="collaborative",
            algorithm="popularity",
            movie_ids=[999_999_999],
            request_id="unknown",
        )
        self._assert_error(
            payload,
            expected_status=400,
            expected_code="unknown_movie",
        )

    def test_invalid_rating_is_normalized_as_422(self) -> None:
        payload = _canonical_payload(
            strategy="collaborative",
            algorithm="popularity",
            movie_ids=self.movie_ids[:1],
            request_id="bad-rating",
        )
        payload["ratings"][0]["rating"] = 6
        self._assert_validation_error(
            payload,
            expected_code="invalid_rating_value",
        )

    def test_invalid_limit_is_normalized_as_422(self) -> None:
        payload = _canonical_payload(
            strategy="collaborative",
            algorithm="popularity",
            movie_ids=self.movie_ids[:1],
            request_id="bad-limit",
        )
        payload["limit"] = 0
        self._assert_validation_error(
            payload,
            expected_code="invalid_limit",
        )

    def test_validation_error_without_request_id_generates_one(self) -> None:
        payload = _canonical_payload(
            strategy="collaborative",
            algorithm="popularity",
            movie_ids=self.movie_ids[:1],
            request_id=None,
        )
        payload["limit"] = 0
        status, body = _submit_validation_error(payload)
        self.assertEqual(422, status)
        self.assertTrue(body["requestId"].startswith("rec-"))

    def test_compatibility_content_endpoint_uses_unified_contract(self) -> None:
        payload = ContentBasedRecommendationRequest(
            requestId="legacy-content",
            ratings=[
                {"movieId": movie_id, "rating": rating}
                for movie_id, rating in zip(
                    self.movie_ids[:3],
                    RATING_VALUES[:3],
                    strict=True,
                )
            ],
            limit=1,
            templateSessionId="ignored-legacy-session",
        )
        response = create_content_based_recommendations(payload).model_dump(
            mode="json"
        )
        self.assertEqual("legacy-content", response["requestId"])
        self.assertEqual("content", response["strategy"])
        self.assertEqual("tfidf", response["algorithm"])
        self.assertEqual(1, response["meta"]["count"])

    def test_compatibility_collaborative_endpoint_uses_unified_contract(self) -> None:
        payload = CollaborativeRecommendationRequest(
            requestId="legacy-collaborative",
            ratings=[
                {"movieId": self.movie_ids[0], "rating": 5},
            ],
            limit=1,
        )
        response = create_collaborative_recommendations(payload).model_dump(
            mode="json"
        )
        self.assertEqual("legacy-collaborative", response["requestId"])
        self.assertEqual("collaborative", response["strategy"])
        self.assertEqual(1, response["meta"]["count"])

    def test_compatibility_endpoint_delegates_to_unified_service(self) -> None:
        service_result = UnifiedRecommendationResult(
            strategy="content",
            algorithm="tfidf",
            recommendations=[],
            limit=1,
        )
        payload = ContentBasedRecommendationRequest(
            ratings=[
                {"movieId": movie_id, "rating": rating}
                for movie_id, rating in zip(
                    self.movie_ids[:3],
                    RATING_VALUES[:3],
                    strict=True,
                )
            ],
            limit=1,
        )
        with patch(
            "app.api.routes.recommendation_routes.recommend_movies",
            return_value=service_result,
        ) as unified_service:
            response = create_content_based_recommendations(payload)

        unified_service.assert_called_once()
        self.assertEqual([], response.recommendations)
        self.assertEqual(0, response.meta.count)

    def test_unexpected_error_is_normalized_without_internal_details(self) -> None:
        payload = RecommendationRequest.model_validate(
            _canonical_payload(
                strategy="collaborative",
                algorithm="popularity",
                movie_ids=self.movie_ids[:1],
                request_id="internal-failure",
            )
        )
        with patch(
            "app.api.routes.recommendation_routes.recommend_movies",
            side_effect=RuntimeError("/private/path should not leak"),
        ):
            with self.assertRaises(RecommendationHttpError) as raised:
                create_recommendations(payload)

        status, body = _render_http_error(raised.exception)
        self.assertEqual(500, status)
        self.assertEqual(
            "internal_recommendation_error",
            body["error"]["code"],
        )
        self.assertNotIn("/private/path", json.dumps(body))
        self.assertEqual("internal-failure", body["requestId"])

    def test_legacy_routes_are_deprecated_and_catalog_health_remain(self) -> None:
        routes = {
            route.path: route
            for route in app.routes
            if isinstance(route, APIRoute)
        }
        self.assertIn("/recommendations", routes)
        self.assertTrue(routes["/recommendations/content-based"].deprecated)
        self.assertTrue(routes["/recommendations/collaborative"].deprecated)
        self.assertEqual({"status": "ok"}, health_check())
        self.assertGreater(get_catalog_status()["totalMovies"], 0)

    def _assert_domain_error(
        self,
        *,
        strategy: str,
        algorithm: str,
        expected_code: str,
    ) -> None:
        payload = _canonical_payload(
            strategy=strategy,
            algorithm=algorithm,
            movie_ids=self.movie_ids[:3],
            request_id=f"error-{expected_code}",
        )
        self._assert_error(
            payload,
            expected_status=400,
            expected_code=expected_code,
        )

    def _assert_error(
        self,
        payload: dict,
        *,
        expected_status: int,
        expected_code: str,
    ) -> None:
        status, body = _submit_canonical(payload)
        self.assertEqual(expected_status, status)
        self.assertEqual(payload["requestId"], body["requestId"])
        self.assertEqual(
            {"requestId", "error"},
            set(body),
        )
        self.assertEqual(
            {"code", "message", "details"},
            set(body["error"]),
        )
        self.assertEqual(expected_code, body["error"]["code"])
        self.assertIsInstance(body["error"]["details"], dict)

    def _assert_validation_error(
        self,
        payload: dict,
        *,
        expected_code: str,
    ) -> None:
        status, body = _submit_validation_error(payload)
        self.assertEqual(422, status)
        self.assertEqual(payload["requestId"], body["requestId"])
        self.assertEqual(expected_code, body["error"]["code"])


def _canonical_payload(
    *,
    strategy: str,
    algorithm: str,
    movie_ids: list[int],
    request_id: str | None,
) -> dict:
    payload = {
        "strategy": strategy,
        "algorithm": algorithm,
        "ratings": [
            {"movieId": movie_id, "rating": rating}
            for movie_id, rating in zip(
                movie_ids,
                RATING_VALUES[: len(movie_ids)],
                strict=True,
            )
        ],
        "limit": 2,
    }
    if request_id is not None:
        payload["requestId"] = request_id
    return payload


def _submit_canonical(payload: dict) -> tuple[int, dict]:
    try:
        request = RecommendationRequest.model_validate(payload)
    except ValidationError:
        return _submit_validation_error(payload)

    try:
        response = create_recommendations(request)
    except RecommendationHttpError as exc:
        return _render_http_error(exc)
    return 200, response.model_dump(mode="json")


def _submit_validation_error(payload: dict) -> tuple[int, dict]:
    try:
        RecommendationRequest.model_validate(payload)
    except ValidationError as exc:
        validation_error = RequestValidationError(
            exc.errors(),
            body=payload,
        )
    else:
        raise AssertionError("Payload did not produce a validation error.")

    response = asyncio.run(
        recommendation_validation_error_handler(
            _request_for_path("/recommendations"),
            validation_error,
        )
    )
    return response.status_code, json.loads(response.body)


def _render_http_error(
    error: RecommendationHttpError,
) -> tuple[int, dict]:
    response = asyncio.run(
        recommendation_http_error_handler(
            _request_for_path("/recommendations"),
            error,
        )
    )
    return response.status_code, json.loads(response.body)


def _request_for_path(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("test", 1),
            "server": ("test", 80),
        }
    )
