FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev ffmpeg tesseract-ocr tesseract-ocr-spa && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    telethon \
    mtranslate \
    cryptography \
    cryptg \
    rich \
    inquirerpy \
    Pillow \
    imagehash && \
    pip install 'urllib3<2.8' --break-system-packages

COPY app/ /app/app/
COPY tg_toolbox/ /app/tg_toolbox/
COPY config/ /app/config/
RUN mkdir -p /app/sessions

CMD ["sh", "-c", "cd /app && exec python -u -m tg_toolbox.tg_toolbox"]
