import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from app.recommenders.collaborative.common.candidate_universe import (
    CandidateUniverseMode,
    load_candidate_movie_ids,
    load_collaborative_support_movie_ids,
    load_public_movie_ids,
)
from app.recommenders.collaborative.common.models import CollaborativeUserRating
from app.recommenders.collaborative.common.offline_context import (
    CollaborativeOfflineContext,
    get_default_collaborative_offline_context,
)
AuditMode = Literal["stand_simulation", "model_evaluation"]


@dataclass(frozen=True)
class AuditHoldoutRating:
    movie_id: int
    rating: float


@dataclass(frozen=True)
class CollaborativeAuditCase:
    case_id: str
    user_id: int
    ratings: list[CollaborativeUserRating]
    holdout_movie_ids: list[int]
    holdout_ratings: list[AuditHoldoutRating]
    audit_mode: AuditMode
    candidate_universe: CandidateUniverseMode


@dataclass(frozen=True)
class StandSimulationConfig:
    case_count: int = 100
    input_count: int = 8
    holdout_count: int = 1
    min_positive_ratings: int = 6
    seed: int = 42


@dataclass(frozen=True)
class ModelEvaluationConfig:
    case_count: int = 100
    min_total_ratings: int = 50
    min_positive_ratings: int = 20
    input_positive_count: int = 20
    input_negative_count: int = 5
    holdout_count: int = 5
    seed: int = 42


@dataclass(frozen=True)
class CollaborativeAuditSplitMetadata:
    audit_mode: AuditMode
    candidate_universe: CandidateUniverseMode
    seed: int
    case_count_requested: int
    case_count_built: int
    public_movie_count: int
    support_movie_count: int
    candidate_movie_count: int
    total_ratings_loaded: int
    candidate_ratings_loaded: int
    total_users_loaded: int
    candidate_users_loaded: int
    eligible_user_count: int
    evaluation_user_count: int
    train_user_count: int
    evaluation_rating_count: int
    train_rating_count: int
    config: dict[str, Any]


@dataclass(frozen=True)
class CollaborativeAuditSplitResult:
    train_ratings: pd.DataFrame
    evaluation_cases: list[CollaborativeAuditCase]
    metadata: CollaborativeAuditSplitMetadata
def build_candidate_universe_ids(
    *,
    candidate_universe: CandidateUniverseMode,
    offline_context: CollaborativeOfflineContext | None = None,
) -> set[int]:
    return load_candidate_movie_ids(
        candidate_universe=candidate_universe,
        offline_context=offline_context,
    )


def load_collaborative_ratings(
    *,
    offline_context: CollaborativeOfflineContext | None = None,
    allowed_movie_ids: set[int] | None = None,
) -> pd.DataFrame:
    context = offline_context or get_default_collaborative_offline_context()
    ratings = pd.read_csv(
        context.ratings_csv_path,
        usecols=["userId", "movieId", "rating"],
        dtype={"userId": "int32", "movieId": "int32", "rating": "float32"},
    ).drop_duplicates(subset=["userId", "movieId"], keep="last")

    if allowed_movie_ids is not None:
        ratings = ratings[ratings["movieId"].isin(allowed_movie_ids)].copy()

    if ratings.empty:
        raise RuntimeError("No collaborative ratings were loaded for the selected scope.")

    return ratings


def select_solid_evaluation_users(
    *,
    ratings: pd.DataFrame,
    min_total_ratings: int,
    min_positive_ratings: int,
) -> pd.DataFrame:
    positives = (ratings["rating"] >= 4.0).astype("int16")
    negatives = (ratings["rating"] <= 2.0).astype("int16")
    summary = (
        ratings.assign(_positive=positives, _negative=negatives)
        .groupby("userId", sort=False)
        .agg(
            totalRatings=("rating", "count"),
            positiveRatings=("_positive", "sum"),
            negativeRatings=("_negative", "sum"),
        )
        .reset_index()
    )

    return summary[
        (summary["totalRatings"] >= min_total_ratings)
        & (summary["positiveRatings"] >= min_positive_ratings)
    ].copy()


