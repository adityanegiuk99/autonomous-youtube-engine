from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends

from app.config import get_settings
from app.routers.channels import router as channels_router
from app.routers.trends import router as trends_router
from app.routers.ideas import router as ideas_router
from app.routers.content import router as content_router
from app.routers.videos import router as videos_router
from app.routers.research import router as research_router
from app.routers.media_assets import router as media_assets_router
from app.routers.approvals import router as approvals_router
from app.routers.analytics import router as analytics_router
from app.routers.workflows import router as workflows_router
from app.routers.operations import router as operations_router
from app.routers.dashboard import router as dashboard_router
from app.routers.publishing import router as publishing_router
from app.security import require_api_token

settings = get_settings()
app = FastAPI(title="Autonomous YouTube Engine API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(channels_router, prefix="/api/v1")
app.include_router(trends_router, prefix="/api/v1")
app.include_router(ideas_router, prefix="/api/v1")
app.include_router(content_router, prefix="/api/v1")
app.include_router(videos_router, prefix="/api/v1")
app.include_router(research_router, prefix="/api/v1")
app.include_router(media_assets_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(workflows_router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(publishing_router, prefix="/api/v1")


@app.get("/api/v1/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.get("/api/v1/auth/verify", tags=["auth"], dependencies=[Depends(require_api_token)])
def verify_local_token():
    return {"authenticated": True, "mode": "single-owner-local"}
