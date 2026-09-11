#!/usr/bin/env python3
"""
convert.py — Convierte vídeos para Telegram (misma lógica que monitor_folder.sh).
Siempre re-codifica: libx264 CRF 28 fast + aac 128k, solo v+1er audio.
Si el resultado supera 50MB, re-codifica en 2 pasadas para estar bajo el límite.
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

# Límite de Telegram (50MB)
MAX_SIZE_MB = 50
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024


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


def has_audio_stream(file_path):
    """Verifica si el vídeo tiene pistas de audio."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return bool(result.stdout.strip())
    except Exception:
        return False


def calc_target_bitrate(duration_seconds, max_bytes=MAX_SIZE_BYTES):
    """Calcula bitrate objetivo para caber bajo max_bytes."""
    audio_bps = 128000
    audio_bytes = int(duration_seconds * audio_bps / 8)
    target_bytes = int(max_bytes * 0.90)  # 90% para margen
    video_bytes = target_bytes - audio_bytes
    if video_bytes <= 0 or duration_seconds <= 0:
        return 0
    bps = int(video_bytes * 8 / duration_seconds)
    # Mínimo 100kbps para que ffmpeg no sequee
    return max(bps, 100000)


def two_pass_convert(video_file, output_path, video_bps, map_args, duration):
    """Ejecuta conversión 2-pass con bitrate fijo."""
    tmp_path = output_path + ".tmp"
    video_file_str = str(video_file)
    # Usar directorio temporal para logs de ffmpeg
    work_dir = Path(tmp_path).parent
    passlog = str(work_dir / "ffmpeg2pass")

    logger.info(f"  📐 2-pass: bitrate={video_bps//1000}kbps")

    # Limpiar logs previos
    for f in work_dir.glob("ffmpeg2pass-*.log*"):
        f.unlink(missing_ok=True)

    # Pasada 1
    pass1 = subprocess.run([
        "ffmpeg", "-y",
        "-fflags", "+genpts",
        "-i", video_file_str,
        "-vf", "scale=-2:720",
        "-c:v", "libx264", "-b:v", str(video_bps),
        "-preset", "fast", "-pass", "1",
        "-passlogfile", passlog,
        "-an", "-f", "null", "-"
    ], capture_output=True, text=True, timeout=7200)

    if pass1.returncode != 0:
        logger.warning(f"  ⚠️  Pasada 1 falló con scale, intentando sin...")
        subprocess.run([
            "ffmpeg", "-y",
            "-fflags", "+genpts",
            "-i", video_file_str,
            "-c:v", "libx264", "-b:v", str(video_bps),
            "-preset", "fast", "-pass", "1",
            "-passlogfile", passlog,
            "-an", "-f", "null", "-"
        ], capture_output=True, text=True, timeout=7200)

    # Pasada 2
    cmd_pass2 = [
        "ffmpeg", "-y",
        "-fflags", "+genpts",
        "-i", video_file_str,
        "-vf", "scale=-2:720",
        "-c:v", "libx264", "-b:v", str(video_bps),
        "-preset", "fast", "-pass", "2",
        "-passlogfile", passlog,
        "-c:a", "aac", "-b:a", "128k",
    ] + map_args + [
        "-map_metadata", "0",
        "-movflags", "+faststart+dash",
        "-f", "mp4", tmp_path
    ]

    if duration > 0:
        cmd_pass2.insert(-1, "-metadata")
        cmd_pass2.insert(-1, f"duration={duration:.6f}")

    result = subprocess.run(cmd_pass2, capture_output=True, text=True, timeout=7200)

    # Limpiar logs de ffmpeg
    for f in work_dir.glob("ffmpeg2pass-*.log*"):
        f.unlink(missing_ok=True)

    if result.returncode != 0 or not Path(tmp_path).exists():
        logger.error(f"  ❌ Pasada 2 falló: {result.stderr[-200:]}")
        return None

    return tmp_path


