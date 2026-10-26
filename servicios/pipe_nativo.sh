#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline de directos "sendo" — ejecución NATIVA en Ubuntu (sin Docker).
# ═══════════════════════════════════════════════════════════════════════════════
#
#   grabador (TwitchRecorder) → compresión (monitor_folder.sh) → subida (subir_videos.py)
#
# Uso:
#   bash servicios/pipe_nativo.sh            # primer plano (Ctrl+C para todo)
#   bash servicios/pipe_nativo.sh start -d   # segundo plano (daemon)
#   bash servicios/pipe_nativo.sh status     # estado de los 3 componentes
#   bash servicios/pipe_nativo.sh logs [recorder|monitor|uploader]
#   bash servicios/pipe_nativo.sh stop       # para los componentes en segundo plano
#   bash servicios/pipe_nativo.sh setup      # crea venvs e instala dependencias
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DATA="${DEVJOBS_DATA:-/srv/devjobs-data}"
RECORD_DIR="$DATA/grabaciones"
WATCH_DIR="$RECORD_DIR/test"
OUTPUT_DIR="$DATA/comprimidos"
PARTES_DIR="$DATA/partes"
RUN_DIR="$DATA/.native"
LOG_DIR="$RUN_DIR/logs"

REC_VENV="$ROOT/TwitchRecorder/.venv"
UP_VENV="$ROOT/downloader_telegram/.venv"

mkdir -p "$RECORD_DIR" "$WATCH_DIR" "$OUTPUT_DIR" "$PARTES_DIR" "$RUN_DIR" "$LOG_DIR"

log()  { echo -e "\033[1;36m[pipe]\033[0m $*"; }
warn() { echo -e "\033[1;33m[pipe]\033[0m $*"; }
err()  { echo -e "\033[1;31m[pipe]\033[0m $*" >&2; }

# ── Comandos de cada componente ──────────────────────────────────────────────
cmd_recorder() {
    cd "$ROOT/TwitchRecorder"
    RECORD_PATH="$RECORD_DIR" TEST_PATH="$WATCH_DIR" COPY_TO_TEST=true \
        exec "$REC_VENV/bin/python" -u main.py
}

cmd_monitor() {
    WATCH_DIR="$WATCH_DIR" \
    OUTPUT_DIR="$OUTPUT_DIR" \
    MONITOR_CONFIG_FILE="$ROOT/TwitchRecorder/config.json" \
    COMPLETED_ONLY=true CODEC=libx264 CRF=28 PRESET=fast THREADS=4 POLL_INTERVAL=30 \
        exec bash "$ROOT/ffmpeg-yt-dlp/scripts/monitor_folder.sh"
}

cmd_uploader() {
    cd "$ROOT/downloader_telegram"
    UPLOADER_CARPETAS="$OUTPUT_DIR" UPLOADER_PARTES="$PARTES_DIR" \
        exec "$UP_VENV/bin/python" -u app/subir_videos.py "$OUTPUT_DIR"
}

