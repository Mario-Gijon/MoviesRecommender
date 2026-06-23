from math import ceil

from fastapi import APIRouter, Query

from app.catalog.catalog_repository import catalog_repository
from app.schemas.catalog_schemas import CatalogStatus, PaginatedMovieCatalogResponse, PublicMovieRecord


router = APIRouter(tags=["catalog"])


@router.get("/catalog/status", response_model=CatalogStatus)
def get_catalog_status() -> CatalogStatus:
    return catalog_repository.get_status()


@router.get("/movies/featured", response_model=list[PublicMovieRecord])
def get_featured_movies() -> list[PublicMovieRecord]:
    return catalog_repository.get_featured_movies()


@router.get("/movies/public-catalog", response_model=PaginatedMovieCatalogResponse)
def get_public_catalog(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=40, ge=1, le=100),
    search: str | None = None,
    genre: str | None = None,
) -> PaginatedMovieCatalogResponse:
    items, total_items = catalog_repository.get_public_catalog_page(
        page=page,
        page_size=pageSize,
        search=search,
        genre=genre,
    )
    total_pages = 0 if total_items == 0 else ceil(total_items / pageSize)
    return PaginatedMovieCatalogResponse(
        items=items,
        page=page,
        pageSize=pageSize,
        totalItems=total_items,
        totalPages=total_pages,
    )
