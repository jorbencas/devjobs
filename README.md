# 🥷 devjobs: Ultimate Automation Suite

Repositorio de herramientas avanzadas para la gestión de activos digitales, automatización de Telegram y procesamiento de documentos legales.

---

## 🛠️ Herramientas del Ecosistema

| # | Herramienta | Descripción | Docker | README |
|---|-------------|-------------|--------|--------|
| 1 | `pdfmanager/` | Gestor de PDFs: desbloquear, unir, dividir, comprimir | ✅ | [README](pdfmanager/README.md) |
| 2 | `downloader_telegram/` | Descargador masivo, clonador y vigilante de Telegram | ✅ | [README](downloader_telegram/README.md) |
| 3 | `hdfull-downloader/` | Descargador de películas HDFull con Docker + noVNC | ✅ | [README](hdfull-downloader/README.md) |
| 4 | `TwitchRecorder/` | Grabador automático de directos de Twitch/YouTube/Kick | ✅ | [README](TwitchRecorder/README.md) |
| 5 | `ffmpeg-yt-dlp/` | Conversor y optimizador de vídeo con ffmpeg + yt-dlp | ✅ | [README](ffmpeg-yt-dlp/README.md) |

---

## 📦 Instalación Rápida (Docker)

Cada herramienta es independiente. Entra en su carpeta y ejecuta:

```bash
# PDFs
cd pdfmanager && docker compose up

# Telegram
cd downloader_telegram && docker compose up

# HDFull (requiere .env con credenciales)
cd hdfull-downloader && ./menu.sh

# Twitch Recorder
cd TwitchRecorder && docker compose up -d

# FFmpeg + yt-dlp
cd ffmpeg-yt-dlp && docker compose build && docker compose up
```

## 📋 Cheat Sheet

```bash
docker_help   # Muestra todos los comandos Docker y de cada proyecto
```
