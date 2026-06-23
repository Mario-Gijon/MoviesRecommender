from app.catalog.catalog_repository import catalog_repository
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationExplanation,
    CollaborativeRecommendationRequest,
    CollaborativeRecommendationResult,
    CollaborativeRecommendedMovie,
    CollaborativeRecommenderDetails,
)


class PopularityBaselineRecommender:
    algorithm_id = "popularity_baseline"
    algorithm_label = "Popularity baseline"

    def recommend(
        self,
        request: CollaborativeRecommendationRequest,
    ) -> CollaborativeRecommendationResult:
        rated_movie_ids = {rating.movie_id for rating in request.ratings}
        candidates = [
            movie
            for movie in catalog_repository.get_recommendation_candidates()
            if int(movie["movieId"]) not in rated_movie_ids
        ]

        scored_candidates = [
            _score_movie(movie)
            for movie in candidates
            if _has_rating_signal(movie)
        ]
        scored_candidates.sort(key=lambda item: item["score"], reverse=True)

        recommendations = [
            CollaborativeRecommendedMovie(
                movie_id=int(item["movie"]["movieId"]),
                rank=rank,
                score=round(float(item["score"]), 6),
                explanation=_build_explanation(item["movie"]),
                algorithm_details={
                    "averageRating": item["averageRating"],
                    "ratingCount": item["ratingCount"],
                    "weightedRating": round(float(item["score"]), 6),
                    "standDisplayScore": item["standDisplayScore"],
                },
            )
            for rank, item in enumerate(scored_candidates[: request.limit], start=1)
        ]

        return CollaborativeRecommendationResult(
            recommendations=recommendations,
            recommender_details=CollaborativeRecommenderDetails(
                algorithm_id=self.algorithm_id,
                algorithm_label=self.algorithm_label,
                is_personalized=False,
                is_explainable=True,
                status="ready",
                details={
                    "rankingSignal": "weighted_rating_popularity",
                    "excludedRatedMovies": len(rated_movie_ids),
                },
            ),
            limit=request.limit,
            template_session_id=request.template_session_id,
        )


def _has_rating_signal(movie: dict) -> bool:
    rating_count = _rating_count(movie)
    average_rating = _average_rating(movie)
    return rating_count > 0 and average_rating > 0


def _score_movie(movie: dict) -> dict:
    rating_count = _rating_count(movie)
    average_rating = _average_rating(movie)
    stand_display_score = _float_value(movie.get("standDisplayScore"))
    confidence = rating_count / (rating_count + 250)
    weighted_rating = average_rating * confidence
    normalized_stand_score = stand_display_score / 100 if stand_display_score > 1 else stand_display_score
    score = weighted_rating * 0.85 + normalized_stand_score * 0.15

    return {
        "movie": movie,
        "score": score,
        "averageRating": average_rating,
        "ratingCount": rating_count,
        "standDisplayScore": stand_display_score,
    }


def _build_explanation(movie: dict) -> CollaborativeRecommendationExplanation:
    rating_count = _rating_count(movie)
    average_rating = _average_rating(movie)

    return CollaborativeRecommendationExplanation(
        headline="Es una recomendación sólida según las valoraciones de la comunidad.",
        reasons=[
            f"Tiene una valoración media de {average_rating:.2f} sobre 5.",
            f"La puntuación está respaldada por {rating_count} valoraciones.",
        ],
        evidence=[
            "Baseline no personalizado basado en popularidad y calidad agregada.",
        ],
    )


def _rating_count(movie: dict) -> int:
    filtered_rating_count = movie.get("filteredRatingCount")
    rating_count = movie.get("ratingCount")
    return int(filtered_rating_count or rating_count or 0)


def _average_rating(movie: dict) -> float:
    filtered_average_rating = movie.get("filteredAverageRating")
    average_rating = movie.get("averageRating")
    return _float_value(filtered_average_rating or average_rating)


def _float_value(value: object) -> float:
    if value is None:
        return 0.0
    return float(value)