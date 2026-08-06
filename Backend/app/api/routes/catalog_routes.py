from math import ceil

import logging

from fastapi import APIRouter, HTTPException, Query

from app.catalog.catalog_repository import (
    OfflineCatalogDataUnavailableError,
    catalog_repository,
)
from app.schemas.catalog_schemas import CatalogStatus, PaginatedMovieCatalogResponse, PublicMovieRecord


router = APIRouter(tags=["catalog"])
logger = logging.getLogger(__name__)


@router.get("/catalog/status", response_model=CatalogStatus)
def get_catalog_status() -> CatalogStatus:
    return _catalog_call(lambda: catalog_repository.get_status())


@router.get("/movies/featured", response_model=list[PublicMovieRecord])
def get_featured_movies() -> list[PublicMovieRecord]:
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
        )
    )
    total_pages = 0 if total_items == 0 else ceil(total_items / pageSize)
    return PaginatedMovieCatalogResponse(
        items=items,
        page=page,
        pageSize=pageSize,
        totalItems=total_items,
        totalPages=total_pages,
    )


def _catalog_call(operation):
    try:
        return operation()
    except OfflineCatalogDataUnavailableError as exc:
        logger.warning("catalog_unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "catalog_unavailable",
                "message": "Offline catalog data is unavailable.",
            },
        ) from exc
