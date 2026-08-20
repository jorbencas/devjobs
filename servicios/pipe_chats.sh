#!/bin/bash
# Listar los chats/grupos/canales desde la sesión del uploader.
# Opciones: [--creados] [--folder <texto>]
#   --creados  -> solo los que creaste tú
#   --folder   -> filtra por nombre de chat o archivado/principal
# Uso:  bash servicios/pipe_chats.sh [--creados] [--folder <texto>]
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/downloader_telegram"

docker compose run --rm uploader python /app/app/subir_videos.py --list-chats "$@"