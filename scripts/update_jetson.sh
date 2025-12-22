#!/usr/bin/env bash
#
# Jetson Voice Assistant - Update Script
# Pulls latest code, updates packages, and restarts services.
#
set -euo pipefail

APP_DIR=${APP_DIR:-"$HOME/jetson-voice-assistant"}

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
echo "  Jetson Voice Assistant - Updater"
echo "=========================================="
echo ""

# --- Validate ---
if [[ ! -d "${APP_DIR}/.git" ]]; then
  log_error "${APP_DIR} is not a git repository"
  exit 1
fi

# --- Pull latest code ---
log_info "Pulling latest code..."
cd "${APP_DIR}"
BEFORE=$(git rev-parse HEAD)
git pull --ff-only
AFTER=$(git rev-parse HEAD)

if [[ "${BEFORE}" == "${AFTER}" ]]; then
  log_ok "Already up to date"
else
  log_ok "Updated: $(git log --oneline -1)"
fi

# --- Update Python packages ---
if [[ ! -d "${APP_DIR}/venv" ]]; then
  log_warn "Virtual environment missing, creating..."
  python3 -m venv "${APP_DIR}/venv"
fi

log_info "Updating Python packages..."
"${APP_DIR}/venv/bin/pip" install --upgrade pip -q
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q
log_ok "Python packages updated"

# --- Restart services ---
log_info "Restarting services..."
sudo systemctl restart voice-assistant.service voice-assistant-portal.service

sleep 2
if systemctl is-active --quiet voice-assistant.service && systemctl is-active --quiet voice-assistant-portal.service; then
  log_ok "Services restarted successfully"
else
  log_warn "One or more services may have issues - check logs"
fi

# --- Show status ---
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "<jetson-ip>")

echo ""
echo "=========================================="
echo "  Update Complete!"
echo "=========================================="
echo ""
echo "  Admin Portal: http://${LOCAL_IP}:8080/settings"
echo "  View logs:    journalctl -u voice-assistant -f"
echo ""
