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
    run_id = started_at.strftime("%Y%m%d_%H%M%S")

    output_dir = RECOMMENDER_AUDIT_DIR / "collaborative_comparison" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)

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

    write_json(output_dir / "evaluation_cases.json", [
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
    ])
    write_json(output_dir / "variant_metrics.json", rows)
    write_json(output_dir / "selected_variants.json", selected_rows)
    write_json(output_dir / "comparison_summary.json", {
        "runId": run_id,
        "startedAt": started_at.isoformat(),
        "caseCount": len(evaluation_cases),
        "limit": args.limit,
        "runtimeRepeats": args.runtime_repeats,
        "apiRepeats": args.api_repeats,
        "skipApi": args.skip_api,
        "selectionWeights": selection_weights(),
        "selectedVariants": selected_rows,
        "overallWinner": overall_winner,
    })

    write_csv(output_dir / "variant_metrics.csv", rows)
    write_csv(output_dir / "selected_variants.csv", selected_rows)

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
        input_positive_rows = positives[holdout_count:holdout_count + min_positive_input]
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
    recommenders = [
        EvaluatedRecommender(
            algorithm_id=PopularityBaselineRecommender.algorithm_id,
            algorithm_label=PopularityBaselineRecommender.algorithm_label,
            variant_id="default",
            recommender=PopularityBaselineRecommender(),
            manifest={},
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
        return {
            "topK": None,
            "minSupport": None,
            "buildTimeSeconds": 0,
            "ratings": None,
            "users": None,
            "publicMovies": None,
            "supportMovies": None,
            "modelMovies": None,
            "neighborRows": 0,
            "neighborsCsvSizeMb": 0,
            "neighborsSqliteSizeMb": 0,
        }

    variant_dir = (
        COLLABORATIVE_RECOMMENDER_MODELS_DIR
        / evaluated.algorithm_id
        / evaluated.variant_id
    )
    csv_path = variant_dir / "neighbors.csv"
    sqlite_path = variant_dir / "neighbors.sqlite"

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
        "neighborsSqliteSizeMb": file_size_mb(sqlite_path),
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
    recommendations_returned: list[int] = []
    discarded_non_public: list[int] = []
    discarded_rated: list[int] = []
    missing_sources: list[int] = []

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

            timings_ms.append(elapsed_ms)

            if repeat_index == 0:
                recommended_ids = [item.movie_id for item in result.recommendations]
                quality_accumulator.add_case(
                    holdout_movie_ids=case.holdout_movie_ids,
                    recommended_movie_ids=recommended_ids,
                )

                details = result.recommender_details.details
                recommendations_returned.append(len(result.recommendations))
                discarded_non_public.append(int(details.get("discardedNonPublicCandidates", 0)))
                discarded_rated.append(int(details.get("discardedRatedCandidates", 0)))
                missing_sources.append(int(details.get("missingSourceNeighborRows", 0)))

    runtime_metrics = {
        "runtimeRuns": len(timings_ms),
        "avgRuntimeMs": round_float(mean(timings_ms)),
        "p50RuntimeMs": round_float(percentile(timings_ms, 50)),
        "p95RuntimeMs": round_float(percentile(timings_ms, 95)),
        "p99RuntimeMs": round_float(percentile(timings_ms, 99)),
        "maxRuntimeMs": round_float(max(timings_ms)),
        "avgRecommendationsReturned": round_float(mean(recommendations_returned)),
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
            recommendations_returned.append(len(payload.get("recommendations", [])))

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
            len(self.unique_recommended_movie_ids)
            / self.public_movie_count
            * 100
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
    size_scores = normalize_lower_is_better(rows, "neighborsSqliteSizeMb")

    scored_rows = []
    for index, row in enumerate(rows):
        decision_score = (
            weights["ndcgAt10"] * ndcg_scores[index]
            + weights["recallAt10"] * recall_scores[index]
            + weights["catalogCoveragePct"] * coverage_scores[index]
            + weights["p95ApiMs"] * latency_scores[index]
            + weights["neighborsSqliteSizeMb"] * size_scores[index]
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
        "neighborsSqliteSizeMb": 0.05,
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

    return [
        (value - minimum) / (maximum - minimum)
        for value in values
    ]


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


if __name__ == "__main__":
    main()