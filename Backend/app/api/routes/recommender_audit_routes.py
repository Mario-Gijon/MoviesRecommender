from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.project_paths.dataset_paths import RECOMMENDER_AUDIT_DIR


router = APIRouter(prefix="/recommender-audit", tags=["recommender-audit"])

COLLABORATIVE_AUDIT_DIR = RECOMMENDER_AUDIT_DIR / "collaborative_comparison"
ALLOWED_AUDIT_FILES = {
    "index.html": "text/html",
    "report.md": "text/markdown",
    "comparison_summary.json": "application/json",
    "variant_metrics.json": "application/json",
    "variant_metrics.csv": "text/csv",
    "selected_variants.json": "application/json",
    "selected_variants.csv": "text/csv",
    "evaluation_cases.json": "application/json",
}


@router.get("/collaborative/runs")
def list_collaborative_audit_runs() -> list[dict]:
    return [
        _run_summary(run_dir)
        for run_dir in _collaborative_run_dirs()
    ]


@router.get("/collaborative")
def get_latest_collaborative_audit() -> FileResponse:
    latest_run_dir = _latest_collaborative_run_dir()
    return _file_response(latest_run_dir, "index.html")


@router.get("/collaborative/{run_id}")
def get_collaborative_audit(run_id: str) -> FileResponse:
    run_dir = _collaborative_run_dir(run_id)
    return _file_response(run_dir, "index.html")


@router.get("/collaborative/{run_id}/files/{filename}")
def get_collaborative_audit_file(
    run_id: str,
    filename: str,
) -> FileResponse:
    run_dir = _collaborative_run_dir(run_id)
    return _file_response(run_dir, filename)


def _collaborative_run_dirs() -> list[Path]:
    if not COLLABORATIVE_AUDIT_DIR.exists():
        return []

    return sorted(
        [
            path
            for path in COLLABORATIVE_AUDIT_DIR.iterdir()
            if path.is_dir()
        ],
        key=lambda path: path.name,
        reverse=True,
    )


def _latest_collaborative_run_dir() -> Path:
    run_dirs = _collaborative_run_dirs()

    if not run_dirs:
        raise HTTPException(
            status_code=404,
            detail="No collaborative recommender audit runs were found.",
        )

    return run_dirs[0]


def _collaborative_run_dir(run_id: str) -> Path:
    run_dir = COLLABORATIVE_AUDIT_DIR / run_id

    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Collaborative recommender audit run was not found: {run_id}",
        )

    if run_dir.resolve().parent != COLLABORATIVE_AUDIT_DIR.resolve():
        raise HTTPException(
            status_code=400,
            detail="Invalid collaborative recommender audit run id.",
        )

    return run_dir


def _file_response(
    run_dir: Path,
    filename: str,
) -> FileResponse:
    if filename not in ALLOWED_AUDIT_FILES:
        raise HTTPException(
            status_code=404,
            detail=f"Collaborative recommender audit file is not exposed: {filename}",
        )

    path = run_dir / filename

    if not path.exists() or not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Collaborative recommender audit file was not found: {filename}",
        )

    return FileResponse(
        path,
        media_type=ALLOWED_AUDIT_FILES[filename],
        filename=None if filename == "index.html" else filename,
    )


def _run_summary(run_dir: Path) -> dict:
    index_path = run_dir / "index.html"
    summary_path = run_dir / "comparison_summary.json"

    return {
        "runId": run_dir.name,
        "hasIndex": index_path.exists(),
        "hasSummary": summary_path.exists(),
        "url": f"/recommender-audit/collaborative/{run_dir.name}",
    }