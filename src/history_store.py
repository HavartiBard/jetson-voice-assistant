import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List
from threading import Lock

MAX_STATS_HISTORY = 720  # 12 hours at 1 sample/min
MAX_QUERY_HISTORY = 500

_lock = Lock()


def _history_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "config", "history.json")


def _load_history() -> Dict[str, Any]:
    path = _history_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"stats": [], "queries": []}


def _save_history(data: Dict[str, Any]) -> None:
    path = _history_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def record_stats(cpu_percent: float, memory_percent: float, disk_percent: float) -> None:
    """Record a system stats snapshot."""
    with _lock:
        history = _load_history()
        history["stats"].append({
            "ts": time.time(),
            "cpu": round(cpu_percent, 1),
            "mem": round(memory_percent, 1),
            "disk": round(disk_percent, 1),
        })
        # Trim old entries
        history["stats"] = history["stats"][-MAX_STATS_HISTORY:]
        _save_history(history)


def get_stats_history(limit: int = 60) -> List[Dict[str, Any]]:
    """Get recent stats history."""
    with _lock:
        history = _load_history()
        return history.get("stats", [])[-limit:]


def record_query(transcription: str, response: str, duration_ms: int = 0) -> None:
    """Record a voice query and response."""
    with _lock:
        history = _load_history()
        history["queries"].append({
            "ts": time.time(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "query": transcription,
            "response": response[:500],  # Truncate long responses
            "duration_ms": duration_ms,
        })
        history["queries"] = history["queries"][-MAX_QUERY_HISTORY:]
        _save_history(history)


def get_query_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent query history, newest first."""
    with _lock:
        history = _load_history()
        queries = history.get("queries", [])
        return list(reversed(queries[-limit:]))


def clear_query_history() -> None:
    """Clear all query history."""
    with _lock:
        history = _load_history()
        history["queries"] = []
        _save_history(history)
