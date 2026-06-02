from pydantic import BaseModel, model_validator


class MovieCoverage(BaseModel):
    availableForContent: bool
    availableForCollaborative: bool
    contentCoverage: float
    collaborativeCoverage: float
    coverageNotes: list[str]


class Movie(BaseModel):
    id: int
    tmdbId: int | None = None
    movieLensId: int | None = None
    imdbId: str | None = None
    title: str
    originalTitle: str | None = None
    year: int
    overview: str | None = None
    posterUrl: str | None = None
    genres: list[str]
    tags: list[str]
    coverage: MovieCoverage
    availableForContent: bool = False
    availableForCollaborative: bool = False

    @model_validator(mode="before")
    @classmethod
    def populate_compatibility_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        coverage = data.get("coverage")
        if isinstance(coverage, dict):
            data.setdefault("availableForContent", coverage.get("availableForContent", False))
            data.setdefault(
                "availableForCollaborative",
                coverage.get("availableForCollaborative", False),
            )

        return data


class CatalogStatus(BaseModel):
    catalogVersion: str
    totalMovies: int
    visibleMovies: int
    recommendableMovies: int
    contentCoverage: float
    collaborativeCoverage: float
    hybridCoverage: float
    lastBuiltDate: str | None = None
    dataMode: str
    sources: list[str]
    notes: list[str]