# ── Comprobaciones y setup ───────────────────────────────────────────────────
check_tools() {
    local missing=()
    for c in python3 ffmpeg ffprobe; do
        command -v "$c" >/dev/null 2>&1 || missing+=("$c")
    done
    command -v tesseract >/dev/null 2>&1 || warn "tesseract no encontrado (OCR de episodios en el uploader). Instala: sudo apt install tesseract-ocr tesseract-ocr-spa"
    command -v deno      >/dev/null 2>&1 || warn "deno no encontrado (lo usa yt-dlp para YouTube). Ver https://deno.land"
    if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
        warn "python3-venv no instalado (falta ensurepip). Instala: sudo apt install python3-venv"
    fi
    if [ ${#missing[@]} -gt 0 ]; then
        err "Faltan binarios obligatorios: ${missing[*]}"
        err "Instala: sudo apt install python3 python3-venv ffmpeg tesseract-ocr tesseract-ocr-spa"
        return 1
    fi
}

setup() {
    check_tools || true
    if ! python3 -m venv --help >/dev/null 2>&1 || ! python3 -c "import ensurepip" >/dev/null 2>&1; then
        err "No se puede crear venv (falta python3-venv). Instala: sudo apt install python3-venv"
        return 1
    fi
    if [ ! -x "$REC_VENV/bin/python" ]; then
        log "Creando venv de TwitchRecorder…"
        python3 -m venv "$REC_VENV"
    fi
    log "Instalando dependencias de TwitchRecorder…"
    "$REC_VENV/bin/pip" install --upgrade pip >/dev/null
    "$REC_VENV/bin/pip" install -r "$ROOT/TwitchRecorder/requirements.txt"

    if [ ! -x "$UP_VENV/bin/python" ]; then
        log "Creando venv de downloader_telegram…"
        python3 -m venv "$UP_VENV"
    fi
    log "Instalando dependencias del uploader…"
    "$UP_VENV/bin/pip" install --upgrade pip >/dev/null
    "$UP_VENV/bin/pip" install -r "$ROOT/downloader_telegram/requirements.txt"

    log "Dependencias instaladas."
}

ensure_venvs() {
    if [ ! -x "$REC_VENV/bin/python" ] || [ ! -x "$UP_VENV/bin/python" ]; then
        log "Faltan venvs; ejecutando setup…"
        setup
    fi
}

# ── Arranque ─────────────────────────────────────────────────────────────────
daemonize() {
    local comp pidfile pid
    for comp in recorder monitor uploader; do
        pidfile="$RUN_DIR/$comp.pid"
        if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
            warn "$comp ya está corriendo (pid $(cat "$pidfile"))."
            continue
        fi
        setsid bash "$SELF" __run "$comp" >>"$LOG_DIR/$comp.log" 2>&1 &
        echo $! > "$pidfile"
        log "$comp arrancado (pid $!). Log: $LOG_DIR/$comp.log"
    done
}

run_foreground() {
    local pids=()
    setsid bash "$SELF" __run recorder >>"$LOG_DIR/recorder.log" 2>&1 & pids+=($!)
    setsid bash "$SELF" __run monitor  >>"$LOG_DIR/monitor.log"  2>&1 & pids+=($!)
    setsid bash "$SELF" __run uploader >>"$LOG_DIR/uploader.log" 2>&1 & pids+=($!)
    log "Pipeline nativo arrancado (Ctrl+C para parar). Logs en $LOG_DIR"
    stop_children() {
        log "Parando pipeline…"
        for pid in "${pids[@]}"; do
            kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
        done
    }
    trap stop_children INT TERM
    wait || true
    stop_children
}

stop_all() {
    local comp pidfile pid
    for comp in uploader monitor recorder; do
        pidfile="$RUN_DIR/$comp.pid"
        if [ -f "$pidfile" ]; then
            pid="$(cat "$pidfile")"
            if kill -0 "$pid" 2>/dev/null; then
                log "Parando $comp (pid $pid)…"
                kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
            fi
            rm -f "$pidfile"
        fi
    done
}

status_all() {
    local comp pidfile pid state
    for comp in recorder monitor uploader; do
        pidfile="$RUN_DIR/$comp.pid"
        if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
            state="UP   (pid $(cat "$pidfile"))"
        else
            state="DOWN"
        fi
        printf '  %-9s %s\n' "$comp" "$state"
    done
}

show_logs() {
    local comp="${1:-uploader}"
    local f="$LOG_DIR/$comp.log"
    [ -f "$f" ] || { err "No existe $f"; exit 1; }
    tail -n 50 -f "$f"
}

# ── Despachador ──────────────────────────────────────────────────────────────
cmd="${1:-run}"
shift || true

case "$cmd" in
    __run)
        case "${1:-}" in
            recorder) cmd_recorder ;;
            monitor)  cmd_monitor ;;
            uploader) cmd_uploader ;;
            *) err "componente desconocido: ${1:-}"; exit 1 ;;
        esac
        ;;
    setup)
        setup
        ;;
    run|start)
        ensure_venvs
        check_tools
        if [ "${1:-}" = "-d" ] || [ "${1:-}" = "--daemon" ]; then
            daemonize
            status_all
        else
            run_foreground
        fi
        ;;
    stop)
        stop_all
        ;;
    status)
        status_all
        ;;
    logs)
        show_logs "${1:-uploader}"
        ;;
    *)
        echo "Uso: $SELF [run|start [-d]|stop|status|logs <recorder|monitor|uploader>|setup]" >&2
        exit 1
        ;;
esac
