#!/bin/bash
# Logs del pipeline completo con color por contenedor:
#   twitchrecorder-sendo    -> azul
#   ffmpeg_monitor-sendo    -> amarillo
#   telegram-uploader-sendo -> rojo
# Uso:  bash servicios/pipeline_logs.sh
# Nota: --tail 50 para que al arrancar ya muestre las últimas líneas de cada
# contenedor, y luego -f lo deja en directo. Los colores van por variable de
# entorno para evitar problemas de escape al copiar/pegar.

B=$'\033[34m'   # azul
G=$'\033[33m'   # amarillo
R=$'\033[31m'   # rojo
RST=$'\033[0m'

for c in twitchrecorder-sendo ffmpeg_monitor-sendo telegram-uploader-sendo; do
    case "$c" in
        twitchrecorder-sendo)     COL="$B" ;;
        ffmpeg_monitor-sendo)     COL="$G" ;;
        telegram-uploader-sendo)  COL="$R" ;;
    esac
    docker logs -f --tail 50 "$c" 2>&1 \
      | sed -u "s#^#${COL}[${c}]${RST} #" &
done

trap 'kill 0' INT
wait