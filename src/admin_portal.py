from flask import Flask, redirect, render_template_string, request, url_for
import psutil

from settings_store import load_settings, save_settings


app = Flask(__name__)


BASE_TEMPLATE = """
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{{ title }}</title>
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; max-width: 900px; }
      header { display: flex; gap: 12px; align-items: baseline; margin-bottom: 16px; }
      nav a { margin-right: 12px; }
      .card { border: 1px solid #ddd; border-radius: 10px; padding: 16px; margin: 12px 0; }
      label { display: block; font-weight: 600; margin-top: 10px; }
      input, select { width: 100%; max-width: 420px; padding: 8px; margin-top: 6px; }
      .row { display: flex; gap: 18px; flex-wrap: wrap; }
      .row > div { flex: 1 1 260px; }
      button { padding: 10px 14px; border-radius: 10px; border: 1px solid #222; background: #222; color: white; cursor: pointer; }
      .muted { color: #666; font-size: 0.95em; }
      .ok { color: #0a7; font-weight: 700; }
    </style>
  </head>
  <body>
    <header>
      <h1 style=\"margin: 0\">{{ title }}</h1>
      <nav>
        <a href=\"{{ url_for('settings') }}\">Settings</a>
        <a href=\"{{ url_for('system_stats') }}\">System Stats</a>
      </nav>
    </header>
    {% if flash %}<div class=\"card\"><span class=\"ok\">{{ flash }}</span></div>{% endif %}
    {{ body | safe }}
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
  <form method="post" action="{{ url_for('save_settings_route') }}">
    <div class="row">
      <div>
        <label for="wake_word">Wake word</label>
        <input id="wake_word" name="wake_word" value="{{ s['wake_word'] }}" />
        <div class="muted">Used for future wake-word gating. Current assistant loop still records fixed windows.</div>
      </div>
      <div>
        <label for="whisper_mode">Whisper mode</label>
        <select id="whisper_mode" name="whisper_mode">
          <option value="local" {% if s['whisper_mode']=='local' %}selected{% endif %}>local (faster-whisper)</option>
          <option value="api" {% if s['whisper_mode']=='api' %}selected{% endif %}>api (OpenAI whisper-1)</option>
        </select>
      </div>
    </div>

    <div class="row">
      <div>
        <label for="whisper_model_size">Whisper model size</label>
        <select id="whisper_model_size" name="whisper_model_size">
          {% for m in ['tiny','base','small','medium','large'] %}
            <option value="{{ m }}" {% if s['whisper_model_size']==m %}selected{% endif %}>{{ m }}</option>
          {% endfor %}
        </select>
        <div class="muted">Jetson Nano usually prefers tiny/base/small.</div>
      </div>
      <div>
        <label for="whisper_language">Language</label>
        <input id="whisper_language" name="whisper_language" value="{{ s['whisper_language'] }}" />
        <div class="muted">Example: en, es, fr. Leave as en for English.</div>
      </div>
    </div>

    <div class="row">
      <div>
        <label for="audio_record_seconds">Record seconds</label>
        <input id="audio_record_seconds" name="audio_record_seconds" type="number" step="0.5" min="1" value="{{ s['audio_record_seconds'] }}" />
      </div>
      <div>
        <label for="audio_sample_rate">Sample rate</label>
        <input id="audio_sample_rate" name="audio_sample_rate" type="number" step="1000" min="8000" value="{{ s['audio_sample_rate'] }}" />
      </div>
      <div>
        <label for="audio_channels">Channels</label>
        <select id="audio_channels" name="audio_channels">
          <option value="1" {% if s['audio_channels']==1 %}selected{% endif %}>1</option>
          <option value="2" {% if s['audio_channels']==2 %}selected{% endif %}>2</option>
        </select>
      </div>
    </div>

    <div style="margin-top: 16px;">
      <button type="submit">Save settings</button>
    </div>
  </form>
</div>
""",
        s=s,
    )

    return render_template_string(BASE_TEMPLATE, title="Admin Portal - Settings", body=body, flash=request.args.get("ok"))


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

    new_settings = {
        "wake_word": (request.form.get("wake_word") or current["wake_word"]).strip(),
        "whisper_mode": (request.form.get("whisper_mode") or current["whisper_mode"]).strip().lower(),
        "whisper_model_size": (request.form.get("whisper_model_size") or current["whisper_model_size"]).strip(),
        "whisper_language": (request.form.get("whisper_language") or current["whisper_language"]).strip(),
        "audio_record_seconds": _to_float(request.form.get("audio_record_seconds"), current["audio_record_seconds"]),
        "audio_sample_rate": _to_int(request.form.get("audio_sample_rate"), current["audio_sample_rate"]),
        "audio_channels": _to_int(request.form.get("audio_channels"), current["audio_channels"]),
    }

    save_settings(new_settings)
    return redirect(url_for("settings", ok="Saved"))


@app.get("/stats")
def system_stats():
    vm = psutil.virtual_memory()
    du = psutil.disk_usage("/")
    cpu_percent = psutil.cpu_percent(interval=0.3)

    body = render_template_string(
        """
<div class="card">
  <div class="row">
    <div>
      <h3 style="margin-top:0">CPU</h3>
      <div><b>Usage:</b> {{ cpu_percent }}%</div>
      <div class="muted">(sampled over ~0.3s)</div>
    </div>
    <div>
      <h3 style="margin-top:0">Memory</h3>
      <div><b>Total:</b> {{ (vm.total/1024/1024)|round(0) }} MB</div>
      <div><b>Used:</b> {{ (vm.used/1024/1024)|round(0) }} MB</div>
      <div><b>Available:</b> {{ (vm.available/1024/1024)|round(0) }} MB</div>
      <div><b>Percent:</b> {{ vm.percent }}%</div>
    </div>
    <div>
      <h3 style="margin-top:0">Disk (/)</h3>
      <div><b>Total:</b> {{ (du.total/1024/1024/1024)|round(2) }} GB</div>
      <div><b>Used:</b> {{ (du.used/1024/1024/1024)|round(2) }} GB</div>
      <div><b>Free:</b> {{ (du.free/1024/1024/1024)|round(2) }} GB</div>
      <div><b>Percent:</b> {{ du.percent }}%</div>
    </div>
  </div>
</div>
""",
        vm=vm,
        du=du,
        cpu_percent=cpu_percent,
    )

    return render_template_string(BASE_TEMPLATE, title="Admin Portal - System Stats", body=body, flash=None)


if __name__ == "__main__":
    # For LAN access on your home network, set host to 0.0.0.0
    app.run(host="0.0.0.0", port=8080, debug=True)
