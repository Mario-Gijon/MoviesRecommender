from pydantic import BaseModel


class Movie(BaseModel):
    id: int
    title: str
    year: int
    posterUrl: str | None = None
    genres: list[str]
    availableForContent: bool
    availableForCollaborative: bool

