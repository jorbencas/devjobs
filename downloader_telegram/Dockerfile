FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    telethon \
    mtranslate \
    cryptography \
    cryptg \
    rich \
    inquirerpy

COPY test_download_protected_content_telegram.py .
COPY test_string.py .
COPY subir_videos.py .

CMD ["python", "-u", "test_download_protected_content_telegram.py"]
