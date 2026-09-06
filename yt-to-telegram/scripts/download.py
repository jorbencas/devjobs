#!/usr/bin/env python3
"""
download.py — Descarga vídeos de canales de YouTube.
Limita a N vídeos por canal (default: 2).
Incluye vídeos normales, shorts y directos.
"""
import json
import os
import subprocess
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("download")

CONFIG_DIR = Path(__file__).parent.parent / "config"
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data/yt-pipeline"))
DOWNLOADS_DIR = DATA_DIR / "downloads"
LOGS_DIR = DATA_DIR / "logs"
DOWNLOADED_IDS_FILE = DATA_DIR / "downloaded_ids.json"

def load_channels():
    """Carga la configuración de canales."""
    channels_file = CONFIG_DIR / "channels.json"
    with open(channels_file) as f:
        return json.load(f)

def load_downloaded_ids():
    """Carga IDs de vídeos ya procesados."""
    if DOWNLOADED_IDS_FILE.exists():
        with open(DOWNLOADED_IDS_FILE) as f:
            return set(json.load(f))
    return set()

def save_downloaded_ids(ids):
    """Guarda IDs de vídeos procesados."""
    DOWNLOADED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DOWNLOADED_IDS_FILE, "w") as f:
        json.dump(list(ids), f)

def get_channel_videos(channel, downloaded_ids, max_videos=2):
    """Obtiene lista de vídeos disponibles de un canal, ordenados del más antiguo al más nuevo."""
    name = channel["name"]
    url = channel["url"]
    
    logger.info(f"  📋 Buscando vídeos de {name}...")
    
    # Obtener más vídeos de los necesarios para poder ordenar por fecha
    fetch_count = max(max_videos * 5, 20)
    
    cmd = [
        "yt-dlp",
        "--remote-components", "ejs:github",
        "--flat-playlist",
        "--print", "%(id)s|||%(title)s|||%(duration)s|||%(live_status)s|||%(upload_date)s",
        "--playlist-end", str(fetch_count),
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.error(f"  ❌ Error listando vídeos: {result.stderr[:200]}")
            return []
        
        videos = []
        for line in result.stdout.strip().split("\n"):
            if "|||" not in line:
                continue
            parts = line.split("|||")
            if len(parts) < 2:
                continue
            
            video_id = parts[0]
            title = parts[1]
            duration = parts[2] if len(parts) > 2 else "0"
            live_status = parts[3] if len(parts) > 3 else ""
            upload_date = parts[4] if len(parts) > 4 else ""
            
            if video_id in downloaded_ids:
                continue
            
            # Formatear fecha: YYYYMMDD → YYYY-MM-DD
            if upload_date and len(upload_date) == 8 and upload_date.isdigit():
                upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
            
            videos.append({
                "id": video_id,
                "title": title,
                "duration": duration,
                "upload_date": upload_date,
                "live_status": live_status,
                "is_short": int(duration) <= 60 if duration.isdigit() else False,
                "is_live": live_status in ["is_live", "is_upcoming"]
            })
        
        # Ordenar por fecha de publicación (más antiguo primero)
        def sort_key(v):
            d = v.get("upload_date", "")
            return d if d else "9999-99-99"
        
        videos.sort(key=sort_key)
        
        return videos[:max_videos]
        
    except subprocess.TimeoutExpired:
        logger.error(f"  ⏰ Timeout listando vídeos del canal")
        return []

def main():
    """Función principal."""
    logger.info("🚀 Iniciando descarga de vídeos de YouTube")
    
    # Crear directorios
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Cargar canales
    channels = load_channels()
    enabled_channels = [c for c in channels if c.get("enabled", True)]
    logger.info(f"📺 {len(enabled_channels)} canales habilitados")
    
    # Descargar vídeos
    all_downloaded = []
    for channel in enabled_channels:
        videos = download_channel_videos(channel, max_videos=channel.get("max_videos", 2))
        all_downloaded.extend(videos)
    
    # Guardar log de descargas
    log_file = LOGS_DIR / f"downloads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w") as f:
        json.dump(all_downloaded, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ Descarga completada: {len(all_downloaded)} vídeos")
    return all_downloaded

if __name__ == "__main__":
    main()
