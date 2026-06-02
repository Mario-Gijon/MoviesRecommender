from pydantic import BaseModel


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
