#!/bin/bash
# Iniciar sesión del uploader de Telegram (crea/autentica sessions/uploader.session).
# Interactivo: pide teléfono + código (y 2FA si la tienes). Solo es necesario una vez.
# Uso:  bash servicios/pipe_setup.sh [--reset]
#   --reset  borra la sesión actual antes de loguear (si está corrupta/vencida,
#            o si la copiaste a medias desde la máquina vieja).
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/downloader_telegram"
mkdir -p sessions

if [ "${1:-}" = "--reset" ]; then
    rm -f sessions/uploader.session
    echo "[i] Sesión previa borrada: sessions/uploader.session"
fi

docker compose run --rm uploader python -u /app/app/subir_videos.py --setup
