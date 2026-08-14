#!/bin/bash
# =============================================================================
#  Instala en ~/.bashrc los alias del pipeline "sendo -> Telegram".
#  Detecta automáticamente la ruta del proyecto (donde está este script).
#  Idempotente: si el bloque ya existe, no añade duplicados.
#
#  Uso:   bash servicios/instalar_aliases.sh
#  Tras:  source ~/.bashrc
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEVJOBS="$(dirname "$SCRIPT_DIR")"
BASHRC="$HOME/.bashrc"
MARCA='# ---------- Pipeline "Directo sendo -> comprimir -> subir a Telegram" ----------'
MARCA2='# ---------- Aliases por proyecto (ver logs, ejecutar, parar, etc.) ----------'

ROJO='\033[0;31m'; VERDE='\033[0;32m'; RESET='\033[0m'
print_ok(){ echo -e "${VERDE}[✓]${RESET} $1"; }
print_err(){ echo -e "${ROJO}[x]${RESET} $1"; }

[ -f "$BASHRC" ] || touch "$BASHRC"

if grep -qF "$MARCA" "$BASHRC"; then
    print_ok "Aliases del pipeline ya instalados (no se tocan)."
else
cat >> "$BASHRC" <<ALIASES

$MARCA
alias plogs='bash $SCRIPT_DIR/pipeline_logs.sh'
alias pipe_setup='bash $SCRIPT_DIR/pipe_setup.sh'
alias pipe_chats='bash $SCRIPT_DIR/pipe_chats.sh'
alias pipe_chats_sendo='bash $SCRIPT_DIR/pipe_chats.sh --folder sendo'
alias pipe_rebuild='bash $SCRIPT_DIR/pipe_rebuild.sh'
alias pipe_test='bash $SCRIPT_DIR/pipe_test_upload.sh'
alias pipe_up='docker compose -f $DEVJOBS/TwitchRecorder/docker-compose.yml up -d twitchrecorder && docker compose -f $DEVJOBS/ffmpeg-yt-dlp/docker-compose.yml up -d monitor && docker compose -f $DEVJOBS/downloader_telegram/docker-compose.yml up -d uploader'
alias pipe_recreate='docker compose -f $DEVJOBS/TwitchRecorder/docker-compose.yml up -d --force-recreate twitchrecorder && docker compose -f $DEVJOBS/ffmpeg-yt-dlp/docker-compose.yml up -d --force-recreate monitor && docker compose -f $DEVJOBS/downloader_telegram/docker-compose.yml up -d --force-recreate uploader'
alias pipe_down='docker compose -f $DEVJOBS/TwitchRecorder/docker-compose.yml down && docker compose -f $DEVJOBS/ffmpeg-yt-dlp/docker-compose.yml down && docker compose -f $DEVJOBS/downloader_telegram/docker-compose.yml down'
alias pipe_ps='docker ps --filter name=twitchrecorder --filter name=ffmpeg_monitor --filter name=telegram-uploader --format "table {{.Names}}\t{{.Status}}"'
alias pipe_sys_start='sudo systemctl start twitch-stream-pipeline.service'
alias pipe_sys_stop='sudo systemctl stop twitch-stream-pipeline.service'
alias pipe_sys_status='systemctl status twitch-stream-pipeline.service'
ALIASES
fi

if grep -qF "$MARCA2" "$BASHRC"; then
    print_ok "Aliases por proyecto ya instalados (no se tocan)."
else
cat >> "$BASHRC" <<ALIASES2

$MARCA2
# =====================================================================
# Un proyecto puede correr en 2 modos. Cada modo tiene su propio juego de
# alias para NO liarse:
#   *_logs / *_stop / *_restart  -> la instancia DAEMON (la del pipeline,
#                                   corre 24/7, es el contenedor "de verdad").
#                                   Los 3 daemons a la vez: plogs / pipe_up /
#                                   pipe_down / pipe_ps.
#   *_manual_*                   -> instancia para PROBAR a mano (se lanza
#                                   en terminal; normalmente son --rm).
#   *_down                       -> para TODO el proyecto (ambas instancias).
# =====================================================================

# ---------- pdfmanager (1 instancia) ----------
alias pdf_run='docker compose -f $DEVJOBS/pdfmanager/docker-compose.yml up'
alias pdf_logs='docker compose -f $DEVJOBS/pdfmanager/docker-compose.yml logs -f'
alias pdf_down='docker compose -f $DEVJOBS/pdfmanager/docker-compose.yml down'

