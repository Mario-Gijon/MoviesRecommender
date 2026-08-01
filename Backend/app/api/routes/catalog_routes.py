from math import ceil

from fastapi import APIRouter, HTTPException, Query

from app.domain.movies.movie_schemas import (
    CatalogStatus,
    Movie,
    PaginatedMovieCatalogResponse,
)
from app.infrastructure.catalog.offline_catalog_repository import (
    OfflineCatalogDataUnavailableError,
    catalog_repository,
)


router = APIRouter(tags=["catalog"])


@router.get("/catalog/status", response_model=CatalogStatus)
def get_catalog_status() -> CatalogStatus:
    return _catalog_call(lambda: catalog_repository.get_status())


@router.get("/movies/featured", response_model=list[Movie])
def get_featured_movies() -> list[Movie]:
    return _catalog_call(lambda: catalog_repository.get_featured_movies())


@router.get("/movies/public-catalog", response_model=PaginatedMovieCatalogResponse)
def get_public_catalog(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=40, ge=1, le=100),
    search: str | None = None,
    genre: str | None = None,
) -> PaginatedMovieCatalogResponse:
    items, total_items = _catalog_call(
        lambda: catalog_repository.get_public_catalog_page(
            page=page,
            page_size=pageSize,
            search=search,
            genre=genre,
        ),
    )
    total_pages = 0 if total_items == 0 else ceil(total_items / pageSize)
    return PaginatedMovieCatalogResponse(
        items=items,
        page=page,
        pageSize=pageSize,
        totalItems=total_items,
        totalPages=total_pages,
    )


def _catalog_call(callable_):
    try:
        return callable_()
    except OfflineCatalogDataUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "catalog_unavailable",
                "message": "Offline catalog data is unavailable.",
            },
        ) from exc
