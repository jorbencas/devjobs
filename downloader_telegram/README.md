# Telegram Ultimate Toolbox

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Descargador masivo, clonador, vigilante de contenido y **subidor automático de vídeos a grupos** en Telegram.

> Subida automática y pipeline "Grabar → Comprimir → Subir": [ver `README_UPLOADER.md`](README_UPLOADER.md).

## Requisitos

- Docker
- Cuenta de Telegram con API ID/Hash (crear en https://my.telegram.org/apps)

## Despliegue

```bash
git clone https://github.com/jorge-bencas/devjobs.git
cd devjobs/downloader_telegram
cp .env.example .env
# Editar .env con tus credenciales de Telegram
docker compose build
docker compose up
```

### Módulo Uploader (`subir_videos.py`)

Sube vídeos comprimidos a varios grupos de Telegram automáticamente (pieza final del pipeline **"Grabar → Comprimir → Subir"**):

```bash
# Setup de sesión (una vez, pide teléfono + código, crea uploader.session)
docker compose run --rm uploader python /app/subir_videos.py --setup

# Descubrir los IDs de tus chats/grupos
docker compose run --rm uploader python /app/subir_videos.py --list-chats

# Modo automático en background (vigila /comprimidos y sube a los grupos)
docker compose up -d uploader
docker compose logs -f uploader
```

El detalle completo (configuración con variables de entorno, `grupos.json`, división de vídeos >2 GB, sesión propia que no conflictúa): [ver `README_UPLOADER.md`](README_UPLOADER.md).

### Generar sesión portátil

```bash
docker compose run --rm telegram python test_string.py
```

### Sin Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install telethon mtranslate cryptography cryptg rich inquirerpy
python test_download_protected_content_telegram.py
```

## Uso

### Menú principal

```
1. Descargas Masivas (Enlace/Rango/TXT)
2. Clonación & Backup (Filtro + Traducción)
3. Modo Vigilante (Alertas por palabras)
4. Uploader a grupos (subir_videos.py, ver README_UPLOADER.md)
5. Re-configurar / Salir
```

## Estructura

```
downloader_telegram/
├── test_download_protected_content_telegram.py  # script principal (3 módulos)
├── subir_videos.py                              # uploader automático a grupos (pipeline)
├── test_string.py                               # generador de sesiones
├── grupos.json                                  # IDs/@usuario de los grupos (uploader)
├── enviados.json                                # registro de vídeos ya subidos (uploader)
├── Dockerfile                                   # imagen Python + dependencias + ffmpeg
├── docker-compose.yml                           # servicios telegram + uploader
├── .env.example                                 # plantilla de credenciales
├── config.bin                                   # credenciales cifradas (AES)
├── secret.key                                   # llave de cifrado
├── ultimate_session.session                     # sesión de Telegram (menú)
├── uploader.session                             # sesión de Telegram (uploader, separada)
├── Descargas_Telegram/                          # carpeta de descargas
├── README_UPLOADER.md                           # documentación del uploader
├── LICENSE                                      # MIT
└── README.md
```

## Seguridad

- Las credenciales (API ID/Hash) se cifran con AES en `config.bin`
- La llave de cifrado se guarda en `secret.key`
- El archivo `.session` contiene el token de persistencia
- **Nunca commitees** `config.bin`, `secret.key`, `.session` ni `.env`

## Dependencias

Se instalan automáticamente en la imagen Docker:

- `Telethon` — Cliente de Telegram para Python
- `cryptography` (Fernet) — Cifrado AES de credenciales
- `mtranslate` — Traducción automática
- `cryptg` — Aceleración de descargas
- `ffmpeg` — División de vídeos >2 GB en el uploader

## Blog

- [Telegram Ultimate Toolbox: Descargador Masivo, Clonador, Vigilante y Uploader](https://blog-jorbencas.vercel.app/proyectos/telegram-ultimate-toolbox/)
