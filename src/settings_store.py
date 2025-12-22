import json
import os
from typing import Any, Dict


DEFAULT_SETTINGS: Dict[str, Any] = {
    "openai_api_key": "",
    "wake_word": "jetson",
    "whisper_mode": "local",
    "whisper_model_size": "small",
    "whisper_language": "en",
    "audio_sample_rate": 16000,
    "audio_channels": 1,
    "audio_record_seconds": 4,
}


def _settings_path() -> str:
    # src/ -> project_root/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "config", "settings.json")


def load_settings() -> Dict[str, Any]:
    path = _settings_path()
    settings = dict(DEFAULT_SETTINGS)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            settings.update({k: v for k, v in data.items() if v is not None})
    except FileNotFoundError:
        pass
    except Exception:
        # Keep defaults if file is corrupt or unreadable
        pass

    return settings


def save_settings(new_settings: Dict[str, Any]) -> Dict[str, Any]:
    path = _settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    merged = dict(DEFAULT_SETTINGS)
    merged.update({k: v for k, v in new_settings.items() if v is not None})

    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, sort_keys=True)
        f.write("\n")

    return merged
