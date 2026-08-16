#!/bin/bash
# Listar los temas (series) de un grupo con foro, desde la sesión del uploader.
# Los IDs que imprime son los que van en "temas" de grupos.json (junto a
# "grupo_series": id del grupo).
# Uso:  bash servicios/pipe_topics.sh <id_grupo>
GRUPO="$1"
if [ -z "$GRUPO" ]; then
    echo "Uso: bash servicios/pipe_topics.sh <id_grupo>"
    echo "  ej: bash servicios/pipe_topics.sh -100999888777"
    exit 1
fi
cd /home/jorge/dev/devjobs/downloader_telegram
docker compose run --rm uploader python /app/subir_videos.py --list-topics "$GRUPO"