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


def record_query(
    transcription: str,
    response: str,
    duration_ms: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    model: str = "",
) -> None:
    """Record a voice query and response with optional token usage."""
    with _lock:
        history = _load_history()
        history["queries"].append({
            "ts": time.time(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "query": transcription,
            "response": response[:500],  # Truncate long responses
            "duration_ms": duration_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model": model,
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


def get_query_analytics() -> Dict[str, Any]:
    """Get aggregated query analytics for dashboard."""
    with _lock:
        history = _load_history()
        queries = history.get("queries", [])
        
        if not queries:
            return {
                "total_queries": 0,
                "total_tokens": 0,
                "avg_duration_ms": 0,
                "avg_tokens_per_query": 0,
                "queries_today": 0,
                "queries_this_week": 0,
                "queries_by_day": [],
                "queries_by_hour": [0] * 24,
            }
        
        now = time.time()
        day_ago = now - 86400
        week_ago = now - 604800
        
        total_tokens = sum(q.get("total_tokens", 0) for q in queries)
        total_duration = sum(q.get("duration_ms", 0) for q in queries)
        queries_today = sum(1 for q in queries if q.get("ts", 0) > day_ago)
        queries_this_week = sum(1 for q in queries if q.get("ts", 0) > week_ago)
        
        # Queries by hour (last 24h)
        queries_by_hour = [0] * 24
        for q in queries:
            if q.get("ts", 0) > day_ago:
                hour = datetime.fromtimestamp(q["ts"]).hour
                queries_by_hour[hour] += 1
        
        # Queries by day (last 7 days)
        queries_by_day = {}
        for q in queries:
            if q.get("ts", 0) > week_ago:
                day = datetime.fromtimestamp(q["ts"]).strftime("%Y-%m-%d")
                queries_by_day[day] = queries_by_day.get(day, 0) + 1
        
        # Convert to sorted list
        sorted_days = sorted(queries_by_day.items())
        
        return {
            "total_queries": len(queries),
            "total_tokens": total_tokens,
            "avg_duration_ms": round(total_duration / len(queries)) if queries else 0,
            "avg_tokens_per_query": round(total_tokens / len(queries)) if queries else 0,
            "queries_today": queries_today,
            "queries_this_week": queries_this_week,
            "queries_by_day": sorted_days,
            "queries_by_hour": queries_by_hour,
        }
