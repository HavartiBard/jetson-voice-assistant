# Jetson Voice Assistant

A customizable voice assistant designed specifically for the NVIDIA Jetson Nano/Orin. This assistant uses wake word detection, local Whisper speech recognition, and natural text-to-speech.

## Features

- 🎙️ **Wake word activation** - Say "jetson" to activate
- 🗣️ **Local speech recognition** using faster-whisper (runs on-device)
- 🔊 **Natural text-to-speech** using Google TTS (with espeak fallback)
- ⏰ Time and date information
- 😄 Tells jokes
- 🌍 Web search capabilities
- 💬 General conversation using OpenAI GPT (optional)
- 🌐 **Admin web portal** for configuration and monitoring
- 📊 **System stats** with historical graphs
- 📝 **Query history** tracking
- 🔌 Extensible command system

## Prerequisites

- NVIDIA Jetson Nano/Orin with JetPack
- Python 3.10+
- USB microphone/speaker (e.g., Jabra SPEAK 510)
- Internet connection (for Google TTS and OpenAI features)
- OpenAI API key (optional, for GPT conversation)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd jetson-voice-assistant
   ```

2. **Create and activate a virtual environment (recommended)**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install system dependencies**
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-venv portaudio19-dev espeak ffmpeg alsa-utils
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

Then open:

- **Settings**: `http://<jetson-ip>:8080/settings`
- **System stats**: `http://<jetson-ip>:8080/stats`

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

1. Say **"jetson"** (wake word) to activate the assistant
2. Wait for "Yes?" response
3. Give your command:
   - "What time is it?" - Get the current time
   - "What's today's date?" - Get the current date
   - "Tell me a joke" - Hear a random joke
   - "Search for [query]" - Search the web
   - "Hello" / "Hi" - Greeting
   - "Thank you" - Acknowledgment
   - "Goodbye" - Exit the assistant
   - Any other question - Uses OpenAI GPT (if configured)

## Customization

You can extend the assistant by adding new commands to the `process_command` method in `src/assistant.py`.

## Troubleshooting

- **Microphone not detected**: Check USB connection. List devices with `arecord -l`
- **No audio output**: Verify speaker with `aplay -D plughw:2,0 /usr/share/sounds/alsa/Front_Center.wav`
- **Wake word not detected**: Speak clearly, check logs with `journalctl -u voice-assistant -f`
- **TTS not working**: Ensure internet connection (gTTS requires it) or espeak will be used as fallback
- **OpenAI errors**: Check API key in admin portal, verify billing at platform.openai.com

### Useful Commands

```bash
# View assistant logs
journalctl -u voice-assistant -f

# View portal logs  
journalctl -u voice-assistant-portal -f

# Restart services
sudo systemctl restart voice-assistant voice-assistant-portal

# Test microphone
arecord -D hw:2,0 -f S16_LE -r 16000 -c 1 -d 3 test.wav

# Test speaker
aplay -D plughw:2,0 test.wav
```

## License

This project is open source and available under the MIT License.

## Acknowledgments

- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Local speech recognition
- [gTTS](https://github.com/pndurette/gTTS) - Google Text-to-Speech
- [OpenAI](https://openai.com/) - GPT conversation
- [Flask](https://flask.palletsprojects.com/) - Admin portal
- [Chart.js](https://www.chartjs.org/) - Stats visualization
- [pyjokes](https://github.com/pyjokes/pyjokes) - Jokes
