"""OpenCV runtime checks: enforce OpenCV >= 5 and detect COOL (Cloud Optimized OpenCV)."""

from __future__ import annotations

import json
import os
import platform
import sys
from functools import lru_cache
from typing import Any

import cv2

MIN_MAJOR = 5


def assert_opencv5() -> None:
    major = int(cv2.__version__.split(".")[0])
    if major < MIN_MAJOR:
        sys.exit(
            f"VisionDoctor requires OpenCV >= {MIN_MAJOR}, found {cv2.__version__} at {cv2.__file__}. "
            "Install the 'opencv' extra or use the COOL venv (/opt/cool/venvs/python_3.12)."
        )


@lru_cache(maxsize=1)
def build_info() -> dict[str, Any]:
    info = cv2.getBuildInformation()
    path = str(cv2.__file__)
    return {
        "version": cv2.__version__,
        "cv2_file": path,
        # COOL installs under /opt/cool and links Arm KleidiCV (docs/05 §1).
        "is_cool": "/opt/cool" in path or "kleidicv" in info.lower(),
        "kleidicv": "kleidicv" in info.lower(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "threads": cv2.getNumThreads(),
        "dnn_engine_env": os.environ.get("OPENCV_FORCE_DNN_ENGINE"),
        "build_information": info,
    }


def summary() -> dict[str, Any]:
    b = build_info()
    return {k: v for k, v in b.items() if k != "build_information"}


assert_opencv5()

if __name__ == "__main__":
    print(json.dumps(summary(), indent=2))
