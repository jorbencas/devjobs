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
    return {f.stem.split("_")[0] for f in channel_dir.glob("*.mp4")}

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
    
    # Listar vídeos disponibles (incluye normales, shorts y directos)
    remaining = max_videos - len(downloaded)
    logger.info(f"  📋 Buscando vídeos (quedan {remaining} plazas)")
    
    # Usar yt-dlp para listar y descargar
    # Incluye: vídeos normales, shorts, y directos finalizados
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s|||%(title)s|||%(duration)s|||%(upload_date)s|||%(live_status)s",
        "--playlist-end", str(remaining * 3),  # Más por si hay errores o shorts
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
            upload_date = parts[3] if len(parts) > 3 else ""
            live_status = parts[4] if len(parts) > 4 else ""
            
            # Saltar si ya está descargado
            if video_id in downloaded:
                continue
            
            # Formatear fecha
            if upload_date and len(upload_date) == 8:
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
            
            if len(videos) >= remaining * 2:  # Más para filtrar después
                break
        
        if not videos:
            logger.info(f"  ℹ️  No hay vídeos nuevos para descargar")
            return []
        
        # Descargar vídeos
        downloaded_videos = []
        for video in videos:
            # Filtrar: no descargar directos en cours
            if video["is_live"] and video["live_status"] == "is_upcoming":
                logger.info(f"  ⏭️  Saltando directo programado: {video['title'][:50]}")
                continue
            
            logger.info(f"  ⬇️  Descargando: {video['title'][:50]}...")
            
            # Formato de salida con fecha y tipo
            video_type = "short" if video["is_short"] else "live" if video["is_live"] else "video"
            output_template = str(channel_dir / f"{video['id']}_{video['upload_date']}_{video_type}_{video['title'][:50].replace('/', '_').replace(':', '_')}.mp4")
            
            # Comando de descarga
            if video["is_short"]:
                # Shorts: descargar directamente
                cmd = [
                    "yt-dlp",
                    "-f", "best[height<=720][ext=mp4]/best",
                    "--merge-output-format", "mp4",
                    "-o", output_template,
                    f"https://www.youtube.com/shorts/{video['id']}"
                ]
            elif video["is_live"]:
                # Directos: descargar si están disponibles
                cmd = [
                    "yt-dlp",
                    "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
                    "--merge-output-format", "mp4",
                    "-o", output_template,
                    f"https://www.youtube.com/watch?v={video['id']}"
                ]
            else:
                # Vídeos normales
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
                                "filename": f.name,
                                "publish_date": video["upload_date"],
                                "video_type": video_type,
                                "downloaded_at": datetime.now().isoformat()
                            })
                            logger.info(f"  ✅ Descargado: {video['title'][:50]}")
                            break
                else:
                    logger.error(f"  ❌ Error descargando: {result.stderr[:100]}")
            except subprocess.TimeoutExpired:
                logger.error(f"  ⏰ Timeout descargando: {video['title'][:50]}")
            
            # Limitar a max_videos
            if len(downloaded_videos) >= remaining:
                break
        
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
