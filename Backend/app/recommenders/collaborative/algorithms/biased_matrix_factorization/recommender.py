import json
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.catalog.catalog_repository import catalog_repository
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import (
    ALGORITHM_ID,
    ALGORITHM_LABEL,
    BmfRatingPrediction,
    BiasedMatrixFactorizationRuntimeConfig,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.runtime_core import (
    BmfCandidatePrediction,
    build_usable_ratings,
    infer_session_profile,
    score_public_candidates,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.storage import (
    get_biased_matrix_factorization_variant_artifacts,
    load_biased_matrix_factorization_manifest,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.recommender import (
    PopularityBaselineRecommender,
)
from app.recommenders.collaborative.common.errors import CollaborativeModelArtifactError
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationExplanation,
    CollaborativeRecommendationRequest,
    CollaborativeRecommendationResult,
    CollaborativeRecommendedMovie,
    CollaborativeRecommenderDetails,
)


@dataclass(frozen=True)
class BmfRuntimeArtifacts:
    manifest: dict[str, Any]
    global_mean: float
    rating_min: float
    rating_max: float
    factor_count: int
    movie_id_to_index: dict[int, int]
    movie_index_to_id: dict[int, int]
    movie_factors: np.ndarray
    movie_biases: np.ndarray
    public_movie_ids: np.ndarray
    public_movie_indices: np.ndarray
    public_movie_count: int
    missing_public_candidates_from_model: int


class BiasedMatrixFactorizationRecommender:
    algorithm_id = ALGORITHM_ID
    algorithm_label = ALGORITHM_LABEL

    def __init__(
        self,
        *,
        runtime_config: BiasedMatrixFactorizationRuntimeConfig,
    ) -> None:
        self._runtime_config = runtime_config
        self._artifacts = get_biased_matrix_factorization_variant_artifacts(
            runtime_config.variant_id
        )
        self._runtime_artifacts: BmfRuntimeArtifacts | None = None
        self._fallback_recommender = PopularityBaselineRecommender()

    def recommend(
        self,
        request: CollaborativeRecommendationRequest,
    ) -> CollaborativeRecommendationResult:
        total_started_at = time.perf_counter()
        runtime_artifacts = self._load_runtime_artifacts()

        rated_movie_ids = {rating.movie_id for rating in request.ratings}
        ratings_by_movie_id = _build_ratings_by_movie_id(request)

        personalized_started_at = time.perf_counter()

        usable_ratings, ignored_unknown_rated_movies = build_usable_ratings(
            ratings_by_movie_id=ratings_by_movie_id,
            movie_id_to_index=runtime_artifacts.movie_id_to_index,
        )

        personalized_recommendations: list[CollaborativeRecommendedMovie] = []
        raw_candidate_count = 0
        filtered_low_score_candidates = 0

        if usable_ratings:
            session_profile = infer_session_profile(
                usable_ratings=usable_ratings,
                movie_factors=runtime_artifacts.movie_factors,
                movie_biases=runtime_artifacts.movie_biases,
                global_mean=runtime_artifacts.global_mean,
                factor_count=runtime_artifacts.factor_count,
                session_inference_steps=self._runtime_config.session_inference_steps,
                session_learning_rate=self._runtime_config.session_learning_rate,
                session_regularization=self._runtime_config.session_regularization,
            )

            scoring_result = score_public_candidates(
                public_movie_ids=runtime_artifacts.public_movie_ids,
                public_movie_indices=runtime_artifacts.public_movie_indices,
                rated_movie_ids=rated_movie_ids,
                movie_factors=runtime_artifacts.movie_factors,
                movie_biases=runtime_artifacts.movie_biases,
                session_profile=session_profile,
                global_mean=runtime_artifacts.global_mean,
                rating_min=runtime_artifacts.rating_min,
                rating_max=runtime_artifacts.rating_max,
                min_prediction_score=self._runtime_config.min_prediction_score,
                scoring_mode=self._runtime_config.scoring_mode,
                movie_bias_weight=self._runtime_config.movie_bias_weight,
                limit=request.limit,
            )
            raw_candidate_count = scoring_result.raw_candidate_count
            filtered_low_score_candidates = scoring_result.filtered_low_score_candidates

            personalized_recommendations = [
                CollaborativeRecommendedMovie(
                    movie_id=candidate.movie_id,
                    rank=rank,
                    score=round(candidate.predicted_rating, 6),
                    explanation=_build_explanation(candidate),
                    algorithm_details=_build_algorithm_details(
                        candidate=candidate,
                        runtime_artifacts=runtime_artifacts,
                        session_user_bias=session_profile.session_bias,
                        movie_bias_weight=self._runtime_config.movie_bias_weight,
                    ),
                )
                for rank, candidate in enumerate(
                    scoring_result.candidates,
                    start=1,
                )
            ]

        personalized_runtime_ms = _elapsed_ms(personalized_started_at)

        fallback_runtime_ms = 0.0
        fallback_recommendations_added = 0
        recommendations = list(personalized_recommendations)

        if len(recommendations) < request.limit:
            fallback_started_at = time.perf_counter()
            excluded_movie_ids = {item.movie_id for item in recommendations}
            fallback_recommendations = self._fallback_recommender.recommend_fillers(
                rated_movie_ids=rated_movie_ids,
                excluded_movie_ids=excluded_movie_ids,
                limit=request.limit - len(recommendations),
                start_rank=len(recommendations) + 1,
                fallback=True,
            )
            fallback_runtime_ms = _elapsed_ms(fallback_started_at)
            fallback_recommendations_added = len(fallback_recommendations)
            recommendations.extend(fallback_recommendations)

        total_runtime_ms = _elapsed_ms(total_started_at)

        return CollaborativeRecommendationResult(
            recommendations=recommendations,
            recommender_details=CollaborativeRecommenderDetails(
                algorithm_id=self.algorithm_id,
                algorithm_label=self.algorithm_label,
                is_personalized=True,
                is_explainable=True,
                status="ready",
                model_version=runtime_artifacts.manifest.get("modelVersion"),
                timing_ms=round(total_runtime_ms, 6),
                details={
                    "modelVariant": self._runtime_config.variant_id,
                    "candidatePolicy": "public_movies_only",
                    "ratingMode": "raw_explicit_ratings",
                    "modelType": "biased_matrix_factorization",
                    "sessionInference": "fold_in_temporary_user_profile",
                    "sessionInferenceSteps": (
                        self._runtime_config.session_inference_steps
                    ),
                    "sessionLearningRate": (
                        self._runtime_config.session_learning_rate
                    ),
                    "sessionRegularization": (
                        self._runtime_config.session_regularization
                    ),
                    "minPredictionScore": self._runtime_config.min_prediction_score,
                    "scoringMode": self._runtime_config.scoring_mode,
                    "movieBiasWeight": self._runtime_config.movie_bias_weight,
                    "usableRatings": len(usable_ratings),
                    "ignoredUnknownRatedMovies": ignored_unknown_rated_movies,
                    "publicCandidates": runtime_artifacts.public_movie_count,
                    "modelPublicCandidates": int(
                        runtime_artifacts.public_movie_ids.shape[0]
                    ),
                    "missingPublicCandidatesFromModel": (
                        runtime_artifacts.missing_public_candidates_from_model
                    ),
                    "rawCandidateCount": raw_candidate_count,
                    "filteredLowScoreCandidates": filtered_low_score_candidates,
                    "personalizedRecommendations": len(personalized_recommendations),
                    "fallbackUsed": fallback_recommendations_added > 0,
                    "fallbackAlgorithm": (
                        PopularityBaselineRecommender.algorithm_id
                        if fallback_recommendations_added > 0
                        else None
                    ),
                    "fallbackRecommendationsAdded": fallback_recommendations_added,
                    "personalizedRuntimeMs": round(personalized_runtime_ms, 6),
                    "fallbackRuntimeMs": round(fallback_runtime_ms, 6),
                    "totalRuntimeMs": round(total_runtime_ms, 6),
                    "artifactLoadingMode": "lazy_cached",
                    "manifestStatus": runtime_artifacts.manifest.get("status"),
                    "manifestRuntimeStatus": runtime_artifacts.manifest.get(
                        "runtimeStatus"
                    ),
                },
            ),
            limit=request.limit,
            template_session_id=request.template_session_id,
        )

    def predict_rating_for_movie(
        self,
        request: CollaborativeRecommendationRequest,
        movie_id: int,
    ) -> BmfRatingPrediction:
        started_at = time.perf_counter()
        runtime_artifacts = self._load_runtime_artifacts()

        movie_index = runtime_artifacts.movie_id_to_index.get(movie_id)
        if movie_index is None:
            return BmfRatingPrediction(
                prediction_available=False,
                predicted_rating_raw=None,
                predicted_rating_regularized=None,
                usable_rating_count=0,
                prediction_runtime_ms=round(_elapsed_ms(started_at), 6),
            )

        ratings_by_movie_id = _build_ratings_by_movie_id(request)
        usable_ratings, _ = build_usable_ratings(
            ratings_by_movie_id=ratings_by_movie_id,
            movie_id_to_index=runtime_artifacts.movie_id_to_index,
        )

        if not usable_ratings:
            return BmfRatingPrediction(
                prediction_available=False,
                predicted_rating_raw=None,
                predicted_rating_regularized=None,
                usable_rating_count=0,
                prediction_runtime_ms=round(_elapsed_ms(started_at), 6),
            )

        session_profile = infer_session_profile(
            usable_ratings=usable_ratings,
            movie_factors=runtime_artifacts.movie_factors,
            movie_biases=runtime_artifacts.movie_biases,
            global_mean=runtime_artifacts.global_mean,
            factor_count=runtime_artifacts.factor_count,
            session_inference_steps=self._runtime_config.session_inference_steps,
            session_learning_rate=self._runtime_config.session_learning_rate,
            session_regularization=self._runtime_config.session_regularization,
        )

        movie_factor = runtime_artifacts.movie_factors[movie_index]
        latent_affinity = float(np.dot(session_profile.session_factors, movie_factor))
        raw_prediction = (
            runtime_artifacts.global_mean
            + session_profile.session_bias
            + float(runtime_artifacts.movie_biases[movie_index])
            + latent_affinity
        )
        clipped_prediction = float(
            np.clip(
                raw_prediction,
                runtime_artifacts.rating_min,
                runtime_artifacts.rating_max,
            )
        )

        return BmfRatingPrediction(
            prediction_available=True,
            predicted_rating_raw=round(float(raw_prediction), 6),
            predicted_rating_regularized=round(clipped_prediction, 6),
            usable_rating_count=len(usable_ratings),
            prediction_runtime_ms=round(_elapsed_ms(started_at), 6),
        )

    def _load_runtime_artifacts(self) -> BmfRuntimeArtifacts:
        if self._runtime_artifacts is not None:
            return self._runtime_artifacts

        manifest = self._load_manifest()
        if manifest.get("status") != "trained":
            raise CollaborativeModelArtifactError(
                code="biased_matrix_factorization_not_trained",
                message=(
                    "Biased Matrix Factorization model is not trained for variant "
                    f"{self._runtime_config.variant_id}. "
                    f"Manifest status: {manifest.get('status')!r}."
                ),
            )

        self._validate_artifact_files()

        movie_factors = np.load(self._artifacts.movie_factors_path).astype(
            np.float32,
            copy=False,
        )
        movie_index_df = pd.read_csv(self._artifacts.movie_index_path).sort_values(
            "movieIndex",
        )
        movie_biases_df = pd.read_csv(self._artifacts.movie_biases_path).sort_values(
            "movieIndex",
        )

        _validate_movie_artifact_shapes(
            movie_factors=movie_factors,
            movie_index_df=movie_index_df,
            movie_biases_df=movie_biases_df,
            variant_id=self._runtime_config.variant_id,
        )

        movie_ids = movie_index_df["movieId"].to_numpy(dtype=np.int32, copy=True)
        movie_indices = movie_index_df["movieIndex"].to_numpy(dtype=np.int32, copy=True)
        movie_biases = movie_biases_df["movieBias"].to_numpy(dtype=np.float32, copy=True)

        movie_id_to_index = {
            int(movie_id): int(movie_index)
            for movie_id, movie_index in zip(movie_ids, movie_indices, strict=True)
        }
        movie_index_to_id = {
            int(movie_index): int(movie_id)
            for movie_id, movie_index in zip(movie_ids, movie_indices, strict=True)
        }

        global_stats = json.loads(
            self._artifacts.global_stats_path.read_text(encoding="utf-8")
        )

        public_movie_ids, public_movie_indices, public_movie_count, missing_public = (
            _build_public_movie_arrays(movie_id_to_index=movie_id_to_index)
        )

        self._runtime_artifacts = BmfRuntimeArtifacts(
            manifest=manifest,
            global_mean=float(global_stats["globalMean"]),
            rating_min=float(global_stats["ratingMin"]),
            rating_max=float(global_stats["ratingMax"]),
            factor_count=int(movie_factors.shape[1]),
            movie_id_to_index=movie_id_to_index,
            movie_index_to_id=movie_index_to_id,
            movie_factors=np.ascontiguousarray(movie_factors),
            movie_biases=np.ascontiguousarray(movie_biases),
            public_movie_ids=public_movie_ids,
            public_movie_indices=public_movie_indices,
            public_movie_count=public_movie_count,
            missing_public_candidates_from_model=missing_public,
        )
        return self._runtime_artifacts

    def _load_manifest(self) -> dict[str, Any]:
        try:
            return load_biased_matrix_factorization_manifest(
                self._runtime_config.variant_id
            )
        except RuntimeError as exc:
            raise CollaborativeModelArtifactError(
                code="biased_matrix_factorization_manifest_missing",
                message=str(exc),
            ) from exc

    def _validate_artifact_files(self) -> None:
        required_paths = [
            self._artifacts.movie_factors_path,
            self._artifacts.movie_biases_path,
            self._artifacts.movie_index_path,
            self._artifacts.global_stats_path,
            self._artifacts.training_metrics_path,
            self._artifacts.manifest_path,
        ]

        for path in required_paths:
            if not path.exists():
                raise CollaborativeModelArtifactError(
                    code="biased_matrix_factorization_artifact_missing",
                    message=(
                        "Biased Matrix Factorization artifact is missing for variant "
                        f"{self._runtime_config.variant_id}: {path}"
                    ),
                )


def _build_ratings_by_movie_id(
    request: CollaborativeRecommendationRequest,
) -> dict[int, float]:
    ratings_by_movie_id: dict[int, float] = {}
    for rating in request.ratings:
        ratings_by_movie_id[rating.movie_id] = float(rating.rating)
    return ratings_by_movie_id


def _build_public_movie_arrays(
    *,
    movie_id_to_index: dict[int, int],
) -> tuple[np.ndarray, np.ndarray, int, int]:
    public_movie_ids: list[int] = []
    public_movie_indices: list[int] = []
    public_movie_count = 0
    missing_public_candidates_from_model = 0

    for movie in catalog_repository.get_recommendation_candidates():
        public_movie_count += 1
        movie_id = int(movie["movieId"])
        movie_index = movie_id_to_index.get(movie_id)

        if movie_index is None:
            missing_public_candidates_from_model += 1
            continue

        public_movie_ids.append(movie_id)
        public_movie_indices.append(movie_index)

    return (
        np.asarray(public_movie_ids, dtype=np.int32),
        np.asarray(public_movie_indices, dtype=np.int32),
        public_movie_count,
        missing_public_candidates_from_model,
    )


def _validate_movie_artifact_shapes(
    *,
    movie_factors: np.ndarray,
    movie_index_df: pd.DataFrame,
    movie_biases_df: pd.DataFrame,
    variant_id: str,
) -> None:
    movie_count = len(movie_index_df)

    if movie_factors.ndim != 2:
        raise CollaborativeModelArtifactError(
            code="biased_matrix_factorization_invalid_movie_factors",
            message=(
                "Movie factors must be a 2D array for Biased Matrix Factorization "
                f"variant {variant_id}."
            ),
        )

    if movie_factors.shape[0] != movie_count:
        raise CollaborativeModelArtifactError(
            code="biased_matrix_factorization_shape_mismatch",
            message=(
                "Movie factor row count does not match movie index rows for "
                f"variant {variant_id}."
            ),
        )

    if len(movie_biases_df) != movie_count:
        raise CollaborativeModelArtifactError(
            code="biased_matrix_factorization_shape_mismatch",
            message=(
                "Movie bias row count does not match movie index rows for "
                f"variant {variant_id}."
            ),
        )

    expected_indices = np.arange(movie_count, dtype=np.int32)
    movie_indices = movie_index_df["movieIndex"].to_numpy(dtype=np.int32, copy=True)
    bias_indices = movie_biases_df["movieIndex"].to_numpy(dtype=np.int32, copy=True)

    if not np.array_equal(movie_indices, expected_indices):
        raise CollaborativeModelArtifactError(
            code="biased_matrix_factorization_invalid_movie_index",
            message=(
                "Movie index must be contiguous from 0 to movie_count - 1 for "
                f"variant {variant_id}."
            ),
        )

    if not np.array_equal(bias_indices, expected_indices):
        raise CollaborativeModelArtifactError(
            code="biased_matrix_factorization_invalid_movie_biases",
            message=(
                "Movie biases must be aligned by contiguous movieIndex for "
                f"variant {variant_id}."
            ),
        )


def _build_explanation(
    candidate: BmfCandidatePrediction,
) -> CollaborativeRecommendationExplanation:
    return CollaborativeRecommendationExplanation(
        headline="Encaja con el perfil de gustos inferido a partir de tus valoraciones.",
        reasons=[
            "El modelo ha inferido un perfil temporal usando las películas que has valorado.",
            "La puntuación se calcula con factores latentes aprendidos a partir de valoraciones de usuarios.",
            f"La predicción estimada para esta película es {candidate.predicted_rating:.2f} sobre 5.",
        ],
        evidence=[
            "Modelo colaborativo basado en factorización matricial sesgada.",
            "Solo se recomiendan películas disponibles en el catálogo público.",
        ],
    )


def _build_algorithm_details(
    *,
    candidate: BmfCandidatePrediction,
    runtime_artifacts: BmfRuntimeArtifacts,
    session_user_bias: float,
    movie_bias_weight: float,
) -> dict[str, Any]:
    return {
        "rankingScore": round(candidate.ranking_score, 6),
        "scoringMode": candidate.scoring_mode,
        "movieBiasWeight": round(movie_bias_weight, 6),
        "predictedRating": round(candidate.predicted_rating, 6),
        "rawPredictedRating": round(candidate.raw_prediction, 6),
        "globalMean": round(runtime_artifacts.global_mean, 6),
        "movieBias": round(candidate.movie_bias, 6),
        "latentAffinity": round(candidate.latent_affinity, 6),
        "sessionUserBias": round(session_user_bias, 6),
        "factorCount": runtime_artifacts.factor_count,
        "fallback": False,
    }


def _elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000
