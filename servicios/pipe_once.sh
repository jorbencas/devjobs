#!/bin/bash
# Una sola pasada del uploader (vigila /comprimidos una vez y sale).
# Útil para comprobar/subir el contenido ya presente sin dejar el bucle corriendo.
# Uso:  bash servicios/pipe_once.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/downloader_telegram"
docker compose run --rm uploader python /app/app/subir_videos.py --once /comprimidos