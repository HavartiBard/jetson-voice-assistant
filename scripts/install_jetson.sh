#!/usr/bin/env bash
#
# Jetson Voice Assistant - Installation Script
# Installs system dependencies, Python packages, and configures systemd services.
#
# Usage:
#   ./install_jetson.sh              # Native installation (systemd)
#   ./install_jetson.sh --container  # Container installation (Docker)
#
set -euo pipefail

# Configuration
APP_DIR=${APP_DIR:-"$HOME/jetson-voice-assistant"}
JETSON_USER=${JETSON_USER:-"$USER"}
MIN_PYTHON_VERSION="3.10"
USE_CONTAINER=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --container|-c)
      USE_CONTAINER=true
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --container, -c  Install using Docker containers"
      echo "  --help, -h       Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "=========================================="
if [[ "${USE_CONTAINER}" == "true" ]]; then
  echo "  Jetson Voice Assistant - Container Install"
else
  echo "  Jetson Voice Assistant - Native Install"
fi
echo "=========================================="
echo ""

log_info "Configuration:"
echo "  APP_DIR:     ${APP_DIR}"
echo "  JETSON_USER: ${JETSON_USER}"
echo "  MODE:        $(if [[ "${USE_CONTAINER}" == "true" ]]; then echo 'Container'; else echo 'Native'; fi)"
echo ""

# --- Pre-flight checks ---

# Check if running as root (we need sudo but shouldn't run the whole script as root)
if [[ $EUID -eq 0 ]]; then
  log_warn "Running as root. Services will be configured for user: ${JETSON_USER}"
fi

# Check app directory exists
if [[ ! -d "${APP_DIR}" ]]; then
  log_error "${APP_DIR} does not exist."
  echo "  Clone the repository first:"
  echo "    git clone <repo-url> ${APP_DIR}"
  exit 1
fi
log_ok "App directory found"

# --- Container Installation Path ---
if [[ "${USE_CONTAINER}" == "true" ]]; then
  # Check for Docker
  if ! command -v docker &> /dev/null; then
    log_error "Docker not found. Install Docker first:"
    echo "  curl -fsSL https://get.docker.com | sh"
    echo "  sudo usermod -aG docker ${JETSON_USER}"
    exit 1
  fi
  log_ok "Docker found"

  # Check for docker-compose (v2 plugin or standalone)
  if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
  elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
  else
    log_error "Docker Compose not found. Install it first."
    exit 1
  fi
  log_ok "Docker Compose found (${COMPOSE_CMD})"

  # Check for required container files
  for file in Dockerfile docker-compose.yml requirements.txt .env.example; do
    if [[ ! -f "${APP_DIR}/${file}" ]]; then
      log_error "Missing required file: ${file}"
      exit 1
    fi
  done
  log_ok "Required container files present"

  # --- Create .env if needed ---
  if [[ ! -f "${APP_DIR}/.env" ]]; then
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    log_ok "Created .env from template"
    log_warn "Edit ${APP_DIR}/.env to add your API keys (optional)"
  else
    log_ok ".env file already exists"
  fi

  # --- Ensure directories exist ---
  mkdir -p "${APP_DIR}/config" "${APP_DIR}/models"
  log_ok "Config and models directories ready"

  # --- Detect audio device ---
  log_info "Detecting audio devices..."
  DETECTED_DEVICE=$(arecord -l 2>/dev/null | grep -m1 'USB\|card' | sed -n 's/card \([0-9]*\):.*/hw:\1,0/p' || echo "hw:0,0")
  log_ok "Detected audio device: ${DETECTED_DEVICE}"

  # Set audio device in environment if not already set
  if ! grep -q "^AUDIO_INPUT_DEVICE=" "${APP_DIR}/.env" 2>/dev/null; then
    echo "AUDIO_INPUT_DEVICE=${DETECTED_DEVICE}" >> "${APP_DIR}/.env"
    echo "AUDIO_OUTPUT_DEVICE=${DETECTED_DEVICE/hw:/plughw:}" >> "${APP_DIR}/.env"
    log_ok "Added audio device to .env"
  fi

  # --- Build containers ---
  log_info "Building Docker containers (this may take several minutes)..."
  cd "${APP_DIR}"
  ${COMPOSE_CMD} build --quiet
  log_ok "Containers built"

  # --- Start containers ---
  log_info "Starting containers..."
  ${COMPOSE_CMD} up -d

  # Brief wait to check if containers started
  sleep 3
  if ${COMPOSE_CMD} ps | grep -q "voice-assistant.*Up"; then
    log_ok "voice-assistant container running"
  else
    log_warn "voice-assistant container may have issues - check logs"
  fi

  if ${COMPOSE_CMD} ps | grep -q "voice-assistant-portal.*Up"; then
    log_ok "voice-assistant-portal container running"
  else
    log_warn "voice-assistant-portal container may have issues - check logs"
  fi

  # --- Detect IP for portal URL ---
  LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "<jetson-ip>")

  echo ""
  echo "=========================================="
  echo "  Container Installation Complete!"
  echo "=========================================="
  echo ""
  echo "  Admin Portal: http://${LOCAL_IP}:8080/settings"
  echo ""
  echo "  Useful commands:"
  echo "    ${COMPOSE_CMD} logs -f assistant  # View assistant logs"
  echo "    ${COMPOSE_CMD} logs -f portal     # View portal logs"
  echo "    ${COMPOSE_CMD} restart            # Restart all containers"
  echo "    ${COMPOSE_CMD} down               # Stop all containers"
  echo "    ${COMPOSE_CMD} pull && ${COMPOSE_CMD} up -d --build  # Update"
  echo ""
  echo "  Optional: Install Ollama for local LLM:"
  echo "    curl -fsSL https://ollama.com/install.sh | sh"
  echo "    ollama pull llama3.2:1b"
  echo ""
  exit 0
