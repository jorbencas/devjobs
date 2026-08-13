#!/bin/bash
# ── Monitor de carpeta para compresión automática ───────────────────
# Uso: ./monitor_folder.sh [carpeta] [opcionales]
# Vigila una carpeta y comprime vídeos nuevos automáticamente

set -e

# ── Configuración ────────────────────────────────────────────────────
WATCH_DIR="${1:-$HOME/Videos/para_comprimir}"
OUTPUT_DIR="${OUTPUT_DIR:-$HOME/Videos/comprimidos}"
LOG_FILE="$OUTPUT_DIR/log_$(date +%Y-%m-%d).txt"
PROCESSED_DIR="$OUTPUT_DIR/.processed"
CRF="${CRF:-28}"
PRESET="${PRESET:-fast}"
CODEC="${CODEC:-libx264}"
AUDIO_CODEC="${AUDIO_CODEC:-aac}"
AUDIO_BITRATE="${AUDIO_BITRATE:-128k}"
POLL_INTERVAL="${POLL_INTERVAL:-30}"
RESOLUTION="${RESOLUTION:-}"
COMPLETED_ONLY="${COMPLETED_ONLY:-false}"

# Extensiones de vídeo soportadas
VIDEO_EXTENSIONS="mp4|mkv|avi|mov|webm|flv|ts|m4v|mpg|mpeg"

# Construye el patrón find: solo *_completed.mp4 si COMPLETED_ONLY, si no cualquier vídeo
video_find_pattern() {
    if [[ "$COMPLETED_ONLY" == "true" ]]; then
        echo -regextype posix-extended -iregex '.*_completed\.('"$VIDEO_EXTENSIONS"')$'
    else
        echo -regextype posix-extended -iregex '.*\.('"$VIDEO_EXTENSIONS"')$'
    fi
}

# ── Colores ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── Funciones ────────────────────────────────────────────────────────
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "$msg" | tee -a "$LOG_FILE"
}

compress_video() {
    local input="$1"
    local filename
    filename=$(basename "$input")
    local name="${filename%.*}"
    local ext="${filename##*.}"
    local output="$OUTPUT_DIR/${name}_compressed.mp4"

    log "${CYAN}Comprimiendo:${NC} $filename"

    # Obtener duración para calcular progreso
    local duration
    duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$input" 2>/dev/null | cut -d. -f1)

    local ffmpeg_args=(-y -i "$input")
    ffmpeg_args+=(-c:v "$CODEC" -crf "$CRF" -preset "$PRESET")
    ffmpeg_args+=(-c:a "$AUDIO_CODEC" -b:a "$AUDIO_BITRATE")
    if [[ -n "$RESOLUTION" ]]; then
        ffmpeg_args+=(-vf "scale=-2:${RESOLUTION}")
    fi
    ffmpeg_args+=(-movflags +faststart)

    if ffmpeg "${ffmpeg_args[@]}" "$output" 2>/dev/null; then
        local input_size output_size
        input_size=$(stat -c%s "$input" 2>/dev/null || stat -f%z "$input" 2>/dev/null || echo 0)
        output_size=$(stat -c%s "$output" 2>/dev/null || stat -f%z "$output" 2>/dev/null || echo 0)

        local input_mb=$((input_size / 1024 / 1024))
        local output_mb=$((output_size / 1024 / 1024))
        local savings=$(( (input_size - output_size) * 100 / input_size ))

        log "${GREEN}✓${NC} $filename → ${output_mb}MB (-${savings}%)"

        # Mover original a carpeta procesados
        mkdir -p "$PROCESSED_DIR"
        mv "$input" "$PROCESSED_DIR/$filename"
        log "  Original movido a: $PROCESSED_DIR/$filename"

        return 0
    else
        log "${RED}✗${NC} Error al comprimir: $filename"
        rm -f "$output"
        return 1
    fi
}

process_pending() {
    local count=0
    while IFS= read -r -d '' file; do
        compress_video "$file" || true
        ((count++))
    done < <(find "$WATCH_DIR" -maxdepth 1 -type f $(video_find_pattern) -print0 2>/dev/null)
    return $count
}

show_help() {
    echo "Uso: $0 [opciones] [carpeta_a_vigilar]"
    echo ""
    echo "Opciones:"
    echo "  -o, --output DIR     Directorio de salida (default: ~/Videos/comprimidos)"
    echo "  -c, --crf VALUE      Calidad CRF (default: 28, menor = mejor)"
    echo "  -p, --preset NAME    Preset de velocidad (default: fast)"
    echo "  --codec NAME         Códec de vídeo (default: libx264)"
    echo "  -r, --resolution N   Escalar altura a N px, ej: 720 (default: sin reescalar)"
    echo "  --completed-only     Procesar solo archivos *_completed.* / *_compressed.*"
    echo "  --interval SEGS      Intervalo de polling en segundos (default: 30)"
    echo "  -h, --help           Mostrar ayuda"
    echo ""
    echo "Ejemplo:"
    echo "  $0 ~/Downloads/videos"
    echo "  $0 -o /mnt/comp -c 23 -p medium ~/Videos/nuevos"
}

# ── Main ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output)   OUTPUT_DIR="$2"; shift 2 ;;
        -c|--crf)      CRF="$2"; shift 2 ;;
        -p|--preset)   PRESET="$2"; shift 2 ;;
        --codec)       CODEC="$2"; shift 2 ;;
        -r|--resolution) RESOLUTION="$2"; shift 2 ;;
        --completed-only) COMPLETED_ONLY="true"; shift ;;
        --interval)    POLL_INTERVAL="$2"; shift 2 ;;
        -h|--help)     show_help; exit 0 ;;
        -*)            echo -e "${RED}Opción desconocida: $1${NC}"; show_help; exit 1 ;;
        *)             WATCH_DIR="$1"; shift ;;
    esac
done

mkdir -p "$WATCH_DIR" "$OUTPUT_DIR" "$PROCESSED_DIR"

log "${CYAN}=== Monitor de vídeo iniciado ===${NC}"
log "Vigilando: $WATCH_DIR"
log "Salida: $OUTPUT_DIR"
log "CRF: $CRF | Preset: $PRESET | Códec: $CODEC"
[[ -n "$RESOLUTION" ]] && log "Resolución: $RESOLUTION (escala)"
[[ "$COMPLETED_ONLY" == "true" ]] && log "Solo archivos *_completed / *_compressed"
log "Polling cada ${POLL_INTERVAL}s"
log "Presiona Ctrl+C para detener"
echo ""

# Procesar vídeos existentes primero
log "Procesando vídeos existentes..."
process_pending
existing=$?
log "Procesados $existing vídeos existentes"

# Bucle principal de monitoreo
log "Iniciando monitoreo..."
while true; do
    # Buscar vídeos nuevos
    new_files=$(find "$WATCH_DIR" -maxdepth 1 -type f $(video_find_pattern) 2>/dev/null | wc -l)

    if [[ "$new_files" -gt 0 ]]; then
        log "Detectados $new_files vídeos nuevos"
        process_pending
    fi

    sleep "$POLL_INTERVAL"
done
