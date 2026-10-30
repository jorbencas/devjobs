#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DL="$ROOT/downloader_telegram"
ENV_FILE="$DL/.env"

usage() {
    cat <<'EOF'
Uso: bash servicios/pipe_test.sh [--sin-subida] [--borrar]

Comprueba:
  1) BOT_TOKEN del bot contra la API de Telegram (getMe)
  2) config.bin/secret.key, grupos.json y uploader.session (--verificar)
  3) subida real de un .txt mínimo (1 byte; Telegram rechaza 0 bytes)
     a Mensajes guardados. Por defecto se conserva para comprobarlo.

Opciones:
  --sin-subida   Omite la prueba de subida real
  --borrar       Borra el mensaje de prueba después de subirlo

El token nunca se imprime. Salida 0 = todo OK.
EOF
}

UPLOAD=1
BORRAR=0
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --sin-subida) UPLOAD=0 ;;
        --borrar) BORRAR=1 ;;
        *) echo "[x] Opción desconocida: $1"; usage; exit 1 ;;
    esac
    shift
done

command -v docker >/dev/null 2>&1 || { echo "[x] Docker no está instalado."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "[x] Falta 'docker compose'."; exit 1; }
[ -f "$ENV_FILE" ] || { echo "[x] No existe $ENV_FILE"; exit 1; }

TOKEN="$(grep -E '^BOT_TOKEN=' "$ENV_FILE" | tail -n1 | cut -d= -f2- || true)"
BOT_OK=0
if [ -z "$TOKEN" ]; then
    echo "[x] BOT_TOKEN no definido en $ENV_FILE"
else
    TMP="$(mktemp)"
    CODE="$(curl -sS --max-time 15 -o "$TMP" -w '%{http_code}' \
        "https://api.telegram.org/bot${TOKEN}/getMe" || true)"
    if [ "$CODE" = "200" ] && grep -q '"ok":true' "$TMP"; then
        DESC="$(python3 - "$TMP" <<'PY' 2>/dev/null || echo "OK"
import json, sys
r = json.load(open(sys.argv[1]))["result"]
print("@" + r["username"] + " (" + r["first_name"] + ")")
PY
)"
        echo "[ok] BOT_TOKEN válido: $DESC"
        BOT_OK=1
    else
        echo "[x] BOT_TOKEN NO válido (HTTP ${CODE:-?})"
        BOT_OK=0
    fi
    rm -f "$TMP"
fi

cd "$DL"
SESSION_OK=0
if docker compose run --rm uploader python -u /app/app/subir_videos.py --verificar; then
    SESSION_OK=1
else
    echo "[x] La sesión del uploader NO es válida."
fi

UPLOAD_OK=0
if [ "$UPLOAD" -eq 1 ]; then
    if docker compose run --rm -T -e PIPE_TEST_BORRAR="$BORRAR" uploader python -u - <<'PY'
import asyncio
import io
import json
import os
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet
from telethon import TelegramClient

CONFIG = Path("/app/config/config.bin")
KEY = Path("/app/config/secret.key")
SESION = "/app/sessions/uploader.session"


async def main():
    datos = json.loads(Fernet(KEY.read_bytes()).decrypt(CONFIG.read_bytes()))
    client = TelegramClient(SESION, int(datos["api_id"]), datos["api_hash"])
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("sesión no autorizada")
        me = await client.get_me()
        nombre = f"pipe_test_{datetime.now():%Y%m%d_%H%M%S}.txt"
        print(f"[i] Subiendo {nombre} (1 byte) a Mensajes guardados...", flush=True)
        msg = await client.send_file(
            "me",
            file=io.BytesIO(b"\n"),
            file_name=nombre,
            caption="Test del pipeline",
            force_document=True,
        )
        if os.environ.get("PIPE_TEST_BORRAR") == "1":
            await client.delete_messages("me", [msg.id])
            print(f"[ok] Subida OK en Mensajes guardados de {me.first_name}; mensaje borrado.", flush=True)
        else:
            print(
                f"[ok] Subida OK en Mensajes guardados de {me.first_name}; "
                f"conservado {nombre} (msg {msg.id}) para comprobarlo.",
                flush=True,
            )
    finally:
        await client.disconnect()


try:
    asyncio.run(main())
except Exception as e:
    print(f"[x] Test de subida FALLÓ: {e}", flush=True)
    raise SystemExit(1)
PY
    then
        UPLOAD_OK=1
    else
        echo "[x] La subida de prueba FALLÓ."
    fi
fi

OK=1
[ "$BOT_OK" -eq 1 ] || OK=0
[ "$SESSION_OK" -eq 1 ] || OK=0
if [ "$UPLOAD" -eq 1 ] && [ "$UPLOAD_OK" -ne 1 ]; then
    OK=0
fi

if [ "$OK" -eq 1 ]; then
    if [ "$UPLOAD" -eq 1 ]; then
        echo "[ok] TEST COMPLETO: bot, sesión y subida funcionan."
    else
        echo "[ok] TEST COMPLETO: bot y sesión funcionan (subida omitida)."
    fi
    exit 0
fi

echo "[x] TEST FALLIDO."
exit 1