fi

# --- Native Installation Path ---

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
if [[ "$(printf '%s\n' "${MIN_PYTHON_VERSION}" "${PYTHON_VERSION}" | sort -V | head -n1)" != "${MIN_PYTHON_VERSION}" ]]; then
  log_error "Python ${MIN_PYTHON_VERSION}+ required, found ${PYTHON_VERSION}"
  exit 1
fi
log_ok "Python ${PYTHON_VERSION} detected"

# Check for required files
for file in requirements.txt .env.example deploy/voice-assistant.service.template deploy/voice-assistant-portal.service.template; do
  if [[ ! -f "${APP_DIR}/${file}" ]]; then
    log_error "Missing required file: ${file}"
    exit 1
  fi
done
log_ok "Required files present"

# --- Install system dependencies ---
log_info "Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
  python3-venv \
  portaudio19-dev \
  espeak \
  ffmpeg \
  alsa-utils \
  > /dev/null
log_ok "System dependencies installed"

# --- Create virtual environment ---
if [[ -d "${APP_DIR}/venv" ]]; then
  log_warn "Virtual environment exists, will upgrade packages"
else
  log_info "Creating virtual environment..."
  python3 -m venv "${APP_DIR}/venv"
  log_ok "Virtual environment created"
fi

log_info "Installing Python packages (this may take a few minutes)..."
"${APP_DIR}/venv/bin/pip" install --upgrade pip -q
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q
log_ok "Python packages installed"

# --- Create .env if needed ---
if [[ ! -f "${APP_DIR}/.env" ]]; then
  cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  log_ok "Created .env from template"
  log_warn "Edit ${APP_DIR}/.env to add your API keys (optional)"
else
  log_ok ".env file already exists"
fi

# --- Ensure config directory exists ---
mkdir -p "${APP_DIR}/config"

# --- Install systemd services ---
log_info "Installing systemd services..."

sed \
  -e "s#__JETSON_USER__#${JETSON_USER}#g" \
  -e "s#__APP_DIR__#${APP_DIR}#g" \
  "${APP_DIR}/deploy/voice-assistant.service.template" \
  | sudo tee /etc/systemd/system/voice-assistant.service > /dev/null

sed \
  -e "s#__JETSON_USER__#${JETSON_USER}#g" \
  -e "s#__APP_DIR__#${APP_DIR}#g" \
  "${APP_DIR}/deploy/voice-assistant-portal.service.template" \
  | sudo tee /etc/systemd/system/voice-assistant-portal.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable voice-assistant.service voice-assistant-portal.service > /dev/null 2>&1
log_ok "Systemd services installed and enabled"

# --- Start services ---
log_info "Starting services..."
sudo systemctl restart voice-assistant.service voice-assistant-portal.service

# Brief wait to check if services started
sleep 2
if systemctl is-active --quiet voice-assistant.service; then
  log_ok "voice-assistant service running"
else
  log_warn "voice-assistant service may have issues - check logs"
fi

if systemctl is-active --quiet voice-assistant-portal.service; then
  log_ok "voice-assistant-portal service running"
else
  log_warn "voice-assistant-portal service may have issues - check logs"
fi

# --- Detect IP for portal URL ---
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "<jetson-ip>")

echo ""
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
echo "  Admin Portal: http://${LOCAL_IP}:8080/settings"
echo ""
echo "  Useful commands:"
echo "    journalctl -u voice-assistant -f        # View assistant logs"
echo "    journalctl -u voice-assistant-portal -f # View portal logs"
echo "    sudo systemctl restart voice-assistant voice-assistant-portal"
echo ""
echo "  Optional: Install Ollama for local LLM:"
echo "    curl -fsSL https://ollama.com/install.sh | sh"
echo "    ollama pull llama3.2:1b"
echo ""
