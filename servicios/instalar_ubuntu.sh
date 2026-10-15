#!/bin/bash
# =============================================================================
#  INSTALADOR TODO-EN-UNO (Ubuntu 64 bits) — pipeline "directo sendo"
#  = grabadora (TwitchRecorder) + compresor (ffmpeg-yt-dlp) + uploader Telegram.
#
#  Hace, de un tirón y de forma idempotente (puedes relanzarlo sin miedo):
#    1) Instala dependencias del sistema y Docker (Engine + compose plugin).
#    2) Localiza el repo (o lo clona si no lo encuentra).
#    3) Crea las carpetas de vídeo (data/pipeline/...).
#    4) Comprueba los secretos (config/, sessions/) y avisa de lo que falte.
#    5) Construye las imágenes Docker.
#    6) Arranca grabadora + compresor (+ uploader si hay secretos).
#    7) Instala y habilita systemd (auto-arranque al encender el PC).
#    8) Instala los alias del pipeline en ~/.bashrc.
#
#  Uso:
#      bash servicios/instalar_ubuntu.sh
#
#  NO lo ejecutes como root ni con sudo: el script pide sudo cuando lo necesita.
# =============================================================================
set -euo pipefail

ROJO='\033[0;31m'; VERDE='\033[0;32m'; AZUL='\033[0;34m'; AMARILLO='\033[0;33m'; RESET='\033[0m'
ok(){   echo -e "${VERDE}[✓]${RESET} $1"; }
info(){ echo -e "${AZUL}[→]${RESET} $1"; }
warn(){ echo -e "${AMARILLO}[!]${RESET} $1"; }
err(){  echo -e "${ROJO}[x]${RESET} $1"; }

uso(){
    cat <<'TXT'
Instalador todo-en-uno (Ubuntu 64 bits) del pipeline "directo sendo".

  bash servicios/instalar_ubuntu.sh

Instala Docker, prepara carpetas y secretos, construye las imágenes, arranca
grabadora + compresor + uploader y deja el auto-arranque configurado (systemd).
Es idempotente: puedes relanzarlo tantas veces como quieras.

  -h, --help   Muestra esta ayuda.
TXT
}

case "${1:-}" in
    -h|--help) uso; exit 0 ;;
esac

REPO_URL="https://github.com/jorbencas/devjobs.git"

# ----------------------------------------------------------------------------
# 0) Comprobaciones previas
# ----------------------------------------------------------------------------
if [ "$(id -u)" -eq 0 ]; then
    err "No lo ejecutes como root/sudo (el script pide sudo cuando lo necesita)."
    err "Ejecútalo como tu usuario:  bash servicios/instalar_ubuntu.sh"
    exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
    err "Este instalador es para Ubuntu/Debian (no encuentro apt-get)."
    exit 1
fi

ARCH="$(dpkg --print-architecture 2>/dev/null || echo desconocida)"
if [ "$ARCH" != "amd64" ] && [ "$ARCH" != "arm64" ]; then
    warn "Arquitectura '$ARCH' (no amd64/arm64). Docker puede no estar disponible."
fi

# ----------------------------------------------------------------------------
# 1) Docker (Engine + compose plugin)
# ----------------------------------------------------------------------------
info "1/8 Instalando/verificando Docker..."

# ¿Docker está presente Y respondiendo? No basta con que exista el binario:
# p. ej. en WSL el "shim" existe aunque la integración esté apagada.
docker_ok(){ docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; }

if command -v docker >/dev/null 2>&1 && docker_ok; then
    ok "Docker ya instalado y funcionando: $(docker --version 2>/dev/null | cut -d, -f1)"
else
    if command -v docker >/dev/null 2>&1; then
        warn "Existe un 'docker' pero no responde (daemon parado o integración WSL off). Instalando/arrancando..."
    fi
    case "$(. /etc/os-release && echo "$VERSION_ID")" in
        20.04|22.04|24.04) ;;
        *) warn "Ubuntu $(. /etc/os-release && echo "${VERSION_ID:-?}"): no es un LTS moderno; el repo oficial de Docker puede no tener paquetes para esta versión. Si falla, usa Ubuntu 20.04 / 22.04 / 24.04." ;;
    esac
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg git
    sudo install -m 0755 -d /etc/apt/keyrings
    if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
            | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
    fi
    CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME:-}")"
    echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo systemctl enable --now docker
    ok "Docker instalado y arrancado."
