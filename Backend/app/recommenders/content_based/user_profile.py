from __future__ import annotations

from collections import Counter

from scipy.sparse import csr_matrix
from sklearn.preprocessing import normalize

from .constants import (
    DEFAULT_PROFILE_SIGNAL_LIMIT,
    MAX_RATING,
    MIN_RATING,
    NEUTRAL_RATING,
    NON_EXPLAINABLE_SIGNAL_TOKENS,
    PROFILE_STYLE_SIGNAL_GROUPS,
)
from .feature_parsing import normalize_feature_token
from .models import ContentIndex, UserMovieRating, UserProfile, UserProfileSummary


VISIBLE_SIGNAL_PREFIXES = ("genre:", "tag:", "keyword:", "text:")


def build_user_profile(
    content_index: ContentIndex,
    ratings: list[UserMovieRating],
    *,
    signal_limit: int = DEFAULT_PROFILE_SIGNAL_LIMIT,
) -> UserProfile:
    validated_ratings = _validate_ratings(content_index=content_index, ratings=ratings)
    row_count, feature_count = content_index.features.shape
    del row_count

    profile_vector = csr_matrix((1, feature_count), dtype=content_index.features.dtype)
    positive_vector = csr_matrix((1, feature_count), dtype=content_index.features.dtype)
    negative_vector = csr_matrix((1, feature_count), dtype=content_index.features.dtype)

    rated_movie_ids: set[int] = set()
    positive_rated_movie_ids: set[int] = set()
    negative_rated_movie_ids: set[int] = set()
    neutral_rated_movie_ids: set[int] = set()

    for item in validated_ratings:
        weight = rating_to_weight(item.rating)
        rated_movie_ids.add(item.movieId)
        row_index = content_index.movieIdToRowIndex[item.movieId]
        movie_vector = content_index.features.getrow(row_index)

        if weight > 0:
            positive_vector = positive_vector + movie_vector.multiply(weight)
            profile_vector = profile_vector + movie_vector.multiply(weight)
            positive_rated_movie_ids.add(item.movieId)
        elif weight < 0:
            negative_weight = abs(weight)
            negative_vector = negative_vector + movie_vector.multiply(negative_weight)
            profile_vector = profile_vector - movie_vector.multiply(negative_weight)
            negative_rated_movie_ids.add(item.movieId)
        else:
            neutral_rated_movie_ids.add(item.movieId)

    if not positive_rated_movie_ids and not negative_rated_movie_ids:
        raise RuntimeError(
            "At least one non-neutral rating is required to build a recommendation profile."
        )

    profile_vector = _normalize_if_non_empty(profile_vector)
    positive_vector = _normalize_if_non_empty(positive_vector)
    negative_vector = _normalize_if_non_empty(negative_vector)

    positive_signals = extract_profile_signals(
        vector=positive_vector,
        feature_names=content_index.featureNames,
        limit=signal_limit,
    )
    negative_signals = extract_profile_signals(
        vector=negative_vector,
        feature_names=content_index.featureNames,
        limit=signal_limit,
    )
    style = detect_profile_style(
        content_index=content_index,
        positive_rated_movie_ids=positive_rated_movie_ids,
        positive_signals=positive_signals,
    )

    return UserProfile(
        profileVector=profile_vector,
        positiveVector=positive_vector,
        negativeVector=negative_vector,
        ratedMovieIds=rated_movie_ids,
        positiveRatedMovieIds=positive_rated_movie_ids,
        negativeRatedMovieIds=negative_rated_movie_ids,
        neutralRatedMovieIds=neutral_rated_movie_ids,
        positiveSignals=positive_signals,
        negativeSignals=negative_signals,
        style=style,
        ratedMovieCount=len(rated_movie_ids),
        positiveRatingCount=len(positive_rated_movie_ids),
        negativeRatingCount=len(negative_rated_movie_ids),
        neutralRatingCount=len(neutral_rated_movie_ids),
    )


def build_user_profile_summary(
    *,
    content_index: ContentIndex,
    ratings: list[UserMovieRating],
    profile: UserProfile,
) -> UserProfileSummary:
    positive_rated_movies = _movie_titles_for_ids(
        ratings=ratings,
        target_ids=profile.positiveRatedMovieIds,
        content_index=content_index,
    )
    negative_rated_movies = _movie_titles_for_ids(
        ratings=ratings,
        target_ids=profile.negativeRatedMovieIds,
        content_index=content_index,
    )
    neutral_rated_movies = _movie_titles_for_ids(
        ratings=ratings,
        target_ids=profile.neutralRatedMovieIds,
        content_index=content_index,
    )

    return UserProfileSummary(
        style=profile.style,
        headline=_headline_for_style(profile.style),
        positiveSignals=profile.positiveSignals,
        negativeSignals=profile.negativeSignals,
        ratedMovieCount=profile.ratedMovieCount,
        positiveRatingCount=profile.positiveRatingCount,
        negativeRatingCount=profile.negativeRatingCount,
        neutralRatingCount=profile.neutralRatingCount,
        positiveRatedMovies=positive_rated_movies,
        negativeRatedMovies=negative_rated_movies,
        neutralRatedMovies=neutral_rated_movies,
    )


def rating_to_weight(rating: float) -> float:
    return (rating - NEUTRAL_RATING) / 2.0


