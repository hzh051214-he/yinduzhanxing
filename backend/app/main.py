"""FastAPI 应用主入口。"""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.api import readings, reports, cities
from app.api import portrait
from app.api import synastry

settings = get_settings()

# 前端静态文件目录（生产环境由 Dockerfile 构建放入）
STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 确保存储目录存在
    os.makedirs(settings.reports_storage_path, exist_ok=True)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    # 生产环境关闭自动文档（可按需开启）
    docs_url="/api/docs" if settings.debug else None,
    redoc_url=None,
)

# CORS — 支持通配符（Railway 会在环境变量里设置真实域名）
cors_origins = settings.cors_origins
if "*" in cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# API 路由
app.include_router(readings.router, prefix="/api")
app.include_router(reports.router,  prefix="/api")
app.include_router(cities.router,   prefix="/api")
app.include_router(portrait.router, prefix="/api")
app.include_router(synastry.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# 前端静态文件托管（生产环境）
if STATIC_DIR.exists():
    # 挂载静态资源（JS/CSS/图片）
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    # 所有非 /api 路由返回 index.html（Vue Router 的 history 模式需要）
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str, request: Request):
        # API 路由已经在上面注册，这里只处理前端路由
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"error": "Frontend not built"}
