#!/bin/bash

VERSION="5.0.0"

# ── Configuración guardada ────────────────────────────────────────────

CONF_FILE="${BASH_SOURCE[0]%/*}/conf.json"

load_config() {
    local mode="${1:-}"
    [[ ! -f "$CONF_FILE" ]] && return 1
    command -v jq &>/dev/null || return 1
    local cfg
    cfg=$(jq -r '.' "$CONF_FILE" 2>/dev/null) || return 1

    # Config global (siempre se carga)
    INPUT_DIR=$(echo "$cfg"     | jq -r '.inputDir // empty')      || true
    OUTPUT_DIR=$(echo "$cfg"    | jq -r '.outputDir // empty')     || true
    MAX_THREADS=$(echo "$cfg"   | jq -r '.maxThreads // empty')    || true
    EXTENSIONS=$(echo "$cfg"    | jq -r '.extensions // empty')    || true
    VERBOSE=$(echo "$cfg"       | jq -r '.verbose // empty')       || true

    # Config por modo
    if [[ -n "$mode" ]] && echo "$cfg" | jq -e ".modes.\"$mode\"" &>/dev/null; then
        local m
        m=$(echo "$cfg" | jq -r ".modes.\"$mode\"")
        case "$mode" in
            convert)
                PRESET=$(echo "$m"        | jq -r '.preset // empty')        || true
                AUDIO_CODEC=$(echo "$m"   | jq -r '.audioCodec // empty')    || true
                AUDIO_BITRATE=$(echo "$m" | jq -r '.audioBitrate // empty')  || true
                RESOLUTION=$(echo "$m"    | jq -r '.resolution // empty')    || true
                MAX_SIZE=$(echo "$m"      | jq -r '.maxSize // empty')       || true
                SOCIAL=$(echo "$m"        | jq -r '.social // empty')        || true
                ;;
            cut)
                START_TIME=$(echo "$m"    | jq -r '.startTime // empty')     || true
                END_TIME=$(echo "$m"      | jq -r '.endTime // empty')       || true
                ;;
            gif)
                GIF_FPS=$(echo "$m"       | jq -r '.gifFps // empty')        || true
                GIF_SCALE=$(echo "$m"     | jq -r '.gifScale // empty')      || true
                ;;
            thumbnail)
                THUMBNAIL_TIME=$(echo "$m"| jq -r '.thumbnailTime // empty') || true
                ;;
            rotate)
                ROTATE_DEGREES=$(echo "$m"| jq -r '.rotateDegrees // empty') || true
                ;;
            crop)
                CROP_SIZE=$(echo "$m"     | jq -r '.cropSize // empty')      || true
                ;;
            fade)
                FADE_SECONDS=$(echo "$m"  | jq -r '.fadeSeconds // empty')   || true
                ;;
            fps)
                TARGET_FPS=$(echo "$m"    | jq -r '.targetFps // empty')     || true
                ;;
            speed)
                SPEED=$(echo "$m"         | jq -r '.speed // empty')         || true
                ;;
            audio-only)
                OUTPUT_FORMAT=$(echo "$m" | jq -r '.outputFormat // empty')  || true
                ;;
        esac
    fi
}

save_config() {
    local mode="${1:-}"
    local tmp="$CONF_FILE.tmp"

    # Si ya existe config, merger; si no, crear nueva
    if [[ -f "$CONF_FILE" ]] && command -v jq &>/dev/null; then
        # Actualizar config global
        jq --arg input "$INPUT_DIR" \
           --arg output "$OUTPUT_DIR" \
           --arg threads "$MAX_THREADS" \
           --arg ext "$EXTENSIONS" \
           --argjson verbose "$VERBOSE" \
           '.inputDir = $input | .outputDir = $output | .maxThreads = $threads | .extensions = $ext | .verbose = $verbose' \
           "$CONF_FILE" > "$tmp" && mv "$tmp" "$CONF_FILE"

        # Guardar config del modo actual
        if [[ -n "$mode" ]]; then
            local mode_config="{}"
            case "$mode" in
                convert)
                    mode_config=$(jq -n \
                        --arg social "$SOCIAL" \
                        --arg preset "$PRESET" \
                        --arg audio "$AUDIO_CODEC" \
                        --arg bitrate "$AUDIO_BITRATE" \
                        --arg res "$RESOLUTION" \
                        --arg max "$MAX_SIZE" \
                        '{social: $social, preset: $preset, audioCodec: $audio, audioBitrate: $bitrate, resolution: $res, maxSize: $max}')
                    ;;
                cut)
                    mode_config=$(jq -n \
                        --arg start "$START_TIME" \
                        --arg end "$END_TIME" \
                        '{startTime: $start, endTime: $end}')
                    ;;
                gif)
                    mode_config=$(jq -n \
                        --arg fps "$GIF_FPS" \
                        --arg scale "$GIF_SCALE" \
                        '{gifFps: $fps, gifScale: $scale}')
                    ;;
                thumbnail)
                    mode_config=$(jq -n \
                        --arg time "$THUMBNAIL_TIME" \
                        '{thumbnailTime: $time}')
                    ;;
                rotate)
                    mode_config=$(jq -n \
                        --arg degrees "$ROTATE_DEGREES" \
                        '{rotateDegrees: $degrees}')
                    ;;
                crop)
                    mode_config=$(jq -n \
                        --arg size "$CROP_SIZE" \
                        '{cropSize: $size}')
                    ;;
                fade)
                    mode_config=$(jq -n \
                        --arg seconds "$FADE_SECONDS" \
                        '{fadeSeconds: $seconds}')
                    ;;
                fps)
                    mode_config=$(jq -n \
                        --arg fps "$TARGET_FPS" \
                        '{targetFps: $fps}')
                    ;;
                speed)
                    mode_config=$(jq -n \
                        --arg speed "$SPEED" \
                        '{speed: $speed}')
                    ;;
                audio-only)
                    mode_config=$(jq -n \
                        --arg format "$OUTPUT_FORMAT" \
                        '{outputFormat: $format}')
                    ;;
            esac

            jq --arg mode "$mode" --argjson cfg "$mode_config" \
               '.modes[$mode] = $cfg' "$CONF_FILE" > "$tmp" && mv "$tmp" "$CONF_FILE"
        fi
    else
        # Crear config nueva
        cat > "$CONF_FILE" <<ENDJSON
{
  "inputDir":     "$INPUT_DIR",
  "outputDir":    "$OUTPUT_DIR",
  "maxThreads":   "$MAX_THREADS",
  "extensions":   "$EXTENSIONS",
  "verbose":      $VERBOSE,
  "modes": {}
}
ENDJSON
        [[ -n "$mode" ]] && save_config "$mode"
    fi
    echo -e "${GREEN}Configuración guardada${NC}"
}

# ── Colores ───────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Cleanup ───────────────────────────────────────────────────────────