fi

# Asegurar el plugin 'docker compose' (v2).
if ! (docker compose version >/dev/null 2>&1 || sudo docker compose version >/dev/null 2>&1); then
    warn "Falta el plugin 'docker compose'; instalándolo..."
    sudo apt-get update -y
    sudo apt-get install -y docker-compose-plugin
fi

command -v git >/dev/null 2>&1 || sudo apt-get install -y git

# Permisos del usuario sobre el socket de Docker.
if ! id -nG "$USER" | grep -qw docker; then
    sudo usermod -aG docker "$USER"
    warn "Añadido '$USER' al grupo docker (efecto permanente tras re-loguear)."
fi

# Cómo invocar docker DURANTE este script (si el grupo aún no aplica, con sudo).
DOCKER="docker"
if ! docker info >/dev/null 2>&1; then DOCKER="sudo docker"; fi
DOCKER_BIN="$(command -v docker || echo /usr/bin/docker)"

# ----------------------------------------------------------------------------
# 2) Repo
# ----------------------------------------------------------------------------
info "2/8 Localizando el código..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CANDIDATE="$(dirname "$SCRIPT_DIR")"
if [ -d "$CANDIDATE/.git" ]; then
    ROOT="$CANDIDATE"
else
    ROOT="${DEVJOBS:-$HOME/devjobs}"
fi

if [ -d "$ROOT/.git" ]; then
    ok "Repo en $ROOT"
else
    info "Clonando $REPO_URL → $ROOT"
    mkdir -p "$(dirname "$ROOT")"
    git clone "$REPO_URL" "$ROOT"
fi
cd "$ROOT"

# ----------------------------------------------------------------------------
# 3) Carpetas de vídeo
# ----------------------------------------------------------------------------
info "3/8 Creando carpetas..."
mkdir -p "$ROOT/data/pipeline/grabaciones/test" \
         "$ROOT/data/pipeline/comprimidos" \
         "$ROOT/data/pipeline/partes"
mkdir -p "$ROOT/downloader_telegram/config" "$ROOT/downloader_telegram/sessions"
ok "data/pipeline/{grabaciones/test,comprimidos,partes}, config/ y sessions/ listas."

# ----------------------------------------------------------------------------
# 4) Secretos
# ----------------------------------------------------------------------------
info "4/8 Comprobando secretos..."
DL="$ROOT/downloader_telegram"
CREDS_OK=0; GRUPOS_OK=0; SESION_OK=0

for f in "$DL/config/config.bin" "$DL/config/secret.key"; do
    if [ -f "$f" ]; then ok "presente: ${f#"$ROOT"/}"; else warn "FALTA: ${f#"$ROOT"/}"; fi
done
[ -f "$DL/config/config.bin" ] && [ -f "$DL/config/secret.key" ] && CREDS_OK=1

if [ -f "$DL/config/grupos.json" ]; then
    ok "presente: downloader_telegram/config/grupos.json"; GRUPOS_OK=1
else
    warn "FALTA: downloader_telegram/config/grupos.json (destinos de subida)."
fi

if [ -f "$DL/sessions/uploader.session" ]; then
    ok "presente: downloader_telegram/sessions/uploader.session"; SESION_OK=1
else
    warn "FALTA: downloader_telegram/sessions/uploader.session (login de Telegram)."
fi

if [ "$CREDS_OK" -eq 0 ]; then
    warn "Sin credenciales el uploader no podrá subir nada. Tráelas de la máquina antigua:"
    echo "    scp USUARIO@ANTIGUO:~/devjobs/downloader_telegram/config/config.bin   $DL/config/"
    echo "    scp USUARIO@ANTIGUO:~/devjobs/downloader_telegram/config/secret.key   $DL/config/"
    echo "    scp USUARIO@ANTIGUO:~/devjobs/downloader_telegram/config/grupos.json  $DL/config/"
    echo "    scp USUARIO@ANTIGUO:~/devjobs/downloader_telegram/sessions/uploader.session $DL/sessions/"
fi

# ----------------------------------------------------------------------------
# 5) Build de imágenes
# ----------------------------------------------------------------------------
info "5/8 Construyendo imágenes (puede tardar unos minutos)..."
$DOCKER compose -f "$ROOT/TwitchRecorder/docker-compose.yml" build
$DOCKER compose -f "$ROOT/ffmpeg-yt-dlp/docker-compose.yml" build monitor
$DOCKER compose -f "$ROOT/downloader_telegram/docker-compose.yml" build uploader
ok "Imágenes construidas."

