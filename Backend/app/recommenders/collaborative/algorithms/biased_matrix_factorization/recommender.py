from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import (
    ALGORITHM_ID,
    ALGORITHM_LABEL,
    BiasedMatrixFactorizationRuntimeConfig,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.storage import (
    get_biased_matrix_factorization_variant_artifacts,
    load_biased_matrix_factorization_manifest,
)
from app.recommenders.collaborative.common.errors import CollaborativeModelArtifactError
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationRequest,
    CollaborativeRecommendationResult,
)


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
        self._manifest = self._load_manifest()

    def recommend(
        self,
        request: CollaborativeRecommendationRequest,
    ) -> CollaborativeRecommendationResult:
        del request
        self._raise_not_trained()

    def predict_rating_for_movie(
        self,
        request: CollaborativeRecommendationRequest,
        movie_id: int,
    ) -> None:
        del request, movie_id
        self._raise_not_trained()

    def _load_manifest(self) -> dict:
        try:
            return load_biased_matrix_factorization_manifest(
                self._runtime_config.variant_id
            )
        except RuntimeError as exc:
            raise CollaborativeModelArtifactError(
                code="biased_matrix_factorization_manifest_missing",
                message=str(exc),
            ) from exc

    def _raise_not_trained(self) -> None:
        status = self._manifest.get("status")
        raise CollaborativeModelArtifactError(
            code="biased_matrix_factorization_not_trained",
            message=(
                "Biased Matrix Factorization is not ready for runtime use. "
                f"Variant {self._runtime_config.variant_id} has status {status!r}."
            ),
        )