def create_user_disjoint_split(
    *,
    ratings: pd.DataFrame,
    evaluation_user_ids: set[int],
    audit_mode: AuditMode,
    candidate_universe: CandidateUniverseMode,
    seed: int,
    case_count_requested: int,
    public_movie_count: int,
    support_movie_count: int,
    candidate_movie_count: int,
    eligible_user_count: int,
    config: dict[str, Any],
    evaluation_cases: list[CollaborativeAuditCase],
) -> CollaborativeAuditSplitResult:
    evaluation_ratings = ratings[ratings["userId"].isin(evaluation_user_ids)].copy()
    train_ratings = ratings[~ratings["userId"].isin(evaluation_user_ids)].copy()

    metadata = CollaborativeAuditSplitMetadata(
        audit_mode=audit_mode,
        candidate_universe=candidate_universe,
        seed=seed,
        case_count_requested=case_count_requested,
        case_count_built=len(evaluation_cases),
        public_movie_count=public_movie_count,
        support_movie_count=support_movie_count,
        candidate_movie_count=candidate_movie_count,
        total_ratings_loaded=int(len(ratings)),
        candidate_ratings_loaded=int(len(ratings)),
        total_users_loaded=int(ratings["userId"].nunique()),
        candidate_users_loaded=int(ratings["userId"].nunique()),
        eligible_user_count=eligible_user_count,
        evaluation_user_count=len(evaluation_user_ids),
        train_user_count=int(train_ratings["userId"].nunique()),
        evaluation_rating_count=int(len(evaluation_ratings)),
        train_rating_count=int(len(train_ratings)),
        config=config,
    )
    return CollaborativeAuditSplitResult(
        train_ratings=train_ratings,
        evaluation_cases=evaluation_cases,
        metadata=metadata,
    )


def create_stand_simulation_split(
    *,
    config: StandSimulationConfig | None = None,
    offline_context: CollaborativeOfflineContext | None = None,
) -> CollaborativeAuditSplitResult:
    resolved_config = config or StandSimulationConfig()
    candidate_universe: CandidateUniverseMode = "public_only"
    context = offline_context or get_default_collaborative_offline_context()

    public_movie_ids = load_public_movie_ids(context)
    support_movie_ids = load_collaborative_support_movie_ids(context)
    candidate_movie_ids = build_candidate_universe_ids(
        candidate_universe=candidate_universe,
        offline_context=context,
    )
    ratings = load_collaborative_ratings(
        offline_context=context,
        allowed_movie_ids=candidate_movie_ids,
    )

    min_total_ratings = max(
        resolved_config.input_count + resolved_config.holdout_count,
        resolved_config.min_positive_ratings + resolved_config.holdout_count,
    )
    eligible_users = select_solid_evaluation_users(
        ratings=ratings,
        min_total_ratings=min_total_ratings,
        min_positive_ratings=resolved_config.min_positive_ratings,
    )
    rng = random.Random(resolved_config.seed)
    user_ids = eligible_users["userId"].astype(int).tolist()
    rng.shuffle(user_ids)

    evaluation_cases: list[CollaborativeAuditCase] = []
    evaluation_user_ids: set[int] = set()

    grouped = ratings.groupby("userId", sort=False)
    for user_id in user_ids:
        case = _build_stand_case_for_user(
            user_id=user_id,
            user_ratings=grouped.get_group(user_id),
            config=resolved_config,
            rng=rng,
        )
        if case is None:
            continue
        evaluation_cases.append(case)
        evaluation_user_ids.add(user_id)
        if len(evaluation_cases) >= resolved_config.case_count:
            break

    if len(evaluation_cases) < resolved_config.case_count:
        raise RuntimeError(
            f"Only {len(evaluation_cases)} stand_simulation cases could be built. "
            f"Requested {resolved_config.case_count}."
        )

    return create_user_disjoint_split(
        ratings=ratings,
        evaluation_user_ids=evaluation_user_ids,
        audit_mode="stand_simulation",
        candidate_universe=candidate_universe,
        seed=resolved_config.seed,
        case_count_requested=resolved_config.case_count,
        public_movie_count=len(public_movie_ids),
        support_movie_count=len(support_movie_ids),
        candidate_movie_count=len(candidate_movie_ids),
        eligible_user_count=len(eligible_users),
        config=asdict(resolved_config),
        evaluation_cases=evaluation_cases,
    )


