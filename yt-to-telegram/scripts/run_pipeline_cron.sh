#!/bin/bash
# run_pipeline_cron.sh — Arranca y para el pipeline yt-to-telegram
# Cron: 0 1 * * * /home/jorge/dev/devjobs/yt-to-telegram/scripts/run_pipeline_cron.sh
#
# Flujo:
# 1. Arranca el servicio yt-pipeline con docker compose up -d
# 2. Para a las 18:00 del mismo día con docker compose down
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
# 18:00 del mismo día = 17 horas desde las 01:00
STOP_TS=$((START_TS + 17 * 3600))

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

log "🚀 Arrancando pipeline yt-to-telegram..."
cd "$COMPOSE_DIR"
docker compose up -d yt-pipeline 2>&1 | tee -a "$LOG_DIR/cron_$(date +%Y%m%d).log"

log "✅ Pipeline arrancado. Para a las $(date -d @$STOP_TS '+%H:%M %d/%m/%Y')"

# Esperar hasta la hora de parada, comprobando cada 5 min
while [ $(date +%s) -lt $STOP_TS ]; do
    REMAINING=$((STOP_TS - $(date +%s)))
    
    # Verificar si el contenedor sigue corriendo
    if ! docker compose ps yt-pipeline 2>/dev/null | grep -q "Up"; then
        log "⚠️  Contenedor yt-pipeline parado inesperadamente"
        break
    fi
    
    # Log cada hora
    if [ $((REMAINING % 3600)) -lt 300 ]; then
        log "⏳ Pipeline activo... quedan $((REMAINING / 3600))h $((REMAINING % 3600 / 60))m"
    fi
    
    sleep 300
done

# Parar el pipeline
log "🛑 Parando pipeline yt-to-telegram..."
cd "$COMPOSE_DIR"
docker compose down 2>&1 | tee -a "$LOG_DIR/cron_$(date +%Y%m%d).log"

# Resumen final
PENDING_CONVERTED=$(find "$DATA_DIR/converted" -name "*.mp4" 2>/dev/null | wc -l)
PENDING_DOWNLOADS=$(find "$DATA_DIR/downloads" -name "*.mp4" 2>/dev/null | wc -l)
log "📊 Resumen final: $PENDING_CONVERTED convertidos sin subir, $PENDING_DOWNLOADS en downloads"
log "✅ Pipeline detenido a las $(date '+%H:%M:%S')"
