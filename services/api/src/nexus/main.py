"""The Nexus API application."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from nexus.api import auth, matters, work
from nexus.config import settings
from nexus.db import engine

log = logging.getLogger("nexus.api")

app = FastAPI(title="Nexus API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(auth.router)
app.include_router(matters.router)
app.include_router(work.router)


@app.exception_handler(Exception)
async def unexpected(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


@app.get("/api/health", tags=["ops"])
def health() -> dict:
    with engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"ok": True, "database": "up", "model": settings().model,
            "model_key_configured": bool(settings().anthropic_api_key)}
