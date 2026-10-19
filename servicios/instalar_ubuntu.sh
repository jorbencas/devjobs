#!/bin/bash
# =============================================================================
#  INSTALADOR TODO-EN-UNO (Ubuntu 64 bits) — pipeline "directo sendo"
#  = grabadora (TwitchRecorder) + compresor (ffmpeg-yt-dlp) + uploader Telegram.
#
#  Hace, de un tirón y de forma idempotente (puedes relanzarlo sin miedo):
#    1) Instala dependencias del sistema y Docker (Engine + compose plugin),
#       mete tu usuario en el grupo 'docker' y comprueba que 'docker compose'
#       es la v2 (flags como --rm fallan con una v1 vieja).
#       En Ubuntu antiguo/EOL (p. ej. 18.10) repunta apt a old-releases y usa el
#       repo de Docker de bionic (glibc compatible) para tener 'docker compose' v2.
#    2) Localiza el repo (o lo clona si no lo encuentra).
#    3) Crea las carpetas de vídeo (data/pipeline/...).
#    4) Comprueba los secretos (config/, sessions/) y avisa de lo que falte.
#    5) Construye las imágenes Docker (solo si faltan; usa --rebuild para forzar).
#    6) Arranca grabadora + compresor (+ uploader si hay secretos).
#    7) Instala y habilita systemd (auto-arranque al encender el PC).
#    8) Instala los alias del pipeline en ~/.bashrc.
#    9) Sincroniza la hora (NTP) y limita los logs de Docker (rotación).
#
#  Uso:
#      bash servicios/instalar_ubuntu.sh [--rebuild]
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
  --rebuild    Fuerza reconstruir las imágenes (por defecto solo se construyen
               si faltan; así relanzar el instalador no recompila nada).
TXT
}

REBUILD=0
case "${1:-}" in
    -h|--help) uso; exit 0 ;;
    --rebuild) REBUILD=1 ;;
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

# Usuario real que ejecuta el script (para el grupo docker y el servicio systemd).
TARGET_USER="$(id -un)"

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
info "1/9 Instalando/verificando Docker..."

# ¿Docker está presente Y respondiendo? No basta con que exista el binario:
# p. ej. en WSL el "shim" existe aunque la integración esté apagada.
docker_ok(){ docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; }

if command -v docker >/dev/null 2>&1 && docker_ok; then
    ok "Docker ya instalado y funcionando: $(docker --version 2>/dev/null | cut -d, -f1)"
