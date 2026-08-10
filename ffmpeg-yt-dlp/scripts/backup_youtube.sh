#!/bin/bash
# ── Backup automático de canales de YouTube ──────────────────────────
# Uso: ./backup_youtube.sh [canal_url1] [canal_url2] ...
# Sin argumentos, usa la lista por defecto

set -e

# ── Configuración ────────────────────────────────────────────────────
BACKUP_DIR="${BACKUP_DIR:-$HOME/Backups/YouTube}"
LOG_FILE="$BACKUP_DIR/log_$(date +%Y-%m-%d).txt"
ARCHIVE_DIR="$BACKUP_DIR/.archives"
MAX_QUALITY="${MAX_QUALITY:-1080}"
MERGE_FORMAT="${MERGE_FORMAT:-mp4}"

# Canales por defecto (editar según necesidad)
DEFAULT_CHANNELS=(
    # "https://www.youtube.com/@CanalEjemplo1"
    # "https://www.youtube.com/@CanalEjemplo2"
)

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

backup_channel() {
    local channel_url="$1"
    local channel_name
    channel_name=$(echo "$channel_url" | sed 's/.*@//; s|.*/||')
    local channel_dir="$BACKUP_DIR/$channel_name"
    local archive_file="$ARCHIVE_DIR/${channel_name}.txt"

    mkdir -p "$channel_dir" "$ARCHIVE_DIR"

    log "${CYAN}Backup:${NC} $channel_name"

    local yt_args=(
        -f "bestvideo[height<=${MAX_QUALITY}][ext=${MERGE_FORMAT}]+bestaudio[ext=m4a]/best[height<=${MAX_QUALITY}]"
        --merge-output-format "$MERGE_FORMAT"
        --embed-thumbnail
        --embed-metadata
        --write-description
        --write-info-json
        -o "$channel_dir/%(upload_date>%Y-%m-%d)s-%(title)s [%(id)s].%(ext)s"
        --yes-playlist
    )

    # Usar archive para no re-descargar
    if [[ -f "$archive_file" ]]; then
        yt_args+=(--download-archive "$archive_file")
    else
        touch "$archive_file"
        yt_args+=(--download-archive "$archive_file")
    fi

    # Ejecutar descarga
    if yt-dlp "${yt_args[@]}" "$channel_url/videos" 2>&1 | tee -a "$LOG_FILE"; then
        log "${GREEN}✓${NC} $channel_name completado"
    else
        log "${RED}✗${NC} Error en $channel_name"
        return 1
    fi
}

show_help() {
    echo "Uso: $0 [opciones] [canal_url1] [canal_url2] ..."
    echo ""
    echo "Opciones:"
    echo "  -d, --dir DIR        Directorio de backup (default: ~/Backups/YouTube)"
    echo "  -q, --quality RES    Calidad máxima (default: 1080)"
    echo "  -f, --format FMT     Formato de salida (default: mp4)"
    echo "  -h, --help           Mostrar ayuda"
    echo ""
    echo "Ejemplo:"
    echo "  $0 https://www.youtube.com/@Canal1 https://www.youtube.com/@Canal2"
    echo "  BACKUP_DIR=/mnt/backup $0 https://www.youtube.com/@Canal1"
}

# ── Main ─────────────────────────────────────────────────────────────
CHANNELS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--dir)      BACKUP_DIR="$2"; shift 2 ;;
        -q|--quality)  MAX_QUALITY="$2"; shift 2 ;;
        -f|--format)   MERGE_FORMAT="$2"; shift 2 ;;
        -h|--help)     show_help; exit 0 ;;
        -*)            echo -e "${RED}Opción desconocida: $1${NC}"; show_help; exit 1 ;;
        *)             CHANNELS+=("$1"); shift ;;
    esac
done

# Usar canales por defecto si no se especificaron
if [[ ${#CHANNELS[@]} -eq 0 ]]; then
    CHANNELS=("${DEFAULT_CHANNELS[@]}")
fi

if [[ ${#CHANNELS[@]} -eq 0 ]]; then
    echo -e "${YELLOW}No hay canales configurados${NC}"
    echo "Edita el script o pasa las URLs como argumentos"
    exit 1
fi

mkdir -p "$BACKUP_DIR" "$ARCHIVE_DIR"
log "${CYAN}=== Backup YouTube iniciado ===${NC}"
log "Canales: ${#CHANNELS[@]}"
log "Destino: $BACKUP_DIR"

errors=0
for channel in "${CHANNELS[@]}"; do
    backup_channel "$channel" || ((errors++))
done

log "${CYAN}=== Backup completado ===${NC}"
log "Errores: $errors/${#CHANNELS[@]}"

exit $errors
