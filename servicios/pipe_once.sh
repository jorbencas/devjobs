#!/bin/bash
# Una sola pasada del uploader (vigila /comprimidos una vez y sale).
# Útil para comprobar/subir el contenido ya presente sin dejar el bucle corriendo.
# Uso:  bash servicios/pipe_once.sh
cd /home/jorge/dev/devjobs/downloader_telegram
docker compose run --rm uploader python /app/subir_videos.py --once /comprimidos