else
    if command -v docker >/dev/null 2>&1; then
        warn "Existe un 'docker' pero no responde (daemon parado o integración WSL off). Instalando/arrancando..."
    fi
    CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME:-}")"
    VERSION_ID="$(. /etc/os-release && echo "${VERSION_ID:-}")"

    # Versiones antiguas/EOL (p. ej. 18.10 "cosmic") no tienen repos de Ubuntu
    # (hay que usar old-releases) NI un repo propio de Docker con 'docker compose'
    # v2: usamos el repo de Docker de "bionic" (glibc compatible) que sí lo trae.
    EOL=0
    if [ -n "$VERSION_ID" ] && dpkg --compare-versions "$VERSION_ID" lt 20.04 2>/dev/null; then
        EOL=1
    fi

    if [ "$EOL" -eq 1 ]; then
        DOCKER_DIST="bionic"
        warn "Ubuntu '$CODENAME' ($VERSION_ID) es antiguo/EOL."
        info "  → apt usará old-releases.ubuntu.com y Docker el repo 'bionic'."
        if [ -f /etc/apt/sources.list ]; then
            if [ ! -f /etc/apt/sources.list.bak-devjobs ]; then
                sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak-devjobs
                ok "Backup: /etc/apt/sources.list.bak-devjobs"
            fi
            sudo sed -i -E \
                -e 's#https?://[a-z0-9.-]*archive\.ubuntu\.com#http://old-releases.ubuntu.com#g' \
                -e 's#https?://[a-z0-9.-]*security\.ubuntu\.com#http://old-releases.ubuntu.com#g' \
                /etc/apt/sources.list
            ok "sources.list → old-releases.ubuntu.com"
        fi
    else
        DOCKER_DIST="$CODENAME"
    fi

    sudo apt-get update -y || warn "apt-get update dio errores (continúo)."
    sudo apt-get install -y ca-certificates curl gnupg git

    # En EOL, libseccomp2 del sistema es demasiado viejo para containerd moderno
    # (exige >= 2.5.0). Instalamos el de focal-updates (ABI compatible; solo libc6).
    if [ "$EOL" -eq 1 ] && [ "$ARCH" = "amd64" ]; then
        SECC="$(dpkg-query -W -f='${Version}' libseccomp2 2>/dev/null || echo 0)"
        if ! dpkg --compare-versions "$SECC" ge 2.5.0 2>/dev/null; then
            info "Actualizando libseccomp2 ($SECC → 2.5.1) para containerd..."
            tmpd="$(mktemp -d)"
            if curl -fsSL -o "$tmpd/libseccomp2.deb" \
                 "https://archive.ubuntu.com/ubuntu/pool/main/libs/libseccomp/libseccomp2_2.5.1-1ubuntu1~20.04.2_amd64.deb"; then
                sudo dpkg -i "$tmpd/libseccomp2.deb" || sudo apt-get -f install -y
            else
                warn "No pude bajar libseccomp2 2.5.1; Docker podría no instalar."
            fi
            rm -rf "$tmpd"
        else
            ok "libseccomp2 ya es >= 2.5.0 ($SECC)."
        fi
    fi

    sudo install -m 0755 -d /etc/apt/keyrings
    if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
            | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
    fi
    echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $DOCKER_DIST stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update -y || warn "apt-get update (repo Docker) dio errores."
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

# Permisos del usuario sobre el socket de Docker: debe estar en el grupo 'docker'.
if ! getent group docker >/dev/null 2>&1; then
    sudo groupadd docker
    ok "Grupo 'docker' creado."
fi
if id -nG "$TARGET_USER" | grep -qw docker; then
    ok "El usuario '$TARGET_USER' ya pertenece al grupo 'docker'."
else
    sudo usermod -aG docker "$TARGET_USER"
    warn "Añadido '$TARGET_USER' al grupo 'docker'."
    warn "No surte efecto en esta sesión: cierra sesión y vuelve a entrar," \
         "o ejecuta 'newgrp docker' (o usa sudo mientras tanto)."
fi

# Cómo invocar docker DURANTE este script (si el grupo aún no aplica, con sudo).
DOCKER="docker"
if ! docker info >/dev/null 2>&1; then DOCKER="sudo docker"; fi
DOCKER_BIN="$(command -v docker || echo /usr/bin/docker)"

# Verificar que 'docker compose' es la v2 (plugin). Si es una v1 vieja o un docker
# antiguo, muchos flags (p. ej. --rm) dan "unknown flag"/error.
if $DOCKER compose version 2>/dev/null | grep -qE 'v2\.|version v2'; then
    ok "docker compose v2 detectado ($( { $DOCKER compose version --short 2>/dev/null; } | head -1 ))."
else
    warn "El comando 'docker compose' no parece la v2 → flags como --rm pueden fallar."
    warn "Comprueba:  docker compose version   (debe decir 'Docker Compose version v2.x')"
    warn "Si tienes una v1 vieja, bórrala:  sudo apt-get remove -y docker-compose"
fi

# ----------------------------------------------------------------------------
# 2) Repo
# ----------------------------------------------------------------------------
info "2/9 Localizando el código..."
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
info "3/9 Creando carpetas..."
mkdir -p "$ROOT/data/pipeline/grabaciones/test" \
         "$ROOT/data/pipeline/comprimidos" \
         "$ROOT/data/pipeline/partes"
mkdir -p "$ROOT/downloader_telegram/config" "$ROOT/downloader_telegram/sessions"
ok "data/pipeline/{grabaciones/test,comprimidos,partes}, config/ y sessions/ listas."

