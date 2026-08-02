#!/usr/bin/env bash
# preview_watcher.sh
# Abre en el host (Windows/WSL) los vídeos que midu.sh pide previsualizar
# cuando se ejecuta dentro del contenedor Docker (donde no se puede lanzar
# un reproductor gráfico de Windows).
#
# Solo actúa cuando existe test_video/.midu_preview_req, y ese archivo solo
# se crea dentro del modo "cortar" de midu.sh. Fuera de ahí, el watcher
# simplemente duerme.
#
# Uso (en WSL, desde la raíz del repo):
#   bash preview_watcher.sh --daemon   # arranca en segundo plano (sobrevive a Ctrl+C)
#   bash preview_watcher.sh --stop     # detiene el daemon
#   bash preview_watcher.sh --status   # ¿corriendo?
#   bash preview_watcher.sh --once     # procesa una petición y sale
#   bash preview_watcher.sh            # bucle en primer plano (debug)
#
# El daemon se apaga solo:
#   - si el contenedor 'yt_ffmpeg_downloader' estaba corriendo y se detiene
#     (por ejemplo Ctrl+C en docker compose), o
#   - tras IDLE_TIMEOUT segundos sin actividad (por defecto 600 = 10 min).
# De modo que solo "vive" mientras tienes la sesión de midu.sh activa.
#
# Requisito: VLC en Windows (busca rutas habituales) o el reproductor
# por defecto de Windows como fallback.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="$REPO_DIR/test_video/.midu_preview_req"
PIDFILE="$REPO_DIR/.preview_watcher.pid"
POLL_INTERVAL=1
IDLE_TIMEOUT=${IDLE_TIMEOUT:-600}
CONTAINER_NAME=${MIDU_CONTAINER_NAME:-yt_ffmpeg_downloader}
CONTAINER_MATCH=${MIDU_CONTAINER_MATCH:-'^(yt_ffmpeg_downloader|ffmpeg-yt-dlp-downloader)'}
ONCE=false
DAEMON_MODE=false

to_windows_path() {
    local p="$1"
    if [[ "$p" == /app/* ]]; then
        p="$REPO_DIR/${p#/app/}"
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

open_request() {
    local req="$1"
    local video winpath vlc
    video=$(head -1 "$req" 2>/dev/null)
    [[ -n "$video" ]] || { rm -f "$req"; return 0; }
    if [[ "$video" != /* ]]; then
        video="$(cd "$(dirname "$REQ_FILE")" && pwd)/$video"
        video="${video//\/.\//\/}"
    fi
    winpath=$(to_windows_path "$video")
    echo "[preview_watcher] Abriendo: $video"
    echo "[preview_watcher]            → $winpath"
    vlc=$(find_vlc) || true
    if [[ -n "$vlc" ]]; then
        "$vlc" "$winpath" >/dev/null 2>&1 &
    elif command -v cmd.exe &>/dev/null; then
        cmd.exe /c start "" "$winpath" >/dev/null 2>&1 &
    else
        echo "[preview_watcher] No se encontró VLC ni reproductor por defecto."
        echo "[preview_watcher] Abre manualmente: $winpath"
    fi
    rm -f "$req"
}

is_running() {
    [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null
}

container_running() {
    command -v docker &>/dev/null || return 2
    docker ps --format '{{.Names}}' 2>/dev/null | grep -Eq "$CONTAINER_MATCH"
}

if [[ -n "${_WATCHER_DAEMON_CHILD:-}" ]]; then
    DAEMON_MODE=true
else
    case "$1" in
        --daemon)
            if is_running; then
                echo "[preview_watcher] Ya está corriendo (pid $(cat "$PIDFILE")). Usa --stop para pararlo."
                exit 0
            fi
            echo "[preview_watcher] Arrancando en segundo plano (pid file: $PIDFILE)..."
            nohup env _WATCHER_DAEMON_CHILD=1 bash "$0" >/dev/null 2>&1 &
            echo "$!" > "$PIDFILE"
            exit 0
            ;;
        --stop)
            if is_running; then
                kill "$(cat "$PIDFILE")" 2>/dev/null
                rm -f "$PIDFILE"
                rm -f "$REQ_FILE"
                echo "[preview_watcher] Detenido."
            else
                rm -f "$PIDFILE"
                rm -f "$REQ_FILE"
                echo "[preview_watcher] No hay daemon activo."
            fi
            exit 0
            ;;
        --status)
            if is_running; then
                echo "[preview_watcher] Corriendo (pid $(cat "$PIDFILE"))."
            else
                echo "[preview_watcher] No está corriendo."
                exit 1
            fi
            exit 0
            ;;
        --once)
            ONCE=true
            ;;
    esac
fi

if [[ "$DAEMON_MODE" == true ]]; then
    trap 'rm -f "$PIDFILE"; rm -f "$REQ_FILE"' EXIT
    echo "[preview_watcher] Daemon activo (idle timeout: ${IDLE_TIMEOUT}s). Vigilando: $REQ_FILE"
else
    trap 'rm -f "$REQ_FILE"' INT TERM
    echo "[preview_watcher] Vigilando: $REQ_FILE  (Ctrl+C para salir)"
fi

last_active=$(date +%s)
container_seen_running=false
poll_count=0
while true; do
    if [[ -f "$REQ_FILE" ]]; then
        open_request "$REQ_FILE"
        last_active=$(date +%s)
        if [[ "$ONCE" == true ]]; then
            exit 0
        fi
    fi
    if [[ "$DAEMON_MODE" == true ]]; then
        now=$(date +%s)
        if [[ $((now - last_active)) -ge "$IDLE_TIMEOUT" ]]; then
            echo "[preview_watcher] Sin actividad durante ${IDLE_TIMEOUT}s. Apagado automático."
            exit 0
        fi
        ((poll_count++))
        if (( poll_count % 5 == 0 )); then
            if container_running; then
                container_seen_running=true
            elif [[ "$container_seen_running" == true ]]; then
                echo "[preview_watcher] Contenedor '$CONTAINER_NAME' detenido. Apagado."
                exit 0
            fi
        fi
    fi
    sleep "$POLL_INTERVAL"
done
