from fastapi import FastAPI # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from fastapi.staticfiles import StaticFiles # type: ignore

from app.api.routes.catalog_routes import router as catalog_router
from app.api.routes.health_routes import router as health_router
from app.api.routes.recommendation_routes import router as recommendation_router
from app.core.config import settings
from app.infrastructure.datasets.movielens_paths import (
    OFFLINE_DATASET_AUDIT_DIR,
    OFFLINE_DATASET_POSTERS_DIR,
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Explainable movie recommender API for local science outreach demos.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(catalog_router)
app.include_router(recommendation_router)
app.mount(
    "/offline/posters",
    StaticFiles(directory=OFFLINE_DATASET_POSTERS_DIR, check_dir=False),
    name="offline-posters",
)
app.mount(
    "/audit",
    StaticFiles(directory=OFFLINE_DATASET_AUDIT_DIR, html=True, check_dir=False),
    name="offline-audit",
)
