#!/bin/bash
# Listar los chats/grupos/canales desde la sesión del uploader.
# Opciones: [--creados] [--folder <texto>]
#   --creados  -> solo los que creaste tú
#   --folder   -> filtra por nombre de chat o archivado/principal
# Uso:  bash servicios/pipe_chats.sh [--creados] [--folder <texto>]
cd /home/jorge/dev/devjobs/downloader_telegram

docker compose run --rm uploader python /app/subir_videos.py --list-chats "$@"