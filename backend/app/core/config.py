from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal


def _csv(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


def _provider() -> Literal["anthropic", "openai_compatible"]:
    v = os.environ.get("LLM_PROVIDER", "anthropic")
    if v not in ("anthropic", "openai_compatible"):
        raise RuntimeError(f"LLM_PROVIDER desconocido: {v}")
    return v  # type: ignore[return-value]


@dataclass(frozen=True)
class Settings:
    cors_origins: list[str] = field(
        default_factory=lambda: _csv("CORS_ORIGINS", "http://localhost:3000"))
    api_key: str | None = field(default_factory=lambda: os.environ.get("API_KEY") or None)
    llm_provider: Literal["anthropic", "openai_compatible"] = field(
        default_factory=lambda: _provider())
    llm_base_url: str | None = field(default_factory=lambda: os.environ.get("LLM_BASE_URL") or None)
    llm_api_key: str | None = field(default_factory=lambda: os.environ.get("LLM_API_KEY") or None)
    rate_limit_per_min: int = field(default_factory=lambda: int(os.environ.get("RATE_LIMIT_PER_MIN", "60")))
    max_body_bytes: int = field(
        default_factory=lambda: int(os.environ.get("MAX_BODY_BYTES", str(12 * 1024 * 1024))))
    llm_vision_model: str | None = field(default_factory=lambda: os.environ.get("LLM_VISION_MODEL") or None)
    llm_model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", "claude-sonnet-5-5"))


def get_settings() -> Settings:
    return Settings()
