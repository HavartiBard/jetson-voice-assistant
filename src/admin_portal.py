from flask import Flask, jsonify, redirect, render_template_string, request, url_for
import psutil
import json
import os
from datetime import datetime

from settings_store import load_settings, save_settings
from history_store import get_stats_history, get_query_history, record_stats, clear_query_history

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
        <a href="{{ url_for('settings') }}" {% if active_page == 'settings' %}class="active"{% endif %}>Settings</a>
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
    return redirect(url_for("settings"))


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

    <button type="submit">💾 Save Settings</button>
  </form>
</div>
""",
        s=s,
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
        "wake_word": (request.form.get("wake_word") or current["wake_word"]).strip(),
        "whisper_mode": (request.form.get("whisper_mode") or current["whisper_mode"]).strip().lower(),
        "whisper_model_size": (request.form.get("whisper_model_size") or current["whisper_model_size"]).strip(),
        "whisper_language": (request.form.get("whisper_language") or current["whisper_language"]).strip(),
        "audio_record_seconds": _to_float(request.form.get("audio_record_seconds"), current["audio_record_seconds"]),
        "audio_sample_rate": _to_int(request.form.get("audio_sample_rate"), current["audio_sample_rate"]),
        "audio_channels": _to_int(request.form.get("audio_channels"), current["audio_channels"]),
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
      </tr>
    </thead>
    <tbody>
      {% for q in queries %}
      <tr>
        <td><span class="time-badge">{{ q.time }}</span></td>
        <td class="query-text" title="{{ q.query }}">{{ q.query }}</td>
        <td class="query-text" title="{{ q.response }}">{{ q.response[:100] }}{% if q.response|length > 100 %}...{% endif %}</td>
        <td>{{ q.duration_ms }}ms</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
