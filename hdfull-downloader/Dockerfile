FROM alpine:3.24

RUN apk add --no-cache \
    chromium \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    ffmpeg \
    curl \
    openbox \
    xsetroot \
    python3 \
    py3-pip \
    font-dejavu \
    ttf-freefont \
    tzdata \
    xauth \
 && python3 -m venv /venv \
 && /venv/bin/pip install --no-cache-dir drissionpage

WORKDIR /app
