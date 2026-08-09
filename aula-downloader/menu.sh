#!/bin/bash

# AULA Downloader - Menú principal
# Colores: Verde y Azul (consistente con otros proyectos devjobs)

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
echo -e "${GREEN}Selecciona una opción:${NC}"
echo ""
echo -e "  ${GREEN}1)${NC} Descargar vídeos de una carpeta"
echo -e "  ${GREEN}2)${NC} Ver ayuda"
echo -e "  ${GREEN}3)${NC} Salir"
echo ""
read -p "Opción: " opcion

case $opcion in
    1)
        echo ""
        echo -e "${BLUE}ℹ${NC} Iniciando descargador..."
        python3 /app/aula_downloader_funciona.py
        ;;
    2)
        echo ""
        echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${BLUE}║${GREEN}                    📖 AYUDA                                 ${BLUE}║${NC}"
        echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "  ${GREEN}Uso:${NC}"
        echo -e "    1. Ejecuta el contenedor"
        echo -e "    2. Introduce tu usuario y contraseña de aula"
        echo -e "    3. Introduce la URL de la carpeta con los vídeos"
        echo -e "    4. El script descargará automáticamente los vídeos"
        echo ""
        echo -e "  ${GREEN}Ejemplo de URL:${NC}"
        echo -e "    https://aula.pmoposiciones.com/mod/folder/view.php?id=4189"
        echo ""
        echo -e "  ${GREEN}Notas:${NC}"
        echo -e "    - Los vídeos se guardan en ./descargas/"
        echo -e "    - Se necesita ffmpeg para la descarga"
        echo -e "    - Los vídeos son DASH/HLS (no MP4 directo)"
        echo ""
        read -p "Presiona Enter para continuar..."
        menu
        ;;
    3)
        echo ""
        echo -e "${GREEN}👋 ¡Hasta luego!${NC}"
        exit 0
        ;;
    *)
        echo ""
        echo -e "${BLUE}✗${NC} Opción no válida"
        sleep 2
        menu
        ;;
esac
