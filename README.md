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
| 6 | `aula-downloader/` | Descargador de vídeos de aula Moodle/Vimeo con Python puro | ✅ | [README](aula-downloader/README.md) |

---

## 🎬 PIPELINE: Directos de Twitch → Telegram

Automatización que graba los directos de **sendo sama**, los comprime y los sube a varios grupos de Telegram, **sin intervención** (ideal para ausencias). Encadena 3 proyectos existentes:

```
┌──────────────┐   *_completed.mp4   ┌──────────────────┐   *_compressed.mp4   ┌──────────────────┐
│ TwitchRecorder│ ────────────────► │ ffmpeg-yt-dlp     │ ──────────────────► │ downloader_telegram│
│  (grabar)     │    mover a test/  │  monitor *720p*    │      a 720p         │  uploader (subir) │
└──────────────┘                    └──────────────────┘                      └──────────────────┘
   /home/jorge/dev/devjobs/data/grabaciones/test/  /home/jorge/dev/devjobs/data/comprimidos/  N grupos
```

| Pieza | Proyecto | Servicio | Qué hace |
|---|---|---|---|
| 1. Grabar | `TwitchRecorder/` | `twitchrecorder` | Graba el directo, lee su título (keyword) y lo mueve a `test/` como `*_KW_<keyword>_completed.mp4` |
| 2. Comprimir | `ffmpeg-yt-dlp/` | `monitor` | Convierte a **720p** → `comprimidos/*_KW_<keyword>_compressed.mp4` (conserva el nombre) |
| 3. Subir | `downloader_telegram/` | `uploader` | Rutea por keyword: sube al grupo cuyo nombre coincida, si no al `default` (`grupos.json`) |

### Arrancar el pipeline

```bash
cd TwitchRecorder && docker compose up -d twitchrecorder
cd ../ffmpeg-yt-dlp && docker compose up -d monitor
cd ../downloader_telegram && docker compose up -d uploader
```

> **Aliases para controlarlo:** `bash servicios/instalar_aliases.sh && source ~/.bashrc`
> instala dos bloques idempotentes: el del pipeline (`plogs`, `pipe_up/down/ps`,
> `pipe_recreate/rebuild`, etc.) y uno **por-proyecto**. Regla: `pipe_*` =
> los 3 daemons del pipeline a la vez; `*_logs`/`*_stop`/`*_restart` = daemon
> individual (p. ej. `ff_logs` para el `ffmpeg_monitor`, `ff_stop` para pararlo);
> `*_manual_*` = la versión para probar a mano. La lista completa está en
> `docker_help.txt` (sección 3 y 4).

### Preparación inicial (solo la primera vez, ANTES de dejarlo solo)

```bash
# 1. Sesión del uploader (una sola vez, pide teléfono + código)
cd downloader_telegram && docker compose run --rm uploader python /app/subir_videos.py --setup

# 2. Descubrir los IDs de tus grupos
docker compose run --rm uploader python /app/subir_videos.py --list-chats [--folder <carpeta>] [--creados]

# 3. Rellenar grupos.json con 'default' + [{nombre, id}] (ruteo por keyword)
```

### Documentación detallada

- **Monitoreo de compresión:** [`ffmpeg-yt-dlp/README_MONITOR.md`](ffmpeg-yt-dlp/README_MONITOR.md)
- **Subida a Telegram:** [`downloader_telegram/README_UPLOADER.md`](downloader_telegram/README_UPLOADER.md)
- **Grabación `_completed`:** [`TwitchRecorder/README.md`](TwitchRecorder/README.md)
- **Comandos Docker y systemd:** [`docker_help.txt`](docker_help.txt)
- **Servicio systemd (auto-arranque al boot):** [`servicios/twitch-stream-pipeline.service`](servicios/twitch-stream-pipeline.service)

### Arranque del pipeline (AUTO al boot)

Los 3 servicios se levantan solos al encender el PC (systemd habilitado).
También puedes arrancarlos a mano con `pipe_up` (o vía systemd con `pipe_sys_start`).
Para quitar el auto-arranque:
`sudo systemctl disable twitch-stream-pipeline.service`
Ver la sección *PIPELINE VÍA SYSTEMD* en `docker_help.txt`.

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

# AULA Downloader
cd aula-downloader && docker compose build && docker compose run --rm aula_downloader
```

## 📋 Cheat Sheet

```bash
docker_help   # Muestra todos los comandos Docker y de cada proyecto
# Pipeline completo de una vez: pipe_up (parar: pipe_down)
# Logs en directo por proyecto/instancia:
#   ff_logs (monitor)  ff_manual_logs (midu)  tw_logs  tg_logs  pdf_logs
# Logs de los 3 daemons del pipeline de una vez (con color): plogs
# Estado de los contenedores: pipe_ps (pipeline) | docker ps
```

## 📝 Blog

Artículos técnicos en [blog-jorbencas.vercel.app](https://blog-jorbencas.vercel.app):

| Proyecto | Artículo |
|----------|----------|
| `ffmpeg-yt-dlp/` | [FFmpeg + yt-dlp Pipeline: 27 Modos](https://blog-jorbencas.vercel.app/proyectos/ffmpeg-yt-dlp/) |
| `ffmpeg-yt-dlp/` | [Guía de comandos de yt-dlp y ffmpeg](https://blog-jorbencas.vercel.app/posts/guia_ffmpeg_y_ÿt_dlp/) |
| `ffmpeg-yt-dlp/` | [Docker: ffmpeg y yt-dlp en WSL](https://blog-jorbencas.vercel.app/posts/docker-to-yt-ffmpeg_in-wls/) |
| `downloader_telegram/` | [Telegram Ultimate Toolbox](https://blog-jorbencas.vercel.app/proyectos/telegram-ultimate-toolbox/) |
| `pdfmanager/` | [PDF Ninja Master](https://blog-jorbencas.vercel.app/proyectos/pdf-ninja-master/) |
