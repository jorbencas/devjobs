#!/bin/bash
# Muestra los contenedores ACTIVOS, separando los del pipeline del resto.
# Pipeline: twitchrecorder-sendo | ffmpeg_monitor-sendo | telegram-uploader-sendo
# Uso:  bash servicios/pipe_ps.sh   (o un alias)
set -euo pipefail

PIPELINE="twitchrecorder-sendo|ffmpeg_monitor-sendo|telegram-uploader-sendo"

if ! docker info >/dev/null 2>&1; then
    echo "[!] El daemon de Docker no está corriendo."
    exit 1
fi

# Línea completa por contenedor (independiente del nombre/estado)
linea() {
    local nom estado up
    nom="$1"
    estado=$(docker inspect --format '{{.State.Status}}' "$nom")
    up=$(docker inspect --format "{{.State.Running}}" "$nom")
    if [ "$up" = "true" ]; then
        up="Up $(docker inspect --format '{{.RestartCount}}' "$nom") restarts"
    else
        up="parado"
    fi
    printf "%-20s %-9s %s\n" "/$nom" "$estado" "$up"
}

echo "================ PIPELINE (grabar -> comprimir -> subir) ================"
printf "%-20s %-9s %s\n" "NOMBRE" "ESTADO" "INFO"
for c in twitchrecorder-sendo ffmpeg_monitor-sendo telegram-uploader-sendo; do
    if docker ps -a --filter "name=^/${c}$" --format '{{.Names}}' | grep -q .; then
        linea "$c"
    else
        printf "%-20s %-9s %s\n" "$c" "ausente" "-"
    fi
done

echo ""
echo "=========== RESTO DE CONTENEDORES ACTIVOS (no pipeline) ============="
otros=$(docker ps --format '{{.Names}}' | grep -Ev "^($PIPELINE)$" || true)
if [ -z "$otros" ]; then
    echo "  (ninguno)"
else
    printf "%-20s %-9s %s\n" "NOMBRE" "ESTADO" "INFO"
    for c in $otros; do
        linea "$c"
    done
fi

echo ""
cont=$(docker ps -q | wc -l)
echo "Total contenedores activos: $cont"