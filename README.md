# Jetson Voice Assistant

A customizable voice assistant designed specifically for the NVIDIA Jetson Nano/Orin. Uses wake word detection, local Whisper speech recognition, and natural text-to-speech with support for both cloud and local LLMs.

## Features

- 🎙️ **Wake word activation** - Customizable wake word (computer, jarvis, alexa, etc.)
- 🗣️ **Local speech recognition** using faster-whisper (runs on-device) or OpenAI Whisper API
- 🔊 **Configurable text-to-speech** - Google TTS, eSpeak, or pyttsx3 (offline options available)
- 🤖 **Dual LLM support** - OpenAI API or local Ollama models
- 🌐 **Admin web portal** for configuration, monitoring, and LLM management
- 📊 **System stats** with real-time CPU/memory/disk graphs
- 📝 **Query history** with token usage tracking and analytics
- 🔌 **Audio device detection** - Auto-detects USB audio devices
- 🐳 **Container-first deployment** - Docker Compose for easy installation
- ⏰ Built-in commands: time, date, jokes, web search, greetings

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Jetson Device                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  Docker Compose                                                          │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────┐ │
│  │  voice-assistant        │    │      voice-assistant-portal         │ │
│  │    (container)          │    │          (container)                │ │
│  │                         │    │                                     │ │
│  │ • Porcupine wake word   │    │ • Dashboard (:8080)                 │ │
│  │ • Whisper STT           │◄──►│ • Settings UI (:8080/settings)      │ │
│  │ • LLM (OpenAI/Ollama)   │    │ • System stats (:8080/stats)        │ │
│  │ • gTTS/espeak TTS       │    │ • Query history (:8080/history)     │ │
│  │ • /dev/snd passthrough  │    │ • Ollama models (:8080/llm)         │ │
│  └────────┬────────────────┘    └─────────────────────────────────────┘ │
│           │                                                              │
│  ┌────────▼─────────┐    ┌───────────────────────────────────────────┐  │
│  │ Shared Volumes   │    │ External Services (optional)              │  │
│  │ • ./config       │    │ • OpenAI API (cloud LLM/Whisper)          │  │
│  │ • ./models       │    │ • Ollama (host or remote, local LLM)      │  │
│  └──────────────────┘    └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- NVIDIA Jetson Nano/Orin with JetPack (or any Linux system with Docker)
- **Docker** and **Docker Compose** installed
- USB microphone/speaker (e.g., Jabra SPEAK 510) or ALSA-compatible audio
- Internet connection for cloud features (Google TTS, OpenAI)
- **Optional**: OpenAI API key for cloud LLM and Whisper API
- **Optional**: Picovoice access key for Porcupine wake word detection
- **Optional**: Ollama for local LLM inference

---

## Quick Start (Docker - Recommended)

### 1. Install Docker on Jetson

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose plugin
sudo apt-get install -y docker-compose-plugin
```

### 2. Deploy the Voice Assistant

```bash
# Clone the repository
git clone https://github.com/HavartiBard/jetson-voice-assistant.git
cd jetson-voice-assistant

# Create config directories
mkdir -p config models

# Copy and edit environment file
cp .env.example .env
nano .env  # Add your API keys

# Find your audio device
arecord -l  # Note the card number (e.g., card 2 = hw:2,0)

# Set audio device in .env
echo "AUDIO_INPUT_DEVICE=hw:2,0" >> .env
echo "AUDIO_OUTPUT_DEVICE=plughw:2,0" >> .env

# Start the containers
docker compose -f docker-compose.prod.yml up -d
```

### 3. Access the Admin Portal

Open `http://<jetson-ip>:8080` in your browser.

### Useful Docker Commands

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f assistant
docker compose -f docker-compose.prod.yml logs -f portal

# Restart services
docker compose -f docker-compose.prod.yml restart

# Update to latest image
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# Stop everything
docker compose -f docker-compose.prod.yml down
```

---

## Portainer Deployment

For a GUI-based deployment, see [deploy/PORTAINER.md](deploy/PORTAINER.md).

---

## Native Installation (Alternative)

If you prefer running without Docker:

```bash
# Clone and setup
git clone https://github.com/HavartiBard/jetson-voice-assistant.git ~/jetson-voice-assistant
cd ~/jetson-voice-assistant

# Run install script (installs deps, creates venv, sets up systemd services)
bash scripts/install_jetson.sh

# Edit environment
nano .env  # Add API keys
```

See `scripts/install_jetson.sh` for details. This installs systemd services for native deployment.

---

## Admin Portal

Access via `http://<jetson-ip>:8080`:

| Endpoint | Description |
|----------|-------------|
| `/` | Dashboard with service status and analytics |
| `/settings` | Configure wake word, LLM provider, audio devices, Whisper settings |
| `/devices` | Audio device selection and volume controls |
| `/stats` | Real-time system stats (CPU, memory, disk) with historical graphs |
| `/history` | Query history with token usage analytics |
| `/llm` | LLM provider settings and Ollama model management |

