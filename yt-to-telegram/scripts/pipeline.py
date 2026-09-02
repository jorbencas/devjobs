#!/usr/bin/env python3
"""
pipeline.py — Orquestador principal del pipeline YouTube → Telegram.
Procesa cada vídeo individualmente: download → convert → upload → delete.
"""
import json
import os
import sys
import logging
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from download import load_channels, load_downloaded_ids, save_downloaded_ids, get_channel_videos
from convert import convert_video
from upload import upload_video

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("pipeline")

CONFIG_DIR = Path(__file__).parent.parent / "config"
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data/yt-pipeline"))
DOWNLOADS_DIR = DATA_DIR / "downloads"
CONVERTED_DIR = DATA_DIR / "converted"
UPLOADED_DIR = DATA_DIR / "uploaded"
LOGS_DIR = DATA_DIR / "logs"


def process_single_video(video_info, channel_name):
    """Descarga, convierte, sube y borra un vídeo individual."""
    video_id = video_info["id"]
    title = video_info["title"]

    # 1. Descargar
    logger.info(f"  📥 Descargando: {title[:60]}...")
    channel_dir = DOWNLOADS_DIR / channel_name.replace("/", "_")
    channel_dir.mkdir(parents=True, exist_ok=True)

    # Obtener upload_date antes de descargar
    upload_date = video_info.get("upload_date", "")
    if not upload_date:
        info_cmd = [
            "yt-dlp", "--remote-components", "ejs:github",
            "--skip-download", "--print", "%(upload_date)s",
            f"https://www.youtube.com/watch?v={video_id}"
        ]
        try:
            info = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
            d = info.stdout.strip()
            if d and len(d) == 8 and d != "NA":
                upload_date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        except Exception:
            pass

    # Formato de salida
    video_type = "short" if video_info.get("is_short") else "live" if video_info.get("is_live") else "video"
    safe_title = title[:50].replace("/", "_").replace(":", "_")
    output_template = str(channel_dir / f"{video_id}_{upload_date}_{video_type}_{safe_title}.mp4")

    # Comando yt-dlp — preferir mp4/h264 para que ffmpeg solo copie
    url = f"https://www.youtube.com/shorts/{video_id}" if video_info.get("is_short") else f"https://www.youtube.com/watch?v={video_id}"
    cmd = [
        "yt-dlp",
        "--remote-components", "ejs:github",
        "-f", "bestvideo[height<=720][ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_template,
        url
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.error(f"  ❌ Error descargando: {result.stderr[:100]}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"  ⏰ Timeout descargando: {title[:50]}")
        return False

    # Buscar archivo descargado
    downloaded_file = None
    for f in channel_dir.glob(f"{video_id}*"):
        if f.suffix == ".mp4":
            downloaded_file = f
            break

    if not downloaded_file:
        logger.error(f"  ❌ Archivo no encontrado tras descarga")
        return False

    logger.info(f"  ✅ Descargado: {downloaded_file.name}")

    # 2. Convertir
    logger.info(f"  🔄 Convirtiendo...")
    converted_file = convert_video(str(downloaded_file), str(CONVERTED_DIR / channel_name.replace("/", "_")))
    if not converted_file:
        logger.error(f"  ❌ Error en conversión")
        # Limpiar archivo descargado
        downloaded_file.unlink(missing_ok=True)
        return False

    logger.info(f"  ✅ Convertido: {Path(converted_file).name}")

    # Limpiar archivo descargado original
    downloaded_file.unlink(missing_ok=True)

    # 3. Subir a Telegram
    logger.info(f"  ⬆️  Subiendo a Telegram...")
    upload_video(
        video_path=converted_file,
        channel_name=channel_name,
        title=title,
        publish_date=upload_date,
        video_type=video_type
    )

    # 4. Mover a uploaded/
    uploaded_channel = UPLOADED_DIR / channel_name.replace("/", "_")
    uploaded_channel.mkdir(parents=True, exist_ok=True)
    dest = uploaded_channel / Path(converted_file).name
    shutil.move(converted_file, dest)
    logger.info(f"  📁 Movido a uploaded: {dest.name}")

    return True


def run_pipeline():
    """Ejecuta el pipeline procesando vídeos uno por uno."""
    logger.info("🚀 Iniciando pipeline YouTube → Telegram (modo individual)")

    # Crear directorios
    for d in [DOWNLOADS_DIR, CONVERTED_DIR, UPLOADED_DIR, LOGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # Cargar canales
    channels = load_channels()
    enabled_channels = [c for c in channels if c.get("enabled", True)]
    logger.info(f"📺 {len(enabled_channels)} canales habilitados")

    downloaded_ids = load_downloaded_ids()
    stats = {"downloaded": 0, "converted": 0, "uploaded": 0, "errors": 0}

    for channel in enabled_channels:
        name = channel["name"]
        logger.info(f"\n{'='*50}")
        logger.info(f"📥 Procesando canal: {name}")
        logger.info(f"{'='*50}")

        videos = get_channel_videos(channel, downloaded_ids, max_videos=channel.get("max_videos", 2))
        if not videos:
            logger.info(f"  ℹ️  No hay vídeos nuevos")
            continue

        for video in videos:
            # Filtrar directos programados
            if video.get("is_live") and video.get("live_status") == "is_upcoming":
                logger.info(f"  ⏭️  Saltando directo programado: {video['title'][:50]}")
                continue

            success = process_single_video(video, name)
            if success:
                downloaded_ids.add(video["id"])
                save_downloaded_ids(downloaded_ids)
                stats["uploaded"] += 1
            else:
                stats["errors"] += 1

    # Guardar log final
    log_file = LOGS_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w") as f:
        json.dump(stats, f, indent=2)

    logger.info(f"\n{'='*50}")
    logger.info(f"✅ Pipeline completado")
    logger.info(f"   Subidos: {stats['uploaded']}")
    logger.info(f"   Errores: {stats['errors']}")
    logger.info(f"{'='*50}")


if __name__ == "__main__":
    run_pipeline()
