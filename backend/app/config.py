"""
Application configuration using Pydantic BaseSettings.

All settings are read from environment variables or a .env file.
Sensitive values (secrets, credentials) should NEVER be hardcoded here —
always override via environment variables in production.
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the project root (SHM-AI/) from this file's location
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Centralised, type-safe application settings.

    Hierarchy (highest → lowest priority):
        1. Environment variables
        2. .env file
        3. Field defaults defined here
    """

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    APP_NAME: str = "SHM-AI Platform"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = Field(
        default="development",
        pattern=r"^(development|staging|production)$",
        description="Runtime environment identifier.",
    )
    DEBUG: bool = True

    # ── API & CORS ─────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: list[str] | str = [
        "https://shm-ai-silk.vercel.app",
        "https://shm-p2k5964w-fardh3en.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:4173",
        "http://localhost:8000",
        "http://localhost:8501",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8501",
    ]
    ALLOWED_ORIGIN_REGEX: str | None = Field(
        default=r"^https:\/\/.*\.vercel\.app$",
        description="Regex pattern for dynamic origins (e.g. Vercel preview/branch deployments).",
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(
        default=False,
        description="Allow credentials (cookies, auth headers) in CORS. Disabled by default.",
    )
    CORS_ALLOW_METHODS: list[str] | str = Field(
        default=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        description="Allowed HTTP methods for CORS requests.",
    )
    CORS_ALLOW_HEADERS: list[str] | str = Field(
        default=["*"],
        description="Allowed HTTP headers for CORS requests.",
    )

    # ── Database ───────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/shm_ai.db",
        description=(
            "Async database URL. "
            "SQLite for development, postgresql+asyncpg:// for production."
        ),
    )
    DATABASE_ECHO: bool = Field(
        default=False,
        description="Log every SQL statement. Set true only for debugging.",
    )

    # ── Filesystem Paths ───────────────────────────────────────────────────────
    BASE_DIR: Path = _PROJECT_ROOT
    WEIGHTS_DIR: Path = _PROJECT_ROOT / "weights"
    REPORTS_DIR: Path = _PROJECT_ROOT / "reports"
    DATASETS_DIR: Path = _PROJECT_ROOT / "datasets"
    UPLOAD_DIR: Path = _PROJECT_ROOT / "data" / "uploads"

    # ── Vision Engine (Phase 2) ────────────────────────────────────────────────
    DEFAULT_MODEL_NAME: str = Field(
        default="yolo11n-seg.pt",
        description=(
            "YOLO model filename inside WEIGHTS_DIR. "
            "Ultralytics will auto-download pretrained weights if not found. "
            "Replace with your fine-tuned crack-detection model when available."
        ),
    )
    INFERENCE_DEVICE: str = Field(
        default="auto",
        description=(
            "Compute device for inference. "
            "'auto' detects CUDA and falls back to CPU automatically. "
            "Explicitly set 'cuda' or 'cpu' to override."
        ),
    )
    CONFIDENCE_THRESHOLD: float = Field(default=0.25, ge=0.0, le=1.0)
    IOU_THRESHOLD: float = Field(default=0.45, ge=0.0, le=1.0)

    # Sliced inference parameters (algorithm inherited from WhatTheCrack legacy)
    SLICE_HEIGHT: int = Field(default=640, ge=64)
    SLICE_WIDTH: int = Field(default=640, ge=64)
    SLICE_OVERLAP_RATIO: float = Field(default=0.4, ge=0.0, lt=1.0)
    SLICE_IF_LARGE: bool = Field(
        default=False,
        description=(
            "Whether to slice images into overlapping tiles. Defaults to False for "
            "responsive cloud CPU inference (single forward pass); set to True for "
            "ultra-high-resolution orthomosaic analysis."
        ),
    )

    # ── Logging ────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(
        default="INFO",
        pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
    )

    # ── Validators ─────────────────────────────────────────────────────────────
    @field_validator("ALLOWED_ORIGINS", "CORS_ALLOW_METHODS", "CORS_ALLOW_HEADERS", mode="before")
    @classmethod
    def parse_string_or_list(cls, v: Any) -> list[str]:
        """
        Parse comma-separated strings, JSON strings, or lists into a list of strings,
        stripping whitespace and trailing slashes for origins.
        """
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [
                            str(item).strip().rstrip("/")
                            for item in parsed
                            if str(item).strip()
                        ]
                except Exception:
                    pass
            return [item.strip().rstrip("/") for item in v.split(",") if item.strip()]
        if isinstance(v, (list, tuple, set)):
            return [str(item).strip().rstrip("/") for item in v if str(item).strip()]
        return v

    @field_validator("ALLOWED_ORIGIN_REGEX", mode="before")
    @classmethod
    def parse_origin_regex(cls, v: Any) -> str | None:
        """Allow None or empty string to disable regex matching."""
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            if not v or v.lower() in ("none", "null"):
                return None
        return str(v)

    @field_validator("WEIGHTS_DIR", "REPORTS_DIR", "DATASETS_DIR", "UPLOAD_DIR", mode="before")
    @classmethod
    def coerce_to_path(cls, v: Any) -> Path:
        """Allow string overrides from environment while keeping Path type."""
        return Path(v)

    def is_origin_allowed(self, origin: str | None) -> bool:
        """Check if an origin is permitted by ALLOWED_ORIGINS or ALLOWED_ORIGIN_REGEX."""
        if not origin:
            return False
        origin_clean = origin.strip().rstrip("/")
        if "*" in self.ALLOWED_ORIGINS or origin_clean in self.ALLOWED_ORIGINS:
            return True
        return bool(
            self.ALLOWED_ORIGIN_REGEX and re.fullmatch(self.ALLOWED_ORIGIN_REGEX, origin_clean)
        )

    @property
    def default_model_path(self) -> Path:
        """Resolved path to the active YOLO model weight file."""
        return self.WEIGHTS_DIR / self.DEFAULT_MODEL_NAME

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Cached settings singleton.

    Usage in FastAPI endpoints::

        from fastapi import Depends
        from backend.app.config import Settings, get_settings

        def my_endpoint(settings: Settings = Depends(get_settings)):
            ...
    """
    return Settings()
