#!/bin/bash

# AULA Downloader - Script de inicio
# Uso: sh start.sh [URL1] [URL2] ...

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

clear

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${GREEN}              📚 AULA DOWNLOADER                             ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         Descarga vídeos de aula.pmoposiciones.com           ${BLUE}║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# If URLs are passed as arguments, use them
if [ $# -gt 0 ]; then
    echo -e "${GREEN}Descargando de $# URLs...${NC}"
    python3 /app/aula_downloader_funciona.py "$@"
else
    # Interactive mode
    echo -e "${GREEN}Selecciona una opción:${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} Descargar de una carpeta"
    echo -e "  ${GREEN}2)${NC} Descargar de URLs predefinidas"
    echo -e "  ${GREEN}3)${NC} Salir"
    echo ""
    read -p "Opción: " opcion

    case $opcion in
        1)
            python3 /app/aula_downloader_funciona.py
            ;;
        2)
            python3 /app/aula_downloader_funciona.py \
                "https://aula.pmoposiciones.com/mod/folder/view.php?id=4189" \
                "https://aula.pmoposiciones.com/mod/folder/view.php?id=4184" \
                "https://aula.pmoposiciones.com/mod/folder/view.php?id=4194" \
                "https://aula.pmoposiciones.com/mod/folder/view.php?id=4127"
            ;;
        3)
            echo -e "${GREEN}👋 ¡Hasta luego!${NC}"
            exit 0
            ;;
        *)
            echo -e "${BLUE}✗${NC} Opción no válida"
            ;;
    esac
fi
