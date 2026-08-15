import json
import os
from typing import Any, Dict

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "server_ip": "192.168.64.150",
    "server_port": 9090,
    "hotkey": "pause",
    "model": "large-v3-turbo",
    "language": "ru",
    "initial_prompt": "Словения, Любляна, словенский язык, словенский, словенская, словенские, словенского, словенскому, словенском, словенцы, по-словенски.",
    "paste_method": "clipboard",
    "device_keyword": "H2n",
    "sample_rate": 16000
}


def load_config() -> Dict[str, Any]:
    """Загружает конфигурацию из config.json или создаёт её с дефолтными значениями."""
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
    except Exception as e:
        print(f"[CONFIG] Ошибка чтения config.json ({e}). Используются дефолтные параметры.")
        return DEFAULT_CONFIG.copy()


def save_config(config_data: Dict[str, Any]) -> None:
    """Сохраняет конфигурацию в config.json."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CONFIG] Ошибка сохранения config.json: {e}")
