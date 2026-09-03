# 🥷 devjobs — Ultimate Automation Suite

<p align="center">
  <strong>Suite auto-hospedada de <u>automatización con Docker</u>: grabación de
  directos, conversión de vídeo, subida a Telegram, descarga de cursos y gestión
  de PDFs — listas para desplegar y olvidar.</strong>
</p>

<p align="center">
  <a href="https://github.com/jorbencas/devjobs/stargazers"><img src="https://img.shields.io/github/stars/jorbencas/devjobs?style=social" alt="Stars"></a>
  <a href="https://github.com/jorbencas/devjobs"><img src="https://img.shields.io/badge/Self--hosted-Docker-blue.svg" alt="Self-hosted: Docker"></a>
  <a href="https://blog-jorbencas.vercel.app"><img src="https://img.shields.io/badge/Blog-jorbencas-orange.svg" alt="Blog"></a>
</p>

> Pipeline completo y monitorizado: **Twitch → ffmpeg → Telegram**, sin intervención.

Repositorio de herramientas avanzadas para la gestión de activos digitales, automatización de Telegram y procesamiento de documentos legales.

---

## 📑 Tabla de contenidos

- [Herramientas del ecosistema](#herramientas-del-ecosistema)
- [Pipeline: directos de Twitch → Telegram](#pipeline-directos-de-twitch--telegram)
- [Instalación rápida (Docker)](#instalación-rápida-docker)
- [Cheat sheet](#cheat-sheet)
- [Blog](#blog)

## 🛠️ Herramientas del Ecosistema

| # | Herramienta | Descripción | Docker | README |
|---|-------------|-------------|--------|--------|
| 1 | `pdfmanager/` | Gestor de PDFs: desbloquear, unir, dividir, comprimir | ✅ | [README](pdfmanager/README.md) |
| 2 | `downloader_telegram/` | Descargador masivo, clonador, vigilante y **bot API interactivo** | ✅ | [README](downloader_telegram/README.md) |
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
   data/pipeline/grabaciones/      data/pipeline/comprimidos/                    N grupos
```

### Flujo completo (paso a paso)

1. **Grabar** — `TwitchRecorder` (`twitchrecorder-sendo`) comprueba si el canal está en
   directo (según `config.json`) y graba con calidad original. Si el canal define
   varias fuentes, coge la primera que esté online. Si cambia de plataforma a
   medio directo (p. ej. Twitch→Kick), concatena las partes en un solo archivo.
2. **Keyword** — lee el **título/descripción** del directo y lo incrusta en el
   nombre: `sendosama_2026-08-13_20-15-00_KW_<keyword>_completed.mp4`. La keyword
   viaja intacta por todo el pipeline.
3. **Cola de espera** (`data/pipeline/grabaciones/test/`): si `copy_to_test: true`, al
   terminar el directo TwitchRecorder **mueve** la grabación a esta carpeta como
   `*_completed.mp4`. Es el punto de entrada del compresor.
   *(Sidecar opcional `*_descripcion.json`: describe la fuente; ver "Configuración
   por fuente" en el README de ffmpeg-yt-dlp.)*
4. **Comprimir** — `ffmpeg-yt-dlp` (`monitor`) vigila esa carpeta cada 30 s,
   detecta los `*_completed.mp4` y los convierte a **720p** (con garantía <2 GB).
   Detecta episodios por OCR (genera `*_episodios.json` con el caption) y deja el
   resultado como `*_compressed.mp4` en `data/pipeline/comprimidos/`, moviendo el original
   a `comprimidos/.processed`.
5. **Subir** — `downloader_telegram` (`uploader`) vigila `data/pipeline/comprimidos/` y
   por cada `*_compressed.mp4` no enviado extrae el **canal** y la **keyword**,
   elige el destino (tema de foro por canal/keyword, o grupo), sube el vídeo con
   su caption, y al terminar **borra todo el residuo** (el `.mp4`, el sidecar
   `*_episodios.json`, el original de `.processed`, los `log_*.txt` y las partes
   si se dividió por >2 GB). Registra lo enviado en `enviados.json`.

Resultado: un directo grabado a las 21:00 aparece ya comprimido y subido a su
tema/serie sin que tengas que hacer nada.

### Carpetas del pipeline

```
data/
├── pipeline/                    ← Pipeline (grabación → compresión → subida)
│   ├── grabaciones/2026/        Grabaciones en bruto por fecha
│   ├── grabaciones/test/        Cola de espera *_completed.mp4
│   ├── comprimidos/             *_compressed.mp4 listos
│   ├── comprimidos/.processed/  Originales ya comprimidos
│   ├── partes/                  Partes divididas (>2GB)
│   └── backups/                 Backups de config del CLI
├── jorbencas_bot/               ← Bot de Telegram
│   ├── .test_githubActions/     Código AI (tips, tools, noticias)
│   └── *.mp4                    Descargas del bot (yt-dlp)
```

| Carpeta | Contenido | Quién escribe / lee |
|---|---|---|
| `data/pipeline/grabaciones/2026/` | Grabaciones en bruto por fecha | `twitchrecorder-sendo` escribe |
| `data/pipeline/grabaciones/test/` | Cola de espera `*_completed.mp4` | `twitchrecorder-sendo` escribe / `monitor` lee |
| `data/pipeline/comprimidos/` | `*_compressed.mp4` listos | `monitor` escribe / `uploader` lee |
| `data/pipeline/comprimidos/.processed/` | Originales ya comprimidos | `monitor` escribe / `uploader` limpia tras subir |
| `data/pipeline/partes/` | Partes divididas (>2GB) | `uploader` lee / `monitor` divide |
| `data/pipeline/backups/` | Backups de config del CLI | `tg_toolbox.py` (export/import) |
| `data/jorbencas_bot/` | Descargas del bot (`/descarga`) | `telegram_bot` escribe |
| `data/jorbencas_bot/.test_githubActions/` | Código AI (tips, tools, noticias) | `telegram_bot` lee |

> **Detalle:** la carpeta `grabaciones/test/` es solo la **bandeja de espera** entre el
> recorder y el compresor (ficamos claros: no es para probar nada, es el punto de
> entrada del monitor). Si TwitchRecorder está parado vacía; al grabar un directo
> se llena temporalmente hasta que el monitor la procesa.

### Las 3 piezas + Bot

| Pieza | Proyecto | Servicio | Qué hace |
|---|---|---|---|
| 1. Grabar | `TwitchRecorder/` | `twitchrecorder-sendo` | Graba el directo, lee su título (keyword) y lo mueve a `test/` como `*_KW_<keyword>_completed.mp4` |
| 2. Comprimir | `ffmpeg-yt-dlp/` | `monitor` | Convierte a **720p** → `pipeline/comprimidos/*_KW_<keyword>_compressed.mp4` (conserva el nombre) |
| 3. Subir | `downloader_telegram/` | `uploader` | Rutea por keyword: sube al grupo cuyo nombre coincida, si no al `default` (`grupos.json`) |
| 🤖 Bot | `downloader_telegram/` | `telegram_bot` | Bot API interactivo: control del pipeline + contenido IA + respuestas por @mención |

### Arrancar el pipeline

```bash
cd TwitchRecorder && docker compose up -d twitchrecorder
cd ../ffmpeg-yt-dlp && docker compose up -d monitor
cd ../downloader_telegram && docker compose up -d uploader

# Bot API interactivo (opcional)
cd ../downloader_telegram && docker compose up -d telegram_bot ollama
```

> **Aliases para controlarlo:** `bash servicios/instalar_aliases.sh && source ~/.bashrc`
> instala dos bloques idempotentes: el del pipeline (`plogs`, `pipe_up/down/ps`,
> `pipe_recreate/rebuild`, etc.) y uno **por-proyecto**. Regla: `pipe_*` =
> los 3 daemons del pipeline a la vez; `*_logs`/`*_stop`/`*_restart` = daemon
> individual (p. ej. `ff_logs` para el `ffmpeg_monitor-sendo`, `ff_stop` para pararlo);
> `*_manual_*` = la versión para probar a mano. La lista completa está en
> `docker_help.txt` (sección 3 y 4).

### Preparación inicial (solo la primera vez, ANTES de dejarlo solo)

```bash
# 1. Sesión del uploader (una sola vez, pide teléfono + código)
cd downloader_telegram && docker compose run --rm uploader python /app/app/subir_videos.py --setup

# 2. Descubrir los IDs de tus grupos
docker compose run --rm uploader python /app/app/subir_videos.py --list-chats [--folder <carpeta>] [--creados]

# 3. Rellenar grupos.json con 'default' + [{nombre, id}] (ruteo por keyword)
```

### Documentación detallada

- **Monitoreo de compresión:** [`ffmpeg-yt-dlp/README.md`](ffmpeg-yt-dlp/README.md) (sección *Monitor de carpeta*)
- **Subida a Telegram:** [`downloader_telegram/README.md`](downloader_telegram/README.md) (sección *Uploader a Telegram*)
- **CLI de Telegram (toolbox):** [`downloader_telegram/README.md`](downloader_telegram/README.md) (sección *CLI consolidada*)
- **Detección de episodios / corte:** [`ffmpeg-yt-dlp/README.md`](ffmpeg-yt-dlp/README.md) (secciones *Corte de inicio/fin* y *Configuración por fuente*)
- **Grabación `_completed`:** [`TwitchRecorder/README.md`](TwitchRecorder/README.md)
- **Comandos Docker y systemd:** [`docker_help.txt`](docker_help.txt)
- **Servicio systemd (auto-arranque al boot):** [`servicios/twitch-stream-pipeline.service`](servicios/twitch-stream-pipeline.service)

### Arranque del pipeline (AUTO al boot)

Los 3 servicios se levantan solos al encender el PC (systemd habilitado).
También puedes arrancarlos a mano con `pipe_up` (o vía systemd con `pipe_sys_start`).
Para quitar el auto-arranque:
`sudo systemctl disable twitch-stream-pipeline.service`
Ver la sección *PIPELINE VÍA SYSTEMD* en `docker_help.txt`.

### Pipeline YouTube → Telegram (cron automático)

El pipeline de YouTube se ejecuta automáticamente cada día de 01:00 a 18:00:

```bash
# Cron configurado (01:00 → 18:00 mismo día)
0 1 * * * /home/jorge/dev/devjobs/yt-to-telegram/scripts/run_pipeline_cron.sh

# Ver logs
cat data/yt-pipeline/logs/cron_$(date +%Y%m%d).log

# Parar manualmente
cd yt-to-telegram && docker compose down
```

Ver [`yt-to-telegram/README.md`](yt-to-telegram/README.md) para más detalles.

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
# Pipeline completo de una vez:
#   pipe_up (encender los 3 daemons)  pipe_down (parar los 3)  pipe_ps (estado)
#   plogs    (logs de los 3 a la vez, con color)
#   pipe_recreate (aplica cambios de CONFIG) | pipe_rebuild (cambios de CÓDIGO)
#   pipe_setup   (login Telegram uploader, una vez) | pipe_once (una pasada)
#   pipe_chats [--creados] · pipe_topics <grupo> · pipe_test [kw] [ruta]
#   pipe_sys_start / pipe_sys_stop / pipe_sys_status  (systemd)
# Logs en directo por proyecto/instancia:
#   ff_logs (monitor)  ff_manual_logs (midu)  tw_logs  tg_logs  pdf_logs
#   (con *_-stop / *_-restart para parar/reiniciar ese daemon individual)
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

---

## 🤝 Contribuir

Aportaciones, correcciones y nuevas herramientas son bienvenidas:

1. **Fork** el repositorio y crea una rama: `git checkout -b feat/mi-mejora`
2. Haz el cambio en la herramienta correspondiente (mantén su `README.md` al día).
3. Abre un **Pull Request** describiendo qué hace y por qué.
4. Para bugs: abre un *issue* con pasos para reproducirlo.
