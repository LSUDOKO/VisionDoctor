"""Op timing + CloudWatch Embedded Metric Format (EMF) emission.

Every OpenCV op that matters for the report is wrapped with ``timed("op")``; timings are kept in
a process-local registry (for benchmarks/tests) and, when ``VD_EMF=1``, printed as EMF JSON
lines which the CloudWatch agent / Lambda / ECS awslogs driver turn into metrics.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

NAMESPACE = "VisionDoctor"
_timings: dict[str, list[float]] = defaultdict(list)
_MAX_SAMPLES = 5000


def record(op: str, ms: float) -> None:
    buf = _timings[op]
    buf.append(ms)
    if len(buf) > _MAX_SAMPLES:
        del buf[: len(buf) - _MAX_SAMPLES]


@contextmanager
def timer(op: str) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        record(op, (time.perf_counter() - t0) * 1000.0)


def timed(op: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def deco(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with timer(op):
                return fn(*args, **kwargs)

        return wrapper

    return deco


def timings() -> dict[str, list[float]]:
    return {k: list(v) for k, v in _timings.items()}


def reset() -> None:
    _timings.clear()


def emit(metric: str, value: float, unit: str = "None", **dims: str) -> None:
    """Emit one EMF metric line (no-op unless VD_EMF=1)."""
    if os.environ.get("VD_EMF") != "1":
        return
    doc: dict[str, Any] = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {"Namespace": NAMESPACE, "Dimensions": [sorted(dims)], "Metrics": [{"Name": metric, "Unit": unit}]}
            ],
        },
        metric: value,
        **dims,
    }
    sys.stdout.write(json.dumps(doc) + "\n")
