#!/bin/bash

VERSION="5.0.0"

# ── Configuración guardada ────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || dirname "${BASH_SOURCE[0]}")"
CONF_FILE="${SCRIPT_DIR}/../conf.json"

load_config() {
    local mode="${1:-}"
    [[ ! -f "$CONF_FILE" ]] && return 1
    command -v jq &>/dev/null || return 1
    local cfg
    cfg=$(jq -c '.' "$CONF_FILE" 2>/dev/null) || return 1

    # Config global (siempre se carga)
    INPUT_DIR=$(echo "$cfg"     | jq -r '.inputDir // empty')      || true
    OUTPUT_DIR=$(echo "$cfg"    | jq -r '.outputDir // empty')     || true
    EXTENSIONS=$(echo "$cfg"    | jq -r '.extensions // empty')    || true
    VERBOSE=$(echo "$cfg"       | jq -r '.verbose // empty')       || true

    # Config por modo
    if [[ -n "$mode" ]] && echo "$cfg" | jq -e ".modes.\"$mode\"" &>/dev/null; then
        local m
        m=$(echo "$cfg" | jq -c ".modes.\"$mode\"")
        case "$mode" in
            convert)
                PRESET=$(echo "$m"        | jq -r '.preset // empty')        || true
                VIDEO_CODEC=$(echo "$m"   | jq -r '.videoCodec // empty')    || true
                AUDIO_CODEC=$(echo "$m"   | jq -r '.audioCodec // empty')    || true
                AUDIO_BITRATE=$(echo "$m" | jq -r '.audioBitrate // empty')  || true
                RESOLUTION=$(echo "$m"    | jq -r '.resolution // empty')    || true
                MAX_SIZE=$(echo "$m"      | jq -r '.maxSize // empty')       || true
                SOCIAL=$(echo "$m"        | jq -r '.social // empty')        || true
                ;;
            cut)
                START_TIME=$(echo "$m"    | jq -r '.startTime // empty')     || true
                END_TIME=$(echo "$m"      | jq -r '.endTime // empty')       || true
                CUT_MODE=$(echo "$m"      | jq -r '.cutMode // empty')       || true
                CUT_CLIPS=()
                if echo "$m" | jq -e '.cutClips | type == "array"' &>/dev/null; then
                    while IFS= read -r clip; do CUT_CLIPS+=("$clip"); done < <(echo "$m" | jq -r '.cutClips[]')
                fi
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
            watermark)
                WATERMARK_FILE=$(echo "$m" | jq -r '.watermarkFile // empty') || true
                ;;
            stabilize)
                STAB_SHAKINESS=$(echo "$m" | jq -r '.stabShakiness // empty') || true
                ;;
            adjust)
                ADJUST_BRIGHTNESS=$(echo "$m" | jq -r '.brightness // empty') || true
                ADJUST_CONTRAST=$(echo "$m"  | jq -r '.contrast // empty')   || true
                ADJUST_SATURATION=$(echo "$m"| jq -r '.saturation // empty') || true
                ADJUST_GAMMA=$(echo "$m"     | jq -r '.gamma // empty')      || true
                ;;
            censor)
                CENSOR_REGIONS=()
                if echo "$m" | jq -e '.regions | type == "array"' &>/dev/null; then
                    while IFS= read -r region; do CENSOR_REGIONS+=("$region"); done < <(echo "$m" | jq -r '.regions[]')
                fi
                ;;
            denoise)
                DENOISE_STRENGTH=$(echo "$m" | jq -r '.denoiseStrength // empty') || true
                ;;
            sharpen)
                SHARPEN_STRENGTH=$(echo "$m" | jq -r '.sharpenStrength // empty') || true
                ;;
            scenes)
                SCENE_THRESHOLD=$(echo "$m" | jq -r '.sceneThreshold // empty') || true
                ;;
            keyframes)
                KEYFRAME_DIR=$(echo "$m" | jq -r '.keyframeDir // empty') || true
                ;;
            aspect)
                ASPECT_RATIO=$(echo "$m" | jq -r '.aspectRatio // empty') || true
                ;;
            metadata)
                METADATA_TITLE=$(echo "$m"  | jq -r '.title // empty')   || true
                METADATA_ARTIST=$(echo "$m" | jq -r '.artist // empty')  || true
                METADATA_COMMENT=$(echo "$m"| jq -r '.comment // empty') || true
                ;;
            download)
                DOWNLOAD_START=$(echo "$m" | jq -r '.dlStart // empty') || true
                DOWNLOAD_END=$(echo "$m"   | jq -r '.dlEnd // empty')   || true
                ;;
            subtitles)
                SUBTITLE_SOFT=$(echo "$m" | jq -r '.subtitleSoft // empty') || true
                SUBTITLE_HARD=$(echo "$m" | jq -r '.subtitleHard // empty') || true
                ;;
            concat)
                CONCAT_FILES=()
                if echo "$m" | jq -e '.files | type == "array"' &>/dev/null; then
                    while IFS= read -r f; do CONCAT_FILES+=("$f"); done < <(echo "$m" | jq -r '.files[]')
                fi
                ;;
        esac
    fi
}

