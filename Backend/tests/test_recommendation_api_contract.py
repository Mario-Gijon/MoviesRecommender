import unittest
from urllib.parse import urlencode

from app.catalog.catalog_repository import catalog_repository
from app.core.config import settings
from tests.http_test_client import HttpTestResponse, LiveApiServer


REGISTERED_COMBINATIONS = (
    ("content", "tfidf"),
    ("collaborative", "popularity"),
    ("collaborative", "item_knn"),
    ("collaborative", "user_knn"),
    ("collaborative", "biased"),
)
PERSONALIZED_COLLABORATIVE_ALGORITHMS = (
    "item_knn",
    "user_knn",
    "biased",
)
RATING_VALUES = (5, 4, 2, 5, 1, 4, 2, 5, 1, 4, 2, 5)

SERVER: LiveApiServer
MOVIE_IDS: list[int]


def setUpModule() -> None:
    global SERVER, MOVIE_IDS
    MOVIE_IDS = [
        int(movie["movieId"])
        for movie in catalog_repository.get_featured_movies()[:12]
    ]
    SERVER = LiveApiServer()
    SERVER.start()


def tearDownModule() -> None:
    SERVER.stop()


class RealRecommenderHttpSmokeTests(unittest.TestCase):
    def test_every_registered_recommender_through_http(self) -> None:
        for strategy, algorithm in REGISTERED_COMBINATIONS:
            with self.subTest(strategy=strategy, algorithm=algorithm):
                rating_count = 3 if strategy == "content" else 12
                response = _post_canonical(
                    strategy=strategy,
                    algorithm=algorithm,
                    movie_ids=MOVIE_IDS[:rating_count],
                    request_id=f"smoke-{strategy}-{algorithm}",
                    limit=2,
                )
                self.assertEqual(200, response.status, response.body)
                self.assertTrue(
                    response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                )
                body = _body_dict(response)
                _assert_canonical_success(self, body)
                self.assertEqual(strategy, body["strategy"])
                self.assertEqual(algorithm, body["algorithm"])
                print(
                    "HTTP recommender smoke "
                    f"{strategy}/{algorithm}: "
                    f"{response.elapsed_seconds:.3f}s"
                )


