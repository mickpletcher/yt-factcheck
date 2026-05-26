#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/opt/evidencechain}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "Missing $ENV_FILE. Create it from .env.production.example and add secrets."
    exit 1
fi

cd "$APP_DIR"
if [ -n "${EVIDENCECHAIN_API_IMAGE:-}" ] && [ -n "${EVIDENCECHAIN_WEB_IMAGE:-}" ]; then
    docker compose pull
fi

docker compose up -d --build --remove-orphans
docker compose ps
