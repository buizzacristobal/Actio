"""Operational middleware: request logging (never bodies/queries), body-size cap,
per-IP rate limiting, and security headers."""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

log = logging.getLogger("legaltech.access")


class HardeningMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate_limit_per_min: int, max_body_bytes: int) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.limit = rate_limit_per_min
        self.max_body = max_body_bytes
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _limited(self, ip: str) -> bool:
        if self.limit <= 0:
            return False
        now = time.monotonic()
        q = self._hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.limit:
            return True
        q.append(now)
        return False

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        ip = request.client.host if request.client else "unknown"
        is_api = request.url.path.startswith("/api/")
        if is_api and int(request.headers.get("content-length") or 0) > self.max_body:
            resp: Response = JSONResponse({"detail": "Solicitud demasiado grande"}, status_code=413)
        elif is_api and self._limited(ip):
            resp = JSONResponse({"detail": "Demasiadas solicitudes"}, status_code=429,
                                headers={"Retry-After": "60"})
        else:
            resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Request-ID"] = rid
        if is_api:
            resp.headers["Cache-Control"] = "no-store"
        # path only: no query string, no body, no client data
        log.info("rid=%s %s %s -> %s %.0fms", rid, request.method, request.url.path,
                 resp.status_code, (time.perf_counter() - start) * 1000)
        return resp
