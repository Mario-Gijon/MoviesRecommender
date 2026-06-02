from collections import Counter

from app.domain.movies.movie_schemas import Movie
from app.domain.recommendations.recommendation_schemas import (
    ExplanationSignal,
    MethodContribution,
    RecommendationItem,
    RecommendationExplanation,
    RecommendationRequest,
    RecommendationResponse,
    UserProfile,
)
from app.infrastructure.catalog.catalog_repository import catalog_repository


STRATEGY_EXPLANATIONS = {
    "content": "Recommended because it shares tags such as {tags} with movies you rated highly.",
    "collaborative": "Recommended because users with similar placeholder tastes would likely rate it highly.",
    "hybrid": "Recommended by combining content matches with collaborative-style evidence.",
}


def build_placeholder_response(payload: RecommendationRequest) -> RecommendationResponse:
    featured_movies = catalog_repository.get_featured_movies()
    featured_by_id = {movie["id"]: movie for movie in featured_movies}
    rated_movies = [
        featured_by_id[rating.movieId]
        for rating in payload.ratings
        if rating.movieId in featured_by_id
    ]
    positive_rated_movies = [
        featured_by_id[rating.movieId]
        for rating in payload.ratings
        if rating.rating >= 4 and rating.movieId in featured_by_id
    ]

    genre_counter: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()
    for movie in positive_rated_movies or rated_movies:
        genre_counter.update(movie["genres"])
        tag_counter.update(movie["tags"])

    favorite_genres = [genre for genre, _count in genre_counter.most_common(3)]
    favorite_tags = [tag for tag, _count in tag_counter.most_common(4)]
    average_rating = round(
        sum(rating.rating for rating in payload.ratings) / len(payload.ratings),
        2,
    ) if payload.ratings else 0.0
    rated_movie_ids = {rating.movieId for rating in payload.ratings}

    candidate_movies = [
        movie for movie in catalog_repository.get_recommendation_candidates()
        if movie["id"] not in rated_movie_ids
    ]

    recommendations = [
        _build_recommendation_item(
            movie=Movie.model_validate(movie),
            strategy=payload.strategy,
            favorite_genres=favorite_genres,
            favorite_tags=favorite_tags,
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
            favoriteTags=favorite_tags,
            selectedStrategy=payload.strategy,
        ),
        recommendations=recommendations,
        explanation=RecommendationExplanation(
            summary=(
                f"This {payload.strategy} demo combines a temporary taste profile with "
                "deterministic placeholder evidence to explain each recommendation."
            ),
            transparencyNotes=[
                "No live external APIs are used.",
                "The ranking is deterministic placeholder data for local demos.",
                "Coverage flags reflect which future recommendation methods could use each title.",
                "Real content, collaborative, and hybrid logic will be added later.",
            ],
        ),
    )


def _build_recommendation_item(
    movie: Movie,
    strategy: str,
    favorite_genres: list[str],
    favorite_tags: list[str],
    index: int,
) -> RecommendationItem:
    shared_genres = [genre for genre in movie.genres if genre in favorite_genres]
    shared_tags = [tag for tag in movie.tags if tag in favorite_tags]
    match_percentage = max(60, 90 - (index - 1) * 8)
    explanation_summary = _build_explanation_summary(strategy, shared_tags, movie.tags)
    method_contributions = _build_method_contributions(strategy, movie, index)
    quality_weight = round(0.52 - (index - 1) * 0.04, 2)

    return RecommendationItem(
        movie=movie,
        score=round(0.96 - (index - 1) * 0.07, 2),
        matchPercentage=match_percentage,
        method=strategy,
        methodContributions=method_contributions,
        explanationSummary=explanation_summary,
        explanationSignals=[
            ExplanationSignal(
                type="content_match",
                label="Shared genres",
                value=", ".join(shared_genres or movie.genres[:2]),
                weight=0.62 if strategy != "collaborative" else 0.18,
            ),
            ExplanationSignal(
                type="content_match" if strategy != "collaborative" else "collaborative_match",
                label="Shared tags",
                value=", ".join(shared_tags or movie.tags[:3]),
                weight=0.68 if strategy != "collaborative" else 0.24,
            ),
            ExplanationSignal(
                type="collaborative_match" if strategy != "content" else "quality_signal",
                label="Strategy",
                value=strategy,
                weight=0.7 if strategy == "collaborative" else 0.5 if strategy == "hybrid" else None,
            ),
            ExplanationSignal(
                type="coverage_note",
                label="Availability",
                value=", ".join(movie.coverage.coverageNotes),
                weight=None,
            ),
            ExplanationSignal(
                type="quality_signal",
                label="Catalog quality signal",
                value=f"Coverage {int(max(movie.coverage.contentCoverage, movie.coverage.collaborativeCoverage) * 100)}%",
                weight=quality_weight,
            ),
        ],
    )


def _build_explanation_summary(strategy: str, shared_tags: list[str], movie_tags: list[str]) -> str:
    if strategy == "content":
        tags_text = ", ".join(shared_tags or movie_tags[:2])
        return STRATEGY_EXPLANATIONS[strategy].format(tags=tags_text)
    return STRATEGY_EXPLANATIONS[strategy]


def _build_method_contributions(strategy: str, movie: Movie, index: int) -> list[MethodContribution]:
    content_score = round(0.88 - (index - 1) * 0.05, 2)
    collaborative_score = round(0.84 - (index - 1) * 0.05, 2)
    popularity_score = round(0.7 - (index - 1) * 0.03, 2)
    diversity_score = round(0.66 - (index - 1) * 0.02, 2)

    if strategy == "content":
        return [
            MethodContribution(
                method="content",
                weight=0.7,
                score=content_score,
                label="Tag and genre overlap",
            ),
            MethodContribution(
                method="popularity",
                weight=0.2,
                score=popularity_score,
                label="Stable demo ranking signal",
            ),
            MethodContribution(
                method="diversity",
                weight=0.1,
                score=diversity_score,
                label="Keeps the list varied",
            ),
        ]

    if strategy == "collaborative":
        return [
            MethodContribution(
                method="collaborative",
                weight=0.7,
                score=collaborative_score,
                label="Similar placeholder users",
            ),
            MethodContribution(
                method="popularity",
                weight=0.2,
                score=popularity_score,
                label="Stable demo ranking signal",
            ),
            MethodContribution(
                method="diversity",
                weight=0.1,
                score=diversity_score,
                label="Keeps the list varied",
            ),
        ]

    return [
        MethodContribution(
            method="content",
            weight=0.45,
            score=content_score,
            label="Tag and genre overlap",
        ),
        MethodContribution(
            method="collaborative",
            weight=0.35,
            score=collaborative_score,
            label="Similar placeholder users",
        ),
        MethodContribution(
            method="popularity",
            weight=0.1,
            score=popularity_score,
            label="Stable demo ranking signal",
        ),
        MethodContribution(
            method="diversity",
            weight=0.1,
            score=diversity_score,
            label="Keeps the list varied",
        ),
    ]
