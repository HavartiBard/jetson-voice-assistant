# Deploying with Portainer

## Quick Setup

### 1. Add Stack from Git Repository

1. **Stacks** → **Add stack** → **Repository**
2. **Repository URL**: `https://github.com/HavartiBard/jetson-voice-assistant`
3. **Reference**: `main` (or `feature/containerization`)
4. **Compose path**: `docker-compose.stack.yml`

### 2. Set Environment Variables

In the Portainer stack editor, add these environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AUDIO_INPUT_DEVICE` | Yes | `hw:0,0` | ALSA input device (find with `arecord -l`) |
| `AUDIO_OUTPUT_DEVICE` | No | `plughw:0,0` | ALSA output device |
| `OPENAI_API_KEY` | No* | - | OpenAI API key for GPT |
| `PICOVOICE_ACCESS_KEY` | No | - | Picovoice key for wake word |
| `WAKE_WORD` | No | `computer` | Wake word (computer, jarvis, alexa, etc.) |
| `WHISPER_MODE` | No | `local` | `local` or `api` |
| `WHISPER_MODEL_SIZE` | No | `small` | tiny, base, small, medium, large |
| `LLM_PROVIDER` | No | `openai` | `openai` or `ollama` |
| `OLLAMA_HOST` | No | `http://host.docker.internal:11434` | Ollama API endpoint |
| `CONFIG_PATH` | No | `./config` | Host path for config persistence |
| `MODELS_PATH` | No | `./models` | Host path for model cache |

*Required if using OpenAI for LLM or Whisper API mode.

### 3. Prepare Host Directories

Before deploying, create the config and models directories on the Jetson:

```bash
mkdir -p ~/voice-assistant/config ~/voice-assistant/models
```

Then set `CONFIG_PATH=/home/james/voice-assistant/config` and `MODELS_PATH=/home/james/voice-assistant/models` in Portainer.

### 4. Deploy

Click **Deploy the stack**.

---

## Auto-Update with Webhooks

Portainer can automatically redeploy when new images are pushed:

1. In your stack, click **Webhooks**
2. **Create a webhook**
3. Copy the webhook URL
4. Add it to your GitHub repo: **Settings** → **Webhooks** → **Add webhook**
   - Payload URL: (paste Portainer webhook URL)
   - Content type: `application/json`
   - Events: Select "Workflow runs" or "Packages"

Now when GitHub Actions builds a new image, Portainer will auto-redeploy.

---

## Finding Audio Devices

SSH to the Jetson and run:

```bash
# List recording devices
arecord -l

# Example output:
# card 2: Device [USB Audio Device], device 0: USB Audio [USB Audio]
#   → Use hw:2,0 for AUDIO_INPUT_DEVICE
```

---

## Troubleshooting

### Container can't access audio
- Ensure `/dev/snd` is accessible
- Check the user is in the `audio` group
- Try setting `privileged: true` temporarily

### Ollama connection refused
- Ensure Ollama is running on the host
- The `host.docker.internal` should resolve to the host IP
- Or set `OLLAMA_HOST=http://<host-ip>:11434`

### View logs
In Portainer: Click container → **Logs**

Or via CLI:
```bash
docker logs -f voice-assistant
docker logs -f voice-assistant-portal
```