---

## LLM Configuration

**OpenAI (Cloud)**:
- Set `OPENAI_API_KEY` in `.env` or via the admin portal
- Select model: `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`, or `gpt-3.5-turbo`

**Ollama (Local)**:
- Install Ollama on the host: `curl -fsSL https://ollama.com/install.sh | sh`
- Pull a model: `ollama pull llama3.2:1b`
- Set `LLM_PROVIDER=ollama` and `OLLAMA_HOST=http://host.docker.internal:11434` in `.env`
- Recommended models for Jetson: `llama3.2:1b`, `phi3:mini`, `tinyllama`

---

## Voice Commands

1. Say your **wake word** (default: "computer") to activate
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

**Tip**: Combine wake word with command: *"Computer, what time is it?"*

**Supported wake words** (Porcupine): `computer`, `jarvis`, `alexa`, `bumblebee`, `picovoice`, `hey google`

## Configuration

### Environment Variables (`.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AUDIO_INPUT_DEVICE` | Yes | `hw:0,0` | ALSA input device (`arecord -l` to find) |
| `AUDIO_OUTPUT_DEVICE` | No | `plughw:0,0` | ALSA output device |
| `OPENAI_API_KEY` | No* | - | OpenAI API key for GPT/Whisper |
| `PICOVOICE_ACCESS_KEY` | No | - | Picovoice key for Porcupine wake word |
| `WAKE_WORD` | No | `computer` | Wake word (computer, jarvis, alexa, etc.) |
| `WHISPER_MODE` | No | `local` | `local` or `api` |
| `WHISPER_MODEL_SIZE` | No | `small` | tiny, base, small, medium, large |
| `LLM_PROVIDER` | No | `openai` | `openai` or `ollama` |
| `LLM_MODEL` | No | `gpt-4o-mini` | Model name for selected provider |
| `OLLAMA_HOST` | No | `http://host.docker.internal:11434` | Ollama endpoint |
| `TTS_PROVIDER` | No | `gtts` | `gtts`, `espeak`, or `pyttsx3` |

*Required if using OpenAI for LLM or Whisper API mode.

### Settings Priority

1. `config/settings.json` (set via admin portal) - highest
2. `.env` file
3. Built-in defaults

### Wake Word Detection

- **With Picovoice key**: Uses Porcupine for fast, accurate wake word detection
- **Without key**: Falls back to Whisper-based detection (higher latency)

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Microphone not detected | Check USB. Run `arecord -l` on host to list devices |
| No audio output | Test: `aplay -D plughw:2,0 /usr/share/sounds/alsa/Front_Center.wav` |
| Wake word not responding | Check logs, verify Picovoice key, try speaking closer |
| TTS sounds robotic | Switch to gTTS in admin portal (requires internet) |
| OpenAI errors | Verify API key in portal, check billing |
| Ollama not connecting | Ensure Ollama running on host, check `OLLAMA_HOST` |
| Container can't access audio | Check `/dev/snd` permissions, try `privileged: true` |

### Useful Commands

```bash
# Docker logs
docker compose -f docker-compose.prod.yml logs -f assistant
docker compose -f docker-compose.prod.yml logs -f portal

# Restart containers
docker compose -f docker-compose.prod.yml restart

# Shell into container
docker exec -it voice-assistant bash

# List audio devices (on host)
arecord -l  # Input devices
aplay -l    # Output devices

# Test microphone (on host)
arecord -D hw:2,0 -f S16_LE -r 16000 -c 1 -d 3 test.wav
aplay -D plughw:2,0 test.wav

# Check Ollama (on host)
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
├── config/                 # Persistent config (Docker volume)
│   └── settings.json       # Persisted settings
├── models/                 # Whisper model cache (Docker volume)
├── deploy/
│   ├── PORTAINER.md        # Portainer deployment guide
│   └── *.service.template  # Systemd templates (native install)
├── .github/workflows/
│   └── docker-publish.yml  # CI/CD for container builds
├── Dockerfile              # Container image definition
├── docker-compose.yml      # Local development
├── docker-compose.prod.yml # Production (pre-built images)
├── docker-compose.stack.yml # Portainer stack
├── .env.example            # Environment template
└── requirements.txt        # Python dependencies
```

## Acknowledgments

- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Local speech recognition
- [Picovoice Porcupine](https://picovoice.ai/platform/porcupine/) - Wake word detection
- [gTTS](https://github.com/pndurette/gTTS) - Google Text-to-Speech
- [OpenAI](https://openai.com/) - GPT and Whisper API
- [Ollama](https://ollama.com/) - Local LLM inference
- [Flask](https://flask.palletsprojects.com/) - Admin portal
- [Chart.js](https://www.chartjs.org/) - Stats visualization
