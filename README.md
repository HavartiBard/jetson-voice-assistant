# Jetson Voice Assistant

A customizable voice assistant designed specifically for the NVIDIA Jetson Nano/Orin. Uses wake word detection, local Whisper speech recognition, and natural text-to-speech with support for both cloud and local LLMs.

## Features

- 🎙️ **Wake word activation** - Customizable wake word (default: "jetson")
- 🗣️ **Local speech recognition** using faster-whisper (runs on-device) or OpenAI Whisper API
- 🔊 **Configurable text-to-speech** - Google TTS, eSpeak, or pyttsx3 (offline options available)
- 🤖 **Dual LLM support** - OpenAI API or local Ollama models
- 🌐 **Admin web portal** for configuration, monitoring, and LLM management
- 📊 **System stats** with real-time CPU/memory/disk graphs
- 📝 **Query history** with token usage tracking and analytics
- 🔌 **Audio device detection** - Auto-detects USB audio devices
- ⏰ Built-in commands: time, date, jokes, web search, greetings

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         Jetson Device                            │
├──────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐    ┌─────────────────────────────────────┐ │
│  │  voice-assistant │    │      voice-assistant-portal         │ │
│  │    (systemd)     │    │          (systemd)                  │ │
│  │                  │    │                                     │ │
│  │ • Wake word      │    │ • Settings UI (:8080/settings)      │ │
│  │ • Whisper STT    │◄──►│ • System stats (:8080/stats)        │ │
│  │ • LLM (OpenAI/   │    │ • Query history (:8080/history)     │ │
│  │   Ollama)        │    │ • Ollama models (:8080/ollama)      │ │
│  │ • gTTS/espeak    │    │                                     │ │
│  └────────┬─────────┘    └─────────────────────────────────────┘ │
│           │                                                      │
│  ┌────────▼─────────┐    ┌─────────────────────────────────────┐ │
│  │ config/          │    │ External Services (optional)        │ │
│  │ • settings.json  │    │ • OpenAI API                        │ │
│  │ • history.json   │    │ • Ollama (local or remote)          │ │
│  └──────────────────┘    └─────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- NVIDIA Jetson Nano/Orin with JetPack (or any Linux system)
- Python 3.10+
- USB microphone/speaker (e.g., Jabra SPEAK 510) or ALSA-compatible audio
- Internet connection for cloud features (Google TTS, OpenAI)
- **Optional**: OpenAI API key for cloud LLM and Whisper API
- **Optional**: Ollama for local LLM inference

## Installation

1. **Install system dependencies**
   ```bash
   sudo apt-get update
   sudo apt-get install -y git python3-venv portaudio19-dev espeak ffmpeg alsa-utils
   ```

2. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd jetson-voice-assistant
   ```

3. **Create and activate a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up environment variables**
   ```bash
   cp .env.example .env
   nano .env  # Edit the file with your settings
   ```
   
   OpenAI API key is optional - set it in the admin portal or `.env` for GPT features.

## Usage

Run the assistant:
```bash
python src/assistant.py
```

Run the admin web portal:
```bash
python src/admin_portal.py
```

### Admin Portal Endpoints

Access via `http://<jetson-ip>:8080`:

| Endpoint | Description |
|----------|-------------|
| `/settings` | Configure wake word, LLM provider, audio devices, Whisper settings |
| `/stats` | Real-time system stats (CPU, memory, disk) with historical graphs |
| `/history` | Query history with token usage analytics |
| `/ollama` | Manage Ollama models (pull, delete, view installed) |

### LLM Configuration

**OpenAI (Cloud)**:
- Set your API key in the admin portal or `.env`
- Select model: `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`, or `gpt-3.5-turbo`

**Ollama (Local)**:
- Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
- Pull a model: `ollama pull llama3.2:1b` (or use the admin portal)
- Set LLM provider to "Ollama" in admin portal
- Recommended models for Jetson: `llama3.2:1b`, `phi3:mini`, `tinyllama`

## Deployment (Jetson)

This project is intended to run on a Jetson Nano as two `systemd` services:

- `voice-assistant` (the assistant)
- `voice-assistant-portal` (the LAN-only admin portal)

### Install on the Jetson

1. Clone the repo onto the Jetson (recommended path):
   ```bash
   git clone <your-github-repo-url> ~/jetson-voice-assistant
   ```

2. Install + enable services:
   ```bash
   bash ~/jetson-voice-assistant/scripts/install_jetson.sh
   ```

3. Edit `~/jetson-voice-assistant/.env` (at minimum set `OPENAI_API_KEY` if you want API features).

4. Confirm services:
   ```bash
   systemctl status voice-assistant
   systemctl status voice-assistant-portal
   ```