class CanonicalRecommendationHttpTests(unittest.TestCase):
    def test_valid_provided_request_id_is_preserved_exactly(self) -> None:
        request_id = "  frontend-id with spaces  "
        response = _post_canonical(
            strategy="collaborative",
            algorithm="popularity",
            movie_ids=[],
            request_id=request_id,
        )
        self.assertEqual(200, response.status)
        self.assertEqual(request_id, _body_dict(response)["requestId"])

    def test_missing_request_id_is_generated(self) -> None:
        response = _post_canonical(
            strategy="collaborative",
            algorithm="popularity",
            movie_ids=[],
            request_id=None,
        )
        self.assertEqual(200, response.status)
        _assert_generated_request_id(self, _body_dict(response)["requestId"])

    def test_invalid_request_ids_generate_safe_error_ids(self) -> None:
        invalid_values = ("", "   \t", "x" * 129, 42)
        for invalid_value in invalid_values:
            with self.subTest(request_id=invalid_value):
                payload = _canonical_payload(
                    strategy="collaborative",
                    algorithm="popularity",
                    movie_ids=[],
                    request_id=invalid_value,
                )
                response = SERVER.request(
                    "POST",
                    "/recommendations",
                    json_body=payload,
                )
                self.assertEqual(422, response.status)
                self.assertTrue(
                    response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                )
                body = _body_dict(response)
                _assert_canonical_error(self, body)
                _assert_generated_request_id(self, body["requestId"])

    def test_valid_request_id_is_preserved_in_domain_error(self) -> None:
        response = _post_canonical(
            strategy="content",
            algorithm="tfidf",
            movie_ids=MOVIE_IDS[:2],
            request_id="domain-error-id",
        )
        self.assertEqual(400, response.status)
        body = _body_dict(response)
        self.assertEqual("domain-error-id", body["requestId"])
        self.assertEqual("insufficient_ratings", body["error"]["code"])

    def test_pydantic_errors_are_normalized(self) -> None:
        cases = (
            (
                "rating",
                {"ratings": [{"movieId": MOVIE_IDS[0], "rating": 6}]},
                "invalid_rating_value",
            ),
            (
                "fractional-rating",
                {"ratings": [{"movieId": MOVIE_IDS[0], "rating": 4.5}]},
                "invalid_rating_value",
            ),
            ("limit", {"limit": 0}, "invalid_limit"),
            ("extra", {"unexpected": True}, "invalid_request"),
        )
        for name, override, expected_code in cases:
            with self.subTest(case=name):
                payload = _canonical_payload(
                    strategy="collaborative",
                    algorithm="popularity",
                    movie_ids=[MOVIE_IDS[0]],
                    request_id=f"validation-{name}",
                )
                payload.update(override)
                response = SERVER.request(
                    "POST",
                    "/recommendations",
                    json_body=payload,
                )
                self.assertEqual(422, response.status)
                body = _body_dict(response)
                _assert_canonical_error(self, body)
                self.assertEqual(f"validation-{name}", body["requestId"])
                self.assertEqual(expected_code, body["error"]["code"])

    def test_dispatch_errors_are_distinct(self) -> None:
        cases = (
            ("hybrid", "tfidf", "unsupported_strategy"),
            ("content", "missing", "unsupported_algorithm"),
            (
                "content",
                "popularity",
                "unsupported_strategy_algorithm_combination",
            ),
        )
        for strategy, algorithm, expected_code in cases:
            with self.subTest(strategy=strategy, algorithm=algorithm):
                response = _post_canonical(
                    strategy=strategy,
                    algorithm=algorithm,
                    movie_ids=MOVIE_IDS[:3],
                    request_id=f"dispatch-{expected_code}",
                )
                self.assertEqual(400, response.status)
                body = _body_dict(response)
                _assert_canonical_error(self, body)
                self.assertEqual(expected_code, body["error"]["code"])

    def test_duplicate_and_unknown_movies_are_rejected(self) -> None:
        cases = (
            (
                [MOVIE_IDS[0], MOVIE_IDS[0]],
                "duplicate_movie_rating",
            ),
            ([999_999_999], "unknown_movie"),
        )
        for movie_ids, expected_code in cases:
            with self.subTest(code=expected_code):
                response = _post_canonical(
                    strategy="collaborative",
                    algorithm="popularity",
                    movie_ids=movie_ids,
                    request_id=f"movie-{expected_code}",
                )
                self.assertEqual(400, response.status)
                body = _body_dict(response)
                _assert_canonical_error(self, body)
                self.assertEqual(expected_code, body["error"]["code"])

    def test_content_preserves_real_non_neutral_minimum(self) -> None:
        response = _post_canonical(
            strategy="content",
            algorithm="tfidf",
            movie_ids=MOVIE_IDS[:2],
            request_id="content-minimum",
        )
        self.assertEqual(400, response.status)
        body = _body_dict(response)
        self.assertEqual("insufficient_ratings", body["error"]["code"])
        self.assertEqual(3, body["error"]["details"]["minimumRequired"])

    def test_popularity_accepts_empty_ratings(self) -> None:
        response = _post_canonical(
            strategy="collaborative",
            algorithm="popularity",
            movie_ids=[],
            request_id="empty-popularity",
        )
        self.assertEqual(200, response.status)
        _assert_canonical_success(self, _body_dict(response))

    def test_personalized_collaborative_algorithms_reject_empty_ratings(
        self,
    ) -> None:
        for algorithm in PERSONALIZED_COLLABORATIVE_ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                response = _post_canonical(
                    strategy="collaborative",
                    algorithm=algorithm,
                    movie_ids=[],
                    request_id=f"empty-{algorithm}",
                )
                self.assertEqual(400, response.status)
                body = _body_dict(response)
                _assert_canonical_error(self, body)
                self.assertEqual("insufficient_ratings", body["error"]["code"])

    def test_unrelated_validation_keeps_fastapi_default_shape(self) -> None:
        response = SERVER.request(
            "GET",
            f"/movies/public-catalog?{urlencode({'page': 0})}",
        )
        self.assertEqual(422, response.status)
        body = _body_dict(response)
        self.assertEqual({"detail"}, set(body))
        self.assertIsInstance(body["detail"], list)

    def test_health_and_catalogue_continue_working(self) -> None:
        health = SERVER.request("GET", "/health")
        self.assertEqual(200, health.status)
        self.assertEqual({"status": "ok"}, health.body)

        status = SERVER.request("GET", "/catalog/status")
        self.assertEqual(200, status.status)
        self.assertGreater(_body_dict(status)["totalMovies"], 0)


