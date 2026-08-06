import logging

from fastapi import APIRouter, HTTPException

from app.core.readiness import check_runtime_readiness


router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def readiness_check() -> dict[str, str]:
    readiness = check_runtime_readiness()
    if not readiness.is_ready:
        logger.warning("runtime_not_ready missing=%s", ",".join(readiness.missing))
        raise HTTPException(
            status_code=503,
            detail={
                "code": "runtime_data_unavailable",
                "message": "Runtime dataset or recommender artifacts are unavailable.",
            },
        )
    return {"status": "ready"}
