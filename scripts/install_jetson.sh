#!/usr/bin/env bash
#
# Jetson Voice Assistant - Installation Script
# Installs system dependencies, Python packages, and configures systemd services.
#
set -euo pipefail

# Configuration
APP_DIR=${APP_DIR:-"$HOME/jetson-voice-assistant"}
JETSON_USER=${JETSON_USER:-"$USER"}
MIN_PYTHON_VERSION="3.10"

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
echo "  Jetson Voice Assistant - Installer"
echo "=========================================="
echo ""

log_info "Configuration:"
echo "  APP_DIR:     ${APP_DIR}"
echo "  JETSON_USER: ${JETSON_USER}"
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