class DeprecatedRecommendationCompatibilityHttpTests(unittest.TestCase):
    def test_legacy_routes_are_deprecated_in_openapi(self) -> None:
        response = SERVER.request("GET", "/openapi.json")
        self.assertEqual(200, response.status)
        paths = _body_dict(response)["paths"]
        self.assertTrue(
            paths["/recommendations/content-based"]["post"]["deprecated"]
        )
        self.assertTrue(
            paths["/recommendations/collaborative"]["post"]["deprecated"]
        )

    def test_content_endpoint_accepts_decimal_and_returns_legacy_shape(
        self,
    ) -> None:
        template_session_id = "legacy-content-template"
        response = SERVER.request(
            "POST",
            "/recommendations/content-based",
            json_body={
                "ratings": [
                    {"movieId": MOVIE_IDS[0], "rating": 4.5},
                    {"movieId": MOVIE_IDS[1], "rating": 4},
                    {"movieId": MOVIE_IDS[2], "rating": 2},
                ],
                "limit": 2,
                "templateSessionId": template_session_id,
            },
        )
        self.assertEqual(200, response.status, response.body)
        body = _body_dict(response)
        self.assertEqual(
            {
                "strategy",
                "profile",
                "recommendations",
                "recommenderDetails",
                "templateSessionId",
                "limit",
            },
            set(body),
        )
        self.assertEqual("content_based", body["strategy"])
        self.assertEqual(template_session_id, body["templateSessionId"])
        self.assertGreater(len(body["recommendations"]), 0)
        self.assertEqual(
            {
                "movieId",
                "rank",
                "movie",
                "scores",
                "explanation",
                "algorithmDetails",
            },
            set(body["recommendations"][0]),
        )
        self.assertIn(
            "recommendationScore",
            body["recommendations"][0]["scores"],
        )
        self.assertIn(
            "matchedSignals",
            body["recommendations"][0]["explanation"],
        )

    def test_collaborative_endpoint_returns_configured_legacy_shape(self) -> None:
        template_session_id = "legacy-collaborative-template"
        response = SERVER.request(
            "POST",
            "/recommendations/collaborative",
            json_body={
                "ratings": _ratings_for(MOVIE_IDS[:12]),
                "limit": 2,
                "templateSessionId": template_session_id,
            },
        )
        self.assertEqual(200, response.status, response.body)
        body = _body_dict(response)
        self.assertEqual(
            {
                "strategy",
                "profile",
                "recommendations",
                "recommenderDetails",
                "templateSessionId",
                "limit",
            },
            set(body),
        )
        self.assertEqual("collaborative", body["strategy"])
        self.assertEqual(template_session_id, body["templateSessionId"])
        self.assertEqual(
            settings.active_collaborative_algorithm,
            body["recommenderDetails"]["algorithmId"],
        )
        self.assertGreater(len(body["recommendations"]), 0)
        self.assertEqual(
            {
                "movieId",
                "rank",
                "movie",
                "scores",
                "explanation",
                "algorithmDetails",
            },
            set(body["recommendations"][0]),
        )

    def test_legacy_validation_keeps_fastapi_default_shape(self) -> None:
        response = SERVER.request(
            "POST",
            "/recommendations/content-based",
            json_body={"ratings": [], "limit": 0},
        )
        self.assertEqual(422, response.status)
        self.assertEqual({"detail"}, set(_body_dict(response)))


def _post_canonical(
    *,
    strategy: str,
    algorithm: str,
    movie_ids: list[int],
    request_id: object | None,
    limit: int = 2,
) -> HttpTestResponse:
    return SERVER.request(
        "POST",
        "/recommendations",
        json_body=_canonical_payload(
            strategy=strategy,
            algorithm=algorithm,
            movie_ids=movie_ids,
            request_id=request_id,
            limit=limit,
        ),
    )


def _canonical_payload(
    *,
    strategy: str,
    algorithm: str,
    movie_ids: list[int],
    request_id: object | None,
    limit: int = 2,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "strategy": strategy,
        "algorithm": algorithm,
        "ratings": _ratings_for(movie_ids),
        "limit": limit,
    }
    if request_id is not None:
        payload["requestId"] = request_id
    return payload


def _ratings_for(movie_ids: list[int]) -> list[dict[str, int]]:
    return [
        {"movieId": movie_id, "rating": rating}
        for movie_id, rating in zip(
            movie_ids,
            RATING_VALUES[: len(movie_ids)],
            strict=True,
        )
    ]


def _body_dict(response: HttpTestResponse) -> dict:
    if not isinstance(response.body, dict):
        raise AssertionError(f"Expected JSON object, got {response.body!r}")
    return response.body


def _assert_generated_request_id(
    test_case: unittest.TestCase,
    request_id: object,
) -> None:
    test_case.assertIsInstance(request_id, str)
    test_case.assertTrue(request_id)
    test_case.assertTrue(str(request_id).startswith("rec-"))
    test_case.assertLessEqual(len(str(request_id)), 128)


def _assert_canonical_error(
    test_case: unittest.TestCase,
    body: dict,
) -> None:
    test_case.assertEqual({"requestId", "error"}, set(body))
    test_case.assertEqual(
        {"code", "message", "details"},
        set(body["error"]),
    )
    test_case.assertIsInstance(body["error"]["details"], dict)


def _assert_canonical_success(
    test_case: unittest.TestCase,
    body: dict,
) -> None:
    test_case.assertEqual(
        {
            "requestId",
            "strategy",
            "algorithm",
            "recommendations",
            "meta",
        },
        set(body),
    )
    test_case.assertEqual(
        len(body["recommendations"]),
        body["meta"]["count"],
    )
    test_case.assertEqual(
        list(range(1, len(body["recommendations"]) + 1)),
        [item["rank"] for item in body["recommendations"]],
    )
    for item in body["recommendations"]:
        test_case.assertEqual(
            {
                "rank",
                "movie",
                "score",
                "matchPercentage",
                "explanation",
            },
            set(item),
        )
        test_case.assertGreaterEqual(item["matchPercentage"], 0)
        test_case.assertLessEqual(item["matchPercentage"], 100)
        test_case.assertEqual(
            {"summary", "reasons"},
            set(item["explanation"]),
        )
