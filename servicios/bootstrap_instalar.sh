#!/bin/bash
# =============================================================================
#  BOOTSTRAP: montar el pipeline "Directo sendo -> comprimir -> subir a Telegram"
#  en una máquina NUEVA (Linux / WSL2 de Windows).
#
#  Uso (en WSL/Linux):
#      bash bash_script  (o: chmod +x && ./bootstrap_instalar.sh)
#
#  Qué hace:
#    1) Comprueba Docker + WSL2.
#    2) Clona / usa el repo devjobs.
#    3) Sustituye la ruta fija /home/jorge/... por la de ESTA máquina.
#    4) Crea las carpetas de videos.     5) Revisa los archivos secretos.
#    6) Construye las imágenes.          7) Instala systemd (arranque MANUAL).
#    8) Añade los alias de ~/.bashrc.
#
#  Puedes cancelar en cualquier momento con Ctrl+C; es seguro volver a lanzarlo
#  (es idempotente: no rehace lo ya hecho).
# =============================================================================
set -euo pipefail

# --- Colores (decorativo) ---
ROJO='\033[0;31m'; VERDE='\033[0;32m'; AZUL='\033[0;34m'; AMARILLO='\033[0;33m'; RESET='\033[0m'
print_ok(){   echo -e "${VERDE}[✓]${RESET} $1"; }
print_info(){ echo -e "${AZUL}[→]${RESET} $1"; }
print_warn(){ echo -e "${AMARILLO}[!]${RESET} $1"; }
print_err(){  echo -e "${ROJO}[x]${RESET} $1"; }

REPO_URL="https://github.com/jorbencas/devjobs.git"
OLD_PATH="/home/jorge/dev/devjobs"

# =============================================================================
print_info "=== Bootstrap pipeline sendo-sama ==="
print_info ""

# --- 0) Directorio del repo ---
DEVJOBS="${DEVJOBS:-$HOME/devjobs}"
while [ -e "$DEVJOBS" ]; do
    read -rp "La ruta $DEVJOBS ya existe. ¿Usarla igualmente? [s/N] " r
    case "${r,,}" in
        s|si|sí|y|yes) break ;;
        *) read -rp "Indica otra ruta (sin barra final): " DEVJOBS ;;
    esac
done

# --- 1) Docker ---
print_info "1/8 Comprobando Docker..."
if ! command -v docker >/dev/null 2>&1; then
    print_err "Docker no está instalado."
    if command -v wsl.exe >/dev/null 2>&1 || [ -n "${WSL_DISTRO_NAME:-}" ]; then
        echo "  Estás en WSL. Instala Docker Desktop para Windows:"
        echo "    https://docs.docker.com/desktop/setup/install/windows-install/"
        echo "  Luego activa la integración con tu distro:"
        echo "    Settings -> Resources -> WSL integration -> activa tu distro."
    else
        echo "  Estás en Linux. Instala docker engine (Debian/Ubuntu):"
        echo "    curl -fsSL https://get.docker.com | sh"
    fi
    print_warn "Re-lanza este script cuando Docker esté disponible."
    exit 1
fi
( docker info >/dev/null 2>&1 && print_ok "Docker OK" ) || {
    print_err "El daemon de Docker no está corriendo."
    print_warn "En WSL con Docker Desktop, abre Docker Desktop primero y espera a que esté 'Engine running'."
    exit 1
}

# --- 2) Código del repo ---
print_info "2/8 Obteniendo el código..."
if [ -d "$DEVJOBS/.git" ]; then
    print_ok "Repo ya clonado en $DEVJOBS"
else
    print_info "Clonando $REPO_URL → $DEVJOBS"
    mkdir -p "$(dirname "$DEVJOBS")"
    git clone "$REPO_URL" "$DEVJOBS"
fi
cd "$DEVJOBS"

