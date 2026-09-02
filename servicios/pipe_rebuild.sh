#!/bin/bash
# Rebuild + recrear los 3 servicios del pipeline CUANDO CAMBIA CÓDIGO.
# (Los .py se copian en la imagen: recorder.py, monitor, subir_videos.py...)
# Uso:  bash servicios/pipe_rebuild.sh
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== TwitchRecorder =="
cd "$ROOT/TwitchRecorder"
docker compose build && docker compose up -d --force-recreate twitchrecorder

echo "== ffmpeg-yt-dlp (monitor) =="
cd "$ROOT/ffmpeg-yt-dlp"
docker compose build && docker compose up -d --force-recreate monitor

echo "== downloader_telegram (uploader) =="
cd "$ROOT/downloader_telegram"
docker compose build && docker compose up -d --force-recreate uploader

echo "Pipeline reconstruido y recreado."
docker ps --filter name=twitchrecorder-sendo --filter name=ffmpeg_monitor-sendo --filter name=telegram-uploader-sendo --format "table {{.Names}}\t{{.Status}}"