# ---------- downloader_telegram ----------
# DAEMON (uploader, parte del pipeline):
alias tg_logs='docker compose -f $DEVJOBS/downloader_telegram/docker-compose.yml logs -f uploader'
alias tg_stop='docker stop telegram-uploader'
alias tg_restart='docker restart telegram-uploader'
# MANUAL (telegram, clonador/interactivo):
alias tg_menu='docker compose -f $DEVJOBS/downloader_telegram/docker-compose.yml run --rm telegram'
alias tg_sessions='docker compose -f $DEVJOBS/downloader_telegram/docker-compose.yml run --rm telegram python test_string.py'
alias tg_manual_logs='docker compose -f $DEVJOBS/downloader_telegram/docker-compose.yml logs -f telegram'
alias tg_manual_stop='docker compose -f $DEVJOBS/downloader_telegram/docker-compose.yml stop telegram'
alias tg_down='docker compose -f $DEVJOBS/downloader_telegram/docker-compose.yml down'

# ---------- hdfull-downloader (1 instancia, --rm) ----------
alias hd_run='docker compose -f $DEVJOBS/hdfull-downloader/docker-compose.yml run --rm hdfull_downloader'
alias hd_clear='docker compose -f $DEVJOBS/hdfull-downloader/docker-compose.yml run --rm hdfull_downloader --clear-profile'
alias hd_menu='bash $DEVJOBS/hdfull-downloader/menu.sh'
alias hd_build='docker compose -f $DEVJOBS/hdfull-downloader/docker-compose.yml build --no-cache'
alias hd_logs='docker compose -f $DEVJOBS/hdfull-downloader/docker-compose.yml logs -f -t --tail=50'
alias hd_down='docker compose -f $DEVJOBS/hdfull-downloader/docker-compose.yml down'

# ---------- aula-downloader (1 instancia, --rm) ----------
alias al_run='docker compose -f $DEVJOBS/aula-downloader/docker-compose.yml run --rm aula_downloader python3 /app/aula_downloader_funciona.py'
alias al_menu='docker compose -f $DEVJOBS/aula-downloader/docker-compose.yml run --rm aula_downloader'
alias al_build='docker compose -f $DEVJOBS/aula-downloader/docker-compose.yml build'
alias al_logs='docker compose -f $DEVJOBS/aula-downloader/docker-compose.yml logs -f -t --tail=50'
alias al_down='docker compose -f $DEVJOBS/aula-downloader/docker-compose.yml down'

# ---------- TwitchRecorder ----------
# DAEMON (producción, parte del pipeline):
alias tw_logs='docker compose -f $DEVJOBS/TwitchRecorder/docker-compose.yml logs -f twitchrecorder'
alias tw_stop='docker stop twitchrecorder'
alias tw_restart='docker restart twitchrecorder'
# MANUAL (prueba puntual):
alias tw_run='docker compose -f $DEVJOBS/TwitchRecorder/docker-compose.yml run --rm run'
alias tw_dry='docker compose -f $DEVJOBS/TwitchRecorder/docker-compose.yml run --rm run --dry-run'
alias tw_down='docker compose -f $DEVJOBS/TwitchRecorder/docker-compose.yml down'

# ---------- ffmpeg-yt-dlp ----------
# DAEMON (monitor, parte del pipeline) —— ver conversión en curso:
alias ff_logs='docker compose -f $DEVJOBS/ffmpeg-yt-dlp/docker-compose.yml logs -f monitor'
alias ff_stop='docker stop ffmpeg_monitor'
alias ff_restart='docker restart ffmpeg_monitor'
# MANUAL (midu, interactivo): SOLO el servicio downloader (no toca al monitor)
alias ff_midu='docker compose -f $DEVJOBS/ffmpeg-yt-dlp/docker-compose.yml up downloader'
alias ff_manual_stop='docker compose -f $DEVJOBS/ffmpeg-yt-dlp/docker-compose.yml stop downloader'
alias ff_manual_logs='docker compose -f $DEVJOBS/ffmpeg-yt-dlp/docker-compose.yml logs -f downloader'
# Preview Watcher (host/WSL, NO Docker):
alias watcher='bash $DEVJOBS/ffmpeg-yt-dlp/preview_watcher.sh'
alias watcher_daemon='bash $DEVJOBS/ffmpeg-yt-dlp/preview_watcher.sh --daemon'
alias watcher_stop='bash $DEVJOBS/ffmpeg-yt-dlp/preview_watcher.sh --stop'
alias watcher_status='bash $DEVJOBS/ffmpeg-yt-dlp/preview_watcher.sh --status'
ALIASES2
fi

print_ok "Aliases instalados en $BASHRC. Recarga con:  source ~/.bashrc"