# ----------------------------------------------------------------------------
# 6) Arranque
# ----------------------------------------------------------------------------
info "6/8 Arrancando servicios..."
$DOCKER compose -f "$ROOT/TwitchRecorder/docker-compose.yml" up -d twitchrecorder
$DOCKER compose -f "$ROOT/ffmpeg-yt-dlp/docker-compose.yml" up -d monitor

if [ "$CREDS_OK" -eq 1 ] && [ "$GRUPOS_OK" -eq 1 ] && [ "$SESION_OK" -eq 1 ]; then
    $DOCKER compose -f "$ROOT/downloader_telegram/docker-compose.yml" up -d uploader
    ok "Grabadora + compresor + uploader arrancados."
else
    warn "No arranco el uploader (faltan secretos). Cuando los tengas:"
    echo "    docker compose -f $ROOT/downloader_telegram/docker-compose.yml up -d uploader"
fi

$DOCKER ps --filter name=twitchrecorder-sendo --filter name=ffmpeg_monitor-sendo \
           --filter name=telegram-uploader-sendo \
           --format "table {{.Names}}\t{{.Status}}"

# ----------------------------------------------------------------------------
# 7) systemd (auto-arranque al boot)
# ----------------------------------------------------------------------------
info "7/8 Configurando auto-arranque (systemd)..."
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
    sudo tee /etc/systemd/system/twitch-stream-pipeline.service >/dev/null <<UNIT
[Unit]
Description=Pipeline Directos sendo sama (grabar + comprimir + subir a Telegram)
After=docker.service network-online.target
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=$USER
SupplementaryGroups=docker
WorkingDirectory=$ROOT
ExecStart=$DOCKER_BIN compose -f $ROOT/TwitchRecorder/docker-compose.yml up -d twitchrecorder
ExecStart=$DOCKER_BIN compose -f $ROOT/ffmpeg-yt-dlp/docker-compose.yml up -d monitor
ExecStart=$DOCKER_BIN compose -f $ROOT/downloader_telegram/docker-compose.yml up -d uploader
ExecStop=$DOCKER_BIN compose -f $ROOT/TwitchRecorder/docker-compose.yml down
ExecStop=$DOCKER_BIN compose -f $ROOT/ffmpeg-yt-dlp/docker-compose.yml down
ExecStop=$DOCKER_BIN compose -f $ROOT/downloader_telegram/docker-compose.yml down

[Install]
WantedBy=multi-user.target
UNIT
    sudo systemctl daemon-reload
    sudo systemctl enable twitch-stream-pipeline.service
    ok "Servicio 'twitch-stream-pipeline' habilitado (arranca al encender el PC)."
else
    warn "No hay systemd activo. Arranca a mano con:  source ~/.bashrc && pipe_up"
fi

# ----------------------------------------------------------------------------
# 8) Alias
# ----------------------------------------------------------------------------
info "8/8 Instalando alias..."
if [ -f "$ROOT/servicios/instalar_aliases.sh" ]; then
    bash "$ROOT/servicios/instalar_aliases.sh"
else
    warn "No encuentro servicios/instalar_aliases.sh (se omite)."
fi

# ----------------------------------------------------------------------------
# Resumen
# ----------------------------------------------------------------------------
echo ""
ok "=== Instalación terminada ==="
echo ""
echo "  Recarga la shell para tener los alias:   source ~/.bashrc"
echo ""
echo "  Comandos útiles:"
echo "    plogs            # ver logs de grabadora + compresor + uploader"
echo "    pipe_ps          # estado de los 3 contenedores"
echo "    pipe_down        # parar todo"
echo "    pipe_up          # levantar todo"
echo "    pipe_sys_status  # estado del auto-arranque (systemd)"
echo ""
if [ "$CREDS_OK" -eq 0 ] || [ "$GRUPOS_OK" -eq 0 ] || [ "$SESION_OK" -eq 0 ]; then
    warn "Recuerda: el uploader necesita config.bin, secret.key, grupos.json y uploader.session."
    warn "Si falta la sesión, haz el login UNA vez:  bash servicios/pipe_setup.sh"
else
    ok "Todos los secretos presentes."
fi
echo ""
warn "Si acabas de entrar al grupo docker, cierra sesión y vuelve a entrar (o reinicia) para no necesitar sudo."