### Update on the Jetson

```bash
bash ~/jetson-voice-assistant/scripts/update_jetson.sh
```

### Voice Commands

1. Say your **wake word** (default: "jetson") to activate
2. Wait for "Yes?" response (or say command immediately after wake word)
3. Give your command:
   - **"What time is it?"** - Get the current time
   - **"What's today's date?"** - Get the current date
   - **"Tell me a joke"** - Hear a random joke
   - **"Search for [query]"** - Search the web
   - **"Hello" / "Hi"** - Greeting
   - **"Thank you"** - Acknowledgment
   - **"Goodbye"** - Exit the assistant
   - **Any other question** - Routes to configured LLM (OpenAI or Ollama)

**Tip**: You can combine the wake word with your command: *"Jetson, what time is it?"*

## Configuration

Settings can be configured via the admin portal or by editing files directly:

| File | Purpose |
|------|---------|
| `config/settings.json` | All assistant settings (persisted by portal) |
| `.env` | Environment variables (fallback, not tracked in git) |
| `.env.example` | Template for `.env` file |

### Settings Priority

Settings are loaded with this priority (highest first):
1. `config/settings.json` (set via admin portal)
2. `.env` file
3. Built-in defaults

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `wake_word` | `jetson` | Word to activate the assistant |
| `whisper_mode` | `local` | `local` (faster-whisper) or `api` (OpenAI) |
| `whisper_model_size` | `small` | Whisper model: `tiny`, `base`, `small`, `medium` |
| `whisper_language` | `en` | Language code for speech recognition |
| `llm_provider` | `openai` | `openai` or `ollama` |
| `llm_model` | `gpt-4o-mini` | Model name for the selected provider |
| `ollama_host` | `http://localhost:11434` | Ollama API endpoint |
| `audio_record_seconds` | `4` | Recording duration after wake word |
| `tts_provider` | `gtts` | TTS engine: `gtts`, `espeak`, or `pyttsx3` |
| `tts_language` | `en` | Language code for text-to-speech |
| `tts_speed` | `150` | Speech rate for espeak/pyttsx3 (words per minute) |

## Customization

Extend the assistant by adding new commands to the `process_command` method in `src/assistant.py`.

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Microphone not detected | Check USB. Run `arecord -l` to list devices |
| No audio output | Test with `aplay -D plughw:2,0 /usr/share/sounds/alsa/Front_Center.wav` |
| Wake word not responding | Check logs, try speaking closer to mic |
| TTS sounds robotic | Switch to gTTS in admin portal (requires internet) |
| OpenAI errors | Verify API key in portal, check billing at platform.openai.com |
| Ollama not connecting | Ensure Ollama is running: `systemctl status ollama` |
| Settings not applying | Restart services or wait for reload signal |

### Useful Commands

```bash
# View assistant logs (live)
journalctl -u voice-assistant -f

# View portal logs (live)
journalctl -u voice-assistant-portal -f

# Restart both services
sudo systemctl restart voice-assistant voice-assistant-portal

# Check service status
systemctl status voice-assistant voice-assistant-portal

# Test microphone (records 3 seconds)
arecord -D hw:2,0 -f S16_LE -r 16000 -c 1 -d 3 test.wav

# Test speaker
aplay -D plughw:2,0 test.wav

# List audio devices
arecord -l  # Input devices
aplay -l    # Output devices

# Check Ollama status
curl http://localhost:11434/api/tags
```

## License

This project is open source and available under the MIT License.

## Project Structure

```
jetson-voice-assistant/
├── src/
│   ├── assistant.py        # Main voice assistant
│   ├── admin_portal.py     # Flask web portal
│   ├── settings_store.py   # Settings management
│   ├── history_store.py    # Query/stats history
│   ├── ollama_client.py    # Ollama API client
│   └── audio_devices.py    # Audio device detection
├── config/
│   └── settings.json       # Persisted settings
├── deploy/
│   ├── voice-assistant.service.template
│   └── voice-assistant-portal.service.template
├── scripts/
│   ├── install_jetson.sh   # Full installation script
│   └── update_jetson.sh    # Update and restart script
├── .env.example            # Environment template
└── requirements.txt        # Python dependencies
```

## Acknowledgments

- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Local speech recognition
- [gTTS](https://github.com/pndurette/gTTS) - Google Text-to-Speech
- [OpenAI](https://openai.com/) - GPT and Whisper API
- [Ollama](https://ollama.com/) - Local LLM inference
- [Flask](https://flask.palletsprojects.com/) - Admin portal
- [Chart.js](https://www.chartjs.org/) - Stats visualization
- [pyjokes](https://github.com/pyjokes/pyjokes) - Jokes