def create_model_evaluation_split(
    *,
    config: ModelEvaluationConfig | None = None,
    offline_context: CollaborativeOfflineContext | None = None,
) -> CollaborativeAuditSplitResult:
    resolved_config = config or ModelEvaluationConfig()
    candidate_universe: CandidateUniverseMode = "public_plus_support"
    context = offline_context or get_default_collaborative_offline_context()

    public_movie_ids = load_public_movie_ids(context)
    support_movie_ids = load_collaborative_support_movie_ids(context)
    candidate_movie_ids = build_candidate_universe_ids(
        candidate_universe=candidate_universe,
        offline_context=context,
    )
    ratings = load_collaborative_ratings(
        offline_context=context,
        allowed_movie_ids=candidate_movie_ids,
    )

    required_total_ratings = max(
        resolved_config.min_total_ratings,
        resolved_config.input_positive_count
        + resolved_config.input_negative_count
        + resolved_config.holdout_count,
    )
    required_positive_ratings = max(
        resolved_config.min_positive_ratings,
        resolved_config.input_positive_count + resolved_config.holdout_count,
    )
    eligible_users = select_solid_evaluation_users(
        ratings=ratings,
        min_total_ratings=required_total_ratings,
        min_positive_ratings=required_positive_ratings,
    )
    rng = random.Random(resolved_config.seed)
    user_ids = eligible_users["userId"].astype(int).tolist()
    rng.shuffle(user_ids)

    evaluation_cases: list[CollaborativeAuditCase] = []
    evaluation_user_ids: set[int] = set()

    grouped = ratings.groupby("userId", sort=False)
    for user_id in user_ids:
        case = _build_model_evaluation_case_for_user(
            user_id=user_id,
            user_ratings=grouped.get_group(user_id),
            config=resolved_config,
            rng=rng,
        )
        if case is None:
            continue
        evaluation_cases.append(case)
        evaluation_user_ids.add(user_id)
        if len(evaluation_cases) >= resolved_config.case_count:
            break

    if len(evaluation_cases) < resolved_config.case_count:
        raise RuntimeError(
            f"Only {len(evaluation_cases)} model_evaluation cases could be built. "
            f"Requested {resolved_config.case_count}."
        )

    return create_user_disjoint_split(
        ratings=ratings,
        evaluation_user_ids=evaluation_user_ids,
        audit_mode="model_evaluation",
        candidate_universe=candidate_universe,
        seed=resolved_config.seed,
        case_count_requested=resolved_config.case_count,
        public_movie_count=len(public_movie_ids),
        support_movie_count=len(support_movie_ids),
        candidate_movie_count=len(candidate_movie_ids),
        eligible_user_count=len(eligible_users),
        config=asdict(resolved_config),
        evaluation_cases=evaluation_cases,
    )