def extract_profile_signals(
    *,
    vector: csr_matrix,
    feature_names: list[str],
    limit: int,
) -> list[str]:
    if vector.nnz == 0:
        return []

    row = vector.getrow(0)
    weighted_features = sorted(
        zip(row.indices.tolist(), row.data.tolist()),
        key=lambda item: item[1],
        reverse=True,
    )

    preferred: list[str] = []
    fallback: list[str] = []
    seen: set[str] = set()

    for feature_index, score in weighted_features:
        if score <= 0:
            continue
        feature_name = feature_names[feature_index]
        if not feature_name.startswith(VISIBLE_SIGNAL_PREFIXES):
            continue
        readable_signal = _to_readable_signal(feature_name)
        if not readable_signal or readable_signal in seen:
            continue
        seen.add(readable_signal)
        if _is_non_explainable_signal(readable_signal):
            fallback.append(readable_signal)
        else:
            preferred.append(readable_signal)
        if len(preferred) >= limit:
            break

    combined = preferred[:limit]
    if len(combined) < limit:
        combined.extend(fallback[: limit - len(combined)])
    return combined


def detect_profile_style(
    *,
    content_index: ContentIndex,
    positive_rated_movie_ids: set[int],
    positive_signals: list[str],
) -> str:
    style_counts = Counter({"family": 0, "teen": 0})

    for movie_id in positive_rated_movie_ids:
        movie = content_index.movies[content_index.movieIdToRowIndex[movie_id]]
        suitability_token = _normalize_visible_signal(movie.get("suitabilityCategory"))
        if suitability_token == "family friendly":
            style_counts["family"] += 2
        if suitability_token == "teen":
            style_counts["teen"] += 2
        for genre in movie.get("genres", []):
            normalized_genre = _normalize_visible_signal(genre)
            if normalized_genre in PROFILE_STYLE_SIGNAL_GROUPS["family"]:
                style_counts["family"] += 1
            if normalized_genre in PROFILE_STYLE_SIGNAL_GROUPS["teen"]:
                style_counts["teen"] += 1

    for signal in positive_signals:
        normalized_signal = _normalize_visible_signal(signal)
        if normalized_signal in PROFILE_STYLE_SIGNAL_GROUPS["family"]:
            style_counts["family"] += 1
        if normalized_signal in PROFILE_STYLE_SIGNAL_GROUPS["teen"]:
            style_counts["teen"] += 1

    if style_counts["family"] >= max(3, style_counts["teen"] + 1):
        return "family"
    if style_counts["teen"] >= max(3, style_counts["family"] + 1):
        return "teen"
    return "mixed"


def _validate_ratings(
    *,
    content_index: ContentIndex,
    ratings: list[UserMovieRating],
) -> list[UserMovieRating]:
    if not ratings:
        raise RuntimeError("At least one rating is required to build a recommendation profile.")

    seen_movie_ids: set[int] = set()
    validated: list[UserMovieRating] = []
    for item in ratings:
        if item.movieId in seen_movie_ids:
            raise RuntimeError(f"Duplicate movieId in ratings: {item.movieId}")
        if item.movieId not in content_index.movieIdToRowIndex:
            raise RuntimeError(f"movieId {item.movieId} does not exist in the public content index.")
        if not isinstance(item.rating, (int, float)):
            raise RuntimeError(
                f"Rating for movieId {item.movieId} must be numeric from 1 to 5."
            )
        if not MIN_RATING <= item.rating <= MAX_RATING:
            raise RuntimeError(f"Rating for movieId {item.movieId} must be between 1 and 5.")
        seen_movie_ids.add(item.movieId)
        validated.append(item)
    return validated


def _normalize_if_non_empty(vector: csr_matrix) -> csr_matrix:
    if vector.nnz == 0:
        return vector
    return normalize(vector, norm="l2", axis=1, copy=False)


def _to_readable_signal(feature_name: str) -> str:
    for prefix in VISIBLE_SIGNAL_PREFIXES:
        if not feature_name.startswith(prefix):
            continue
        signal = feature_name[len(prefix) :]
        signal = signal.replace("_", " ").strip()
        signal = signal.replace('"', "")
        signal = signal.replace("  ", " ")
        return signal
    return ""


def _is_non_explainable_signal(signal: str) -> bool:
    return _normalize_visible_signal(signal) in NON_EXPLAINABLE_SIGNAL_TOKENS


def _normalize_visible_signal(signal: object) -> str:
    if signal is None:
        return ""
    normalized = normalize_feature_token(str(signal))
    return normalized.replace("_", " ")


def _headline_for_style(style: str) -> str:
    if style == "family":
        return "Parece que te van las peliculas visuales, familiares y con aventura."
    if style == "teen":
        return "Parece que te van las peliculas con accion, fantasia o ciencia ficcion."
    return "Parece que tienes gustos variados, asi que buscaremos una mezcla equilibrada."


def _movie_titles_for_ids(
    *,
    ratings: list[UserMovieRating],
    target_ids: set[int],
    content_index: ContentIndex,
) -> list[str]:
    titles: list[str] = []
    for item in ratings:
        if item.movieId not in target_ids:
            continue
        movie = content_index.movies[content_index.movieIdToRowIndex[item.movieId]]
        titles.append(str(movie.get("displayTitle", item.movieId)))
    return titles
