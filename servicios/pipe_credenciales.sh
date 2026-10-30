#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DL="$ROOT/downloader_telegram"
RESET=0
ASK_BOT=1
BOT_TOKEN_ARG=""

usage() {
    cat <<'EOF'
Uso: bash servicios/pipe_credenciales.sh [opciones]

Genera en ESTA máquina:
  - downloader_telegram/config/config.bin + secret.key (API_ID / API_HASH)
  - downloader_telegram/sessions/uploader.session (login con teléfono + código)
  - BOT_TOKEN en downloader_telegram/.env (opcional)

Opciones:
  --reset             Borra uploader.session antes de volver a loguear
  --bot-token TOKEN   Guarda ese BOT_TOKEN sin preguntar
  --no-bot            No toca el BOT_TOKEN
  -h, --help          Muestra esta ayuda

IMPORTANTE: el token del bot NO se genera aquí. Se crea en Telegram con
@BotFather (/newbot) y se pega en este script. El teléfono + código sirven
para crear la sesión de la cuenta que sube los vídeos (uploader).
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --reset)
            RESET=1
            ;;
        --bot-token)
            shift
            [ $# -gt 0 ] || { echo "[x] Falta el valor de --bot-token"; exit 1; }
            BOT_TOKEN_ARG="$1"
            ;;
        --no-bot)
            ASK_BOT=0
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[x] Opción desconocida: $1"
            usage
            exit 1
            ;;
    esac
    shift
done

command -v docker >/dev/null 2>&1 || {
    echo "[x] Docker no está instalado. Ejecuta primero: bash servicios/instalar_ubuntu.sh"
    exit 1
}
docker compose version >/dev/null 2>&1 || {
    echo "[x] Falta el comando 'docker compose' (plugin de Docker)."
    exit 1
}
[ -d "$DL" ] || {
    echo "[x] No encuentro $DL"
    exit 1
}

mkdir -p "$DL/config" "$DL/sessions"
cd "$DL"

if ! docker image inspect downloader_telegram-telegram >/dev/null 2>&1 \
   || ! docker image inspect downloader_telegram-uploader >/dev/null 2>&1; then
    echo "[i] Construyendo imágenes de Telegram (solo la primera vez)..."
    docker compose build telegram uploader
fi

if [ ! -f config/config.bin ] || [ ! -f config/secret.key ]; then
    echo
    echo "[i] No hay config.bin/secret.key: los genero ahora."
    echo "    Sácalos de https://my.telegram.org/apps (con la cuenta de este equipo)."
    read -rp "API ID: " API_ID
    read -rsp "API HASH: " API_HASH
    echo
    [ -n "$API_ID" ] && [ -n "$API_HASH" ] || {
        echo "[x] API ID y API HASH son obligatorios."
        exit 1
    }
    docker compose run --rm -T -e API_ID -e API_HASH telegram python -c '
import json, os
from pathlib import Path
from cryptography.fernet import Fernet
d = Path("config")
d.mkdir(exist_ok=True)
k = d / "secret.key"
key = k.read_bytes() if k.exists() else Fernet.generate_key()
if not k.exists():
    k.write_bytes(key)
data = json.dumps({"api_id": os.environ["API_ID"], "api_hash": os.environ["API_HASH"]}).encode()
(d / "config.bin").write_bytes(Fernet(key).encrypt(data))
print("OK: config/config.bin + config/secret.key")
'
else
    echo "[i] config.bin y secret.key ya existen: se reutilizan."
fi

if [ "$ASK_BOT" -eq 1 ]; then
    TOKEN="$BOT_TOKEN_ARG"
    if [ -z "$TOKEN" ] && grep -q '^BOT_TOKEN=..*' .env 2>/dev/null; then
        echo "[i] .env ya tiene BOT_TOKEN: se conserva."
    elif [ -z "$TOKEN" ]; then
        echo
        echo "[i] Token del bot: créalo en Telegram con @BotFather -> /newbot"
        read -rsp "Pega BOT_TOKEN (vacío = omitir): " TOKEN
        echo
    fi
    if [ -n "$TOKEN" ]; then
        touch .env
        if grep -q '^BOT_TOKEN=' .env; then
            sed -i "s|^BOT_TOKEN=.*|BOT_TOKEN=$TOKEN|" .env
        else
            printf '\nBOT_TOKEN=%s\n' "$TOKEN" >> .env
        fi
        echo "[ok] BOT_TOKEN guardado en downloader_telegram/.env"
    fi
fi

if [ "$RESET" -eq 1 ]; then
    rm -f sessions/uploader.session
    echo "[i] Sesión anterior borrada: sessions/uploader.session"
fi
touch sessions/uploader.session

echo
echo "[i] Login del uploader. Cuando lo pida, escribe el teléfono (ej. +34...) y"
echo "    el código que llegue a tu Telegram. Si tienes 2FA, pide también la clave."
echo
docker compose run --rm uploader python -u /app/app/subir_videos.py --setup

echo
echo "[i] Comprobando credenciales y sesión..."
docker compose run --rm uploader python -u /app/app/subir_videos.py --verificar || true

echo
echo "[ok] Listo en esta máquina:"
echo "     - downloader_telegram/config/config.bin"
echo "     - downloader_telegram/config/secret.key"
echo "     - downloader_telegram/sessions/uploader.session"
echo "     - downloader_telegram/.env (si configuraste BOT_TOKEN)"
echo
echo "[i] Siguiente paso: arranca el pipeline con  pipe_up"
