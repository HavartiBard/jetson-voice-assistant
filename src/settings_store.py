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
    # LLM Settings
    "llm_provider": "openai",  # "openai" or "ollama"
    "llm_model": "gpt-4o-mini",  # Model name for the selected provider
    "ollama_host": "http://localhost:11434",  # Ollama API endpoint
}

# Curated list of Ollama models suitable for Jetson (limited RAM)
RECOMMENDED_OLLAMA_MODELS = [
    {"name": "llama3.2:1b", "size": "1.3GB", "description": "Fast, general purpose"},
    {"name": "llama3.2:3b", "size": "2.0GB", "description": "Better quality, still fast"},
    {"name": "phi3:mini", "size": "2.3GB", "description": "Microsoft's efficient model"},
    {"name": "gemma2:2b", "size": "1.6GB", "description": "Google's compact model"},
    {"name": "qwen2.5:1.5b", "size": "1.0GB", "description": "Alibaba's efficient model"},
    {"name": "tinyllama", "size": "637MB", "description": "Ultra-lightweight"},
]

# OpenAI models
OPENAI_MODELS = [
    {"name": "gpt-4o-mini", "description": "Fast and affordable"},
    {"name": "gpt-4o", "description": "Most capable"},
    {"name": "gpt-4-turbo", "description": "High performance"},
    {"name": "gpt-3.5-turbo", "description": "Legacy, fast"},
]


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
