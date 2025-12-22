from flask import Flask, jsonify, redirect, render_template_string, request, url_for
import psutil
import json
import os
import subprocess
import socket
import time as time_module
from datetime import datetime

from settings_store import load_settings, save_settings, RECOMMENDED_OLLAMA_MODELS, OPENAI_MODELS
from history_store import get_stats_history, get_query_history, record_stats, clear_query_history, get_query_analytics
from audio_devices import get_audio_input_devices, get_audio_output_devices
from ollama_client import OllamaClient, check_ollama_status

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


def _check_service_status(service_name: str) -> dict:
    """Check systemd service status."""
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
  <!-- Health Status Banner -->
  <div class="health-banner {{ 'health-ok' if health_status == 'healthy' else 'health-warn' }}">
    <div class="health-icon">{{ '✓' if health_status == 'healthy' else '⚠' }}</div>
    <div class="health-text">
      <strong>System {{ health_status.title() }}</strong>
      <span>Uptime: {{ jetson_stats.uptime }}</span>
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
</script>
""",
        services=services,
        health_status=health_status,
        vm=vm,
        du=du,
        cpu_percent=cpu_percent,
        jetson_stats=jetson_stats,
        analytics=analytics,
    )

    return render_template_string(BASE_TEMPLATE, title="Dashboard | Jetson Assistant", body=body, flash=None, active_page="dashboard")


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
          <label for="whisper_model_size">Model Size</label>
          <select id="whisper_model_size" name="whisper_model_size">
            {% for m in ['tiny','base','small','medium','large'] %}
              <option value="{{ m }}" {% if s['whisper_model_size']==m %}selected{% endif %}>{{ m }}</option>
            {% endfor %}
          </select>
          <div class="hint">Smaller = faster, larger = more accurate</div>
        </div>
        <div>
          <label for="whisper_language">Language</label>
          <input id="whisper_language" name="whisper_language" value="{{ s['whisper_language'] }}" />
          <div class="hint">ISO code: en, es, fr, de, etc.</div>
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
    </div>

    <button type="submit">💾 Save Settings</button>
  </form>
</div>
""",
        s=s,
        input_devices=get_audio_input_devices(),
        output_devices=get_audio_output_devices(),
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
