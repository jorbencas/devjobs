#!/usr/bin/env python3
"""Helper para leer config del monitor desde config.json.

Uso: python3 get_monitor_config.py <archivo_video>
Devuelve JSON: {"detectar": true/false, "corte": true/false, "descripcion": true/false}
"""
import json
import os
import sys
import re
from pathlib import Path

# Config path: configurable via env var, default to host path
CONFIG_FILE = Path(os.environ.get(
    "MONITOR_CONFIG_FILE",
    "/home/jorge/dev/devjobs/TwitchRecorder/config.json"
))


def extract_channel(filename: str) -> str:
    """Extrae el nombre del canal del nombre del archivo.
    Formato: channel_YYYY-MM-DD_HH-MM-SS_KW_keyword.mp4"""
    name = Path(filename).stem
    # Quitar sufijos como _completed, _compressed, __parteN
    for suffix in ["_completed", "_compressed"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    # Quitar __parteN
    name = re.sub(r"__parte\d+$", "", name)
    # El canal es todo antes de la fecha (primer _ seguido de dígitos)
    match = re.match(r"^(.+?)_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", name)
    if match:
        return match.group(1)
    # Fallback: primer segmento antes de _
    return name.split("_")[0]


def get_channel_config(channel: str) -> dict:
    """Lee config.json y devuelve la config del canal."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        return {}

    channels = config.get("channels", {})
    if channel not in channels:
        return {}

    channel_data = channels[channel]
    platforms = channel_data.get("platform", [])
    if isinstance(platforms, str):
        platforms = [{"platform": platforms}]

    # Tomar la primera plataforma que tenga detectar/corte definido
    # (normalmente todos tienen la misma config)
    for p in platforms:
        result = {}
        if "detectar" in p:
            result["detectar"] = p["detectar"]
        if "corte" in p:
            result["corte"] = p["corte"]
        if "descripcion" in p:
            result["descripcion"] = p["descripcion"]
        if result:
            return result

    # Defaults si no hay config específica
    return {"detectar": True, "corte": True}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: get_monitor_config.py <video_file>"}))
        sys.exit(1)

    video_file = sys.argv[1]
    channel = extract_channel(video_file)
    config = get_channel_config(channel)

    # Defaults
    result = {
        "detectar": config.get("detectar", True),
        "corte": config.get("corte", True),
        "descripcion": config.get("descripcion", False),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()