def convert_video(video_path, output_dir):
    """Convierte un vídeo para Telegram. Garantiza resultado <50MB."""
    video_file = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / video_file.name)
    tmp_path = output_path + ".tmp"

    logger.info(f"🔄 Convirtiendo: {video_file.name[:50]}...")

    duration = get_video_duration(video_file)
    has_audio = has_audio_stream(video_file)
    input_size = video_file.stat().st_size / (1024 * 1024)

    # Si el original ya es <50MB y dura <5min, remux rápido con re-encode
    # (siempre H.264+AAC para compatibilidad Telegram)
    if input_size <= MAX_SIZE_MB and duration <= 300:
        logger.info(f"  📦 Original {input_size:.0f}MB < {MAX_SIZE_MB}MB, remux rápido...")
        map_args = ["-map", "0:v:0"]
        if has_audio:
            map_args.extend(["-map", "0:a:0"])
        cmd = [
            "ffmpeg", "-y", "-i", str(video_file),
            "-c:v", "libx264", "-crf", "28", "-preset", "fast",
            "-vf", "scale=-2:720",
            "-c:a", "aac", "-b:a", "128k",
        ] + map_args + [
            "-map_metadata", "0",
            "-movflags", "+faststart",
            "-f", "mp4", tmp_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if result.returncode == 0 and Path(tmp_path).exists():
            Path(tmp_path).rename(output_path)
            output_size = Path(output_path).stat().st_size / (1024 * 1024)
            savings = int((input_size - output_size) * 100 / input_size) if input_size > 0 else 0
            logger.info(f"  ✅ Remux: {output_size:.1f}MB ({savings:+d}%)")
            _extract_thumbnail(output_path, duration)
            return output_path
        # Si falla el remux, continuar con re-encode
        if Path(tmp_path).exists():
            Path(tmp_path).unlink()

    # Calcular bitrate objetivo si tenemos duración
    target_bps = calc_target_bitrate(duration) if duration > 0 else 0

    map_args = ["-map", "0:v:0"]
    if has_audio:
        map_args.extend(["-map", "0:a:0"])

    try:
        # Si el vídeo es largo (>5min) y tenemos duración, ir directo a 2-pass
        if duration > 300 and target_bps > 0:
            logger.info(f"  ⏱️  Vídeo {duration/60:.0f}min, usando 2-pass directo...")
            tmp_path = two_pass_convert(video_file, output_path, target_bps, map_args, duration)
            if tmp_path and Path(tmp_path).exists():
                tmp_size = Path(tmp_path).stat().st_size
                if tmp_size <= MAX_SIZE_BYTES:
                    Path(tmp_path).rename(output_path)
                    output_size = tmp_size / (1024 * 1024)
                    savings = int((input_size - output_size) * 100 / input_size) if input_size > 0 else 0
                    logger.info(f"  ✅ Convertido: {output_size:.1f}MB ({savings:+d}%)")
                    _extract_thumbnail(output_path, duration)
                    return output_path
                else:
                    logger.warning(f"  ⚠️  2-pass dio {tmp_size/(1024*1024):.0f}MB, reintentando con bitrate menor...")
                    # Reintentar con 70% del bitrate
                    lower_bps = int(target_bps * 0.7)
                    if Path(tmp_path).exists():
                        Path(tmp_path).unlink()
                    tmp_path = two_pass_convert(video_file, output_path, lower_bps, map_args, duration)
                    if tmp_path and Path(tmp_path).exists():
                        tmp_size = Path(tmp_path).stat().st_size
                        if tmp_size <= MAX_SIZE_BYTES:
                            Path(tmp_path).rename(output_path)
                            output_size = tmp_size / (1024 * 1024)
                            savings = int((input_size - output_size) * 100 / input_size) if input_size > 0 else 0
                            logger.info(f"  ✅ Convertido: {output_size:.1f}MB ({savings:+d}%)")
                            _extract_thumbnail(output_path, duration)
                            return output_path

        # Fallback: CRF 28 (para vídeos cortos o si 2-pass falló)
        logger.info(f"  🎬 Usando CRF 28...")
        cmd = [
            "ffmpeg", "-y",
            "-fflags", "+genpts",
            "-i", str(video_file),
            "-c:v", "libx264", "-crf", "28", "-preset", "fast",
            "-vf", "scale=-2:720",
            "-c:a", "aac", "-b:a", "128k",
        ] + map_args + [
            "-map_metadata", "0",
            "-movflags", "+faststart",
            "-f", "mp4", tmp_path
        ]

        if duration > 0:
            cmd.insert(-1, "-metadata")
            cmd.insert(-1, f"duration={duration:.6f}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if result.returncode != 0 or not Path(tmp_path).exists():
            logger.error(f"  ❌ Error convirtiendo: {result.stderr[-300:]}")
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()
            return None

        # Verificar tamaño — si >50MB, forzar 2-pass
        tmp_size = Path(tmp_path).stat().st_size
        if tmp_size > MAX_SIZE_BYTES:
            if duration > 0 and target_bps > 0:
                logger.info(f"  ⚠️  CRF dio {tmp_size/(1024*1024):.0f}MB, forzando 2-pass...")
                Path(tmp_path).unlink(missing_ok=True)
                tmp_path = two_pass_convert(video_file, output_path, target_bps, map_args, duration)
                if not tmp_path or not Path(tmp_path).exists():
                    return None
                tmp_size = Path(tmp_path).stat().st_size
                # Si aún >50MB, intentar con 60% bitrate
                if tmp_size > MAX_SIZE_BYTES:
                    logger.warning(f"  ⚠️  2-pass dio {tmp_size/(1024*1024):.0f}MB, bitrate mínimo...")
                    Path(tmp_path).unlink(missing_ok=True)
                    lower_bps = int(target_bps * 0.6)
                    tmp_path = two_pass_convert(video_file, output_path, lower_bps, map_args, duration)
                    if not tmp_path or not Path(tmp_path).exists():
                        return None
                    tmp_size = Path(tmp_path).stat().st_size
            else:
                logger.error(f"  ❌ {tmp_size/(1024*1024):.0f}MB > {MAX_SIZE_MB}MB pero sin duración para 2-pass")
                Path(tmp_path).unlink(missing_ok=True)
                return None

        # Renombrar tmp → final
        Path(tmp_path).rename(output_path)
        output_size = Path(output_path).stat().st_size / (1024 * 1024)
        savings = int((input_size - output_size) * 100 / input_size) if input_size > 0 else 0
        logger.info(f"  ✅ Convertido: {output_size:.1f}MB ({savings:+d}%)")

        _extract_thumbnail(output_path, duration)
        return output_path

    except subprocess.TimeoutExpired:
        logger.error(f"  ⏰ Timeout convirtiendo")
        Path(tmp_path).unlink(missing_ok=True)
        return None


def _extract_thumbnail(output_path, duration):
    """Extrae thumbnail del vídeo convertido."""
    thumb_path = Path(output_path).with_suffix('.jpg')
    try:
        thumb_time = min(5, duration * 0.1) if duration > 0 else 5
        thumb_cmd = [
            "ffmpeg", "-y",
            "-i", str(output_path),
            "-ss", f"{thumb_time:.1f}",
            "-vframes", "1",
            "-vf", "scale=320:-1",
            "-q:v", "4",
            "-update", "1",
            str(thumb_path)
        ]
        result = subprocess.run(thumb_cmd, capture_output=True, text=True, timeout=30)
        if thumb_path.exists() and thumb_path.stat().st_size > 0:
            logger.info(f"  🖼️  Thumbnail: {thumb_path.name}")
        else:
            logger.warning(f"  ⚠️  Thumbnail no creada. ffmpeg stderr: {result.stderr[-200:]}")
    except Exception as e:
        logger.warning(f"  ⚠️  Thumbnail falló: {e}")


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
