"""Ollama API client for local LLM integration."""
import json
import requests
from typing import Any, Dict, Generator, List, Optional


class OllamaClient:
    """Client for interacting with Ollama API."""
    
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host.rstrip("/")
        self.timeout = 30
    
    def is_available(self) -> bool:
        """Check if Ollama server is running."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List installed models."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                models.append({
                    "name": m.get("name", ""),
                    "size": m.get("size", 0),
                    "size_human": _format_size(m.get("size", 0)),
                    "modified_at": m.get("modified_at", ""),
                    "family": m.get("details", {}).get("family", ""),
                    "parameter_size": m.get("details", {}).get("parameter_size", ""),
                })
            return models
        except Exception as e:
            print(f"Error listing Ollama models: {e}")
            return []
    
    def pull_model(self, model_name: str) -> Generator[Dict[str, Any], None, None]:
        """Pull/download a model. Yields progress updates."""
        try:
            resp = requests.post(
                f"{self.host}/api/pull",
                json={"name": model_name, "stream": True},
                stream=True,
                timeout=None,  # No timeout for downloads
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        yield data
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            yield {"error": str(e)}
    
    def delete_model(self, model_name: str) -> bool:
        """Delete a model."""
        try:
            resp = requests.delete(
                f"{self.host}/api/delete",
                json={"name": model_name},
                timeout=self.timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False
    
    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Send a chat completion request."""
        try:
            resp = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": stream,
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "content": data.get("message", {}).get("content", ""),
                "model": data.get("model", model),
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                "done": data.get("done", True),
            }
        except requests.exceptions.Timeout:
            return {"error": "Request timed out", "content": ""}
        except Exception as e:
            return {"error": str(e), "content": ""}
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get info about a specific model."""
        try:
            resp = requests.post(
                f"{self.host}/api/show",
                json={"name": model_name},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None


def _format_size(size_bytes: int) -> str:
    """Format bytes to human readable size."""
    if size_bytes == 0:
        return "0B"
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"


# Convenience function for quick checks
def check_ollama_status(host: str = "http://localhost:11434") -> Dict[str, Any]:
    """Quick status check for Ollama service."""
    client = OllamaClient(host)
    available = client.is_available()
    models = client.list_models() if available else []
    return {
        "available": available,
        "host": host,
        "model_count": len(models),
        "models": models,
    }
