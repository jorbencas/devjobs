#!/usr/bin/env python3
"""
pipeline.py — Orquestador principal del pipeline YouTube → Telegram.
Ejecuta: download → convert → upload en orden.
"""
import sys
import logging
from pathlib import Path

# Añadir directorio de scripts al path
sys.path.insert(0, str(Path(__file__).parent))

from download import main as download_main
from convert import main as convert_main
from upload import main as upload_main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("pipeline")

def run_pipeline():
    """Ejecuta el pipeline completo."""
    logger.info("🚀 Iniciando pipeline YouTube → Telegram")
    
    # Paso 1: Descargar
    logger.info("\n" + "="*50)
    logger.info("📥 PASO 1: Descargando vídeos")
    logger.info("="*50)
    downloaded = download_main()
    
    # Paso 2: Convertir
    logger.info("\n" + "="*50)
    logger.info("🔄 PASO 2: Convirtiendo vídeos")
    logger.info("="*50)
    converted = convert_main()
    
    # Paso 3: Subir
    logger.info("\n" + "="*50)
    logger.info("⬆️  PASO 3: Subiendo a Telegram")
    logger.info("="*50)
    upload_main()
    
    logger.info("\n" + "="*50)
    logger.info("✅ Pipeline completado")
    logger.info("="*50)

if __name__ == "__main__":
    run_pipeline()
