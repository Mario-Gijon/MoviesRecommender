import argparse
import csv
import json
import math
import random
import shutil
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi.testclient import TestClient

from app.catalog.catalog_repository import catalog_repository
from app.core.config import settings
from app.main import app
from app.project_paths.dataset_paths import (
    COLLABORATIVE_RECOMMENDER_MODELS_DIR,
    OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
    RECOMMENDER_AUDIT_DIR,
)
from app.recommenders.collaborative import registry as collaborative_registry
from app.recommenders.collaborative.algorithms.item_knn_cosine.recommender import (
    ItemKnnCosineRecommender,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import (
    ALGORITHM_ID as BIASED_MATRIX_FACTORIZATION_ALGORITHM_ID,
    ALGORITHM_LABEL as BIASED_MATRIX_FACTORIZATION_ALGORITHM_LABEL,
    BiasedMatrixFactorizationRuntimeConfig,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.recommender import (
    BiasedMatrixFactorizationRecommender,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.recommender import (
    PopularityBaselineRecommender,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.storage import (
    get_popularity_baseline_artifacts,
    load_popularity_baseline_manifest,
)
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.models import (
    ALGORITHM_ID as USER_KNN_ALGORITHM_ID,
)
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.recommender import (
    UserKnnPearsonShrinkageRecommender,
)
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.storage import (
    get_user_knn_pearson_shrinkage_artifacts,
    load_user_knn_pearson_shrinkage_manifest,
)
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationRequest,
    CollaborativeUserRating,
)


@dataclass(frozen=True)
class EvaluationHoldoutRating:
    movie_id: int
    rating: float


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    user_id: int
    ratings: list[CollaborativeUserRating]
    holdout_movie_ids: list[int]
    holdout_ratings: list[EvaluationHoldoutRating]

    def to_request(self, *, limit: int) -> CollaborativeRecommendationRequest:
        return CollaborativeRecommendationRequest(
            ratings=self.ratings,
            limit=limit,
            template_session_id=self.case_id,
        )

    def to_api_payload(self, *, limit: int) -> dict[str, Any]:
        return {
            "ratings": [
                {
                    "movieId": rating.movie_id,
                    "rating": rating.rating,
                }
                for rating in self.ratings
            ],
            "limit": limit,
            "templateSessionId": self.case_id,
        }


@dataclass(frozen=True)
class EvaluatedRecommender:
    algorithm_id: str
    algorithm_label: str
    variant_id: str
    recommender: object
    manifest: dict[str, Any]


def main() -> None:
    args = parse_args()
    started_at = datetime.now(timezone.utc)
    evaluation_id = started_at.strftime("%Y%m%d_%H%M%S")
    run_id = "current"

    output_dir = RECOMMENDER_AUDIT_DIR / "collaborative_comparison" / run_id
    prepare_output_dir(output_dir)

    public_catalog = catalog_repository.get_recommendation_candidates()
    public_movie_ids = {int(movie["movieId"]) for movie in public_catalog}
    public_movies_by_id = {int(movie["movieId"]): movie for movie in public_catalog}

    evaluation_cases = build_evaluation_cases(
        public_movie_ids=public_movie_ids,
        case_count=args.case_count,
        min_positive_input=args.min_positive_input,
        holdout_count=args.holdout_count,
        seed=args.seed,
    )
    recommenders = load_evaluated_recommenders(requested_variants=args.variant)

    rows: list[dict[str, Any]] = []
    api_client = TestClient(app)

    for evaluated in recommenders:
        print(f"Evaluating {evaluated.algorithm_id} / {evaluated.variant_id}")

        runtime_and_quality_metrics = benchmark_runtime_and_quality(
            evaluated=evaluated,
            cases=evaluation_cases,
            public_movie_ids=public_movie_ids,
            public_movies_by_id=public_movies_by_id,
            limit=args.limit,
            runtime_repeats=args.runtime_repeats,
        )

        api_metrics = (
            empty_api_metrics()
            if args.skip_api
            else benchmark_api(
                evaluated=evaluated,
                client=api_client,
                cases=evaluation_cases,
                limit=args.limit,
                api_repeats=args.api_repeats,
            )
        )

        rows.append(
            {
                "algorithmId": evaluated.algorithm_id,
                "algorithmLabel": evaluated.algorithm_label,
                "variantId": evaluated.variant_id,
                **offline_metrics(evaluated),
                **runtime_and_quality_metrics,
                **api_metrics,
            }
        )

    rows = sort_rows(rows)
    generated_files = [
        "evaluation_cases.json",
        "variant_metrics.csv",
        "variant_metrics.json",
        "comparison_summary.json",
        "report.md",
        "index.html",
    ]
    summary = {
        "runId": run_id,
        "evaluationId": evaluation_id,
        "startedAt": started_at.isoformat(),
        "caseCount": len(evaluation_cases),
        "limit": args.limit,
        "runtimeRepeats": args.runtime_repeats,
        "apiRepeats": args.api_repeats,
        "skipApi": args.skip_api,
        "evaluatedVariants": [
            {
                "algorithmId": row["algorithmId"],
                "algorithmLabel": row["algorithmLabel"],
                "variantId": row["variantId"],
                "ratingPredictionSupported": row["ratingPredictionSupported"],
            }
            for row in rows
        ],
        "generatedFiles": generated_files,
    }

    write_json(output_dir / "evaluation_cases.json", serialize_evaluation_cases(evaluation_cases))
    write_json(output_dir / "variant_metrics.json", rows)
    write_json(output_dir / "comparison_summary.json", summary)
    write_csv(output_dir / "variant_metrics.csv", rows)
    write_markdown_report(
        path=output_dir / "report.md",
        summary=summary,
        rows=rows,
    )
    write_html_report(
        path=output_dir / "index.html",
        summary=summary,
        rows=rows,
    )

    print()
    print(f"Evaluation completed: {output_dir}")
    print("Evaluated variants:")
    for row in rows:
        print(row["algorithmId"], row["variantId"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-count", type=int, default=100)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--runtime-repeats", type=int, default=3)
    parser.add_argument("--api-repeats", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-positive-input", type=int, default=3)
    parser.add_argument("--holdout-count", type=int, default=1)
    parser.add_argument("--variant", action="append", default=None)
    parser.add_argument("--skip-api", action="store_true")
    return parser.parse_args()


def build_evaluation_cases(
    *,
    public_movie_ids: set[int],
    case_count: int,
    min_positive_input: int,
    holdout_count: int,
    seed: int,
) -> list[EvaluationCase]:
    if case_count <= 0:
        raise RuntimeError("--case-count must be greater than 0.")

    ratings = load_public_ratings(public_movie_ids)
    grouped = ratings.groupby("userId", sort=False)
    user_ids = [int(user_id) for user_id in grouped.groups.keys()]

    rng = random.Random(seed)
    rng.shuffle(user_ids)

    cases: list[EvaluationCase] = []
    for user_id in user_ids:
        user_ratings = grouped.get_group(user_id)
        positives = user_ratings[user_ratings["rating"] >= 4.0].to_dict("records")
        negatives = user_ratings[user_ratings["rating"] <= 2.0].to_dict("records")

        if len(positives) < min_positive_input + holdout_count:
            continue

        rng.shuffle(positives)
        rng.shuffle(negatives)

        holdout_rows = positives[:holdout_count]
        input_positive_rows = positives[holdout_count : holdout_count + min_positive_input]
        input_rows = list(input_positive_rows)
        if negatives:
            input_rows.append(negatives[0])

        ratings_input = [
            CollaborativeUserRating(
                movie_id=int(row["movieId"]),
                rating=to_app_rating(float(row["rating"])),
            )
            for row in input_rows
        ]
        holdout_ratings = [
            EvaluationHoldoutRating(
                movie_id=int(row["movieId"]),
                rating=float(row["rating"]),
            )
            for row in holdout_rows
        ]

        cases.append(
            EvaluationCase(
                case_id=f"eval-user-{user_id}-{len(cases) + 1}",
                user_id=user_id,
                ratings=ratings_input,
                holdout_movie_ids=[item.movie_id for item in holdout_ratings],
                holdout_ratings=holdout_ratings,
            )
        )
        if len(cases) >= case_count:
            break

    if len(cases) < case_count:
        raise RuntimeError(
            f"Only {len(cases)} evaluation cases could be built. Requested {case_count}."
        )
    return cases


def prepare_output_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=False)


def load_public_ratings(public_movie_ids: set[int]) -> pd.DataFrame:
    chunks = []
    for chunk in pd.read_csv(
        OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
        usecols=["userId", "movieId", "rating"],
        dtype={"userId": "int32", "movieId": "int32", "rating": "float32"},
        chunksize=1_000_000,
    ):
        filtered = chunk[chunk["movieId"].isin(public_movie_ids)]
        if not filtered.empty:
            chunks.append(filtered)

    if not chunks:
        raise RuntimeError("No public movie ratings found for evaluation.")

    ratings = pd.concat(chunks, ignore_index=True)
    return ratings.drop_duplicates(subset=["userId", "movieId"], keep="last")


def to_app_rating(rating: float) -> int:
    if rating >= 4.5:
        return 5
    if rating >= 3.5:
        return 4
    if rating >= 2.5:
        return 3
    if rating >= 1.5:
        return 2
    return 1


def load_evaluated_recommenders(
    *,
    requested_variants: list[str] | None,
) -> list[EvaluatedRecommender]:
    recommenders = [
        EvaluatedRecommender(
            algorithm_id=PopularityBaselineRecommender.algorithm_id,
            algorithm_label=PopularityBaselineRecommender.algorithm_label,
            variant_id="default",
            recommender=PopularityBaselineRecommender(),
            manifest=load_popularity_baseline_manifest(),
        )
    ]

    item_knn_dir = COLLABORATIVE_RECOMMENDER_MODELS_DIR / "item_knn_cosine"
    if item_knn_dir.exists():
        for variant_dir in sorted(item_knn_dir.iterdir()):
            if not variant_dir.is_dir():
                continue
            variant_id = variant_dir.name
            if requested_variants and variant_id not in requested_variants:
                continue

            manifest_path = variant_dir / "model_manifest.json"
            sqlite_path = variant_dir / "neighbors.sqlite"
            if not manifest_path.exists() or not sqlite_path.exists():
                continue

            recommenders.append(
                EvaluatedRecommender(
                    algorithm_id="item_knn_cosine",
                    algorithm_label="ItemKNN Cosine",
                    variant_id=variant_id,
                    recommender=ItemKnnCosineRecommender(model_variant_id=variant_id),
                    manifest=json.loads(manifest_path.read_text(encoding="utf-8")),
                )
            )

    user_knn_artifacts = get_user_knn_pearson_shrinkage_artifacts()
    if (
        user_knn_artifacts.manifest_path.exists()
        and user_knn_artifacts.ratings_sqlite_path.exists()
        and (not requested_variants or user_knn_artifacts.variant_dir.name in requested_variants)
    ):
        recommenders.append(
            EvaluatedRecommender(
                algorithm_id=USER_KNN_ALGORITHM_ID,
                algorithm_label="UserKNN Pearson Shrinkage",
                variant_id=user_knn_artifacts.variant_dir.name,
                recommender=UserKnnPearsonShrinkageRecommender(),
                manifest=load_user_knn_pearson_shrinkage_manifest(),
            )
        )

    biased_mf_dir = (
        COLLABORATIVE_RECOMMENDER_MODELS_DIR
        / BIASED_MATRIX_FACTORIZATION_ALGORITHM_ID
    )
    if biased_mf_dir.exists():
        for variant_dir in sorted(biased_mf_dir.iterdir()):
            if not variant_dir.is_dir():
                continue

            variant_id = variant_dir.name
            if requested_variants and variant_id not in requested_variants:
                continue

            manifest_path = variant_dir / "model_manifest.json"
            if not manifest_path.exists():
                continue

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not (
                manifest.get("status") == "trained"
                and manifest.get("runtimeStatus") == "ready"
            ):
                print(
                    "Skipping biased_matrix_factorization variant",
                    variant_id,
                    "because it is not runtime-ready:",
                    "status=",
                    manifest.get("status"),
                    "runtimeStatus=",
                    manifest.get("runtimeStatus"),
                )
                continue

            recommenders.append(
                EvaluatedRecommender(
                    algorithm_id=BIASED_MATRIX_FACTORIZATION_ALGORITHM_ID,
                    algorithm_label=BIASED_MATRIX_FACTORIZATION_ALGORITHM_LABEL,
                    variant_id=variant_id,
                    recommender=BiasedMatrixFactorizationRecommender(
                        runtime_config=BiasedMatrixFactorizationRuntimeConfig(
                            variant_id=variant_id
                        )
                    ),
                    manifest=manifest,
                )
            )

    return recommenders


def offline_metrics(evaluated: EvaluatedRecommender) -> dict[str, Any]:
    counts = evaluated.manifest.get("counts", {})
    parameters = evaluated.manifest.get("parameters", {})

    if evaluated.algorithm_id == "popularity_baseline":
        artifacts = get_popularity_baseline_artifacts()
        ranking_csv_size_mb = file_size_mb(artifacts.ranking_csv_path)
        ranking_sqlite_size_mb = file_size_mb(artifacts.ranking_sqlite_path)
        return {
            "buildTimeSeconds": counts.get("buildTimeSeconds"),
            "modelArtifactSizeMb": ranking_sqlite_size_mb,
            "ratings": None,
            "users": None,
            "publicMovies": counts.get("publicCandidates"),
            "supportMovies": None,
            "modelMovies": counts.get("rankedMovies"),
            "neighborRows": None,
            "rankingRows": counts.get("rankedMovies"),
            "topK": None,
            "minSupport": None,
            "neighborsCsvSizeMb": None,
            "neighborsSqliteSizeMb": None,
            "rankingCsvSizeMb": ranking_csv_size_mb,
            "rankingSqliteSizeMb": ranking_sqlite_size_mb,
            "ratingsSqliteSizeMb": None,
            "userStatsCsvSizeMb": None,
            "topNeighbors": None,
            "minOverlap": None,
            "shrinkage": None,
            "minCandidateNeighborCount": None,
            "candidateShrinkage": None,
            "minPredictionScore": None,
        }

    if evaluated.algorithm_id == USER_KNN_ALGORITHM_ID:
        return {
            "buildTimeSeconds": counts.get("buildTimeSeconds"),
            "modelArtifactSizeMb": counts.get("ratingsSqliteSizeMb"),
            "ratings": counts.get("ratings"),
            "users": counts.get("users"),
            "publicMovies": counts.get("publicMovies"),
            "supportMovies": counts.get("publicMoviesWithRatings"),
            "modelMovies": counts.get("movies"),
            "neighborRows": None,
            "rankingRows": None,
            "topK": None,
            "minSupport": None,
            "neighborsCsvSizeMb": None,
            "neighborsSqliteSizeMb": None,
            "rankingCsvSizeMb": None,
            "rankingSqliteSizeMb": None,
            "ratingsSqliteSizeMb": counts.get("ratingsSqliteSizeMb"),
            "userStatsCsvSizeMb": counts.get("userStatsCsvSizeMb"),
            "topNeighbors": getattr(evaluated.recommender, "_runtime_config").top_neighbors,
            "minOverlap": getattr(evaluated.recommender, "_runtime_config").min_overlap,
            "shrinkage": getattr(evaluated.recommender, "_runtime_config").shrinkage,
            "minCandidateNeighborCount": getattr(evaluated.recommender, "_runtime_config").min_candidate_neighbor_count,
            "candidateShrinkage": getattr(evaluated.recommender, "_runtime_config").candidate_shrinkage,
            "minPredictionScore": getattr(evaluated.recommender, "_runtime_config").min_prediction_score,
        }

    if evaluated.algorithm_id == BIASED_MATRIX_FACTORIZATION_ALGORITHM_ID:
        config = evaluated.manifest.get("config", {})
        counts = evaluated.manifest.get("counts", {})
        variant_dir = COLLABORATIVE_RECOMMENDER_MODELS_DIR / evaluated.algorithm_id / evaluated.variant_id
        return {
            "buildTimeSeconds": counts.get("buildTimeSeconds"),
            "modelArtifactSizeMb": None,
            "ratings": counts.get("ratings"),
            "users": counts.get("users"),
            "publicMovies": counts.get("publicMovies"),
            "supportMovies": counts.get("supportMovies"),
            "modelMovies": counts.get("modelMovies"),
            "neighborRows": None,
            "rankingRows": None,
            "topK": None,
            "minSupport": None,
            "neighborsCsvSizeMb": None,
            "neighborsSqliteSizeMb": None,
            "rankingCsvSizeMb": None,
            "rankingSqliteSizeMb": None,
            "ratingsSqliteSizeMb": None,
            "userStatsCsvSizeMb": None,
            "topNeighbors": None,
            "minOverlap": None,
            "shrinkage": None,
            "minCandidateNeighborCount": None,
            "candidateShrinkage": None,
            "minPredictionScore": config.get("minPredictionScore"),
        }

    variant_dir = COLLABORATIVE_RECOMMENDER_MODELS_DIR / evaluated.algorithm_id / evaluated.variant_id
    neighbors_csv_size_mb = file_size_mb(variant_dir / "neighbors.csv")
    neighbors_sqlite_size_mb = file_size_mb(variant_dir / "neighbors.sqlite")
    return {
        "buildTimeSeconds": counts.get("buildTimeSeconds"),
        "modelArtifactSizeMb": neighbors_sqlite_size_mb,
        "ratings": counts.get("ratings"),
        "users": counts.get("users"),
        "publicMovies": counts.get("publicMovies"),
        "supportMovies": counts.get("supportMovies"),
        "modelMovies": counts.get("modelMovies"),
        "neighborRows": counts.get("generatedNeighborRows"),
        "rankingRows": None,
        "topK": parameters.get("topK"),
        "minSupport": parameters.get("minSupport"),
        "neighborsCsvSizeMb": neighbors_csv_size_mb,
        "neighborsSqliteSizeMb": neighbors_sqlite_size_mb,
        "rankingCsvSizeMb": None,
        "rankingSqliteSizeMb": None,
        "ratingsSqliteSizeMb": None,
        "userStatsCsvSizeMb": None,
        "topNeighbors": None,
        "minOverlap": None,
        "shrinkage": None,
        "minCandidateNeighborCount": None,
        "candidateShrinkage": None,
        "minPredictionScore": None,
    }


def benchmark_runtime_and_quality(
    *,
    evaluated: EvaluatedRecommender,
    cases: list[EvaluationCase],
    public_movie_ids: set[int],
    public_movies_by_id: dict[int, dict[str, Any]],
    limit: int,
    runtime_repeats: int,
) -> dict[str, Any]:
    timings_ms: list[float] = []
    personalized_runtime_ms: list[float] = []
    fallback_runtime_ms: list[float] = []
    total_runtime_details_ms: list[float] = []
    recommendations_returned: list[int] = []
    fallback_used_values: list[int] = []
    fallback_recommendations_added: list[int] = []

    quality_accumulator = QualityAccumulator(
        public_movie_count=len(public_movie_ids),
        limit=limit,
        public_movies_by_id=public_movies_by_id,
    )

    for repeat_index in range(runtime_repeats):
        for case in cases:
            request = case.to_request(limit=limit)
            started_at = time.perf_counter()
            result = evaluated.recommender.recommend(request)
            elapsed_ms = (time.perf_counter() - started_at) * 1000

            details = result.recommender_details.details
            timings_ms.append(elapsed_ms)
            personalized_runtime_ms.append(float(details.get("personalizedRuntimeMs", elapsed_ms)))
            fallback_runtime_ms.append(float(details.get("fallbackRuntimeMs", 0.0)))
            total_runtime_details_ms.append(float(details.get("totalRuntimeMs", elapsed_ms)))

            if repeat_index > 0:
                continue

            recommended_ids = [item.movie_id for item in result.recommendations]
            quality_accumulator.add_case(
                case=case,
                recommended_movie_ids=recommended_ids,
                public_movie_ids=public_movie_ids,
            )
            if hasattr(evaluated.recommender, "predict_rating_for_movie"):
                for holdout in case.holdout_ratings:
                    prediction = evaluated.recommender.predict_rating_for_movie(
                        request=request,
                        movie_id=holdout.movie_id,
                    )
                    quality_accumulator.add_rating_prediction(
                        actual_rating=holdout.rating,
                        prediction_runtime_ms=prediction.prediction_runtime_ms,
                        predicted_rating_raw=(
                            prediction.predicted_rating_raw
                            if prediction.prediction_available
                            else None
                        ),
                        predicted_rating_regularized=(
                            prediction.predicted_rating_regularized
                            if prediction.prediction_available
                            else None
                        ),
                    )

            recommendations_returned.append(len(result.recommendations))
            fallback_recommendations_added.append(int(details.get("fallbackRecommendationsAdded", 0)))
            fallback_used_values.append(1 if bool(details.get("fallbackUsed", False)) else 0)

    fallback_used_cases = sum(fallback_used_values)
    cases_below_limit = sum(1 for value in recommendations_returned if value < limit)
    zero_recommendation_cases = sum(1 for value in recommendations_returned if value == 0)

    return {
        "runtimeRuns": len(timings_ms),
        "avgRuntimeMs": round_float(mean(timings_ms)),
        "p50RuntimeMs": round_float(percentile(timings_ms, 50)),
        "p95RuntimeMs": round_float(percentile(timings_ms, 95)),
        "p99RuntimeMs": round_float(percentile(timings_ms, 99)),
        "maxRuntimeMs": round_float(max(timings_ms)),
        "avgPersonalizedRuntimeMs": round_float(mean(personalized_runtime_ms)),
        "avgFallbackRuntimeMs": round_float(mean(fallback_runtime_ms)),
        "avgTotalRuntimeMs": round_float(mean(total_runtime_details_ms)),
        "fallbackUsedCases": fallback_used_cases,
        "fallbackUsedPct": pct(fallback_used_cases, len(fallback_used_values)),
        "avgFallbackRecommendationsAdded": round_float(mean(fallback_recommendations_added)),
        "minRecommendationsReturned": min(recommendations_returned) if recommendations_returned else 0,
        "zeroRecommendationCases": zero_recommendation_cases,
        "casesBelowLimit": cases_below_limit,
        "casesBelowLimitPct": pct(cases_below_limit, len(recommendations_returned)),
        **quality_accumulator.metrics(evaluated=evaluated),
    }


def benchmark_api(
    *,
    evaluated: EvaluatedRecommender,
    client: TestClient,
    cases: list[EvaluationCase],
    limit: int,
    api_repeats: int,
) -> dict[str, Any]:
    set_active_recommender_for_api(evaluated)

    timings_ms: list[float] = []
    response_sizes_kb: list[float] = []
    status_code_errors = 0

    for _ in range(api_repeats):
        for case in cases:
            started_at = time.perf_counter()
            response = client.post(
                "/recommendations/collaborative",
                json=case.to_api_payload(limit=limit),
            )
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            timings_ms.append(elapsed_ms)
            response_sizes_kb.append(len(response.content) / 1024)
            if response.status_code >= 400:
                status_code_errors += 1

    return {
        "apiRuns": len(timings_ms),
        "avgApiMs": round_float(mean(timings_ms)),
        "p50ApiMs": round_float(percentile(timings_ms, 50)),
        "p95ApiMs": round_float(percentile(timings_ms, 95)),
        "p99ApiMs": round_float(percentile(timings_ms, 99)),
        "maxApiMs": round_float(max(timings_ms)),
        "avgResponseSizeKb": round_float(mean(response_sizes_kb)),
        "statusCodeErrorCount": status_code_errors,
    }


def empty_api_metrics() -> dict[str, Any]:
    return {
        "apiRuns": 0,
        "avgApiMs": None,
        "p50ApiMs": None,
        "p95ApiMs": None,
        "p99ApiMs": None,
        "maxApiMs": None,
        "avgResponseSizeKb": None,
        "statusCodeErrorCount": None,
    }


def set_active_recommender_for_api(evaluated: EvaluatedRecommender) -> None:
    settings.active_collaborative_algorithm = evaluated.algorithm_id
    collaborative_registry.COLLABORATIVE_RECOMMENDER_REGISTRY[evaluated.algorithm_id] = (
        evaluated.recommender
    )


class QualityAccumulator:
    def __init__(
        self,
        *,
        public_movie_count: int,
        limit: int,
        public_movies_by_id: dict[int, dict[str, Any]],
    ) -> None:
        self.public_movie_count = public_movie_count
        self.limit = limit
        self.public_movies_by_id = public_movies_by_id
        self.case_count = 0
        self.hit_at_5_values: list[float] = []
        self.hit_at_10_values: list[float] = []
        self.recall_at_5_values: list[float] = []
        self.recall_at_10_values: list[float] = []
        self.precision_at_5_values: list[float] = []
        self.precision_at_10_values: list[float] = []
        self.ndcg_at_5_values: list[float] = []
        self.ndcg_at_10_values: list[float] = []
        self.mrr_at_10_values: list[float] = []
        self.map_at_10_values: list[float] = []
        self.unique_recommended_movie_ids: set[int] = set()
        self.recommended_movie_ids_all: list[int] = []
        self.non_public_recommendation_count = 0
        self.already_rated_recommendation_count = 0
        self.total_recommendation_count = 0
        self.rating_prediction_attempts = 0
        self.rating_prediction_available_count = 0
        self.rating_prediction_runtimes_ms: list[float] = []
        self.raw_prediction_errors: list[float] = []
        self.regularized_prediction_errors: list[float] = []
        self.raw_prediction_biases: list[float] = []
        self.regularized_prediction_biases: list[float] = []

    def add_case(
        self,
        *,
        case: EvaluationCase,
        recommended_movie_ids: list[int],
        public_movie_ids: set[int],
    ) -> None:
        self.case_count += 1
        self.unique_recommended_movie_ids.update(recommended_movie_ids)
        self.recommended_movie_ids_all.extend(recommended_movie_ids)

        holdout_ids = set(case.holdout_movie_ids)
        input_movie_ids = {rating.movie_id for rating in case.ratings}
        self.total_recommendation_count += len(recommended_movie_ids)
        self.non_public_recommendation_count += sum(
            1 for movie_id in recommended_movie_ids if movie_id not in public_movie_ids
        )
        self.already_rated_recommendation_count += sum(
            1 for movie_id in recommended_movie_ids if movie_id in input_movie_ids
        )

        self.hit_at_5_values.append(hit_rate_at_k(recommended_movie_ids, holdout_ids, 5))
        self.hit_at_10_values.append(hit_rate_at_k(recommended_movie_ids, holdout_ids, 10))
        self.recall_at_5_values.append(recall_at_k(recommended_movie_ids, holdout_ids, 5))
        self.recall_at_10_values.append(recall_at_k(recommended_movie_ids, holdout_ids, 10))
        self.precision_at_5_values.append(precision_at_k(recommended_movie_ids, holdout_ids, 5))
        self.precision_at_10_values.append(precision_at_k(recommended_movie_ids, holdout_ids, 10))
        self.ndcg_at_5_values.append(ndcg_at_k(recommended_movie_ids, holdout_ids, 5))
        self.ndcg_at_10_values.append(ndcg_at_k(recommended_movie_ids, holdout_ids, 10))
        self.mrr_at_10_values.append(mrr_at_k(recommended_movie_ids, holdout_ids, 10))
        self.map_at_10_values.append(map_at_k(recommended_movie_ids, holdout_ids, 10))

    def add_rating_prediction(
        self,
        *,
        actual_rating: float,
        prediction_runtime_ms: float,
        predicted_rating_raw: float | None,
        predicted_rating_regularized: float | None,
    ) -> None:
        self.rating_prediction_attempts += 1
        self.rating_prediction_runtimes_ms.append(prediction_runtime_ms)

        if predicted_rating_raw is not None:
            self.rating_prediction_available_count += 1
            raw_error = abs(predicted_rating_raw - actual_rating)
            self.raw_prediction_errors.append(raw_error)
            self.raw_prediction_biases.append(predicted_rating_raw - actual_rating)
        elif predicted_rating_regularized is not None:
            self.rating_prediction_available_count += 1

        if predicted_rating_regularized is not None:
            regularized_error = abs(predicted_rating_regularized - actual_rating)
            self.regularized_prediction_errors.append(regularized_error)
            self.regularized_prediction_biases.append(
                predicted_rating_regularized - actual_rating
            )

    def metrics(self, *, evaluated: EvaluatedRecommender) -> dict[str, Any]:
        coverage_pct = pct(len(self.unique_recommended_movie_ids), self.public_movie_count)
        catalog_stats = summarize_catalog_fields(
            recommended_movie_ids=self.recommended_movie_ids_all,
            public_movies_by_id=self.public_movies_by_id,
        )
        rating_prediction_metrics = build_rating_prediction_metrics(
            evaluated=evaluated,
            accumulator=self,
        )

        return {
            "evaluationCases": self.case_count,
            "hitRateAt5": round_float(mean(self.hit_at_5_values)),
            "hitRateAt10": round_float(mean(self.hit_at_10_values)),
            "recallAt5": round_float(mean(self.recall_at_5_values)),
            "recallAt10": round_float(mean(self.recall_at_10_values)),
            "precisionAt5": round_float(mean(self.precision_at_5_values)),
            "precisionAt10": round_float(mean(self.precision_at_10_values)),
            "ndcgAt5": round_float(mean(self.ndcg_at_5_values)),
            "ndcgAt10": round_float(mean(self.ndcg_at_10_values)),
            "mrrAt10": round_float(mean(self.mrr_at_10_values)),
            "mapAt10": round_float(mean(self.map_at_10_values)),
            "catalogCoveragePct": coverage_pct,
            "uniqueRecommendedMovies": len(self.unique_recommended_movie_ids),
            "nonPublicRecommendationCount": self.non_public_recommendation_count,
            "nonPublicRecommendationPct": pct(
                self.non_public_recommendation_count,
                self.total_recommendation_count,
            ),
            "alreadyRatedRecommendationCount": self.already_rated_recommendation_count,
            "alreadyRatedRecommendationPct": pct(
                self.already_rated_recommendation_count,
                self.total_recommendation_count,
            ),
            **catalog_stats,
            **rating_prediction_metrics,
        }


def build_rating_prediction_metrics(
    *,
    evaluated: EvaluatedRecommender,
    accumulator: QualityAccumulator,
) -> dict[str, Any]:
    supported = hasattr(evaluated.recommender, "predict_rating_for_movie")
    if not supported:
        return {
            "ratingPredictionSupported": False,
            "predictionCoveragePct": None,
            "ratingPredictionRuns": None,
            "avgRatingPredictionMs": None,
            "maeRaw": None,
            "rmseRaw": None,
            "maeRegularized": None,
            "rmseRegularized": None,
            "avgPredictionBiasRaw": None,
            "avgPredictionBiasRegularized": None,
            "p95AbsoluteErrorRaw": None,
            "p95AbsoluteErrorRegularized": None,
        }

    raw_rmse = rmse(accumulator.raw_prediction_errors)
    regularized_rmse = rmse(accumulator.regularized_prediction_errors)
    return {
        "ratingPredictionSupported": True,
        "predictionCoveragePct": pct(
            accumulator.rating_prediction_available_count,
            accumulator.rating_prediction_attempts,
        ),
        "ratingPredictionRuns": accumulator.rating_prediction_attempts,
        "avgRatingPredictionMs": round_float(mean(accumulator.rating_prediction_runtimes_ms)),
        "maeRaw": round_float(mean(accumulator.raw_prediction_errors)) if accumulator.raw_prediction_errors else None,
        "rmseRaw": round_float(raw_rmse) if raw_rmse is not None else None,
        "maeRegularized": round_float(mean(accumulator.regularized_prediction_errors)) if accumulator.regularized_prediction_errors else None,
        "rmseRegularized": round_float(regularized_rmse) if regularized_rmse is not None else None,
        "avgPredictionBiasRaw": round_float(mean(accumulator.raw_prediction_biases)) if accumulator.raw_prediction_biases else None,
        "avgPredictionBiasRegularized": round_float(mean(accumulator.regularized_prediction_biases)) if accumulator.regularized_prediction_biases else None,
        "p95AbsoluteErrorRaw": round_float(percentile(accumulator.raw_prediction_errors, 95)) if accumulator.raw_prediction_errors else None,
        "p95AbsoluteErrorRegularized": round_float(percentile(accumulator.regularized_prediction_errors, 95)) if accumulator.regularized_prediction_errors else None,
    }


def summarize_catalog_fields(
    *,
    recommended_movie_ids: list[int],
    public_movies_by_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    if not recommended_movie_ids:
        return {
            "avgRecommendedRatingCount": None,
            "medianRecommendedRatingCount": None,
            "avgRecommendedTmdbPopularity": None,
            "medianRecommendedTmdbPopularity": None,
        }

    rating_counts: list[float] = []
    tmdb_popularities: list[float] = []
    rating_count_available = True
    tmdb_popularity_available = True

    for movie_id in recommended_movie_ids:
        movie = public_movies_by_id.get(movie_id)
        if movie is None:
            continue
        rating_count = movie.get("ratingCount")
        tmdb_popularity = movie.get("tmdbPopularity")
        if rating_count is not None:
            rating_counts.append(float(rating_count))
        else:
            rating_count_available = False
        if tmdb_popularity is not None:
            tmdb_popularities.append(float(tmdb_popularity))
        else:
            tmdb_popularity_available = False

    return {
        "avgRecommendedRatingCount": (
            round_float(mean(rating_counts))
            if rating_counts and rating_count_available
            else None
        ),
        "medianRecommendedRatingCount": (
            round_float(median(rating_counts))
            if rating_counts and rating_count_available
            else None
        ),
        "avgRecommendedTmdbPopularity": (
            round_float(mean(tmdb_popularities))
            if tmdb_popularities and tmdb_popularity_available
            else None
        ),
        "medianRecommendedTmdbPopularity": (
            round_float(median(tmdb_popularities))
            if tmdb_popularities and tmdb_popularity_available
            else None
        ),
    }


def hit_rate_at_k(recommended_movie_ids: list[int], holdout_movie_ids: set[int], k: int) -> float:
    return 1.0 if set(recommended_movie_ids[:k]) & holdout_movie_ids else 0.0


def recall_at_k(recommended_movie_ids: list[int], holdout_movie_ids: set[int], k: int) -> float:
    if not holdout_movie_ids:
        return 0.0
    return len(set(recommended_movie_ids[:k]) & holdout_movie_ids) / len(holdout_movie_ids)


def precision_at_k(recommended_movie_ids: list[int], holdout_movie_ids: set[int], k: int) -> float:
    if k <= 0:
        return 0.0
    return len(set(recommended_movie_ids[:k]) & holdout_movie_ids) / k


def ndcg_at_k(recommended_movie_ids: list[int], holdout_movie_ids: set[int], k: int) -> float:
    dcg = 0.0
    for rank, movie_id in enumerate(recommended_movie_ids[:k], start=1):
        if movie_id in holdout_movie_ids:
            dcg += 1 / math.log2(rank + 1)
    ideal_hits = min(len(holdout_movie_ids), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def mrr_at_k(recommended_movie_ids: list[int], holdout_movie_ids: set[int], k: int) -> float:
    for rank, movie_id in enumerate(recommended_movie_ids[:k], start=1):
        if movie_id in holdout_movie_ids:
            return 1 / rank
    return 0.0


def map_at_k(recommended_movie_ids: list[int], holdout_movie_ids: set[int], k: int) -> float:
    if not holdout_movie_ids:
        return 0.0
    hit_count = 0
    precision_sum = 0.0
    for rank, movie_id in enumerate(recommended_movie_ids[:k], start=1):
        if movie_id not in holdout_movie_ids:
            continue
        hit_count += 1
        precision_sum += hit_count / rank
    return precision_sum / min(len(holdout_movie_ids), k)


def rmse(errors: list[float]) -> float | None:
    if not errors:
        return None
    return math.sqrt(sum(error * error for error in errors) / len(errors))


def file_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    return round(path.stat().st_size / 1024 / 1024, 3)


def mean(values: list[float] | list[int]) -> float:
    if not values:
        return 0.0
    return float(statistics.mean(values))


def median(values: list[float] | list[int]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def percentile(values: list[float], percentile_value: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = math.ceil(percentile_value / 100 * len(ordered)) - 1
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def pct(numerator: int | float, denominator: int | float) -> float | None:
    if not denominator:
        return None
    return round_float(numerator / denominator * 100)


def round_float(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: ("null" if row.get(key) is None else row.get(key))
                    for key in fieldnames
                }
            )


SECTION_COLUMNS = {
    "Evaluated variants": [
        "algorithmId",
        "algorithmLabel",
        "variantId",
        "ratingPredictionSupported",
    ],
    "Ranking quality": [
        "algorithmId",
        "variantId",
        "evaluationCases",
        "hitRateAt5",
        "hitRateAt10",
        "precisionAt5",
        "precisionAt10",
        "recallAt5",
        "recallAt10",
        "ndcgAt5",
        "ndcgAt10",
        "mrrAt10",
        "mapAt10",
    ],
    "Rating prediction": [
        "algorithmId",
        "variantId",
        "ratingPredictionSupported",
        "predictionCoveragePct",
        "ratingPredictionRuns",
        "avgRatingPredictionMs",
        "maeRaw",
        "rmseRaw",
        "maeRegularized",
        "rmseRegularized",
        "avgPredictionBiasRaw",
        "avgPredictionBiasRegularized",
        "p95AbsoluteErrorRaw",
        "p95AbsoluteErrorRegularized",
    ],
    "Coverage and popularity": [
        "algorithmId",
        "variantId",
        "catalogCoveragePct",
        "uniqueRecommendedMovies",
        "avgRecommendedRatingCount",
        "medianRecommendedRatingCount",
        "avgRecommendedTmdbPopularity",
        "medianRecommendedTmdbPopularity",
    ],
    "Public catalog safety": [
        "algorithmId",
        "variantId",
        "nonPublicRecommendationCount",
        "nonPublicRecommendationPct",
        "alreadyRatedRecommendationCount",
        "alreadyRatedRecommendationPct",
    ],
    "Fallback and robustness": [
        "algorithmId",
        "variantId",
        "fallbackUsedCases",
        "fallbackUsedPct",
        "avgFallbackRecommendationsAdded",
        "minRecommendationsReturned",
        "zeroRecommendationCases",
        "casesBelowLimit",
        "casesBelowLimitPct",
    ],
    "Runtime performance": [
        "algorithmId",
        "variantId",
        "runtimeRuns",
        "avgRuntimeMs",
        "p50RuntimeMs",
        "p95RuntimeMs",
        "p99RuntimeMs",
        "maxRuntimeMs",
        "avgPersonalizedRuntimeMs",
        "avgFallbackRuntimeMs",
        "avgTotalRuntimeMs",
    ],
    "API performance": [
        "algorithmId",
        "variantId",
        "apiRuns",
        "avgApiMs",
        "p50ApiMs",
        "p95ApiMs",
        "p99ApiMs",
        "maxApiMs",
        "avgResponseSizeKb",
        "statusCodeErrorCount",
    ],
    "Offline build and artifact cost": [
        "algorithmId",
        "variantId",
        "buildTimeSeconds",
        "modelArtifactSizeMb",
        "ratings",
        "users",
        "publicMovies",
        "supportMovies",
        "modelMovies",
        "neighborRows",
        "rankingRows",
        "neighborsCsvSizeMb",
        "neighborsSqliteSizeMb",
        "rankingCsvSizeMb",
        "rankingSqliteSizeMb",
        "ratingsSqliteSizeMb",
        "userStatsCsvSizeMb",
    ],
    "Algorithm parameters": [
        "algorithmId",
        "variantId",
        "topK",
        "minSupport",
        "topNeighbors",
        "minOverlap",
        "shrinkage",
        "minCandidateNeighborCount",
        "candidateShrinkage",
        "minPredictionScore",
    ],
}


def write_markdown_report(*, path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    content = [
        "# Collaborative recommender audit",
        "",
        "Measured values only. No winner selection and no automatic conclusions.",
        "",
        "## Run configuration",
        "",
        markdown_key_value_table(
            {
                "runId": summary["runId"],
                "evaluationId": summary["evaluationId"],
                "startedAt": summary["startedAt"],
                "caseCount": summary["caseCount"],
                "limit": summary["limit"],
                "runtimeRepeats": summary["runtimeRepeats"],
                "apiRepeats": summary["apiRepeats"],
                "skipApi": summary["skipApi"],
            }
        ),
        "",
    ]

    for section_title, columns in SECTION_COLUMNS.items():
        content.extend(
            [
                f"## {section_title}",
                "",
                markdown_rows_table(rows, columns),
                "",
            ]
        )

    content.extend(
        [
            "## Generated files",
            "",
            *[f"- `{filename}`" for filename in summary["generatedFiles"]],
            "",
        ]
    )
    path.write_text("\n".join(content), encoding="utf-8")


def write_html_report(*, path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    sections_html = "".join(
        f"""
  <section>
    <h2>{escape(section_title)}</h2>
    {html_rows_table(rows, columns)}
  </section>
"""
        for section_title, columns in SECTION_COLUMNS.items()
    )

    generated_files_links = "".join(
        f'<a href="/recommender-audit/collaborative/files/{escape(filename)}">{escape(filename)}</a>'
        for filename in summary["generatedFiles"]
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Collaborative recommender audit {escape(str(summary["runId"]))}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      color-scheme: dark;
      --bg: #08111f;
      --panel: #101a2f;
      --panel-strong: #14213b;
      --text: #eaf2ff;
      --muted: #9fb1c9;
      --border: rgba(148, 163, 184, 0.24);
      --border-strong: rgba(103, 217, 255, 0.32);
      --cyan: #67d9ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(77, 163, 255, 0.16), transparent 34rem),
        linear-gradient(180deg, #08111f 0%, #0a1221 46%, #070d18 100%);
      color: var(--text);
      line-height: 1.5;
    }}
    main {{ max-width: 1480px; margin: 0 auto; padding: 28px; }}
    header, section {{
      background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.012)), var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 22px;
      margin: 18px 0;
    }}
    h1 {{ margin: 0 0 8px; font-size: 32px; }}
    h2 {{ margin: 0 0 14px; font-size: 20px; }}
    p {{ margin: 0 0 12px; color: var(--muted); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin: 20px 0;
    }}
    .metric-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 15px 17px;
    }}
    .metric-label {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 5px;
      font-weight: 700;
    }}
    .metric-value {{ font-weight: 800; font-size: 18px; }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: rgba(8, 17, 31, 0.48);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1080px;
      font-size: 13px;
    }}
    th, td {{
      padding: 11px 12px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.16);
      text-align: right;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2), th:nth-child(3), td:nth-child(3) {{
      text-align: left;
    }}
    th {{
      background: linear-gradient(180deg, rgba(77, 163, 255, 0.22), rgba(77, 163, 255, 0.10)), var(--panel-strong);
      position: sticky;
      top: 0;
      border-bottom: 1px solid var(--border-strong);
    }}
    .links a {{
      display: inline-flex;
      align-items: center;
      margin: 5px 9px 5px 0;
      padding: 8px 11px;
      color: #dbeafe;
      background: rgba(77, 163, 255, 0.12);
      border: 1px solid rgba(77, 163, 255, 0.28);
      border-radius: 999px;
      text-decoration: none;
      font-weight: 700;
      font-size: 13px;
    }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>Collaborative recommender audit</h1>
    <p>Measured values only. No winner selection and no automatic conclusions.</p>
  </header>
  <div class="grid">
    {html_metric_card("Run ID", summary["runId"])}
    {html_metric_card("Started at", summary["startedAt"])}
    {html_metric_card("Cases", summary["caseCount"])}
    {html_metric_card("Limit", summary["limit"])}
    {html_metric_card("Runtime repeats", summary["runtimeRepeats"])}
    {html_metric_card("API repeats", summary["apiRepeats"])}
  </div>
  <section>
    <h2>Generated files</h2>
    <div class="links">{generated_files_links}</div>
  </section>
  {sections_html}
</main>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (str(row["algorithmId"]), str(row["variantId"])))


def serialize_evaluation_cases(cases: list[EvaluationCase]) -> list[dict[str, Any]]:
    return [
        {
            "caseId": case.case_id,
            "userId": case.user_id,
            "ratings": [
                {"movieId": rating.movie_id, "rating": rating.rating}
                for rating in case.ratings
            ],
            "holdoutMovieIds": case.holdout_movie_ids,
            "holdoutRatings": [
                {"movieId": rating.movie_id, "rating": rating.rating}
                for rating in case.holdout_ratings
            ],
        }
        for case in cases
    ]


def markdown_key_value_table(values: dict[str, Any]) -> str:
    rows = [{"key": key, "value": value} for key, value in values.items()]
    return markdown_rows_table(rows, ["key", "value"])


def markdown_rows_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(markdown_value(row.get(column)) for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def markdown_value(value: object) -> str:
    return format_report_value(value).replace("|", "\\|")


def html_metric_card(label: str, value: object) -> str:
    return (
        '<div class="metric-card">'
        f'<span class="metric-label">{escape(label)}</span>'
        f'<span class="metric-value">{escape(format_report_value(value))}</span>'
        "</div>"
    )


def html_rows_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(
            f"<td>{escape(format_report_value(row.get(column)))}</td>"
            for column in columns
        )
        body_rows.append(f"<tr>{cells}</tr>")
    body = "".join(body_rows)
    return f'<div class="table-wrap"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>'


def format_report_value(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


if __name__ == "__main__":
    main()
