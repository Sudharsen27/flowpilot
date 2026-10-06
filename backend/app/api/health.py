import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@router.get("/health/ready", response_model=None)
def ready(db: Session = Depends(get_db)) -> JSONResponse | dict[str, object]:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.warning("database readiness check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "checks": {"database": "unavailable"}},
        )
    return {"status": "ok", "checks": {"database": "ok"}}
