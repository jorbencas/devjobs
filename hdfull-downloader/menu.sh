#!/usr/bin/env bash
# HDFull Downloader - menú interactivo
# Ejecuta:  ./menu.sh

set -u
cd "$(dirname "$0")" || exit 1

DEFAULT_URL="https://hdfull.sbs/pelicula/the-king-of-kings"
LOGDIR="logs"
LOGFILE="$LOGDIR/ultimo_run.log"
NAME_PATTERN="hdfull-downloader-downloader-run-"
NOVNC_URL="http://localhost:6080/vnc.html"

mkdir -p "$LOGDIR"

trap 'echo; echo "Menú terminado."; exit 0' INT TERM

banner() {
  clear
  echo "======================================================"
  echo "        HDFULL DOWNLOADER - MENÚ INTERACTIVO"
  echo "======================================================"
  echo "  noVNC: $NOVNC_URL"
  echo "======================================================"
  echo
}

check_env() {
  if [ ! -f .env ]; then
    echo "!! Falta el archivo .env (HDFULL_USER / HDFULL_PASS)"
    echo "   Crea el .env antes de continuar."
    echo
  elif ! grep -q "^HDFULL_USER=." .env 2>/dev/null || ! grep -q "^HDFULL_PASS=." .env 2>/dev/null; then
    echo "!! El .env no tiene HDFULL_USER/HDFULL_PASS rellenos."
    echo
  fi
}

build_if_needed() {
  if ! docker image inspect hdfull-downloader:latest >/dev/null 2>&1; then
    echo "Imagen no encontrada. Construyendo (puede tardar)..."
    docker compose build || { echo "ERROR construyendo la imagen"; return 1; }
  fi
}

cleanup_leftovers() {
  local ids
  ids=$(docker ps -aq --filter "name=$NAME_PATTERN")
  if [ -n "$ids" ]; then
    echo "Limpiando contenedores residuales de ejecuciones anteriores..."
    docker rm -f $ids >/dev/null 2>&1
  fi
}

ask_url() {
  echo "URL de la película (vacío = por defecto):"
  read -r -p "> " MENU_URL
  MENU_URL="${MENU_URL:-$DEFAULT_URL}"
  echo "Usando: $MENU_URL"
}

run_foreground() {
  local url="$1"
  build_if_needed || return 1
  cleanup_leftovers
  echo
  echo "Descargando en PRIMER PLANO. Para resolver el captcha abre:"
  echo "  $NOVNC_URL"
  echo "Ctrl+C interrumpe la descarga y vuelve al menú."
  echo "------------------------------------------------------"
  docker compose run --rm --service-ports -e HDFULL_URL="$url" downloader | tee "$LOGFILE"
  echo "------------------------------------------------------"
  echo "Descarga finalizada. MP4 en downloads/  (logs en $LOGFILE)"
}

status() {
  echo "--- Contenedores de descargas ---"
  docker ps -a --filter "name=$NAME_PATTERN" --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}" | head -10
  echo
  echo "--- Último run ($LOGFILE) ---"
  if [ -f "$LOGFILE" ]; then
    tail -n 15 "$LOGFILE"
  else
    echo "(sin logs)"
  fi
  echo
  read -r -p "Pulsa ENTER para volver al menú..."
}

open_novnc() {
  if command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c start "$NOVNC_URL" >/dev/null 2>&1 \
      && echo "Abierto: $NOVNC_URL" \
      || echo "Abre en el navegador: $NOVNC_URL"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$NOVNC_URL" >/dev/null 2>&1 &
    echo "Abierto: $NOVNC_URL"
  else
    echo "Abre en el navegador: $NOVNC_URL"
  fi
}

while true; do
  banner
  check_env
  echo " 1) Descargar película (logs en directo)"
  echo " 2) Estado / últimos logs"
  echo " 3) Abrir noVNC (resolver captcha)"
  echo " 0) Salir"
  echo
  if ! read -r -p "Opción: " op; then
    echo
    echo "Entrada cerrada."
    exit 0
  fi
  case "$op" in
    1) ask_url; run_foreground "$MENU_URL"; read -r -p "Pulsa ENTER para volver al menú...";;
    2) status;;
    3) open_novnc; read -r -p "Pulsa ENTER para volver al menú...";;
    0) echo "Adiós."; exit 0;;
    *) echo "Opción no válida."; sleep 1;;
  esac
done
