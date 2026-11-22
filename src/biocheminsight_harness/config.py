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


def ocr_url() -> str:
    return _setting("OCR_URL", "ocr_url",
                    _setting("PADDLEOCR_URL", "paddleocr_url",
                             "http://127.0.0.1:8010"))


def paddleocr_url() -> str:
    return ocr_url()


def harness_url() -> str:
    return _setting("BIOCHEMINSIGHT_HARNESS_URL", "harness_url",
                    "http://127.0.0.1:8011")


def perception_batch_size() -> int:
    raw = os.environ.get("BIOCHEMINSIGHT_PERCEPTION_BATCH", "")
    try:
        size = int(raw)
    except ValueError:
        size = 8
    return max(1, size)


def save_deployment(url: str, ocr_url: str | None = None,
                    harness_url_override: str | None = None) -> dict:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg = _config()
    cfg["biocheminsight_url"] = url
    if ocr_url:
        cfg["ocr_url"] = ocr_url
        cfg["paddleocr_url"] = ocr_url
    if harness_url_override:
        cfg["harness_url"] = harness_url_override
    _CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def auth_credentials() -> tuple[str, str] | None:
    return auth()


def auth() -> tuple[str, str] | None:
    user = _setting("BIOCHEMINSIGHT_USER", "biocheminsight_user", "")
    password = _setting("BIOCHEMINSIGHT_PASS", "biocheminsight_pass", "")
    if user and password:
        return (user, password)
    return None


def save_auth(user: str, password: str) -> dict:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg = _config()
    cfg["biocheminsight_user"] = user
    cfg["biocheminsight_pass"] = password
    _CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return {"saved": True}