# ----------------------------------------------------------------------------
# 4) Secretos
# ----------------------------------------------------------------------------
info "4/9 Comprobando secretos..."
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
# 5) Build de imágenes (solo si faltan, salvo --rebuild)
# ----------------------------------------------------------------------------
info "5/9 Imágenes Docker..."
construir=0
if [ "$REBUILD" -eq 1 ]; then
    construir=1
else
    REPO_IMGS="$($DOCKER images --format '{{.Repository}}' 2>/dev/null || true)"
    if grep -q 'twitchrecorder' <<<"$REPO_IMGS" \
       && grep -qE 'ffmpeg[_-]yt[_-]dlp' <<<"$REPO_IMGS" \
       && grep -qE 'downloader[_-]telegram' <<<"$REPO_IMGS"; then
        construir=0
    else
        construir=1
    fi
fi
if [ "$construir" -eq 1 ]; then
    info "Construyendo imágenes (puede tardar unos minutos)..."
    $DOCKER compose -f "$ROOT/TwitchRecorder/docker-compose.yml" build
    $DOCKER compose -f "$ROOT/ffmpeg-yt-dlp/docker-compose.yml" build monitor
    $DOCKER compose -f "$ROOT/downloader_telegram/docker-compose.yml" build uploader
    ok "Imágenes construidas."
else
    ok "Imágenes ya construidas (usa --rebuild para reconstruirlas)."
fi

# ----------------------------------------------------------------------------
# 6) Arranque
# ----------------------------------------------------------------------------
info "6/9 Arrancando servicios..."
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
info "7/9 Configurando auto-arranque (systemd)..."
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
User=$TARGET_USER
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
info "8/9 Instalando alias..."
if [ -f "$ROOT/servicios/instalar_aliases.sh" ]; then
    bash "$ROOT/servicios/instalar_aliases.sh"
else
    warn "No encuentro servicios/instalar_aliases.sh (se omite)."
fi

# ----------------------------------------------------------------------------
# 9) Hora (NTP) y rotación de logs de Docker
# ----------------------------------------------------------------------------
info "9/9 Sincronizando hora y límite de logs de Docker..."

# 9a) Reloj sincronizado (Telegram/MTProto es muy sensible a la hora).
if command -v timedatectl >/dev/null 2>&1; then
    if [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null || echo no)" != "yes" ]; then
        sudo apt-get install -y systemd-timesyncd >/dev/null 2>&1 || true
        if sudo timedatectl set-ntp true 2>/dev/null; then
            ok "NTP activado (la hora se sincroniza sola)."
        else
            warn "No pude activar NTP; revisa la hora a mano (date -u)."
        fi
    else
        ok "Hora ya sincronizada por NTP."
    fi
else
    warn "Sin 'timedatectl' (¿no es systemd?): asegúrate de que la hora sea correcta."
fi

# 9b) Rotación de logs de Docker (evita llenar el disco corriendo 24/7).
DAEMON_JSON=/etc/docker/daemon.json
NUEVO_DAEMON=0
if [ ! -f "$DAEMON_JSON" ]; then
    echo '{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }' \
        | sudo tee "$DAEMON_JSON" >/dev/null
    NUEVO_DAEMON=1
elif ! grep -q '"max-size"' "$DAEMON_JSON" 2>/dev/null; then
    warn "Ya existe $DAEMON_JSON sin límite de logs; NO lo toco (añade 'log-opts' a mano si quieres)."
else
    ok "Rotación de logs de Docker ya configurada."
fi
if [ "$NUEVO_DAEMON" -eq 1 ]; then
    sudo systemctl restart docker 2>/dev/null || true
    ok "Docker limitará los logs (10 MB × 3 por contenedor)."
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
# Verificación final: ¿puede tu usuario usar docker sin sudo ya?
echo ""
if docker info >/dev/null 2>&1; then
    ok "Tu usuario ya puede usar Docker/'docker compose' sin sudo."
else
    warn "Tu usuario AÚN necesita sudo para docker en esta sesión."
    warn "Cierra sesión y vuelve a entrar (o reinicia), o ejecuta:  newgrp docker"
    warn "Y comprueba:  docker ps   (debe listar sin 'permission denied')."
fi

