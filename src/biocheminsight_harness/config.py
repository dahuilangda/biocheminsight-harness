"""Deployment connection settings; read from env vars or config file."""
from __future__ import annotations

import json
import os
from pathlib import Path

_CONFIG_FILE = Path.home() / ".biocheminsight" / "config.json"


def _config() -> dict:
    if _CONFIG_FILE.is_file():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _setting(env_key: str, file_key: str, default: str) -> str:
    return os.environ.get(env_key) or _config().get(file_key, default)


def biocheminsight_url() -> str:
    return _setting("BIOCHEMINSIGHT_URL", "biocheminsight_url",
                    "http://127.0.0.1:8000")


def paddleocr_url() -> str:
    return _setting("PADDLEOCR_URL", "paddleocr_url",
                    "http://127.0.0.1:8010")


def harness_url() -> str:
    return _setting("BIOCHEMINSIGHT_HARNESS_URL", "harness_url",
                    "http://127.0.0.1:8011")


def save_deployment(url: str, paddle_url: str | None = None,
                    harness_url_override: str | None = None) -> dict:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg = _config()
    cfg["biocheminsight_url"] = url
    if paddle_url:
        cfg["paddleocr_url"] = paddle_url
    if harness_url_override:
        cfg["harness_url"] = harness_url_override
    _CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg
