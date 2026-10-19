#!/bin/bash
# =============================================================================
#  diagnostico_docker — ¿Por qué falla 'docker'/'docker compose' como usuario?
#
#  Uso:   bash servicios/diagnostico_docker.sh
#
#  No cambia NADA: solo imprime el estado y sugiere el arreglo exacto.
#  Distingue los 3 fallos típicos:
#    - 'permission denied'  → tu usuario no está en el grupo del socket.
#    - 'cannot connect'     → el daemon Docker no está arrancado.
#    - 'unknown flag'/v1    → 'docker compose' es la v1 vieja (falta el plugin).
# =============================================================================
set -uo pipefail

ROJO='\033[0;31m'; VERDE='\033[0;32m'; AZUL='\033[0;34m'; AMARILLO='\033[0;33m'; RESET='\033[0m'
ok(){   echo -e "${VERDE}[✓]${RESET} $1"; }
info(){ echo -e "${AZUL}[→]${RESET} $1"; }
warn(){ echo -e "${AMARILLO}[!]${RESET} $1"; }
err(){  echo -e "${ROJO}[x]${RESET} $1"; }

U="$(id -un)"
echo ""
echo "DEVJOBS — diagnóstico de Docker (usuario no-root)"
echo "================================================="
info "Usuario: $U (uid $(id -u))"
info "Grupos:  $(id -nG)"
echo ""

# 1) ¿Existe 'docker' y de dónde sale?
DOCKER_BIN="$(command -v docker || true)"
if [ -z "$DOCKER_BIN" ]; then
    err "No encuentro el comando 'docker'."
    echo "    → Instálalo:  bash servicios/instalar_ubuntu.sh"
    exit 1
fi
REAL="$(readlink -f "$DOCKER_BIN" 2>/dev/null || echo "$DOCKER_BIN")"
info "Binario: $DOCKER_BIN"
case "$REAL" in
    */snap/*)
        warn "Es un Docker de SNAP ($REAL). El repo oficial (docker-ce) vive en /usr/bin/docker."
        warn "Tener snap + .deb a la vez mezcla sockets/grupos."
        echo "    → Quita uno (recomendado el snap):  sudo snap remove docker"
        ;;
esac
if dpkg -S "$REAL" >/dev/null 2>&1; then
    info "Paquete del CLI: $(dpkg -S "$REAL" 2>/dev/null | cut -d: -f1)"
else
    warn "El CLI 'docker' no lo provee ningún paquete .deb (¿snap, WSL o copia manual?)."
fi
echo ""

# 2) Grupo del socket.
if getent group docker >/dev/null 2>&1; then
    ok "Grupo 'docker': $(getent group docker)"
else
    warn "No existe el grupo 'docker'."
fi

SOCK="/var/run/docker.sock"
SOCK_GROUP="docker"
if [ -S "$SOCK" ]; then
    SOCK_GROUP="$(stat -c '%G' "$SOCK" 2>/dev/null || echo docker)"
    info "Socket: $(ls -l "$SOCK" 2>/dev/null)"
    if id -nG "$U" | grep -qw "$SOCK_GROUP"; then
        ok "Perteneces al grupo del socket ('$SOCK_GROUP')."
    else
        err "NO perteneces al grupo del socket ('$SOCK_GROUP') → 'permission denied'."
        echo "    → sudo usermod -aG $SOCK_GROUP $U    y luego cierra/abre sesión (o 'newgrp $SOCK_GROUP')"
    fi
    if [ "$SOCK_GROUP" = "root" ]; then
        warn "El socket es root:root (dockerd arrancó sin el grupo 'docker')."
        echo "    → sudo systemctl restart docker    (lo recreará como root:docker)"
    fi
else
    warn "No existe el socket $SOCK → el daemon no está corriendo."
    echo "    → sudo systemctl enable --now docker"
fi
echo ""

# 3) ¿Responde sin sudo?
if docker info >/dev/null 2>&1; then
    ok "'docker info' funciona sin sudo."
else
    DINFO="$(docker info 2>&1 || true)"
    err "'docker info' falla sin sudo:"
    echo "$DINFO" | sed 's/^/      /'
    if echo "$DINFO" | grep -qi 'permission denied'; then
        echo "    → Falta grupo:  sudo usermod -aG $SOCK_GROUP $U   + cierra/abre sesión"
    elif echo "$DINFO" | grep -qi 'cannot connect'; then
        echo "    → Daemon parado:  sudo systemctl enable --now docker"
    fi
fi
echo ""

# 4) ¿compose v2 (plugin) o v1 vieja?
info "docker --version: $(docker --version 2>&1 | head -1)"
CERR="$(docker compose version 2>&1 || true)"
if docker compose version >/dev/null 2>&1; then
    CV="$(docker compose version --short 2>/dev/null || docker compose version 2>/dev/null | head -1)"
    ok "docker compose (v2): $CV"
elif command -v docker-compose >/dev/null 2>&1; then
    warn "Solo existe 'docker-compose' (v1): $(docker-compose version --short 2>/dev/null | head -1)"
    echo "    → El pipeline usa 'docker compose' (v2). Instala el plugin y quita la v1:"
    echo "        sudo apt-get update && sudo apt-get install -y docker-compose-plugin"
    echo "        sudo apt-get remove -y docker-compose"
else
    err "No funciona 'docker compose' (ni existe el binario 'docker-compose' v1)."
    echo "    Error exacto de 'docker compose version':"
    echo "$CERR" | sed 's/^/      /'

    # Versión del CLI (los plugins 'docker compose' necesitan CLI >= 19.03).
    DVER="$(docker --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
    [ -n "$DVER" ] && info "Versión del CLI 'docker': $DVER  (los plugins necesitan >= 19.03)"

    # ¿Está el plugin v2 instalado en disco? ¿Funciona por sí solo?
    PLUG=0
    for p in /usr/libexec/docker/cli-plugins/docker-compose \
             /usr/lib/docker/cli-plugins/docker-compose \
             /usr/local/lib/docker/cli-plugins/docker-compose \
             "$HOME/.docker/cli-plugins/docker-compose"; do
        if [ -f "$p" ]; then
            info "Plugin v2 presente en disco: $p"
            PLUG=1
            if [ -x "$p" ]; then
                ok "El plugin funciona por sí solo: $("$p" version 2>&1 | head -1)"
                echo "    → Tu CLI 'docker' es viejo y NO soporta plugins. Instala el CLI moderno:"
                echo "        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin"
            fi
        fi
    done

    if echo "$CERR" | grep -qi "is not a docker command"; then
        echo "    → Es docker pero SIN el plugin v2:  sudo apt-get install -y docker-compose-plugin"
    elif echo "$CERR" | grep -qiE "command not found|no se encontró|not found"; then
        echo "    → No hay CLI de Docker (o no está en el PATH):  bash servicios/instalar_ubuntu.sh"
    elif [ "$PLUG" -eq 1 ]; then
        echo "    → El plugin existe pero tu 'docker' no lo ve. Suele ser un CLI viejo"
        echo "       (docker.io 18.09) o otro docker (snap/WSL). Instala docker-ce:"
        echo "        sudo apt-get install -y docker-ce docker-ce-cli containerd.io"
    else
        echo "    → Falta el plugin:  sudo apt-get install -y docker-compose-plugin"
    fi
fi
echo ""

# 5) Resumen.
echo "Comprobación final:  docker ps"
if docker ps >/dev/null 2>&1; then
    ok "¡Todo listo! Ya puedes usar Docker sin sudo."
else
    warn "Aún falla. Aplica el '→' de arriba y reinicia la sesión (cerrar/abrir)."
fi
echo ""
