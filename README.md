<div align="center">

# 🥷 devjobs

**Ultimate Automation Suite**

![Python](https://img.shields.io/badge/python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![License](https://img.shields.io/github/license/jorbencas/devjobs?style=for-the-badge)
![Repo size](https://img.shields.io/github/repo-size/jorbencas/devjobs?style=for-the-badge&label=Repo%20size)

[![Scraper](https://img.shields.io/badge/Pipeline-Twitch%20→%20Telegram-9146FF?style=flat-square&logo=twitch&logoColor=white)](#pipeline-directos-de-twitch--telegram)
[![YouTube](https://img.shields.io/badge/Pipeline-YouTube%20→%20Telegram-FF0000?style=flat-square&logo=youtube&logoColor=white)](#pipeline-youtube--telegram)
[![Blog](https://img.shields.io/badge/Blog-jorbencas-orange?style=flat-square&logo=vercel&logoColor=white)](https://blog-jorbencas.vercel.app)

Suite auto-hospedada de **automatización con Docker**: grabación de directos, conversión de vídeo, subida a Telegram, descarga de cursos y gestión de PDFs — listas para desplegar y olvidar.

**[📖 Blog: Devjobs Suite](https://blog-jorbencas.vercel.app/proyectos/devjobs-automation-suite)** · **[🔧 Instalación](https://blog-jorbencas.vercel.app/posts/instalacion-devjobs)** · **[💬 docker_help.txt](docker_help.txt)**

</div>

---

## 📋 Overview

> **[📖 Leer más en el blog](https://blog-jorbencas.vercel.app/proyectos/devjobs-automation-suite)** — Explicación detallada de la arquitectura y decisiones de diseño.

| Pipeline | Descripción | Frecuencia | Blog |
|----------|-------------|------------|------|
| 🎬 **Twitch → Telegram** | Grabar → comprimir 720p → subir a Telegram | Automático 24/7 | [📖](https://blog-jorbencas.vercel.app/proyectos/devjobs-automation-suite) |
| 📺 **YouTube → Telegram** | Descargar canales → convertir → subir con topics | Cron 01:00→18:00 | [📖](https://blog-jorbencas.vercel.app/proyectos/devjobs-automation-suite) |
| 🤖 **Bot Telegram** | Descargas por URL + contenido IA (tips, tools) | En tiempo real | [📖](https://blog-jorbencas.vercel.app/proyectos/telegram-ultimate-toolbox) |
| 📄 **PDF Manager** | Desbloquear, unir, dividir, comprimir PDFs | Bajo demanda | [📖](https://blog-jorbencas.vercel.app/proyectos/pdf-ninja-master) |

---

## 🛠️ Herramientas del Ecosistema

| # | Herramienta | Descripción | Blog | README |
|---|-------------|-------------|------|--------|
| 1 | `TwitchRecorder/` | Grabador automático de directos (Twitch/YouTube/Kick) | [📖](https://blog-jorbencas.vercel.app/proyectos/devjobs-automation-suite) | [README](TwitchRecorder/README.md) |
| 2 | `ffmpeg-yt-dlp/` | Conversor y optimizador de vídeo (33 modos) | [📖](https://blog-jorbencas.vercel.app/proyectos/ffmpeg-yt-dlp) | [README](ffmpeg-yt-dlp/README.md) |
| 3 | `downloader_telegram/` | Descargador masivo + bot API interactivo | [📖](https://blog-jorbencas.vercel.app/proyectos/telegram-ultimate-toolbox) | [README](downloader_telegram/README.md) |
| 4 | `yt-to-telegram/` | Pipeline YouTube → Telegram (160 canales) | [📖](https://blog-jorbencas.vercel.app/proyectos/devjobs-automation-suite) | [README](yt-to-telegram/README.md) |
| 5 | `pdfmanager/` | Gestor de PDFs: desbloquear, unir, dividir | [📖](https://blog-jorbencas.vercel.app/proyectos/pdf-ninja-master) | [README](pdfmanager/README.md) |
| 6 | `hdfull-downloader/` | Descargador de películas HDFull con noVNC | — | [README](hdfull-downloader/README.md) |
| 7 | `aula-downloader/` | Descargador de vídeos Moodle/Vimeo | — | [README](aula-downloader/README.md) |

---

## 🎬 PIPELINE: Directos de Twitch → Telegram

Automatización que graba los directos de **sendosama**, los comprime y los sube a varios grupos de Telegram, **sin intervención**.

```
┌──────────────┐   *_completed.mp4   ┌──────────────────┐   *_compressed.mp4   ┌──────────────────┐
│ TwitchRecorder│ ────────────────► │ ffmpeg-yt-dlp     │ ──────────────────► │ downloader_telegram│
│  (grabar)     │    copiar a test/ │  monitor *720p*    │      a 720p         │  uploader (subir) │
└──────────────┘                    └──────────────────┘                      └──────────────────┘
   data/pipeline/grabaciones/      data/pipeline/comprimidos/                    N grupos
```

### Flujo completo

| Paso | Servicio | Qué hace |
|------|----------|----------|
| 1. **Grabar** | `twitchrecorder-sendo` | Detecta directo, graba calidad original, concatena partes si cambia plataforma |
| 2. **Keyword** | — | Extrae título → `*_KW_<keyword>_completed.mp4` (viaja por todo el pipeline) |
| 3. **Cola** | — | Copia a `test/` (original queda en grabaciones/) |
| 4. **Comprimir** | `ffmpeg_monitor-sendo` | Convierte a 720p, detecta episodios OCR, gestiona sidecars |
| 5. **Subir** | `telegram-uploader-sendo` | Rutea por keyword, sube a temas de Telegram, limpia residuos |

### Contenedores Docker

| Contenedor | Servicio | Qué hace |
|------------|----------|----------|
| `twitchrecorder-sendo` | Grabador | Detecta directos, graba calidad original, concatena partes |
| `ffmpeg_monitor-sendo` | Compresor | Convierte a 720p, detecta episodios por OCR |
| `telegram-uploader-sendo` | Subidor | Rutea por keyword, sube a temas de Telegram |

### Configuración

```json
{
    "channels": {
        "sendosama": {
            "platform": [
                { "platform": "web", "url": "https://watch.sendosama.net/", "detectar": true, "corte": false },
                { "platform": "youtube", "channel": "sendosenpai" },
                { "platform": "twitch", "detectar": true, "corte": false },
                { "platform": "kick", "detectar": true, "corte": false }
            ],
            "start_time": { "Sunday": "19:00", "*": "21:30" },
            "dias_plataforma": {
                "Sunday": ["youtube", "twitch", "web", "kick"],
                "*": ["web", "twitch", "kick"]
            }
        }
    }
}
```

---

## 📺 PIPELINE: YouTube → Telegram

Pipeline independiente que descarga vídeos de **160 canales de YouTube**, los convierte a 720p y los sube a un grupo de Telegram con topics por canal.

| Canal | Topic ID | Estado |
|-------|----------|--------|
| MoureDev | 28 | ✅ Habilitado |
| Midudev | 30 | ✅ Habilitado |
| Carlos Azaustre | 32 | ✅ Habilitado |
| Linkfydev | 45 | ✅ Habilitado |
| Jorexdev | 644 | ✅ Habilitado |
| La Inteligencia Artificial | 645 | ✅ Habilitado |
| *...154 más* | 26-183 | ⏸️ Deshabilitado |

### Gestión rápida (aliases)

```bash
yt_up        # Arrancar pipeline
yt_down      # Parar pipeline
yt_logs      # Ver logs en tiempo real
yt_restart   # Reiniciar pipeline
yt_rebuild   # Rebuild + arrancar
yt_ps        # Ver estado
```

### Cron automático

```bash
# 01:00 → 18:00 (mismo día)
0 1 * * * /home/jorge/dev/devjobs/yt-to-telegram/scripts/run_pipeline_cron.sh
```

---

## 📦 Instalación Rápida

```bash
# Clonar
git clone https://github.com/jorbencas/devjobs.git
cd devjobs

# Instalar aliases
bash servicios/instalar_aliases.sh && source ~/.bashrc

# Pipeline Twitch → Telegram
pipe_up

# Pipeline YouTube → Telegram
yt_up

# Bot Telegram
tg_bot
```

> **[📖 Guía completa de instalación](https://blog-jorbencas.vercel.app/posts/instalacion-devjobs)**

---

## 📋 Cheat Sheet

| Alias | Descripción |
|-------|-------------|
| `pipe_up` | Arrancar pipeline Twitch (3 daemons) |
| `pipe_down` | Parar pipeline Twitch |
| `plogs` | Logs de los 3 daemons |
| `pipe_ps` | Estado de los 3 contenedores |
| `pipe_rebuild` | Rebuild + recrear (cambios en código) |
| `yt_up` | Arrancar pipeline YouTube |
| `yt_down` | Parar pipeline YouTube |
| `yt_logs` | Logs del pipeline YouTube |
| `tg_bot` | Arrancar bot Telegram |
| `tg_bot_logs` | Logs del bot |
| `docker_help` | Ver todos los comandos |

> **[📖 Referencia completa: docker_help.txt](docker_help.txt)**

---

## 📚 Blog Posts

Artículos relacionados en [blog-jorbencas.vercel.app](https://blog-jorbencas.vercel.app):

| Post | Descripción |
|------|-------------|
| [Devjobs Automation Suite](https://blog-jorbencas.vercel.app/proyectos/devjobs-automation-suite) | Arquitectura completa del ecosistema |
| [Instalación de Devjobs](https://blog-jorbencas.vercel.app/posts/instalacion-devjobs) | Guía paso a paso de configuración |
| [FFmpeg + yt-dlp Pipeline](https://blog-jorbencas.vercel.app/proyectos/ffmpeg-yt-dlp) | 33 modos de conversión de vídeo |
| [Telegram Ultimate Toolbox](https://blog-jorbencas.vercel.app/proyectos/telegram-ultimate-toolbox) | Bot, uploader y descargador masivo |
| [PDF Ninja Master](https://blog-jorbencas.vercel.app/proyectos/pdf-ninja-master) | Gestor de PDFs con Docker |
| [Docker: ffmpeg y yt-dlp](https://blog-jorbencas.vercel.app/posts/docker-to-yt-ffmpeg_in-wls) | Guía de instalación en WSL |

---

## 🤝 Contribuir

1. **Fork** el repositorio y crea una rama: `git checkout -b feat/mi-mejora`
2. Haz el cambio en la herramienta correspondiente (mantén su `README.md` al día).
3. Abre un **Pull Request** describiendo qué hace y por qué.
4. Para bugs: abre un *issue* con pasos para reproducirlo.

---

<div align="center">

**Made with ❤️ by [Jorge (@jorbencas)](https://github.com/jorbencas)**

</div>