save_config() {
    local mode="${1:-}"
    local tmp="$CONF_FILE.tmp"

    if ! command -v jq &>/dev/null; then
        echo -e "${RED}ERROR: jq no está instalado. No se pudo guardar la configuración.${NC}"
        echo -e "  ${DIM}Alpine: apk add jq   |   Ubuntu/Debian: sudo apt install jq${NC}"
        return 1
    fi

    # ── Config global: solo campos no vacíos (no pisa valores guardados) ──
    local global_json="{}"
    [[ -n "$INPUT_DIR" ]]   && global_json=$(echo "$global_json" | jq --arg v "$INPUT_DIR"   '. + {inputDir: $v}')
    [[ -n "$OUTPUT_DIR" ]]  && global_json=$(echo "$global_json" | jq --arg v "$OUTPUT_DIR"  '. + {outputDir: $v}')
    [[ -n "$EXTENSIONS" ]]  && global_json=$(echo "$global_json" | jq --arg v "$EXTENSIONS"  '. + {extensions: $v}')
    if [[ "$VERBOSE" == "true" ]]; then
        global_json=$(echo "$global_json" | jq '. + {verbose: true}')
    else
        global_json=$(echo "$global_json" | jq '. + {verbose: false}')
    fi

    # ── Config del modo ──
    local mode_json="{}"
    local arr_json="[]"
    case "$mode" in
        convert)
            mode_json=$(jq -n \
                --arg social "$SOCIAL" \
                --arg preset "$PRESET" \
                --arg codec "$VIDEO_CODEC" \
                --arg audio "$AUDIO_CODEC" \
                --arg bitrate "$AUDIO_BITRATE" \
                --arg res "$RESOLUTION" \
                --arg max "$MAX_SIZE" \
                '{social: $social, preset: $preset, videoCodec: $codec, audioCodec: $audio, audioBitrate: $bitrate, resolution: $res, maxSize: $max}')
            ;;
        cut)
            arr_json="[]"
            [[ ${#CUT_CLIPS[@]} -gt 0 ]] && arr_json=$(printf '%s\n' "${CUT_CLIPS[@]}" | jq -R . | jq -s .)
            mode_json=$(jq -n \
                --arg start "$START_TIME" \
                --arg end "$END_TIME" \
                --arg cut_mode "${CUT_MODE:-normal}" \
                --argjson clips "$arr_json" \
                '{startTime: $start, endTime: $end, cutMode: $cut_mode, cutClips: $clips}')
            ;;
        gif)
            mode_json=$(jq -n \
                --arg fps "$GIF_FPS" \
                --arg scale "$GIF_SCALE" \
                '{gifFps: $fps, gifScale: $scale}')
            ;;
        thumbnail)
            mode_json=$(jq -n \
                --arg time "$THUMBNAIL_TIME" \
                '{thumbnailTime: $time}')
            ;;
        rotate)
            mode_json=$(jq -n \
                --arg degrees "$ROTATE_DEGREES" \
                '{rotateDegrees: $degrees}')
            ;;
        crop)
            mode_json=$(jq -n \
                --arg size "$CROP_SIZE" \
                '{cropSize: $size}')
            ;;
        fade)
            mode_json=$(jq -n \
                --arg seconds "$FADE_SECONDS" \
                '{fadeSeconds: $seconds}')
            ;;
        fps)
            mode_json=$(jq -n \
                --arg fps "$TARGET_FPS" \
                '{targetFps: $fps}')
            ;;
        speed)
            mode_json=$(jq -n \
                --arg speed "$SPEED" \
                '{speed: $speed}')
            ;;
        audio-only)
            mode_json=$(jq -n \
                --arg format "$OUTPUT_FORMAT" \
                '{outputFormat: $format}')
            ;;
        watermark)
            mode_json=$(jq -n \
                --arg file "$WATERMARK_FILE" \
                '{watermarkFile: $file}')
            ;;
        stabilize)
            mode_json=$(jq -n \
                --arg strength "$STAB_SHAKINESS" \
                '{stabShakiness: $strength}')
            ;;
        adjust)
            mode_json=$(jq -n \
                --arg brightness "$ADJUST_BRIGHTNESS" \
                --arg contrast "$ADJUST_CONTRAST" \
                --arg saturation "$ADJUST_SATURATION" \
                --arg gamma "$ADJUST_GAMMA" \
                '{brightness: $brightness, contrast: $contrast, saturation: $saturation, gamma: $gamma}')
            ;;
        censor)
            arr_json="[]"
            [[ ${#CENSOR_REGIONS[@]} -gt 0 ]] && arr_json=$(printf '%s\n' "${CENSOR_REGIONS[@]}" | jq -R . | jq -s .)
            mode_json=$(jq -n --argjson regions "$arr_json" '{regions: $regions}')
            ;;
        denoise)
            mode_json=$(jq -n \
                --arg strength "$DENOISE_STRENGTH" \
                '{denoiseStrength: $strength}')
            ;;
        sharpen)
            mode_json=$(jq -n \
                --arg strength "$SHARPEN_STRENGTH" \
                '{sharpenStrength: $strength}')
            ;;
        scenes)
            mode_json=$(jq -n \
                --arg threshold "$SCENE_THRESHOLD" \
                '{sceneThreshold: $threshold}')
            ;;
        keyframes)
            mode_json=$(jq -n \
                --arg dir "$KEYFRAME_DIR" \
                '{keyframeDir: $dir}')
            ;;
        aspect)
            mode_json=$(jq -n \
                --arg ratio "$ASPECT_RATIO" \
                '{aspectRatio: $ratio}')
            ;;
        metadata)
            mode_json=$(jq -n \
                --arg title "$METADATA_TITLE" \
                --arg artist "$METADATA_ARTIST" \
                --arg comment "$METADATA_COMMENT" \
                '{title: $title, artist: $artist, comment: $comment}')
            ;;
        download)
            mode_json=$(jq -n \
                --arg start "$DOWNLOAD_START" \
                --arg end "$DOWNLOAD_END" \
                '{dlStart: $start, dlEnd: $end}')
            ;;
        subtitles)
            mode_json=$(jq -n \
                --arg soft "$SUBTITLE_SOFT" \
                --arg hard "$SUBTITLE_HARD" \
                '{subtitleSoft: $soft, subtitleHard: $hard}')
            ;;
        concat)
            arr_json="[]"
            [[ ${#CONCAT_FILES[@]} -gt 0 ]] && arr_json=$(printf '%s\n' "${CONCAT_FILES[@]}" | jq -R . | jq -s .)
            mode_json=$(jq -n --argjson files "$arr_json" '{files: $files}')
            ;;
        merge-audio)
            mode_json=$(jq -n \
                --arg audio "$AUDIO_INPUT" \
                --arg format "$OUTPUT_FORMAT" \
                '{audioInput: $audio, outputFormat: $format}')
            ;;
    esac

    # ── Base: leer config existente o partir de vacío ──
    local base="{}"
    if [[ -f "$CONF_FILE" ]] && jq -e '.' "$CONF_FILE" &>/dev/null; then
        base=$(jq -c '.' "$CONF_FILE")
    fi

    # ── Mezclar global + modo ──
    local new_cfg
    new_cfg=$(echo "$base" | jq -c \
        --argjson g "$global_json" \
        --argjson m "$mode_json" \
        --arg mode "$mode" \
        '. + $g |
         if $mode != "" and ($m | length) > 0 then .modes[$mode] = $m else . end')
    new_cfg=$(echo "$new_cfg" | jq -c 'if has("modes") then . else . + {modes: {}} end')

    # ── Escribir ──
    mkdir -p "$(dirname "$CONF_FILE")"
    if echo "$new_cfg" | jq . > "$tmp" && mv "$tmp" "$CONF_FILE"; then
        echo -e "${GREEN}Configuración guardada${NC}"
    else
        echo -e "${RED}ERROR: No se pudo escribir la configuración${NC}"
        return 1
    fi
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
    if [[ "${panel_lines:-0}" -gt 0 ]]; then
        printf '\033[%dA\033[J' "$panel_lines" >&2
    fi
    rm -rf "$PROG_DIR" 2>/dev/null
    rm -f "$OUTPUT_DIR"/.tmp_* "$OUTPUT_DIR"/*.log "$OUTPUT_DIR"/*.progress 2>/dev/null
    rm -f "$SCRIPT_DIR/.midu_preview_req" 2>/dev/null
    echo -e "${GREEN}Limpieza completada.${NC}"
    exit 130
}
trap cleanup SIGINT SIGTERM SIGHUP
trap 'rm -f "$SCRIPT_DIR/.midu_preview_req" 2>/dev/null' EXIT

# ── Help ──────────────────────────────────────────────────────────────

show_help() {
    cat <<EOF
midu.sh v${VERSION} — Conversor, descargador y editor de vídeo

═══════════════════════════════════════════════════════════════════════
 QUÉ HACE CADA MODO (resumen rápido)
═══════════════════════════════════════════════════════════════════════

  -d URL          Descarga de YouTube, Twitch, Kick, TikTok, Instagram,
                  Twitter/X, Facebook, Vimeo, Reddit, SoundCloud y 1000+ sitios
  --cut           Corta un trozo del vídeo (rápido, sin perder calidad)
  --cut --remove  Elimina secciones del vídeo (ej: --clips 00:01:00-00:02:30)
  --cut --extract Extrae clips y los une en un solo vídeo
  --clips         Lista de clips (ej: -clips 00:01:00-00:02:30,00:05:00-00:07:15)
  --convert       Convierte/comprime el vídeo (ajusta tamaño y calidad)
  --gif           Crea un GIF animado a partir del vídeo
  --thumbnail     Saca una captura de pantalla (imagen PNG) del vídeo
  --info          Muestra datos del vídeo: duración, codecs, resolución
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
  --stabilize     Quita el temblor del vídeo (vidstab)
  --adjust        Ajusta brillo, contraste, saturación, gamma
  --censor        Pixela regiones del vídeo (caras, matrículas)
  --denoise       Reduce ruido del vídeo
  --sharpen       Enfoca vídeos borrosos
  --reverse       Invierte el vídeo (al revés)
  --scenes        Detecta escenas y corta automáticamente
  --keyframes     Extrae todas las imágenes I-frame
  --aspect        Cambia ratio de aspecto (16:9, 4:3, 21:9)
  --metadata      Editar título, autor, comentario del vídeo

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
  -vc, --video-codec C   Códec de vídeo: h264|hevc|av1|vp9 (default: h264)
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

ESTABILIZACIÓN:
  --stabilize [SHAKE]    Estabilizar vídeo tembloroso (shakiness: 1-10, default: 5)

AJUSTE DE IMAGEN:
  --adjust brightness=N contrast=N saturation=N gamma=N
                         Ajustar parámetros de imagen (-1.0 a 1.0, gamma: 0.1-10)

CENSURA:
  --censor X:Y:W:H...   Pixelar regiones del vídeo (una o más separadas por espacio)

DENOISE/SHARPEN:
  --denoise [STRENGTH]   Reducir ruido (1-100, default: 50)
  --sharpen [STRENGTH]   Enfocar vídeo (1-10, default: 5)

EFECTOS:
  --reverse              Invertir vídeo (reproducción al revés)
  --scenes [THRESHOLD]   Detectar y cortar por escenas (0.0-1.0, default: 0.3)
  --keyframes [DIR]      Extraer keyframes como imágenes (default: ./keyframes)
  --aspect RATIO         Cambiar aspect ratio (16:9, 4:3, 21:9, 1:1, 9:16)

METADATA:
  --metadata title=X artist=Y comment=Z
                         Editar metadata del vídeo

GENERAL:
  -n, --non-interactive  Sin prompts, usa valores por defecto
  -c, --save-config      Guarda la configuración actual en conf.json
  -v, --verbose          Muestra progreso línea por línea (default: resumen)
  --two-pass             Two-pass encoding (mejor calidad con --max-gb)
  --hw-accel             Usar aceleración por hardware para decodificar
  --dry-run              Preview sin ejecutar (muestra comandos)
  --collision POLICY     Colisión: skip|rename|overwrite (default: overwrite)
  --notify               Notificación al terminar (notify-send)
  --write-subs           Descargar subtítulos automáticamente con yt-dlp
  --sub-langs LANGS      Idiomas de subtítulos (default: es,en)
  --checkpoint FILE      Guardar progreso para resume
  --resume [FILE]        Continuar desde checkpoint
  --retry                Reintentar archivos fallidos al terminar
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
SELECTED_FILES=()
PRESET="default"
VIDEO_CODEC="h264"
AUDIO_CODEC="aac"
AUDIO_BITRATE="128k"
RESOLUTION="original"
MAX_SIZE=""
MAX_THREADS=4
EXTENSIONS="avi,webm,mkv,mp4,flv"
INTERACTIVE=true
VERBOSE=false
SOCIAL=""
START_TIME=""
END_TIME=""
CUT_MODE="normal"                  # normal|remove|extract — sub-modo de corte
CUT_CLIPS=()                       # Lista de clips para remove/extract (formato: start-end,start-end)
declare -A FILE_CUT                # Config de corte por vídeo (clave=archivo, valor=MODE|start|end|clips;)

# ── Nuevas funcionalidades ───────────────────────────────────────────
MODE=""                         # download|audio-only|merge-audio|concat|watch|cut|convert|gif|thumbnail|info|rotate|crop|fade|normalize|watermark|deinterlace|fps
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
STAB_SHAKINESS=""               # Nivel de estabilización (1-10)
ADJUST_BRIGHTNESS=""            # Brillo (-1.0 a 1.0)
ADJUST_CONTRAST=""              # Contraste (-1.0 a 1.0)
ADJUST_SATURATION=""            # Saturación (-1.0 a 1.0)
ADJUST_GAMMA=""                 # Gamma (0.1 a 10)
CENSOR_REGIONS=()               # Regiones a censurar (x:y:w:h)
CENSOR_FRAMES=""                # Rango de frames a censurar
DENOISE_STRENGTH=""             # Fuerza del denoise (1-100)
SHARPEN_STRENGTH=""             # Fuerza del sharpen (1-10)
ASPECT_RATIO=""                 # Ratio de aspecto (16:9, 4:3, 21:9)
METADATA_TITLE=""               # Metadata título
METADATA_ARTIST=""              # Metadata artista
METADATA_COMMENT=""             # Metadata comentario
SCENE_THRESHOLD=""              # Umbral de detección de escenas (0.0-1.0)
KEYFRAME_DIR=""                 # Directorio para keyframes
TWO_PASS=false                  # Two-pass encoding
HW_ACCEL=false                  # Aceleración por hardware
DRY_RUN=false                   # Modo preview sin ejecutar
COLLISION="overwrite"           # Política de colisión (skip|rename|overwrite)
NOTIFY=false                    # Notificación al terminar
CHECKPOINT_FILE=""              # Archivo de checkpoint
RETRY_FAILED=false              # Reintentar archivos fallidos
SUBS_DOWNLOAD=false             # Descargar subtítulos automáticamente
SUBS_LANGS="es,en"             # Idiomas de subtítulos a descargar

# ── Parse flags ───────────────────────────────────────────────────────

SAVE_CONFIG=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -s|--social)     SOCIAL="$2"; shift 2 ;;
        -p|--preset)     PRESET="$2"; shift 2 ;;
        -vc|--video-codec) VIDEO_CODEC="$2"; shift 2 ;;
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
        --cut)             MODE="cut"; shift
                            # Check for sub-modes
                            case "${1:-}" in
                                --remove)  CUT_MODE="remove"; shift ;;
                                --extract) CUT_MODE="extract"; shift ;;
                            esac
                            ;;
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
        --clips)           IFS=',' read -ra CUT_CLIPS <<< "$2"; shift 2 ;;
        --stabilize)       MODE="stabilize"; STAB_SHAKINESS="${2:-5}"; shift 2 ;;
        --adjust)          MODE="adjust"; shift
                            while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
                                case "$1" in
                                    brightness=*) ADJUST_BRIGHTNESS="${1#*=}"; shift ;;
                                    contrast=*)   ADJUST_CONTRAST="${1#*=}"; shift ;;
                                    saturation=*) ADJUST_SATURATION="${1#*=}"; shift ;;
                                    gamma=*)      ADJUST_GAMMA="${1#*=}"; shift ;;
                                    *) shift ;;
                                esac
                            done
                            ;;
        --censor)          MODE="censor"; shift
                            while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
                                CENSOR_REGIONS+=("$1"); shift
                            done
                            ;;
        --denoise)         MODE="denoise"; DENOISE_STRENGTH="${2:-50}"; shift 2 ;;
        --sharpen)         MODE="sharpen"; SHARPEN_STRENGTH="${2:-5}"; shift 2 ;;
        --reverse)         MODE="reverse"; shift ;;
        --scenes)          MODE="scenes"; SCENE_THRESHOLD="${2:-0.3}"; shift 2 ;;
        --keyframes)       MODE="keyframes"; KEYFRAME_DIR="${2:-./keyframes}"; shift 2 ;;
        --aspect)          MODE="aspect"; ASPECT_RATIO="$2"; shift 2 ;;
        --metadata)        MODE="metadata"; shift
                            while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
                                case "$1" in
                                    title=*)    METADATA_TITLE="${1#*=}"; shift ;;
                                    artist=*)   METADATA_ARTIST="${1#*=}"; shift ;;
                                    comment=*)  METADATA_COMMENT="${1#*=}"; shift ;;
                                    *) shift ;;
                                esac
                            done
                            ;;
        --two-pass)        TWO_PASS=true; shift ;;
        --hw-accel)        HW_ACCEL=true; shift ;;
        --dry-run)         DRY_RUN=true; shift ;;
        --collision)       COLLISION="$2"; shift 2 ;;
        --notify)          NOTIFY=true; shift ;;
        --checkpoint)      CHECKPOINT_FILE="$2"; shift 2 ;;
        --resume)          CHECKPOINT_FILE="${2:-.midu_checkpoint}"; shift; INTERACTIVE=false; MODE="resume" ;;
        --retry)           RETRY_FAILED=true; shift ;;
        --write-subs)      SUBS_DOWNLOAD=true; shift ;;
        --sub-langs)       SUBS_LANGS="$2"; shift 2 ;;
        --watch)           WATCH_MODE=true; shift ;;
        --preview)         MODE="preview"; shift ;;
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
            VIDEO_CODEC="h264"
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="128k"
            PRESET="web"
            ;;
        telegram)
            RESOLUTION="1080"
            MAX_SIZE="2"
            VIDEO_CODEC="hevc"
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="128k"
            PRESET="default"
            ;;
        instagram)
            RESOLUTION="1080"
            MAX_SIZE="0.5"
            VIDEO_CODEC="h264"
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="128k"
            PRESET="default"
            ;;
        tiktok)
            RESOLUTION="1080"
            MAX_SIZE="0.5"
            VIDEO_CODEC="h264"
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="128k"
            PRESET="default"
            ;;
        youtube)
            RESOLUTION="original"
            MAX_SIZE=""
            VIDEO_CODEC="h264"
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="192k"
            PRESET="archive"
            ;;
        twitter|tw)
            RESOLUTION="720"
            MAX_SIZE="0.5"
            VIDEO_CODEC="h264"
            AUDIO_CODEC="aac"
            AUDIO_BITRATE="128k"
            PRESET="web"
            ;;
        facebook|fb)
            RESOLUTION="1080"
            MAX_SIZE="1"
            VIDEO_CODEC="h264"
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
    # Validar que sea un número
    if ! [[ "$MAX_SIZE" =~ ^[0-9]+\.?[0-9]*$ ]]; then
        echo -e "${RED}ERROR: Tamaño máximo no válido: $MAX_SIZE${NC}"
        exit 1
    fi
    # Si tiene punto, es decimal (ej: 0.5GB = 512MB)
    if [[ "$MAX_SIZE" == *.* ]]; then
        MAX_SIZE_MB=$(echo "$MAX_SIZE * 1024" | bc 2>/dev/null)
        if [[ -z "$MAX_SIZE_MB" ]]; then
            echo -e "${RED}ERROR: No se pudo calcular el tamaño (instala 'bc')${NC}"
            exit 1
        fi
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

    # Obtener duración del vídeo
    local duration
    duration=$(get_duration "$file")
    if [[ -z "$duration" || ! "$duration" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}ERROR: No se pudo obtener la duración del vídeo${NC}"
        return 1
    fi

    # Validar tiempos contra la duración
    if [[ -n "$START_TIME" ]]; then
        local start_secs=$(time_to_seconds "$START_TIME")
        if [[ "$start_secs" -ge "$duration" ]]; then
            echo -e "${RED}ERROR: Tiempo de inicio ($START_TIME) es mayor o igual a la duración ($(format_time "$duration"))${NC}"
            return 1
        fi
    fi

    if [[ -n "$END_TIME" ]]; then
        local end_secs=$(time_to_seconds "$END_TIME")
        if [[ "$end_secs" -gt "$duration" ]]; then
            echo -e "${YELLOW}AVISO: Tiempo de fin ($END_TIME) es mayor que la duración ($(format_time "$duration"))${NC}"
            echo -e "  ${DIM}Se cortará hasta el final del vídeo${NC}"
            END_TIME=""
        fi
        if [[ -n "$START_TIME" ]]; then
            local start_secs=$(time_to_seconds "$START_TIME")
            if [[ "$end_secs" -le "$start_secs" ]]; then
                echo -e "${RED}ERROR: Tiempo de fin ($END_TIME) debe ser mayor que el inicio ($START_TIME)${NC}"
                return 1
            fi
        fi
    fi

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

# ── Eliminar secciones del vídeo ─────────────────────────────────────

remove_clips() {
    local file="$1"
    local output_dir="$2"

    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_trimmed.$ext"

    local duration
    duration=$(get_duration "$file")
    if [[ -z "$duration" || ! "$duration" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}ERROR: No se pudo obtener la duración del vídeo${NC}"
        return 1
    fi

    # Convertir clips a segundos y ordenar
    local keep_segments=()
    local clip_secs=()

    for clip in "${CUT_CLIPS[@]}"; do
        local start="${clip%%-*}"
        local end="${clip##*-}"
        local start_s=$(time_to_seconds "$start")
        local end_s=$(time_to_seconds "$end")

        if [[ "$start_s" -ge "$end_s" ]]; then
            echo -e "${RED}ERROR: Clip inválido ($start ≥ $end)${NC}"
            return 1
        fi
        if [[ "$end_s" -gt "$duration" ]]; then
            echo -e "${YELLOW}AVISO: Clip $clip excede la duración, se recorta${NC}"
            end_s=$duration
        fi
        clip_secs+=("$start_s $end_s")
    done

    # Ordenar clips por tiempo de inicio
    IFS=$'\n' sorted=($(sort -n <<< "${clip_secs[*]}")); unset IFS

    # Construir segmentos a mantener (lo que NO está en los clips)
    local prev_end=0
    for clip in "${sorted[@]}"; do
        local c_start="${clip%% *}"
        local c_end="${clip##* }"
        if [[ "$c_start" -gt "$prev_end" ]]; then
            keep_segments+=("$prev_end $c_start")
        fi
        prev_end=$c_end
    done
    # Si queda algo después del último clip
    if [[ "$prev_end" -lt "$duration" ]]; then
        keep_segments+=("$prev_end $duration")
    fi

    if [[ ${#keep_segments[@]} -eq 0 ]]; then
        echo -e "${RED}ERROR: No quedan segmentos tras eliminar las secciones${NC}"
        return 1
    fi

    echo -e "${BOLD}Eliminando secciones:${NC} $file"
    echo -e "  ${DIM}Duración original: $(format_time "$duration")${NC}"
    for clip in "${sorted[@]}"; do
        local c_start="${clip%% *}"
        local c_end="${clip##* }"
        echo -e "  ${RED}Eliminar: $(format_time "$c_start") → $(format_time "$c_end")${NC}"
    done

    # Usar select filter para saltar las secciones
    local vf=""
    local seg_idx=0
    for seg in "${keep_segments[@]}"; do
        local s_start="${seg%% *}"
        local s_end="${seg##* }"
        local seg_len=$((s_end - s_start))
        if [[ $seg_idx -eq 0 ]]; then
            vf="select='between(t,$s_start,$s_end)',setpts=N/FRAME_RATE/TB"
        else
            vf="$vf+select='between(t,$s_start,$s_end)',setpts=N/FRAME_RATE/TB"
        fi
        ((seg_idx++))
    done

    # Usar trim + concat para mayor fiabilidad
    local has_audio
    has_audio=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$file" 2>/dev/null | head -1)

    local filter_parts=()
    local concat_inputs=""
    local input_idx=0

    for seg in "${keep_segments[@]}"; do
        local s_start="${seg%% *}"
        local s_end="${seg##* }"
        local seg_len=$((s_end - s_start))
        filter_parts+=(-ss "$s_start" -t "$seg_len" -i "$file")
        if [[ -n "$has_audio" ]]; then
            concat_inputs="${concat_inputs}[${input_idx}:v][${input_idx}:a]"
        else
            concat_inputs="${concat_inputs}[${input_idx}:v]"
        fi
        ((input_idx++))
    done

    local n=${#keep_segments[@]}
    local concat_map=(-map "[outv]")
    local concat_codecs=(-c:v libx264 -preset fast)
    if [[ -n "$has_audio" ]]; then
        concat_inputs="${concat_inputs}concat=n=${n}:v=1:a=1[outv][outa]"
        concat_map=(-map "[outv]" -map "[outa]")
        concat_codecs=(-c:v libx264 -preset fast -c:a aac)
    else
        concat_inputs="${concat_inputs}concat=n=${n}:v=1[outv]"
        concat_codecs=(-c:v libx264 -preset fast -an)
    fi

    mkdir -p "$output_dir"

    local ffmpeg_args=(-y)
    ffmpeg_args+=("${filter_parts[@]}")
    ffmpeg_args+=(-filter_complex "$concat_inputs")
    ffmpeg_args+=("${concat_map[@]}")
    ffmpeg_args+=("${concat_codecs[@]}")
    ffmpeg_args+=(-movflags +faststart "$output_file")

    if ffmpeg "${ffmpeg_args[@]}" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        local new_duration
        new_duration=$(get_duration "$output_file")
        echo -e "${GREEN}Secciones eliminadas:${NC} $output_file (${out_mb}MB, $(format_time "$new_duration"))"
    else
        echo -e "${RED}Error al eliminar secciones${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Extraer clips y unirlos ──────────────────────────────────────────

extract_clips() {
    local file="$1"
    local output_dir="$2"

    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_clips.$ext"

    local duration
    duration=$(get_duration "$file")
    if [[ -z "$duration" || ! "$duration" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}ERROR: No se pudo obtener la duración del vídeo${NC}"
        return 1
    fi

    echo -e "${BOLD}Extrayendo clips:${NC} $file"

    # Extraer cada clip individualmente
    local clip_files=()
    local idx=1

    for clip in "${CUT_CLIPS[@]}"; do
        local start="${clip%%-*}"
        local end="${clip##*-}"
        local start_s=$(time_to_seconds "$start")
        local end_s=$(time_to_seconds "$end")

        if [[ "$start_s" -ge "$end_s" ]]; then
            echo -e "${RED}ERROR: Clip inválido ($start ≥ $end)${NC}"
            return 1
        fi
        if [[ "$end_s" -gt "$duration" ]]; then
            echo -e "${YELLOW}AVISO: Clip $clip excede la duración, se recorta${NC}"
            end_s=$duration
        fi

        local clip_len=$((end_s - start_s))
        local clip_file="/tmp/clip_${filename}_${idx}.mp4"

        echo -e "  ${DIM}Clip $idx: $(format_time "$start_s") → $(format_time "$end_s") (${clip_len}s)${NC}"

        if ! ffmpeg -y -ss "$start_s" -i "$file" -t "$clip_len" -c copy "$clip_file" 2>/dev/null; then
            echo -e "${RED}Error al extraer clip $idx${NC}"
            rm -f /tmp/clip_${filename}_*.mp4
            return 1
        fi
        clip_files+=("$clip_file")
        ((idx++))
    done

    # Crear lista de concat
    local list_file="/tmp/concat_clips_$$.txt"
    printf "file '%s'\n" "${clip_files[@]}" > "$list_file"

    mkdir -p "$output_dir"

    echo -e "  ${DIM}Uniendo ${#clip_files[@]} clips...${NC}"

    if ffmpeg -y -f concat -safe 0 -i "$list_file" -c copy -movflags +faststart "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        local new_duration
        new_duration=$(get_duration "$output_file")
        echo -e "${GREEN}Clips extraídos:${NC} $output_file (${out_mb}MB, $(format_time "$new_duration"))"
    else
        echo -e "${RED}Error al unir clips${NC}"
        rm -f "$output_file"
    fi

    # Limpiar clips temporales
    rm -f /tmp/clip_${filename}_*.mp4 "$list_file"
}

# ── Estabilizar vídeo (vidstab) ──────────────────────────────────────

stabilize_video() {
    local file="$1"
    local output_dir="$2"
    local shakiness="${STAB_SHAKINESS:-5}"

    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_stable.$ext"
    local transforms="/tmp/vidstab_${filename}_$$.trf"

    mkdir -p "$output_dir"

    echo -e "${BOLD}Estabilizando:${NC} $file (shakiness: $shakiness)"

    # Paso 1: Detectar movimientos
    echo -e "  ${DIM}Paso 1/2: Analizando movimientos...${NC}"
    if ! ffmpeg -y -i "$file" -vf "vidstabdetect=shakiness=$shakiness:input=$transforms" -f null - 2>/dev/null; then
        echo -e "${RED}Error en la detección de estabilización${NC}"
        rm -f "$transforms"
        return 1
    fi

    # Paso 2: Aplicar estabilización
    echo -e "  ${DIM}Paso 2/2: Aplicando estabilización...${NC}"
    if ffmpeg -y -i "$file" -vf "vidstabtransform=input=$transforms:zoom=1:smoothing=10:interpol=linear" -c:v libx264 -preset fast -c:a copy -movflags +faststart "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Estabilización completada:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al estabilizar${NC}"
        rm -f "$output_file"
        rm -f "$transforms"
        return 1
    fi
    rm -f "$transforms"
}

# ── Ajustar brillo/contraste/saturación ──────────────────────────────

adjust_video() {
    local file="$1"
    local output_dir="$2"

    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_adjusted.$ext"

    # Construir filtro eq
    local eq_parts=()
    [[ -n "$ADJUST_BRIGHTNESS" ]] && eq_parts+=("brightness=$ADJUST_BRIGHTNESS")
    [[ -n "$ADJUST_CONTRAST" ]] && eq_parts+=("contrast=$ADJUST_CONTRAST")
    [[ -n "$ADJUST_SATURATION" ]] && eq_parts+=("saturation=$ADJUST_SATURATION")
    [[ -n "$ADJUST_GAMMA" ]] && eq_parts+=("gamma=$ADJUST_GAMMA")

    if [[ ${#eq_parts[@]} -eq 0 ]]; then
        echo -e "${RED}ERROR: Indica al menos un ajuste (brightness, contrast, saturation, gamma)${NC}"
        return 1
    fi

    local eq_filter=$(IFS=','; echo "${eq_parts[*]}")

    mkdir -p "$output_dir"

    echo -e "${BOLD}Ajustando:${NC} $file"
    echo -e "  ${DIM}Filtros: $eq_filter${NC}"

    if ffmpeg -y -i "$file" -vf "eq=$eq_filter" -c:v libx264 -preset fast -c:a copy -movflags +faststart "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Ajuste completado:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al ajustar${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Censurar/blur regiones ───────────────────────────────────────────

censor_video() {
    local file="$1"
    local output_dir="$2"

    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_censored.$ext"

    if [[ ${#CENSOR_REGIONS[@]} -eq 0 ]]; then
        echo -e "${RED}ERROR: Indica las regiones a censurar (x:y:w:h)${NC}"
        return 1
    fi

    mkdir -p "$output_dir"

    echo -e "${BOLD}Censurando:${NC} $file"

    # Construir filtro de blur para cada región
    local vf_parts=()
    local idx=0
    for region in "${CENSOR_REGIONS[@]}"; do
        local x="${region%%:*}"
        local rest="${region#*:}"
        local y="${rest%%:*}"
        rest="${rest#*:}"
        local w="${rest%%:*}"
        local h="${rest##*:}"
        vf_parts+=("boxblur=20:20:enable='between(t,0,999999)':x=$x:y=$y:w=$w:h=$h")
        ((idx++))
    done

    local vf=$(IFS=','; echo "${vf_parts[*]}")

    if ffmpeg -y -i "$file" -vf "$vf" -c:v libx264 -preset fast -c:a copy -movflags +faststart "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Censura completada:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al censurar${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Reducir ruido (denoise) ──────────────────────────────────────────

denoise_video() {
    local file="$1"
    local output_dir="$2"
    local strength="${DENOISE_STRENGTH:-50}"

    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_denoised.$ext"

    mkdir -p "$output_dir"

    echo -e "${BOLD}Reduciendo ruido:${NC} $file (fuerza: $strength)"

    # nlmeans: s=sigma (1-30 recomendado, mayor = más denoise)
    local sigma=$((strength / 5))
    [[ "$sigma" -lt 1 ]] && sigma=1
    [[ "$sigma" -gt 30 ]] && sigma=30

    if ffmpeg -y -i "$file" -vf "nlmeans=s=$sigma:p=3:r=9" -c:v libx264 -preset slow -c:a copy -movflags +faststart "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Denoise completado:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al reducir ruido${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Enfocar vídeo (sharpen) ──────────────────────────────────────────

sharpen_video() {
    local file="$1"
    local output_dir="$2"
    local strength="${SHARPEN_STRENGTH:-5}"

    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_sharp.$ext"

    mkdir -p "$output_dir"

    echo -e "${BOLD}Enfocando:${NC} $file (fuerza: $strength)"

    # unsharp: 5:5:strength:5:5:0
    if ffmpeg -y -i "$file" -vf "unsharp=5:5:$strength:5:5:0" -c:v libx264 -preset fast -c:a copy -movflags +faststart "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Sharpen completado:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al enfocar${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Invertir vídeo (reverse) ─────────────────────────────────────────

reverse_video() {
    local file="$1"
    local output_dir="$2"

    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_reverse.$ext"

    mkdir -p "$output_dir"

    echo -e "${BOLD}Invirtiendo:${NC} $file"

    if ffmpeg -y -i "$file" -vf "reverse" -af "areverse" -c:v libx264 -preset fast -c:a copy -movflags +faststart "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Reverse completado:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al invertir${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Detectar y cortar por escenas ────────────────────────────────────

scenes_video() {
    local file="$1"
    local output_dir="$2"
    local threshold="${SCENE_THRESHOLD:-0.3}"

    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"

    mkdir -p "$output_dir"

    echo -e "${BOLD}Detectando escenas:${NC} $file (umbral: $threshold)"

    # Detectar timestamps de escenas
    local timestamps
    timestamps=$(ffmpeg -i "$file" -vf "select='gt(scene,$threshold)',showinfo" -vsync vfr -f null - 2>&1 | grep 'pts_time' | sed 's/.*pts_time:\([0-9.]*\).*/\1/' | sort -n)

    if [[ -z "$timestamps" ]]; then
        echo -e "${YELLOW}No se detectaron cambios de escena${NC}"
        return 0
    fi

    local n_scenes=$(echo "$timestamps" | wc -l)
    echo -e "  ${GREEN}Detectadas $n_scenes escenas${NC}"

    # Mostrar timestamps
    local idx=1
    while IFS= read -r ts; do
        local fmt_ts
        fmt_ts=$(format_time "$(printf '%.0f' "$ts")")
        echo -e "  ${DIM}Escena $idx: $fmt_ts ($ts s)${NC}"
        ((idx++))
    done <<< "$timestamps"

    # Guardar lista de timestamps
    local list_file="$output_dir/${filename}_scenes.txt"
    echo "$timestamps" > "$list_file"
    echo -e "  ${DIM}Timestamps guardados en: $list_file${NC}"

    # Cortar por escenas
    local prev_ts=0
    local clip_idx=1
    while IFS= read -r ts; do
        local start_s=$(printf '%.0f' "$prev_ts")
        local end_s=$(printf '%.0f' "$ts")
        local duration=$((end_s - start_s))
        if [[ "$duration" -gt 0 ]]; then
            local clip_file="$output_dir/${filename}_scene_${clip_idx}.${ext}"
            if ffmpeg -y -ss "$prev_ts" -i "$file" -t "$duration" -c copy "$clip_file" 2>/dev/null; then
                echo -e "  ${GREEN}Escena $clip_idx:${NC} $clip_file"
            fi
            ((clip_idx++))
        fi
        prev_ts="$ts"
    done <<< "$timestamps"

    # Última escena hasta el final
    local clip_file="$output_dir/${filename}_scene_${clip_idx}.${ext}"
    if ffmpeg -y -ss "$prev_ts" -i "$file" -c copy "$clip_file" 2>/dev/null; then
        echo -e "  ${GREEN}Escena $clip_idx:${NC} $clip_file"
    fi

    echo -e "${GREEN}Cortado en $clip_idx escenas${NC}"
}

# ── Extraer keyframes como imágenes ──────────────────────────────────

keyframes_video() {
    local file="$1"
    local output_dir="$2"
    local keyframe_dir="${KEYFRAME_DIR:-$output_dir/keyframes}"

    mkdir -p "$keyframe_dir"

    local filename
    filename=$(basename "$file")
    filename="${filename%.*}"

    echo -e "${BOLD}Extrayendo keyframes:${NC} $file → $keyframe_dir"

    local count
    count=$(ffmpeg -i "$file" -vf "select=eq(pict_type\,I)" -vsync vfr "$keyframe_dir/${filename}_keyframe_%04d.png" 2>&1 | grep 'Output file' | wc -l)

    # Contar archivos creados
    local n_files
    n_files=$(find "$keyframe_dir" -name "${filename}_keyframe_*.png" 2>/dev/null | wc -l)

    echo -e "${GREEN}Extraídos $n_files keyframes${NC} en $keyframe_dir"
}

# ── Cambiar aspect ratio ─────────────────────────────────────────────

aspect_video() {
    local file="$1"
    local output_dir="$2"

    if [[ -z "$ASPECT_RATIO" ]]; then
        echo -e "${RED}ERROR: Indica el ratio de aspecto (ej: 16:9, 4:3, 21:9)${NC}"
        return 1
    fi

    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_${ASPECT_RATIO/:/}.${ext}"

    mkdir -p "$output_dir"

    echo -e "${BOLD}Cambiando aspect ratio:${NC} $file → $ASPECT_RATIO"

    # Convertir ratio a decimal
    local ratio_w="${ASPECT_RATIO%%:*}"
    local ratio_h="${ASPECT_RATIO##*:}"
    local target_ratio=$(echo "scale=4; $ratio_w / $ratio_h" | bc 2>/dev/null)

    # Obtener dimensiones actuales
    local dims
    dims=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$file" 2>/dev/null)
    local cur_w="${dims%%,*}"
    local cur_h="${dims##*,}"
    local cur_ratio=$(echo "scale=4; $cur_w / $cur_h" | bc 2>/dev/null)

    # Calcular filtro
    local vf=""
    if [[ $(echo "$cur_ratio > $target_ratio" | bc 2>/dev/null) -eq 1 ]]; then
        # Vídeo más ancho: pillarbox (barras laterales)
        local new_w=$(echo "scale=0; $cur_h * $target_ratio / 1" | bc 2>/dev/null)
        vf="scale=${new_w}:${cur_h},pad=${cur_w}:${cur_h}:(ow-iw)/2:(oh-ih)/2"
    else
        # Vídeo más alto: letterbox (barras arriba/abajo)
        local new_h=$(echo "scale=0; $cur_w / $target_ratio / 1" | bc 2>/dev/null)
        vf="scale=${cur_w}:${new_h},pad=${cur_w}:${cur_h}:(ow-iw)/2:(oh-ih)/2"
    fi

    if ffmpeg -y -i "$file" -vf "$vf" -c:v libx264 -preset fast -c:a copy -movflags +faststart "$output_file" 2>/dev/null; then
        local out_size
        out_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo 0)
        local out_mb=$((out_size / 1024 / 1024))
        echo -e "${GREEN}Aspect ratio cambiado:${NC} $output_file (${out_mb}MB)"
    else
        echo -e "${RED}Error al cambiar aspect ratio${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Editar metadata ──────────────────────────────────────────────────

metadata_video() {
    local file="$1"
    local output_dir="$2"

    local filename
    filename=$(basename "$file")
    local ext="${filename##*.}"
    filename="${filename%.*}"
    local output_file="$output_dir/${filename}_meta.$ext"

    mkdir -p "$output_dir"

    echo -e "${BOLD}Editando metadata:${NC} $file"

    local meta_args=()
    [[ -n "$METADATA_TITLE" ]] && meta_args+=(-metadata "title=$METADATA_TITLE")
    [[ -n "$METADATA_ARTIST" ]] && meta_args+=(-metadata "artist=$METADATA_ARTIST")
    [[ -n "$METADATA_COMMENT" ]] && meta_args+=(-metadata "comment=$METADATA_COMMENT")

    if [[ ${#meta_args[@]} -eq 0 ]]; then
        echo -e "${RED}ERROR: Indica al menos un campo de metadata (title, artist, comment)${NC}"
        return 1
    fi

    if ffmpeg -y -i "$file" -c copy "${meta_args[@]}" -movflags +faststart "$output_file" 2>/dev/null; then
        echo -e "${GREEN}Metadata actualizada:${NC} $output_file"
    else
        echo -e "${RED}Error al editar metadata${NC}"
        rm -f "$output_file"
        return 1
    fi
}

# ── Comprobar espacio en disco ───────────────────────────────────────

check_disk_space() {
    local dir="$1"
    local min_mb="${2:-500}"

    local available_kb
    available_kb=$(df -k "$dir" 2>/dev/null | awk 'NR==2{print $4}')
    if [[ -n "$available_kb" ]]; then
        local available_mb=$((available_kb / 1024))
        if [[ "$available_mb" -lt "$min_mb" ]]; then
            echo -e "${RED}AVISO: Poco espacio en disco (${available_mb}MB disponibles, mínimo ${min_mb}MB)${NC}"
            return 1
        fi
    fi
    return 0
}

# ── Comprobar colisión de archivo ────────────────────────────────────

check_collision() {
    local file="$1"

    if [[ ! -f "$file" ]]; then
        return 0  # No existe, OK
    fi

    case "$COLLISION" in
        skip)
            echo -e "${YELLOW}Omitido (ya existe): $(basename "$file")${NC}"
            return 1
            ;;
        rename)
            local base="${file%.*}"
            local ext="${file##*.}"
            local idx=1
            while [[ -f "${base}_${idx}.${ext}" ]]; do
                ((idx++))
            done
            echo "${base}_${idx}.${ext}"
            return 0
            ;;
        overwrite|*)
            return 0  # Sobreescribir
            ;;
    esac
}

# ── Guardar checkpoint ───────────────────────────────────────────────

save_checkpoint() {
    local file="$1"
    local status="$2"  # pending|done|failed

    if [[ -z "$CHECKPOINT_FILE" ]]; then
        return 0
    fi

    echo "$file|$status|$(date +%s)" >> "$CHECKPOINT_FILE"
}

# ── Cargar checkpoint ────────────────────────────────────────────────

load_checkpoint() {
    if [[ -z "$CHECKPOINT_FILE" || ! -f "$CHECKPOINT_FILE" ]]; then
        return 1
    fi

    echo -e "${BOLD}Checkpoint encontrado:${NC} $CHECKPOINT_FILE"
    local total_done=$(grep '|done|' "$CHECKPOINT_FILE" 2>/dev/null | wc -l)
    local total_failed=$(grep '|failed|' "$CHECKPOINT_FILE" 2>/dev/null | wc -l)
    echo -e "  ${GREEN}Completados: $total_done${NC}"
    [[ $total_failed -gt 0 ]] && echo -e "  ${RED}Fallidos: $total_failed${NC}"
    echo ""
}

# ── Verificar si archivo ya fue procesado ────────────────────────────

is_checkpoint_done() {
    local file="$1"

    if [[ -z "$CHECKPOINT_FILE" || ! -f "$CHECKPOINT_FILE" ]]; then
        return 1
    fi

    grep -q "^${file}|done|" "$CHECKPOINT_FILE" 2>/dev/null
}

# ── Notificación ─────────────────────────────────────────────────────

send_notification() {
    local title="$1"
    local message="$2"

    if [[ "$NOTIFY" != true ]]; then
        return 0
    fi

    # Intentar notify-send (Linux desktop)
    if command -v notify-send &>/dev/null; then
        notify-send "$title" "$message" 2>/dev/null
    fi

    # Intentar webhook a ntfy.sh (si está configurado)
    if [[ -n "$NTFY_URL" ]]; then
        curl -s -d "$message" "$NTFY_URL" >/dev/null 2>&1
    fi
}

# ── Dry-run / preview ────────────────────────────────────────────────

show_dry_run() {
    local cmd="$1"
    echo -e "${YELLOW}[DRY-RUN]${NC} $cmd"
}

run_or_dry() {
    if [[ "$DRY_RUN" == true ]]; then
        show_dry_run "$*"
        return 0
    fi
    "$@"
}

# ── Estimación de tiempo ─────────────────────────────────────────────

declare -A FILE_TIMES_START
declare -A FILE_TIMES_END

track_time_start() {
    local file="$1"
    FILE_TIMES_START["$file"]=$(date +%s)
}

track_time_end() {
    local file="$1"
    FILE_TIMES_END["$file"]=$(date +%s)
}

estimate_remaining() {
    local current_idx="$1"
    local total="$2"

    if [[ "$current_idx" -le 1 ]]; then
        return 0
    fi

    # Calcular tiempo promedio por archivo
    local total_elapsed=0
    local count=0
    for file in "${!FILE_TIMES_END[@]}"; do
        if [[ -n "${FILE_TIMES_START[$file]}" && -n "${FILE_TIMES_END[$file]}" ]]; then
            local elapsed=$((${FILE_TIMES_END[$file]} - FILE_TIMES_START[$file]))
            total_elapsed=$((total_elapsed + elapsed))
            ((count++))
        fi
    done

    if [[ "$count" -gt 0 ]]; then
        local avg_time=$((total_elapsed / count))
        local remaining=$((total - current_idx))
        local eta=$((avg_time * remaining))
        local eta_fmt
        eta_fmt=$(format_time "$eta")
        echo -e "  ${DIM}Tiempo estimado restante: $eta_fmt${NC}"
    fi
}

# ── Previsualización de vídeo (abrir en el host) ──────────────────────

# Busca VLC instalado en Windows (rutas habituales)
find_vlc() {
    local cand win_user=""
    if command -v cmd.exe &>/dev/null; then
        win_user=$(cmd.exe /c echo %USERNAME% 2>/dev/null | tr -d '\r')
    fi
    for cand in \
        "/mnt/c/Program Files/VideoLAN/VLC/vlc.exe" \
        "/mnt/c/Program Files (x86)/VideoLAN/VLC/vlc.exe" \
        "/mnt/c/Users/${win_user}/AppData/Local/Programs/VLC/vlc.exe" \
        "/mnt/c/Users/${win_user}/AppData/Local/VideoLAN/VLC/vlc.exe"
    do
        if [[ -n "$cand" && -f "$cand" ]]; then
            printf '%s' "$cand"
            return 0
        fi
    done
    return 1
}

# Convierte /mnt/c/... (o /app/... con HOST_PROJECT) a ruta Windows C:\...
to_windows_path() {
    local p="$1"
    if [[ -n "${HOST_PROJECT:-}" && "$p" == /app/* ]]; then
        p="${HOST_PROJECT}/${p#/app/}"
    fi
    if [[ "$p" =~ ^/mnt/([a-zA-Z])/(.*)$ ]]; then
        local drive="${BASH_REMATCH[1]}"
        local rest="${BASH_REMATCH[2]}"
        drive=$(printf '%s' "$drive" | tr 'a-z' 'A-Z')
        printf '%s:\\%s' "$drive" "${rest//\//\\}"
        return 0
    fi
    printf '%s' "${p//\//\\}"
}

# Abre un vídeo con VLC (o el reproductor por defecto). Si se ejecuta
# dentro del contenedor Docker, escribe una petición para el watcher del host.
host_open_video() {
    local file="$1"
    if [[ "$file" != /* ]]; then
        file="$(cd "$(dirname "$file")" 2>/dev/null && pwd)/$(basename "$file")"
    fi
    if [[ -d /mnt/c ]]; then
        local vlc="" winpath
        vlc=$(find_vlc) || true
        winpath=$(to_windows_path "$file")
        if [[ -n "$vlc" ]]; then
            "$vlc" "$winpath" >/dev/null 2>&1 &
            return 0
        fi
        if command -v cmd.exe &>/dev/null; then
            cmd.exe /c start "" "$winpath" >/dev/null 2>&1 &
            return 0
        fi
        echo -e "${YELLOW}No se encontró VLC. Instálalo o abre el vídeo manualmente.${NC}"
        return 1
    fi
    if command -v xdg-open &>/dev/null; then
        xdg-open "$file" >/dev/null 2>&1 &
        return 0
    fi
    if [[ -d "$SCRIPT_DIR" ]]; then
        printf '%s\n' "$file" > "$SCRIPT_DIR/.midu_preview_req"
        echo -e "  ${DIM}Petición de previsualización enviada al host.${NC}"
        return 0
    fi
    echo -e "${YELLOW}No se puede abrir el vídeo desde este entorno.${NC}"
    return 1
}

# Pregunta en el flujo interactivo (cut) si se desea visualizar el vídeo
ask_preview() {
    local file="$1"
    local val
    read -rp "  → ¿Visualizar el vídeo para ver los tiempos? [S/n]: " val
    case "$val" in
        ""|[Ss]) ;;
        [Nn]) return 1 ;;
        *) echo -e "${RED}Respuesta no válida${NC}"; return 1 ;;
    esac
    if ! host_open_video "$file"; then
        return 1
    fi
    read -rp "  → Pulsa Enter cuando hayas visto el vídeo (o 'N' para continuar): " val
    return 0
}

# ── Reintentar archivos fallidos ─────────────────────────────────────

retry_failed_files() {
    local failed_list="$1"
    local output_dir="$2"

    if [[ ! -f "$failed_list" ]]; then
        return 0
    fi

    local failed_files=()
    while IFS= read -r line; do
        [[ -n "$line" ]] && failed_files+=("$line")
    done < "$failed_list"

    if [[ ${#failed_files[@]} -eq 0 ]]; then
        return 0
    fi

    echo ""
    echo -e "${BOLD}Archivos fallidos:${NC} ${#failed_files[@]}"
    read -rp "  ¿Reintentar? [S/n]: " val
    if [[ "$val" =~ ^[Nn] ]]; then
        return 0
    fi

    for file in "${failed_files[@]}"; do
        if [[ -f "$file" ]]; then
            echo -e "${BOLD}Reintentando:${NC} $file"
            convertir_archivo "$file" "$output_dir"
        fi
    done
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

    # Descargar subtítulos automáticamente
    if [[ "$SUBS_DOWNLOAD" == true ]]; then
        ytdlp_args+=(--write-subs --write-auto-subs --sub-langs "$SUBS_LANGS" --sub-format srt)
    fi

    ytdlp_args+=(--merge-output-format mp4 -o "$output_dir/%(title)s.%(ext)s" "$url")

    local ytdlp_exit=0
    if [[ "$VERBOSE" == true ]]; then
        yt-dlp "${ytdlp_args[@]}" || ytdlp_exit=$?
    else
        yt-dlp "${ytdlp_args[@]}" 2>&1 | tail -5 || ytdlp_exit=${PIPESTATUS[0]}
    fi

    if [[ $ytdlp_exit -eq 0 ]]; then
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
        # Escapar comillas simples en nombres de archivo para ffmpeg concat
        local escaped_f="${f//\'/\'\\\'\'}"
        echo "file '$escaped_f'" >> "$list_file"
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

buscar_archivos() {
    # Si ya hay archivos seleccionados en el menú, usar esos
    if [[ ${#SELECTED_FILES[@]} -gt 0 ]]; then
        archivos=("${SELECTED_FILES[@]}")
        total=${#archivos[@]}
        saltados=0
        return 0
    fi

    # Selección única desde el menú: usar solo ese archivo
    if [[ -n "$SELECTED_FILE" ]]; then
        archivos=("$SELECTED_FILE")
        total=${#archivos[@]}
        saltados=0
        return 0
    fi

    local ext_array
    IFS=',' read -ra ext_array <<< "$EXTENSIONS"

    archivos=()
    saltados=0
    for ext in "${ext_array[@]}"; do
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
    if [[ -z "$choice" || ! "$choice" =~ ^[0-9]+$ || "$choice" -lt 1 || "$choice" -gt ${#all_files[@]} ]]; then
        echo -e "${RED}Selección no válida${NC}"
        return 1
    fi

    SELECTED_FILE="${all_files[$((choice - 1))]}"
    echo -e "  → ${CYAN}$(basename "$SELECTED_FILE")${NC}"
    echo ""
    return 0
}

# ── Seleccionar múltiples archivos ────────────────────────────────

select_video_files() {
    local dir="$1"

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
        SELECTED_FILES=("${all_files[0]}")
        echo -e "  → ${CYAN}$(basename "${SELECTED_FILES[0]}")${NC}"
        echo ""
        return 0
    fi

    echo -e "  ${DIM}Ejemplo: 1,3,5 o 1-5 o 'all' para todos${NC}"
    read -rp "  → Selecciona: " choice
    echo ""

    SELECTED_FILES=()

    if [[ "$choice" == "all" || "$choice" == "a" ]]; then
        SELECTED_FILES=("${all_files[@]}")
    elif [[ "$choice" =~ ^[0-9]+-[0-9]+$ ]]; then
        # Rango: 1-5
        local start="${choice%%-*}"
        local end="${choice##*-}"
        if [[ "$start" -ge 1 && "$end" -le ${#all_files[@]} && "$start" -le "$end" ]]; then
            for ((j=start-1; j<end; j++)); do
                SELECTED_FILES+=("${all_files[$j]}")
            done
        else
            echo -e "${RED}Rango no válido${NC}"
            return 1
        fi
    elif [[ "$choice" =~ ^[0-9,]+$ ]]; then
        # Lista: 1,3,5
        IFS=',' read -ra indices <<< "$choice"
        for idx in "${indices[@]}"; do
            idx=$(echo "$idx" | xargs)
            if [[ "$idx" -ge 1 && "$idx" -le ${#all_files[@]} ]]; then
                SELECTED_FILES+=("${all_files[$((idx - 1))]}")
            else
                echo -e "${RED}Índice $idx fuera de rango${NC}"
                return 1
            fi
        done
    else
        # Un solo número
        if [[ "$choice" -ge 1 && "$choice" -le ${#all_files[@]} ]]; then
            SELECTED_FILES=("${all_files[$((choice - 1))]}")
        else
            echo -e "${RED}Selección no válida${NC}"
            return 1
        fi
    fi

    echo -e "  ${CYAN}Seleccionados: ${#SELECTED_FILES[@]} archivo(s)${NC}"
    for f in "${SELECTED_FILES[@]}"; do
        echo -e "    → $(basename "$f")"
    done
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
        echo -e "  ${DIM}Archivo: $CONF_FILE${NC}"
        echo ""
        echo -e "  ${BOLD}Contenido:${NC}"
        echo -e "    $(jq -r '"Entrada:     " + (.inputDir // "")' "$CONF_FILE" 2>/dev/null)"
        echo -e "    $(jq -r '"Salida:      " + (.outputDir // "")' "$CONF_FILE" 2>/dev/null)"
        echo -e "    $(jq -r '"Extensiones: " + (.extensions // "")' "$CONF_FILE" 2>/dev/null)"
        echo -e "    $(jq -r '"Progreso:    " + if .verbose == true then "detallado" else "resumen" end' "$CONF_FILE" 2>/dev/null)"
        saved_modes=$(jq -r '.modes | keys | join(", ")' "$CONF_FILE" 2>/dev/null)
        [[ -n "$saved_modes" ]] && echo -e "  ${BOLD}Modos guardados:${NC} ${CYAN}$saved_modes${NC}"
        echo ""
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
    echo -e "    ${GREEN} 1)${NC} Descargar vídeo       ${DIM}— YouTube, Twitch, Kick, TikTok, +1000${NC}"
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
    echo -e "    ${GREEN}18)${NC} Estabilizar           ${DIM}— Quitar temblor (vidstab)${NC}"
    echo -e "    ${GREEN}19)${NC} Ajustar imagen        ${DIM}— Brillo, contraste, saturación${NC}"
    echo -e "    ${GREEN}20)${NC} Censurar              ${DIM}— Pixelar/caras, matrículas${NC}"
    echo -e "    ${GREEN}21)${NC} Reducir ruido         ${DIM}— Denoise para vídeo viejo${NC}"
    echo -e "    ${GREEN}22)${NC} Enfocar               ${DIM}— Sharpen para vídeo borroso${NC}"
    echo -e "    ${GREEN}23)${NC} Invertir              ${DIM}— Reproducir al revés${NC}"
    echo -e "    ${GREEN}24)${NC} Cortar por escenas    ${DIM}— Auto-detectar cambios${NC}"
    echo -e "    ${GREEN}25)${NC} Extraer keyframes     ${DIM}— Sacar imágenes I-frame${NC}"
    echo -e "    ${GREEN}26)${NC} Cambiar aspect ratio  ${DIM}— 16:9, 4:3, 21:9${NC}"
    echo -e "    ${GREEN}27)${NC} Editar metadata       ${DIM}— Título, autor, etc.${NC}"
    echo ""
    read -rp "  → Selecciona [1-27]: " mode_val
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
        18) MODE="stabilize" ;;
        19) MODE="adjust" ;;
        20) MODE="censor" ;;
        21) MODE="denoise" ;;
        22) MODE="sharpen" ;;
        23) MODE="reverse" ;;
        24) MODE="scenes" ;;
        25) MODE="keyframes" ;;
        26) MODE="aspect" ;;
        27) MODE="metadata" ;;
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
            echo -e "  ${DIM}Soporta: YouTube, Twitch, Kick, TikTok, Instagram, Twitter/X,"
            echo -e "  Facebook, Vimeo, Dailymotion, Reddit, SoundCloud, y 1000+ sitios${NC}"
            read -rp "  → URL: " URL
            [[ -z "$URL" ]] && { echo -e "${RED}Se requiere URL${NC}"; exit 1; }

            # Validar que la URL esté soportada
            echo -e "  ${DIM}Comprobando URL...${NC}"
            if ! yt-dlp --simulate --no-warnings "$URL" >/dev/null 2>&1; then
                echo -e "${RED}ERROR: URL no soportada o no válida${NC}"
                echo -e "  ${DIM}yt-dlp no puede descargar de este sitio${NC}"
                echo -e "  ${DIM}Lista de sitios soportados: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md${NC}"
                exit 1
            fi
            echo -e "  ${GREEN}URL válida${NC}"
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

            # Seleccionar archivo(s) - multi-selección para modos batch
            case "$MODE" in
                cut|convert|gif|thumbnail|rotate|crop|fade|normalize|watermark|deinterlace|fps|speed|subtitles|audio-only)
                    echo -e "${BOLD}  Selecciona los vídeos${NC}"
                    if ! select_video_files "$INPUT_DIR"; then
                        exit 1
                    fi
                    ;;
                *)
                    echo -e "${BOLD}  Selecciona el vídeo${NC}"
                    if ! select_video_file "$INPUT_DIR" "$MODE"; then
                        exit 1
                    fi
                    ;;
            esac
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

            # Nombre de salida personalizado (solo si hay 1 archivo)
            if [[ ${#SELECTED_FILES[@]} -eq 1 ]]; then
                SELECTED_FILE="${SELECTED_FILES[0]}"
                base_name=$(basename "$SELECTED_FILE")
                base_name="${base_name%.*}"
                ask_output_name "$base_name" "$(basename "$SELECTED_FILE" | sed 's/.*\.//')"
            elif [[ ${#SELECTED_FILES[@]} -gt 1 ]]; then
                echo -e "  ${DIM}(${#SELECTED_FILES[@]} archivos, cada uno mantendrá su nombre)${NC}"
                echo ""
            fi
            ;;
    esac

    # ══════════════════════════════════════════════════════════════════
    #  PASO 4: Parámetros específicos de cada modo
    # ══════════════════════════════════════════════════════════════════

    case "$MODE" in

        cut)
            cut_archivos=()
            if [[ ${#SELECTED_FILES[@]} -gt 0 ]]; then
                cut_archivos=("${SELECTED_FILES[@]}")
            elif [[ -n "$SELECTED_FILE" ]]; then
                cut_archivos=("$SELECTED_FILE")
            fi

            if [[ ${#cut_archivos[@]} -eq 0 ]]; then
                echo -e "${RED}No hay archivos seleccionados${NC}"
                exit 1
            fi

            FILE_CUT=()
            for f in "${cut_archivos[@]}"; do
                echo -e "${BOLD}  Vídeo ${CYAN}$(basename "$f")${NC}${BOLD} (${#cut_archivos[@]} en total)${NC}"
                echo ""

                ask_preview "$f"
                echo ""

                echo -e "${BOLD}  Tipo de corte${NC}"
                echo -e "    ${GREEN}1)${NC} Cortar un trozo     ${DIM}— Mantener solo ese trozo${NC}"
                echo -e "    ${GREEN}2)${NC} Eliminar secciones  ${DIM}— Quitar partes del vídeo${NC}"
                echo -e "    ${GREEN}3)${NC} Extraer clips       ${DIM}— Sacar varios trozos y unirlos${NC}"
                cut_def=1
                case "${CUT_MODE:-normal}" in
                    remove)  cut_def=2 ;;
                    extract) cut_def=3 ;;
                esac
                read -rp "  → [1-3] (default: $cut_def): " cut_val
                echo ""
                case "$cut_val" in
                    2) CUT_MODE="remove" ;;
                    3) CUT_MODE="extract" ;;
                    1) CUT_MODE="normal" ;;
                    "") : ;;
                    *) echo -e "${RED}Opción no válida${NC}"; exit 1 ;;
                esac

                if [[ "$CUT_MODE" == "normal" ]]; then
                    echo -e "${BOLD}  Tiempo de corte${NC}"
                    echo -e "  ${DIM}Formato: HH:MM:SS o MM:SS o segundos${NC}"
                    echo -e "  ${DIM}Vacío = conservar el valor actual (o dejar sin límite)${NC}"
                    read -rp "  → Tiempo inicio [$START_TIME]: " t_start
                    [[ -n "$t_start" ]] && START_TIME="$t_start"
                    read -rp "  → Tiempo fin [$END_TIME]: " t_end
                    [[ -n "$t_end" ]] && END_TIME="$t_end"
                    [[ -z "$START_TIME" && -z "$END_TIME" ]] && { echo -e "${RED}Indica al menos un tiempo${NC}"; exit 1; }
                else
                    echo -e "${BOLD}  Secciones a ${CUT_MODE}${NC}"
                    echo -e "  ${DIM}Formato: inicio-fin separados por coma${NC}"
                    echo -e "  ${DIM}Ejemplo: 00:01:00-00:02:30,00:05:00-00:07:15${NC}"
                    if [[ "$CUT_MODE" == "remove" ]]; then
                        echo -e "  ${DIM}Estas secciones se eliminarán del vídeo${NC}"
                    else
                        echo -e "  ${DIM}Estos clips se extraerán y unirán en un solo vídeo${NC}"
                    fi
                    if [[ ${#CUT_CLIPS[@]} -gt 0 ]]; then
                        echo -e "  ${DIM}Actual: ${CUT_CLIPS[*]}${NC}"
                    fi
                    echo -e "  ${DIM}Vacío = conservar los actuales${NC}"
                    read -rp "  → Clips: " clips_input
                    if [[ -n "$clips_input" ]]; then
                        IFS=',' read -ra CUT_CLIPS <<< "$clips_input"
                    elif [[ ${#CUT_CLIPS[@]} -eq 0 ]]; then
                        echo -e "${RED}Indica al menos un clip${NC}"; exit 1
                    fi
                    echo ""
                    echo -e "  ${CYAN}Clips a ${CUT_MODE}:${NC}"
                    for clip in "${CUT_CLIPS[@]}"; do
                        echo -e "    → $clip"
                    done
                fi
                echo ""

                cut_clips_csv=""
                if [[ ${#CUT_CLIPS[@]} -gt 0 ]]; then
                    cut_clips_csv=$(IFS=';'; printf '%s' "${CUT_CLIPS[*]}")
                fi
                FILE_CUT["$f"]="${CUT_MODE}|${START_TIME}|${END_TIME}|${cut_clips_csv}"
                echo -e "  ${GREEN}✔ Configuración guardada${NC} para ${CYAN}$(basename "$f")${NC}"
                if [[ "$CUT_MODE" == "normal" ]]; then
                    echo -e "  ${DIM}  Modo: ${CUT_MODE} | Inicio: ${START_TIME:-—} | Fin: ${END_TIME:-—}${NC}"
                else
                    echo -e "  ${DIM}  Modo: ${CUT_MODE} | Clips: ${cut_clips_csv:-—}${NC}"
                fi
                echo ""
            done
            unset cut_archivos cut_clips_csv f cut_def
            ;;

        convert)
            echo -e "${BOLD}  Red social (atajo)${NC}"
            echo -e "    ${GREEN}0)${NC} Ninguna — Manual"
            echo -e "    ${GREEN}1)${NC} WhatsApp  ${GREEN}2)${NC} Telegram  ${GREEN}3)${NC} Instagram"
            echo -e "    ${GREEN}4)${NC} TikTok    ${GREEN}5)${NC} YouTube   ${GREEN}6)${NC} Twitter"
            echo -e "    ${GREEN}7)${NC} Facebook"
            social_def=0
            case "$SOCIAL" in
                whatsapp)   social_def=1 ;;
                telegram)   social_def=2 ;;
                instagram)  social_def=3 ;;
                tiktok)     social_def=4 ;;
                youtube)    social_def=5 ;;
                twitter|tw) social_def=6 ;;
                facebook|fb) social_def=7 ;;
            esac
            read -rp "  → [0-7] (default: $social_def): " val
            case "$val" in
                0) SOCIAL="" ;;
                1) apply_social_preset "whatsapp" ;;
                2) apply_social_preset "telegram" ;;
                3) apply_social_preset "instagram" ;;
                4) apply_social_preset "tiktok" ;;
                5) apply_social_preset "youtube" ;;
                6) apply_social_preset "twitter" ;;
                7) apply_social_preset "facebook" ;;
                "") : ;;
                *) echo -e "${RED}Opción no válida${NC}"; exit 1 ;;
            esac
            echo ""

            echo -e "${BOLD}  Preset de calidad${NC}"
            echo -e "    ${GREEN}1)${NC} ultrafast — Muy rápido, poco peso"
            echo -e "    ${GREEN}2)${NC} web       — Rápido, buen balance"
            echo -e "    ${GREEN}3)${NC} default   — Equilibrado"
            echo -e "    ${GREEN}4)${NC} archive   — Alta calidad"
            echo -e "    ${GREEN}5)${NC} quality   — Máxima calidad"
            preset_def=3
            case "$PRESET" in
                ultrafast) preset_def=1 ;;
                web)       preset_def=2 ;;
                archive)   preset_def=4 ;;
                quality)   preset_def=5 ;;
            esac
            read -rp "  → [1-5] (default: $preset_def): " val
            case "$val" in
                1) PRESET="ultrafast" ;;
                2) PRESET="web" ;;
                4) PRESET="archive" ;;
                5) PRESET="quality" ;;
                3) PRESET="default" ;;
                "") : ;;
                *) echo -e "${RED}Opción no válida${NC}"; exit 1 ;;
            esac
            echo ""

            echo -e "${BOLD}  Códec de vídeo${NC}"
            echo -e "    ${GREEN}1)${NC} h264 — Máxima compatibilidad"
            echo -e "    ${GREEN}2)${NC} hevc — Mejor calidad/menor tamaño (más lento)"
            echo -e "    ${GREEN}3)${NC} av1  — Máxima eficiencia (muy lento)"
            echo -e "    ${GREEN}4)${NC} vp9  — Buen equilibrio para web"
            codec_def=1
            case "$VIDEO_CODEC" in
                hevc) codec_def=2 ;;
                av1)  codec_def=3 ;;
                vp9)  codec_def=4 ;;
            esac
            read -rp "  → [1-4] (default: $codec_def): " val
            case "$val" in
                1) VIDEO_CODEC="h264" ;;
                2) VIDEO_CODEC="hevc" ;;
                3) VIDEO_CODEC="av1" ;;
                4) VIDEO_CODEC="vp9" ;;
                "") : ;;
                *) echo -e "${RED}Opción no válida${NC}"; exit 1 ;;
            esac
            echo ""

            echo -e "${BOLD}  Resolución${NC}"
            echo -e "    ${GREEN}1)${NC} original  ${GREEN}2)${NC} 4k  ${GREEN}3)${NC} 1080  ${GREEN}4)${NC} 720  ${GREEN}5)${NC} 480  ${GREEN}6)${NC} 360"
            res_def=1
            case "$RESOLUTION" in
                original) res_def=1 ;;
                4k)       res_def=2 ;;
                1080)     res_def=3 ;;
                720)      res_def=4 ;;
                480)      res_def=5 ;;
                360)      res_def=6 ;;
            esac
            read -rp "  → [1-6] (default: $res_def): " val
            case "$val" in
                1) RESOLUTION="original" ;;
                2) RESOLUTION="4k" ;;
                3) RESOLUTION="1080" ;;
                4) RESOLUTION="720" ;;
                5) RESOLUTION="480" ;;
                6) RESOLUTION="360" ;;
                "") : ;;
                *) echo -e "${RED}Opción no válida${NC}"; exit 1 ;;
            esac
            echo ""

            echo -e "${BOLD}  Tamaño máximo en GB${NC} ${DIM}(vacío = sin límite)${NC}"
            read -rp "  → ${MAX_SIZE:-sin límite}GB : " val
            if [[ -n "$val" ]]; then
                MAX_SIZE="$val"
            elif [[ -z "$MAX_SIZE" && -z "$val" ]]; then
                :
            fi
            echo ""
            ;;

        gif)
            echo -e "${BOLD}  FPS del GIF${NC}"
            echo -e "  ${DIM}Más FPS = más suave pero más pesado${NC}"
            echo -e "    ${GREEN}1)${NC} 10 FPS — Ligero"
            echo -e "    ${GREEN}2)${NC} 15 FPS — Normal"
            echo -e "    ${GREEN}3)${NC} 25 FPS — Suave"
            gif_fps_def="${GIF_FPS:-10}"
            read -rp "  → [1-3] o número personalizado (default: $gif_fps_def): " val
            case "$val" in
                1) GIF_FPS=10 ;;
                2) GIF_FPS=15 ;;
                3) GIF_FPS=25 ;;
                "") : ;;
                *) [[ -n "$val" ]] && GIF_FPS="$val" ;;
            esac
            echo ""

            echo -e "${BOLD}  Tamaño del GIF${NC}"
            echo -e "    ${GREEN}1)${NC} 320px — Pequeño"
            echo -e "    ${GREEN}2)${NC} 480px — Mediano"
            echo -e "    ${GREEN}3)${NC} 640px — Grande"
            gif_scale_def="${GIF_SCALE:-480:-1}"
            read -rp "  → [1-3] o WxH personalizado (default: $gif_scale_def): " val
            case "$val" in
                1) GIF_SCALE="320:-1" ;;
                2) GIF_SCALE="480:-1" ;;
                3) GIF_SCALE="640:-1" ;;
                "") : ;;
                *) [[ -n "$val" ]] && GIF_SCALE="$val" ;;
            esac
            echo ""
            ;;

        thumbnail)
            echo -e "${BOLD}  Timestamp del frame${NC}"
            echo -e "  ${DIM}En qué momento del vídeo quieres la captura${NC}"
            echo -e "    ${GREEN}1)${NC} 00:00:01 — Primer segundo"
            echo -e "    ${GREEN}2)${NC} 00:00:05 — 5 segundos"
            echo -e "    ${GREEN}3)${NC} Mitad del vídeo"
            thumb_def="${THUMBNAIL_TIME:-00:00:01}"
            read -rp "  → [1-3] o tiempo personalizado (default: $thumb_def): " val
            case "$val" in
                1) THUMBNAIL_TIME="00:00:01" ;;
                2) THUMBNAIL_TIME="00:00:05" ;;
                3)
                    thumb_file="${SELECTED_FILES[0]:-$SELECTED_FILE}"
                    dur=$(get_duration "$thumb_file")
                    if [[ -n "$dur" && "$dur" =~ ^[0-9]+$ ]]; then
                        mid=$((dur / 2))
                        THUMBNAIL_TIME=$(format_time "$mid")
                    else
                        THUMBNAIL_TIME="00:00:05"
                    fi
                    ;;
                "") : ;;
                *) [[ -n "$val" ]] && THUMBNAIL_TIME="$val" ;;
            esac
            echo ""
            ;;

        rotate)
            echo -e "${BOLD}  ¿Cuánto quieres girar el vídeo?${NC}"
            echo -e "    ${GREEN}1)${NC} 90°  — Girar a la derecha"
            echo -e "    ${GREEN}2)${NC} 180° — Dar la vuelta"
            echo -e "    ${GREEN}3)${NC} 270° — Girar a la izquierda"
            rot_def="${ROTATE_DEGREES:-—}"
            case "$ROTATE_DEGREES" in
                90)  rot_def=1 ;;
                180) rot_def=2 ;;
                270) rot_def=3 ;;
            esac
            read -rp "  → [1-3] (default: $rot_def): " val
            case "$val" in
                1) ROTATE_DEGREES=90 ;;
                2) ROTATE_DEGREES=180 ;;
                3) ROTATE_DEGREES=270 ;;
                "") : ;;
                *) [[ -n "$val" ]] && ROTATE_DEGREES="$val" ;;
            esac
            [[ -z "$ROTATE_DEGREES" ]] && { echo -e "${RED}Selecciona grados${NC}"; exit 1; }
            echo ""
            ;;

        crop)
            echo -e "${BOLD}  Tamaño de recorte (Ancho:Alto)${NC}"
            echo -e "  ${DIM}Ejemplo: 640:480 = recortar a 640x480 píxeles${NC}"
            echo -e "  ${DIM}El vídeo se recortará desde el centro${NC}"
            read -rp "  → W:H [$CROP_SIZE]: " csize
            [[ -n "$csize" ]] && CROP_SIZE="$csize"
            [[ -z "$CROP_SIZE" ]] && { echo -e "${RED}Indica el tamaño${NC}"; exit 1; }
            echo ""
            ;;

        fade)
            echo -e "${BOLD}  Duración del efecto fade${NC}"
            echo -e "  ${DIM}Cuántos segundos dura el aparecer y desaparecer${NC}"
            echo -e "    ${GREEN}1)${NC} 0.5s — Rápido"
            echo -e "    ${GREEN}2)${NC} 1s   — Normal"
            echo -e "    ${GREEN}3)${NC} 2s   — Lento"
            fade_def="${FADE_SECONDS:-1}"
            read -rp "  → [1-3] o segundos personalizados (default: $fade_def): " val
            case "$val" in
                1) FADE_SECONDS=0.5 ;;
                2) FADE_SECONDS=1 ;;
                3) FADE_SECONDS=2 ;;
                "") : ;;
                *) [[ -n "$val" ]] && FADE_SECONDS="$val" ;;
            esac
            echo ""
            ;;

        watermark)
            echo -e "${BOLD}  Imagen de marca de agua${NC}"
            echo -e "  ${DIM}Ruta completa del archivo PNG o JPG${NC}"
            read -rp "  → Ruta [$WATERMARK_FILE]: " wm_file
            [[ -n "$wm_file" ]] && WATERMARK_FILE="$wm_file"
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
            fps_def="${TARGET_FPS:-—}"
            case "$TARGET_FPS" in
                24) fps_def=1 ;;
                30) fps_def=2 ;;
                60) fps_def=3 ;;
                120) fps_def=4 ;;
            esac
            read -rp "  → [1-4] o número personalizado (default: $fps_def): " val
            case "$val" in
                1) TARGET_FPS=24 ;;
                2) TARGET_FPS=30 ;;
                3) TARGET_FPS=60 ;;
                4) TARGET_FPS=120 ;;
                "") : ;;
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
            speed_def="${SPEED:-—}"
            case "$SPEED" in
                0.25) speed_def=1 ;;
                0.5)  speed_def=2 ;;
                0.75) speed_def=3 ;;
                1.5)  speed_def=4 ;;
                2)    speed_def=5 ;;
                4)    speed_def=6 ;;
            esac
            read -rp "  → [1-6] o factor personalizado (default: $speed_def): " val
            case "$val" in
                1) SPEED=0.25 ;;
                2) SPEED=0.5 ;;
                3) SPEED=0.75 ;;
                4) SPEED=1.5 ;;
                5) SPEED=2 ;;
                6) SPEED=4 ;;
                "") : ;;
                *) [[ -n "$val" ]] && SPEED="$val" ;;
            esac
            [[ -z "$SPEED" ]] && { echo -e "${RED}Indica la velocidad${NC}"; exit 1; }
            echo ""
            ;;

        subtitles)
            echo -e "${BOLD}  Tipo de subtítulos${NC}"
            echo -e "    ${GREEN}1)${NC} Soft — Se pueden quitar después"
            echo -e "    ${GREEN}2)${NC} Hard — Siempre visibles en el vídeo"
            sub_def=1
            [[ -n "$SUBTITLE_SOFT" ]] && sub_def=1
            [[ -n "$SUBTITLE_HARD" ]] && sub_def=2
            read -rp "  → [1-2] (default: $sub_def): " val
            echo ""
            case "$val" in
                1)
                    echo -e "${BOLD}  Archivo de subtítulos${NC}"
                    read -rp "  → Ruta (.srt) [$SUBTITLE_SOFT]: " sub_path
                    [[ -n "$sub_path" ]] && SUBTITLE_SOFT="$sub_path"
                    [[ -z "$SUBTITLE_SOFT" || ! -f "$SUBTITLE_SOFT" ]] && { echo -e "${RED}Archivo no encontrado${NC}"; exit 1; }
                    ;;
                2)
                    echo -e "${BOLD}  Archivo de subtítulos${NC}"
                    read -rp "  → Ruta (.srt) [$SUBTITLE_HARD]: " sub_path
                    [[ -n "$sub_path" ]] && SUBTITLE_HARD="$sub_path"
                    [[ -z "$SUBTITLE_HARD" || ! -f "$SUBTITLE_HARD" ]] && { echo -e "${RED}Archivo no encontrado${NC}"; exit 1; }
                    ;;
                "") : ;;
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
            out_fmt_def=1
            case "$OUTPUT_FORMAT" in
                mp3)  out_fmt_def=1 ;;
                m4a)  out_fmt_def=2 ;;
                flac) out_fmt_def=3 ;;
                wav)  out_fmt_def=4 ;;
                opus) out_fmt_def=5 ;;
            esac
            read -rp "  → [1-5] (default: $out_fmt_def): " val
            case "$val" in
                1) OUTPUT_FORMAT="mp3" ;;
                2) OUTPUT_FORMAT="m4a" ;;
                3) OUTPUT_FORMAT="flac" ;;
                4) OUTPUT_FORMAT="wav" ;;
                5) OUTPUT_FORMAT="opus" ;;
                "") : ;;
                *) echo -e "${RED}Opción no válida${NC}"; exit 1 ;;
            esac
            echo ""

            echo -e "${BOLD}  Nombre del archivo de audio${NC}"
            audio_base=
            audio_base=$(basename "${SELECTED_FILES[0]:-$SELECTED_FILE}")
            audio_base="${audio_base%.*}"
            ask_output_name "$audio_base" "$OUTPUT_FORMAT"
            ;;

        stabilize)
            echo -e "${BOLD}  Nivel de estabilización${NC}"
            echo -e "    ${GREEN}1)${NC} 3  — Suave"
            echo -e "    ${GREEN}2)${NC} 5  — Normal (recomendado)"
            echo -e "    ${GREEN}3)${NC} 7  — Fuerte"
            echo -e "    ${GREEN}4)${NC} 10 — Máximo"
            stab_def=2
            case "$STAB_SHAKINESS" in
                3)  stab_def=1 ;;
                7)  stab_def=3 ;;
                10) stab_def=4 ;;
            esac
            read -rp "  → [1-4] (default: $stab_def): " val
            case "$val" in
                1) STAB_SHAKINESS=3 ;;
                2) STAB_SHAKINESS=5 ;;
                3) STAB_SHAKINESS=7 ;;
                4) STAB_SHAKINESS=10 ;;
                "") : ;;
                *) [[ -n "$val" ]] && STAB_SHAKINESS="$val" ;;
            esac
            echo ""
            ;;

        adjust)
            echo -e "${BOLD}  Ajustes de imagen${NC}"
            echo -e "  ${DIM}Vacío = conservar el valor actual de ese parámetro${NC}"
            echo -e "  ${DIM}Rango: -1.0 a 1.0 (brillo, contraste, saturación) o 0.1-10 (gamma)${NC}"
            read -rp "  → Brillo [$ADJUST_BRIGHTNESS]: " v
            [[ -n "$v" ]] && ADJUST_BRIGHTNESS="$v"
            read -rp "  → Contraste [$ADJUST_CONTRAST]: " v
            [[ -n "$v" ]] && ADJUST_CONTRAST="$v"
            read -rp "  → Saturación [$ADJUST_SATURATION]: " v
            [[ -n "$v" ]] && ADJUST_SATURATION="$v"
            read -rp "  → Gamma [$ADJUST_GAMMA]: " v
            [[ -n "$v" ]] && ADJUST_GAMMA="$v"
            [[ -z "$ADJUST_BRIGHTNESS" && -z "$ADJUST_CONTRAST" && -z "$ADJUST_SATURATION" && -z "$ADJUST_GAMMA" ]] && { echo -e "${RED}Indica al menos un ajuste${NC}"; exit 1; }
            echo ""
            ;;

        censor)
            echo -e "${BOLD}  Regiones a censurar${NC}"
            echo -e "  ${DIM}Formato: x:y:w:h (posición X, posición Y, ancho, alto)${NC}"
            echo -e "  ${DIM}Ejemplo: 100:50:200:150${NC}"
            echo -e "  ${DIM}Escribe 'fin' cuando termines${NC}"
            if [[ ${#CENSOR_REGIONS[@]} -gt 0 ]]; then
                echo -e "  ${DIM}Actual: ${CENSOR_REGIONS[*]}${NC}"
                echo -e "  ${DIM}Vacío = conservar las actuales${NC}"
            fi
            new_regions=()
            while true; do
                read -rp "  → Región: " region
                [[ "$region" == "fin" || -z "$region" ]] && break
                new_regions+=("$region")
            done
            if [[ ${#new_regions[@]} -gt 0 ]]; then
                CENSOR_REGIONS=("${new_regions[@]}")
            fi
            [[ ${#CENSOR_REGIONS[@]} -eq 0 ]] && { echo -e "${RED}Indica al menos una región${NC}"; exit 1; }
            echo ""
            ;;

        denoise)
            echo -e "${BOLD}  Fuerza del denoise${NC}"
            echo -e "    ${GREEN}1)${NC} 25  — Suave"
            echo -e "    ${GREEN}2)${NC} 50  — Normal (recomendado)"
            echo -e "    ${GREEN}3)${NC} 75  — Fuerte"
            echo -e "    ${GREEN}4)${NC} 100 — Máximo"
            denoise_def=2
            case "$DENOISE_STRENGTH" in
                25)  denoise_def=1 ;;
                75)  denoise_def=3 ;;
                100) denoise_def=4 ;;
            esac
            read -rp "  → [1-4] (default: $denoise_def): " val
            case "$val" in
                1) DENOISE_STRENGTH=25 ;;
                2) DENOISE_STRENGTH=50 ;;
                3) DENOISE_STRENGTH=75 ;;
                4) DENOISE_STRENGTH=100 ;;
                "") : ;;
                *) [[ -n "$val" ]] && DENOISE_STRENGTH="$val" ;;
            esac
            echo ""
            ;;

        sharpen)
            echo -e "${BOLD}  Fuerza del sharpen${NC}"
            echo -e "    ${GREEN}1)${NC} 2  — Suave"
            echo -e "    ${GREEN}2)${NC} 5  — Normal (recomendado)"
            echo -e "    ${GREEN}3)${NC} 8  — Fuerte"
            echo -e "    ${GREEN}4)${NC} 10 — Máximo"
            sharpen_def=2
            case "$SHARPEN_STRENGTH" in
                2)  sharpen_def=1 ;;
                8)  sharpen_def=3 ;;
                10) sharpen_def=4 ;;
            esac
            read -rp "  → [1-4] (default: $sharpen_def): " val
            case "$val" in
                1) SHARPEN_STRENGTH=2 ;;
                2) SHARPEN_STRENGTH=5 ;;
                3) SHARPEN_STRENGTH=8 ;;
                4) SHARPEN_STRENGTH=10 ;;
                "") : ;;
                *) [[ -n "$val" ]] && SHARPEN_STRENGTH="$val" ;;
            esac
            echo ""
            ;;

        scenes)
            echo -e "${BOLD}  Umbral de detección de escenas${NC}"
            echo -e "    ${GREEN}1)${NC} 0.2  — Detecta muchos cambios"
            echo -e "    ${GREEN}2)${NC} 0.3  — Equilibrado (recomendado)"
            echo -e "    ${GREEN}3)${NC} 0.5  — Solo cambios grandes"
            scene_def=2
            case "$SCENE_THRESHOLD" in
                0.2) scene_def=1 ;;
                0.5) scene_def=3 ;;
            esac
            read -rp "  → [1-3] (default: $scene_def): " val
            case "$val" in
                1) SCENE_THRESHOLD=0.2 ;;
                2) SCENE_THRESHOLD=0.3 ;;
                3) SCENE_THRESHOLD=0.5 ;;
                "") : ;;
                *) [[ -n "$val" ]] && SCENE_THRESHOLD="$val" ;;
            esac
            echo ""
            ;;

        keyframes)
            echo -e "${BOLD}  Directorio de salida para keyframes${NC}"
            kf_dir_default="${KEYFRAME_DIR:-./keyframes}"
            read -rp "  → Directorio (default: $kf_dir_default): " kf_dir
            [[ -n "$kf_dir" ]] && KEYFRAME_DIR="$kf_dir"
            [[ -z "$KEYFRAME_DIR" ]] && KEYFRAME_DIR="./keyframes"
            echo ""
            ;;

        aspect)
            echo -e "${BOLD}  Ratio de aspecto objetivo${NC}"
            echo -e "    ${GREEN}1)${NC} 16:9 — Widescreen"
            echo -e "    ${GREEN}2)${NC} 4:3  — Clásico"
            echo -e "    ${GREEN}3)${NC} 21:9 — Cine"
            echo -e "    ${GREEN}4)${NC} 1:1  — Cuadrado (Instagram)"
            echo -e "    ${GREEN}5)${NC} 9:16 — Vertical (Stories/TikTok)"
            aspect_def=1
            case "$ASPECT_RATIO" in
                16:9) aspect_def=1 ;;
                4:3)  aspect_def=2 ;;
                21:9) aspect_def=3 ;;
                1:1)  aspect_def=4 ;;
                9:16) aspect_def=5 ;;
            esac
            read -rp "  → [1-5] o personalizado (default: $aspect_def): " val
            case "$val" in
                1) ASPECT_RATIO="16:9" ;;
                2) ASPECT_RATIO="4:3" ;;
                3) ASPECT_RATIO="21:9" ;;
                4) ASPECT_RATIO="1:1" ;;
                5) ASPECT_RATIO="9:16" ;;
                "") : ;;
                *) [[ -n "$val" ]] && ASPECT_RATIO="$val" ;;
            esac
            echo ""
            ;;

        metadata)
            echo -e "${BOLD}  Metadata del vídeo${NC}"
            echo -e "  ${DIM}Vacío = conservar el valor actual de ese campo${NC}"
            read -rp "  → Título [$METADATA_TITLE]: " v
            [[ -n "$v" ]] && METADATA_TITLE="$v"
            read -rp "  → Artista [$METADATA_ARTIST]: " v
            [[ -n "$v" ]] && METADATA_ARTIST="$v"
            read -rp "  → Comentario [$METADATA_COMMENT]: " v
            [[ -n "$v" ]] && METADATA_COMMENT="$v"
            [[ -z "$METADATA_TITLE" && -z "$METADATA_ARTIST" && -z "$METADATA_COMMENT" ]] && { echo -e "${RED}Indica al menos un campo${NC}"; exit 1; }
            echo ""
            ;;
    esac

    # ══════════════════════════════════════════════════════════════════
    #  PASO 5: Progreso
    # ══════════════════════════════════════════════════════════════════
    if [[ "$MODE" != "info" ]]; then
        echo -e "${BOLD}  Progreso${NC}"
        echo -e "    ${GREEN}1)${NC} Resumen  — Solo resultado"
        echo -e "    ${GREEN}2)${NC} Detallado — Porcentaje y tiempo"
        prog_def=1
        [[ "$VERBOSE" == "true" ]] && prog_def=2
        read -rp "  → [1-2] (default: $prog_def): " val
        case "$val" in
            1) VERBOSE=false ;;
            2) VERBOSE=true ;;
            "") : ;;
            *) echo -e "${RED}Opción no válida${NC}"; exit 1 ;;
        esac
        echo ""
    fi

    # ══════════════════════════════════════════════════════════════════
    #  PASO 6: Resumen y confirmación
    # ══════════════════════════════════════════════════════════════════
    echo -e "${BOLD}═══════════════════════════════════════${NC}"
    echo -e "${BOLD} Resumen${NC}"
    echo -e "${BOLD}═══════════════════════════════════════${NC}"

    # Nombre del modo
    mode_name=
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
        stabilize)    mode_name="Estabilizar" ;;
        adjust)       mode_name="Ajustar imagen" ;;
        censor)       mode_name="Censurar" ;;
        denoise)      mode_name="Reducir ruido" ;;
        sharpen)      mode_name="Enfocar" ;;
        reverse)      mode_name="Invertir" ;;
        scenes)       mode_name="Cortar por escenas" ;;
        keyframes)    mode_name="Extraer keyframes" ;;
        aspect)       mode_name="Cambiar aspect ratio" ;;
        metadata)     mode_name="Editar metadata" ;;
        watch)        mode_name="Modo vigilancia" ;;
        preview)      mode_name="Previsualizar" ;;
        resume)       mode_name="Reanudar" ;;
    esac

    echo -e "  Modo:      ${CYAN}$mode_name${NC}"
    [[ -n "$URL" ]] && echo -e "  URL:       ${CYAN}$URL${NC}"
    if [[ ${#SELECTED_FILES[@]} -gt 1 ]]; then
        echo -e "  Archivos:  ${CYAN}${#SELECTED_FILES[@]} seleccionados${NC}"
    elif [[ ${#SELECTED_FILES[@]} -eq 1 ]]; then
        echo -e "  Archivo:   ${CYAN}$(basename "${SELECTED_FILES[0]}")${NC}"
    elif [[ -n "$SELECTED_FILE" ]]; then
        echo -e "  Archivo:   ${CYAN}$(basename "$SELECTED_FILE")${NC}"
    fi
    [[ -n "$OUTPUT_NAME" ]] && echo -e "  Salida:    ${CYAN}$OUTPUT_NAME${NC}"
    [[ -n "$INPUT_DIR" && "$MODE" != "download" && "$MODE" != "concat" ]] && echo -e "  Entrada:   ${CYAN}$INPUT_DIR${NC}"
    [[ -n "$OUTPUT_DIR" && "$MODE" != "info" ]] && echo -e "  Destino:   ${CYAN}$OUTPUT_DIR${NC}"
    if [[ "$MODE" == "cut" && ${#FILE_CUT[@]} -gt 1 ]]; then
        echo -e "  Corte:     ${CYAN}por vídeo (${#FILE_CUT[@]} configurados)${NC}"
        echo -e "  ${DIM}  Se preguntaron tiempos por cada archivo${NC}"
    else
        [[ -n "$START_TIME" ]] && echo -e "  Inicio:    ${CYAN}$START_TIME${NC}"
        [[ -n "$END_TIME" ]] && echo -e "  Fin:       ${CYAN}$END_TIME${NC}"
        [[ -n "$CUT_MODE" ]] && echo -e "  Tipo:      ${CYAN}$CUT_MODE${NC}"
        [[ ${#CUT_CLIPS[@]} -gt 0 ]] && echo -e "  Clips:     ${CYAN}${CUT_CLIPS[*]}${NC}"
    fi
    [[ -n "$SOCIAL" ]] && echo -e "  Social:    ${CYAN}$SOCIAL${NC}"
    [[ -n "$PRESET" && "$MODE" == "convert" ]] && echo -e "  Preset:    ${CYAN}$PRESET${NC}"
    [[ -n "$VIDEO_CODEC" && "$MODE" == "convert" ]] && echo -e "  Codec:     ${CYAN}$VIDEO_CODEC${NC}"
    [[ -n "$RESOLUTION" && "$MODE" == "convert" ]] && echo -e "  Resolución:${CYAN} $RESOLUTION${NC}"
    [[ -n "$MAX_SIZE" ]] && echo -e "  Tamaño máx:${CYAN} ${MAX_SIZE}GB${NC}"
    [[ -n "$AUDIO_CODEC" && "$MODE" == "convert" ]] && echo -e "  Audio:     ${CYAN}$AUDIO_CODEC ($AUDIO_BITRATE)${NC}"
    [[ -n "$ROTATE_DEGREES" ]] && echo -e "  Rotación:  ${CYAN}${ROTATE_DEGREES}°${NC}"
    [[ -n "$CROP_SIZE" ]] && echo -e "  Crop:      ${CYAN}$CROP_SIZE${NC}"
    [[ -n "$FADE_SECONDS" ]] && echo -e "  Fade:      ${CYAN}${FADE_SECONDS}s${NC}"
    [[ -n "$SPEED" ]] && echo -e "  Velocidad: ${CYAN}${SPEED}x${NC}"
    [[ -n "$TARGET_FPS" ]] && echo -e "  FPS:       ${CYAN}$TARGET_FPS${NC}"
    [[ -n "$GIF_FPS" ]] && echo -e "  GIF FPS:   ${CYAN}$GIF_FPS${NC}"
    [[ -n "$GIF_SCALE" ]] && echo -e "  GIF Tamaño:${CYAN} $GIF_SCALE${NC}"
    [[ -n "$THUMBNAIL_TIME" ]] && echo -e "  Timestamp: ${CYAN}$THUMBNAIL_TIME${NC}"
    [[ -n "$OUTPUT_FORMAT" ]] && echo -e "  Formato:   ${CYAN}$OUTPUT_FORMAT${NC}"
    [[ -n "$WATERMARK_FILE" ]] && echo -e "  Marca agua:${CYAN} $WATERMARK_FILE${NC}"
    [[ -n "$STAB_SHAKINESS" ]] && echo -e "  Estabilizar:${CYAN} $STAB_SHAKINESS${NC}"
    [[ -n "$ADJUST_BRIGHTNESS" ]] && echo -e "  Brillo:    ${CYAN}$ADJUST_BRIGHTNESS${NC}"
    [[ -n "$ADJUST_CONTRAST" ]] && echo -e "  Contraste: ${CYAN}$ADJUST_CONTRAST${NC}"
    [[ -n "$ADJUST_SATURATION" ]] && echo -e "  Saturación:${CYAN} $ADJUST_SATURATION${NC}"
    [[ -n "$ADJUST_GAMMA" ]] && echo -e "  Gamma:     ${CYAN}$ADJUST_GAMMA${NC}"
    [[ ${#CENSOR_REGIONS[@]} -gt 0 ]] && echo -e "  Regiones:  ${CYAN}${CENSOR_REGIONS[*]}${NC}"
    [[ -n "$DENOISE_STRENGTH" ]] && echo -e "  Denoise:   ${CYAN}$DENOISE_STRENGTH${NC}"
    [[ -n "$SHARPEN_STRENGTH" ]] && echo -e "  Sharpen:   ${CYAN}$SHARPEN_STRENGTH${NC}"
    [[ -n "$SCENE_THRESHOLD" ]] && echo -e "  Umbral:    ${CYAN}$SCENE_THRESHOLD${NC}"
    [[ -n "$KEYFRAME_DIR" ]] && echo -e "  Keyframes: ${CYAN}$KEYFRAME_DIR${NC}"
    [[ -n "$ASPECT_RATIO" ]] && echo -e "  Aspecto:   ${CYAN}$ASPECT_RATIO${NC}"
    [[ -n "$METADATA_TITLE" ]] && echo -e "  Título:    ${CYAN}$METADATA_TITLE${NC}"
    [[ -n "$METADATA_ARTIST" ]] && echo -e "  Artista:   ${CYAN}$METADATA_ARTIST${NC}"
    [[ -n "$METADATA_COMMENT" ]] && echo -e "  Comentario:${CYAN} $METADATA_COMMENT${NC}"
    [[ -n "$DOWNLOAD_START" ]] && echo -e "  Descarga desde: ${CYAN}$DOWNLOAD_START${NC}"
    [[ -n "$DOWNLOAD_END" ]] && echo -e "  Descarga hasta: ${CYAN}$DOWNLOAD_END${NC}"
    [[ -n "$SUBTITLE_SOFT" ]] && echo -e "  Subtítulos soft: ${CYAN}$SUBTITLE_SOFT${NC}"
    [[ -n "$SUBTITLE_HARD" ]] && echo -e "  Subtítulos hard: ${CYAN}$SUBTITLE_HARD${NC}"
    if [[ ${#CONCAT_FILES[@]} -gt 0 ]]; then
        echo -e "  Archivos:  ${CYAN}${CONCAT_FILES[*]}${NC}"
    fi
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

# ── Resolver códec de vídeo ───────────────────────────────────────────
VIDEO_CODEC="${VIDEO_CODEC:-h264}"
VIDEO_ENCODER=""
ENC_FLAGS=()
ENC_CRF_EXTRA=()
case "$VIDEO_CODEC" in
    h264) VIDEO_ENCODER="libx264" ;;
    hevc) VIDEO_ENCODER="libx265" ;;
    av1)  VIDEO_ENCODER="libsvtav1" ;;
    vp9)  VIDEO_ENCODER="libvpx-vp9" ;;
    *)    echo -e "${RED}Códec de vídeo no válido: $VIDEO_CODEC${NC}"; exit 1 ;;
esac

# Presets por codec (ENCODE_SPEED: ultrafast|fast|medium|slow|veryslow)
ENC_CRF="$CRF"
case "$VIDEO_CODEC" in
    h264|hevc)
        ENC_FLAGS=(-preset "$ENCODE_SPEED")
        if [[ "$VIDEO_CODEC" == "hevc" ]]; then
            ENC_CRF=$((CRF + 5)); [[ $ENC_CRF -gt 51 ]] && ENC_CRF=51
        fi
        ;;
    vp9)
        vp9_cpu=2
        case "$ENCODE_SPEED" in ultrafast) vp9_cpu=5;; fast) vp9_cpu=4;; medium) vp9_cpu=2;; slow) vp9_cpu=1;; veryslow) vp9_cpu=0;; esac
        ENC_FLAGS=(-deadline good -cpu-used "$vp9_cpu" -row-mt 1)
        ENC_CRF_EXTRA=(-b:v 0)
        ENC_CRF=$((CRF + 8));  [[ $ENC_CRF -gt 63 ]] && ENC_CRF=63
        ;;
    av1)
        svt_preset=8
        case "$ENCODE_SPEED" in ultrafast) svt_preset=13;; fast) svt_preset=10;; medium) svt_preset=8;; slow) svt_preset=5;; veryslow) svt_preset=2;; esac
        ENC_FLAGS=(-preset "$svt_preset")
        ENC_CRF=$((CRF + 12)); [[ $ENC_CRF -gt 63 ]] && ENC_CRF=63
        ;;
esac

# Fallback si ffmpeg no tiene el codificador (excepto GPU)
if [[ "$GPU" == "none" ]] && ! ffmpeg -hide_banner -encoders 2>/dev/null | grep -q "^.*$VIDEO_ENCODER"; then
    echo -e "${YELLOW}ADVERTENCIA: ffmpeg no tiene el codificador $VIDEO_ENCODER. Usando libx264${NC}"
    VIDEO_CODEC="h264"
    VIDEO_ENCODER="libx264"
    ENC_CRF="$CRF"
    ENC_FLAGS=(-preset "$ENCODE_SPEED")
    ENC_CRF_EXTRA=()
fi

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
    echo -e "  Hilos:      4 (máx)"
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
        # Validar que la URL esté soportada
        echo -e "${BOLD}Comprobando URL...${NC}"
        if ! yt-dlp --simulate --no-warnings "$URL" >/dev/null 2>&1; then
            echo -e "${RED}ERROR: URL no soportada o no válida${NC}"
            echo -e "  ${DIM}yt-dlp no puede descargar de este sitio${NC}"
            echo -e "  ${DIM}Lista: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md${NC}"
            exit 1
        fi
        echo -e "${GREEN}URL válida${NC}"
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
    preview)
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para previsualizar en $INPUT_DIR${NC}"
            exit 0
        fi
        host_open_video "${archivos[0]}"
        exit 0
        ;;
    cut)
        case "$CUT_MODE" in
            remove)
                if [[ ${#CUT_CLIPS[@]} -eq 0 ]]; then
                    echo -e "${RED}ERROR: Se requiere -clips para eliminar secciones${NC}"
                    echo "  Uso: ./midu.sh --cut --remove -clips 00:01:00-00:02:30,00:05:00-00:07:15"
                    exit 1
                fi
                ;;
            extract)
                if [[ ${#CUT_CLIPS[@]} -eq 0 ]]; then
                    echo -e "${RED}ERROR: Se requiere -clips para extraer clips${NC}"
                    echo "  Uso: ./midu.sh --cut --extract -clips 00:01:00-00:02:30,00:05:00-00:07:15"
                    exit 1
                fi
                ;;
            normal)
                if [[ -z "$START_TIME" && -z "$END_TIME" ]]; then
                    echo -e "${RED}ERROR: Se requiere -ss y/o -e para cortar${NC}"
                    echo "  Uso: ./midu.sh --cut -ss 00:01:30 -e 00:03:45"
                    exit 1
                fi
                ;;
        esac
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para cortar en $INPUT_DIR${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            # Config por vídeo (modo interactivo multi-selección)
            per_cut_mode="$CUT_MODE"
            per_start="$START_TIME"
            per_end="$END_TIME"
            per_clips=("${CUT_CLIPS[@]}")
            if [[ -n "${FILE_CUT[$file]:-}" ]]; then
                per_clips_csv=""
                IFS='|' read -r per_cut_mode per_start per_end per_clips_csv <<< "${FILE_CUT[$file]}"
                per_clips=()
                if [[ -n "$per_clips_csv" ]]; then
                    IFS=';' read -ra per_clips <<< "$per_clips_csv"
                fi
            fi
            case "$per_cut_mode" in
                remove)
                    CUT_CLIPS=("${per_clips[@]}")
                    remove_clips "$file" "$OUTPUT_DIR"
                    ;;
                extract)
                    CUT_CLIPS=("${per_clips[@]}")
                    extract_clips "$file" "$OUTPUT_DIR"
                    ;;
                *)
                    START_TIME="$per_start"
                    END_TIME="$per_end"
                    cut_video "$file" "$OUTPUT_DIR"
                    ;;
            esac
        done
        unset per_cut_mode per_start per_end per_clips per_clips_csv
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
    stabilize)
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para estabilizar${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            stabilize_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    adjust)
        if [[ -z "$ADJUST_BRIGHTNESS" && -z "$ADJUST_CONTRAST" && -z "$ADJUST_SATURATION" && -z "$ADJUST_GAMMA" ]]; then
            echo -e "${RED}ERROR: Indica al menos un ajuste (brightness, contrast, saturation, gamma)${NC}"
            exit 1
        fi
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para ajustar${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            adjust_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    censor)
        if [[ ${#CENSOR_REGIONS[@]} -eq 0 ]]; then
            echo -e "${RED}ERROR: Indica las regiones a censurar (x:y:w:h)${NC}"
            exit 1
        fi
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para censurar${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            censor_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    denoise)
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para reducir ruido${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            denoise_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    sharpen)
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para enfocar${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            sharpen_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    reverse)
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para invertir${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            reverse_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    scenes)
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para detectar escenas${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            scenes_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    keyframes)
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para extraer keyframes${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            keyframes_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    aspect)
        if [[ -z "$ASPECT_RATIO" ]]; then
            echo -e "${RED}ERROR: Se requiere ratio de aspecto${NC}"
            echo "  Uso: ./midu.sh --aspect 16:9"
            exit 1
        fi
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para cambiar aspect ratio${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            aspect_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    metadata)
        if [[ -z "$METADATA_TITLE" && -z "$METADATA_ARTIST" && -z "$METADATA_COMMENT" ]]; then
            echo -e "${RED}ERROR: Indica al menos un campo de metadata${NC}"
            exit 1
        fi
        buscar_archivos
        if [[ $total -eq 0 ]]; then
            echo -e "${YELLOW}No hay vídeos para editar metadata${NC}"
            exit 0
        fi
        mkdir -p "$OUTPUT_DIR"
        for file in "${archivos[@]}"; do
            metadata_video "$file" "$OUTPUT_DIR"
        done
        exit 0
        ;;
    resume)
        if [[ -z "$CHECKPOINT_FILE" || ! -f "$CHECKPOINT_FILE" ]]; then
            echo -e "${RED}ERROR: No se encontró el checkpoint${NC}"
            exit 1
        fi
        load_checkpoint
        # Filtrar archivos ya completados
        pending_files=()
        for file in "${archivos[@]}"; do
            if ! is_checkpoint_done "$file"; then
                pending_files+=("$file")
            fi
        done
        if [[ ${#pending_files[@]} -eq 0 ]]; then
            echo -e "${GREEN}Todos los archivos ya fueron procesados${NC}"
            exit 0
        fi
        echo -e "${BOLD}Archivos pendientes:${NC} ${#pending_files[@]}"
        mkdir -p "$OUTPUT_DIR"
        for file in "${pending_files[@]}"; do
            convertir_archivo "$file" "$OUTPUT_DIR" && save_checkpoint "$file" "done" || save_checkpoint "$file" "failed"
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

echo -e "${BOLD}Encontrados${NC} $total archivos, $saltados ya hechos (hilos: 4 máx)"
echo ""

# ── Convertir ─────────────────────────────────────────────────────────

# Escribe una línea en el log del job (batch) o directamente a stdout (modo simple)
emit_log() {
    local logf="${1:-}"
    shift
    if [[ -n "$logf" ]]; then
        printf '%b\n' "$*" >> "$logf"
    else
        printf '%b\n' "$*"
    fi
}

procesados=0
fallidos=0
active_threads=()

convertir_archivo() {
    local file="$1"
    local output_dir="$2"
    local file_idx="${3:-0}"
    local prog_file=""
    local job_log=""
    if [[ -n "${PROG_DIR:-}" && "$file_idx" -gt 0 ]]; then
        prog_file="$PROG_DIR/${file_idx}.prog"
        job_log="$PROG_DIR/${file_idx}.log"
    fi
    local filename
    filename=$(basename "$file")
    filename="${filename%.*}"
    local output_file="$output_dir/$filename.mp4"
    local tmp_file="$output_dir/.tmp_$$_$(date +%s%N)_$RANDOM.mp4"

    # ── Config de corte por vídeo (modo interactivo multi-selección) ──
    if [[ -n "${FILE_CUT[$file]:-}" ]]; then
        local cut_cfg="${FILE_CUT[$file]}"
        local per_mode per_start per_end per_clips
        IFS='|' read -r per_mode per_start per_end per_clips <<< "$cut_cfg"
        CUT_MODE="${per_mode:-normal}"
        START_TIME="$per_start"
        END_TIME="$per_end"
        CUT_CLIPS=()
        if [[ -n "$per_clips" ]]; then
            IFS=';' read -ra CUT_CLIPS <<< "$per_clips"
        fi
    fi

    # ── Modos remove/extract: despachar a sus funciones ────────────────
    if [[ "$CUT_MODE" == "remove" || "$CUT_MODE" == "extract" ]]; then
        if [[ "$CUT_MODE" == "remove" ]]; then
            remove_clips "$file" "$output_dir"
        else
            extract_clips "$file" "$output_dir"
        fi
        return $?
    fi

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
            emit_log "$job_log" "${RED}ERROR: Tiempo de inicio ($START_TIME) mayor que la duración del vídeo ($(format_time "$duration"))${NC}"
            return 1
        fi

        # Si no hay END_TIME, usar la duración del archivo
        if [[ "$end_secs" -eq 0 ]]; then
            end_secs=$duration
        fi

        # Validar que end_secs sea mayor que start_secs
        if [[ "$end_secs" -le "$start_secs" ]]; then
            emit_log "$job_log" "${RED}ERROR: Tiempo de fin ($END_TIME) debe ser mayor que el inicio ($START_TIME)${NC}"
            return 1
        fi

        effective_duration=$((end_secs - start_secs))
    fi

    local duration_fmt
    duration_fmt=$(format_time "$effective_duration")

    local remux="false"
    if can_remux "$file" && [[ "${VIDEO_CODEC:-h264}" == "h264" ]] && [[ -z "$MAX_SIZE" ]] && [[ -z "$START_TIME" ]] && [[ -z "$END_TIME" ]] && [[ -z "$SUBTITLE_HARD" ]] && [[ -z "$SPEED" ]]; then
        remux="true"
    fi

    if [[ "$VERBOSE" == true ]]; then
        emit_log "$job_log" "[$file_idx/$total] ${filename} (${duration_fmt:-??:??:??}) [remux=$remux]"
    fi

    # ── Tamaño máximo: calcular bitrate objetivo (con margen del 8%) ──
    local audio_kbps
    audio_kbps=$(echo "$AUDIO_BITRATE" | sed 's/k//')
    local bitrate_k=""
    local size_target_bytes=0
    local attempt=0
    local use_twopass=false
    [[ "$TWO_PASS" == true ]] && use_twopass=true
    if [[ -n "$MAX_SIZE_MB" && -n "$effective_duration" && "$effective_duration" -gt 0 ]]; then
        local total_bits
        total_bits=$(echo "$MAX_SIZE_MB * 1024 * 1024 * 8" | bc 2>/dev/null | cut -d. -f1)
        local video_kbits=$((total_bits / 1000 - audio_kbps * effective_duration))

        if [[ "$video_kbits" -lt 0 ]]; then
            emit_log "$job_log" "${YELLOW}AVISO: El tamaño máximo (${MAX_SIZE}GB) es demasiado pequeño para el audio y la duración${NC}"
            emit_log "$job_log" "  ${DIM}Se usará bitrate mínimo de 100k${NC}"
            video_kbits=0
        fi

        bitrate_k=$((video_kbits / effective_duration))
        bitrate_k=$((bitrate_k * 92 / 100))
        if [[ "$bitrate_k" -lt 100 ]]; then
            bitrate_k=100
        fi

        size_target_bytes=$(echo "$MAX_SIZE_MB * 1024 * 1024" | bc 2>/dev/null | cut -d. -f1)
        [[ "$GPU" == "cpu" ]] && use_twopass=true

        [[ "$VERBOSE" == true ]] && emit_log "$job_log" "  → Bitrate vídeo: ${bitrate_k}k (para ${MAX_SIZE}GB en ${effective_duration}s)"
    fi

    while true; do
    local ffmpeg_args=(-y)

    # ── HW-accel decoding ──────────────────────────────────────────
    if [[ "$HW_ACCEL" == true ]]; then
        ffmpeg_args+=(-hwaccel auto -hwaccel_output_format auto)
    fi

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

        if [[ -n "$bitrate_k" ]]; then
            case "$GPU:$VIDEO_CODEC" in
                nvenc:h264) ffmpeg_args+=(-c:v h264_nvenc -b:v "${bitrate_k}k" -maxrate "$((bitrate_k * 2))k" -bufsize "${bitrate_k}k" -preset "$ENCODE_SPEED") ;;
                vaapi:h264) ffmpeg_args+=(-vaapi_device /dev/dri/renderD128 -c:v h264_vaapi -b:v "${bitrate_k}k" -maxrate "$((bitrate_k * 2))k" -bufsize "${bitrate_k}k") ;;
                *)          ffmpeg_args+=(-c:v "$VIDEO_ENCODER" -threads 4 -b:v "${bitrate_k}k" -maxrate "$((bitrate_k * 2))k" -bufsize "${bitrate_k}k" "${ENC_FLAGS[@]}") ;;
            esac
        else
            case "$GPU:$VIDEO_CODEC" in
                nvenc:h264) ffmpeg_args+=(-c:v h264_nvenc -rc constqp -qp "$CRF" -preset "$ENCODE_SPEED") ;;
                vaapi:h264) ffmpeg_args+=(-vaapi_device /dev/dri/renderD128 -c:v h264_vaapi -qp "$CRF") ;;
                *)          ffmpeg_args+=(-c:v "$VIDEO_ENCODER" -threads 4 -crf "$ENC_CRF" "${ENC_CRF_EXTRA[@]}" "${ENC_FLAGS[@]}") ;;
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

    # Map streams: vídeo (input0) + audio si existe + subtítulos soft si existe (input1)
    ffmpeg_args+=(-map 0:v:0)
    local has_audio
    has_audio=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$file" 2>/dev/null | head -1)
    if [[ -n "$has_audio" ]]; then
        ffmpeg_args+=(-map 0:a:0)
    fi
    if [[ -n "$SUBTITLE_SOFT" ]]; then
        ffmpeg_args+=(-map 1:s:0 -c:s copy)
    fi
    ffmpeg_args+=(-map_metadata 0 -movflags +faststart)
    ffmpeg_args+=("$tmp_file")

    local ffmpeg_log="$tmp_file.log"
    rm -f "$ffmpeg_log"

    # ── Two-pass encoding ─────────────────────────────────────────
    if [[ "$use_twopass" == true && "$remux" != "true" ]]; then
        emit_log "$job_log" "  ${DIM}Two-pass: pasada 1/2...${NC}"

        # Construir args para pasada 1 (sin audio, sin salida final)
        local pass1_args=()
        local _p
        for _p in "${ffmpeg_args[@]}"; do
            [[ "$_p" == "$tmp_file" ]] && continue
            pass1_args+=("$_p")
        done
        pass1_args+=(-f null /dev/null -pass 1 -passlogfile "$tmp_file.passlog")

        if ! ffmpeg "${pass1_args[@]}" 2>/dev/null; then
            emit_log "$job_log" "${RED}Error en pasada 1${NC}"
            rm -f "$tmp_file" "$ffmpeg_log" "$tmp_file.passlog"*
            return 1
        fi

        emit_log "$job_log" "  ${DIM}Two-pass: pasada 2/2...${NC}"
        # Añadir pasada 2 a los args
        ffmpeg_args+=(-pass 2 -passlogfile "$tmp_file.passlog")
    fi

    if [[ "$VERBOSE" == true ]]; then
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
            if [[ -n "$out_time_us" && "$out_time_us" =~ ^[0-9]+$ && "$out_time_us" -gt 0 && -n "$effective_duration" && "$effective_duration" =~ ^[0-9]+$ && "$effective_duration" -gt 0 ]]; then
                local cur_secs=$((out_time_us / 1000000))
                local pct=$((cur_secs * 100 / effective_duration))
                [[ "$pct" -gt 100 ]] && pct=100
                local cur_fmt
                cur_fmt=$(format_time "$cur_secs")
                local remain_secs=$((effective_duration - cur_secs))
                [[ "$remain_secs" -lt 0 ]] && remain_secs=0
                local remain_fmt
                remain_fmt=$(format_time "$remain_secs")

                if [[ -n "$prog_file" ]]; then
                    printf '%s|%s|%s|%s|%s|%s\n' "$file_idx" "$filename" "$pct" "$cur_fmt" "$duration_fmt" "$remain_fmt" > "$prog_file.tmp"
                    mv -f "$prog_file.tmp" "$prog_file" 2>/dev/null
                elif [[ "$VERBOSE" == true ]]; then
                    printf "  ${DIM}%3d%% | %s / %s | falta %s${NC}\r" "$pct" "$cur_fmt" "$duration_fmt" "$remain_fmt" >&2
                fi
            fi
        fi
        sleep 0.5
    done
    wait "$ffmpeg_pid"
    local ffmpeg_exit=$?
    rm -f "$prog_file" "$prog_file.tmp" 2>/dev/null

    if [[ "$VERBOSE" == true && -z "$job_log" ]]; then
        printf "  ${DIM}100%% | %s / %s | completado${NC}\n" "$duration_fmt" "$duration_fmt" >&2
    fi

    if [[ "$ffmpeg_exit" -ne 0 ]]; then
        emit_log "$job_log" "${RED}[$file_idx/$total] ERROR: $filename (ffmpeg exit: $ffmpeg_exit)${NC}"
        if [[ -f "$ffmpeg_log" ]]; then
            if [[ -n "$job_log" ]]; then
                tail -5 "$ffmpeg_log" | sed 's/^/    /' >> "$job_log"
            else
                tail -5 "$ffmpeg_log" | sed 's/^/    /'
            fi
        fi
        rm -f "$tmp_file" "$ffmpeg_log"
        return 1
    fi
    rm -f "$ffmpeg_log"

    if [[ ! -f "$tmp_file" ]]; then
        emit_log "$job_log" "${RED}[$file_idx/$total] ERROR: archivo temporal no creado${NC}"
        return 1
    fi

    local size
    size=$(stat -c%s "$tmp_file" 2>/dev/null || stat -f%z "$tmp_file" 2>/dev/null || echo 0)
    if [[ "$size" -lt 1024 ]]; then
        emit_log "$job_log" "${RED}[$file_idx/$total] ERROR: archivo temporal sospechosamente pequeño (${size} bytes)${NC}"
        rm -f "$tmp_file"
        return 1
    fi

    # ── Verificar tamaño máximo; si se supera, re-codificar con menos bitrate ──
    if [[ -n "$MAX_SIZE_MB" && "$size" -gt "$size_target_bytes" && "$attempt" -lt 2 ]]; then
        attempt=$((attempt + 1))
        local shrink_pct=$((size_target_bytes * 100 / size))
        bitrate_k=$((bitrate_k * shrink_pct * 90 / 10000))
        if [[ "$bitrate_k" -lt 100 ]]; then
            bitrate_k=100
        fi
        emit_log "$job_log" "${YELLOW}Tamaño $((size / 1024 / 1024))MB > máx ${MAX_SIZE}GB; reintento $attempt con bitrate ${bitrate_k}k${NC}"
        rm -f "$tmp_file" "$tmp_file.passlog"*
        continue
    fi
    break
    done

    mv "$tmp_file" "$output_file"

    local orig_size
    orig_size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo 0)
    local orig_mb=$((orig_size / 1024 / 1024))
    local out_mb=$((size / 1024 / 1024))
    local ratio=0
    if [[ "$orig_size" -gt 0 ]]; then
        ratio=$((size * 100 / orig_size))
    fi

    emit_log "$job_log" "  ${GREEN}OK${NC}: ${orig_mb}MB → ${out_mb}MB (${ratio}%)"

    if [[ -n "$MAX_SIZE_MB" ]]; then
        emit_log "$job_log" "  ${DIM}Tamaño final: ${out_mb}MB (límite ${MAX_SIZE}GB)${NC}"
        if [[ "$size" -gt "$size_target_bytes" ]]; then
            emit_log "$job_log" "${YELLOW}AVISO: No se pudo bajar de ${MAX_SIZE}GB (límite de bitrate mínimo alcanzado)${NC}"
        fi
    fi

    return 0
}

# ── Ejecutar ──────────────────────────────────────────────────────────

# Comprobar espacio en disco
if ! check_disk_space "$OUTPUT_DIR" 500; then
    echo -e "${RED}Continuando con poco espacio...${NC}"
fi

# Crear checkpoint si se pide
if [[ -n "$CHECKPOINT_FILE" ]]; then
    : > "$CHECKPOINT_FILE"
fi

# Lista de archivos fallidos para retry
FAILED_LIST="/tmp/midu_failed_$$.txt"
: > "$FAILED_LIST"

procesados=0
fallidos=0
active_threads=()
file_index=0
BATCH_START=$(date +%s)

# ── Panel de progreso por archivo ──────────────────────────────────────
PROG_DIR=$(mktemp -d /tmp/midu_prog_XXXXXX)
panel_lines=0
declare -A PID_IDX
declare -A PID_FILE

clear_panel() {
    if [[ "${panel_lines:-0}" -gt 0 ]]; then
        printf '\033[%dA\033[J' "$panel_lines" >&2
        panel_lines=0
    fi
}

render_progress_panel() {
    [[ -t 2 ]] || return 0
    local data="" pf line idx name pct cur dur rem lines=0
    for pf in "$PROG_DIR"/*.prog; do
        [[ -f "$pf" ]] || continue
        data+=$(cat "$pf")
        data+=$'\n'
    done
    if [[ -n "$data" ]]; then
        local sorted
        sorted=$(printf '%s' "$data" | sort -t'|' -k1,1n)
        clear_panel
        while IFS= read -r line; do
            [[ -n "$line" ]] || continue
            IFS='|' read -r idx name pct cur dur rem <<< "$line"
            [[ -n "$pct" && -n "$dur" ]] || continue
            printf '  %s%% | %s / %s | falta %s  %b[%s] %s%b\n' "$pct" "$cur" "$dur" "$rem" "$DIM" "$idx" "$name" "$NC" >&2
            ((lines++))
        done <<< "$sorted"
        panel_lines=$lines
    else
        clear_panel
    fi
}

finish_job_display() {
    local pid="$1"
    local estimate_line="${2:-}"
    local idx="${PID_IDX[$pid]:-0}"
    clear_panel
    if [[ -n "$idx" && -f "$PROG_DIR/${idx}.log" ]]; then
        cat "$PROG_DIR/${idx}.log" >&2
    fi
    if [[ -n "$estimate_line" ]]; then
        printf '%s\n' "$estimate_line" >&2
    fi
    rm -f "$PROG_DIR/${idx}.log" "$PROG_DIR/${idx}.prog" "$PROG_DIR/${idx}.prog.tmp"
    render_progress_panel
}

for file in "${archivos[@]}"; do
    ((file_index++))

    # Saltar si ya está en checkpoint
    if is_checkpoint_done "$file" 2>/dev/null; then
        ((procesados++))
        continue
    fi

    # Comprobar espacio antes de cada archivo
    check_disk_space "$OUTPUT_DIR" 100 || true

    track_time_start "$file"
    convertir_archivo "$file" "$OUTPUT_DIR" "$file_index" &
    PID_IDX[$!]=$file_index
    PID_FILE[$!]=$file
    active_threads+=($!)
    render_progress_panel

    while [ "${#active_threads[@]}" -ge "$MAX_THREADS" ]; do
        for i in "${!active_threads[@]}"; do
            if ! kill -0 "${active_threads[i]}" 2>/dev/null; then
                pid="${active_threads[i]}"
                file_for_pid="${PID_FILE[$pid]}"
                wait "$pid" 2>/dev/null
                rc=$?
                if [[ "$rc" -eq 0 ]]; then
                    ((procesados++))
                    save_checkpoint "$file_for_pid" "done" 2>/dev/null || true
                else
                    ((fallidos++))
                    echo "$file_for_pid" >> "$FAILED_LIST"
                    save_checkpoint "$file_for_pid" "failed" 2>/dev/null || true
                fi
                track_time_end "$file_for_pid"
                estimate_out=$(estimate_remaining "${PID_IDX[$pid]}" "$total")
                unset 'active_threads[i]'
                finish_job_display "$pid" "$estimate_out"
            fi
        done
        active_threads=("${active_threads[@]}")
        render_progress_panel
        sleep 0.5
    done
done

for pid in "${active_threads[@]}"; do
    while kill -0 "$pid" 2>/dev/null; do
        render_progress_panel
        sleep 0.5
    done
    wait "$pid" 2>/dev/null
    rc=$?
    if [[ "$rc" -eq 0 ]]; then
        ((procesados++))
    else
        ((fallidos++))
    fi
    estimate_out=$(estimate_remaining "${PID_IDX[$pid]}" "$total")
    finish_job_display "$pid" "$estimate_out"
done
clear_panel
rm -rf "$PROG_DIR"

BATCH_END=$(date +%s)
BATCH_ELAPSED=$((BATCH_END - BATCH_START))
BATCH_FMT=$(format_time "$BATCH_ELAPSED")

echo ""
echo -e "${BOLD}Completado:${NC} ${GREEN}$procesados OK${NC}, ${RED}$fallidos fallos${NC} de $total archivos."
echo -e "${DIM}Tiempo total: $BATCH_FMT${NC}"

# Notificación
if [[ "$NOTIFY" == true ]]; then
    send_notification "midu.sh" "Procesamiento completado: $procesados OK, $fallidos falllos ($BATCH_FMT)"
fi

# Reintentar archivos fallidos
if [[ "$RETRY_FAILED" == true && "$fallidos" -gt 0 ]]; then
    retry_failed_files "$FAILED_LIST" "$OUTPUT_DIR"
fi

rm -f "$FAILED_LIST"
