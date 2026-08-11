# Telegram Ultimate Toolbox

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Descargador masivo, clonador y vigilante de contenido en Telegram.

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
4. Re-configurar / Salir
```

## Estructura

```
downloader_telegram/
├── test_download_protected_content_telegram.py  # script principal
├── test_string.py                               # generador de sesiones
├── Dockerfile                                   # imagen Python + dependencias
├── docker-compose.yml                           # servicio con volúmenes
├── .env.example                                 # plantilla de credenciales
├── config.bin                                   # credenciales cifradas (AES)
├── secret.key                                   # llave de cifrado
├── ultimate_session.session                     # sesión de Telegram
├── Descargas_Telegram/                          # carpeta de descargas
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

## Blog

- [Telegram Ultimate Toolbox: Descargador Masivo y Vigilante](https://blog-jorbencas.vercel.app/proyectos/telegram-ultimate-toolbox/)
