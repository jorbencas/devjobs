#!/usr/bin/env python3
"""
convert.py — Convierte vídeos para Telegram (misma lógica que monitor_folder.sh).
Siempre re-codifica: libx264 CRF 28 fast + aac 128k, solo v+1er audio.
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


def get_video_duration(file_path):
    """Obtiene la duración del vídeo en segundos."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip()) if result.stdout.strip() else 0
    except Exception:
        return 0


def convert_video(video_path, output_dir):
    """Convierte un vídeo para Telegram igual que monitor_folder.sh."""
    video_file = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / video_file.name)
    tmp_path = output_path + ".tmp"

    logger.info(f"🔄 Convirtiendo: {video_file.name[:50]}...")

    duration = get_video_duration(video_file)

    # Comando exacto del monitor: libx264 CRF 28 fast + aac 128k + 720p
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_file),
        "-c:v", "libx264", "-crf", "28", "-preset", "fast",
        "-vf", "scale=-2:720",
        "-c:a", "aac", "-b:a", "128k",
        "-map", "0:v:0", "-map", "0:a:0",
        "-map_metadata", "0",
        "-movflags", "+faststart",
        "-f", "mp4",
        tmp_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0 or not Path(tmp_path).exists():
            logger.error(f"  ❌ Error convirtiendo: {result.stderr[-300:]}")
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()
            return None

        # Límite 50MB Telegram: si supera, 2 pasadas
        tmp_size = Path(tmp_path).stat().st_size
        max_bytes = 50 * 1024 * 1024
        if tmp_size > max_bytes and duration > 0:
            logger.info(f"  ⚠️  {tmp_size/(1024*1024):.0f}MB > 50MB, 2 pasadas...")
            audio_bps = 128000
            audio_bytes = int(duration * audio_bps / 8)
            video_bytes = max_bytes - audio_bytes
            video_bps = int(video_bytes * 8 / duration)
            if video_bps > 0:
                # Pasada 1
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(video_file),
                    "-vf", "scale=-2:720",
                    "-c:v", "libx264", "-b:v", str(video_bps),
                    "-preset", "fast", "-pass", "1", "-an", "-f", "null", "-"
                ], capture_output=True, timeout=1800)
                # Pasada 2
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(video_file),
                    "-vf", "scale=-2:720",
                    "-c:v", "libx264", "-b:v", str(video_bps),
                    "-preset", "fast", "-pass", "2",
                    "-c:a", "aac", "-b:a", "128k",
                    "-map", "0:v:0", "-map", "0:a:0",
                    "-map_metadata", "0",
                    "-movflags", "+faststart",
                    "-f", "mp4", tmp_path
                ], capture_output=True, timeout=1800)
                for f in Path(".").glob("ffmpeg2pass-*.log*"):
                    f.unlink(missing_ok=True)

        # Renombrar tmp → final
        Path(tmp_path).rename(output_path)
        input_size = video_file.stat().st_size / (1024 * 1024)
        output_size = Path(output_path).stat().st_size / (1024 * 1024)
        savings = int((input_size - output_size) * 100 / input_size) if input_size > 0 else 0

        logger.info(f"  ✅ Convertido: {output_size:.1f}MB ({savings:+d}%)")
        return output_path

    except subprocess.TimeoutExpired:
        logger.error(f"  ⏰ Timeout convirtiendo")
        if Path(tmp_path).exists():
            Path(tmp_path).unlink()
        return None


def main():
    """Función principal."""
    logger.info("🔄 Iniciando conversión de vídeos")

    CONVERTED_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    pending = []
    for channel_dir in DOWNLOADS_DIR.iterdir():
        if not channel_dir.is_dir():
            continue
        channel_name = channel_dir.name
        converted_channel_dir = CONVERTED_DIR / channel_name
        converted_channel_dir.mkdir(parents=True, exist_ok=True)
        for video_file in channel_dir.glob("*.mp4"):
            converted_file = converted_channel_dir / video_file.name
            if converted_file.exists():
                continue
            pending.append({
                "channel": channel_name,
                "input_path": str(video_file),
                "output_path": str(converted_file),
                "filename": video_file.name,
            })

    logger.info(f"📹 {len(pending)} vídeos pendientes de conversión")

    converted = []
    for video in pending:
        result = convert_video(video["input_path"], str(CONVERTED_DIR / video["channel"]))
        if result:
            converted.append(video)

    log_file = LOGS_DIR / f"conversions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w") as f:
        json.dump(converted, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ Conversión completada: {len(converted)} vídeos")
    return converted


if __name__ == "__main__":
    main()
