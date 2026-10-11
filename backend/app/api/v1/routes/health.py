"""Liveness + readiness probes for Kubernetes / load balancers."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.common import HealthStatus

router = APIRouter()


@router.get("/live", response_model=HealthStatus)
async def liveness():
    return HealthStatus(version=settings.APP_VERSION, env=settings.APP_ENV)


@router.get("/ready", response_model=HealthStatus)
async def readiness(db: AsyncSession = Depends(get_db)):
    components: dict[str, str] = {}
    try:
        await db.execute(text("SELECT 1"))
        components["database"] = "ok"
    except Exception as e:  # noqa: BLE001
        components["database"] = f"error: {e}"

    try:
        from app.embeddings.embedder import get_embedder
        get_embedder()
        components["embedder"] = "ok"
    except Exception as e:  # noqa: BLE001
        components["embedder"] = f"error: {e}"

    status = "ok" if all(v == "ok" for v in components.values()) else "degraded"
    return HealthStatus(
        status=status,
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
        components=components,
    )
