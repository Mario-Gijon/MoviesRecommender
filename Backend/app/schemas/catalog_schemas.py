from pydantic import BaseModel, Field


class MovieCoverage(BaseModel):
    availableForContent: bool
    availableForCollaborative: bool
    contentCoverage: float
    collaborativeCoverage: float
    coverageNotes: list[str]


class PublicMovieRecord(BaseModel):
    movieId: int
    id: int
    tmdbId: int | None = None
    movieLensId: int | None = None
    imdbId: str | None = None
    title: str
    cleanTitle: str | None = None
    originalTitle: str | None = None
    year: int
    overview: str | None = None
    displayTitle: str | None = None
    displayOverview: str | None = None
    posterUrl: str | None = None
    posterPath: str | None = None
    posterFile: str | None = None
    runtime: int | None = None
    originalLanguage: str | None = None
    genres: list[str]
    displayGenres: list[str] | None = None
    keywords: list[str] = Field(default_factory=list)
    userTags: list[str] = Field(default_factory=list)
    topCast: list[str] = Field(default_factory=list)
    directors: list[str] = Field(default_factory=list)
    tags: list[str]
    ratingCount: int | None = None
    averageRating: float | None = None
    filteredRatingCount: int | None = None
    filteredAverageRating: float | None = None
    candidateScore: float | None = None
    dataReliabilityScore: float | None = None
    recencyScore: float | None = None
    tmdbPopularity: float | None = None
    tmdbVoteAverage: float | None = None
    tmdbVoteCount: int | None = None
    suitabilityCategory: str | None = None
    standDisplayScore: float | None = None
    standDisplayReasons: list[str] = Field(default_factory=list)
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


class PaginatedMovieCatalogResponse(BaseModel):
    items: list[PublicMovieRecord]
    page: int
    pageSize: int
    totalItems: int
    totalPages: int