cleanup() {
    echo ""
    echo -e "${RED}Interrumpido. Limpiando...${NC}"
    if [[ -n "${active_threads[*]}" ]]; then
        for pid in "${active_threads[@]}"; do
            kill "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null
        done
    fi
    rm -f "$OUTPUT_DIR"/.tmp_* "$OUTPUT_DIR"/*.log "$OUTPUT_DIR"/*.progress 2>/dev/null
    echo -e "${GREEN}Limpieza completada.${NC}"
    exit 130
}
trap cleanup SIGINT SIGTERM SIGHUP

# ── Help ──────────────────────────────────────────────────────────────

show_help() {
    cat <<EOF
midu.sh v${VERSION} — Conversor, descargador y editor de vídeo

═══════════════════════════════════════════════════════════════════════
 QUÉ HACE CADA MODO (resumen rápido)
═══════════════════════════════════════════════════════════════════════

  -d URL          Descarga vídeos de YouTube, Kick, Twitch, etc.
  --cut           Corta un trozo del vídeo (rápido, sin perder calidad)
  --convert       Convierte/comprime el vídeo (ajusta tamaño y calidad)
  --gif           Crea un GIF animado a partir del vídeo
  --thumbnail     Saca una captura de pantalla (imagen PNG) del vídeo
  --info          Muestra datos del vídeo: duración, resolución, codecs...
  --rotate        Gira el vídeo 90°, 180° o 270°
  --crop          Recorta el vídeo a un tamaño específico (ej: 640:480)
  --fade          Añade fade in (aparecer) y fade out (desaparecer)
  --normalize     Equaliza el volumen del audio para que suene parejo
  --watermark     Pone una imagen encima del vídeo (logo, marca, etc)
  --deinterlace   Quita el "entrelazado" de vídeos de TV viejos (rayas)
  --fps           Cambia los frames por segundo (ej: de 30 a 60 para más suavidad)
  --speed         Acelera o ralentiza el vídeo (0.5 = mitad, 2 = doble)
  -sl / -sh       Embebe o quema subtítulos en el vídeo
  --concat        Une varios vídeos en uno solo
  -ao / -ma       Extrae solo audio o mezcla audio con vídeo
  --watch         Vigila una carpeta y convierte automáticamente

═══════════════════════════════════════════════════════════════════════

Uso: ./midu.sh [opciones]

MODO DESCARGA:
  -d, --download URL     Descargar vídeo de URL (YouTube, Twitch, Kick, etc)
  -ds, --dl-start TIME   Inicio descarga parcial (ej: 00:05:00)
  -de, --dl-end TIME     Fin descarga parcial (ej: 00:10:00)

MODO CORTE (lossless, sin re-encoding):
  --cut                  Cortar vídeo por tiempo
  -ss, --start TIME      Tiempo de inicio (ej: 00:01:30 o 90)
  -e, --end TIME         Tiempo de fin (ej: 00:03:45 o 225)

MODO CONVERSIÓN:
  --convert              Convertir/comprimir vídeos (modo por defecto)
  -s, --social PLATFORM  Preset para red social (whatsapp|telegram|instagram|tiktok|youtube|twitter|facebook)
  -p, --preset PRESET    Calidad: ultrafast|web|default|archive|quality (default: default)
  -g, --max-gb GB        Tamaño máximo en GB (ej: 2GB)
  -i, --input DIR        Directorio de entrada (default: ./test)
  -o, --output DIR       Directorio de salida (default: ./optimizados)

MODO GIF:
  --gif                  Convertir a GIF animado
  --gif-fps FPS          FPS del GIF (default: 10)
  --gif-scale SIZE       Escala del GIF (default: 480:-1)

MODO THUMBNAIL:
  --thumbnail            Extraer frame como imagen PNG
  --thumbnail-time TIME  Timestamp del frame (default: 00:00:01)

MODO INFO:
  --info                 Mostrar info del vídeo (duración, codecs, etc)

MODO ROTAR:
  --rotate GRADOS        Rotar vídeo (90, 180, 270)

MODO CROP:
  --crop W:H             Recortar vídeo

MODO FADE:
  --fade SEGUNDOS        Fade in/out automático

MODO NORMALIZE:
  --normalize            Normalizar audio (loudnorm)

MODO WATERMARK:
  --watermark FILE       Añadir marca de agua (png/jpg)

MODO DEINTERLACE:
  --deinterlace          Desentrelazar vídeo

MODO FPS:
  --fps N                Cambiar framerate

VELOCIDAD:
  --speed FACTOR         Velocidad del vídeo (0.25, 0.5, 0.75, 1.5, 2, 4)

SUBTÍTULOS:
  -sl, --sub-soft FILE   Subtítulos soft (embed en contenedor)
  -sh, --sub-hard FILE   Subtítulos hard (quemados en vídeo)

AUDIO:
  -ao, --audio-out URL   Extraer solo audio (mp3 por defecto)
  -of, --out-format FMT  Formato audio: mp3|m4a|flac|wav|opus (default: mp3)
  -ma, --merge-audio FILE  Mezclar audio con vídeo (-ma audio.mp3)

CONCATENAR:
  --concat FILE...       Unir varios archivos en uno solo

WATCH:
  --watch                Monitorear carpeta, convertir automáticamente

GENERAL:
  -n, --non-interactive  Sin prompts, usa valores por defecto
  -c, --save-config      Guarda la configuración actual en conf.json
  -v, --verbose          Muestra progreso línea por línea (default: resumen)
  -V, --version          Versión
  -h, --help             Muestra esta ayuda

FLUJO RECOMENDADO:
  ./midu.sh -d "URL"                                    # 1. Descargar
  ./midu.sh --cut -ss 00:01:30 -e 00:03:45              # 2. Cortar (lossless)
  ./midu.sh --convert -p web                             # 3. Convertir

Ejemplos:
  ./midu.sh -d "https://kick.com/..."                   # Descargar de Kick
  ./midu.sh -d "https://twitch.tv/..."                  # Descargar de Twitch
  ./midu.sh --cut -ss 00:05:00 -e 00:10:00              # Cortar 5 minutos
  ./midu.sh --convert -s telegram                       # Listo para Telegram
  ./midu.sh --gif                                       # Convertir a GIF
  ./midu.sh --gif --gif-fps 15 --gif-scale 320:-1       # GIF personalizado
  ./midu.sh --thumbnail --thumbnail-time 00:01:30       # Extraer frame
  ./midu.sh --info                                      # Info del vídeo
  ./midu.sh --rotate 90                                 # Rotar 90°
  ./midu.sh --crop 640:480                              # Recortar
  ./midu.sh --fade 2                                    # Fade 2 segundos
  ./midu.sh --normalize                                 # Normalizar audio
  ./midu.sh --watermark logo.png                        # Marca de agua
  ./midu.sh --deinterlace                               # Desentrelazar
  ./midu.sh --fps 60                                    # Cambiar a 60fps
  ./midu.sh --speed 2.0                                 # Doble de velocidad
  ./midu.sh -sl subs.srt                                # Embebir subtítulos
  ./midu.sh -sh subs.srt                                # Quemar subtítulos
  ./midu.sh -ao "URL"                                   # Extraer audio
  ./midu.sh -ma audio.mp3                               # Mezclar audio con vídeo
  ./midu.sh --concat v1.mkv v2.mkv v3.mkv              # Unir vídeos
  ./midu.sh --watch                                     # Modo watch
EOF
}

# ── Defaults ──────────────────────────────────────────────────────────

INPUT_DIR="./test"
OUTPUT_DIR="./optimizados"
PRESET="default"
AUDIO_CODEC="aac"
AUDIO_BITRATE="128k"
RESOLUTION="original"
MAX_SIZE=""
MAX_THREADS=$(nproc)
EXTENSIONS="avi,webm,mkv,mp4,flv"
INTERACTIVE=true
VERBOSE=false
SOCIAL=""
START_TIME=""
END_TIME=""

# ── Nuevas funcionalidades ───────────────────────────────────────────MODE=""                         # download|audio-only|merge-audio|concat|watch|cut|convert|gif|thumbnail|info|rotate|crop|fade|normalize|watermark|deinterlace|fps
URL=""                          # URL para descargar
DOWNLOAD_START=""               # Inicio descarga parcial
DOWNLOAD_END=""                 # Fin descarga parcial
AUDIO_INPUT=""                  # Archivo de audio para mezclar
OUTPUT_FORMAT=""                # Formato de salida (mp3, m4a, wav, etc)
SUBTITLE_SOFT=""                # Subtítulos soft (embed)
SUBTITLE_HARD=""                # Subtítulos hard (quemados)
SPEED=""                        # Factor de velocidad (0.5, 1.5, 2, etc)
CONCAT_FILES=()                 # Lista de archivos para concatenar
WATCH_MODE=false                # Modo watch
ROTATE_DEGREES=""               # Grados de rotación (90, 180, 270)
CROP_SIZE=""                    # Tamaño de crop (W:H)
FADE_SECONDS=""                 # Duración del fade en segundos
WATERMARK_FILE=""               # Archivo de marca de agua
TARGET_FPS=""                   # Framerate de salida
GIF_FPS=""                      # FPS del GIF
GIF_SCALE=""                    # Escala del GIF (ej: 480:-1)
THUMBNAIL_TIME=""               # Timestamp del frame a extraer

# ── Parse flags ───────────────────────────────────────────────────────

SAVE_CONFIG=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -s|--social)     SOCIAL="$2"; shift 2 ;;
        -p|--preset)     PRESET="$2"; shift 2 ;;
        -g|--max-gb)     MAX_SIZE="$2"; shift 2 ;;
        -ss|--start)     START_TIME="$2"; shift 2 ;;
        -e|--end)        END_TIME="$2"; shift 2 ;;
        -d|--download)   MODE="download"; URL="$2"; shift 2 ;;
        -ds|--dl-start)  DOWNLOAD_START="$2"; shift 2 ;;
        -de|--dl-end)    DOWNLOAD_END="$2"; shift 2 ;;
        -ao|--audio-out) MODE="audio-only"; URL="$2"; shift 2 ;;
        -of|--out-format) OUTPUT_FORMAT="$2"; shift 2 ;;
        -ma|--merge-audio) MODE="merge-audio"; AUDIO_INPUT="$2"; shift 2 ;;
        -sl|--sub-soft)    SUBTITLE_SOFT="$2"; shift 2 ;;
        -sh|--sub-hard)    SUBTITLE_HARD="$2"; shift 2 ;;
        --speed)           SPEED="$2"; shift 2 ;;
        --concat)          MODE="concat"; shift; CONCAT_FILES=(); while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do CONCAT_FILES+=("$1"); shift; done ;;
        --cut)             MODE="cut"; shift ;;
        --convert)         MODE="convert"; shift ;;
        --gif)             MODE="gif"; shift ;;
        --thumbnail)       MODE="thumbnail"; shift ;;
        --info)            MODE="info"; shift ;;
        --rotate)          MODE="rotate"; ROTATE_DEGREES="$2"; shift 2 ;;
        --crop)            MODE="crop"; CROP_SIZE="$2"; shift 2 ;;
        --fade)            MODE="fade"; FADE_SECONDS="$2"; shift 2 ;;
        --normalize)       MODE="normalize"; shift ;;
        --watermark)       MODE="watermark"; WATERMARK_FILE="$2"; shift 2 ;;
        --deinterlace)     MODE="deinterlace"; shift ;;
        --fps)             MODE="fps"; TARGET_FPS="$2"; shift 2 ;;
        --gif-fps)         GIF_FPS="$2"; shift 2 ;;
        --gif-scale)       GIF_SCALE="$2"; shift 2 ;;
        --thumbnail-time)  THUMBNAIL_TIME="$2"; shift 2 ;;
        --watch)           WATCH_MODE=true; shift ;;
        -i|--input)        INPUT_DIR="$2"; shift 2 ;;
        -o|--output)     OUTPUT_DIR="$2"; shift 2 ;;
        -n|--non-interactive) INTERACTIVE=false; shift ;;
        -c|--save-config)     SAVE_CONFIG=true; shift ;;
        -v|--verbose)         VERBOSE=true; shift ;;
        -V|--version)         echo "midu.sh v${VERSION}"; exit 0 ;;
        -h|--help)            show_help; exit 0 ;;
        -*)                   echo -e "${RED}Opción desconocida: $1${NC}"; show_help; exit 1 ;;
        *)                    INPUT_DIR="$1"; shift ;;
    esac
done

# ── Auto-detectar modo CLI ──────────────────────────────────────────
# Si se pasó cualquier flag de procesamiento, saltar modo interactivo
if [[ -n "$MODE" || -n "$URL" || -n "$SUBTITLE_SOFT" || -n "$SUBTITLE_HARD" || -n "$SPEED" || -n "$AUDIO_INPUT" || ${#CONCAT_FILES[@]} -gt 0 || "$WATCH_MODE" == true || "$MODE" == "cut" || "$MODE" == "convert" ]]; then
    INTERACTIVE=false
fi

# ── Aplicar preset de red social ──────────────────────────────────────

apply_social_preset() {
    local platform="$1"
    case "$platform" in
        whatsapp)
            RESOLUTION="720"
            MAX_SIZE="1"
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="128k"
            PRESET="web"
            ;;
        telegram)
            RESOLUTION="1080"
            MAX_SIZE="2"
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="128k"
            PRESET="default"
            ;;
        instagram)
            RESOLUTION="1080"
            MAX_SIZE="0.5"
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="128k"
            PRESET="default"
            ;;
        tiktok)
            RESOLUTION="1080"
            MAX_SIZE="0.5"
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="128k"
            PRESET="default"
            ;;
        youtube)
            RESOLUTION="original"
            MAX_SIZE=""
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="192k"
            PRESET="archive"
            ;;
        twitter|tw)
            RESOLUTION="720"
            MAX_SIZE="0.5"
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="128k"
            PRESET="web"
            ;;
        facebook|fb)
            RESOLUTION="1080"
            MAX_SIZE="1"
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="128k"
            PRESET="default"
            ;;
        *)
            echo -e "${RED}Red social desconocida: $platform${NC}"
            echo "  Disponibles: whatsapp|telegram|instagram|tiktok|youtube|twitter|facebook"
            exit 1
            ;;
    esac
}

if [[ -n "$SOCIAL" ]]; then
    apply_social_preset "$SOCIAL"
fi

# ── Convertir GB a MB internamente ────────────────────────────────────
# MAX_SIZE se guarda en GB para el usuario, pero internamente se usa MB

MAX_SIZE_MB=""
if [[ -n "$MAX_SIZE" ]]; then
    # Si tiene punto, es decimal (ej: 0.5GB = 512MB)
    if [[ "$MAX_SIZE" == *.* ]]; then
        MAX_SIZE_MB=$(echo "$MAX_SIZE * 1024" | bc 2>/dev/null || python3 -c "print(int(float('$MAX_SIZE') * 1024))")
    else
        MAX_SIZE_MB=$((MAX_SIZE * 1024))
    fi
fi

# ── Detectar GPU ──────────────────────────────────────────────────────

detect_gpu() {
    if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null 2>&1; then
        echo "nvenc"
    elif command -v vainfo &>/dev/null 2>&1; then
        echo "vaapi"
    else
        echo "cpu"
    fi
}

GPU=$(detect_gpu)

# ── Verificar dependencias ────────────────────────────────────────────

if ! command -v ffmpeg &>/dev/null; then
    echo -e "${RED}ERROR: ffmpeg no está instalado${NC}"
    echo "  Alpine: apk add ffmpeg"
    echo "  Ubuntu: sudo apt install ffmpeg"
    exit 1
fi

if ! command -v ffprobe &>/dev/null; then
    echo -e "${RED}ERROR: ffprobe no está instalado${NC}"
    exit 1
fi

if [[ "$MODE" == "download" || "$MODE" == "audio-only" ]] && ! command -v yt-dlp &>/dev/null; then
    echo -e "${RED}ERROR: yt-dlp no está instalado${NC}"
    echo "  pip install yt-dlp"
    echo "  https://github.com/yt-dlp/yt-dlp"
    exit 1
fi

if ! ffmpeg -hide_banner -encoders 2>/dev/null | grep -q "libx264"; then
    echo -e "${YELLOW}ADVERTENCIA: ffmpeg no tiene soporte libx264${NC}"
fi

# ── Funciones auxiliares ──────────────────────────────────────────────

time_to_seconds() {
    local t="$1"
    if [[ -z "$t" ]]; then
        echo "0"
        return
    fi
    # Si es solo un número, son segundos
    if [[ "$t" =~ ^[0-9]+$ ]]; then
        echo "$t"
        return
    fi
    # Formato HH:MM:SS o MM:SS
    local hours=0 mins=0 secs=0
    local IFS=':'
    read -ra time_parts <<< "$t"
    case ${#time_parts[@]} in
        3) hours=${time_parts[0]}; mins=${time_parts[1]}; secs=${time_parts[2]} ;;
        2) mins=${time_parts[0]}; secs=${time_parts[1]} ;;
        1) secs=${time_parts[0]} ;;
    esac
    echo $((hours * 3600 + mins * 60 + secs))
}

get_resolution_filter() {
    case "$1" in
        original) echo "" ;;
        4k|2160)   echo "scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2" ;;
        1440)      echo "scale=2560:1440:force_original_aspect_ratio=decrease,pad=2560:1440:(ow-iw)/2:(oh-ih)/2" ;;
        1080)      echo "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" ;;
        720)       echo "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" ;;
        480)       echo "scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2" ;;
        360)       echo "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2" ;;
        *)         echo -e "${RED}Resolución desconocida: $1${NC}"; exit 1 ;;
    esac
}

get_audio_args() {
    local codec="$1"
    local bitrate="$2"
    case "$codec" in
        copy)    echo "-c:a copy" ;;
        aac)     echo "-c:a aac -b:a $bitrate" ;;
        opus)    echo "-c:a libopus -b:a $bitrate" ;;
        mp3)     echo "-c:a libmp3lame -b:a $bitrate" ;;
        flac)    echo "-c:a flac" ;;
        vorbis)  echo "-c:a libvorbis -b:a $bitrate" ;;
        ac3)     echo "-c:a ac3 -b:a $bitrate" ;;
        eac3)    echo "-c:a eac3 -b:a $bitrate" ;;
        pcm_s16le) echo "-c:a pcm_s16le" ;;
        pcm_s24le) echo "-c:a pcm_s24le" ;;
        *)       echo -e "${RED}Códec desconocido: $codec${NC}"; exit 1 ;;
    esac
}

format_time() {
    printf "%02d:%02d:%02d" $(($1/3600)) $(($1%3600/60)) $(($1%60))
}

get_duration() {
    ffprobe -v error -show_entries format=duration -of csv=p=0 "$1" 2>/dev/null | cut -d. -f1
}

can_remux() {
    local file="$1"
    local v_codec a_codec
    v_codec=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$file" 2>/dev/null)
    a_codec=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$file" 2>/dev/null)
    [[ "$v_codec" == "h264" && "$a_codec" == "aac" ]]
}

# ── Cortar vídeo (lossless) ──────────────────────────────────────────

cut_video() {
    local file="$1"
    local output_dir="$2"

    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_cut.$ext"

    local ffmpeg_args=(-y)

    if [[ -n "$START_TIME" ]]; then
        ffmpeg_args+=(-ss "$START_TIME")
    fi

    ffmpeg_args+=(-i "$file")

    if [[ -n "$END_TIME" ]]; then
        if [[ -n "$START_TIME" ]]; then
            local start_secs=$(time_to_seconds "$START_TIME")
            local end_secs=$(time_to_seconds "$END_TIME")
            local seg_duration=$((end_secs - start_secs))
            [[ "$seg_duration" -gt 0 ]] && ffmpeg_args+=(-t "$seg_duration")
        else
            ffmpeg_args+=(-to "$END_TIME")
        fi
    fi

    ffmpeg_args+=(-c copy -movflags +faststart "$output_file")

    mkdir -p "$output_dir"

    echo -e "${BOLD}Cortando:${NC} $file → $output_file"

    if ffmpeg "${ffmpeg_args[@]}" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Corte completado:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al cortar${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Descargar vídeo de URL ────────────────────────────────────────────

download_video() {
    local url="$1"
    local output_dir="$2"

    echo -e "${BOLD}Descargando:${NC} $url"
    mkdir -p "$output_dir"

    local ytdlp_args=(-f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best")

    # Descarga parcial
    if [[ -n "$DOWNLOAD_START" ]]; then
        ytdlp_args+=(--download-sections "*${DOWNLOAD_START}-")
        [[ -n "$DOWNLOAD_END" ]] && ytdlp_args[-1]="*${DOWNLOAD_START}-${DOWNLOAD_END}"
    fi

    ytdlp_args+=(--merge-output-format mp4 -o "$output_dir/%(title)s.%(ext)s" "$url")

    if [[ "$VERBOSE" == true ]]; then
        yt-dlp "${ytdlp_args[@]}"
    else
        yt-dlp "${ytdlp_args[@]}" 2>&1 | tail -5
    fi

    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}Descarga completada${NC}"
    else
        echo -e "${RED}Error en la descarga${NC}"
        return 1
    fi
}

# ── Extraer solo audio ────────────────────────────────────────────────

extract_audio() {
    local input="$1"
    local output_dir="$2"
    local out_fmt="${OUTPUT_FORMAT:-mp3}"

    local filename
    filename=$(basename "$input")
    filename="${filename%.*}"
    local output_file="$output_dir/$filename.$out_fmt"

    echo -e "${BOLD}Extrayendo audio:${NC} $input → $output_file"

    mkdir -p "$output_dir"

    local ffmpeg_args=(-y -i "$input")

    # Agregar corte si se especificó
    if [[ -n "$START_TIME" ]]; then
        ffmpeg_args+=(-ss "$START_TIME")
    fi
    if [[ -n "$END_TIME" ]]; then
        local start_secs=$(time_to_seconds "$START_TIME")
        local end_secs=$(time_to_seconds "$END_TIME")
        local duration_secs=$(get_duration "$input")
        if [[ "$end_secs" -gt 0 && "$start_secs" -ge 0 ]]; then
            local seg_duration=$((end_secs - start_secs))
            [[ "$seg_duration" -gt 0 ]] && ffmpeg_args+=(-t "$seg_duration")
        fi
    fi

    case "$out_fmt" in
        mp3)  ffmpeg_args+=(-vn -c:a libmp3lame -b:a "$AUDIO_BITRATE") ;;
        m4a)  ffmpeg_args+=(-vn -c:a aac -b:a "$AUDIO_BITRATE") ;;
        flac) ffmpeg_args+=(-vn -c:a flac) ;;
        wav)  ffmpeg_args+=(-vn -c:a pcm_s16le) ;;
        opus) ffmpeg_args+=(-vn -c:a libopus -b:a "$AUDIO_BITRATE") ;;
        *)    ffmpeg_args+=(-vn -c:a copy) ;;
    esac

    ffmpeg_args+=("$output_file")

    if ffmpeg "${ffmpeg_args[@]}" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Audio extraído:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error extrayendo audio${NC}"
        return 1
    fi
}

# ── Mezclar audio con vídeo ──────────────────────────────────────────

merge_audio() {
    local video="$1"
    local audio="$2"
    local output_dir="$3"

    local video_name
    video_name=$(basename "$video")
    video_name="${video_name%.*}"
    local audio_name
    audio_name=$(basename "$audio")
    audio_name="${audio_name%.*}"
    local output_file="$output_dir/${video_name}_${audio_name}.mp4"

    echo -e "${BOLD}Mezclando:${NC} $video + $audio → $output_file"

    mkdir -p "$output_dir"

    local ffmpeg_args=(-y -i "$video" -i "$audio")

    # Agregar corte si se especificó
    if [[ -n "$START_TIME" ]]; then
        ffmpeg_args=(-y -i "$video" -ss "$START_TIME" -i "$audio")
    fi

    ffmpeg_args+=(-map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a "$AUDIO_BITRATE")

    if [[ -n "$END_TIME" ]]; then
        local start_secs=$(time_to_seconds "$START_TIME")
        local end_secs=$(time_to_seconds "$END_TIME")
        local seg_duration=$((end_secs - start_secs))
        [[ "$seg_duration" -gt 0 ]] && ffmpeg_args+=(-t "$seg_duration")
    fi

    ffmpeg_args+=(-shortest -movflags +faststart "$output_file")

    if ffmpeg "${ffmpeg_args[@]}" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Mezcla completada:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error mezclando audio y vídeo${NC}"
        return 1
    fi
}

# ── Concatenar vídeos ────────────────────────────────────────────────

concat_videos() {
    local output_dir="$1"
    shift
    local files=("$@")

    if [[ ${#files[@]} -lt 2 ]]; then
        echo -e "${RED}ERROR: Se necesitan al menos2 archivos para concatenar${NC}"
        return 1
    fi

    local list_file
    list_file=$(mktemp /tmp/concat_list_XXXXXX.txt)
    rm -f "$list_file"

    for f in "${files[@]}"; do
        if [[ ! -f "$f" ]]; then
            echo -e "${RED}ERROR: Archivo no encontrado: $f${NC}"
            rm -f "$list_file"
            return 1
        fi
        echo "file '$f'" >> "$list_file"
    done

    local basename
    basename=$(basename "${files[0]}")
    basename="${basename%.*}"
    local output_file="$output_dir/${basename}_concat.mp4"

    echo -e "${BOLD}Concatenando:${NC} ${#files[@]} archivos → $output_file"
    mkdir -p "$output_dir"

    if ffmpeg -y -f concat -safe0 -i "$list_file" -c copy -movflags +faststart "$output_file"2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size /1024 /1024))
        echo -e "${GREEN}Concatenación completada:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error en la concatenación${NC}"
        rm -f "$list_file"
        return 1
    fi
    rm -f "$list_file"
}

# ── Convertir a GIF animado ─────────────────────────────────────────

gif_video() {
    local file="$1"
    local output_dir="$2"
    local filename
    filename=$(basename "$file")
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}.gif"
    local fps_val="${GIF_FPS:-10}"
    local scale_val="${GIF_SCALE:-480:-1}"

    mkdir -p "$output_dir"
    echo -e "${BOLD}Convirtiendo a GIF:${NC} $file → $output_file"

    local vf="fps=$fps_val,scale=$scale_val:flags=lanczos"
    local ffmpeg_args=(-y -i "$file" -vf "$vf" -loop 0 "$output_file")

    if ffmpeg "${ffmpeg_args[@]}" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        local out_kb=$((out_size / 1024))
        echo -e "${GREEN}GIF creado:${NC} $output_file (${out_kb}KB)"
    else
        echo -e "${RED}Error al crear GIF${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Extraer thumbnail (frame) ───────────────────────────────────────

thumbnail_video() {
    local file="$1"
    local output_dir="$2"
    local filename
    filename=$(basename "$file")
    filename="${filename%.*}"
    local timestamp="${THUMBNAIL_TIME:-00:00:01}"
    local output_file="$output_dir/${filename}_thumb.png"

    mkdir -p "$output_dir"
    echo -e "${BOLD}Extrayendo thumbnail:${NC} $file @ $timestamp"

    if ffmpeg -y -ss "$timestamp" -i "$file" -vframes 1 -q:v 2 "$output_file" 2>/dev/null; then
        echo -e "${GREEN}Thumbnail creado:${NC} $output_file"
    else
        echo -e "${RED}Error al extraer thumbnail${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Info del vídeo ──────────────────────────────────────────────────

info_video() {
    local file="$1"
    echo -e "${BOLD}═══════════════════════════════════════${NC}"
    echo -e "${BOLD} Info: $(basename "$file")${NC}"
    echo -e "${BOLD}═══════════════════════════════════════${NC}"

    local size
    size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo 0)
    local size_mb=$((size / 1024 / 1024))
    echo -e "  Tamaño:      ${CYAN}${size_mb}MB${NC}"

    local duration
    duration=$(get_duration "$file")
    if [[ -n "$duration" && "$duration" =~ ^[0-9]+$ ]]; then
        local dur_fmt
        dur_fmt=$(format_time "$duration")
        echo -e "  Duración:    ${CYAN}${dur_fmt}${NC}"
    fi

    # Resolución
    local res
    res=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$file" 2>/dev/null)
    if [[ -n "$res" ]]; then
        local w h
        w=$(echo "$res" | cut -d, -f1)
        h=$(echo "$res" | cut -d, -f2)
        echo -e "  Resolución:  ${CYAN}${w}x${h}${NC}"
    fi

    # Framerate
    local fps
    fps=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$file" 2>/dev/null | head -1)
    if [[ -n "$fps" ]]; then
        echo -e "  FPS:         ${CYAN}${fps}${NC}"
    fi

    # Códecs
    local v_codec
    v_codec=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$file" 2>/dev/null)
    echo -e "  Vídeo:       ${CYAN}${v_codec:-N/A}${NC}"

    local a_codec
    a_codec=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$file" 2>/dev/null)
    echo -e "  Audio:       ${CYAN}${a_codec:-N/A}${NC}"

    # Bitrate
    local bitrate
    bitrate=$(ffprobe -v error -show_entries format=bit_rate -of csv=p=0 "$file" 2>/dev/null)
    if [[ -n "$bitrate" && "$bitrate" != "N/A" ]]; then
        local bitrate_kbps=$((bitrate / 1000))
        echo -e "  Bitrate:     ${CYAN}${bitrate_kbps}kbps${NC}"
    fi

    echo -e "${BOLD}═══════════════════════════════════════${NC}"
}

# ── Rotar vídeo ─────────────────────────────────────────────────────

rotate_video() {
    local file="$1"
    local output_dir="$2"
    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_rot${ROTATE_DEGREES}.$ext"

    mkdir -p "$output_dir"
    echo -e "${BOLD}Rotando ${ROTATE_DEGREES}°:${NC} $file → $output_file"

    local transpose_val
    case "$ROTATE_DEGREES" in
        90)  transpose_val=1 ;;
        180) transpose_val=2 ;;
        270) transpose_val=3 ;;
        *)   echo -e "${RED}Grados no válidos: $ROTATE_DEGREES (usa 90, 180 o 270)${NC}"; return 1 ;;
    esac

    if ffmpeg -y -i "$file" -vf "transpose=$transpose_val" -c:a copy "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Rotación completada:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al rotar${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Crop vídeo ──────────────────────────────────────────────────────

crop_video() {
    local file="$1"
    local output_dir="$2"
    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_cropped.$ext"

    mkdir -p "$output_dir"
    echo -e "${BOLD}Recortando ${CROP_SIZE}:${NC} $file → $output_file"

    local w h
    w=$(echo "$CROP_SIZE" | cut -d: -f1)
    h=$(echo "$CROP_SIZE" | cut -d: -f2)

    if ffmpeg -y -i "$file" -vf "crop=${w}:${h}" -c:a copy "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Crop completado:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al recortar${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Fade in/out ─────────────────────────────────────────────────────

fade_video() {
    local file="$1"
    local output_dir="$2"
    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_fade.$ext"
    local fade_dur="${FADE_SECONDS:-1}"

    mkdir -p "$output_dir"
    echo -e "${BOLD}Aplicando fade (${fade_dur}s):${NC} $file → $output_file"

    local duration
    duration=$(get_duration "$file")
    if [[ -z "$duration" || ! "$duration" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}No se pudo obtener la duración del vídeo${NC}"
        return 1
    fi

    local fade_out_start=$((duration - fade_dur))
    [[ "$fade_out_start" -lt 0 ]] && fade_out_start=0

    if ffmpeg -y -i "$file" \
        -vf "fade=t=in:st=0:d=${fade_dur},fade=t=out:st=${fade_out_start}:d=${fade_dur}" \
        -af "afade=t=in:st=0:d=${fade_dur},afade=t=out:st=${fade_out_start}:d=${fade_dur}" \
        "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Fade aplicado:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al aplicar fade${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Normalizar audio ────────────────────────────────────────────────

normalize_video() {
    local file="$1"
    local output_dir="$2"
    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_norm.$ext"

    mkdir -p "$output_dir"
    echo -e "${BOLD}Normalizando audio:${NC} $file → $output_file"

    if ffmpeg -y -i "$file" \
        -af "loudnorm=I=-16:TP=-1.5:LRA=11" \
        -c:v copy "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Audio normalizado:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al normalizar${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Marca de agua ───────────────────────────────────────────────────

watermark_video() {
    local file="$1"
    local output_dir="$2"
    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_watermarked.$ext"

    mkdir -p "$output_dir"
    echo -e "${BOLD}Añadiendo marca de agua:${NC} $file + $WATERMARK_FILE → $output_file"

    if ffmpeg -y -i "$file" -i "$WATERMARK_FILE" \
        -filter_complex "overlay=W-w-10:H-h-10" \
        -c:a copy "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Marca de agua aplicada:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al añadir marca de agua${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Desentrelazar ───────────────────────────────────────────────────

deinterlace_video() {
    local file="$1"
    local output_dir="$2"
    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_deint.$ext"

    mkdir -p "$output_dir"
    echo -e "${BOLD}Desentrelazando:${NC} $file → $output_file"

    if ffmpeg -y -i "$file" \
        -vf "yadif" -c:a copy "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Desentrelazado:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al desentrelazar${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Cambiar FPS ─────────────────────────────────────────────────────

fps_video() {
    local file="$1"
    local output_dir="$2"
    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_${TARGET_FPS}fps.$ext"

    mkdir -p "$output_dir"
    echo -e "${BOLD}Cambiando a ${TARGET_FPS}fps:${NC} $file → $output_file"

    if ffmpeg -y -i "$file" \
        -vf "fps=$TARGET_FPS" -c:a copy "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}FPS cambiado:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al cambiar FPS${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Modo watch ───────────────────────────────────────────────────────

run_watch_mode() {
    local input_dir="$1"
    local output_dir="$2"

    echo -e "${BOLD}Modo watch activado:${NC} $input_dir → $output_dir"
    echo -e "${DIM}Presiona Ctrl+C para salir${NC}"
    echo ""

    mkdir -p "$output_dir"
    local marker
    marker=$(mktemp /tmp/midu_watch_XXXXXX)
    touch "$marker"

    # Procesar archivos existentes
    buscar_archivos
    if [[ $total -gt 0 ]]; then
        echo -e "${CYAN}Procesando $total archivos existentes...${NC}"
        for file in "${archivos[@]}"; do
            convertir_archivo "$file" "$OUTPUT_DIR"
        done
    fi

    echo -e "${CYAN}Esperando nuevos archivos...${NC}"

    if command -v inotifywait &>/dev/null; then
        inotifywait -m -e close_write --format '%w%f' "$input_dir" | while read -r file; do
            case "$file" in
                *.avi|*.webm|*.mkv|*.mp4|*.flv)
                    echo -e "${CYAN}Nuevo archivo detectado:${NC} $file"
                    convertir_archivo "$file" "$OUTPUT_DIR"
                    ;;
            esac
        done
    else
        while true; do
            sleep 5
            while IFS= read -r -d $'\0' file; do
                echo -e "${CYAN}Nuevo archivo detectado:${NC} $file"
                convertir_archivo "$file" "$OUTPUT_DIR"
            done < <(find "$input_dir" -maxdepth1 -type f \( -iname "*.avi" -o -iname "*.webm" -o -iname "*.mkv" -o -iname "*.mp4" -o -iname "*.flv" \) -newer "$marker" -print0)
            touch "$marker"
        done
    fi
    rm -f "$marker"
}

# ── Buscar archivos (función reutilizable) ────────────────────────────

IFS=',' read -ra EXT_ARRAY <<< "$EXTENSIONS"

buscar_archivos() {
    archivos=()
    saltados=0
    for ext in "${EXT_ARRAY[@]}"; do
        ext=$(echo "$ext" | xargs)
        while IFS= read -r -d '' file; do
            filename=$(basename "$file")
            filename="${filename%.*}"
            output_file="$OUTPUT_DIR/$filename.mp4"

            if [[ -f "$output_file" ]]; then
                out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
                if [[ "$out_size" -gt 1024 ]]; then
                    ((saltados++))
                    continue
                fi
            fi

            archivos+=("$file")
        done < <(find "$INPUT_DIR" -maxdepth 2 -type f -iname "*.$ext" -print0)
    done
    total=${#archivos[@]}
}

# ── Seleccionar archivo de vídeo ────────────────────────────────────

select_video_file() {
    local dir="$1"
    local mode_hint="${2:-}"

    IFS=',' read -ra exts <<< "$EXTENSIONS"
    local all_files=()
    for ext in "${exts[@]}"; do
        ext=$(echo "$ext" | xargs)
        while IFS= read -r -d '' f; do
            all_files+=("$f")
        done < <(find "$dir" -maxdepth 2 -type f -iname "*.$ext" -print0 2>/dev/null)
    done

    if [[ ${#all_files[@]} -eq 0 ]]; then
        echo -e "  ${YELLOW}No hay vídeos en $dir${NC}"
        return 1
    fi

    echo -e "${BOLD}  Vídeos disponibles:${NC}"
    echo ""
    local i=1
    for f in "${all_files[@]}"; do
        local name
        name=$(basename "$f")
        local size
        size=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null || echo 0)
        local size_mb=$((size / 1024 / 1024))
        printf "    ${GREEN}%2d)${NC} %s ${DIM}(%dMB)${NC}\n" "$i" "$name" "$size_mb"
        ((i++))
    done
    echo ""

    if [[ ${#all_files[@]} -eq 1 ]]; then
        echo -e "  ${DIM}Solo hay 1 archivo, se selecciona automáticamente${NC}"
        SELECTED_FILE="${all_files[0]}"
        echo -e "  → ${CYAN}$(basename "$SELECTED_FILE")${NC}"
        echo ""
        return 0
    fi

    read -rp "  → Selecciona [1-${#all_files[@]}]: " choice
    if [[ -z "$choice" || "$choice" -lt 1 || "$choice" -gt ${#all_files[@]} ]]; then
        echo -e "${RED}Selección no válida${NC}"
        return 1
    fi

    SELECTED_FILE="${all_files[$((choice - 1))]}"
    echo -e "  → ${CYAN}$(basename "$SELECTED_FILE")${NC}"
    echo ""
    return 0
}

# ── Pedir nombre de salida ─────────────────────────────────────────

ask_output_name() {
    local default_name="$1"
    local ext="$2"

    echo -e "${BOLD}  Nombre de salida${NC} ${DIM}(Enter = ${default_name}.${ext})${NC}"
    read -rp "  → $default_name : " custom_name
    if [[ -n "$custom_name" ]]; then
        # Quitar extensión si la puso
        custom_name="${custom_name%.*}"
        OUTPUT_NAME="$custom_name"
    else
        OUTPUT_NAME="$default_name"
    fi
    echo ""
}

# ── Modo interactivo ──────────────────────────────────────────────────

if [[ "$INTERACTIVE" == true && -t 0 ]]; then
    echo ""
    echo -e "${BOLD}═══════════════════════════════════════${NC}"
    echo -e "${BOLD} midu.sh v${VERSION}${NC}"
    echo -e "${BOLD}═══════════════════════════════════════${NC}"
    echo ""

    # ── ¿Usar config guardada? ────────────────────────────────────────
    if [[ -f "$CONF_FILE" ]] && command -v jq &>/dev/null; then
        echo -e "  ${YELLOW}Configuración guardada encontrada${NC}"
        read -rp "  ¿Usarla? [S/n]: " val
        if [[ ! "$val" =~ ^[Nn] ]]; then
            load_config
            echo -e "  ${GREEN}Configuración global cargada${NC}"
            echo ""
        fi
    fi

    # ══════════════════════════════════════════════════════════════════
    #  PASO 1: Seleccionar modo
    # ══════════════════════════════════════════════════════════════════
    echo -e "${BOLD}  ¿Qué quieres hacer?${NC}"
    echo ""
    echo -e "    ${GREEN} 1)${NC} Descargar vídeo       ${DIM}— YouTube, Kick, Twitch${NC}"
    echo -e "    ${GREEN} 2)${NC} Cortar vídeo          ${DIM}— Sin perder calidad${NC}"
    echo -e "    ${GREEN} 3)${NC} Convertir/comprimir   ${DIM}— Ajustar tamaño y calidad${NC}"
    echo -e "    ${GREEN} 4)${NC} Crear GIF             ${DIM}— Animación a partir del vídeo${NC}"
    echo -e "    ${GREEN} 5)${NC} Captura (thumbnail)   ${DIM}— Screenshot del vídeo${NC}"
    echo -e "    ${GREEN} 6)${NC} Info del vídeo        ${DIM}— Duración, codecs, resolución${NC}"
    echo -e "    ${GREEN} 7)${NC} Rotar vídeo           ${DIM}— 90°, 180° o 270°${NC}"
    echo -e "    ${GREEN} 8)${NC} Recortar (crop)       ${DIM}— Cortar a tamaño específico${NC}"
    echo -e "    ${GREEN} 9)${NC} Fade in/out           ${DIM}— Aparecer/desaparecer${NC}"
    echo -e "    ${GREEN}10)${NC} Normalizar audio      ${DIM}— Volumen parejo${NC}"
    echo -e "    ${GREEN}11)${NC} Marca de agua         ${DIM}— Poner imagen encima${NC}"
    echo -e "    ${GREEN}12)${NC} Desentrelazar         ${DIM}— Quitar rayas de TV vieja${NC}"
    echo -e "    ${GREEN}13)${NC} Cambiar FPS           ${DIM}— Frames por segundo${NC}"
    echo -e "    ${GREEN}14)${NC} Cambiar velocidad     ${DIM}— Más rápido o lento${NC}"
    echo -e "    ${GREEN}15)${NC} Subtítulos            ${DIM}— Embeber o quemar${NC}"
    echo -e "    ${GREEN}16)${NC} Unir vídeos           ${DIM}— Concatenar varios archivos${NC}"
    echo -e "    ${GREEN}17)${NC} Extraer audio         ${DIM}— Solo audio del vídeo${NC}"
    echo ""
    read -rp "  → Selecciona [1-17]: " mode_val
    echo ""

    case "$mode_val" in
        1)  MODE="download" ;;
        2)  MODE="cut" ;;
        3)  MODE="convert" ;;
        4)  MODE="gif" ;;
        5)  MODE="thumbnail" ;;
        6)  MODE="info" ;;
        7)  MODE="rotate" ;;
        8)  MODE="crop" ;;
        9)  MODE="fade" ;;
        10) MODE="normalize" ;;
        11) MODE="watermark" ;;
        12) MODE="deinterlace" ;;
        13) MODE="fps" ;;
        14) MODE="speed" ;;
        15) MODE="subtitles" ;;
        16) MODE="concat" ;;
        17) MODE="audio-only" ;;
        *)  echo -e "${RED}Opción no válida${NC}"; exit 1 ;;
    esac

    # ── Cargar config del modo seleccionado ─────────────────────────────
    if [[ -f "$CONF_FILE" ]] && command -v jq &>/dev/null; then
        load_config "$MODE"
        echo -e "  ${DIM}Configuración de $MODE cargada${NC}"
        echo ""
    fi

    # ══════════════════════════════════════════════════════════════════
    #  PASO 2: Directorio de entrada y selección de archivo
    # ══════════════════════════════════════════════════════════════════

    case "$MODE" in
        # -- Descarga: solo pide URL --
        download)
            echo -e "${BOLD}  URL a descargar${NC}"
            echo -e "  ${DIM}YouTube, Kick, Twitch, etc.${NC}"
            read -rp "  → URL: " URL
            [[ -z "$URL" ]] && { echo -e "${RED}Se requiere URL${NC}"; exit 1; }
            echo ""
            echo -e "${BOLD}  Descarga parcial (opcional)${NC}"
            echo -e "  ${DIM}Deja vacío para descargar todo${NC}"
            read -rp "  → Inicio (ej: 00:05:00): " DOWNLOAD_START
            read -rp "  → Fin (ej: 00:10:00):    " DOWNLOAD_END
            echo ""
            ;;

        # -- Concat: pide lista de archivos --
        concat)
            echo -e "${BOLD}  Archivos a unir${NC}"
            echo -e "  ${DIM}Escribe las rutas separadas por espacio${NC}"
            echo -e "  ${DIM}Ejemplo: /videos/a.mkv /videos/b.mkv /videos/c.mkv${NC}"
            read -rp "  → Archivos: " -a CONCAT_FILES
            [[ ${#CONCAT_FILES[@]} -lt 2 ]] && { echo -e "${RED}Se necesitan al menos 2 archivos${NC}"; exit 1; }
            echo ""
            ;;

        # -- Todos los demás modos: elegir directorio y archivo --
        *)
            echo -e "${BOLD}  Directorio de entrada${NC}"
            echo -e "  ${DIM}¿Dónde están los vídeos?${NC}"
            read -rp "  → $INPUT_DIR : " val
            [[ -n "$val" ]] && INPUT_DIR="$val"

            if [[ ! -d "$INPUT_DIR" ]]; then
                echo -e "  ${RED}El directorio no existe${NC}"
                read -rp "  ¿Quieres crearlo? [S/n]: " val
                if [[ ! "$val" =~ ^[Nn] ]]; then
                    mkdir -p "$INPUT_DIR" 2>/dev/null || { echo -e "${RED}No se pudo crear${NC}"; exit 1; }
                    echo -e "  ${GREEN}Creado: $INPUT_DIR${NC}"
                else
                    exit 0
                fi
            fi
            echo ""

            # Seleccionar archivo específico
            echo -e "${BOLD}  Selecciona el vídeo${NC}"
            if ! select_video_file "$INPUT_DIR" "$MODE"; then
                exit 1
            fi
            ;;
    esac

    # ══════════════════════════════════════════════════════════════════
    #  PASO 3: Directorio de salida y nombre
    # ══════════════════════════════════════════════════════════════════

    case "$MODE" in
        info|concat|download)
            # Estos modos no necesitan configurar salida
            ;;

        *)
            echo -e "${BOLD}  Directorio de salida${NC}"
            read -rp "  → $OUTPUT_DIR : " val
            [[ -n "$val" ]] && OUTPUT_DIR="$val"

            if [[ ! -d "$OUTPUT_DIR" ]]; then
                mkdir -p "$OUTPUT_DIR" 2>/dev/null && echo -e "  ${GREEN}Creado: $OUTPUT_DIR${NC}" || echo -e "  ${RED}No se pudo crear${NC}"
            fi
            echo ""

            # Nombre de salida personalizado (excepto info)
            if [[ -n "$SELECTED_FILE" ]]; then
                local base_name
                base_name=$(basename "$SELECTED_FILE")
                base_name="${base_name%.*}"
                ask_output_name "$base_name" "$(basename "$SELECTED_FILE" | sed 's/.*\.//')"
            fi
            ;;
    esac

    # ══════════════════════════════════════════════════════════════════
    #  PASO 4: Parámetros específicos de cada modo
    # ══════════════════════════════════════════════════════════════════

    case "$MODE" in

        cut)
            echo -e "${BOLD}  Tiempo de corte${NC}"
            echo -e "  ${DIM}Formato: HH:MM:SS o MM:SS o segundos${NC}"
            echo -e "  ${DIM}Deja vacío para cortar desde el inicio o hasta el final${NC}"
            read -rp "  → Tiempo inicio: " START_TIME
            read -rp "  → Tiempo fin:    " END_TIME
            [[ -z "$START_TIME" && -z "$END_TIME" ]] && { echo -e "${RED}Indica al menos un tiempo${NC}"; exit 1; }
            echo ""
            ;;

        convert)
            echo -e "${BOLD}  Red social (atajo)${NC}"
            echo -e "    ${GREEN}0)${NC} Ninguna — Manual"
            echo -e "    ${GREEN}1)${NC} WhatsApp  ${GREEN}2)${NC} Telegram  ${GREEN}3)${NC} Instagram"
            echo -e "    ${GREEN}4)${NC} TikTok    ${GREEN}5)${NC} YouTube   ${GREEN}6)${NC} Twitter"
            echo -e "    ${GREEN}7)${NC} Facebook"
            read -rp "  → [0-7] (default: 0): " val
            case "$val" in
                1) apply_social_preset "whatsapp" ;;
                2) apply_social_preset "telegram" ;;
                3) apply_social_preset "instagram" ;;
                4) apply_social_preset "tiktok" ;;
                5) apply_social_preset "youtube" ;;
                6) apply_social_preset "twitter" ;;
                7) apply_social_preset "facebook" ;;
            esac
            echo ""

            echo -e "${BOLD}  Preset de calidad${NC}"
            echo -e "    ${GREEN}1)${NC} ultrafast — Muy rápido, poco peso"
            echo -e "    ${GREEN}2)${NC} web       — Rápido, buen balance"
            echo -e "    ${GREEN}3)${NC} default   — Equilibrado"
            echo -e "    ${GREEN}4)${NC} archive   — Alta calidad"
            echo -e "    ${GREEN}5)${NC} quality   — Máxima calidad"
            read -rp "  → [1-5] (default: 3): " val
            case "$val" in
                1) PRESET="ultrafast" ;;
                2) PRESET="web" ;;
                4) PRESET="archive" ;;
                5) PRESET="quality" ;;
                3|"") PRESET="default" ;;
            esac
            echo ""

            echo -e "${BOLD}  Resolución${NC}"
            echo -e "    ${GREEN}1)${NC} original  ${GREEN}2)${NC} 4k  ${GREEN}3)${NC} 1080  ${GREEN}4)${NC} 720  ${GREEN}5)${NC} 480  ${GREEN}6)${NC} 360"
            read -rp "  → [1-6] (default: 1): " val
            case "$val" in
                1|"") RESOLUTION="original" ;;
                2) RESOLUTION="4k" ;;
                3) RESOLUTION="1080" ;;
                4) RESOLUTION="720" ;;
                5) RESOLUTION="480" ;;
                6) RESOLUTION="360" ;;
            esac
            echo ""

            echo -e "${BOLD}  Tamaño máximo en GB${NC} ${DIM}(vacío = sin límite)${NC}"
            read -rp "  → ${MAX_SIZE}GB : " val
            [[ -n "$val" ]] && MAX_SIZE="$val"
            echo ""
            ;;

        gif)
            echo -e "${BOLD}  FPS del GIF${NC}"
            echo -e "  ${DIM}Más FPS = más suave pero más pesado${NC}"
            echo -e "    ${GREEN}1)${NC} 10 FPS — Ligero (default)"
            echo -e "    ${GREEN}2)${NC} 15 FPS — Normal"
            echo -e "    ${GREEN}3)${NC} 25 FPS — Suave"
            read -rp "  → [1-3] o número personalizado (default: 10): " val
            case "$val" in
                1|"") GIF_FPS=10 ;;
                2) GIF_FPS=15 ;;
                3) GIF_FPS=25 ;;
                *) [[ -n "$val" ]] && GIF_FPS="$val" ;;
            esac
            echo ""

            echo -e "${BOLD}  Tamaño del GIF${NC}"
            echo -e "    ${GREEN}1)${NC} 320px — Pequeño (default)"
            echo -e "    ${GREEN}2)${NC} 480px — Mediano"
            echo -e "    ${GREEN}3)${NC} 640px — Grande"
            read -rp "  → [1-3] o WxH personalizado (default: 480): " val
            case "$val" in
                1) GIF_SCALE="320:-1" ;;
                2|"") GIF_SCALE="480:-1" ;;
                3) GIF_SCALE="640:-1" ;;
                *) [[ -n "$val" ]] && GIF_SCALE="$val" ;;
            esac
            echo ""
            ;;

        thumbnail)
            echo -e "${BOLD}  Timestamp del frame${NC}"
            echo -e "  ${DIM}En qué momento del vídeo quieres la captura${NC}"
            echo -e "    ${GREEN}1)${NC} 00:00:01 — Primer segundo (default)"
            echo -e "    ${GREEN}2)${NC} 00:00:05 — 5 segundos"
            echo -e "    ${GREEN}3)${NC} Mitad del vídeo"
            read -rp "  → [1-3] o tiempo personalizado (HH:MM:SS): " val
            case "$val" in
                1|"") THUMBNAIL_TIME="00:00:01" ;;
                2) THUMBNAIL_TIME="00:00:05" ;;
                3)
                    dur=$(get_duration "$SELECTED_FILE")
                    if [[ -n "$dur" && "$dur" =~ ^[0-9]+$ ]]; then
                        mid=$((dur / 2))
                        THUMBNAIL_TIME=$(format_time "$mid")
                    else
                        THUMBNAIL_TIME="00:00:05"
                    fi
                    ;;
                *) [[ -n "$val" ]] && THUMBNAIL_TIME="$val" ;;
            esac
            echo ""
            ;;

        rotate)
            echo -e "${BOLD}  ¿Cuánto quieres girar el vídeo?${NC}"
            echo -e "    ${GREEN}1)${NC} 90°  — Girar a la derecha"
            echo -e "    ${GREEN}2)${NC} 180° — Dar la vuelta"
            echo -e "    ${GREEN}3)${NC} 270° — Girar a la izquierda"
            read -rp "  → [1-3]: " val
            case "$val" in
                1) ROTATE_DEGREES=90 ;;
                2) ROTATE_DEGREES=180 ;;
                3) ROTATE_DEGREES=270 ;;
                *) [[ -n "$val" ]] && ROTATE_DEGREES="$val" ;;
            esac
            [[ -z "$ROTATE_DEGREES" ]] && { echo -e "${RED}Selecciona grados${NC}"; exit 1; }
            echo ""
            ;;

        crop)
            echo -e "${BOLD}  Tamaño de recorte (Ancho:Alto)${NC}"
            echo -e "  ${DIM}Ejemplo: 640:480 = recortar a 640x480 píxeles${NC}"
            echo -e "  ${DIM}El vídeo se recortará desde el centro${NC}"
            read -rp "  → W:H: " CROP_SIZE
            [[ -z "$CROP_SIZE" ]] && { echo -e "${RED}Indica el tamaño${NC}"; exit 1; }
            echo ""
            ;;

        fade)
            echo -e "${BOLD}  Duración del efecto fade${NC}"
            echo -e "  ${DIM}Cuántos segundos dura el aparecer y desaparecer${NC}"
            echo -e "    ${GREEN}1)${NC} 0.5s — Rápido"
            echo -e "    ${GREEN}2)${NC} 1s   — Normal"
            echo -e "    ${GREEN}3)${NC} 2s   — Lento"
            read -rp "  → [1-3] o segundos personalizados (default: 1): " val
            case "$val" in
                1) FADE_SECONDS=0.5 ;;
                2|"") FADE_SECONDS=1 ;;
                3) FADE_SECONDS=2 ;;
                *) [[ -n "$val" ]] && FADE_SECONDS="$val" ;;
            esac
            echo ""
            ;;

        watermark)
            echo -e "${BOLD}  Imagen de marca de agua${NC}"
            echo -e "  ${DIM}Ruta completa del archivo PNG o JPG${NC}"
            read -rp "  → Ruta: " WATERMARK_FILE
            [[ -z "$WATERMARK_FILE" || ! -f "$WATERMARK_FILE" ]] && { echo -e "${RED}Archivo no encontrado${NC}"; exit 1; }
            echo ""
            ;;

        fps)
            echo -e "${BOLD}  Frames por segundo objetivo${NC}"
            echo -e "  ${DIM}Más FPS = vídeo más suave${NC}"
            echo -e "    ${GREEN}1)${NC} 24 FPS — Cine"
            echo -e "    ${GREEN}2)${NC} 30 FPS — Estándar"
            echo -e "    ${GREEN}3)${NC} 60 FPS — Suave (gaming)"
            echo -e "    ${GREEN}4)${NC} 120 FPS — Muy suave"
            read -rp "  → [1-4] o número personalizado: " val
            case "$val" in
                1) TARGET_FPS=24 ;;
                2) TARGET_FPS=30 ;;
                3) TARGET_FPS=60 ;;
                4) TARGET_FPS=120 ;;
                *) [[ -n "$val" ]] && TARGET_FPS="$val" ;;
            esac
            [[ -z "$TARGET_FPS" ]] && { echo -e "${RED}Indica los FPS${NC}"; exit 1; }
            echo ""
            ;;

        speed)
            echo -e "${BOLD}  Velocidad del vídeo${NC}"
            echo -e "    ${GREEN}1)${NC} 0.25x — Muy lento"
            echo -e "    ${GREEN}2)${NC} 0.5x  — Mitad"
            echo -e "    ${GREEN}3)${NC} 0.75x — Un poco lento"
            echo -e "    ${GREEN}4)${NC} 1.5x  — Un poco rápido"
            echo -e "    ${GREEN}5)${NC} 2x    — Doble"
            echo -e "    ${GREEN}6)${NC} 4x    — Cuádruple"
            read -rp "  → [1-6] o factor personalizado: " val
            case "$val" in
                1) SPEED=0.25 ;;
                2) SPEED=0.5 ;;
                3) SPEED=0.75 ;;
                4) SPEED=1.5 ;;
                5) SPEED=2 ;;
                6) SPEED=4 ;;
                *) [[ -n "$val" ]] && SPEED="$val" ;;
            esac
            [[ -z "$SPEED" ]] && { echo -e "${RED}Indica la velocidad${NC}"; exit 1; }
            echo ""
            ;;

        subtitles)
            echo -e "${BOLD}  Tipo de subtítulos${NC}"
            echo -e "    ${GREEN}1)${NC} Soft — Se pueden quitar después"
            echo -e "    ${GREEN}2)${NC} Hard — Siempre visibles en el vídeo"
            read -rp "  → [1-2]: " val
            echo ""
            case "$val" in
                1)
                    echo -e "${BOLD}  Archivo de subtítulos${NC}"
                    read -rp "  → Ruta (.srt): " SUBTITLE_SOFT
                    [[ -z "$SUBTITLE_SOFT" || ! -f "$SUBTITLE_SOFT" ]] && { echo -e "${RED}Archivo no encontrado${NC}"; exit 1; }
                    ;;
                2)
                    echo -e "${BOLD}  Archivo de subtítulos${NC}"
                    read -rp "  → Ruta (.srt): " SUBTITLE_HARD
                    [[ -z "$SUBTITLE_HARD" || ! -f "$SUBTITLE_HARD" ]] && { echo -e "${RED}Archivo no encontrado${NC}"; exit 1; }
                    ;;
                *) echo -e "${RED}Opción no válida${NC}"; exit 1 ;;
            esac
            echo ""
            ;;

        audio-only)
            echo -e "${BOLD}  Formato de audio de salida${NC}"
            echo -e "    ${GREEN}1)${NC} mp3  — Compatible con todo"
            echo -e "    ${GREEN}2)${NC} m4a  — Calidad, tamaño medio"
            echo -e "    ${GREEN}3)${NC} flac — Sin pérdida, pesado"
            echo -e "    ${GREEN}4)${NC} wav  — Sin compresión"
            echo -e "    ${GREEN}5)${NC} opus — Eficiente, moderno"
            read -rp "  → [1-5] (default: 1): " val
            case "$val" in
                1|"") OUTPUT_FORMAT="mp3" ;;
                2) OUTPUT_FORMAT="m4a" ;;
                3) OUTPUT_FORMAT="flac" ;;
                4) OUTPUT_FORMAT="wav" ;;
                5) OUTPUT_FORMAT="opus" ;;
            esac
            echo ""

            echo -e "${BOLD}  Nombre del archivo de audio${NC}"
            local audio_base
            audio_base=$(basename "$SELECTED_FILE")
            audio_base="${audio_base%.*}"
            ask_output_name "$audio_base" "$OUTPUT_FORMAT"
            ;;
    esac

    # ══════════════════════════════════════════════════════════════════
    #  PASO 5: Progreso
    # ══════════════════════════════════════════════════════════════════
    if [[ "$MODE" != "info" ]]; then
        echo -e "${BOLD}  Progreso${NC}"
        echo -e "    ${GREEN}1)${NC} Resumen  — Solo resultado"
        echo -e "    ${GREEN}2)${NC} Detallado — Porcentaje y tiempo"
        read -rp "  → [1-2] (default: 1): " val
        [[ "$val" == "2" ]] && VERBOSE=true
        echo ""
    fi

    # ══════════════════════════════════════════════════════════════════
    #  PASO 6: Resumen y confirmación
    # ══════════════════════════════════════════════════════════════════
    echo -e "${BOLD}═══════════════════════════════════════${NC}"
    echo -e "${BOLD} Resumen${NC}"
    echo -e "${BOLD}═══════════════════════════════════════${NC}"

    # Nombre del modo
    local mode_name
    case "$MODE" in
        download)     mode_name="Descargar vídeo" ;;
        cut)          mode_name="Cortar vídeo" ;;
        convert)      mode_name="Convertir/comprimir" ;;
        gif)          mode_name="Crear GIF" ;;
        thumbnail)    mode_name="Captura de pantalla" ;;
        info)         mode_name="Info del vídeo" ;;
        rotate)       mode_name="Rotar vídeo" ;;
        crop)         mode_name="Recortar vídeo" ;;
        fade)         mode_name="Fade in/out" ;;
        normalize)    mode_name="Normalizar audio" ;;
        watermark)    mode_name="Marca de agua" ;;
        deinterlace)  mode_name="Desentrelazar" ;;
        fps)          mode_name="Cambiar FPS" ;;
        speed)        mode_name="Cambiar velocidad" ;;
        subtitles)    mode_name="Subtítulos" ;;
        concat)       mode_name="Unir vídeos" ;;
        audio-only)   mode_name="Extraer audio" ;;
    esac

    echo -e "  Modo:      ${CYAN}$mode_name${NC}"
    [[ -n "$URL" ]] && echo -e "  URL:       ${CYAN}$URL${NC}"
    [[ -n "$SELECTED_FILE" ]] && echo -e "  Archivo:   ${CYAN}$(basename "$SELECTED_FILE")${NC}"
    [[ -n "$OUTPUT_NAME" ]] && echo -e "  Salida:    ${CYAN}$OUTPUT_NAME${NC}"
    [[ -n "$INPUT_DIR" && "$MODE" != "download" && "$MODE" != "concat" ]] && echo -e "  Entrada:   ${CYAN}$INPUT_DIR${NC}"
    [[ -n "$OUTPUT_DIR" && "$MODE" != "info" ]] && echo -e "  Destino:   ${CYAN}$OUTPUT_DIR${NC}"
    [[ -n "$START_TIME" ]] && echo -e "  Inicio:    ${CYAN}$START_TIME${NC}"
    [[ -n "$END_TIME" ]] && echo -e "  Fin:       ${CYAN}$END_TIME${NC}"
    [[ -n "$SOCIAL" ]] && echo -e "  Social:    ${CYAN}$SOCIAL${NC}"
    [[ -n "$PRESET" && "$MODE" == "convert" ]] && echo -e "  Preset:    ${CYAN}$PRESET${NC}"
    [[ -n "$ROTATE_DEGREES" ]] && echo -e "  Rotación:  ${CYAN}${ROTATE_DEGREES}°${NC}"
    [[ -n "$CROP_SIZE" ]] && echo -e "  Crop:      ${CYAN}$CROP_SIZE${NC}"
    [[ -n "$SPEED" ]] && echo -e "  Velocidad: ${CYAN}${SPEED}x${NC}"
    [[ -n "$TARGET_FPS" ]] && echo -e "  FPS:       ${CYAN}$TARGET_FPS${NC}"
    echo -e "${BOLD}═══════════════════════════════════════${NC}"
    echo ""

    read -rp "  ¿Guardar esta configuración? [S/n]: " val
    if [[ ! "$val" =~ ^[Nn] ]]; then
        save_config "$MODE"
    fi
    echo ""

    read -rp "  ¿Empezar? [S/n]: " val
    if [[ "$val" =~ ^[Nn] ]]; then
        echo "Cancelado."
        exit 0
    fi
    echo ""
fi

# Guardar con flag -c aunque no sea interactivo
if [[ "$SAVE_CONFIG" == true && "$INTERACTIVE" == false ]]; then
    save_config "$MODE"
fi

# ── Aplicar preset de calidad ─────────────────────────────────────────

case "$PRESET" in
    ultrafast) CRF=28; ENCODE_SPEED="ultrafast" ;;
    web)       CRF=28; ENCODE_SPEED="fast" ;;
    default)   CRF=23; ENCODE_SPEED="medium" ;;
    archive)   CRF=18; ENCODE_SPEED="slow" ;;
    quality)   CRF=15; ENCODE_SPEED="veryslow" ;;
    *)         echo -e "${RED}Preset desconocido: $PRESET${NC}"; exit 1 ;;
esac

# ── Resumen (modo non-interactive) ───────────────────────────────────

if [[ "$INTERACTIVE" == false && -z "$MODE" ]]; then
    echo ""
    echo -e "${BOLD}═══════════════════════════════════════${NC}"
    echo -e "${BOLD} midu.sh v${VERSION}${NC}"
    echo -e "${BOLD}═══════════════════════════════════════${NC}"
    echo -e "  Entrada:    $INPUT_DIR"
    echo -e "  Salida:     $OUTPUT_DIR"
    [[ -n "$SOCIAL" ]] && echo -e "  Red social: $SOCIAL"
    echo -e "  Preset:     $PRESET (CRF $CRF, $ENCODE_SPEED)"
    echo -e "  Audio:      $AUDIO_CODEC ($AUDIO_BITRATE)"
    echo -e "  Resolución: $RESOLUTION"
    [[ -n "$MAX_SIZE" ]] && echo -e "  Tamaño máx: ${MAX_SIZE}GB"
    echo -e "  GPU:        $GPU"
    echo -e "  Hilos:      $MAX_THREADS"
    echo -e "  Extensiones: $EXTENSIONS"
    echo -e "${BOLD}═══════════════════════════════════════${NC}"
    echo ""
fi

# ── Ejecutar modos especiales ────────────────────────────────────────

case "$MODE" in
    download)
        if [[ -z "$URL" ]]; then
            echo -e "${RED}ERROR: Se requiere URL para descargar${NC}"
            echo "  Uso: ./midu.sh -d <URL>"
            exit 1
        fi
        download_video "$URL" "$OUTPUT_DIR"
        exit $?
        ;;
    audio-only)
        if [[ -z "$URL" ]]; then
            # Si no hay URL, extraer audio de archivos locales
            buscar_archivos
            if [[ $total -eq 0 ]]; then
                echo -e "${YELLOW}No hay archivos de audio para extraer${NC}"
                exit 0
            fi
            for file in "${archivos[@]}"; do
                extract_audio "$file" "$OUTPUT_DIR"
            done
            exit 0
        fi
        # Descargar y extraer audio
        mkdir -p "$OUTPUT_DIR"
        local_tmp="$OUTPUT_DIR/.tmp_download_$(date +%s)"
        mkdir -p "$local_tmp"
        download_video "$URL" "$local_tmp"
        downloaded=$(find "$local_tmp" -type f \( -name "*.mp4" -o -name "*.webm" -o -name "*.mkv" \) | head -1)
        if [[ -n "$downloaded" ]]; then
            extract_audio "$downloaded" "$OUTPUT_DIR"
            rm -rf "$local_tmp"
        else
            echo -e "${RED}No se pudo descargar el vídeo${NC}"
            rm -rf "$local_tmp"
            exit 1
        fi
        exit 0
        ;;
    merge-audio)
        if [[ -z "$AUDIO_INPUT" ]]; then
            echo -e "${RED}ERROR: Se requiere archivo de audio${NC}"
            echo "  Uso: ./midu.sh -ma <audio.mp3>"
            exit 1
        fi
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para mezclar${NC}"
            exit 0
        fi
        for file in "${archivos[@]}"; do
            merge_audio "$file" "$AUDIO_INPUT" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    concat)
        if [[ ${#CONCAT_FILES[@]} -lt 2 ]]; then
            echo -e "${RED}ERROR: Se necesitan al menos2 archivos${NC}"
            echo "  Uso: ./midu.sh --concat video1.mkv video2.mkv video3.mkv"
            exit 1
        fi
        concat_videos "$OUTPUT_DIR" "${CONCAT_FILES[@]}"
        exit $?
        ;;
    watch)
        run_watch_mode "$INPUT_DIR" "$OUTPUT_DIR"
        exit 0
        ;;
    cut)
        if [[ -z "$START_TIME" && -z "$END_TIME" ]]; then
            echo -e "${RED}ERROR: Se requiere -ss y/o -e para cortar${NC}"
            echo "  Uso: ./midu.sh --cut -ss 00:01:30 -e 00:03:45"
            exit 1
        fi
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para cortar en $INPUT_DIR${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            cut_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    convert)
        # Continúa al flujo de conversión normal más abajo
        ;;
    gif)
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para convertir a GIF${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            gif_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    thumbnail)
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para extraer thumbnail${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            thumbnail_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    info)
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para mostrar info${NC}"
            exit 0
        fi
        for file in "${archivos[@]}"; do
            info_video "$file"
        done
        exit 0
        ;;
    rotate)
        if [[ -z "$ROTATE_DEGREES" ]]; then
            echo -e "${RED}ERROR: Se requiere grados de rotación${NC}"
            echo "  Uso: ./midu.sh --rotate 90"
            exit 1
        fi
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para rotar${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            rotate_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    crop)
        if [[ -z "$CROP_SIZE" ]]; then
            echo -e "${RED}ERROR: Se requiere tamaño de crop (W:H)${NC}"
            echo "  Uso: ./midu.sh --crop 640:480"
            exit 1
        fi
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para recortar${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            crop_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    fade)
        if [[ -z "$FADE_SECONDS" ]]; then
            echo -e "${RED}ERROR: Se requiere duración del fade${NC}"
            echo "  Uso: ./midu.sh --fade 2"
            exit 1
        fi
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para aplicar fade${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            fade_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    normalize)
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para normalizar audio${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            normalize_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    watermark)
        if [[ -z "$WATERMARK_FILE" || ! -f "$WATERMARK_FILE" ]]; then
            echo -e "${RED}ERROR: Se requiere archivo de marca de agua válido${NC}"
            echo "  Uso: ./midu.sh --watermark logo.png"
            exit 1
        fi
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para añadir marca de agua${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            watermark_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    deinterlace)
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para desentrelazar${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            deinterlace_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    fps)
        if [[ -z "$TARGET_FPS" ]]; then
            echo -e "${RED}ERROR: Se requiere FPS objetivo${NC}"
            echo "  Uso: ./midu.sh --fps 60"
            exit 1
        fi
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para cambiar FPS${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            fps_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
esac

# ── Buscar archivos ───────────────────────────────────────────────────

if [[ "$INTERACTIVE" == false ]]; then
    if ! mkdir -p "$OUTPUT_DIR" 2>/dev/null; then
        echo -e "${RED}ERROR: No se pudo crear el directorio: $OUTPUT_DIR${NC}"
        exit 1
    fi
    if [ ! -w "$OUTPUT_DIR" ]; then
        echo -e "${RED}ERROR: Sin permisos de escritura en: $OUTPUT_DIR${NC}"
        exit 1
    fi
fi

buscar_archivos

if [[ $total -eq 0 ]]; then
    echo ""
    echo -e "${YELLOW}No hay vídeos nuevos para convertir en $INPUT_DIR${NC}"
    [[ $saltados -gt 0 ]] && echo -e "  ${DIM}($saltados ya convertidos)${NC}"
    exit 0
fi

echo -e "${BOLD}Encontrados${NC} $total archivos, $saltados ya hechos (hilos: $MAX_THREADS)"
echo ""

# ── Convertir ─────────────────────────────────────────────────────────

procesados=0
fallidos=0
active_threads=()

convertir_archivo() {
    local file="$1"
    local output_dir="$2"
    local filename
    filename=$(basename "$file")
    filename="${filename%.*}"
    local output_file="$output_dir/$filename.mp4"
    local tmp_file="$output_dir/.tmp_$$_$(date +%s).mp4"

    local duration
    duration=$(get_duration "$file")
    # Validar que duration sea un número
    if [[ -z "$duration" || ! "$duration" =~ ^[0-9]+$ ]]; then
        duration=0
    fi

    # Calcular duración del segmento a cortar
    local effective_duration=$duration
    if [[ -n "$START_TIME" || -n "$END_TIME" ]]; then
        local start_secs=$(time_to_seconds "$START_TIME")
        local end_secs=$(time_to_seconds "$END_TIME")

        # Validar que start_secs no sea mayor que la duración del archivo
        if [[ "$start_secs" -ge "$duration" ]]; then
            echo -e "${RED}ERROR: Tiempo de inicio ($START_TIME) mayor que la duración del vídeo ($duration_fmt)${NC}"
            return 1
        fi

        # Si no hay END_TIME, usar la duración del archivo
        if [[ "$end_secs" -eq 0 ]]; then
            end_secs=$duration
        fi

        # Validar que end_secs sea mayor que start_secs
        if [[ "$end_secs" -le "$start_secs" ]]; then
            echo -e "${RED}ERROR: Tiempo de fin ($END_TIME) debe ser mayor que el inicio ($START_TIME)${NC}"
            return 1
        fi

        effective_duration=$((end_secs - start_secs))
    fi

    local duration_fmt
    duration_fmt=$(format_time "$effective_duration")

    local remux="false"
    if can_remux "$file" && [[ -z "$MAX_SIZE" ]] && [[ -z "$START_TIME" ]] && [[ -z "$END_TIME" ]] && [[ -z "$SUBTITLE_HARD" ]] && [[ -z "$SPEED" ]]; then
        remux="true"
    fi

    if [[ "$VERBOSE" == true ]]; then
        echo "[$procesados/$total] ${filename} (${duration_fmt:-??:??:??}) [remux=$remux]"
    fi

    local ffmpeg_args=(-y)

    # ── Corte: -ss ANTES de -i (rápido) ────────────────────────────
    if [[ -n "$START_TIME" ]]; then
        ffmpeg_args+=(-ss "$START_TIME")
    fi

    ffmpeg_args+=(-i "$file")

    # ── Subtítulos soft: input adicional ───────────────────────────
    if [[ -n "$SUBTITLE_SOFT" ]]; then
        ffmpeg_args+=(-i "$SUBTITLE_SOFT")
    fi

    # ── Duración del segmento ───────────────────────────────────────
    if [[ -n "$START_TIME" || -n "$END_TIME" ]] && [[ "$effective_duration" -gt 0 ]]; then
        ffmpeg_args+=(-t "$effective_duration")
    fi

    if [[ "$remux" == "true" ]]; then
        ffmpeg_args+=(-c copy -movflags +faststart)
    else
        # ── Construir filtros de vídeo (-vf) ───────────────────────
        # Todos los filtros se combinan en una sola cadena: -vf "f1,f2,f3"
        local vf_parts=()

        local res_filter
        res_filter=$(get_resolution_filter "$RESOLUTION")
        [[ -n "$res_filter" ]] && vf_parts+=("$res_filter")

        # Velocidad: setpts=PTS/factor
        if [[ -n "$SPEED" ]]; then
            vf_parts+=("setpts=PTS/$SPEED")
        fi

        # Subtítulos hard: quemar en vídeo
        if [[ -n "$SUBTITLE_HARD" ]]; then
            vf_parts+=("subtitles=${SUBTITLE_HARD}:force_style=FontSize=24")
        fi

        # Unir filtros con comas
        local vf_combined=""
        if [[ ${#vf_parts[@]} -gt 0 ]]; then
            local IFS=','
            vf_combined="${vf_parts[*]}"
        fi

        local audio_kbps
        audio_kbps=$(echo "$AUDIO_BITRATE" | sed 's/k//')

        if [[ -n "$MAX_SIZE_MB" && -n "$effective_duration" && "$effective_duration" -gt 0 ]]; then
            local total_bits=$((MAX_SIZE_MB * 1024 * 8))
            local total_kbits=$((total_bits / 1000))
            local video_kbits=$((total_kbits - (audio_kbps * effective_duration)))
            local video_bitrate=$((video_kbits / effective_duration))

            if [[ "$video_bitrate" -lt 100 ]]; then
                video_bitrate=100
            fi

            [[ "$VERBOSE" == true ]] && echo "  → Bitrate vídeo: ${video_bitrate}k (para ${MAX_SIZE}GB en ${effective_duration}s)"

            case "$GPU" in
                nvenc) ffmpeg_args+=(-c:v h264_nvenc -b:v "${video_bitrate}k" -maxrate "$((video_bitrate * 2))k" -bufsize "${video_bitrate}k" -preset "$ENCODE_SPEED") ;;
                vaapi) ffmpeg_args+=(-vaapi_device /dev/dri/renderD128 -c:v h264_vaapi -b:v "${video_bitrate}k" -maxrate "$((video_bitrate * 2))k" -bufsize "${video_bitrate}k") ;;
                *)     ffmpeg_args+=(-c:v libx264 -threads 0 -b:v "${video_bitrate}k" -maxrate "$((video_bitrate * 2))k" -bufsize "${video_bitrate}k" -preset "$ENCODE_SPEED") ;;
            esac
        else
            case "$GPU" in
                nvenc) ffmpeg_args+=(-c:v h264_nvenc -rc constqp -qp "$CRF" -preset "$ENCODE_SPEED") ;;
                vaapi) ffmpeg_args+=(-vaapi_device /dev/dri/renderD128 -c:v h264_vaapi -qp "$CRF") ;;
                *)     ffmpeg_args+=(-c:v libx264 -threads 0 -crf "$CRF" -preset "$ENCODE_SPEED") ;;
            esac
        fi

        # Aplicar filtros de vídeo combinados
        if [[ -n "$vf_combined" ]]; then
            ffmpeg_args+=(-vf "$vf_combined")
        fi

        # Audio codec y bitrate
        case "$AUDIO_CODEC" in
            copy)    ffmpeg_args+=(-c:a copy) ;;
            aac)     ffmpeg_args+=(-c:a aac -b:a "$AUDIO_BITRATE") ;;
            opus)    ffmpeg_args+=(-c:a libopus -b:a "$AUDIO_BITRATE") ;;
            mp3)     ffmpeg_args+=(-c:a libmp3lame -b:a "$AUDIO_BITRATE") ;;
            flac)    ffmpeg_args+=(-c:a flac) ;;
            vorbis)  ffmpeg_args+=(-c:a libvorbis -b:a "$AUDIO_BITRATE") ;;
            ac3)     ffmpeg_args+=(-c:a ac3 -b:a "$AUDIO_BITRATE") ;;
            eac3)    ffmpeg_args+=(-c:a eac3 -b:a "$AUDIO_BITRATE") ;;
            pcm_s16le) ffmpeg_args+=(-c:a pcm_s16le) ;;
            pcm_s24le) ffmpeg_args+=(-c:a pcm_s24le) ;;
        esac

        if [[ -n "$SPEED" ]]; then
            # atempo solo acepta0.5-100, encadenar para valores extremos
            local atempo_val="$SPEED"
            if [[ "$atempo_val" == "0.25" ]]; then
                ffmpeg_args+=(-af "atempo=0.5,atempo=0.5")
            elif [[ "$atempo_val" == "0.5" ]]; then
                ffmpeg_args+=(-af "atempo=0.5")
            elif [[ "$atempo_val" == "2" || "$atempo_val" == "2.0" ]]; then
                ffmpeg_args+=(-af "atempo=2.0")
            elif [[ "$atempo_val" == "4" || "$atempo_val" == "4.0" ]]; then
                ffmpeg_args+=(-af "atempo=2.0,atempo=2.0")
            elif [[ "$atempo_val" == "0.75" ]]; then
                ffmpeg_args+=(-af "atempo=0.75")
            else
                ffmpeg_args+=(-af "atempo=$atempo_val")
            fi
        fi

    fi

    # Map streams: vídeo (input0) + audio (input0) + subtítulos soft si existe (input1)
    ffmpeg_args+=(-map 0:v:0 -map 0:a:0)
    if [[ -n "$SUBTITLE_SOFT" ]]; then
        ffmpeg_args+=(-map 1:s:0 -c:s copy)
    fi
    ffmpeg_args+=(-map_metadata 0 -movflags +faststart)
    ffmpeg_args+=("$tmp_file")

    local ffmpeg_log="$tmp_file.log"
    rm -f "$ffmpeg_log"

    if [[ "$VERBOSE" == true ]]; then
        echo -e "  ${DIM}ffmpeg ${ffmpeg_args[*]}${NC}"
        ffmpeg "${ffmpeg_args[@]}" \
            -progress pipe:2 \
            -stats_period 0.5 \
            2>"$ffmpeg_log" &
    else
        ffmpeg "${ffmpeg_args[@]}" \
            -progress pipe:2 \
            -stats_period 0.5 \
            2>"$ffmpeg_log" 1>/dev/null &
    fi
    local ffmpeg_pid=$!

    while kill -0 "$ffmpeg_pid" 2>/dev/null; do
        if [[ -f "$ffmpeg_log" ]]; then
            local out_time_us
            out_time_us=$(tail -20 "$ffmpeg_log" 2>/dev/null | grep -m1 '^out_time_us=' | cut -d= -f2)
            if [[ -n "$out_time_us" && "$out_time_us" -gt 0 && -n "$effective_duration" && "$effective_duration" -gt 0 ]]; then
                local cur_secs=$((out_time_us / 1000000))
                local pct=$((cur_secs * 100 / effective_duration))
                [[ "$pct" -gt 100 ]] && pct=100
                local cur_fmt
                cur_fmt=$(format_time "$cur_secs")
                local remain_secs=$((effective_duration - cur_secs))
                [[ "$remain_secs" -lt 0 ]] && remain_secs=0
                local remain_fmt
                remain_fmt=$(format_time "$remain_secs")

                if [[ "$VERBOSE" == true ]]; then
                    printf "  ${DIM}%3d%% | %s / %s | falta %s${NC}\r" "$pct" "$cur_fmt" "$duration_fmt" "$remain_fmt" >&2
                fi
            fi
        fi
        sleep 0.5
    done
    wait "$ffmpeg_pid"
    local ffmpeg_exit=$?

    if [[ "$VERBOSE" == true ]]; then
        printf "  ${DIM}100%% | %s / %s | completado${NC}\n" "$duration_fmt" "$duration_fmt" >&2
    fi

    if [[ "$ffmpeg_exit" -ne 0 ]]; then
        echo -e "${RED}[$procesados/$total] ERROR: $filename (ffmpeg exit: $ffmpeg_exit)${NC}"
        if [[ -f "$ffmpeg_log" ]]; then
            tail -5 "$ffmpeg_log" | sed 's/^/    /'
        fi
        rm -f "$tmp_file" "$ffmpeg_log"
        return 1
    fi
    rm -f "$ffmpeg_log"

    if [[ ! -f "$tmp_file" ]]; then
        echo -e "${RED}[$procesados/$total] ERROR: archivo temporal no creado${NC}"
        return 1
    fi

    local size
    size=$(stat -c%s "$tmp_file" 2>/dev/null || stat -f%z "$tmp_file" 2>/dev/null || echo 0)
    if [[ "$size" -lt 1024 ]]; then
        echo -e "${RED}[$procesados/$total] ERROR: archivo temporal sospechosamente pequeño (${size} bytes)${NC}"
        rm -f "$tmp_file"
        return 1
    fi

    mv "$tmp_file" "$output_file"

    local orig_size
    orig_size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo 0)
    local orig_mb=$((orig_size / 1024 / 1024))
    local out_mb=$((size / 1024 / 1024))
    local ratio=0
    if [[ "$orig_size" -gt 0 ]]; then
        ratio=$((size * 100 / orig_size))
    fi

    if [[ "$VERBOSE" == true ]]; then
        echo -e "  ${GREEN}OK${NC}: ${orig_mb}MB → ${out_mb}MB (${ratio}%)"
    fi

    rm "$file"
    return 0
}

# ── Ejecutar ──────────────────────────────────────────────────────────

procesados=0
fallidos=0
active_threads=()

for file in "${archivos[@]}"; do
    convertir_archivo "$file" "$OUTPUT_DIR" &
    active_threads+=($!)

    while [ "${#active_threads[@]}" -ge "$MAX_THREADS" ]; do
        for i in "${!active_threads[@]}"; do
            if ! kill -0 "${active_threads[i]}" 2>/dev/null; then
                wait "${active_threads[i]}" 2>/dev/null
                if [[ $? -eq 0 ]]; then
                    ((procesados++))
                else
                    ((fallidos++))
                fi
                unset 'active_threads[i]'
            fi
        done
        active_threads=("${active_threads[@]}")
        sleep 0.5
    done
done

for pid in "${active_threads[@]}"; do
    wait "$pid" 2>/dev/null
    if [[ $? -eq 0 ]]; then
        ((procesados++))
    else
        ((fallidos++))
    fi
done

echo ""
echo -e "${BOLD}Completado:${NC} ${GREEN}$procesados OK${NC}, ${RED}$fallidos fallos${NC} de $total archivos."
