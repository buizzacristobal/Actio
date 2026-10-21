from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.middleware import HardeningMiddleware
from app.engine.cmf_rates import RateNotFoundError
from app.services.extractor import ExtractionError
from app.services.generator import PdfUnavailableError


def _err(status: int, msg: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": msg})


def create_app() -> FastAPI:
    app = FastAPI(title="LegalTech Chile Engine", version="0.1.0")
    settings = get_settings()
    app.add_middleware(
        HardeningMiddleware, rate_limit_per_min=settings.rate_limit_per_min,
        max_body_bytes=settings.max_body_bytes)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins,
        allow_methods=["POST", "GET"], allow_headers=["Content-Type", "X-API-Key"])

    # Zero data retention: error bodies never echo client documents or inputs.
    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        fields = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": fields})

    @app.exception_handler(ExtractionError)
    async def _extraction(_: Request, exc: ExtractionError):
        return _err(422, "No se pudo extraer un instrumento válido del documento")

    @app.exception_handler(RateNotFoundError)
    async def _rates(_: Request, exc: RateNotFoundError):
        return _err(422, str(exc))

    @app.exception_handler(PdfUnavailableError)
    async def _pdf(_: Request, exc: PdfUnavailableError):
        return _err(501, str(exc))

    @app.exception_handler(RuntimeError)
    async def _runtime(_: Request, exc: RuntimeError):
        # configuration problems (e.g. OCR not configured) are actionable, not leaks
        return _err(422, str(exc)) if "no configurado" in str(exc) else _err(500, "Error interno")

    @app.exception_handler(ValueError)
    async def _value(_: Request, exc: ValueError):
        return _err(422, str(exc))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        return _err(500, "Error interno")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": app.version}

    app.include_router(api_router)
    return app


app = create_app()
