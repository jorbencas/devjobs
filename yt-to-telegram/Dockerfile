FROM python:3.12-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar yt-dlp
RUN pip install --no-cache-dir yt-dlp

# Crear directorio de trabajo
WORKDIR /app

# Copiar scripts
COPY scripts/ /app/scripts/
COPY config/ /app/config/

# Comando por defecto
CMD ["python", "/app/scripts/pipeline.py"]
