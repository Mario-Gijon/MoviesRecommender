from fastapi import APIRouter

from app.domain.movies.movie_schemas import CatalogStatus, Movie
from app.infrastructure.catalog.catalog_repository import catalog_repository


router = APIRouter(tags=["catalog"])


@router.get("/catalog/status", response_model=CatalogStatus)
def get_catalog_status() -> CatalogStatus:
    return catalog_repository.get_status()


@router.get("/movies/featured", response_model=list[Movie])
def get_featured_movies() -> list[Movie]:
    return catalog_repository.get_featured_movies()
