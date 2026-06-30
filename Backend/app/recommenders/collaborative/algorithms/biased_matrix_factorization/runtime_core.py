from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BmfUsableRating:
    movie_id: int
    movie_index: int
    rating: float


@dataclass(frozen=True)
class BmfSessionProfile:
    session_bias: float
    session_factors: np.ndarray
    usable_rating_count: int
    ignored_unknown_rated_movies: int


@dataclass(frozen=True)
class BmfCandidatePrediction:
    movie_id: int
    movie_index: int
    raw_prediction: float
    predicted_rating: float
    ranking_score: float
    scoring_mode: str
    movie_bias: float
    latent_affinity: float


@dataclass(frozen=True)
class BmfScoringResult:
    candidates: list[BmfCandidatePrediction]
    raw_candidate_count: int
    filtered_low_score_candidates: int


def build_usable_ratings(
    *,
    ratings_by_movie_id: dict[int, float],
    movie_id_to_index: dict[int, int],
) -> tuple[list[BmfUsableRating], int]:
    usable_ratings: list[BmfUsableRating] = []
    ignored_unknown_rated_movies = 0

    for movie_id, rating in ratings_by_movie_id.items():
        movie_index = movie_id_to_index.get(movie_id)
        if movie_index is None:
            ignored_unknown_rated_movies += 1
            continue

        usable_ratings.append(
            BmfUsableRating(
                movie_id=movie_id,
                movie_index=movie_index,
                rating=float(rating),
            )
        )

    return usable_ratings, ignored_unknown_rated_movies


def infer_session_profile(
    *,
    usable_ratings: list[BmfUsableRating],
    movie_factors: np.ndarray,
    movie_biases: np.ndarray,
    global_mean: float,
    factor_count: int,
    session_inference_steps: int,
    session_learning_rate: float,
    session_regularization: float,
) -> BmfSessionProfile:
    session_bias = 0.0
    session_factors = np.zeros(factor_count, dtype=np.float32)

    if not usable_ratings:
        return BmfSessionProfile(
            session_bias=session_bias,
            session_factors=session_factors,
            usable_rating_count=0,
            ignored_unknown_rated_movies=0,
        )

    for _ in range(session_inference_steps):
        for usable_rating in usable_ratings:
            movie_index = usable_rating.movie_index
            movie_factor = movie_factors[movie_index]
            movie_bias = float(movie_biases[movie_index])

            latent_affinity = float(np.dot(session_factors, movie_factor))
            prediction = global_mean + session_bias + movie_bias + latent_affinity
            error = usable_rating.rating - prediction

            session_bias += session_learning_rate * (
                error - session_regularization * session_bias
            )

            session_factors += session_learning_rate * (
                error * movie_factor
                - session_regularization * session_factors
            )

    return BmfSessionProfile(
        session_bias=float(session_bias),
        session_factors=session_factors,
        usable_rating_count=len(usable_ratings),
        ignored_unknown_rated_movies=0,
    )


def score_candidate_movies(
    *,
    candidate_movie_ids: np.ndarray,
    candidate_movie_indices: np.ndarray,
    rated_movie_ids: set[int],
    movie_factors: np.ndarray,
    movie_biases: np.ndarray,
    session_profile: BmfSessionProfile,
    global_mean: float,
    rating_min: float,
    rating_max: float,
    min_prediction_score: float,
    scoring_mode: str,
    movie_bias_weight: float,
    limit: int,
) -> BmfScoringResult:
    if scoring_mode not in {
        "predicted_rating",
        "personalized_lift",
        "latent_affinity",
        "hybrid_personalized_bias",
    }:
        raise ValueError(f"Unsupported BMF scoring mode: {scoring_mode}")

    if limit <= 0:
        return BmfScoringResult(
            candidates=[],
            raw_candidate_count=0,
            filtered_low_score_candidates=0,
        )

    if candidate_movie_ids.shape[0] != candidate_movie_indices.shape[0]:
        raise ValueError(
            "candidate_movie_ids and candidate_movie_indices must have same length."
        )

    if candidate_movie_indices.shape[0] == 0:
        return BmfScoringResult(
            candidates=[],
            raw_candidate_count=0,
            filtered_low_score_candidates=0,
        )

    candidate_movie_factors = movie_factors[candidate_movie_indices]
    candidate_movie_biases = movie_biases[candidate_movie_indices]

    raw_predictions = (
        global_mean
        + session_profile.session_bias
        + candidate_movie_biases
        + candidate_movie_factors @ session_profile.session_factors
    )
    clipped_predictions = np.clip(raw_predictions, rating_min, rating_max)

    candidates: list[BmfCandidatePrediction] = []
    raw_candidate_count = 0
    filtered_low_score_candidates = 0

    for position, movie_id_value in enumerate(candidate_movie_ids):
        movie_id = int(movie_id_value)
        if movie_id in rated_movie_ids:
            continue

        raw_candidate_count += 1

        raw_prediction = float(raw_predictions[position])
        predicted_rating = float(clipped_predictions[position])
        if predicted_rating <= min_prediction_score:
            filtered_low_score_candidates += 1
            continue

        movie_index = int(candidate_movie_indices[position])
        movie_factor = movie_factors[movie_index]
        latent_affinity = float(np.dot(session_profile.session_factors, movie_factor))
        movie_bias = float(movie_biases[movie_index])
        personalized_lift = raw_prediction - global_mean - movie_bias

        if scoring_mode == "predicted_rating":
            ranking_score = predicted_rating
        elif scoring_mode == "personalized_lift":
            ranking_score = personalized_lift
        elif scoring_mode == "latent_affinity":
            ranking_score = latent_affinity
        elif scoring_mode == "hybrid_personalized_bias":
            ranking_score = latent_affinity + movie_bias_weight * movie_bias
        candidates.append(
            BmfCandidatePrediction(
                movie_id=movie_id,
                movie_index=movie_index,
                raw_prediction=raw_prediction,
                predicted_rating=predicted_rating,
                ranking_score=ranking_score,
                scoring_mode=scoring_mode,
                movie_bias=movie_bias,
                latent_affinity=latent_affinity,
            )
        )

    candidates.sort(
        key=lambda candidate: (
            candidate.ranking_score,
            candidate.predicted_rating,
            candidate.raw_prediction,
            -candidate.movie_id,
        ),
        reverse=True,
    )

    return BmfScoringResult(
        candidates=candidates[:limit],
        raw_candidate_count=raw_candidate_count,
        filtered_low_score_candidates=filtered_low_score_candidates,
    )
