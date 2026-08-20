#!/bin/bash
# Iniciar sesión del uploader de Telegram (crea/autentica uploader.session).
# Interactivo: pide teléfono + código. Solo es necesario una vez.
# Uso:  bash servicios/pipe_setup.sh
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/downloader_telegram"

if [ ! -f uploader.session ]; then
    touch uploader.session   # evitar que Docker lo monte como directorio
fi

docker compose run --rm uploader python /app/app/subir_videos.py --setup