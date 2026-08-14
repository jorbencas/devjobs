#!/bin/bash
# Iniciar sesión del uploader de Telegram (crea/autentica uploader.session).
# Interactivo: pide teléfono + código. Solo es necesario una vez.
# Uso:  bash servicios/pipe_setup.sh
set -e
cd /home/jorge/dev/devjobs/downloader_telegram

if [ ! -f uploader.session ]; then
    touch uploader.session   # evitar que Docker lo monte como directorio
fi

docker compose run --rm uploader python /app/subir_videos.py --setup