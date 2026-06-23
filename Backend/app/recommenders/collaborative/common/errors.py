from dataclasses import dataclass


@dataclass(frozen=True)
class CollaborativeRecommendationError(RuntimeError):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


class CollaborativeAlgorithmNotAvailableError(CollaborativeRecommendationError):
    pass


class CollaborativeModelArtifactError(CollaborativeRecommendationError):
    pass
