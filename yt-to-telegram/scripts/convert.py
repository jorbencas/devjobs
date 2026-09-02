#!/usr/bin/env python3
"""
convert.py — Convierte vídeos descargados a 720p para Telegram.
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
logger = logging.getLogger("convert")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data/yt-pipeline"))
DOWNLOADS_DIR = DATA_DIR / "downloads"
CONVERTED_DIR = DATA_DIR / "converted"
LOGS_DIR = DATA_DIR / "logs"

def get_pending_videos():
    """Obtiene vídeos descargados que aún no están convertidos."""
    pending = []
    
    for channel_dir in DOWNLOADS_DIR.iterdir():
        if not channel_dir.is_dir():
            continue
        
        channel_name = channel_dir.name
        converted_channel_dir = CONVERTED_DIR / channel_name
        converted_channel_dir.mkdir(parents=True, exist_ok=True)
        
        for video_file in channel_dir.glob("*.mp4"):
            # Verificar si ya está convertido
            converted_file = converted_channel_dir / video_file.name
            if converted_file.exists():
                continue
            
            pending.append({
                "channel": channel_name,
                "input_path": str(video_file),
                "output_path": str(converted_file),
                "filename": video_file.name
            })
    
    return pending

def convert_video(video):
    """Convierte un vídeo a 720p para Telegram."""
    logger.info(f"🔄 Convirtiendo: {video['filename'][:50]}...")
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video["input_path"],
        "-c:v", "libx264", "-crf", "28", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-vf", "scale='trunc(ow/2)*2:trunc(oh/2)*2'",
        "-map", "0:v:0", "-map", "0:a:0",
        "-map_metadata", "0",
        "-movflags", "+faststart",
        "-f", "mp4",
        video["output_path"]
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if result.returncode == 0 and Path(video["output_path"]).exists():
            # Obtener tamaño
            input_size = Path(video["input_path"]).stat().st_size / (1024 * 1024)
            output_size = Path(video["output_path"]).stat().st_size / (1024 * 1024)
            savings = int((input_size - output_size) * 100 / input_size) if input_size > 0 else 0
            
            logger.info(f"  ✅ Convertido: {output_size:.1f}MB (-{savings}%)")
            return True
        else:
            logger.error(f"  ❌ Error convirtiendo: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"  ⏰ Timeout convirtiendo")
        return False

def main():
    """Función principal."""
    logger.info("🔄 Iniciando conversión de vídeos")
    
    # Crear directorios
    CONVERTED_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Obtener vídeos pendientes
    pending = get_pending_videos()
    logger.info(f"📹 {len(pending)} vídeos pendientes de conversión")
    
    # Convertir vídeos
    converted = []
    for video in pending:
        if convert_video(video):
            converted.append(video)
    
    # Guardar log de conversiones
    log_file = LOGS_DIR / f"conversions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w") as f:
        json.dump(converted, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ Conversión completada: {len(converted)} vídeos")
    return converted

if __name__ == "__main__":
    main()
