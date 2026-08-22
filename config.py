import json
import os
import shutil
from typing import Any, Dict

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
CONFIG_EXAMPLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.example.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "server_ip": "192.168.1.100",
    "server_port": 9090,
    "hotkey": "f8",
    "model": "large-v3-turbo",
    "language": "ru",
    "initial_prompt": "",
    "custom_replacements": {},
    "translation_enabled": True,
    "paste_method": "clipboard",
    "device_keyword": "",
    "sample_rate": 16000
}


def load_config() -> Dict[str, Any]:
    """Loads configuration from config.json or initializes it from config.example.json."""
    if not os.path.exists(CONFIG_PATH):
        if os.path.exists(CONFIG_EXAMPLE_PATH):
            try:
                shutil.copy(CONFIG_EXAMPLE_PATH, CONFIG_PATH)
            except Exception:
                save_config(DEFAULT_CONFIG)
        else:
            save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
    except Exception as e:
        print(f"[CONFIG] Error reading config.json ({e}). Using default settings.")
        return DEFAULT_CONFIG.copy()


def save_config(config_data: Dict[str, Any]) -> None:
    """Saves configuration to config.json."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CONFIG] Error saving config.json: {e}")
