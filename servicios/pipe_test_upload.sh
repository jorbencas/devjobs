#!/bin/bash
# PRUEBA RÁPIDA: copiar un vídeo como *_compressed.mp4 a /comprimidos
# para que el uploader lo suba (ruteo por keyword o fallback a Jorge videos).
# Uso:  bash servicios/pipe_test_upload.sh [keyword]
#   sin argumento -> prueba el grupo fallback (default)
#   con uno -> prueba el ruteo por keyword (ej. cuid_opcional)
KEY=${1:-prueba_upload}
SRC=${2:-/home/jorge/dev/devjobs/data/grabaciones/test/.placeholder}
DEST=/home/jorge/dev/devjobs/data/comprimidos/sendo_KW_${KEY}_compressed.mp4

# Buscar un mp4 de ejemplo si no se pasó uno explícito
if [ ! -f "$SRC" ]; then
    SRC=$(find /home/jorge/dev/devjobs/data/grabaciones -maxdepth 2 -name "*.mp4" 2>/dev/null | head -1)
fi
if [ -z "$SRC" ]; then
    echo "[!] No hay un .mp4 de ejemplo. Pasa la ruta: bash pipe_test_upload.sh <keyword> <ruta>"
    exit 1
fi

cp "$SRC" "$DEST"
echo "Copiado como: $DEST"
echo "El uploader lo subirá en ~60 s (ruteo por keyword '$KEY' o fallback Jorge videos)."
echo "Para ver la subida: plogs"