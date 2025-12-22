#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-"$HOME/jetson-voice-assistant"}
JETSON_USER=${JETSON_USER:-"$USER"}

echo "Installing Jetson Voice Assistant"
echo "- APP_DIR: ${APP_DIR}"
echo "- JETSON_USER: ${JETSON_USER}"

if [[ ! -d "${APP_DIR}" ]]; then
  echo "ERROR: ${APP_DIR} does not exist. Clone the repo there first."
  exit 1
fi

python3 -m venv "${APP_DIR}/venv"
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

if [[ ! -f "${APP_DIR}/.env" ]]; then
  cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  echo "Created ${APP_DIR}/.env from .env.example (edit it to add secrets like OPENAI_API_KEY)."
fi

# Install systemd services
sudo mkdir -p /etc/systemd/system

sudo sed \
  -e "s#__JETSON_USER__#${JETSON_USER}#g" \
  -e "s#__APP_DIR__#${APP_DIR}#g" \
  "${APP_DIR}/deploy/voice-assistant.service.template" \
  > /etc/systemd/system/voice-assistant.service

sudo sed \
  -e "s#__JETSON_USER__#${JETSON_USER}#g" \
  -e "s#__APP_DIR__#${APP_DIR}#g" \
  "${APP_DIR}/deploy/voice-assistant-portal.service.template" \
  > /etc/systemd/system/voice-assistant-portal.service

sudo systemctl daemon-reload
sudo systemctl enable voice-assistant.service voice-assistant-portal.service
sudo systemctl restart voice-assistant.service voice-assistant-portal.service

echo "Done."
echo "- Portal: http://<jetson-ip>:8080/settings"
echo "- Logs: journalctl -u voice-assistant -f   OR   journalctl -u voice-assistant-portal -f"
