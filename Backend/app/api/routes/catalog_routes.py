from fastapi import APIRouter

from app.infrastructure.catalog.catalog_repository import catalog_repository


router = APIRouter(tags=["catalog"])


@router.get("/catalog/status")
def get_catalog_status() -> dict:
    return catalog_repository.get_status()


@router.get("/movies/featured")
def get_featured_movies() -> list[dict]:
    return catalog_repository.get_featured_movies()

