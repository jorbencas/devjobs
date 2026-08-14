#!/bin/bash
# Logs del pipeline completo con color por contenedor:
#   twitchrecorder    -> azul
#   ffmpeg_monitor    -> amarillo
#   telegram-uploader -> rojo
# Uso:  bash servicios/pipeline_logs.sh
# Nota: --tail 50 para que al arrancar ya muestre las últimas líneas de cada
# contenedor, y luego -f lo deja en directo. Los colores van por variable de
# entorno para evitar problemas de escape al copiar/pegar.

B=$'\033[34m'   # azul
G=$'\033[33m'   # amarillo
R=$'\033[31m'   # rojo
RST=$'\033[0m'

for c in twitchrecorder ffmpeg_monitor telegram-uploader; do
    case "$c" in
        twitchrecorder)     COL="$B" ;;
        ffmpeg_monitor)     COL="$G" ;;
        telegram-uploader)  COL="$R" ;;
    esac
    docker logs -f --tail 50 "$c" 2>&1 \
      | sed -u "s#^#${COL}[${c}]${RST} #" &
done

trap 'kill 0' INT
wait