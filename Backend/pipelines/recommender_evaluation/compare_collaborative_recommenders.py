import argparse
import csv
import json
import math
import random
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi.testclient import TestClient

from html import escape
import shutil

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
from app.recommenders.collaborative.algorithms.popularity_baseline.recommender import (
    PopularityBaselineRecommender,
)
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationRequest,
    CollaborativeUserRating,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.storage import (
    get_popularity_baseline_artifacts,
    load_popularity_baseline_manifest,
)


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    user_id: int
    ratings: list[CollaborativeUserRating]
    holdout_movie_ids: list[int]

    def to_request(self, *, limit: int) -> CollaborativeRecommendationRequest:
        return CollaborativeRecommendationRequest(
            ratings=self.ratings,
            limit=limit,
            template_session_id=self.case_id,
        )

    def to_api_payload(self, *, limit: int) -> dict:
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

    public_movie_ids = {
        int(movie["movieId"])
        for movie in catalog_repository.get_recommendation_candidates()
    }

    evaluation_cases = build_evaluation_cases(
        public_movie_ids=public_movie_ids,
        case_count=args.case_count,
        min_positive_input=args.min_positive_input,
        holdout_count=args.holdout_count,
        seed=args.seed,
    )

    recommenders = load_evaluated_recommenders(
        requested_variants=args.variant,
    )

    rows = []
    api_client = TestClient(app)

    for evaluated in recommenders:
        print(f"Evaluating {evaluated.algorithm_id} / {evaluated.variant_id}")

        runtime_metrics, quality_metrics = benchmark_runtime_and_quality(
            evaluated=evaluated,
            cases=evaluation_cases,
            public_movie_count=len(public_movie_ids),
            limit=args.limit,
            runtime_repeats=args.runtime_repeats,
        )

        if args.skip_api:
            api_metrics = empty_api_metrics()
        else:
            api_metrics = benchmark_api(
                evaluated=evaluated,
                client=api_client,
                cases=evaluation_cases,
                limit=args.limit,
                api_repeats=args.api_repeats,
            )

        row = {
            "algorithmId": evaluated.algorithm_id,
            "algorithmLabel": evaluated.algorithm_label,
            "variantId": evaluated.variant_id,
            **offline_metrics(evaluated),
            **runtime_metrics,
            **api_metrics,
            **quality_metrics,
        }
        rows.append(row)

    rows = add_decision_scores(rows)
    selected_rows = select_best_variant_per_algorithm(rows)
    overall_winner = max(selected_rows, key=lambda item: item["decisionScore"])

    write_json(
        output_dir / "evaluation_cases.json",
        [
            {
                "caseId": case.case_id,
                "userId": case.user_id,
                "ratings": [
                    {
                        "movieId": rating.movie_id,
                        "rating": rating.rating,
                    }
                    for rating in case.ratings
                ],
                "holdoutMovieIds": case.holdout_movie_ids,
            }
            for case in evaluation_cases
        ],
    )
    summary = {
        "runId": run_id,
        "evaluationId": evaluation_id,
        "startedAt": started_at.isoformat(),
        "caseCount": len(evaluation_cases),
        "limit": args.limit,
        "runtimeRepeats": args.runtime_repeats,
        "apiRepeats": args.api_repeats,
        "skipApi": args.skip_api,
        "selectionWeights": selection_weights(),
        "selectedVariants": selected_rows,
        "highestDecisionScoreVariant": overall_winner,
    }

    write_json(output_dir / "variant_metrics.json", rows)
    write_json(output_dir / "selected_variants.json", selected_rows)
    write_json(output_dir / "comparison_summary.json", summary)

    write_csv(output_dir / "variant_metrics.csv", rows)
    write_csv(output_dir / "selected_variants.csv", selected_rows)

    write_markdown_report(
        path=output_dir / "report.md",
        summary=summary,
        rows=rows,
        selected_rows=selected_rows,
    )
    write_html_report(
        path=output_dir / "index.html",
        summary=summary,
        rows=rows,
        selected_rows=selected_rows,
    )

    print()
    print(f"Evaluation completed: {output_dir}")
    print("Selected variants:")
    for row in selected_rows:
        print(
            row["algorithmId"],
            row["variantId"],
            "decisionScore=",
            row["decisionScore"],
        )
    print(
        "Overall winner:",
        overall_winner["algorithmId"],
        overall_winner["variantId"],
        "decisionScore=",
        overall_winner["decisionScore"],
    )


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
        input_positive_rows = positives[
            holdout_count : holdout_count + min_positive_input
        ]
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

        holdout_movie_ids = [int(row["movieId"]) for row in holdout_rows]

        cases.append(
            EvaluationCase(
                case_id=f"eval-user-{user_id}-{len(cases) + 1}",
                user_id=user_id,
                ratings=ratings_input,
                holdout_movie_ids=holdout_movie_ids,
            )
        )

        if len(cases) >= case_count:
            break

    if len(cases) < case_count:
        raise RuntimeError(
            f"Only {len(cases)} evaluation cases could be built. "
            f"Requested {case_count}."
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
        dtype={
            "userId": "int32",
            "movieId": "int32",
            "rating": "float32",
        },
        chunksize=1_000_000,
    ):
        filtered = chunk[chunk["movieId"].isin(public_movie_ids)]
        if not filtered.empty:
            chunks.append(filtered)

    if not chunks:
        raise RuntimeError("No public movie ratings found for evaluation.")

    ratings = pd.concat(chunks, ignore_index=True)
    ratings = ratings.drop_duplicates(subset=["userId", "movieId"], keep="last")
    return ratings


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
    baseline_manifest = load_popularity_baseline_manifest()

    recommenders = [
        EvaluatedRecommender(
            algorithm_id=PopularityBaselineRecommender.algorithm_id,
            algorithm_label=PopularityBaselineRecommender.algorithm_label,
            variant_id="default",
            recommender=PopularityBaselineRecommender(),
            manifest=baseline_manifest,
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

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            recommenders.append(
                EvaluatedRecommender(
                    algorithm_id="item_knn_cosine",
                    algorithm_label="ItemKNN Cosine",
                    variant_id=variant_id,
                    recommender=ItemKnnCosineRecommender(model_variant_id=variant_id),
                    manifest=manifest,
                )
            )

    if len(recommenders) == 1:
        raise RuntimeError("No ItemKNN Cosine variants were found.")

    return recommenders


def offline_metrics(evaluated: EvaluatedRecommender) -> dict[str, Any]:
    counts = evaluated.manifest.get("counts", {})
    parameters = evaluated.manifest.get("parameters", {})

    if evaluated.algorithm_id == "popularity_baseline":
        artifacts = get_popularity_baseline_artifacts()
        ranking_sqlite_size_mb = file_size_mb(artifacts.ranking_sqlite_path)

        return {
            "topK": None,
            "minSupport": None,
            "buildTimeSeconds": counts.get("buildTimeSeconds", 0),
            "ratings": None,
            "users": None,
            "publicMovies": counts.get("publicCandidates"),
            "supportMovies": None,
            "modelMovies": counts.get("rankedMovies"),
            "neighborRows": 0,
            "neighborsCsvSizeMb": 0,
            "neighborsSqliteSizeMb": 0,
            "rankingRows": counts.get("rankedMovies"),
            "rankingCsvSizeMb": file_size_mb(artifacts.ranking_csv_path),
            "rankingSqliteSizeMb": ranking_sqlite_size_mb,
            "modelArtifactSizeMb": ranking_sqlite_size_mb,
        }

    variant_dir = (
        COLLABORATIVE_RECOMMENDER_MODELS_DIR
        / evaluated.algorithm_id
        / evaluated.variant_id
    )
    csv_path = variant_dir / "neighbors.csv"
    sqlite_path = variant_dir / "neighbors.sqlite"
    neighbors_sqlite_size_mb = file_size_mb(sqlite_path)

    return {
        "topK": parameters.get("topK"),
        "minSupport": parameters.get("minSupport"),
        "buildTimeSeconds": counts.get("buildTimeSeconds"),
        "ratings": counts.get("ratings"),
        "users": counts.get("users"),
        "publicMovies": counts.get("publicMovies"),
        "supportMovies": counts.get("supportMovies"),
        "modelMovies": counts.get("modelMovies"),
        "neighborRows": counts.get("generatedNeighborRows"),
        "neighborsCsvSizeMb": file_size_mb(csv_path),
        "neighborsSqliteSizeMb": neighbors_sqlite_size_mb,
        "rankingRows": 0,
        "rankingCsvSizeMb": 0,
        "rankingSqliteSizeMb": 0,
        "modelArtifactSizeMb": neighbors_sqlite_size_mb,
    }


def benchmark_runtime_and_quality(
    *,
    evaluated: EvaluatedRecommender,
    cases: list[EvaluationCase],
    public_movie_count: int,
    limit: int,
    runtime_repeats: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    timings_ms: list[float] = []
    personalized_runtime_ms: list[float] = []
    fallback_runtime_ms: list[float] = []
    total_runtime_details_ms: list[float] = []

    recommendations_returned: list[int] = []
    discarded_non_public: list[int] = []
    discarded_rated: list[int] = []
    missing_sources: list[int] = []
    fallback_used_values: list[int] = []
    fallback_recommendations_added: list[int] = []

    quality_accumulator = QualityAccumulator(
        public_movie_count=public_movie_count,
        limit=limit,
    )

    for repeat_index in range(runtime_repeats):
        for case in cases:
            request = case.to_request(limit=limit)

            started = time.perf_counter()
            result = evaluated.recommender.recommend(request)
            elapsed_ms = (time.perf_counter() - started) * 1000

            details = result.recommender_details.details

            timings_ms.append(elapsed_ms)
            personalized_runtime_ms.append(
                float(details.get("personalizedRuntimeMs", elapsed_ms))
            )
            fallback_runtime_ms.append(float(details.get("fallbackRuntimeMs", 0.0)))
            total_runtime_details_ms.append(
                float(details.get("totalRuntimeMs", elapsed_ms))
            )

            if repeat_index == 0:
                recommended_ids = [item.movie_id for item in result.recommendations]
                quality_accumulator.add_case(
                    holdout_movie_ids=case.holdout_movie_ids,
                    recommended_movie_ids=recommended_ids,
                )

                recommendation_count = len(result.recommendations)
                fallback_added = int(details.get("fallbackRecommendationsAdded", 0))

                recommendations_returned.append(recommendation_count)
                fallback_recommendations_added.append(fallback_added)
                fallback_used_values.append(
                    1 if bool(details.get("fallbackUsed", False)) else 0
                )
                discarded_non_public.append(
                    int(details.get("discardedNonPublicCandidates", 0))
                )
                discarded_rated.append(int(details.get("discardedRatedCandidates", 0)))
                missing_sources.append(int(details.get("missingSourceNeighborRows", 0)))

    fallback_used_cases = sum(fallback_used_values)
    cases_below_limit = sum(
        1
        for recommendation_count in recommendations_returned
        if recommendation_count < limit
    )
    zero_recommendation_cases = sum(
        1
        for recommendation_count in recommendations_returned
        if recommendation_count == 0
    )

    runtime_metrics = {
        "runtimeRuns": len(timings_ms),
        "avgRuntimeMs": round_float(mean(timings_ms)),
        "p50RuntimeMs": round_float(percentile(timings_ms, 50)),
        "p95RuntimeMs": round_float(percentile(timings_ms, 95)),
        "p99RuntimeMs": round_float(percentile(timings_ms, 99)),
        "maxRuntimeMs": round_float(max(timings_ms)),
        "avgPersonalizedRuntimeMs": round_float(mean(personalized_runtime_ms)),
        "avgFallbackRuntimeMs": round_float(mean(fallback_runtime_ms)),
        "avgTotalRuntimeMs": round_float(mean(total_runtime_details_ms)),
        "avgRecommendationsReturned": round_float(mean(recommendations_returned)),
        "minRecommendationsReturned": (
            min(recommendations_returned) if recommendations_returned else 0
        ),
        "zeroRecommendationCases": zero_recommendation_cases,
        "casesBelowLimit": cases_below_limit,
        "casesBelowLimitPct": (
            round_float(cases_below_limit / len(recommendations_returned) * 100)
            if recommendations_returned
            else 0.0
        ),
        "fallbackUsedCases": fallback_used_cases,
        "fallbackUsedPct": (
            round_float(fallback_used_cases / len(fallback_used_values) * 100)
            if fallback_used_values
            else 0.0
        ),
        "avgFallbackRecommendationsAdded": round_float(
            mean(fallback_recommendations_added)
        ),
        "avgDiscardedNonPublicCandidates": round_float(mean(discarded_non_public)),
        "avgDiscardedRatedCandidates": round_float(mean(discarded_rated)),
        "avgMissingSourceNeighborRows": round_float(mean(missing_sources)),
    }

    return runtime_metrics, quality_accumulator.metrics()


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
    recommendations_returned: list[int] = []
    status_code_errors = 0

    api_personalized_runtime_ms: list[float] = []
    api_fallback_runtime_ms: list[float] = []
    api_total_runtime_ms: list[float] = []
    api_fallback_used_values: list[int] = []
    api_fallback_recommendations_added: list[int] = []

    for _ in range(api_repeats):
        for case in cases:
            started = time.perf_counter()
            response = client.post(
                "/recommendations/collaborative",
                json=case.to_api_payload(limit=limit),
            )
            elapsed_ms = (time.perf_counter() - started) * 1000

            timings_ms.append(elapsed_ms)
            response_sizes_kb.append(len(response.content) / 1024)

            if response.status_code >= 400:
                status_code_errors += 1
                continue

            payload = response.json()
            details = payload.get("recommenderDetails", {}).get("details", {})

            recommendation_count = len(payload.get("recommendations", []))
            fallback_added = int(details.get("fallbackRecommendationsAdded", 0))

            recommendations_returned.append(recommendation_count)
            api_personalized_runtime_ms.append(
                float(details.get("personalizedRuntimeMs", 0.0))
            )
            api_fallback_runtime_ms.append(float(details.get("fallbackRuntimeMs", 0.0)))
            api_total_runtime_ms.append(float(details.get("totalRuntimeMs", 0.0)))
            api_fallback_recommendations_added.append(fallback_added)
            api_fallback_used_values.append(
                1 if bool(details.get("fallbackUsed", False)) else 0
            )

    api_fallback_used_cases = sum(api_fallback_used_values)
    api_cases_below_limit = sum(
        1
        for recommendation_count in recommendations_returned
        if recommendation_count < limit
    )
    api_zero_recommendation_cases = sum(
        1
        for recommendation_count in recommendations_returned
        if recommendation_count == 0
    )

    return {
        "apiRuns": len(timings_ms),
        "avgApiMs": round_float(mean(timings_ms)),
        "p50ApiMs": round_float(percentile(timings_ms, 50)),
        "p95ApiMs": round_float(percentile(timings_ms, 95)),
        "p99ApiMs": round_float(percentile(timings_ms, 99)),
        "maxApiMs": round_float(max(timings_ms)),
        "avgResponseSizeKb": round_float(mean(response_sizes_kb)),
        "avgApiRecommendationsReturned": round_float(mean(recommendations_returned)),
        "statusCodeErrorCount": status_code_errors,
        "avgApiPersonalizedRuntimeMs": round_float(mean(api_personalized_runtime_ms)),
        "avgApiFallbackRuntimeMs": round_float(mean(api_fallback_runtime_ms)),
        "avgApiTotalRuntimeMs": round_float(mean(api_total_runtime_ms)),
        "apiFallbackUsedCases": api_fallback_used_cases,
        "apiFallbackUsedPct": (
            round_float(api_fallback_used_cases / len(api_fallback_used_values) * 100)
            if api_fallback_used_values
            else 0.0
        ),
        "avgApiFallbackRecommendationsAdded": round_float(
            mean(api_fallback_recommendations_added)
        ),
        "minApiRecommendationsReturned": (
            min(recommendations_returned) if recommendations_returned else 0
        ),
        "apiZeroRecommendationCases": api_zero_recommendation_cases,
        "apiCasesBelowLimit": api_cases_below_limit,
        "apiCasesBelowLimitPct": (
            round_float(api_cases_below_limit / len(recommendations_returned) * 100)
            if recommendations_returned
            else 0.0
        ),
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
        "avgApiRecommendationsReturned": None,
        "statusCodeErrorCount": None,
        "avgApiPersonalizedRuntimeMs": None,
        "avgApiFallbackRuntimeMs": None,
        "avgApiTotalRuntimeMs": None,
        "apiFallbackUsedCases": None,
        "apiFallbackUsedPct": None,
        "avgApiFallbackRecommendationsAdded": None,
        "minApiRecommendationsReturned": None,
        "apiZeroRecommendationCases": None,
        "apiCasesBelowLimit": None,
        "apiCasesBelowLimitPct": None,
    }


def set_active_recommender_for_api(evaluated: EvaluatedRecommender) -> None:
    settings.active_collaborative_algorithm = evaluated.algorithm_id
    collaborative_registry.COLLABORATIVE_RECOMMENDER_REGISTRY[
        evaluated.algorithm_id
    ] = evaluated.recommender


class QualityAccumulator:
    def __init__(self, *, public_movie_count: int, limit: int) -> None:
        self.public_movie_count = public_movie_count
        self.limit = limit
        self.case_count = 0
        self.hit_at_5_values: list[float] = []
        self.hit_at_10_values: list[float] = []
        self.recall_at_5_values: list[float] = []
        self.recall_at_10_values: list[float] = []
        self.ndcg_at_5_values: list[float] = []
        self.ndcg_at_10_values: list[float] = []
        self.mrr_at_10_values: list[float] = []
        self.unique_recommended_movie_ids: set[int] = set()

    def add_case(
        self,
        *,
        holdout_movie_ids: list[int],
        recommended_movie_ids: list[int],
    ) -> None:
        self.case_count += 1
        self.unique_recommended_movie_ids.update(recommended_movie_ids)

        holdout = set(holdout_movie_ids)

        self.hit_at_5_values.append(hit_rate_at_k(recommended_movie_ids, holdout, 5))
        self.hit_at_10_values.append(hit_rate_at_k(recommended_movie_ids, holdout, 10))
        self.recall_at_5_values.append(recall_at_k(recommended_movie_ids, holdout, 5))
        self.recall_at_10_values.append(recall_at_k(recommended_movie_ids, holdout, 10))
        self.ndcg_at_5_values.append(ndcg_at_k(recommended_movie_ids, holdout, 5))
        self.ndcg_at_10_values.append(ndcg_at_k(recommended_movie_ids, holdout, 10))
        self.mrr_at_10_values.append(mrr_at_k(recommended_movie_ids, holdout, 10))

    def metrics(self) -> dict[str, Any]:
        coverage_pct = (
            len(self.unique_recommended_movie_ids) / self.public_movie_count * 100
        )

        return {
            "evaluationCases": self.case_count,
            "hitRateAt5": round_float(mean(self.hit_at_5_values)),
            "hitRateAt10": round_float(mean(self.hit_at_10_values)),
            "recallAt5": round_float(mean(self.recall_at_5_values)),
            "recallAt10": round_float(mean(self.recall_at_10_values)),
            "ndcgAt5": round_float(mean(self.ndcg_at_5_values)),
            "ndcgAt10": round_float(mean(self.ndcg_at_10_values)),
            "mrrAt10": round_float(mean(self.mrr_at_10_values)),
            "catalogCoveragePct": round_float(coverage_pct),
            "uniqueRecommendedMovies": len(self.unique_recommended_movie_ids),
        }


def hit_rate_at_k(
    recommended_movie_ids: list[int],
    holdout_movie_ids: set[int],
    k: int,
) -> float:
    return 1.0 if set(recommended_movie_ids[:k]) & holdout_movie_ids else 0.0


def recall_at_k(
    recommended_movie_ids: list[int],
    holdout_movie_ids: set[int],
    k: int,
) -> float:
    if not holdout_movie_ids:
        return 0.0

    hits = len(set(recommended_movie_ids[:k]) & holdout_movie_ids)
    return hits / len(holdout_movie_ids)


def ndcg_at_k(
    recommended_movie_ids: list[int],
    holdout_movie_ids: set[int],
    k: int,
) -> float:
    dcg = 0.0

    for rank, movie_id in enumerate(recommended_movie_ids[:k], start=1):
        if movie_id in holdout_movie_ids:
            dcg += 1 / math.log2(rank + 1)

    ideal_hits = min(len(holdout_movie_ids), k)
    if ideal_hits == 0:
        return 0.0

    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def mrr_at_k(
    recommended_movie_ids: list[int],
    holdout_movie_ids: set[int],
    k: int,
) -> float:
    for rank, movie_id in enumerate(recommended_movie_ids[:k], start=1):
        if movie_id in holdout_movie_ids:
            return 1 / rank

    return 0.0


def add_decision_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weights = selection_weights()

    ndcg_scores = normalize_higher_is_better(rows, "ndcgAt10")
    recall_scores = normalize_higher_is_better(rows, "recallAt10")
    coverage_scores = normalize_higher_is_better(rows, "catalogCoveragePct")
    latency_scores = normalize_lower_is_better(rows, "p95ApiMs")
    size_scores = normalize_lower_is_better(rows, "modelArtifactSizeMb")

    scored_rows = []
    for index, row in enumerate(rows):
        decision_score = (
            weights["ndcgAt10"] * ndcg_scores[index]
            + weights["recallAt10"] * recall_scores[index]
            + weights["catalogCoveragePct"] * coverage_scores[index]
            + weights["p95ApiMs"] * latency_scores[index]
            + weights["modelArtifactSizeMb"] * size_scores[index]
        )

        scored_row = dict(row)
        scored_row["decisionScore"] = round_float(decision_score)
        scored_rows.append(scored_row)

    return scored_rows


def selection_weights() -> dict[str, float]:
    return {
        "ndcgAt10": 0.45,
        "recallAt10": 0.25,
        "catalogCoveragePct": 0.15,
        "p95ApiMs": 0.10,
        "modelArtifactSizeMb": 0.05,
    }


def normalize_higher_is_better(
    rows: list[dict[str, Any]],
    key: str,
) -> list[float]:
    values = [numeric_value(row.get(key)) for row in rows]
    return normalize(values)


def normalize_lower_is_better(
    rows: list[dict[str, Any]],
    key: str,
) -> list[float]:
    values = [numeric_value(row.get(key)) for row in rows]
    normalized = normalize(values)
    return [1 - value for value in normalized]


def normalize(values: list[float]) -> list[float]:
    minimum = min(values)
    maximum = max(values)

    if maximum == minimum:
        return [1.0 for _ in values]

    return [(value - minimum) / (maximum - minimum) for value in values]


def numeric_value(value: object) -> float:
    if value is None:
        return 0.0

    return float(value)


def select_best_variant_per_algorithm(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    best_by_algorithm: dict[str, dict[str, Any]] = {}

    for row in rows:
        current_best = best_by_algorithm.get(row["algorithmId"])
        if current_best is None or row["decisionScore"] > current_best["decisionScore"]:
            best_by_algorithm[row["algorithmId"]] = row

    return list(best_by_algorithm.values())


def file_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0

    return round(path.stat().st_size / 1024 / 1024, 3)


def mean(values: list[float] | list[int]) -> float:
    if not values:
        return 0.0

    return float(statistics.mean(values))


def percentile(values: list[float], percentile_value: int) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    index = math.ceil(percentile_value / 100 * len(ordered)) - 1
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def round_float(value: float | None) -> float | None:
    if value is None:
        return None

    return round(float(value), 6)


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = sorted({key for row in rows for key in row.keys()})

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


REPORT_COLUMNS = [
    "algorithmId",
    "variantId",
    "decisionScore",
    "buildTimeSeconds",
    "modelArtifactSizeMb",
    "neighborRows",
    "rankingRows",
    "avgRuntimeMs",
    "avgPersonalizedRuntimeMs",
    "avgFallbackRuntimeMs",
    "avgTotalRuntimeMs",
    "avgApiMs",
    "p95ApiMs",
    "hitRateAt10",
    "recallAt10",
    "ndcgAt10",
    "catalogCoveragePct",
    "fallbackUsedPct",
    "minRecommendationsReturned",
    "zeroRecommendationCases",
    "casesBelowLimit",
]

OFFLINE_REPORT_COLUMNS = [
    "algorithmId",
    "variantId",
    "topK",
    "minSupport",
    "buildTimeSeconds",
    "modelArtifactSizeMb",
    "neighborsSqliteSizeMb",
    "rankingSqliteSizeMb",
    "neighborRows",
    "rankingRows",
    "modelMovies",
    "publicMovies",
]

RUNTIME_REPORT_COLUMNS = [
    "algorithmId",
    "variantId",
    "avgRuntimeMs",
    "p50RuntimeMs",
    "p95RuntimeMs",
    "p99RuntimeMs",
    "maxRuntimeMs",
    "avgPersonalizedRuntimeMs",
    "avgFallbackRuntimeMs",
    "avgTotalRuntimeMs",
]

API_REPORT_COLUMNS = [
    "algorithmId",
    "variantId",
    "avgApiMs",
    "p50ApiMs",
    "p95ApiMs",
    "p99ApiMs",
    "maxApiMs",
    "avgResponseSizeKb",
    "statusCodeErrorCount",
]

QUALITY_REPORT_COLUMNS = [
    "algorithmId",
    "variantId",
    "evaluationCases",
    "hitRateAt5",
    "hitRateAt10",
    "recallAt5",
    "recallAt10",
    "ndcgAt5",
    "ndcgAt10",
    "mrrAt10",
    "catalogCoveragePct",
    "uniqueRecommendedMovies",
]

FALLBACK_REPORT_COLUMNS = [
    "algorithmId",
    "variantId",
    "fallbackUsedCases",
    "fallbackUsedPct",
    "avgFallbackRecommendationsAdded",
    "minRecommendationsReturned",
    "zeroRecommendationCases",
    "casesBelowLimit",
    "casesBelowLimitPct",
    "apiFallbackUsedCases",
    "apiFallbackUsedPct",
    "avgApiFallbackRecommendationsAdded",
    "minApiRecommendationsReturned",
    "apiZeroRecommendationCases",
    "apiCasesBelowLimit",
    "apiCasesBelowLimitPct",
]


def write_markdown_report(
    *,
    path: Path,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
) -> None:
    sorted_rows = sort_rows_by_decision_score(rows)
    sorted_selected_rows = sort_rows_by_algorithm(selected_rows)

    content = [
        "# Collaborative recommender evaluation",
        "",
        "This report presents measured values from a collaborative recommender evaluation run.",
        "It does not add manual conclusions; rows are shown from generated metrics.",
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
        "## Decision score weights",
        "",
        markdown_key_value_table(summary["selectionWeights"]),
        "",
        "## Decision score ranking",
        "",
        "Rows are sorted by `decisionScore` using the configured weights above.",
        "",
        markdown_rows_table(sorted_rows, REPORT_COLUMNS),
        "",
        "## Selected variants by algorithm",
        "",
        "Selected variants are the highest `decisionScore` rows per `algorithmId`.",
        "",
        markdown_rows_table(sorted_selected_rows, REPORT_COLUMNS),
        "",
        "## Offline/build metrics",
        "",
        markdown_rows_table(sorted_rows, OFFLINE_REPORT_COLUMNS),
        "",
        "## Runtime metrics",
        "",
        markdown_rows_table(sorted_rows, RUNTIME_REPORT_COLUMNS),
        "",
        "## API metrics",
        "",
        markdown_rows_table(sorted_rows, API_REPORT_COLUMNS),
        "",
        "## Quality metrics",
        "",
        markdown_rows_table(sorted_rows, QUALITY_REPORT_COLUMNS),
        "",
        "## Fallback and recommendation-count metrics",
        "",
        markdown_rows_table(sorted_rows, FALLBACK_REPORT_COLUMNS),
        "",
        "## Generated files",
        "",
        "- `comparison_summary.json`",
        "- `variant_metrics.json`",
        "- `variant_metrics.csv`",
        "- `selected_variants.json`",
        "- `selected_variants.csv`",
        "- `evaluation_cases.json`",
        "- `index.html`",
        "",
    ]

    path.write_text("\n".join(content), encoding="utf-8")


def write_html_report(
    *,
    path: Path,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
) -> None:
    sorted_rows = sort_rows_by_decision_score(rows)
    sorted_selected_rows = sort_rows_by_algorithm(selected_rows)

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Collaborative recommender evaluation {escape(str(summary["runId"]))}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
    :root {{
      color-scheme: dark;
      --bg: #08111f;
      --bg-soft: #0b1526;
      --panel: #101a2f;
      --panel-strong: #14213b;
      --panel-soft: #17243d;
      --text: #eaf2ff;
      --muted: #9fb1c9;
      --border: rgba(148, 163, 184, 0.24);
      --border-strong: rgba(103, 217, 255, 0.32);
      --blue: #4da3ff;
      --gold: #e3b341;
      --cyan: #67d9ff;
      --red: #ff6b6b;
      --green: #6bd6a7;
      --shadow: rgba(0, 0, 0, 0.32);
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(77, 163, 255, 0.16), transparent 34rem),
        radial-gradient(circle at top right, rgba(227, 179, 65, 0.10), transparent 28rem),
        linear-gradient(180deg, #08111f 0%, #0a1221 46%, #070d18 100%);
      color: var(--text);
      line-height: 1.5;
      min-height: 100vh;
    }}

    main {{
      max-width: 1480px;
      margin: 0 auto;
      padding: 34px;
    }}

    header {{
      margin-bottom: 24px;
      padding: 26px 28px;
      border: 1px solid var(--border-strong);
      border-radius: 24px;
      background:
        linear-gradient(135deg, rgba(77, 163, 255, 0.16), rgba(16, 26, 47, 0.88)),
        var(--panel);
      box-shadow: 0 22px 70px var(--shadow);
    }}

    h1 {{
      margin: 0 0 8px;
      font-size: 32px;
      letter-spacing: -0.04em;
      line-height: 1.08;
    }}

    h2 {{
      margin: 0 0 14px;
      font-size: 20px;
      letter-spacing: -0.025em;
    }}

    p {{
      margin: 0 0 12px;
      color: var(--muted);
    }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin: 20px 0;
    }}

    .metric-card {{
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.015)),
        var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 15px 17px;
      box-shadow: 0 14px 44px rgba(0, 0, 0, 0.18);
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

    .metric-value {{
      font-weight: 800;
      font-size: 18px;
      color: var(--text);
    }}

    section {{
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0.012)),
        var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 22px;
      margin: 18px 0;
      box-shadow: 0 18px 56px rgba(0, 0, 0, 0.24);
    }}

    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: rgba(8, 17, 31, 0.48);
    }}

    .table-wrap::-webkit-scrollbar {{
      height: 11px;
    }}

    .table-wrap::-webkit-scrollbar-track {{
      background: rgba(255, 255, 255, 0.05);
      border-radius: 999px;
    }}

    .table-wrap::-webkit-scrollbar-thumb {{
      background: rgba(103, 217, 255, 0.36);
      border-radius: 999px;
    }}

    .table-wrap::-webkit-scrollbar-thumb:hover {{
      background: rgba(103, 217, 255, 0.56);
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

    th:first-child,
    td:first-child,
    th:nth-child(2),
    td:nth-child(2) {{
      text-align: left;
    }}

    th {{
      background:
        linear-gradient(180deg, rgba(77, 163, 255, 0.22), rgba(77, 163, 255, 0.10)),
        var(--panel-strong);
      color: #dbeafe;
      font-weight: 800;
      position: sticky;
      top: 0;
      z-index: 1;
      border-bottom: 1px solid var(--border-strong);
    }}

    tbody tr {{
      background: rgba(16, 26, 47, 0.62);
    }}

    tbody tr:nth-child(even) {{
      background: rgba(23, 36, 61, 0.62);
    }}

    tbody tr:hover {{
      background: rgba(77, 163, 255, 0.13);
    }}

    tr:last-child td {{
      border-bottom: 0;
    }}

    code {{
      background: rgba(103, 217, 255, 0.12);
      color: #c8f4ff;
      padding: 2px 7px;
      border: 1px solid rgba(103, 217, 255, 0.22);
      border-radius: 8px;
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

    .links a:hover {{
      background: rgba(77, 163, 255, 0.22);
      border-color: rgba(103, 217, 255, 0.48);
    }}

    @media (max-width: 760px) {{
      main {{
        padding: 18px;
      }}

      header,
      section {{
        border-radius: 18px;
      }}

      h1 {{
        font-size: 26px;
      }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>Collaborative recommender evaluation</h1>
    <p>This page presents measured values from a generated evaluation run. It does not add manual conclusions.</p>
  </header>

  <div class="grid">
    {html_metric_card("Run ID", summary["runId"])}
    {html_metric_card("Started at", summary["startedAt"])}
    {html_metric_card("Cases", summary["caseCount"])}
    {html_metric_card("Limit", summary["limit"])}
    {html_metric_card("Runtime repeats", summary["runtimeRepeats"])}
    {html_metric_card("API repeats", summary["apiRepeats"])}
    {html_metric_card("Evaluation ID", summary["evaluationId"])}
  </div>

  <section>
    <h2>Generated files</h2>
    <p>Files are generated in the same audit run directory.</p>
    <div class="links">
      <a href="/recommender-audit/collaborative/files/comparison_summary.json">comparison_summary.json</a>
      <a href="/recommender-audit/collaborative/files/variant_metrics.csv">variant_metrics.csv</a>
      <a href="/recommender-audit/collaborative/files/variant_metrics.json">variant_metrics.json</a>
      <a href="/recommender-audit/collaborative/files/selected_variants.csv">selected_variants.csv</a>
      <a href="/recommender-audit/collaborative/files/selected_variants.json">selected_variants.json</a>
      <a href="/recommender-audit/collaborative/files/evaluation_cases.json">evaluation_cases.json</a>
      <a href="/recommender-audit/collaborative/files/report.md">report.md</a>
    </div>
  </section>

  <section>
    <h2>Decision score weights</h2>
    {html_key_value_table(summary["selectionWeights"])}
  </section>

  <section>
    <h2>Decision score ranking</h2>
    <p>Rows are sorted by <code>decisionScore</code> using the configured weights above.</p>
    {html_rows_table(sorted_rows, REPORT_COLUMNS)}
  </section>

  <section>
    <h2>Selected variants by algorithm</h2>
    <p>Selected variants are the highest <code>decisionScore</code> rows per <code>algorithmId</code>.</p>
    {html_rows_table(sorted_selected_rows, REPORT_COLUMNS)}
  </section>

  <section>
    <h2>Offline/build metrics</h2>
    {html_rows_table(sorted_rows, OFFLINE_REPORT_COLUMNS)}
  </section>

  <section>
    <h2>Runtime metrics</h2>
    {html_rows_table(sorted_rows, RUNTIME_REPORT_COLUMNS)}
  </section>

  <section>
    <h2>API metrics</h2>
    {html_rows_table(sorted_rows, API_REPORT_COLUMNS)}
  </section>

  <section>
    <h2>Quality metrics</h2>
    {html_rows_table(sorted_rows, QUALITY_REPORT_COLUMNS)}
  </section>

  <section>
    <h2>Fallback and recommendation-count metrics</h2>
    {html_rows_table(sorted_rows, FALLBACK_REPORT_COLUMNS)}
  </section>
</main>
</body>
</html>
"""

    path.write_text(html, encoding="utf-8")


def sort_rows_by_decision_score(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: numeric_value(row.get("decisionScore")),
        reverse=True,
    )


def sort_rows_by_algorithm(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (str(row.get("algorithmId")), str(row.get("variantId"))),
    )


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
    formatted = format_report_value(value)
    return formatted.replace("|", "\\|")


def html_metric_card(label: str, value: object) -> str:
    return (
        '<div class="metric-card">'
        f'<span class="metric-label">{escape(label)}</span>'
        f'<span class="metric-value">{escape(format_report_value(value))}</span>'
        "</div>"
    )


def html_key_value_table(values: dict[str, Any]) -> str:
    rows = [{"key": key, "value": value} for key, value in values.items()]
    return html_rows_table(rows, ["key", "value"])


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
        return ""

    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")

    return str(value)


if __name__ == "__main__":
    main()
