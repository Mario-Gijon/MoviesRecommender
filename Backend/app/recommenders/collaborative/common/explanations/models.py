from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


CollaborativeExplanationStrength = Literal["strong", "medium", "weak", "fallback"]


@dataclass(frozen=True)
class EvidenceMovie:
    movieId: int
    title: str
    userRating: int | float | None = None
    role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceProfile:
    profileLabel: str | None = None
    groupSummary: str | None = None
    sharedMovies: list[EvidenceMovie] = field(default_factory=list)
    role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profileLabel": self.profileLabel,
            "groupSummary": self.groupSummary,
            "sharedMovies": [movie.to_dict() for movie in self.sharedMovies],
            "role": self.role,
        }


@dataclass(frozen=True)
class CollaborativeExplanation:
    explanationText: str
    explanationType: str
    explanationSource: str
    fidelity: str
    evidenceStrength: CollaborativeExplanationStrength
    evidenceMovies: list[EvidenceMovie] = field(default_factory=list)
    evidenceProfiles: list[EvidenceProfile] = field(default_factory=list)
    templateId: str | None = None
    limitations: list[str] = field(default_factory=list)
    debug: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "explanationText": self.explanationText,
            "explanationType": self.explanationType,
            "explanationSource": self.explanationSource,
            "fidelity": self.fidelity,
            "evidenceStrength": self.evidenceStrength,
            "evidenceMovies": [movie.to_dict() for movie in self.evidenceMovies],
            "evidenceProfiles": [profile.to_dict() for profile in self.evidenceProfiles],
            "templateId": self.templateId,
            "limitations": list(self.limitations),
            "debug": self.debug,
        }
