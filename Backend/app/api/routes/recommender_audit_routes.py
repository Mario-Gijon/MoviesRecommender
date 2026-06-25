from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.project_paths.dataset_paths import RECOMMENDER_AUDIT_DIR


router = APIRouter(prefix="/recommender-audit", tags=["recommender-audit"])

CURRENT_COLLABORATIVE_AUDIT_DIR = (
    RECOMMENDER_AUDIT_DIR / "collaborative_comparison" / "current"
)

ALLOWED_AUDIT_FILES = {
    "index.html": "text/html",
    "report.md": "text/markdown",
    "comparison_summary.json": "application/json",
    "variant_metrics.json": "application/json",
    "variant_metrics.csv": "text/csv",
    "evaluation_cases.json": "application/json",
}


@router.get("/collaborative")
def get_current_collaborative_audit() -> FileResponse:
    return _file_response("index.html")


@router.get("/collaborative/files/{filename}")
def get_current_collaborative_audit_file(filename: str) -> FileResponse:
    return _file_response(filename)


def _file_response(filename: str) -> FileResponse:
    if filename not in ALLOWED_AUDIT_FILES:
        raise HTTPException(
            status_code=404,
            detail=f"Collaborative recommender audit file is not exposed: {filename}",
        )

    path = CURRENT_COLLABORATIVE_AUDIT_DIR / filename

    if not path.exists() or not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Collaborative recommender audit file was not found: {filename}",
        )

    if path.resolve().parent != CURRENT_COLLABORATIVE_AUDIT_DIR.resolve():
        raise HTTPException(
            status_code=400,
            detail="Invalid collaborative recommender audit file path.",
        )

    return FileResponse(
        path,
        media_type=ALLOWED_AUDIT_FILES[filename],
        filename=None if filename == "index.html" else filename,
    )
