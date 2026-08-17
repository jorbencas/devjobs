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
    inquirerpy

COPY app/ /app/app/
COPY config/config.bin config/secret.key config/grupos.json config/enviados.json /app/config/
COPY sessions/* /app/sessions/

CMD ["python", "-u", "/app/app/tg_toolbox.py"]
