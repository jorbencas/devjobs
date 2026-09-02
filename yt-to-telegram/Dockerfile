FROM python:3.12-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instalar deno (necesario para yt-dlp YouTube)
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh && \
    ln -s /usr/local/bin/deno /usr/bin/deno

# Instalar yt-dlp
RUN pip install --no-cache-dir yt-dlp

# Crear directorio de trabajo
WORKDIR /app

# Copiar scripts
COPY scripts/ /app/scripts/
COPY config/ /app/config/

# Comando por defecto
CMD ["python", "/app/scripts/pipeline.py"]
