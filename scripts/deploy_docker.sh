#!/usr/bin/env bash
#
# Jetson Voice Assistant - Docker Deployment Script
# Deploys the voice assistant using pre-built container images.
#
set -euo pipefail

# Configuration
APP_DIR=${APP_DIR:-"$HOME/jetson-voice-assistant"}
COMPOSE_FILE="docker-compose.prod.yml"

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
echo "  Jetson Voice Assistant - Docker Deploy"
echo "=========================================="
echo ""

# --- Pre-flight checks ---

# Check Docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed."
    echo ""
    echo "Install Docker with:"
    echo "  curl -fsSL https://get.docker.com | sh"
    echo "  sudo usermod -aG docker \$USER"
    echo "  newgrp docker"
    exit 1
fi
log_ok "Docker installed"

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    log_error "Docker Compose plugin not found."
    echo ""
    echo "Install with:"
    echo "  sudo apt-get install -y docker-compose-plugin"
    exit 1
fi
log_ok "Docker Compose available"

# Check app directory exists
if [[ ! -d "${APP_DIR}" ]]; then
    log_error "${APP_DIR} does not exist."
    echo "  Clone the repository first:"
    echo "    git clone https://github.com/HavartiBard/jetson-voice-assistant.git ${APP_DIR}"
    exit 1
fi
log_ok "App directory found: ${APP_DIR}"

cd "${APP_DIR}"

# --- Create directories ---
log_info "Creating config and models directories..."
mkdir -p config models
log_ok "Directories created"

# --- Create .env if needed ---
if [[ ! -f ".env" ]]; then
    if [[ -f ".env.example" ]]; then
        cp .env.example .env
        log_ok "Created .env from template"
        log_warn "Edit .env to configure your settings"
    else
        log_error ".env.example not found"
        exit 1
    fi
else
    log_ok ".env file exists"
fi

# --- Detect audio device ---
log_info "Detecting audio devices..."
if command -v arecord &> /dev/null; then
    echo ""
    arecord -l 2>/dev/null || true
    echo ""
    
    # Try to auto-detect USB device
    USB_CARD=$(arecord -l 2>/dev/null | grep -i "usb" | head -1 | sed -n 's/card \([0-9]*\):.*/\1/p' || echo "")
    if [[ -n "${USB_CARD}" ]]; then
        log_info "Detected USB audio on card ${USB_CARD}"
        
        # Check if already set in .env
        if ! grep -q "^AUDIO_INPUT_DEVICE=" .env 2>/dev/null; then
            echo "" >> .env
            echo "# Auto-detected audio device" >> .env
            echo "AUDIO_INPUT_DEVICE=hw:${USB_CARD},0" >> .env
            echo "AUDIO_OUTPUT_DEVICE=plughw:${USB_CARD},0" >> .env
            log_ok "Added audio device to .env: hw:${USB_CARD},0"
        else
            log_info "AUDIO_INPUT_DEVICE already set in .env"
        fi
    else
        log_warn "No USB audio device detected. Set AUDIO_INPUT_DEVICE manually in .env"
    fi
else
    log_warn "arecord not found - cannot auto-detect audio devices"
fi

# --- Pull latest images ---
log_info "Pulling latest container images..."
docker compose -f "${COMPOSE_FILE}" pull
log_ok "Images pulled"

# --- Stop existing containers ---
log_info "Stopping any existing containers..."
docker compose -f "${COMPOSE_FILE}" down 2>/dev/null || true

# --- Start containers ---
log_info "Starting voice assistant containers..."
docker compose -f "${COMPOSE_FILE}" up -d
log_ok "Containers started"

# --- Wait for startup ---
sleep 3

# --- Check status ---
log_info "Checking container status..."
if docker ps --format "{{.Names}}" | grep -q "voice-assistant$"; then
    log_ok "voice-assistant container running"
else
    log_warn "voice-assistant container may have issues"
fi

if docker ps --format "{{.Names}}" | grep -q "voice-assistant-portal"; then
    log_ok "voice-assistant-portal container running"
else
    log_warn "voice-assistant-portal container may have issues"
fi

# --- Get IP for portal URL ---
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "<jetson-ip>")

echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "  Admin Portal: http://${LOCAL_IP}:8080"
echo ""
echo "  Useful commands:"
echo "    docker compose -f ${COMPOSE_FILE} logs -f assistant  # View assistant logs"
echo "    docker compose -f ${COMPOSE_FILE} logs -f portal     # View portal logs"
echo "    docker compose -f ${COMPOSE_FILE} restart            # Restart services"
echo "    docker compose -f ${COMPOSE_FILE} pull && docker compose -f ${COMPOSE_FILE} up -d  # Update"
echo ""
echo "  Configuration:"
echo "    Edit ${APP_DIR}/.env and restart containers"
echo ""
