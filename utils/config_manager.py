"""
config_manager.py
─────────────────
앱 설정(API 키 등)을 로컬 파일에 저장/불러옵니다.
설정 파일 위치: 앱 폴더 내 config.json
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(data: dict) -> None:
    existing = load_config()
    existing.update(data)
    CONFIG_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def get_value(key: str, default: str = "") -> str:
    return load_config().get(key, default)
