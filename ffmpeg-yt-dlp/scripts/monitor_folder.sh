#!/bin/bash
# ── Monitor de carpeta para compresión automática ───────────────────
# Uso: ./monitor_folder.sh [carpeta] [opcionales]
# Vigila una carpeta y comprime vídeos nuevos automáticamente

set -e

# ── Configuración ────────────────────────────────────────────────────
WATCH_DIR="${1:-$HOME/data/grabaciones/test}"
OUTPUT_DIR="${OUTPUT_DIR:-$HOME/data/comprimidos}"
LOG_FILE="$OUTPUT_DIR/log_$(date +%Y-%m-%d).txt"
PROCESSED_DIR="$OUTPUT_DIR/.processed"
CRF="${CRF:-28}"
PRESET="${PRESET:-fast}"
CODEC="${CODEC:-libx264}"
AUDIO_CODEC="${AUDIO_CODEC:-aac}"
AUDIO_BITRATE="${AUDIO_BITRATE:-128k}"
POLL_INTERVAL="${POLL_INTERVAL:-30}"
RESOLUTION="${RESOLUTION:-}"
TAMANO_MAX_MB="${TAMANO_MAX_MB:-1900}"
COMPLETED_ONLY="${COMPLETED_ONLY:-false}"
# Detección de episodios (corte de extremos + metadata para el uploader)
OCR_STEP="${OCR_STEP:-180}"
CORTE_MARGEN="${CORTE_MARGEN:-300}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
    # Escribir a un temporal y renombrar al terminar, para que el uploader
    # (que vigila *_compressed.mp4) nunca coja un archivo a medio escribir.
    local tmp_output="${output}.tmp"

    log "${CYAN}Comprimiendo:${NC} $filename"

    # Detectar episodios para recortar extremos y guardar metadata para el uploader
    local det_json="${OUTPUT_DIR}/${name}_episodios.json"
    local cut_inicio=""
    local cut_fin=""
    local duration
    if command -v python3 >/dev/null 2>&1 && command -v tesseract >/dev/null 2>&1 \
       && [[ -f "$SCRIPT_DIR/detectar_episodios.py" ]]; then
        local det
        det=$(python3 "$SCRIPT_DIR/detectar_episodios.py" "$input" "$OCR_STEP" "$CORTE_MARGEN" 2>/dev/null)
        if [[ -n "$det" ]] && echo "$det" | grep -q '"episodios"'; then
            echo "$det" > "$det_json"
            local rango desc
            desc=$(echo "$det" | python3 -c "import sys,json;print(json.load(sys.stdin).get('descripcion',''))" 2>/dev/null)
            rango=${desc:-$(echo "$det" | python3 -c "import sys,json;print(json.load(sys.stdin).get('rango',''))" 2>/dev/null)}
            cut_inicio=$(echo "$det" | python3 -c "import sys,json;d=json.load(sys.stdin).get('corte',{});print(d.get('inicio',''))" 2>/dev/null)
            cut_fin=$(echo "$det" | python3 -c "import sys,json;d=json.load(sys.stdin).get('corte',{});print(d.get('fin',''))" 2>/dev/null)
            corte_posible=$(echo "$det" | python3 -c "import sys,json;d=json.load(sys.stdin).get('corte',{});print(str(d.get('posible',False)).lower())" 2>/dev/null)
            if [[ -n "$rango" ]]; then
                if [[ "$corte_posible" == "true" ]]; then
                    log "  Contenido detectado: $rango (corte ${cut_inicio}s → ${cut_fin}s)"
                else
                    log "  Contenido detectado: $rango (sin corte: margen inválido)"
                    cut_inicio=""
                    cut_fin=""
                fi
            else
                log "  Contenido no detectado (sin corte)"
            fi
        fi
    fi

    # Obtener duración para calcular progreso
    if [[ -n "$cut_inicio" && -n "$cut_fin" ]]; then
        duration=$(( cut_fin - cut_inicio ))
    else
        duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$input" 2>/dev/null | cut -d. -f1)
    fi

    local slice_args=()
    if [[ -n "$cut_inicio" && -n "$cut_fin" ]]; then
        slice_args=(-ss "$cut_inicio" -i "$input" -t "$duration")
    else
        slice_args=(-i "$input")
    fi
    local -a vf_args=()
    [[ -n "$RESOLUTION" ]] && vf_args=(-vf "scale=-2:${RESOLUTION}")

    local ffmpeg_args=(-y)
    if [[ -n "$cut_inicio" && -n "$cut_fin" ]]; then
        ffmpeg_args+=(-ss "$cut_inicio" -i "$input" -t "$duration")
    else
        ffmpeg_args+=(-i "$input")
    fi
    ffmpeg_args+=(-c:v "$CODEC" -crf "$CRF" -preset "$PRESET")
    ffmpeg_args+=(-c:a "$AUDIO_CODEC" -b:a "$AUDIO_BITRATE")
    ffmpeg_args+=("${vf_args[@]}")
    ffmpeg_args+=(-movflags +faststart)
    # -f mp4 explícito: el temporal acaba en .tmp y ffmpeg necesita el formato
    # para no fallar al elegir muxer por extensión.
    ffmpeg_args+=(-f mp4)

    if ffmpeg "${ffmpeg_args[@]}" "$tmp_output" 2>/dev/null; then
        # ── Límite de tamaño (Telegram ~2 GB): si el CRF one-pass supera el tope,
        #    se re-codifica en 2 pasadas apuntando a ese tamaño (garantía < 2 GB).
        local size_bytes
        size_bytes=$(stat -c%s "$tmp_output" 2>/dev/null || stat -f%z "$tmp_output" 2>/dev/null || echo 0)
        local max_bytes=$(( TAMANO_MAX_MB * 1024 * 1024 ))
        if [[ "$size_bytes" -gt "$max_bytes" && -n "$duration" && "$duration" -gt 0 ]]; then
            log "⚠  $filename pesa $((size_bytes/1024/1024))MB (>${TAMANO_MAX_MB}MB). Re-codificando en 2 pasadas ≤ ${TAMANO_MAX_MB}MB..."
            local abps=128000
            case "$AUDIO_BITRATE" in
                *k) abps=$(( ${AUDIO_BITRATE%k} * 1000 )) ;;
                *M) abps=$(( ${AUDIO_BITRATE%M} * 1000000 )) ;;
            esac
            local audio_bytes=$(( duration * abps / 8 ))
            local video_bytes=$(( max_bytes - audio_bytes ))
            local video_bps=$(( video_bytes * 8 / duration ))
            if [[ "$video_bps" -gt 0 ]]; then
                ffmpeg "${slice_args[@]}" "${vf_args[@]}" -c:v "$CODEC" -b:v "$video_bps" \
                    -preset "$PRESET" -pass 1 -an -f null - \
                    2>/dev/null
                if ffmpeg "${slice_args[@]}" "${vf_args[@]}" -c:v "$CODEC" -b:v "$video_bps" \
                    -preset "$PRESET" -pass 2 \
                    -c:a "$AUDIO_CODEC" -b:a "$AUDIO_BITRATE" \
                    -movflags +faststart -f mp4 "$tmp_output" 2>/dev/null; then
                    log "  ✓ 2 pasadas completadas → ${TAMANO_MAX_MB}MB"
                else
                    log "${RED}✗${NC} Falló la 2ª pasada; se mantiene el CRF one-pass."
                fi
                rm -f ffmpeg2pass-*.log ffmpeg2pass-*.log.mbtree
            fi
        fi

        mv "$tmp_output" "$output"
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
        rm -f "$tmp_output"
        rm -f "$det_json"
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
    echo "  -o, --output DIR     Directorio de salida (default: ~/data/comprimidos)"
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
