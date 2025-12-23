# Jetson Voice Assistant - Container Image
# Optimized for NVIDIA Jetson devices (ARM64)
#
# Build: docker build -t jetson-voice-assistant .
# Run:   docker-compose up -d

ARG BASE_IMAGE=python:3.10-slim-bookworm

FROM ${BASE_IMAGE}

LABEL maintainer="Jetson Voice Assistant"
LABEL description="Voice assistant with wake word detection, STT, and LLM integration"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Audio stack
    alsa-utils \
    portaudio19-dev \
    pulseaudio \
    # TTS
    espeak \
    espeak-ng \
    # Media processing
    ffmpeg \
    # Build tools (for some Python packages)
    build-essential \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app user (non-root for security, but in audio group)
RUN groupadd -r assistant && \
    useradd -r -g assistant -G audio -d /app assistant && \
    mkdir -p /app /app/config /app/models /app/.cache && \
    chown -R assistant:assistant /app

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY --chown=assistant:assistant requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    # Create openWakeWord resources directory with proper permissions
    mkdir -p /usr/local/lib/python3.10/site-packages/openwakeword/resources && \
    chmod -R 777 /usr/local/lib/python3.10/site-packages/openwakeword/resources

# Copy application code
COPY --chown=assistant:assistant src/ ./src/
COPY --chown=assistant:assistant .env.example .

# Create default config directory structure
RUN mkdir -p /app/config && chown -R assistant:assistant /app/config

# Switch to non-root user
USER assistant

# Default environment variables (can be overridden)
ENV HOME=/app
ENV HF_HOME=/app/models
ENV WHISPER_MODE=local
ENV WHISPER_MODEL_SIZE=small
ENV WHISPER_LANGUAGE=en
ENV AUDIO_SAMPLE_RATE=16000
ENV AUDIO_CHANNELS=1
ENV AUDIO_RECORD_SECONDS=4

# Health check - verify Python can import main modules
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "from src.assistant import VoiceAssistant; print('OK')" || exit 1

# Expose admin portal port
EXPOSE 8080

# Default command runs the voice assistant
CMD ["python", "src/assistant.py"]
