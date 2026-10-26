#!/bin/sh
# Arranca el escritorio virtual, VNC/noVNC y el descargador de hdfull.

CLEAR_PROFILE=false
URL=""

# Procesar argumentos
for arg in "$@"; do
  case "$arg" in
    --clear-profile) CLEAR_PROFILE=true ;;
    *) URL="$arg" ;;
  esac
done

# Borrar perfil si se pide
if [ "$CLEAR_PROFILE" = true ]; then
    echo "Borrando perfil del navegador..."
    rm -rf /profile/*
    echo "Perfil borrado. Se creará uno nuevo."
fi

pkill -f "remote-debugging-port=9312" 2>/dev/null || true
pkill -f "user-data-dir=/profile" 2>/dev/null || true
rm -f /profile/SingletonLock /profile/SingletonSocket /profile/SingletonCookie || true

Xvfb :99 -screen 0 1400x900x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
sleep 2

export DISPLAY=:99
export XAUTHORITY=/dev/null
xhost + 2>/dev/null || true
xhost +local:root 2>/dev/null || true
xsetroot -solid darkgray 2>/dev/null || true
openbox &
sleep 4

x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -noxdamage -quiet >/tmp/x11vnc.log 2>&1 &
sleep 1

websockify --web=/usr/share/novnc 6080 localhost:5900 &
sleep 1

echo "======================================================"
echo "  noVNC:  http://localhost:6080/vnc.html"
echo "  VNC:    localhost:5900"
echo "======================================================"

export DISPLAY=:99
# Fallback a variable de entorno si no hay argumento positional
if [ -z "$URL" ] && [ -n "$HDFULL_URL" ]; then
    URL="$HDFULL_URL"
fi
echo "URL: $URL"
if [ "$CLEAR_PROFILE" = true ]; then
    echo ">>> Perfil borrado <<<"
fi
if [ -n "$URL" ]; then
    /venv/bin/python /app/hdfull_downloader.py "$URL"
else
    echo "ERROR: No se ha proporcionado URL"
    /venv/bin/python /app/hdfull_downloader.py
fi
echo "=== descargador terminado ==="
