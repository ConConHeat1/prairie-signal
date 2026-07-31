"""Structured logging with privacy-safe request fields."""

from __future__ import annotations

import logging
import time
from uuid import uuid4

import structlog
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from prairie_signal_api.metrics import HTTP_DURATION, HTTP_REQUESTS


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", level=level.upper(), force=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


class PrivacySafeRequestMiddleware:
    """Log route templates only; never log query strings, IPs, or headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = structlog.get_logger("http")

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.monotonic()
        request_id = uuid4().hex
        status_code = 500

        async def send_with_metrics(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message).append("x-request-id", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_metrics)
        finally:
            route = scope.get("route")
            route_template = getattr(route, "path", "<unmatched>")
            method = str(scope.get("method", "UNKNOWN"))
            duration = time.monotonic() - started
            HTTP_REQUESTS.labels(method, route_template, str(status_code)).inc()
            HTTP_DURATION.labels(method, route_template).observe(duration)
            self.logger.info(
                "request_completed",
                request_id=request_id,
                method=method,
                route=route_template,
                status=status_code,
                duration_ms=round(duration * 1000, 2),
            )


def privacy_safe_log_fields(request: Request) -> dict[str, str]:
    """Small separately testable allow-list used by diagnostics."""
    route = request.scope.get("route")
    return {
        "method": request.method,
        "route": getattr(route, "path", "<unmatched>"),
    }
