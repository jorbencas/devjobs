#!/bin/sh
# Arranca el escritorio virtual, VNC/noVNC y el descargador de hdfull.

pkill -f "remote-debugging-port=9312" 2>/dev/null || true
pkill -f "user-data-dir=/profile" 2>/dev/null || true
rm -f /profile/SingletonLock /profile/SingletonSocket /profile/SingletonCookie || true

Xvfb :99 -screen 0 1400x900x24 -nolisten tcp &
sleep 2

export DISPLAY=:99
xsetroot -solid darkgray 2>/dev/null || true
openbox &
sleep 2

x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -quiet &
sleep 1

websockify --web=/usr/share/novnc 6080 localhost:5900 &
sleep 1

echo "======================================================"
echo "  noVNC:  http://localhost:6080/vnc.html"
echo "  VNC:    localhost:5900"
echo "======================================================"

export DISPLAY=:99
/venv/bin/python /app/hdfull_downloader.py "$@"
echo "=== descargador terminado ==="
