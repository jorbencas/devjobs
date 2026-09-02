"""pipeline_bridge.py — IPC via filesystem entre el bot y los servicios del pipeline.

Cada servicio escribe su estado en status.json.
El bot lee status.json y escribe órdenes en control.json.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("PIPELINE_DATA", "/data"))
STATUS_FILE = DATA_DIR / "pipeline_status.json"
CONTROL_FILE = DATA_DIR / "pipeline_control.json"
LOGS_FILE = DATA_DIR / "pipeline_logs.json"

MAX_LOG_LINES = 200


def _ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Status (servicios → bot) ──

def update_status(service: str, **kwargs):
    """Servicio actualiza su estado.
    Ej: update_status('recorder', status='recording', channel='midudev')
    """
    _ensure_dirs()
    status = _read_status()
    status[service] = {**kwargs, "updated_at": _now_iso()}
    status["last_update"] = _now_iso()
    _write_status(status)


def remove_status(service: str):
    """Servicio se limpia del status."""
    _ensure_dirs()
    status = _read_status()
    status.pop(service, None)
    status["last_update"] = _now_iso()
    _write_status(status)


def get_status() -> dict:
    """Lee el estado completo del pipeline."""
    return _read_status()


def get_queue_count() -> dict:
    """Cuenta archivos en cola: grabaciones, comprimidos, subiendo."""
    recordings_dir = DATA_DIR / "grabaciones" / "test"
    compressed_dir = DATA_DIR / "comprimidos"

    recording = len(list(recordings_dir.glob("*_completed.*"))) if recordings_dir.exists() else 0
    compressed = len(list(compressed_dir.glob("*_compressed.*"))) if compressed_dir.exists() else 0

    status = _read_status()
    uploading = 1 if status.get("uploader", {}).get("status") == "uploading" else 0

    return {"grabaciones": recording, "comprimidos": compressed, "subiendo": uploading}


# ── Control (bot → servicios) ──

def send_control(action: str, **kwargs):
    """Envía una orden a los servicios.
    Ej: send_control('pause')
    """
    _ensure_dirs()
    control = {"action": action, "timestamp": _now_iso(), **kwargs}
    _write_control(control)


def read_control() -> dict | None:
    """Servicio lee si hay alguna orden pendiente. La consume (la borra)."""
    _ensure_dirs()
    if not CONTROL_FILE.exists():
        return None
    try:
        data = json.loads(CONTROL_FILE.read_text(encoding="utf-8"))
        CONTROL_FILE.unlink(missing_ok=True)
        return data
    except (json.JSONDecodeError, OSError):
        return None


def peek_control() -> dict | None:
    """Lee la orden sin consumirla."""
    if not CONTROL_FILE.exists():
        return None
    try:
        return json.loads(CONTROL_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def clear_control():
    """Limpia la orden de control."""
    CONTROL_FILE.unlink(missing_ok=True)


# ── Logs (servicios → bot) ──

def append_log(source: str, message: str):
    """Añade una línea de log. source: 'recorder', 'monitor', 'uploader'."""
    _ensure_dirs()
    logs = _read_logs()
    logs.append({"ts": _now_iso(), "src": source, "msg": message})
    if len(logs) > MAX_LOG_LINES:
        logs = logs[-MAX_LOG_LINES:]
    _write_logs(logs)


def get_logs(count: int = 20, source: str = None) -> list:
    """Devuelve las últimas N líneas de log, opcionalmente filtrando por servicio."""
    logs = _read_logs()
    if source:
        logs = [l for l in logs if l.get("src") == source]
    return logs[-count:]


# ── Internos ──

def _read_status() -> dict:
    if not STATUS_FILE.exists():
        return {}
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_status(data: dict):
    STATUS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_logs() -> list:
    if not LOGS_FILE.exists():
        return []
    try:
        return json.loads(LOGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _write_logs(data: list):
    LOGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_control(data: dict):
    CONTROL_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