def serialize_evaluation_cases(
    cases: list[CollaborativeAuditCase],
) -> list[dict[str, Any]]:
    return [
        {
            "caseId": case.case_id,
            "userId": case.user_id,
            "auditMode": case.audit_mode,
            "candidateUniverse": case.candidate_universe,
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


def serialize_split_metadata(
    metadata: CollaborativeAuditSplitMetadata,
) -> dict[str, Any]:
    return asdict(metadata)


def write_evaluation_cases_json(
    path: Path,
    cases: list[CollaborativeAuditCase],
) -> None:
    path.write_text(
        json.dumps(serialize_evaluation_cases(cases), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_split_metadata_json(
    path: Path,
    metadata: CollaborativeAuditSplitMetadata,
) -> None:
    path.write_text(
        json.dumps(serialize_split_metadata(metadata), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_train_ratings_csv(
    path: Path,
    train_ratings: pd.DataFrame,
) -> None:
    train_ratings.to_csv(path, index=False, encoding="utf-8")


def _build_stand_case_for_user(
    *,
    user_id: int,
    user_ratings: pd.DataFrame,
    config: StandSimulationConfig,
    rng: random.Random,
) -> CollaborativeAuditCase | None:
    positives = user_ratings[user_ratings["rating"] >= 4.0].to_dict("records")
    negatives = user_ratings[user_ratings["rating"] <= 2.0].to_dict("records")

    if len(positives) < config.holdout_count + config.min_positive_ratings:
        return None

    rng.shuffle(positives)
    rng.shuffle(negatives)

    holdout_rows = positives[: config.holdout_count]
    remaining_positives = positives[config.holdout_count :]

    negative_target = 1 if negatives and config.input_count >= 4 else 0
    positive_target = config.input_count - negative_target

    if len(remaining_positives) < positive_target:
        return None

    input_rows = list(remaining_positives[:positive_target]) + list(negatives[:negative_target])
    rng.shuffle(input_rows)

    return CollaborativeAuditCase(
        case_id=f"stand-user-{user_id}",
        user_id=int(user_id),
        ratings=[
            CollaborativeUserRating(
                movie_id=int(row["movieId"]),
                rating=to_app_rating(float(row["rating"])),
            )
            for row in input_rows[: config.input_count]
        ],
        holdout_movie_ids=[int(row["movieId"]) for row in holdout_rows],
        holdout_ratings=[
            AuditHoldoutRating(
                movie_id=int(row["movieId"]),
                rating=float(row["rating"]),
            )
            for row in holdout_rows
        ],
        audit_mode="stand_simulation",
        candidate_universe="public_only",
    )


def _build_model_evaluation_case_for_user(
    *,
    user_id: int,
    user_ratings: pd.DataFrame,
    config: ModelEvaluationConfig,
    rng: random.Random,
) -> CollaborativeAuditCase | None:
    positives = user_ratings[user_ratings["rating"] >= 4.0].to_dict("records")
    negatives = user_ratings[user_ratings["rating"] <= 2.0].to_dict("records")

    if len(positives) < config.input_positive_count + config.holdout_count:
        return None

    rng.shuffle(positives)
    rng.shuffle(negatives)

    holdout_rows = positives[: config.holdout_count]
    remaining_positives = positives[config.holdout_count :]

    input_positive_rows = remaining_positives[: config.input_positive_count]
    input_negative_rows = negatives[: config.input_negative_count]

    if len(input_positive_rows) < config.input_positive_count:
        return None

    input_rows = list(input_positive_rows) + list(input_negative_rows)
    rng.shuffle(input_rows)

    return CollaborativeAuditCase(
        case_id=f"model-eval-user-{user_id}",
        user_id=int(user_id),
        ratings=[
            CollaborativeUserRating(
                movie_id=int(row["movieId"]),
                rating=to_app_rating(float(row["rating"])),
            )
            for row in input_rows
        ],
        holdout_movie_ids=[int(row["movieId"]) for row in holdout_rows],
        holdout_ratings=[
            AuditHoldoutRating(
                movie_id=int(row["movieId"]),
                rating=float(row["rating"]),
            )
            for row in holdout_rows
        ],
        audit_mode="model_evaluation",
        candidate_universe="public_plus_support",
    )


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["stand_simulation", "model_evaluation"],
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case-count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--write-train-ratings", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "stand_simulation":
        result = create_stand_simulation_split(
            config=StandSimulationConfig(
                case_count=args.case_count,
                seed=args.seed,
            )
        )
    else:
        result = create_model_evaluation_split(
            config=ModelEvaluationConfig(
                case_count=args.case_count,
                seed=args.seed,
            )
        )

    write_evaluation_cases_json(output_dir / "evaluation_cases.json", result.evaluation_cases)
    write_split_metadata_json(output_dir / "split_metadata.json", result.metadata)

    if args.write_train_ratings:
        write_train_ratings_csv(output_dir / "train_ratings.csv", result.train_ratings)


if __name__ == "__main__":
    main()
