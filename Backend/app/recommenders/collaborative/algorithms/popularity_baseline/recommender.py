from pathlib import Path

from app.recommenders.collaborative.algorithms.popularity_baseline.models import (
    ALGORITHM_ID,
    ALGORITHM_LABEL,
    PopularityRankingEntry,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.storage import (
    load_popularity_baseline_manifest,
    load_popularity_ranking,
)
from app.recommenders.collaborative.common.errors import CollaborativeModelArtifactError
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationExplanation,
    CollaborativeRecommendationRequest,
    CollaborativeRecommendationResult,
    CollaborativeRecommendedMovie,
    CollaborativeRecommenderDetails,
)


class PopularityBaselineRecommender:
    algorithm_id = ALGORITHM_ID
    algorithm_label = ALGORITHM_LABEL

    def __init__(self, *, artifact_root: Path | None = None) -> None:
        self._artifact_root = artifact_root
        self._ranking: list[PopularityRankingEntry] | None = None
        self._manifest: dict | None = None

    def recommend(
        self,
        request: CollaborativeRecommendationRequest,
    ) -> CollaborativeRecommendationResult:
        rated_movie_ids = {rating.movie_id for rating in request.ratings}

        recommendations = self.recommend_fillers(
            rated_movie_ids=rated_movie_ids,
            excluded_movie_ids=set(),
            limit=request.limit,
            start_rank=1,
            fallback=False,
        )

        manifest = self._load_manifest()

        return CollaborativeRecommendationResult(
            recommendations=recommendations,
            recommender_details=CollaborativeRecommenderDetails(
                algorithm_id=self.algorithm_id,
                algorithm_label=self.algorithm_label,
                is_personalized=False,
                is_explainable=True,
                status="ready",
                model_version=manifest.get("modelVersion"),
                details={
                    "rankingSignal": "weighted_rating_popularity",
                    "rankingSource": "precomputed_popularity_ranking",
                    "excludedRatedMovies": len(rated_movie_ids),
                },
            ),
            limit=request.limit,
            template_session_id=request.template_session_id,
        )

    def recommend_fillers(
        self,
        *,
        rated_movie_ids: set[int],
        excluded_movie_ids: set[int],
        limit: int,
        start_rank: int,
        fallback: bool = True,
    ) -> list[CollaborativeRecommendedMovie]:
        if limit <= 0:
            return []

        recommendations: list[CollaborativeRecommendedMovie] = []

        for entry in self._load_ranking():
            if entry.movie_id in rated_movie_ids:
                continue

            if entry.movie_id in excluded_movie_ids:
                continue

            recommendations.append(
                CollaborativeRecommendedMovie(
                    movie_id=entry.movie_id,
                    rank=start_rank + len(recommendations),
                    score=round(entry.score, 6),
                    explanation=(
                        _build_fallback_explanation(entry)
                        if fallback
                        else _build_explanation(entry)
                    ),
                    algorithm_details={
                        "averageRating": entry.average_rating,
                        "ratingCount": entry.rating_count,
                        "weightedRating": round(entry.score, 6),
                        "standDisplayScore": entry.stand_display_score,
                        "rankingSource": "precomputed_popularity_ranking",
                        "fallback": fallback,
                        "fallbackAlgorithm": self.algorithm_id if fallback else None,
                    },
                )
            )

            if len(recommendations) >= limit:
                break

        return recommendations

    def _load_ranking(self) -> list[PopularityRankingEntry]:
        if self._ranking is None:
            try:
                self._ranking = load_popularity_ranking(
                    artifact_root=self._artifact_root
                )
            except RuntimeError as exc:
                raise CollaborativeModelArtifactError(
                    code="popularity_baseline_ranking_missing",
                    message=str(exc),
                ) from exc

        return self._ranking

    def _load_manifest(self) -> dict:
        if self._manifest is None:
            try:
                self._manifest = load_popularity_baseline_manifest(
                    artifact_root=self._artifact_root
                )
            except RuntimeError as exc:
                raise CollaborativeModelArtifactError(
                    code="popularity_baseline_manifest_missing",
                    message=str(exc),
                ) from exc

        return self._manifest


def _build_explanation(
    entry: PopularityRankingEntry,
) -> CollaborativeRecommendationExplanation:
    return CollaborativeRecommendationExplanation(
        headline="Es una recomendación sólida según las valoraciones de la comunidad.",
        reasons=[
            f"Tiene una valoración media de {entry.average_rating:.2f} sobre 5.",
            f"La puntuación está respaldada por {entry.rating_count} valoraciones.",
        ],
        evidence=[
            "Baseline no personalizado basado en popularidad y calidad agregada.",
        ],
    )


def _build_fallback_explanation(
    entry: PopularityRankingEntry,
) -> CollaborativeRecommendationExplanation:
    return CollaborativeRecommendationExplanation(
        headline="Completamos la lista con una opción bien valorada por la comunidad.",
        reasons=[
            "No había suficientes coincidencias personalizadas para completar todas las recomendaciones.",
            f"Esta película destaca en el ranking público con una media de {entry.average_rating:.2f} sobre 5.",
            f"Su posición está respaldada por {entry.rating_count} valoraciones de usuarios.",
        ],
        evidence=[
            "Fallback público basado en ranking agregado de la comunidad.",
        ],
    )
