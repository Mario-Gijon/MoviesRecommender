from collections import Counter

from app.domain.movies.movie_schemas import Movie
from app.domain.recommendations.recommendation_schemas import (
    ExplanationSignal,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationExplanation,
    UserProfile,
)
from app.infrastructure.catalog.catalog_repository import catalog_repository


METHOD_LABELS = {
    "content": "content-based placeholder",
    "collaborative": "collaborative placeholder",
    "hybrid": "hybrid placeholder",
}


def build_placeholder_response(payload: RecommendationRequest) -> RecommendationResponse:
    featured_movies = catalog_repository.get_featured_movies()
    featured_by_id = {movie["id"]: movie for movie in featured_movies}
    rated_movies = [featured_by_id[rating.movieId] for rating in payload.ratings if rating.movieId in featured_by_id]

    genre_counter: Counter[str] = Counter()
    for movie in rated_movies:
        genre_counter.update(movie["genres"])

    favorite_genres = [genre for genre, _count in genre_counter.most_common(3)]
    average_rating = round(
        sum(rating.rating for rating in payload.ratings) / len(payload.ratings),
        2,
    ) if payload.ratings else 0.0

    candidate_movies = [
        movie for movie in catalog_repository.get_recommendation_candidates()
        if movie["id"] not in {rating.movieId for rating in payload.ratings}
    ]

    recommendations = [
        _build_recommendation_item(
            movie=Movie.model_validate(movie),
            strategy=payload.strategy,
            favorite_genres=favorite_genres,
            index=index,
        )
        for index, movie in enumerate(candidate_movies[:3], start=1)
    ]

    return RecommendationResponse(
        strategy=payload.strategy,
        userProfile=UserProfile(
            ratedMoviesCount=len(payload.ratings),
            averageRating=average_rating,
            favoriteGenres=favorite_genres,
            selectedStrategy=payload.strategy,
        ),
        recommendations=recommendations,
        explanation=RecommendationExplanation(
            summary=(
                f"This placeholder {payload.strategy} strategy uses your temporary ratings "
                "and genre overlap to produce deterministic demo recommendations."
            ),
            transparencyNotes=[
                "No live external APIs are used.",
                "The ranking is deterministic placeholder data for local demos.",
                "Real content, collaborative, and hybrid logic will be added later.",
            ],
        ),
    )


def _build_recommendation_item(
    movie: Movie,
    strategy: str,
    favorite_genres: list[str],
    index: int,
) -> RecommendationItem:
    shared_genres = [genre for genre in movie.genres if genre in favorite_genres]
    match_percentage = max(60, 90 - (index - 1) * 8)

    return RecommendationItem(
        movie=movie,
        score=round(0.96 - (index - 1) * 0.07, 2),
        matchPercentage=match_percentage,
        method=METHOD_LABELS[strategy],
        explanationSummary=(
            f"{movie.title} is surfaced because it overlaps with your rated preferences "
            f"through {', '.join(shared_genres or movie.genres[:2])}."
        ),
        explanationSignals=[
            ExplanationSignal(
                label="Shared genres",
                value=", ".join(shared_genres or movie.genres[:2]),
            ),
            ExplanationSignal(
                label="Strategy",
                value=strategy,
            ),
            ExplanationSignal(
                label="Availability",
                value=(
                    "content + collaborative"
                    if movie.availableForContent and movie.availableForCollaborative
                    else "single-source placeholder"
                ),
            ),
        ],
    )

