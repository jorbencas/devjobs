#!/usr/bin/env python3
"""
Descargador de vídeos de Kick.com
Usa la API de canales para obtener el recording_url (m3u8) y ffmpeg para descargar.

Uso:
  python kick_download.py <url> [output.mp4]

Ejemplos:
  python kick_download.py https://kick.com/sendosama/videos/01a087f2-...
  python kick_download.py https://kick.com/sendosama/videos/01a087f2-... /descargas/video.mp4

Requisitos:
  - ffmpeg (en PATH o en contenedor docker ffmpeg_monitor-sendo)
  - requests (pip install requests)
"""
import sys
import os
import re
import json
import subprocess
import requests


def extract_channel_and_video_id(url: str) -> tuple[str, str]:
    """Extrae channel_slug y video_id de una URL de Kick."""
    # Formato: https://kick.com/<channel>/videos/<uuid>
    match = re.match(r"https?://(?:www\.)?kick\.com/([\w-]+)/videos/([\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12})", url)
    if match:
        return match.group(1), match.group(2)
    raise ValueError(f"URL no válida de Kick: {url}")


def get_channel_id(slug: str) -> int:
    """Obtiene el channel_id numérico desde el slug."""
    resp = requests.get(f"https://kick.com/api/v2/channels/{slug}", timeout=10)
    resp.raise_for_status()
    return resp.json()["id"]


def get_recording_url(channel_id: int, video_id: str) -> str:
    """Obtiene el recording_url (m3u8) desde la API de canales."""
    resp = requests.get(f"https://web.kick.com/api/v1/channels/{channel_id}/videos", timeout=10)
    resp.raise_for_status()
    videos = resp.json().get("data", [])
    for v in videos:
        if v.get("id") == video_id:
            recording_url = v.get("recording_url")
            if recording_url:
                return recording_url
            raise ValueError(f"Vídeo encontrado pero sin recording_url: {video_id}")
    raise ValueError(f"Vídeo {video_id} no encontrado en el canal {channel_id}")


def download_with_ffmpeg(m3u8_url: str, output: str, use_docker: bool = False) -> bool:
    """Descarga el m3u8 usando ffmpeg."""
    if use_docker:
        container_output = f"/comprimidos/{os.path.basename(output)}"
        cmd = [
            "docker", "exec", "ffmpeg_monitor-sendo",
            "ffmpeg", "-y", "-i", m3u8_url,
            "-c", "copy", "-bsf:a", "aac_adtstoasc",
            container_output
        ]
    else:
        cmd = ["ffmpeg", "-y", "-i", m3u8_url, "-c", "copy", "-bsf:a", "aac_adtstoasc", output]

    print(f"Descargando con ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

    if use_docker and result.returncode == 0:
        subprocess.run(["docker", "cp", f"ffmpeg_monitor-sendo:{container_output}", output], check=True)
        subprocess.run(["docker", "exec", "ffmpeg_monitor-sendo", "rm", "-f", container_output], check=True)

    return result.returncode == 0


def check_ffmpeg_available() -> bool:
    """Comprueba si ffmpeg está disponible en el PATH."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def check_docker_ffmpeg() -> bool:
    """Comprueba si ffmpeg está disponible en el contenedor docker."""
    try:
        result = subprocess.run(
            ["docker", "exec", "ffmpeg_monitor-sendo", "ffmpeg", "-version"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except:
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    url = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else None

    # Extraer IDs de la URL
    channel_slug, video_id = extract_channel_and_video_id(url)
    print(f"Canal: {channel_slug}")
    print(f"Video: {video_id}")

    # Obtener channel_id
    print("Obteniendo channel_id...")
    channel_id = get_channel_id(channel_slug)
    print(f"Channel ID: {channel_id}")

    # Obtener recording_url
    print("Obteniendo recording_url...")
    m3u8_url = get_recording_url(channel_id, video_id)
    print(f"Stream: {m3u8_url[:80]}...")

    # Determinar output
    if not output:
        output = f"/home/jorge/dev/devjobs/descargas/{channel_slug}_{video_id[:8]}.mp4"
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    # Seleccionar ffmpeg
    if check_ffmpeg_available():
        use_docker = False
    elif check_docker_ffmpeg():
        use_docker = True
        print("Usando ffmpeg desde contenedor docker")
    else:
        print("ERROR: ffmpeg no disponible (ni en PATH ni en docker)")
        sys.exit(1)

    # Descargar
    success = download_with_ffmpeg(m3u8_url, output, use_docker)

    if success:
        size_mb = os.path.getsize(output) / (1024 * 1024)
        print(f"\nGuardado: {output}")
        print(f"Tamaño: {size_mb:.1f} MB")
    else:
        print("\nError en la descarga")
        sys.exit(1)


if __name__ == "__main__":
    main()
