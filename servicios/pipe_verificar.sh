#!/bin/bash
# Comprueba los secretos del uploader de Telegram sin subir nada:
#   1) config.bin + secret.key (que la clave descifre de verdad),
#   2) grupos.json válido,
#   3) uploader.session existe y está AUTORIZADA.
# Útil tras copiar los secretos a una máquina nueva.
# Uso:  bash servicios/pipe_verificar.sh
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/downloader_telegram"
docker compose run --rm uploader python -u /app/app/subir_videos.py --verificar
