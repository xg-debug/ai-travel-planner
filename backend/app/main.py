from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import uuid
import os
from app.api.map_routes import router as map_routes_router
from app.api.trip_planning import router as trip_planning_router
from app.api.trip_plans import router as trip_plans_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.admin import router as admin_router
from app.core.database import Base, engine
import app.models  # noqa: F401
from app.core.config import settings


def _build_log_handlers():
    handlers = [logging.StreamHandler()]
    if settings.LOG_FILE:
        log_dir = os.path.dirname(settings.LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(settings.LOG_FILE, encoding="utf-8"))
    return handlers


logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=_build_log_handlers(),
    force=True,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# 允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件（用于上传的文件）
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# 注册路由
app.include_router(trip_planning_router, prefix="/api/trip", tags=["trip-planning"])
app.include_router(trip_plans_router, prefix="/api/trip", tags=["trip-plans"])
app.include_router(map_routes_router, prefix="/api/trip", tags=["map-routes"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
        "health": "/api/health"
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    request_id = str(uuid.uuid4())[:8]
    logger.exception("Unhandled exception request_id=%s error=%s", request_id, exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"服务暂时不可用，请稍后重试（错误编号: {request_id}）"
        },
    )
