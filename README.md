# Jetson Voice Assistant

A customizable voice assistant designed specifically for the NVIDIA Jetson Nano. This assistant can understand voice commands, answer questions, tell jokes, search the web, and more.

## Features

- 🎙️ Voice recognition using Whisper
- 🔊 Text-to-speech conversion
- ⏰ Time and date information
- 😄 Tells jokes
- 🌍 Web search capabilities
- 💬 General conversation using OpenAI's GPT-3.5
- 🔌 Extensible command system

## Prerequisites

- NVIDIA Jetson Nano with JetPack 4.6 or later
- Python 3.6+
- Microphone (USB or built-in)
- Speaker or audio output device
- OpenAI API key (for advanced features)

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

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   For Jetson Nano, you might need to install some dependencies manually:
   ```bash
   sudo apt-get install portaudio19-dev
   pip install pyaudio
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   nano .env  # Edit the file with your settings
   ```
   
   Make sure to add your OpenAI API key to the `.env` file.

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

- "What time is it?" - Get the current time
- "What's today's date?" - Get the current date
- "Tell me a joke" - Hear a random joke
- "Search for [query]" - Search the web
- "Goodbye" - Exit the assistant

## Customization

You can extend the assistant by adding new commands to the `process_command` method in `src/assistant.py`.

## Troubleshooting

- **Microphone not working**: Check if your microphone is properly connected and selected as the default input device.
- **Speech recognition issues**: Ensure you have a stable internet connection as the assistant uses Google's Speech Recognition service.
- **Performance issues**: The Jetson Nano might struggle with heavy processing. Try closing other applications to free up resources.

## License

This project is open source and available under the MIT License.

## Acknowledgments

- Google Speech Recognition
- OpenAI GPT-3.5
- PyAudio
- pyttsx3
- pyjokes
