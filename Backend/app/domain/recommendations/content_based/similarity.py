from __future__ import annotations

from scipy.sparse import csr_matrix

from .constants import (
    DEFAULT_MATCHED_SIGNAL_LIMIT,
    DEFAULT_SIMILARITY_LIMIT,
    MAX_SIMILARITY_LIMIT,
    NON_EXPLAINABLE_SIGNAL_TOKENS,
)
from .feature_parsing import normalize_feature_token
from .schemas import ContentIndex, ContentSimilarityCandidate, UserProfile


VISIBLE_SIGNAL_PREFIXES = ("genre:", "tag:", "keyword:", "text:")


def rank_by_content_similarity(
    content_index: ContentIndex,
    user_profile: UserProfile,
    *,
    limit: int = DEFAULT_SIMILARITY_LIMIT,
) -> list[ContentSimilarityCandidate]:
    _validate_limit(limit)

    similarity_column = content_index.features.dot(user_profile.profileVector.transpose()).tocsr()
    candidate_rows: list[tuple[float, str, int, ContentSimilarityCandidate]] = []

    for row_index, similarity_value in zip(
        similarity_column.nonzero()[0].tolist(),
        similarity_column.data.tolist(),
    ):
        movie = content_index.movies[row_index]
        movie_id = int(movie["movieId"])
        if movie_id in user_profile.ratedMovieIds:
            continue

        candidate = ContentSimilarityCandidate(
            movieId=movie_id,
            displayTitle=str(movie.get("displayTitle", "")),
            year=_optional_int(movie.get("year")),
            suitabilityCategory=str(movie.get("suitabilityCategory", "")),
            standDisplayScore=float(movie.get("standDisplayScore", 0.0)),
            contentSimilarity=float(similarity_value),
            genres=list(movie.get("genres", [])),
            matchedSignals=_extract_matched_signals(
                user_positive_vector=user_profile.positiveVector,
                candidate_vector=content_index.features.getrow(row_index),
                feature_names=content_index.featureNames,
                limit=DEFAULT_MATCHED_SIGNAL_LIMIT,
            ),
        )
        candidate_rows.append(
            (
                candidate.contentSimilarity,
                candidate.displayTitle.casefold(),
                candidate.movieId,
                candidate,
            )
        )

    candidate_rows.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [item[3] for item in candidate_rows[:limit]]


def _extract_matched_signals(
    *,
    user_positive_vector: csr_matrix,
    candidate_vector: csr_matrix,
    feature_names: list[str],
    limit: int,
) -> list[str]:
    if user_positive_vector.nnz == 0 or candidate_vector.nnz == 0:
        return []

    overlap_vector = user_positive_vector.multiply(candidate_vector).tocsr()
    if overlap_vector.nnz == 0:
        return []

    weighted_features = sorted(
        zip(overlap_vector.indices.tolist(), overlap_vector.data.tolist()),
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


def _validate_limit(limit: int) -> None:
    if limit < 1:
        raise RuntimeError("Similarity limit must be at least 1.")
    if limit > MAX_SIMILARITY_LIMIT:
        raise RuntimeError(f"Similarity limit must be at most {MAX_SIMILARITY_LIMIT}.")


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
    normalized = normalize_feature_token(signal).replace("_", " ")
    return normalized in NON_EXPLAINABLE_SIGNAL_TOKENS


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return int(value)
