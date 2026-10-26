"""Structured JSON logging (structlog) with trace/camera/incident context."""

from __future__ import annotations

import logging
import os
from typing import Any

import structlog


def setup(level: str | None = None) -> None:
    lvl = getattr(logging, (level or os.environ.get("VD_LOG_LEVEL", "INFO")).upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=lvl)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(lvl),
    )


def get(name: str = "visiondoctor") -> Any:
    return structlog.get_logger(name)
