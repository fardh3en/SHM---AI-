"""
Structured logging configuration for the SHM-AI platform.

Call configure_logging() once at application startup before any other imports
that use the logging module.
"""
import logging
import sys

from backend.app.config import get_settings


def configure_logging() -> None:
    """
    Configure root logger with consistent format across all modules.
    Respects LOG_LEVEL from settings and quiets noisy third-party loggers.
    """
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)-40s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # ── Suppress noisy third-party loggers ────────────────────────────────────
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DATABASE_ECHO else logging.WARNING
    )
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured — level={settings.LOG_LEVEL}, env={settings.APP_ENV}"
    )