# --- 3) Ruta fija → ruta local ---
print_info "3/8 Ajustando rutas..."
if [ "$DEVJOBS" != "$OLD_PATH" ]; then
    N=$(
      grep -rl "$OLD_PATH" \
        TwitchRecorder/docker-compose.yml \
        ffmpeg-yt-dlp/docker-compose.yml \
        downloader_telegram/docker-compose.yml \
        servicios/twitch-stream-pipeline.service \
        servicios/*.sh 2>/dev/null | wc -l
    )
    if [ "$N" -gt 0 ]; then
        for f in $(grep -rl "$OLD_PATH" \
                    TwitchRecorder/docker-compose.yml \
                    ffmpeg-yt-dlp/docker-compose.yml \
                    downloader_telegram/docker-compose.yml \
                    servicios/twitch-stream-pipeline.service \
                    servicios/*.sh 2>/dev/null); do
            sed -i "s#${OLD_PATH}#${DEVJOBS}#g" "$f"
            print_ok "ok: ${f}"
        done
    else
        print_info "No había referencias a $OLD_PATH (ruta ya genérica)."
    fi
else
    print_info "Ruta ya es $DEVJOBS (la original)."
fi

# --- 4) Carpetas ---
print_info "4/8 Creando carpetas de vídeo..."
mkdir -p "$DEVJOBS/data/grabaciones/test" "$DEVJOBS/data/comprimidos" "$DEVJOBS/data/backups" "$DEVJOBS/data/partes"
print_ok "data: grabaciones/test, comprimidos, backups y partes listas"

# --- 5) Secretos (config.bin, secret.key, uploader.session, .env, grupos.json) ---
print_info "5/8 Revisando secretos..."
DL="$DEVJOBS/downloader_telegram"
# Config de credenciales: viene de config.bin + secret.key (en gitignore).
# Si no existen, la alternativa es dotar de UPLOADER_API_ID / UPLOADER_API_HASH
# por variables de entorno en el docker-compose.
if [ ! -f "$DL/config.bin" ]; then
    print_warn "Falta $DL/config.bin (truco de credenciales cifradas)."
    if [ -f "$DL/.env" ] && grep -q "^API_IS=" "$DL/.env"; then
        print_info "Usaré UPLOADER_API_ID / UPLOADER_API_HASH desde $DL/.env."
    else
        print_warn "Sin config.bin ni .env no puedo autenticar el uploader."
        echo "  Opciones (elige una):"
        echo "    a) Copia a mano {config.bin, secret.key} desde la máquina antigua."
        echo "    b) Crea un $DL/.env con API_IS=<api_id> y API_HASH=<api_hash>."
        echo "       Luego, tras el build, corre:  bash servicios/pipe_setup.sh"
    fi
fi
# Sesión de Telegram: si no existe, se hace login con pipe_setup.
if [ ! -f "$DL/uploader.session" ]; then
    print_warn "Falta uploader.session → habrá que hacer login de Telegram tras el build."
else
    print_ok "uploader.session presente (reusa sesión)."
fi
# grupos.json: imprescindible (NO está en gitignore → suele venir del repo).
if [ ! -f "$DL/grupos.json" ]; then
    print_err "Falta $DL/grupos.json (destinos de subida)."
    echo "  Crea el archivo con el 'default' y tus grupos (ver README_UPLOADER.md)"
    echo "  o rellénalo tras el build con:  bash servicios/pipe_chats.sh --creados"
fi

SESION_AUTH=no
if [ -f "$DL/uploader.session" ]; then
    # Heurística: si config.bin existe, la sesión suele estar validada.
    [ -f "$DL/config.bin" ] && SESION_AUTH=si
fi

# --- 6) Build de imágenes ---
print_info "6/8 Construyendo imágenes Docker..."
docker compose -f "$DEVJOBS/TwitchRecorder/docker-compose.yml" build
docker compose -f "$DEVJOBS/downloader_telegram/docker-compose.yml" build
print_ok "Imágenes construidas"

# --- 7) systemd (arranque manual, SIN auto-arranque al boot) ---
print_info "7/8 Configurando systemd (arranque manual)..."
if systemctl --version >/dev/null 2>&1; then
    if [ "$DEVJOBS" != "$OLD_PATH" ]; then
        # El servicio usa rutas absolutas; asegurar que apunta a la real.
        sed -i "s#${OLD_PATH}#${DEVJOBS}#g" "$DEVJOBS/servicios/twitch-stream-pipeline.service"
    fi
    # Quitar cualquier envoltorio .env si el servicio no lo usa (compat.)
    sudo cp "$DEVJOBS/servicios/twitch-stream-pipeline.service" /etc/systemd/system/
    sudo systemctl daemon-reload
    # SIN auto-arranque al encender el PC (se arranca a mano con pipe_up o
    # "sudo systemctl start"). Si algún día se quiere al boot: habilitar con
    #   sudo systemctl enable twitch-stream-pipeline.service
    print_ok "Servicio systemd instalado (SIN auto-arranque al boot)."
else
    print_warn "No hay systemd (¿estás en WSL sin systemd?)."
    # Si es WSL, lo dejamos preparado automáticamente (no duplica [boot]).
    if [ -n "${WSL_DISTRO_NAME:-}" ] || command -v wsl.exe >/dev/null 2>&1; then
        if ! grep -q "^systemd=true" /etc/wsl.conf 2>/dev/null; then
            sudo sh -c 'sed -i "/^\[boot\]$/d" /etc/wsl.conf; printf "[boot]\nsystemd=true\n" >> /etc/wsl.conf'
            print_ok "Añadido systemd=true a /etc/wsl.conf."
        else
            print_ok "systemd=true ya está en /etc/wsl.conf."
        fi
        print_warn "Reinicia WSL desde PowerShell con:  wsl --shutdown"
        print_warn "Vuelve a lanzar este script después para instalar el servicio."
    else
        print_warn "Prueba iniciar WSL con systemd (añadir en /etc/wsl.conf):"
        echo "  [boot]"
        echo "  systemd=true"
        echo "  Y reinicia WSL (wsl --shutdown). Vuelve a lanzar este script después."
    fi
fi

# --- 8) Aliases ---
print_info "8/8 Instalando alias de ~/.bashrc..."
BASHRC="$HOME/.bashrc"
if grep -q "alias plogs=" "$BASHRC" 2>/dev/null; then
    print_info "Aliases ya presentes, se omite."
elif [ -f "$DEVJOBS/servicios/instalar_aliases.sh" ]; then
    bash "$DEVJOBS/servicios/instalar_aliases.sh"
else
    # Bloque de aliases hardcodeado (fallback si no existe el instalador).
    cat >> "$BASHRC" <<'ALIASES'

# ---------- Pipeline "Directo sendo -> comprimir -> subir" ----------
alias plogs='bash '"$DEVJOBS"'/servicios/pipeline_logs.sh'
alias pipe_setup='bash '"$DEVJOBS"'/servicios/pipe_setup.sh'
alias pipe_chats='bash '"$DEVJOBS"'/servicios/pipe_chats.sh'
alias pipe_rebuild='bash '"$DEVJOBS"'/servicios/pipe_rebuild.sh'
alias pipe_test='bash '"$DEVJOBS"'/servicios/pipe_test_upload.sh'
alias pipe_up='docker compose -f '"$DEVJOBS"'/TwitchRecorder/docker-compose.yml up -d twitchrecorder && docker compose -f '"$DEVJOBS"'/ffmpeg-yt-dlp/docker-compose.yml up -d monitor && docker compose -f '"$DEVJOBS"'/downloader_telegram/docker-compose.yml up -d uploader'
alias pipe_recreate='docker compose -f '"$DEVJOBS"'/TwitchRecorder/docker-compose.yml up -d --force-recreate twitchrecorder && docker compose -f '"$DEVJOBS"'/ffmpeg-yt-dlp/docker-compose.yml up -d --force-recreate monitor && docker compose -f '"$DEVJOBS"'/downloader_telegram/docker-compose.yml up -d --force-recreate uploader'
alias pipe_down='docker compose -f '"$DEVJOBS"'/TwitchRecorder/docker-compose.yml down && docker compose -f '"$DEVJOBS"'/ffmpeg-yt-dlp/docker-compose.yml down && docker compose -f '"$DEVJOBS"'/downloader_telegram/docker-compose.yml down'
alias pipe_ps='docker ps --filter name=twitchrecorder --filter name=ffmpeg_monitor --filter name=telegram-uploader --format "table {{.Names}}\t{{.Status}}"'
alias pipe_sys_start='sudo systemctl start twitch-stream-pipeline.service'
alias pipe_sys_stop='sudo systemctl stop twitch-stream-pipeline.service'
alias pipe_sys_status='systemctl status twitch-stream-pipeline.service'
ALIASES
    print_ok "Aliases del pipeline añadidos."
fi

# =============================================================================
print_info ""
print_ok "=== Bootstrap terminado ==="
echo ""
echo "  Recarga los alias:   source ~/.bashrc"
echo "  La sesión de Telegram:"
if [ "$SESION_AUTH" = "no" ] && [ ! -f "$DL/uploader.session" ]; then
    echo "    bash servicios/pipe_setup.sh   (pide teléfono + código, UNA vez)"
fi
if [ -f "$DL/config.bin" ]; then
    echo "    El config.bin ya está → credenciales OK."
else
    echo "    Recuerda: sin config.bin/.env no hay credenciales (ver paso 5)."
fi
echo ""
echo "  Código suelto:"
if command -v systemctl >/dev/null 2>&1; then
    echo "    sudo systemctl start twitch-stream-pipeline.service   (levanta todo, a mano)"
    echo "    (NO se arranca solo al boot. Para activarlo:"
    echo "     sudo systemctl enable twitch-stream-pipeline.service)"
fi
echo "    source ~/.bashrc && pipe_up        # levantar sin systemd"
echo "    plogs                              # ver los logs de los 3 servicios"
echo ""
print_warn "Carpetas compartidas en Windows: accede a ellas desde Explorador"
print_warn "con \\\\wsl$\\<distro>\\<ruta_devjobs>  (o \\wsl.localhost\\...) para"
print_warn "comprobar los vídeos que se van generando."