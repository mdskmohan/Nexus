"""The Nexus API application."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
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


def _plain(error: dict) -> str:
    field = str(error["loc"][-1]).replace("_", " ") if error.get("loc") else "value"
    ctx = error.get("ctx") or {}
    kind = error.get("type", "")
    if kind == "missing":
        return f"{field.capitalize()} is required."
    if kind == "string_too_short":
        return f"{field.capitalize()} must be at least {ctx.get('min_length')} characters."
    if kind == "string_too_long":
        return f"{field.capitalize()} must be at most {ctx.get('max_length')} characters."
    if "email" in field or "email" in str(error.get("msg", "")):
        return "Enter a valid email address."
    return f"{field.capitalize()}: {error.get('msg', 'is not valid')}."


@app.exception_handler(RequestValidationError)
async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse({"detail": " ".join(_plain(e) for e in exc.errors())}, status_code=422)


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
