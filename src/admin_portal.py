from flask import Flask, jsonify, redirect, render_template_string, request, url_for
import psutil
import json
import os
import subprocess
import socket
import time as time_module
from datetime import datetime

from settings_store import load_settings, save_settings, RECOMMENDED_OLLAMA_MODELS, OPENAI_MODELS, TTS_PROVIDERS
from history_store import get_stats_history, get_query_history, record_stats, clear_query_history, get_query_analytics
from audio_devices import get_audio_input_devices, get_audio_output_devices, get_card_number_from_device, get_mute_status
from ollama_client import OllamaClient, check_ollama_status
from hardware_profiles import get_device_identity, get_hardware_profile

# Reload signal file path
RELOAD_SIGNAL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'config', '.reload_signal'
)


app = Flask(__name__)


BASE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ title }}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {
      --bg-primary: #0f0f0f;
      --bg-secondary: #1a1a1a;
      --bg-card: #242424;
      --bg-hover: #2d2d2d;
      --text-primary: #ffffff;
      --text-secondary: #a0a0a0;
      --text-muted: #666666;
      --accent: #6366f1;
      --accent-hover: #818cf8;
      --success: #22c55e;
      --warning: #f59e0b;
      --danger: #ef4444;
      --border: #333333;
      --border-light: #404040;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg-primary);
      color: var(--text-primary);
      min-height: 100vh;
      line-height: 1.6;
    }

    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }

    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 20px 0;
      margin-bottom: 32px;
      border-bottom: 1px solid var(--border);
    }

    .logo {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .logo-icon {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, var(--accent) 0%, #a855f7 100%);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
    }

    .logo h1 {
      font-size: 1.5rem;
      font-weight: 600;
      background: linear-gradient(135deg, var(--text-primary) 0%, var(--text-secondary) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    nav {
      display: flex;
      gap: 8px;
    }

    nav a {
      color: var(--text-secondary);
      text-decoration: none;
      padding: 10px 18px;
      border-radius: 8px;
      font-weight: 500;
      font-size: 0.95rem;
      transition: all 0.2s ease;
    }

    nav a:hover, nav a.active {
      background: var(--bg-card);
      color: var(--text-primary);
    }

    nav a.active {
      background: var(--accent);
      color: white;
    }

    .card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      margin-bottom: 24px;
      transition: all 0.2s ease;
    }

    .card:hover {
      border-color: var(--border-light);
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }

    .card-title {
      font-size: 1.1rem;
      font-weight: 600;
      color: var(--text-primary);
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }

    .stat-card {
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      text-align: center;
      transition: all 0.3s ease;
    }

    .stat-card:hover {
      transform: translateY(-2px);
      border-color: var(--accent);
    }

    .stat-value {
      font-size: 2.5rem;
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent) 0%, #a855f7 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .stat-label {
      font-size: 0.85rem;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-top: 4px;
    }

    .stat-detail {
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-top: 8px;
    }

    .chart-container {
      position: relative;
      height: 300px;
      margin-top: 16px;
    }

    .form-group {
      margin-bottom: 20px;
    }

    .form-row {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 20px;
    }

    label {
      display: block;
      font-weight: 500;
      color: var(--text-primary);
      margin-bottom: 8px;
      font-size: 0.95rem;
    }

    input, select {
      width: 100%;
      padding: 12px 16px;
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 10px;
      color: var(--text-primary);
      font-size: 0.95rem;
      transition: all 0.2s ease;
    }

    input:focus, select:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
    }

    input::placeholder {
      color: var(--text-muted);
    }

    .hint {
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-top: 6px;
    }

    .hint a {
      color: var(--accent);
      text-decoration: none;
    }

    .hint a:hover {
      text-decoration: underline;
    }

    button, .btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 12px 24px;
      background: linear-gradient(135deg, var(--accent) 0%, #7c3aed 100%);
      border: none;
      border-radius: 10px;
      color: white;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
    }

    button:hover, .btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }

    .btn-secondary {
      background: var(--bg-secondary);
      border: 1px solid var(--border);
    }

    .btn-secondary:hover {
      background: var(--bg-hover);
      box-shadow: none;
    }

    .btn-danger {
      background: var(--danger);
    }

    .alert {
      padding: 16px 20px;
      border-radius: 10px;
      margin-bottom: 24px;
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .alert-success {
      background: rgba(34, 197, 94, 0.1);
      border: 1px solid rgba(34, 197, 94, 0.3);
      color: var(--success);
    }

    .query-table {
      width: 100%;
      border-collapse: collapse;
    }

    .query-table th, .query-table td {
      padding: 14px 16px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }

    .query-table th {
      font-weight: 600;
      color: var(--text-secondary);
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .query-table tr:hover td {
      background: var(--bg-hover);
    }

    .query-text {
      max-width: 300px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .time-badge {
      display: inline-block;
      padding: 4px 10px;
      background: var(--bg-secondary);
      border-radius: 6px;
      font-size: 0.8rem;
      color: var(--text-secondary);
    }

    .empty-state {
      text-align: center;
      padding: 60px 20px;
      color: var(--text-muted);
    }

    .empty-state-icon {
      font-size: 48px;
      margin-bottom: 16px;
      opacity: 0.5;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .card {
      animation: fadeIn 0.3s ease;
    }

    .progress-ring {
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 8px;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="logo">
        <div class="logo-icon">🎙️</div>
        <h1>Jetson Assistant</h1>
      </div>
      <nav>
        <a href="{{ url_for('dashboard') }}" {% if active_page == 'dashboard' %}class="active"{% endif %}>Dashboard</a>
        <a href="{{ url_for('devices') }}" {% if active_page == 'devices' %}class="active"{% endif %}>Devices</a>
        <a href="{{ url_for('settings') }}" {% if active_page == 'settings' %}class="active"{% endif %}>Settings</a>
        <a href="{{ url_for('llm_settings') }}" {% if active_page == 'llm' %}class="active"{% endif %}>LLM Models</a>
        <a href="{{ url_for('system_stats') }}" {% if active_page == 'stats' %}class="active"{% endif %}>System Stats</a>
        <a href="{{ url_for('query_history') }}" {% if active_page == 'history' %}class="active"{% endif %}>Query History</a>
      </nav>
    </header>
    {% if flash %}
    <div class="alert alert-success">
      <span>✓</span> {{ flash }}
    </div>
    {% endif %}
    {{ body | safe }}
  </div>
</body>
</html>
"""


@app.get("/")
def root():
    return redirect(url_for("dashboard"))


def _is_running_in_container() -> bool:
    """Detect if running inside a Docker container."""
    # Check for .dockerenv file (most reliable)
    if os.path.exists('/.dockerenv'):
        return True
    # Check cgroup for docker/containerd (older Docker versions)
    try:
        with open('/proc/1/cgroup', 'r') as f:
            content = f.read()
            if 'docker' in content or 'containerd' in content:
                return True
    except Exception:
        pass
    return False


def _check_service_status(service_name: str) -> dict:
    """Check service status - works in both native and container environments."""
    # In container mode, we can only reliably check our own process
    if _is_running_in_container():
        # Portal is obviously running if serving this request
        if "portal" in service_name:
            return {"name": service_name, "status": "running", "ok": True}
        # For assistant, check if config/history files are being updated (indirect check)
        # or just report container mode status
        if "assistant" in service_name:
            # Check if assistant process is in this container (single-container mode)
            try:
                result = subprocess.run(
                    ['pgrep', '-f', 'assistant.py'],
                    capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    return {"name": service_name, "status": "running", "ok": True}
            except Exception:
                pass
            # Multi-container mode: assume running (can't check other container)
            return {"name": service_name, "status": "running (container)", "ok": True}
        return {"name": service_name, "status": "container mode", "ok": True}
    
    # Native mode: use systemctl
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', service_name],
            capture_output=True, text=True, timeout=5
        )
        is_active = result.stdout.strip() == 'active'
        return {"name": service_name, "status": "running" if is_active else "stopped", "ok": is_active}
    except Exception:
        return {"name": service_name, "status": "unknown", "ok": False}


def _check_openai_status() -> dict:
    """Check OpenAI API connectivity."""
    settings = load_settings()
    api_key = settings.get('openai_api_key', '')
    if not api_key:
        return {"name": "OpenAI API", "status": "not configured", "ok": False}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        start = time_module.time()
        client.models.list()
        latency = int((time_module.time() - start) * 1000)
        return {"name": "OpenAI API", "status": f"connected ({latency}ms)", "ok": True, "latency": latency}
    except Exception as e:
        return {"name": "OpenAI API", "status": f"error: {str(e)[:30]}", "ok": False}


def _check_internet() -> dict:
    """Check internet connectivity."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return {"name": "Internet", "status": "connected", "ok": True}
    except OSError:
        return {"name": "Internet", "status": "offline", "ok": False}


def _check_audio_devices() -> dict:
    """Check audio device availability."""
    try:
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True, timeout=5)
        has_devices = 'card' in result.stdout.lower()
        return {"name": "Audio Devices", "status": "available" if has_devices else "not found", "ok": has_devices}
    except Exception:
        return {"name": "Audio Devices", "status": "error", "ok": False}


def _get_jetson_stats() -> dict:
    """Get Jetson-specific stats (temperature, GPU if available)."""
    stats = {"temperatures": [], "gpu_usage": None, "uptime": ""}
    
    # Get CPU temperatures from thermal zones
    try:
        thermal_zones = []
        for i in range(10):
            temp_path = f"/sys/class/thermal/thermal_zone{i}/temp"
            type_path = f"/sys/class/thermal/thermal_zone{i}/type"
            if os.path.exists(temp_path):
                with open(temp_path) as f:
                    temp = int(f.read().strip()) / 1000.0
                zone_type = "Zone"
                if os.path.exists(type_path):
                    with open(type_path) as f:
                        zone_type = f.read().strip()
                thermal_zones.append({"name": zone_type, "temp": round(temp, 1)})
        stats["temperatures"] = thermal_zones
    except Exception:
        pass
    
    # Get uptime
    try:
        with open('/proc/uptime') as f:
            uptime_seconds = float(f.read().split()[0])
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            if days > 0:
                stats["uptime"] = f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                stats["uptime"] = f"{hours}h {minutes}m"
            else:
                stats["uptime"] = f"{minutes}m"
    except Exception:
        stats["uptime"] = "unknown"
    
    # Try to get GPU usage (tegrastats for Jetson)
    try:
        # Check for NVIDIA GPU via nvidia-smi (works on desktop + some Jetsons)
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            stats["gpu_usage"] = int(result.stdout.strip().split('\n')[0])
    except Exception:
        pass
    
    return stats


def _run_amixer(args: list[str], timeout: int = 3) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["amixer", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _amixer_card_args_from_device(device_id: str) -> tuple[bool, list[str] | None, str | None]:
    card = get_card_number_from_device(device_id)
    if not card:
        return False, None, "No ALSA card could be determined for this device"
    return True, ["-c", str(card)], None


def _parse_amixer_percent(stdout: str) -> int | None:
    import re

    m = re.search(r"\[(\d+)%\]", stdout)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _parse_amixer_switch(stdout: str) -> bool | None:
    import re

    m = re.search(r"\[(on|off)\]", stdout, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1).lower() == "on"


def _list_mixer_controls(card: str, timeout: int = 3) -> list[str]:
    try:
        result = _run_amixer(["-c", card, "scontrols"], timeout=timeout)
        if result.returncode != 0:
            return []
        names: list[str] = []
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line.startswith("Simple mixer control"):
                continue
            # Simple mixer control 'Master',0
            start = line.find("'")
            end = line.rfind("'")
            if start != -1 and end != -1 and end > start:
                names.append(line[start + 1 : end])
        return names
    except Exception:
        return []


def _choose_reasonable_control(card: str, prefer: list[str]) -> str | None:
    controls = _list_mixer_controls(card)
    lowered = {c.lower(): c for c in controls}
    for p in prefer:
        if p.lower() in lowered:
            return lowered[p.lower()]
    return controls[0] if controls else None


def _is_internal_audio_device_name(name: str) -> bool:
    n = (name or "").lower()
    # Heuristic: hide Jetson internal/board audio endpoints by default.
    # Keep USB devices visible.
    needles = [
        "jetson",
        "orin",
        "nvidia",
        "tegra",
        "ape",
        "hdmi",
        "i2s",
        "spdif",
    ]
    return any(x in n for x in needles)


def _filter_audio_devices(devices: list, show_all: bool = False) -> list:
    """Filter audio devices, hiding internal Jetson devices unless show_all is True."""
    if show_all:
        return devices
    return [d for d in devices if not _is_internal_audio_device_name(d.get("name", ""))]


@app.get("/dashboard")
def dashboard():
    """Main dashboard with service status and analytics."""
    # Service status checks
    services = [
        _check_service_status("voice-assistant"),
        _check_service_status("voice-assistant-portal"),
        _check_openai_status(),
        _check_internet(),
        _check_audio_devices(),
    ]
    
    # Get microphone mute status
    settings = load_settings()
    audio_input_device = settings.get('audio_input_device', 'default')
    mute_status = get_mute_status(audio_input_device)
    
    # System metrics
    vm = psutil.virtual_memory()
    du = psutil.disk_usage("/")
    cpu_percent = psutil.cpu_percent(interval=0.3)
    jetson_stats = _get_jetson_stats()
    
    # Query analytics
    analytics = get_query_analytics()
    
    # Overall health
    all_ok = all(s["ok"] for s in services)
    health_status = "healthy" if all_ok else "degraded"
    
    body = render_template_string(
        """
<div class="dashboard-grid">
  <!-- Status Banner Row -->
  <div class="status-banner-row">
    <!-- Health Status Banner -->
    <div class="health-banner {{ 'health-ok' if health_status == 'healthy' else 'health-warn' }}">
      <div class="health-icon">{{ '✓' if health_status == 'healthy' else '⚠' }}</div>
      <div class="health-text">
        <strong>System {{ health_status.title() }}</strong>
        <span>Uptime: {{ jetson_stats.uptime }}</span>
      </div>
    </div>

    <!-- Microphone Status Card -->
    <div id="mute-banner" class="mic-status-card {{ 'mic-muted' if mute_status.is_muted else 'mic-active' }}">
      <div class="mic-icon">{{ '🔇' if mute_status.is_muted else '🎙️' }}</div>
      <div class="mic-text">
        <strong>{{ 'Muted' if mute_status.is_muted else 'Listening' }}</strong>
        <span>{{ 'Paused' if mute_status.is_muted else 'Active' }}</span>
      </div>
    </div>
  </div>

  <!-- Service Status Grid -->
  <div class="card">
    <div class="card-header">
      <h2 class="card-title">Service Status</h2>
    </div>
    <div class="service-grid">
      {% for svc in services %}
      <div class="service-item {{ 'service-ok' if svc.ok else 'service-err' }}">
        <div class="service-indicator"></div>
        <div class="service-info">
          <div class="service-name">{{ svc.name }}</div>
          <div class="service-status">{{ svc.status }}</div>
        </div>
      </div>
      {% endfor %}
    </div>
  </div>

  <!-- Quick Stats Row -->
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-value">{{ cpu_percent }}%</div>
      <div class="stat-label">CPU</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{{ vm.percent }}%</div>
      <div class="stat-label">Memory</div>
      <div class="stat-detail">{{ (vm.used/1024/1024/1024)|round(1) }}GB / {{ (vm.total/1024/1024/1024)|round(1) }}GB</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{{ du.percent }}%</div>
      <div class="stat-label">Disk</div>
    </div>
    {% if jetson_stats.gpu_usage is not none %}
    <div class="stat-card">
      <div class="stat-value">{{ jetson_stats.gpu_usage }}%</div>
      <div class="stat-label">GPU</div>
    </div>
    {% endif %}
    {% if jetson_stats.temperatures %}
    <div class="stat-card">
      <div class="stat-value">{{ jetson_stats.temperatures[0].temp }}°C</div>
      <div class="stat-label">{{ jetson_stats.temperatures[0].name }}</div>
    </div>
    {% endif %}
  </div>

  <!-- Usage Analytics -->
  <div class="card">
    <div class="card-header">
      <h2 class="card-title">Usage Analytics</h2>
    </div>
    <div class="analytics-grid">
      <div class="analytics-stat">
        <div class="analytics-value">{{ analytics.total_queries }}</div>
        <div class="analytics-label">Total Queries</div>
      </div>
      <div class="analytics-stat">
        <div class="analytics-value">{{ analytics.queries_today }}</div>
        <div class="analytics-label">Today</div>
      </div>
      <div class="analytics-stat">
        <div class="analytics-value">{{ analytics.queries_this_week }}</div>
        <div class="analytics-label">This Week</div>
      </div>
      <div class="analytics-stat">
        <div class="analytics-value">{{ analytics.total_tokens | default(0) }}</div>
        <div class="analytics-label">Total Tokens</div>
      </div>
      <div class="analytics-stat">
        <div class="analytics-value">{{ analytics.avg_duration_ms }}ms</div>
        <div class="analytics-label">Avg Response</div>
      </div>
      <div class="analytics-stat">
        <div class="analytics-value">{{ analytics.avg_tokens_per_query }}</div>
        <div class="analytics-label">Avg Tokens/Query</div>
      </div>
    </div>
  </div>

  <!-- Queries Over Time Chart -->
  <div class="card">
    <div class="card-header">
      <h2 class="card-title">Queries Over Time</h2>
      <span class="time-badge">Last 7 days</span>
    </div>
    <div class="chart-container">
      <canvas id="queriesChart"></canvas>
    </div>
  </div>

  <!-- Activity by Hour -->
  <div class="card">
    <div class="card-header">
      <h2 class="card-title">Activity by Hour</h2>
      <span class="time-badge">Last 24 hours</span>
    </div>
    <div class="chart-container" style="height: 200px;">
      <canvas id="hourlyChart"></canvas>
    </div>
  </div>

  {% if jetson_stats.temperatures|length > 1 %}
  <!-- Temperature Details -->
  <div class="card">
    <div class="card-header">
      <h2 class="card-title">Thermal Zones</h2>
    </div>
    <div class="temp-grid">
      {% for t in jetson_stats.temperatures %}
      <div class="temp-item">
        <div class="temp-value {{ 'temp-hot' if t.temp > 70 else ('temp-warm' if t.temp > 50 else 'temp-cool') }}">{{ t.temp }}°C</div>
        <div class="temp-label">{{ t.name }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
  {% endif %}
</div>

<style>
  .dashboard-grid { display: flex; flex-direction: column; gap: 24px; }
  .health-banner {
    display: flex; align-items: center; gap: 16px;
    padding: 20px 24px; border-radius: 16px;
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(34, 197, 94, 0.05) 100%);
    border: 1px solid rgba(34, 197, 94, 0.3);
  }
  .health-warn {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(245, 158, 11, 0.05) 100%);
    border-color: rgba(245, 158, 11, 0.3);
  }
  .health-icon { font-size: 32px; }
  .health-ok .health-icon { color: var(--success); }
  .health-warn .health-icon { color: var(--warning); }
  .health-text { display: flex; flex-direction: column; }
  .health-text strong { font-size: 1.2rem; }
  .health-text span { color: var(--text-secondary); font-size: 0.9rem; }
  
  .status-banner-row {
    display: flex; gap: 16px; align-items: stretch;
  }
  .status-banner-row .health-banner { flex: 1; }
  
  .mic-status-card {
    display: flex; align-items: center; gap: 12px;
    padding: 16px 20px; border-radius: 12px;
    min-width: 140px;
  }
  .mic-muted {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(239, 68, 68, 0.05) 100%);
    border: 1px solid rgba(239, 68, 68, 0.3);
  }
  .mic-active {
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(34, 197, 94, 0.02) 100%);
    border: 1px solid rgba(34, 197, 94, 0.2);
  }
  .mic-icon { font-size: 24px; }
  .mic-text { display: flex; flex-direction: column; }
  .mic-text strong { font-size: 1rem; }
  .mic-muted .mic-text strong { color: var(--danger); }
  .mic-active .mic-text strong { color: var(--success); }
  .mic-text span { color: var(--text-secondary); font-size: 0.8rem; }
  
  .service-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
  .service-item {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 16px; background: var(--bg-secondary);
    border-radius: 10px; border: 1px solid var(--border);
  }
  .service-indicator { width: 10px; height: 10px; border-radius: 50%; }
  .service-ok .service-indicator { background: var(--success); box-shadow: 0 0 8px var(--success); }
  .service-err .service-indicator { background: var(--danger); box-shadow: 0 0 8px var(--danger); }
  .service-name { font-weight: 500; }
  .service-status { font-size: 0.8rem; color: var(--text-muted); }
  
  .analytics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 16px; }
  .analytics-stat { text-align: center; padding: 16px; background: var(--bg-secondary); border-radius: 10px; }
  .analytics-value { font-size: 1.8rem; font-weight: 700; color: var(--accent); }
  .analytics-label { font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px; }
  
  .temp-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 12px; }
  .temp-item { text-align: center; padding: 12px; background: var(--bg-secondary); border-radius: 8px; }
  .temp-value { font-size: 1.4rem; font-weight: 600; }
  .temp-cool { color: var(--success); }
  .temp-warm { color: var(--warning); }
  .temp-hot { color: var(--danger); }
  .temp-label { font-size: 0.75rem; color: var(--text-muted); margin-top: 4px; }
</style>

<script>
// Queries by day chart
const dailyCtx = document.getElementById('queriesChart').getContext('2d');
const dailyData = {{ analytics.queries_by_day | tojson }};
new Chart(dailyCtx, {
  type: 'bar',
  data: {
    labels: dailyData.map(d => d[0]),
    datasets: [{
      label: 'Queries',
      data: dailyData.map(d => d[1]),
      backgroundColor: 'rgba(99, 102, 241, 0.6)',
      borderColor: '#6366f1',
      borderWidth: 1,
      borderRadius: 6,
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { color: '#333' }, ticks: { color: '#666' } },
      y: { beginAtZero: true, grid: { color: '#333' }, ticks: { color: '#666', stepSize: 1 } }
    }
  }
});

// Hourly activity chart
const hourlyCtx = document.getElementById('hourlyChart').getContext('2d');
const hourlyData = {{ analytics.queries_by_hour | tojson }};
const hourLabels = Array.from({length: 24}, (_, i) => i.toString().padStart(2, '0') + ':00');
new Chart(hourlyCtx, {
  type: 'bar',
  data: {
    labels: hourLabels,
    datasets: [{
      label: 'Queries',
      data: hourlyData,
      backgroundColor: 'rgba(168, 85, 247, 0.6)',
      borderColor: '#a855f7',
      borderWidth: 1,
      borderRadius: 4,
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false }, ticks: { color: '#666', maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } },
      y: { beginAtZero: true, grid: { color: '#333' }, ticks: { color: '#666', stepSize: 1 } }
    }
  }
});

// Auto-refresh mute status every 2 seconds
function updateMuteStatus() {
  fetch('/api/mute-status')
    .then(r => r.json())
    .then(data => {
      const card = document.getElementById('mute-banner');
      if (card) {
        card.className = 'mic-status-card ' + (data.is_muted ? 'mic-muted' : 'mic-active');
        card.querySelector('.mic-icon').textContent = data.is_muted ? '🔇' : '🎙️';
        card.querySelector('.mic-text strong').textContent = data.is_muted ? 'Muted' : 'Listening';
        card.querySelector('.mic-text span').textContent = data.is_muted ? 'Paused' : 'Active';
      }
    })
    .catch(e => console.log('Mute status fetch error:', e));
}
setInterval(updateMuteStatus, 2000);
</script>
""",
        services=services,
        health_status=health_status,
        mute_status=mute_status,
        vm=vm,
        du=du,
        cpu_percent=cpu_percent,
        jetson_stats=jetson_stats,
        analytics=analytics,
    )

    return render_template_string(BASE_TEMPLATE, title="Dashboard | Jetson Assistant", body=body, flash=None, active_page="dashboard")


@app.get("/devices")
def devices():
    show_all = (request.args.get("show_all") or "").strip() in ("1", "true", "yes", "on")
    body = render_template_string(
        """
<div class="card">
  <div class="card-header">
    <h2 class="card-title">Devices</h2>
    <div style="display:flex; gap: 10px; align-items:center;">
      <button type="button" class="btn btn-secondary" onclick="refreshDevices()">↻ Refresh</button>
      <button type="button" class="btn btn-secondary" onclick="toggleShowAll()" id="show-all-btn">—</button>
    </div>
  </div>
  <div class="hint">Shows detected audio devices and basic controls for the currently selected input/output devices.</div>
</div>

<div class="card">
  <div class="card-header">
    <h2 class="card-title">Active Selection</h2>
  </div>
  <div class="form-row">
    <div>
      <label>Input Device (Settings)</label>
      <div id="active-input" class="time-badge">Loading…</div>
      <div id="active-input-profile" class="hint"></div>
    </div>
    <div>
      <label>Output Device (Settings)</label>
      <div id="active-output" class="time-badge">Loading…</div>
      <div id="active-output-profile" class="hint"></div>
    </div>
    <div>
      <label>Microphone Mute</label>
      <div id="active-mute" class="time-badge">Loading…</div>
      <div class="hint">Mute status is reported by the assistant.</div>
    </div>
  </div>
</div>

<div class="card">
  <div class="card-header">
    <h2 class="card-title">Output Controls</h2>
  </div>
  <div class="form-row">
    <div>
      <label for="output-control">Mixer Control</label>
      <select id="output-control"></select>
      <div class="hint">If the default control doesn’t work, pick another.</div>
    </div>
    <div>
      <label for="output-volume">Volume</label>
      <input id="output-volume" type="range" min="0" max="100" value="10" oninput="onOutputVolumePreview()" onchange="setOutputVolume()" />
      <div class="hint"><span id="output-volume-label">—</span></div>
    </div>
    <div>
      <label>&nbsp;</label>
      <button type="button" class="btn btn-secondary" onclick="toggleOutputMute()">Toggle Mute</button>
      <div class="hint" id="output-mute-state">—</div>
    </div>
  </div>
</div>

<div class="card">
  <div class="card-header">
    <h2 class="card-title">Input Controls</h2>
  </div>
  <div class="form-row">
    <div>
      <label for="input-control">Mixer Control</label>
      <select id="input-control"></select>
      <div class="hint">Look for controls like “Mic”, “Capture”, “Input”.</div>
    </div>
    <div>
      <label for="input-gain">Sensitivity / Gain</label>
      <input id="input-gain" type="range" min="0" max="100" value="50" oninput="onInputGainPreview()" onchange="setInputGain()" />
      <div class="hint"><span id="input-gain-label">—</span></div>
    </div>
    <div>
      <label>&nbsp;</label>
      <button type="button" class="btn btn-secondary" onclick="refreshDevices()">Reload State</button>
      <div class="hint">Changes apply immediately, but some devices may ignore mixer gain.</div>
    </div>
  </div>
</div>

<div class="card">
  <div class="card-header">
    <h2 class="card-title">Detected ALSA Devices</h2>
  </div>
  <table class="query-table">
    <thead>
      <tr>
        <th>Type</th>
        <th>Name</th>
        <th>Device ID</th>
        <th>Card</th>
      </tr>
    </thead>
    <tbody id="device-table">
      <tr><td colspan="4" class="empty-state">Loading…</td></tr>
    </tbody>
  </table>
</div>

<script>
const SHOW_ALL = {{ 'true' if show_all else 'false' }};

function esc(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function toggleShowAll() {
  const url = new URL(window.location.href);
  if (SHOW_ALL) url.searchParams.delete('show_all');
  else url.searchParams.set('show_all', '1');
  window.location.href = url.toString();
}

function onOutputVolumePreview() {
  const v = document.getElementById('output-volume').value;
  document.getElementById('output-volume-label').textContent = v + '%';
}
function onInputGainPreview() {
  const v = document.getElementById('input-gain').value;
  document.getElementById('input-gain-label').textContent = v + '%';
}

async function setOutputVolume() {
  const control = document.getElementById('output-control').value;
  const volume = parseInt(document.getElementById('output-volume').value, 10);
  try {
    const resp = await fetch('/api/audio/output/volume', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({control, volume})
    });
    const data = await resp.json();
    if (!data.success) alert(data.error || 'Failed to set volume');
    await refreshMixerStates();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function toggleOutputMute() {
  const control = document.getElementById('output-control').value;
  try {
    const resp = await fetch('/api/audio/output/mute', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({control, action: 'toggle'})
    });
    const data = await resp.json();
    if (!data.success) alert(data.error || 'Failed to toggle mute');
    await refreshMixerStates();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function setInputGain() {
  const control = document.getElementById('input-control').value;
  const gain = parseInt(document.getElementById('input-gain').value, 10);
  try {
    const resp = await fetch('/api/audio/input/gain', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({control, gain})
    });
    const data = await resp.json();
    if (!data.success) alert(data.error || 'Failed to set gain');
    await refreshMixerStates();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function refreshMixerStates() {
  try {
    const resp = await fetch('/api/devices/state' + (SHOW_ALL ? '?show_all=1' : ''));
    const data = await resp.json();
    if (!data.success) throw new Error(data.error || 'Failed');

    document.getElementById('active-input').textContent = data.active.input_device_name || data.active.input_device_id || '—';
    document.getElementById('active-output').textContent = data.active.output_device_name || data.active.output_device_id || '—';
    document.getElementById('active-mute').textContent = data.active.mute && data.active.mute.is_muted ? 'Muted' : 'Active';

    document.getElementById('active-input-profile').textContent = data.active.input_profile_text || '';
    document.getElementById('active-output-profile').textContent = data.active.output_profile_text || '';

    const outVol = data.output && typeof data.output.volume_percent === 'number' ? data.output.volume_percent : null;
    const outMute = data.output && typeof data.output.is_on === 'boolean' ? data.output.is_on : null;
    if (outVol !== null) {
      document.getElementById('output-volume').value = outVol;
      document.getElementById('output-volume-label').textContent = outVol + '%';
    }
    document.getElementById('output-mute-state').textContent = outMute === null ? '—' : (outMute ? 'On' : 'Off');

    const inGain = data.input && typeof data.input.gain_percent === 'number' ? data.input.gain_percent : null;
    if (inGain !== null) {
      document.getElementById('input-gain').value = inGain;
      document.getElementById('input-gain-label').textContent = inGain + '%';
    }
  } catch (e) {
    console.error(e);
  }
}

async function refreshDevices() {
  const table = document.getElementById('device-table');
  table.innerHTML = '<tr><td colspan="4" class="empty-state">Loading…</td></tr>';
  try {
    const resp = await fetch('/api/devices/state' + (SHOW_ALL ? '?show_all=1' : ''));
    const data = await resp.json();
    if (!data.success) throw new Error(data.error || 'Failed');

    const outControls = data.output_controls || [];
    const inControls = data.input_controls || [];

    const outSel = document.getElementById('output-control');
    outSel.innerHTML = '';
    outControls.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      outSel.appendChild(opt);
    });
    if (data.output && data.output.control_name) outSel.value = data.output.control_name;

    const inSel = document.getElementById('input-control');
    inSel.innerHTML = '';
    inControls.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      inSel.appendChild(opt);
    });
    if (data.input && data.input.control_name) inSel.value = data.input.control_name;

    const rows = [];
    (data.detected || []).forEach(d => {
      rows.push('<tr>' +
        '<td>' + esc(d.type) + '</td>' +
        '<td><strong>' + esc(d.name) + '</strong></td>' +
        '<td><span class="time-badge">' + esc(d.id) + '</span></td>' +
        '<td>' + esc(d.card) + '</td>' +
      '</tr>');
    });
    table.innerHTML = rows.length ? rows.join('') : '<tr><td colspan="4" class="empty-state">No devices detected</td></tr>';
    await refreshMixerStates();
  } catch (e) {
    table.innerHTML = '<tr><td colspan="4" class="empty-state">Error: ' + esc(e.message) + '</td></tr>';
  }
}

refreshDevices();
document.getElementById('show-all-btn').textContent = SHOW_ALL ? 'Hide Internal Devices' : 'Show Internal Devices';
onOutputVolumePreview();
onInputGainPreview();
</script>
"""
    )
    return render_template_string(
        BASE_TEMPLATE,
        title="Devices | Jetson Assistant",
        body=body,
        flash=request.args.get("ok"),
        active_page="devices",
        show_all=show_all,
    )


@app.get("/settings")
def settings():
    s = load_settings()

    body = render_template_string(
        """
<div class="card">
  <div class="card-header">
    <h2 class="card-title">Assistant Configuration</h2>
  </div>
  <form method="post" action="{{ url_for('save_settings_route') }}">
    <div class="form-group">
      <div class="form-row">
        <div>
          <label for="openai_api_key">OpenAI API Key</label>
          <input id="openai_api_key" name="openai_api_key" type="password" value="{{ s.get('openai_api_key', '') }}" placeholder="sk-..." />
          <div class="hint">Required for GPT chat fallback and Whisper API mode. <a href="https://platform.openai.com/api-keys" target="_blank">Get one here →</a></div>
        </div>
      </div>
    </div>

    <div class="form-group">
      <div class="form-row">
        <div>
          <label for="wake_word">Wake Word</label>
          <input id="wake_word" name="wake_word" value="{{ s['wake_word'] }}" />
          <div class="hint">Trigger word to activate the assistant</div>
        </div>
        <div>
          <label for="whisper_mode">Whisper Mode</label>
          <select id="whisper_mode" name="whisper_mode">
            <option value="local" {% if s['whisper_mode']=='local' %}selected{% endif %}>Local (faster-whisper)</option>
            <option value="api" {% if s['whisper_mode']=='api' %}selected{% endif %}>API (OpenAI whisper-1)</option>
          </select>
          <div class="hint">Local runs on-device, API requires internet</div>
        </div>
      </div>
    </div>

    <div class="form-group">
      <div class="form-row">
        <div>
          <label for="whisper_model_size">Speech-to-Text Model Size</label>
          <select id="whisper_model_size" name="whisper_model_size">
            <option value="tiny" {% if s['whisper_model_size']=='tiny' %}selected{% endif %}>tiny (~75MB, fastest)</option>
            <option value="base" {% if s['whisper_model_size']=='base' %}selected{% endif %}>base (~150MB, fast)</option>
            <option value="small" {% if s['whisper_model_size']=='small' %}selected{% endif %}>small (~500MB, balanced)</option>
            <option value="medium" {% if s['whisper_model_size']=='medium' %}selected{% endif %}>medium (~1.5GB, accurate)</option>
            <option value="large" {% if s['whisper_model_size']=='large' %}selected{% endif %}>large (~3GB, most accurate)</option>
          </select>
          <div class="hint">Whisper model for converting your voice to text. Larger = more accurate but uses more RAM.</div>
        </div>
        <div>
          <label for="whisper_language">Speech Language</label>
          <input id="whisper_language" name="whisper_language" value="{{ s['whisper_language'] }}" />
          <div class="hint">ISO code for speech recognition: en, es, fr, de, etc.</div>
        </div>
      </div>
    </div>

    <div class="form-group">
      <div class="form-row">
        <div>
          <label for="audio_record_seconds">Record Duration (seconds)</label>
          <input id="audio_record_seconds" name="audio_record_seconds" type="number" step="0.5" min="1" value="{{ s['audio_record_seconds'] }}" />
        </div>
        <div>
          <label for="audio_sample_rate">Sample Rate (Hz)</label>
          <input id="audio_sample_rate" name="audio_sample_rate" type="number" step="1000" min="8000" value="{{ s['audio_sample_rate'] }}" />
        </div>
        <div>
          <label for="audio_channels">Audio Channels</label>
          <select id="audio_channels" name="audio_channels">
            <option value="1" {% if s['audio_channels']==1 %}selected{% endif %}>Mono</option>
            <option value="2" {% if s['audio_channels']==2 %}selected{% endif %}>Stereo</option>
          </select>
        </div>
      </div>
    </div>

    <div class="form-group">
      <div class="form-row">
        <div>
          <label for="audio_input_device">Input Device (Microphone)</label>
          <select id="audio_input_device" name="audio_input_device">
            {% for dev in input_devices %}
            <option value="{{ dev.id }}" {% if s.get('audio_input_device')==dev.id %}selected{% endif %}>{{ dev.name }}</option>
            {% endfor %}
          </select>
        </div>
        <div>
          <label for="audio_output_device">Output Device (Speaker)</label>
          <select id="audio_output_device" name="audio_output_device">
            {% for dev in output_devices %}
            <option value="{{ dev.id }}" {% if s.get('audio_output_device')==dev.id %}selected{% endif %}>{{ dev.name }}</option>
            {% endfor %}
          </select>
        </div>
      </div>
      <div style="margin-top: 8px;">
        <label style="display: flex; align-items: center; gap: 8px; font-weight: normal; cursor: pointer;">
          <input type="checkbox" name="show_all_devices" value="1" {% if show_all_devices %}checked{% endif %} onchange="this.form.submit()" />
          Show all devices (including internal Jetson audio)
        </label>
      </div>
    </div>

    <div class="form-group">
      <h3 class="form-section-title">Text-to-Speech</h3>
      <div class="form-row">
        <div>
          <label for="tts_provider">TTS Provider</label>
          <select id="tts_provider" name="tts_provider">
            {% for p in tts_providers %}
            <option value="{{ p.name }}" {% if s.get('tts_provider')==p.name %}selected{% endif %}>{{ p.label }} - {{ p.description }}</option>
            {% endfor %}
          </select>
          <div class="hint">Google TTS sounds natural but needs internet; espeak/pyttsx3 work offline</div>
        </div>
        <div>
          <label for="tts_language">TTS Language</label>
          <input id="tts_language" name="tts_language" value="{{ s.get('tts_language', 'en') }}" />
          <div class="hint">Language code: en, es, fr, de, etc.</div>
        </div>
        <div>
          <label for="tts_speed">Speech Speed</label>
          <input id="tts_speed" name="tts_speed" type="number" min="50" max="300" value="{{ s.get('tts_speed', 150) }}" />
          <div class="hint">Words per minute (espeak/pyttsx3 only)</div>
        </div>
      </div>
    </div>

    <button type="submit">💾 Save Settings</button>
  </form>
</div>

<script>
function esc2(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
</script>
""",
        s=s,
        input_devices=_filter_audio_devices(get_audio_input_devices(), s.get('show_all_devices', False)),
        output_devices=_filter_audio_devices(get_audio_output_devices(), s.get('show_all_devices', False)),
        tts_providers=TTS_PROVIDERS,
        show_all_devices=s.get('show_all_devices', False),
    )

    return render_template_string(BASE_TEMPLATE, title="Settings | Jetson Assistant", body=body, flash=request.args.get("ok"), active_page="settings")


@app.post("/settings")
def save_settings_route():
    def _to_int(val, default):
        try:
            return int(val)
        except Exception:
            return default

    def _to_float(val, default):
        try:
            return float(val)
        except Exception:
            return default

    current = load_settings()

    api_key_from_form = request.form.get("openai_api_key", "").strip()
    api_key = api_key_from_form if api_key_from_form else current.get("openai_api_key", "")

    new_settings = {
        "openai_api_key": api_key,
        "wake_word": (request.form.get("wake_word") or current.get("wake_word", "jetson")).strip(),
        "whisper_mode": (request.form.get("whisper_mode") or current.get("whisper_mode", "local")).strip().lower(),
        "whisper_model_size": (request.form.get("whisper_model_size") or current.get("whisper_model_size", "small")).strip(),
        "whisper_language": (request.form.get("whisper_language") or current.get("whisper_language", "en")).strip(),
        "audio_record_seconds": _to_float(request.form.get("audio_record_seconds"), current.get("audio_record_seconds", 4)),
        "audio_sample_rate": _to_int(request.form.get("audio_sample_rate"), current.get("audio_sample_rate", 16000)),
        "audio_channels": _to_int(request.form.get("audio_channels"), current.get("audio_channels", 1)),
        "audio_input_device": request.form.get("audio_input_device") or current.get("audio_input_device", ""),
        "audio_output_device": request.form.get("audio_output_device") or current.get("audio_output_device", ""),
        # TTS settings
        "tts_provider": (request.form.get("tts_provider") or current.get("tts_provider", "gtts")).strip(),
        "tts_language": (request.form.get("tts_language") or current.get("tts_language", "en")).strip(),
        "tts_speed": _to_int(request.form.get("tts_speed"), current.get("tts_speed", 150)),
        # Debug/advanced settings
        "show_all_devices": request.form.get("show_all_devices") == "1",
    }

    save_settings(new_settings)
    
    # Trigger reload signal for the assistant
    try:
        os.makedirs(os.path.dirname(RELOAD_SIGNAL_PATH), exist_ok=True)
        with open(RELOAD_SIGNAL_PATH, 'w') as f:
            f.write('reload')
    except Exception as e:
        print(f"Failed to trigger reload signal: {e}")
    
    return redirect(url_for("settings", ok="Settings saved and applied"))


@app.get("/llm")
def llm_settings():
    """LLM model configuration page."""
    s = load_settings()
    ollama_status = check_ollama_status(s.get("ollama_host", "http://localhost:11434"))
    
    body = render_template_string(
        """
<div class="card">
  <div class="card-header">
    <h2 class="card-title">LLM Provider</h2>
  </div>
  <form method="post" action="{{ url_for('save_llm_settings') }}">
    <div class="form-group">
      <div class="form-row">
        <div>
          <label for="llm_provider">Provider</label>
          <select id="llm_provider" name="llm_provider" onchange="toggleProvider()">
            <option value="openai" {% if s.llm_provider == 'openai' %}selected{% endif %}>OpenAI API</option>
            <option value="ollama" {% if s.llm_provider == 'ollama' %}selected{% endif %}>Ollama (Local)</option>
          </select>
          <div class="hint">OpenAI requires API key; Ollama runs models locally</div>
        </div>
        <div>
          <label for="ollama_host">Ollama Host</label>
          <input id="ollama_host" name="ollama_host" value="{{ s.ollama_host }}" placeholder="http://localhost:11434" />
          <div class="hint">Ollama API endpoint (usually localhost:11434)</div>
        </div>
      </div>
    </div>

    <!-- OpenAI Model Selection -->
    <div id="openai-section" class="provider-section">
      <div class="form-group">
        <label for="openai_model">OpenAI Model</label>
        <select id="openai_model" name="openai_model">
          {% for m in openai_models %}
          <option value="{{ m.name }}" {% if s.llm_model == m.name %}selected{% endif %}>{{ m.name }} - {{ m.description }}</option>
          {% endfor %}
        </select>
      </div>
    </div>

    <!-- Ollama Model Selection -->
    <div id="ollama-section" class="provider-section">
      <div class="ollama-status {{ 'status-ok' if ollama_status.available else 'status-err' }}">
        <span class="status-dot"></span>
        <span>Ollama: {{ 'Connected' if ollama_status.available else 'Not available' }}</span>
        {% if ollama_status.available %}
        <span class="status-detail">{{ ollama_status.model_count }} model(s) installed</span>
        {% endif %}
      </div>
      
      {% if ollama_status.available and ollama_status.models %}
      <div class="form-group">
        <label for="ollama_model">Installed Models</label>
        <select id="ollama_model" name="ollama_model">
          {% for m in ollama_status.models %}
          <option value="{{ m.name }}" {% if s.llm_model == m.name %}selected{% endif %}>{{ m.name }} ({{ m.size_human }})</option>
          {% endfor %}
        </select>
      </div>
      {% else %}
      <div class="empty-hint">No models installed. Use the panel below to install one.</div>
      {% endif %}
    </div>

    <button type="submit">💾 Save LLM Settings</button>
  </form>
</div>

<!-- Model Installation -->
<div class="card">
  <div class="card-header">
    <h2 class="card-title">Install Ollama Models</h2>
    <span class="time-badge">Recommended for Jetson</span>
  </div>
  
  <div class="model-grid">
    {% for m in recommended_models %}
    <div class="model-card">
      <div class="model-header">
        <strong>{{ m.name }}</strong>
        <span class="model-size">{{ m.size }}</span>
      </div>
      <div class="model-desc">{{ m.description }}</div>
      <button type="button" class="btn btn-secondary btn-sm" onclick="installModel('{{ m.name }}')" 
        {% if not ollama_status.available %}disabled{% endif %}>
        Install
      </button>
    </div>
    {% endfor %}
  </div>
  
  <div id="install-progress" class="install-progress" style="display: none;">
    <div class="progress-header">
      <span id="progress-model">Installing...</span>
      <span id="progress-status"></span>
    </div>
    <div class="progress-bar">
      <div id="progress-fill" class="progress-fill"></div>
    </div>
  </div>
</div>

<!-- Installed Models Management -->
{% if ollama_status.available and ollama_status.models %}
<div class="card">
  <div class="card-header">
    <h2 class="card-title">Manage Installed Models</h2>
  </div>
  <table class="query-table">
    <thead>
      <tr>
        <th>Model</th>
        <th>Size</th>
        <th>Family</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for m in ollama_status.models %}
      <tr>
        <td><strong>{{ m.name }}</strong></td>
        <td>{{ m.size_human }}</td>
        <td>{{ m.family or '—' }}</td>
        <td>
          <button type="button" class="btn btn-danger btn-sm" onclick="deleteModel('{{ m.name }}')">Delete</button>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}

<style>
  .provider-section { display: none; margin-top: 16px; }
  .provider-section.active { display: block; }
  .ollama-status {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 16px; background: var(--bg-secondary);
    border-radius: 8px; margin-bottom: 16px;
  }
  .status-dot { width: 10px; height: 10px; border-radius: 50%; }
  .status-ok .status-dot { background: var(--success); }
  .status-err .status-dot { background: var(--danger); }
  .status-detail { color: var(--text-muted); font-size: 0.85rem; margin-left: auto; }
  .empty-hint { color: var(--text-muted); padding: 16px; text-align: center; }
  
  .model-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
  .model-card {
    padding: 16px; background: var(--bg-secondary);
    border: 1px solid var(--border); border-radius: 10px;
  }
  .model-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .model-size { font-size: 0.8rem; color: var(--accent); background: rgba(99,102,241,0.1); padding: 2px 8px; border-radius: 4px; }
  .model-desc { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 12px; }
  .btn-sm { padding: 8px 16px; font-size: 0.85rem; }
  
  .install-progress { margin-top: 20px; padding: 16px; background: var(--bg-secondary); border-radius: 10px; }
  .progress-header { display: flex; justify-content: space-between; margin-bottom: 10px; }
  .progress-bar { height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
  .progress-fill { height: 100%; background: var(--accent); width: 0%; transition: width 0.3s; }
</style>

<script>
function toggleProvider() {
  const provider = document.getElementById('llm_provider').value;
  document.querySelectorAll('.provider-section').forEach(s => s.classList.remove('active'));
  document.getElementById(provider + '-section').classList.add('active');
}
toggleProvider();

async function installModel(name) {
  const progress = document.getElementById('install-progress');
  const progressModel = document.getElementById('progress-model');
  const progressStatus = document.getElementById('progress-status');
  const progressFill = document.getElementById('progress-fill');
  
  progress.style.display = 'block';
  progressModel.textContent = 'Installing ' + name + '...';
  progressStatus.textContent = 'Starting...';
  progressFill.style.width = '0%';
  
  try {
    const resp = await fetch('/api/ollama/pull', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({model: name})
    });
    const data = await resp.json();
    if (data.success) {
      progressStatus.textContent = 'Complete!';
      progressFill.style.width = '100%';
      setTimeout(() => location.reload(), 1000);
    } else {
      progressStatus.textContent = 'Error: ' + (data.error || 'Unknown');
    }
  } catch (e) {
    progressStatus.textContent = 'Error: ' + e.message;
  }
}

async function deleteModel(name) {
  if (!confirm('Delete model ' + name + '?')) return;
  try {
    const resp = await fetch('/api/ollama/delete', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({model: name})
    });
    const data = await resp.json();
    if (data.success) {
      location.reload();
    } else {
      alert('Error: ' + (data.error || 'Unknown'));
    }
  } catch (e) {
    alert('Error: ' + e.message);
  }
}
</script>
""",
        s=s,
        ollama_status=ollama_status,
        openai_models=OPENAI_MODELS,
        recommended_models=RECOMMENDED_OLLAMA_MODELS,
    )

    return render_template_string(BASE_TEMPLATE, title="LLM Models | Jetson Assistant", body=body, flash=request.args.get("ok"), active_page="llm")


@app.post("/llm")
def save_llm_settings():
    """Save LLM configuration."""
    current = load_settings()
    
    provider = request.form.get("llm_provider", "openai").strip()
    ollama_host = request.form.get("ollama_host", "http://localhost:11434").strip()
    
    # Get model based on provider
    if provider == "openai":
        model = request.form.get("openai_model", "gpt-4o-mini").strip()
    else:
        model = request.form.get("ollama_model", "").strip()
    
    current["llm_provider"] = provider
    current["llm_model"] = model
    current["ollama_host"] = ollama_host
    
    save_settings(current)
    
    # Trigger reload
    try:
        os.makedirs(os.path.dirname(RELOAD_SIGNAL_PATH), exist_ok=True)
        with open(RELOAD_SIGNAL_PATH, 'w') as f:
            f.write('reload')
    except Exception:
        pass
    
    return redirect(url_for("llm_settings", ok="LLM settings saved"))


@app.post("/api/ollama/pull")
def api_ollama_pull():
    """Pull/install an Ollama model."""
    data = request.get_json() or {}
    model = data.get("model", "")
    if not model:
        return jsonify({"success": False, "error": "No model specified"})
    
    settings = load_settings()
    client = OllamaClient(settings.get("ollama_host", "http://localhost:11434"))
    
    # Pull model (blocking for simplicity - could be made async)
    last_status = ""
    for update in client.pull_model(model):
        if "error" in update:
            return jsonify({"success": False, "error": update["error"]})
        last_status = update.get("status", "")
    
    return jsonify({"success": True, "status": last_status})


@app.post("/api/ollama/delete")
def api_ollama_delete():
    """Delete an Ollama model."""
    data = request.get_json() or {}
    model = data.get("model", "")
    if not model:
        return jsonify({"success": False, "error": "No model specified"})
    
    settings = load_settings()
    client = OllamaClient(settings.get("ollama_host", "http://localhost:11434"))
    
    success = client.delete_model(model)
    return jsonify({"success": success})


@app.get("/api/ollama/status")
def api_ollama_status():
    """Get Ollama status and models."""
    settings = load_settings()
    status = check_ollama_status(settings.get("ollama_host", "http://localhost:11434"))
    return jsonify(status)


def _get_process_memory(name_pattern: str) -> float:
    """Get memory usage of processes matching name pattern (in MB)."""
    total = 0.0
    for proc in psutil.process_iter(['name', 'cmdline', 'memory_info']):
        try:
            name = proc.info['name'] or ''
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if name_pattern.lower() in name.lower() or name_pattern.lower() in cmdline.lower():
                total += proc.info['memory_info'].rss / 1024 / 1024
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return round(total, 1)


def _get_memory_breakdown() -> list:
    """Get memory usage breakdown by component."""
    settings = load_settings()
    whisper_sizes = {'tiny': 75, 'base': 150, 'small': 500, 'medium': 1500, 'large': 3000}
    whisper_model = settings.get('whisper_model_size', 'small')
    whisper_estimate = whisper_sizes.get(whisper_model, 500)
    
    components = []
    
    # Voice Assistant process
    assistant_mem = _get_process_memory('assistant.py')
    if assistant_mem > 0:
        components.append({
            'name': 'Voice Assistant',
            'memory_mb': assistant_mem,
            'note': f'Includes Whisper {whisper_model} (~{whisper_estimate}MB)'
        })
    
    # Admin Portal
    portal_mem = _get_process_memory('admin_portal')
    if portal_mem > 0:
        components.append({'name': 'Admin Portal', 'memory_mb': portal_mem, 'note': 'Flask web server'})
    
    # Ollama
    ollama_mem = _get_process_memory('ollama')
    if ollama_mem > 0:
        llm_model = settings.get('llm_model', '')
        components.append({'name': 'Ollama', 'memory_mb': ollama_mem, 'note': f'LLM: {llm_model}' if llm_model else 'Local LLM server'})
    
    # System/Other
    total_used = sum(c['memory_mb'] for c in components)
    vm = psutil.virtual_memory()
    system_mem = round(vm.used / 1024 / 1024 - total_used, 1)
    if system_mem > 0:
        components.append({'name': 'System & Other', 'memory_mb': system_mem, 'note': 'OS, drivers, other processes'})
    
    return components


@app.get("/stats")
def system_stats():
    vm = psutil.virtual_memory()
    du = psutil.disk_usage("/")
    cpu_percent = psutil.cpu_percent(interval=0.3)

    # Record current stats
    record_stats(cpu_percent, vm.percent, du.percent)

    # Get historical data
    stats_history = get_stats_history(60)
    labels = [datetime.fromtimestamp(s["ts"]).strftime("%H:%M") for s in stats_history]
    cpu_data = [s["cpu"] for s in stats_history]
    mem_data = [s["mem"] for s in stats_history]
    
    # Get memory breakdown
    memory_breakdown = _get_memory_breakdown()

    body = render_template_string(
        """
<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-value">{{ cpu_percent }}%</div>
    <div class="stat-label">CPU Usage</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{{ vm.percent }}%</div>
    <div class="stat-label">Memory</div>
    <div class="stat-detail">{{ (vm.used/1024/1024/1024)|round(1) }}GB / {{ (vm.total/1024/1024/1024)|round(1) }}GB</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{{ du.percent }}%</div>
    <div class="stat-label">Disk Usage</div>
    <div class="stat-detail">{{ (du.used/1024/1024/1024)|round(1) }}GB / {{ (du.total/1024/1024/1024)|round(1) }}GB</div>
  </div>
</div>

<!-- Memory Breakdown -->
<div class="card">
  <div class="card-header">
    <h2 class="card-title">Memory Breakdown</h2>
    <span class="time-badge">By Component</span>
  </div>
  <div class="memory-breakdown">
    {% for comp in memory_breakdown %}
    <div class="memory-item">
      <div class="memory-bar-container">
        <div class="memory-bar" style="width: {{ (comp.memory_mb / (vm.total/1024/1024) * 100)|round(1) }}%"></div>
      </div>
      <div class="memory-info">
        <div class="memory-name">{{ comp.name }}</div>
        <div class="memory-value">{{ comp.memory_mb }}MB</div>
      </div>
      <div class="memory-note">{{ comp.note }}</div>
    </div>
    {% endfor %}
  </div>
  <style>
    .memory-breakdown { display: flex; flex-direction: column; gap: 12px; }
    .memory-item { background: var(--bg-secondary); padding: 14px 16px; border-radius: 10px; }
    .memory-bar-container { height: 6px; background: var(--border); border-radius: 3px; margin-bottom: 10px; }
    .memory-bar { height: 100%; background: linear-gradient(90deg, var(--accent), #a855f7); border-radius: 3px; min-width: 4px; }
    .memory-info { display: flex; justify-content: space-between; align-items: center; }
    .memory-name { font-weight: 500; }
    .memory-value { font-weight: 600; color: var(--accent); }
    .memory-note { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }
  </style>
</div>

<div class="card">
  <div class="card-header">
    <h2 class="card-title">Resource History</h2>
    <span class="time-badge">Last {{ stats_history|length }} samples</span>
  </div>
  <div class="chart-container">
    <canvas id="statsChart"></canvas>
  </div>
</div>

<script>
const ctx = document.getElementById('statsChart').getContext('2d');
new Chart(ctx, {
  type: 'line',
  data: {
    labels: {{ labels | tojson }},
    datasets: [{
      label: 'CPU %',
      data: {{ cpu_data | tojson }},
      borderColor: '#6366f1',
      backgroundColor: 'rgba(99, 102, 241, 0.1)',
      fill: true,
      tension: 0.4
    }, {
      label: 'Memory %',
      data: {{ mem_data | tojson }},
      borderColor: '#a855f7',
      backgroundColor: 'rgba(168, 85, 247, 0.1)',
      fill: true,
      tension: 0.4
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: { color: '#a0a0a0' }
      }
    },
    scales: {
      x: {
        grid: { color: '#333' },
        ticks: { color: '#666' }
      },
      y: {
        min: 0,
        max: 100,
        grid: { color: '#333' },
        ticks: { color: '#666' }
      }
    }
  }
});
</script>
""",
        vm=vm,
        du=du,
        cpu_percent=cpu_percent,
        stats_history=stats_history,
        labels=labels,
        cpu_data=cpu_data,
        mem_data=mem_data,
        memory_breakdown=memory_breakdown,
    )

    return render_template_string(BASE_TEMPLATE, title="System Stats | Jetson Assistant", body=body, flash=None, active_page="stats")


@app.get("/history")
def query_history():
    queries = get_query_history(50)

    body = render_template_string(
        """
<div class="card">
  <div class="card-header">
    <h2 class="card-title">Query History</h2>
    {% if queries %}
    <form method="post" action="{{ url_for('clear_history') }}" style="margin:0">
      <button type="submit" class="btn btn-danger" onclick="return confirm('Clear all query history?')">🗑️ Clear History</button>
    </form>
    {% endif %}
  </div>

  {% if queries %}
  <table class="query-table">
    <thead>
      <tr>
        <th>Time</th>
        <th>Query</th>
        <th>Response</th>
        <th>Duration</th>
        <th>Tokens</th>
        <th>Model</th>
      </tr>
    </thead>
    <tbody>
      {% for q in queries %}
      <tr>
        <td><span class="time-badge">{{ q.time }}</span></td>
        <td class="query-text" title="{{ q.query }}">{{ q.query }}</td>
        <td class="query-text" title="{{ q.response }}">{{ q.response[:100] }}{% if q.response|length > 100 %}...{% endif %}</td>
        <td>{{ q.duration_ms }}ms</td>
        <td>
          {% if q.total_tokens %}
          <span class="token-badge" title="Prompt: {{ q.prompt_tokens }}, Completion: {{ q.completion_tokens }}">{{ q.total_tokens }}</span>
          {% else %}
          <span class="token-badge token-na">—</span>
          {% endif %}
        </td>
        <td><span class="model-badge">{{ q.model or '—' }}</span></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  <style>
    .token-badge { 
      display: inline-block; padding: 4px 8px; background: rgba(99, 102, 241, 0.2); 
      border-radius: 6px; font-size: 0.8rem; color: var(--accent); cursor: help;
    }
    .token-na { background: var(--bg-secondary); color: var(--text-muted); }
    .model-badge { font-size: 0.75rem; color: var(--text-muted); }
  </style>
  {% else %}
  <div class="empty-state">
    <div class="empty-state-icon">📝</div>
    <p>No queries recorded yet.</p>
    <p style="font-size: 0.9rem; margin-top: 8px;">Voice queries will appear here once you start using the assistant.</p>
  </div>
  {% endif %}
</div>
""",
        queries=queries,
    )

    return render_template_string(BASE_TEMPLATE, title="Query History | Jetson Assistant", body=body, flash=request.args.get("ok"), active_page="history")


@app.post("/history/clear")
def clear_history():
    clear_query_history()
    return redirect(url_for("query_history", ok="History cleared"))


@app.get("/api/stats")
def api_stats():
    """JSON endpoint for live stats updates."""
    vm = psutil.virtual_memory()
    du = psutil.disk_usage("/")
    cpu_percent = psutil.cpu_percent(interval=0.1)
    record_stats(cpu_percent, vm.percent, du.percent)
    return jsonify({
        "cpu": cpu_percent,
        "memory": vm.percent,
        "disk": du.percent,
    })


@app.get("/api/mute-status")
def api_mute_status():
    """JSON endpoint for microphone mute status."""
    settings = load_settings()
    audio_input_device = settings.get('audio_input_device', 'default')
    mute_status = get_mute_status(audio_input_device)
    return jsonify(mute_status)


@app.get("/api/devices/state")
def api_devices_state():
    show_all = (request.args.get("show_all") or "").strip() in ("1", "true", "yes", "on")
    settings = load_settings()
    input_device_id = settings.get("audio_input_device", "default")
    output_device_id = settings.get("audio_output_device", "default")

    detected = []
    for d in get_audio_input_devices():
        if not show_all and _is_internal_audio_device_name(d.get("name") or ""):
            continue
        detected.append({"type": "input", "id": d.get("id"), "name": d.get("name"), "card": d.get("card")})
    for d in get_audio_output_devices():
        if not show_all and _is_internal_audio_device_name(d.get("name") or ""):
            continue
        detected.append({"type": "output", "id": d.get("id"), "name": d.get("name"), "card": d.get("card")})

    mute_status = get_mute_status(input_device_id)

    active_input_identity = get_device_identity(input_device_id)
    active_output_identity = get_device_identity(output_device_id)
    input_profile = get_hardware_profile(input_device_id)
    output_profile = get_hardware_profile(output_device_id)

    input_card = get_card_number_from_device(input_device_id)
    output_card = get_card_number_from_device(output_device_id)

    input_controls = _list_mixer_controls(str(input_card), timeout=2) if input_card else []
    output_controls = _list_mixer_controls(str(output_card), timeout=2) if output_card else []

    chosen_output_control = _choose_reasonable_control(str(output_card), ["Anker PowerConf S330", "Master", "PCM", "Speaker"]) if output_card else None
    chosen_input_control = _choose_reasonable_control(str(input_card), ["Mic", "Capture", "Input", "Headset"]) if input_card else None

    output_state = {"control_name": chosen_output_control, "volume_percent": None, "is_on": None}
    input_state = {"control_name": chosen_input_control, "gain_percent": None}

    try:
        if output_card and chosen_output_control:
            r = _run_amixer(["-c", str(output_card), "sget", chosen_output_control], timeout=2)
            if r.returncode == 0:
                output_state["volume_percent"] = _parse_amixer_percent(r.stdout)
                output_state["is_on"] = _parse_amixer_switch(r.stdout)
    except Exception:
        pass

    try:
        if input_card and chosen_input_control:
            r = _run_amixer(["-c", str(input_card), "sget", chosen_input_control], timeout=2)
            if r.returncode == 0:
                input_state["gain_percent"] = _parse_amixer_percent(r.stdout)
    except Exception:
        pass

    return jsonify(
        {
            "success": True,
            "detected": detected,
            "active": {
                "input_device_id": input_device_id,
                "output_device_id": output_device_id,
                "input_device_name": next((d.get("name") for d in get_audio_input_devices() if d.get("id") == input_device_id), input_device_id),
                "output_device_name": next((d.get("name") for d in get_audio_output_devices() if d.get("id") == output_device_id), output_device_id),
                "mute": mute_status,
                "input_identity": active_input_identity,
                "output_identity": active_output_identity,
                "input_profile": {"name": input_profile.name},
                "output_profile": {"name": output_profile.name},
                "input_profile_text": f"Profile: {input_profile.name} • ALSA: {active_input_identity.get('alsa_card_name') or '—'}",
                "output_profile_text": f"Profile: {output_profile.name} • ALSA: {active_output_identity.get('alsa_card_name') or '—'}",
            },
            "input_controls": input_controls,
            "output_controls": output_controls,
            "input": input_state,
            "output": output_state,
        }
    )


@app.post("/api/audio/output/volume")
def api_set_output_volume():
    payload = request.get_json(silent=True) or {}
    volume = payload.get("volume")
    control = (payload.get("control") or "").strip()

    settings = load_settings()
    output_device_id = settings.get("audio_output_device", "default")
    ok, card_args, err = _amixer_card_args_from_device(output_device_id)
    if not ok or not card_args:
        return jsonify({"success": False, "error": err or "No output ALSA card"})

    try:
        volume_int = int(volume)
        if volume_int < 0 or volume_int > 100:
            raise ValueError("Volume out of range")
    except Exception:
        return jsonify({"success": False, "error": "Invalid volume"})

    if not control:
        card = card_args[1]
        control = _choose_reasonable_control(str(card), ["Master", "PCM", "Speaker"]) or ""

    if not control:
        return jsonify({"success": False, "error": "No mixer control available"})

    try:
        r = _run_amixer([*card_args, "sset", control, f"{volume_int}%"], timeout=3)
        if r.returncode != 0:
            return jsonify({"success": False, "error": (r.stderr or r.stdout or "amixer failed")[:200]})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.post("/api/audio/output/mute")
def api_output_mute():
    payload = request.get_json(silent=True) or {}
    action = (payload.get("action") or "toggle").strip().lower()
    control = (payload.get("control") or "").strip()

    settings = load_settings()
    output_device_id = settings.get("audio_output_device", "default")
    ok, card_args, err = _amixer_card_args_from_device(output_device_id)
    if not ok or not card_args:
        return jsonify({"success": False, "error": err or "No output ALSA card"})

    if not control:
        card = card_args[1]
        control = _choose_reasonable_control(str(card), ["Master", "PCM", "Speaker"]) or ""

    if not control:
        return jsonify({"success": False, "error": "No mixer control available"})

    try:
        if action == "mute":
            r = _run_amixer([*card_args, "sset", control, "mute"], timeout=3)
        elif action == "unmute":
            r = _run_amixer([*card_args, "sset", control, "unmute"], timeout=3)
        else:
            r = _run_amixer([*card_args, "sset", control, "toggle"], timeout=3)
        if r.returncode != 0:
            return jsonify({"success": False, "error": (r.stderr or r.stdout or "amixer failed")[:200]})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.post("/api/audio/input/gain")
def api_set_input_gain():
    payload = request.get_json(silent=True) or {}
    gain = payload.get("gain")
    control = (payload.get("control") or "").strip()

    settings = load_settings()
    input_device_id = settings.get("audio_input_device", "default")
    ok, card_args, err = _amixer_card_args_from_device(input_device_id)
    if not ok or not card_args:
        return jsonify({"success": False, "error": err or "No input ALSA card"})

    try:
        gain_int = int(gain)
        if gain_int < 0 or gain_int > 100:
            raise ValueError("Gain out of range")
    except Exception:
        return jsonify({"success": False, "error": "Invalid gain"})

    if not control:
        card = card_args[1]
        control = _choose_reasonable_control(str(card), ["Mic", "Capture", "Input"]) or ""

    if not control:
        return jsonify({"success": False, "error": "No mixer control available"})

    try:
        r = _run_amixer([*card_args, "sset", control, f"{gain_int}%"], timeout=3)
        if r.returncode != 0:
            return jsonify({"success": False, "error": (r.stderr or r.stdout or "amixer failed")[:200]})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.get("/api/dashboard")
def api_dashboard():
    """JSON endpoint for dashboard live updates."""
    # Service status checks
    services = [
        _check_service_status("voice-assistant"),
        _check_service_status("voice-assistant-portal"),
        _check_openai_status(),
        _check_internet(),
        _check_audio_devices(),
    ]
    
    # Get microphone mute status
    settings = load_settings()
    audio_input_device = settings.get('audio_input_device', 'default')
    mute_status = get_mute_status(audio_input_device)
    
    # System metrics
    vm = psutil.virtual_memory()
    du = psutil.disk_usage("/")
    cpu_percent = psutil.cpu_percent(interval=0.1)
    jetson_stats = _get_jetson_stats()
    
    # Query analytics
    analytics = get_query_analytics()
    
    # Overall health
    all_ok = all(s["ok"] for s in services)
    
    return jsonify({
        "services": services,
        "health": "healthy" if all_ok else "degraded",
        "mute_status": mute_status,
        "system": {
            "cpu": cpu_percent,
            "memory": vm.percent,
            "memory_used_gb": round(vm.used / 1024 / 1024 / 1024, 1),
            "memory_total_gb": round(vm.total / 1024 / 1024 / 1024, 1),
            "disk": du.percent,
            "gpu": jetson_stats.get("gpu_usage"),
            "uptime": jetson_stats.get("uptime", ""),
            "temperatures": jetson_stats.get("temperatures", []),
        },
        "analytics": analytics,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
