#!/bin/bash
# run_pipeline_cron.sh — Ejecuta el pipeline de 01:00 a 18:00+1
# Cron: 0 1 * * * /home/jorge/dev/devjobs/yt-to-telegram/scripts/run_pipeline_cron.sh
#
# Flujo:
# 1. Arranca yt-pipeline (download → convert → upload)
# 2. Para a las 18:00 del día siguiente
# 3. Si quedan videos, los anota en pending_videos.log
# 4. La siguiente vez que se ejecute, continúa con esos videos

set -euo pipefail

COMPOSE_DIR="/home/jorge/dev/devjobs/yt-to-telegram"
DATA_DIR="/home/jorge/dev/devjobs/data/yt-pipeline"
LOG_DIR="$DATA_DIR/logs"
PENDING_LOG="$LOG_DIR/pending_videos.log"
RUNNING_MARKER="/tmp/yt-pipeline-cron-running"

# Timestamps
START_TS=$(date +%s)
# 18:00 del día siguiente = 41 horas desde las 01:00
STOP_TS=$((START_TS + 41 * 3600))

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_DIR/cron_$(date +%Y%m%d).log"
}

# Evitar instancias duplicadas
if [ -f "$RUNNING_MARKER" ]; then
    OLD_PID=$(cat "$RUNNING_MARKER")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        log "⚠️  Pipeline ya corriendo (PID $OLD_PID), saltando"
        exit 0
    else
        log "🗑️  Marker huérfano (PID $OLD_PID muerto), limpiando"
        rm -f "$RUNNING_MARKER"
    fi
fi

echo $$ > "$RUNNING_MARKER"
trap 'rm -f "$RUNNING_MARKER"' EXIT

mkdir -p "$LOG_DIR"

log "🚀 Pipeline arrancado. Para a las $(date -d @$STOP_TS '+%H:%M %d/%m/%Y')"

# Ejecutar pipeline en bucle hasta la hora de parada
while [ $(date +%s) -lt $STOP_TS ]; do
    log "▶️  Ejecutando pipeline..."
    
    cd "$COMPOSE_DIR"
    docker compose run --rm yt-pipeline python /app/scripts/pipeline.py \
        >> "$LOG_DIR/pipeline_$(date +%Y%m%d_%H%M%S).log" 2>&1 || true
    
    # Verificar si quedan videos pendientes
    PENDING_CONVERTED=$(find "$DATA_DIR/converted" -name "*.mp4" 2>/dev/null | wc -l)
    PENDING_DOWNLOADS=$(find "$DATA_DIR/downloads" -name "*.mp4" 2>/dev/null | wc -l)
    
    if [ "$PENDING_CONVERTED" -gt 0 ] || [ "$PENDING_DOWNLOADS" -gt 0 ]; then
        log "📋 Videos pendientes: $PENDING_CONVERTED convertidos, $PENDING_DOWNLOADS en downloads"
        echo "$(date '+%Y-%m-%d %H:%M:%S') | convertidos=$PENDING_CONVERTED downloads=$PENDING_DOWNLOADS" >> "$PENDING_LOG"
    fi
    
    # Esperar 10 minutos antes del siguiente ciclo
    REMAINING=$((STOP_TS - $(date +%s)))
    if [ $REMAINING -gt 600 ]; then
        log "⏳ Esperando 10 min... (quedan $((REMAINING / 3600))h $((REMAINING % 3600 / 60))m)"
        sleep 600
    else
        log "⏰ Quedan menos de 10 min, parando"
        break
    fi
done

log "🛑 Pipeline detenido a las $(date '+%H:%M:%S')"

# Resumen final
PENDING_CONVERTED=$(find "$DATA_DIR/converted" -name "*.mp4" 2>/dev/null | wc -l)
PENDING_DOWNLOADS=$(find "$DATA_DIR/downloads" -name "*.mp4" 2>/dev/null | wc -l)
log "📊 Resumen final: $PENDING_CONVERTED convertidos sin subir, $PENDING_DOWNLOADS en downloads"
