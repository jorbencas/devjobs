#!/bin/bash
# Rebuild + recrear los 3 servicios del pipeline CUANDO CAMBIA CÓDIGO.
# (Los .py se copian en la imagen: recorder.py, monitor, subir_videos.py...)
# Uso:  bash servicios/pipe_rebuild.sh
set -e

echo "== TwitchRecorder =="
cd /home/jorge/dev/devjobs/TwitchRecorder
docker compose build && docker compose up -d --force-recreate twitchrecorder

echo "== ffmpeg-yt-dlp (monitor) =="
cd /home/jorge/dev/devjobs/ffmpeg-yt-dlp
docker compose build && docker compose up -d --force-recreate monitor

echo "== downloader_telegram (uploader) =="
cd /home/jorge/dev/devjobs/downloader_telegram
docker compose build && docker compose up -d --force-recreate uploader

echo "Pipeline reconstruido y recreado."
docker ps --filter name=twitchrecorder --filter name=ffmpeg_monitor --filter name=telegram-uploader --format "table {{.Names}}\t{{.Status}}"