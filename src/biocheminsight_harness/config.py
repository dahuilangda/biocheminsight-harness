"""Environment-driven settings; values are read at call time."""
from __future__ import annotations

import os


def biocheminsight_url() -> str:
    return os.environ.get("BIOCHEMINSIGHT_URL", "http://127.0.0.1:8000")


def paddleocr_url() -> str:
    return os.environ.get("PADDLEOCR_URL", "http://127.0.0.1:8010")


def harness_url() -> str:
    return os.environ.get("BIOCHEMINSIGHT_HARNESS_URL",
                          "http://127.0.0.1:8011")
