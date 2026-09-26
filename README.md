<div align="center">

# 🥷 devjobs

**Ultimate Automation Suite**

![Python](https://img.shields.io/badge/python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![License](https://img.shields.io/github/license/jorbencas/devjobs?style=for-the-badge)
![Repo size](https://img.shields.io/github/repo-size/jorbencas/devjobs?style=for-the-badge&label=Repo%20size)

[![Scraper](https://img.shields.io/badge/Pipeline-Twitch%20→%20Telegram-9146FF?style=flat-square&logo=twitch&logoColor=white)](#pipeline-directos-de-twitch--telegram)
[![YouTube](https://img.shields.io/badge/Pipeline-YouTube%20→%20Telegram-FF0000?style=flat-square&logo=youtube&logoColor=white)](#pipeline-youtube--telegram)
[![Bot](https://img.shields.io/badge/Bot-Telegram%20AI-0088CC?style=flat-square&logo=telegram&logoColor=white)](#-bot-telegram)
[![Project Gen](https://img.shields.io/badge/Project%20Generator-AI-8B5CF6?style=flat-square&logo=github-actions&logoColor=white)](#project-generator)
[![Blog](https://img.shields.io/badge/Blog-jorbencas-orange?style=flat-square&logo=vercel&logoColor=white)](https://blog-jorbencas.vercel.app)

Suite auto-hospedada de **automatización con Docker**: grabación de directos, conversión de vídeo, subida a Telegram, descarga de cursos, gestión de PDFs, **generador de proyectos con IA** — listas para desplegar y olvidar.

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
| 2 | `ffmpeg-yt-dlp/` | Conversor y optimizador de vídeo (37 modos) | [📖](https://blog-jorbencas.vercel.app/proyectos/ffmpeg-yt-dlp) | [README](ffmpeg-yt-dlp/README.md) |
| 3 | `downloader_telegram/` | Descargador masivo + bot API interactivo + CLI consolidada | [📖](https://blog-jorbencas.vercel.app/proyectos/telegram-ultimate-toolbox) | [README](downloader_telegram/README.md) |
| 4 | `yt-to-telegram/` | Pipeline YouTube → Telegram (160 canales) | [📖](https://blog-jorbencas.vercel.app/proyectos/devjobs-automation-suite) | [README](yt-to-telegram/README.md) |
| 5 | `pdfmanager/` | Gestor de PDFs: desbloquear, unir, dividir | [📖](https://blog-jorbencas.vercel.app/proyectos/pdf-ninja-master) | [README](pdfmanager/README.md) |
| 5 | `hdfull-downloader/` | Descargador de películas HDFull con noVNC | — | [README](hdfull-downloader/README.md) |
| 6 | `aula-downloader/` | Descargador de vídeos Moodle/Vimeo | — | [README](aula-downloader/README.md) |
| 7 | `scripts/kick_download.py` | Descargador de vídeos Kick.com (API + ffmpeg) | — | [docker_help.txt](docker_help.txt#3i) |
| 8 | `scripts/discord_monitor.py` | Bot Discord: graba streams automáticamente con OBS | — | [docker_help.txt](docker_help.txt#3j) |

---

## 🎬 PIPELINE: Directos → Telegram (Sending Pipeline)

Automatización que graba directos de **Twitch/YouTube/Kick/Web**, los comprime, detecta episodios por OCR y los sube a Telegram **sin intervención**.

```
┌──────────────┐  *_completed.mp4  ┌──────────────────┐  *_compressed.mp4  ┌──────────────────┐
│ TwitchRecorder│ ──────────────► │ ffmpeg-yt-dlp     │ ────────────────► │ downloader_telegram│
│  (grabar)     │  copiar a test/ │  monitor + OCR    │    comprimir      │  uploader (subir) │
└──────────────┘                  └──────────────────┘                    └──────────────────┘
   data/pipeline/grabaciones/    data/pipeline/comprimidos/                  N grupos/temas
```

### Flujo completo

| Paso | Contenedor | Qué hace |
|------|------------|----------|
| 1. **Detectar** | `twitchrecorder-sendo` | Comprueba directos cada 30s en web → YouTube → Kick → Twitch (orden configurable) |
| 2. **Grabar** | `twitchrecorder-sendo` | Graba calidad original con yt-dlp, concatena partes si cambia de plataforma |
| 3. **Keyword** | — | Extrae título del directo → `*_KW_<keyword>_completed.mp4` |
| 4. **Cola** | — | Copia a `test/` (el original queda en `grabaciones/`) |
| 5. **OCR** | `ffmpeg_monitor-sendo` | Detecta episodios/temporada/película por OCR de la franja superior |
| 6. **Comprimir** | `ffmpeg_monitor-sendo` | Convierte a 720p (CRF 28), recorta extremos si `corte: true` |
| 7. **Subir** | `telegram-uploader-sendo` | Rutea por keyword a grupos/temas de Telegram, divide si >2GB |
| 8. **Limpiar** | `telegram-uploader-sendo` | Marca como enviado, borra comprimido y residuos |

### Contenedores Docker

| Contenedor | Servicio | Puerto | Estado |
|------------|----------|--------|--------|
| `twitchrecorder-sendo` | Grabador (daemon) | — | `unless-stopped` |
| `ffmpeg_monitor-sendo` | Compresor + OCR (daemon) | — | `unless-stopped` |
| `telegram-uploader-sendo` | Subidor (daemon) | — | `unless-stopped` |

### Detección de episodios (OCR)

El monitor ejecuta OCR en la franja superior (top 25%) de cada frame cada 90 segundos:

1. **Preprocesamiento**: escala de grises → contraste 2x → sharpen → binarizar
2. **OCR triple**: 3 modos PSM (3, 6, 7) y se queda el con más patrones
3. **Patrones**: `Episodio 5`, `EP. 3`, `S01E02`, `1x02`, `#12`, fuzzy OCR
4. **Filtrado**: descarta outliers con solapamiento significativo (>50% + 3x muestras)
5. **Clasificación**: episodios, temporada, o película (por frecuencia de "película")

### Configuración (schedule por platform)

`TwitchRecorder/config.json` controla todo el comportamiento del grabador. **Novedad:** cada platform tiene su propio `schedule` (días/horas).

```json
{
    "channels": {
        "sendosama": {
            "platform": [
                {
                    "platform": "web",
                    "url": "https://watch.sendosama.net/",
                    "detectar": true,
                    "corte": false,
                    "schedule": [
                        {"days": ["Sunday"], "time": "19:00"},
                        {"days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], "time": "21:30"}
                    ]
                },
                {
                    "platform": "twitch",
                    "detectar": false,
                    "corte": false,
                    "schedule": []
                }
            ]
        }
    },
    "record_path": "/recordings",
    "check_every": 30,
    "max_duration": "24:00:00",
    "retry_interval": 1,
    "copy_to_test": true,
    "test_path": "/recordings/test"
}
```

**Campos globales:**

| Campo | Qué hace | Default |
|-------|----------|---------|
| `record_path` | Ruta de grabaciones crudas | `/recordings` |
| `check_every` | Segundos entre comprobaciones | `30` |
| `max_duration` | Duración máxima (`HH:MM:SS`) | `24:00:00` |
| `retry_interval` | Segundos antes de reconectar | `1` |
| `copy_to_test` | Copiar a `test_path` como `*_completed.mp4` al terminar | `true` |
| `test_path` | Carpeta que vigila el monitor | `/recordings/test` |

**Campos por canal:**

| Campo | Qué hace | Default |
|-------|----------|---------|
| `enabled` | Si `false`, el canal se salta completamente | `true` |
| `platform` | Lista de fuentes en orden de prioridad | Requerido |

**Campos por plataforma:**

| Campo | Qué hace | Default |
|-------|----------|---------|
| `platform` | Tipo: `web`, `youtube`, `twitch`, `kick` | Requerido |
| `url` | URL directa (solo `web`) | — |
| `detectar` | OCR de episodios en el monitor | `true` |
| `corte` | Recortar intro/outro según episodios | `true` |
| `schedule` | **NUEVO:** Días/horas de vigilancia | `[]` = ignorado |

**`schedule` en detalle:** Controla cuándo y qué vigilar por plataforma. Si `schedule: []` → **se ignora** (no se vigila). Formato: `[{"days": ["Monday"], "time": "18:00"}, ...]`.

---

## 📺 PIPELINE: YouTube → Telegram

Pipeline independiente que descarga vídeos de **160 canales de YouTube**, los convierte a 720p y los sube a un grupo de Telegram con topics por canal.

| Canal | Topic ID | Estado |
|-------|----------|--------|
| MoureDev | 28 | ✅ Habilitado |
| Midudev | 30 | ✅ Habilitado |
| Carlos Azaustre | 32 | ✅ Habilitado |
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

## 🤖 Bot Telegram (@jorbencas_bot)

Bot interactivo con **comandos**, **botones inline** y **contenido IA (Gemini)**. Descarga vídeos de cualquier plataforma via yt-dlp.

### Comandos

| Comando | Qué hace | Botones |
|---|---|---|
| `/tip` | Tip de programación (Gemini + DB) | 🔄 Otro tip, 💡 Concepto, 🛠 Tool |
| `/concepto` | Concepto con código de ejemplo | 🔄 Otro, 💡 Tip, 🛠 Tool |
| `/tool` | Herramienta IA (Gemini + DB) | 🔄 Otro, 💡 Tip, 📖 Concepto |
| `/noticias` | Últimas noticias scrapeadas | 📰 Más noticias, 💡 Tip |
| `/descarga URL` | Descarga vídeo de cualquier plataforma | — |

**IA:** Solo **Gemini** (Gemini 2.5-flash por defecto). Sin OPENAI/ANTHROPIC keys.

---

## 💡 Project Generator — movido a `test_githubActions`

El **generador de ideas de proyectos con IA (Gemini)** ya no vive en este repositorio.
Migrado a [`jorbencas/test_githubActions`](https://github.com/jorbencas/test_githubActions/tree/master/project_generator),
donde se ejecuta con su propio cron (cada 4 h) y envía los resultados a un canal de Telegram.

Motivo: solo usa IA + Telegram + scraping de ideas; no tiene ninguna dependencia de los
pipelines de vídeo de este repo. Así `devjobs` queda sin claves de IA ni workflows de Actions.

| | |
|---|---|
| **Ubicación** | `test_githubActions/project_generator/` |
| **Workflow** | `.github/workflows/generate-projects.yml` (cron `0 */4 * * *` + manual) |
| **Secrets** | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_REPORTS_PROYECTOS_CHANNEL_ID`, `GEMINI_API_KEY` |
| **Docs** | [`project_generator/README.md`](https://github.com/jorbencas/test_githubActions/blob/master/project_generator/README.md) · [`SECRETS.md`](https://github.com/jorbencas/test_githubActions/blob/master/project_generator/SECRETS.md) |

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

# CLI Toolbox
tg_menu
```

> **[📖 Guía completa de instalación](https://blog-jorbencas.vercel.app/posts/instalacion-devjobs)**

---

## 📋 Cheat Sheet

| Alias | Descripción |
|-------|-------------|
| `pipe_up` | Arrancar pipeline (3 daemons) |
| `pipe_down` | Parar pipeline |
| `pipe_rebuild` | Rebuild + recrear (cambios en código) |
| `pipe_ps` | Estado de los 3 contenedores |
| `pipe_logs` | Logs de los 3 daemons en tiempo real |
| `pipe_once` | Ejecutar uploader una sola vez (sin bucle) |
| `pipe_setup` | Iniciar sesión del uploader (interactivo) |
| `yt_up` | Arrancar pipeline YouTube |
| `yt_down` | Parar pipeline YouTube |
| `yt_logs` | Logs del pipeline YouTube |
| `tg_bot` | Arrancar bot Telegram |
| `tg_bot_logs` | Logs del bot |
| `docker_help` | Ver todos los comandos |
| `tg_menu` | CLI toolbox interactiva |

### Scripts del pipeline (`servicios/`)

| Script | Qué hace |
|--------|----------|
| `pipe_rebuild.sh` | Rebuild + recreate de los 3 containers |
| `pipe_ps.sh` | Estado de containers (pipeline + resto) |
| `pipe_once.sh` | Uploader una sola pasada |
| `pipe_setup.sh` | Login interactivo del uploader |
| `pipe_logs.sh` | Logs en tiempo real de los 3 daemons |

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
| [Docker: ffmpeg y yt-dlp](https://blog-jorbencas.vercel.app/posts/docker-to-yt-ffmpeg_in-wls) | Guía de instalación en WLS |

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