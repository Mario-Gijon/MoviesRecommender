from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    DEFAULT_DIVERSIFIED_LIMIT,
    DEFAULT_TEMPLATE_SESSION_ID,
    MAX_DIVERSIFIED_LIMIT,
    MAX_RATING,
    MINIMUM_REQUIRED_NON_NEUTRAL_RATINGS,
    MIN_RATING,
    NEUTRAL_RATING,
    RECOMMENDED_MINIMUM_RATINGS,
)
from .diversification import rank_diversified_recommendations
from .explanations import explain_diversified_recommendations
from .index_loader import load_content_index
from .schemas import (
    ContentRecommendationItem,
    ContentRecommendationProfileSummary,
    ContentRecommendationRequest,
    ContentRecommendationResponse,
    TemporaryMovieRating,
    UserMovieRating,
)
from .user_profile import build_user_profile, build_user_profile_summary


@dataclass(frozen=True)
class ContentRecommendationDomainError(RuntimeError):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def recommend_content_based_movies(
    request: ContentRecommendationRequest,
) -> ContentRecommendationResponse:
    content_index = load_content_index()
    validated_ratings = _validate_request(request, content_index=content_index)
    user_ratings = [UserMovieRating(movieId=item.movieId, rating=int(item.rating)) for item in validated_ratings]
    non_neutral_rating_count = sum(1 for item in user_ratings if item.rating != NEUTRAL_RATING)

    if non_neutral_rating_count < MINIMUM_REQUIRED_NON_NEUTRAL_RATINGS:
        raise ContentRecommendationDomainError(
            code="insufficient_non_neutral_ratings",
            message=(
                "At least 3 non-neutral ratings are required to get recommendations."
            ),
        )

    try:
        profile = build_user_profile(content_index=content_index, ratings=user_ratings)
    except RuntimeError as exc:
        message = str(exc)
        code = "empty_user_profile" if "non-neutral" in message.lower() else "invalid_request"
        raise ContentRecommendationDomainError(code=code, message=message) from exc

    profile_summary = build_user_profile_summary(
        content_index=content_index,
        ratings=user_ratings,
        profile=profile,
    )
    template_session_id = request.templateSessionId or DEFAULT_TEMPLATE_SESSION_ID
    diversified_candidates = rank_diversified_recommendations(
        content_index=content_index,
        user_profile=profile,
        limit=request.limit,
    )
    if not diversified_candidates:
        raise ContentRecommendationDomainError(
            code="no_recommendations_available",
            message="No recommendations are available for the provided ratings.",
        )

    explained_recommendations = explain_diversified_recommendations(
        content_index=content_index,
        user_profile=profile,
        diversified_candidates=diversified_candidates,
        limit=request.limit,
        template_session_id=template_session_id,
    )

    recommendation_items = [
        _build_recommendation_item(
            recommendation=item,
            movie_metadata=content_index.movies[content_index.movieIdToRowIndex[item.movieId]],
        )
        for item in explained_recommendations
    ]

    return ContentRecommendationResponse(
        profile=ContentRecommendationProfileSummary(
            style=profile_summary.style,
            headline=profile_summary.headline,
            ratedMovieCount=profile.ratedMovieCount,
            nonNeutralRatingCount=non_neutral_rating_count,
            positiveRatingCount=profile.positiveRatingCount,
            negativeRatingCount=profile.negativeRatingCount,
            minimumRequiredRatings=MINIMUM_REQUIRED_NON_NEUTRAL_RATINGS,
            recommendedMinimumRatings=RECOMMENDED_MINIMUM_RATINGS,
            confidence=_confidence_for_count(non_neutral_rating_count),
            positiveSignals=profile.positiveSignals,
            negativeSignals=profile.negativeSignals,
        ),
        recommendations=recommendation_items,
        templateSessionId=template_session_id,
        limit=request.limit,
    )


def _validate_request(
    request: ContentRecommendationRequest,
    *,
    content_index,
) -> list[TemporaryMovieRating]:
    if not request.ratings:
        raise ContentRecommendationDomainError(
            code="empty_ratings",
            message="At least one rating is required.",
        )
    if request.limit < 1 or request.limit > MAX_DIVERSIFIED_LIMIT:
        raise ContentRecommendationDomainError(
            code="invalid_limit",
            message=f"limit must be between 1 and {MAX_DIVERSIFIED_LIMIT}.",
        )

    seen_movie_ids: set[int] = set()
    validated: list[TemporaryMovieRating] = []
    for item in request.ratings:
        if item.movieId in seen_movie_ids:
            raise ContentRecommendationDomainError(
                code="duplicate_rating_movie",
                message=f"Duplicate rating for movieId {item.movieId}.",
            )
        if item.movieId not in content_index.movieIdToRowIndex:
            raise ContentRecommendationDomainError(
                code="unknown_public_movie",
                message=f"movieId {item.movieId} does not exist in the public content index.",
            )
        if not isinstance(item.rating, (int, float)):
            raise ContentRecommendationDomainError(
                code="invalid_rating_value",
                message=f"Rating for movieId {item.movieId} must be numeric between 1 and 5.",
            )
        numeric_rating = float(item.rating)
        if numeric_rating < MIN_RATING or numeric_rating > MAX_RATING or not numeric_rating.is_integer():
            raise ContentRecommendationDomainError(
                code="invalid_rating_value",
                message=f"Rating for movieId {item.movieId} must be an integer between 1 and 5.",
            )
        seen_movie_ids.add(item.movieId)
        validated.append(TemporaryMovieRating(movieId=item.movieId, rating=int(numeric_rating)))
    return validated


def _confidence_for_count(non_neutral_rating_count: int) -> str:
    if non_neutral_rating_count < 5:
        return "low"
    if non_neutral_rating_count < 8:
        return "medium"
    return "high"


def _build_recommendation_item(*, recommendation, movie_metadata: dict) -> ContentRecommendationItem:
    tmdb_id = movie_metadata.get("tmdbId")
    return ContentRecommendationItem(
        movieId=recommendation.movieId,
        displayTitle=recommendation.displayTitle,
        year=recommendation.year,
        genres=recommendation.genres,
        suitabilityCategory=recommendation.suitabilityCategory,
        standDisplayScore=recommendation.standDisplayScore,
        recommendationScore=recommendation.recommendationScore,
        contentSimilarity=recommendation.contentSimilarity,
        mmrScore=recommendation.mmrScore,
        explanation=recommendation.explanation,
        posterPath=_optional_text(movie_metadata.get("posterPath")),
        tmdbId=int(tmdb_id) if tmdb_id not in (None, "", "null") else None,
        originalTitle=_optional_text(movie_metadata.get("originalTitle")),
        originalLanguage=_optional_text(movie_metadata.get("originalLanguage")),
        overview=_optional_text(movie_metadata.get("overview")),
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
