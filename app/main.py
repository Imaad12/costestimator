"""FastAPI application factory: REST API (/api) + server-rendered local web UI."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .core.errors import AppError, AuthRequired
from .database import get_db

log = logging.getLogger("ksa.app")


def load_persisted_settings() -> None:
    db = get_db()
    row = db.one("SELECT value FROM settings WHERE key='company'")
    if row and row["value"]:
        get_settings().company.update(json.loads(row["value"]))


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings().ensure_dirs()
    get_db()
    load_persisted_settings()
    log.info("KSA Construction Estimating Suite started")
    yield


class SerializeRequests:
    """ASGI middleware: one request at a time. The app shares one SQLite connection and uses explicit transactions, so requests
    are serialised to rule out interleaved transactions (adequate for the local single-user / small-team design)."""

    def __init__(self, app):
        import asyncio
        self.app, self.lock = app, asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        async with self.lock:
            await self.app(scope, receive, send)


def create_app() -> FastAPI:
    from .api.routes import router as api_router
    from .web.routes import router as web_router

    app = FastAPI(title="KSA Construction Estimating Suite", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        path = request.url.path
        if path.startswith("/api"):
            return JSONResponse(exc.to_dict(), status_code=exc.status_code)
        if isinstance(exc, AuthRequired):
            return RedirectResponse("/login", status_code=303)
        return HTMLResponse(f"<h2>{exc.code}</h2><p>{exc.message}</p><p><a href='javascript:history.back()'>Back</a></p>", status_code=exc.status_code)

    @app.exception_handler(ValueError)
    async def value_error(request: Request, exc: ValueError):
        return JSONResponse({"error": "BAD_VALUE", "message": str(exc)}, status_code=422)

    static = Path(__file__).parent / "web" / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")
    app.include_router(api_router)
    app.include_router(web_router)
    from .web.routes_ext import router as web_ext_router
    app.include_router(web_ext_router)
    from .web.routes_tender import router as web_tender_router
    app.include_router(web_tender_router)
    from .web.routes_ops import router as web_ops_router
    app.include_router(web_ops_router)
    app.add_middleware(SerializeRequests)
    from .security import Hardening
    app.add_middleware(Hardening)
    return app


app = create_app()
