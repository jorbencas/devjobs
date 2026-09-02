#!/usr/bin/env python3
"""
download.py — Descarga vídeos de canales de YouTube.
Limita a N vídeos por canal (default: 2).
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

def load_channels():
    """Carga la configuración de canales."""
    channels_file = CONFIG_DIR / "channels.json"
    with open(channels_file) as f:
        return json.load(f)

def get_downloaded_videos(channel_name):
    """Obtiene lista de vídeos ya descargados de un canal."""
    channel_dir = DOWNLOADS_DIR / channel_name
    if not channel_dir.exists():
        return set()
    return {f.stem for f in channel_dir.glob("*.mp4")}

def download_channel_videos(channel, max_videos=2):
    """Descarga hasta max_videos de un canal."""
    name = channel["name"]
    url = channel["url"]
    
    logger.info(f"📥 Procesando canal: {name}")
    
    # Crear directorio del canal
    channel_dir = DOWNLOADS_DIR / name
    channel_dir.mkdir(parents=True, exist_ok=True)
    
    # Verificar vídeos ya descargados
    downloaded = get_downloaded_videos(name)
    if len(downloaded) >= max_videos:
        logger.info(f"  ⏭️  Ya tiene {len(downloaded)} vídeos, saltando")
        return []
    
    # Listar vídeos disponibles
    remaining = max_videos - len(downloaded)
    logger.info(f"  📋 Buscando vídeos (quedan {remaining} plazas)")
    
    # Usar yt-dlp para listar y descargar
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s|||%(title)s|||%(duration)s",
        "--playlist-end", str(remaining * 2),  # Más por si hay errores
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
            
            # Saltar si ya está descargado
            if video_id in downloaded:
                continue
            
            videos.append({"id": video_id, "title": title})
            
            if len(videos) >= remaining:
                break
        
        if not videos:
            logger.info(f"  ℹ️  No hay vídeos nuevos para descargar")
            return []
        
        # Descargar vídeos
        downloaded_videos = []
        for video in videos:
            logger.info(f"  ⬇️  Descargando: {video['title'][:50]}...")
            
            output_template = str(channel_dir / f"{video['id']}_{video['title'][:50].replace('/', '_').replace(':', '_')}.mp4")
            
            cmd = [
                "yt-dlp",
                "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
                "--merge-output-format", "mp4",
                "-o", output_template,
                f"https://www.youtube.com/watch?v={video['id']}"
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                if result.returncode == 0:
                    # Buscar el archivo descargado
                    for f in channel_dir.glob(f"{video['id']}*"):
                        if f.suffix == ".mp4":
                            downloaded_videos.append({
                                "id": video["id"],
                                "title": video["title"],
                                "channel": name,
                                "path": str(f),
                                "downloaded_at": datetime.now().isoformat()
                            })
                            logger.info(f"  ✅ Descargado: {video['title'][:50]}")
                            break
                else:
                    logger.error(f"  ❌ Error descargando: {result.stderr[:100]}")
            except subprocess.TimeoutExpired:
                logger.error(f"  ⏰ Timeout descargando: {video['title'][:50]}")
        
        return downloaded_videos
        
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
