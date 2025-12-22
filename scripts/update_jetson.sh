#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-"$HOME/jetson-voice-assistant"}

if [[ ! -d "${APP_DIR}/.git" ]]; then
  echo "ERROR: ${APP_DIR} is not a git repo"
  exit 1
fi

echo "Updating repo in ${APP_DIR}..."
git -C "${APP_DIR}" pull

if [[ ! -d "${APP_DIR}/venv" ]]; then
  python3 -m venv "${APP_DIR}/venv"
fi

"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

sudo systemctl restart voice-assistant.service voice-assistant-portal.service

echo "Updated and restarted services."
