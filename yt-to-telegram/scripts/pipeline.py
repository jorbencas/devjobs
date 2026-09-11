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
FAILED_IDS_FILE = DATA_DIR / "failed_ids.json"


def load_failed_ids():
    """Carga IDs de vídeos que fallaron (no reintentar)."""
    if FAILED_IDS_FILE.exists():
        with open(FAILED_IDS_FILE) as f:
            return set(json.load(f))
    return set()


def save_failed_ids(ids):
    """Guarda IDs de vídeos fallidos."""
    FAILED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FAILED_IDS_FILE, "w") as f:
        json.dump(list(ids), f)


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

    # Limpiar archivo descargado original + thumbnails
    downloaded_file.unlink(missing_ok=True)
    for ext in ['.jpg', '.webp', '.png']:
        downloaded_file.with_suffix(ext).unlink(missing_ok=True)

    # 3. Subir a Telegram
    logger.info(f"  ⬆️  Subiendo a Telegram...")
    uploaded_ok = upload_video(
        video_path=converted_file,
        channel_name=channel_name,
        title=title,
        publish_date=upload_date,
        video_type=video_type
    )

    # 4. Borrar archivos locales SOLO si la subida fue exitosa
    if uploaded_ok:
        # Borrar convertido
        Path(converted_file).unlink(missing_ok=True)
        # Borrar thumbnail
        thumb_src = Path(converted_file).with_suffix('.jpg')
        if thumb_src.exists():
            thumb_src.unlink()
        logger.info(f"  🗑️  Borrado de local: {Path(converted_file).name}")
    else:
        # Limpiar thumbnail si la subida falló
        thumb_src = Path(converted_file).with_suffix('.jpg')
        if thumb_src.exists():
            thumb_src.unlink()
        logger.warning(f"  ⚠️  No se borró (subida fallida). "
                       f"El archivo queda en converted/ para reintentar.")

    return True


def upload_pending_converted():
    """Sube vídeos convertidos pendientes a Telegram."""
    from upload import get_pending_videos, upload_video, move_to_uploaded, load_topics, get_topic_id
    
    pending = get_pending_videos()
    if not pending:
        logger.info("ℹ️  No hay vídeos convertidos pendientes de subir")
        return 0
    
    logger.info(f"📤 {len(pending)} vídeos pendientes de subir a Telegram")
    
    topics = load_topics()
    uploaded_count = 0
    
    for video in pending:
        topic_id = get_topic_id(video["channel"], topics)
        if not topic_id:
            logger.warning(f"  ⚠️  No hay tema para {video['channel']}, saltando")
            continue
        
        logger.info(f"  📹 Subiendo: {video['filename'][:50]}...")
        if upload_video(video["path"], video["channel"], video["title"], video.get("publish_date", "")):
            move_to_uploaded(video)
            uploaded_count += 1
            logger.info(f"  ✅ Subido: {video['filename'][:50]}")
        else:
            logger.error(f"  ❌ Error subiendo: {video['filename'][:50]}")
    
    return uploaded_count


def run_pipeline():
    """Ejecuta el pipeline: primero sube pendientes, luego descarga nuevos."""
    logger.info("🚀 Iniciando pipeline YouTube → Telegram")

    # Crear directorios
    for d in [DOWNLOADS_DIR, CONVERTED_DIR, UPLOADED_DIR, LOGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    stats = {"downloaded": 0, "converted": 0, "uploaded": 0, "errors": 0}

    # FASE 1: Subir vídeos convertidos pendientes
    logger.info("\n" + "="*50)
    logger.info("📤 FASE 1: Subiendo vídeos pendientes")
    logger.info("="*50)
    uploaded = upload_pending_converted()
    stats["uploaded"] = uploaded

    # FASE 2: Descargar y procesar nuevos vídeos
    logger.info("\n" + "="*50)
    logger.info("📥 FASE 2: Descargando vídeos nuevos")
    logger.info("="*50)

    channels = load_channels()
    enabled_channels = [c for c in channels if c.get("enabled", True)]
    logger.info(f"📺 {len(enabled_channels)} canales habilitados")

    downloaded_ids = load_downloaded_ids()
    failed_ids = load_failed_ids()

    for channel in enabled_channels:
        name = channel["name"]
        logger.info(f"\n{'='*50}")
        logger.info(f"📥 Procesando canal: {name}")
        logger.info(f"{'='*50}")

        videos = get_channel_videos(channel, downloaded_ids, max_videos=999)
        if not videos:
            logger.info(f"  ℹ️  No hay vídeos nuevos")
            continue

        for video in videos:
            # Filtrar directos programados
            if video.get("is_live") and video.get("live_status") == "is_upcoming":
                logger.info(f"  ⏭️  Saltando directo programado: {video['title'][:50]}")
                continue

            # Saltar vídeos que ya fallaron
            if video["id"] in failed_ids:
                logger.info(f"  ⏭️  Saltando vídeo previamente fallido: {video['title'][:50]}")
                continue

            success = process_single_video(video, name)
            if success:
                downloaded_ids.add(video["id"])
                save_downloaded_ids(downloaded_ids)
                stats["uploaded"] += 1
            else:
                failed_ids.add(video["id"])
                save_failed_ids(failed_ids)
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
