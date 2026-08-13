# FFmpeg + yt-dlp Pipeline

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Conversor, descargador y editor de vídeo con ffmpeg, yt-dlp y preview watcher para WSL.



## Requisitos

- Docker
- (Opcional) VLC en Windows para previsualización desde WSL

## Despliegue

```bash
git clone https://github.com/jorge-bencas/devjobs.git
cd devjobs/ffmpeg-yt-dlp
docker compose build
docker compose up
```

### Fuera de Docker

```bash
# Instalar dependencias (Ubuntu/Debian)
sudo apt install ffmpeg
pip install yt-dlp

# Ejecutar
cd test_video
bash midu.sh
```

## Uso

### Ejecutar midu.sh (interactivo)

```bash
docker compose build
docker compose up
```

Al ejecutar, `midu.sh` arranca un menú interactivo con 33 modos.

### Ejecutar midu.sh (CLI)

```bash
# Dentro del contenedor o con yt-dlp + ffmpeg instalados
./midu.sh -d "URL"                              # Descargar
./midu.sh -d "URL" -dq 1080                     # Descargar a 1080p
./midu.sh -d "URL" -df mkv                      # Descargar como MKV
./midu.sh -d "URL" --playlist                   # Descargar playlist
./midu.sh --cut -ss 00:01:30 -e 00:03:45        # Cortar (lossless)
./midu.sh --convert -s telegram                  # Convertir para Telegram
./midu.sh --convert -p web -g 1.5               # Comprimir a 1.5GB
./midu.sh --convert -vc hevc --container mkv     # H265 a MKV
./midu.sh --remux --container mp4                # Cambiar contenedor sin re-encoding
./midu.sh --tracks "v:0,a:1,s:0"                 # Reordenar pistas
./midu.sh --concat-smart v1.mp4 v2.mp4           # Unir (auto-detecta compat)
./midu.sh --concat-smart --crossfade 1 v1.mp4 v2.mp4  # Unir con crossfade
./midu.sh --chain "cut=00:01:00:00:05:00" "convert=720"  # Pipeline encadenado
./midu.sh --compose                             # Compose:选 pistas personalizadas
./midu.sh --hls                                 # HLS streaming (m3u8)
./midu.sh --gif                                  # Crear GIF
./midu.sh --thumbnail --thumbnail-time 00:01:30  # Captura de pantalla
./midu.sh --info                                 # Info del vídeo
```

### Preview Watcher (WSL)

Abre vídeos en VLC/Windows mientras el contenedor Docker corre:

```bash
bash preview_watcher.sh --daemon   # segundo plano
bash preview_watcher.sh --stop     # detener
bash preview_watcher.sh --status   # verificar
bash preview_watcher.sh --once     # procesar una petición y salir
bash preview_watcher.sh            # bucle en primer plano (debug)
```

### Backup de canales de YouTube

Script para backup automático con archive (no re-descarga):

```bash
# Backup de canales específicos
bash scripts/backup_youtube.sh https://www.youtube.com/@Canal1 https://www.youtube.com/@Canal2

# Backup con calidad y formato personalizados
bash scripts/backup_youtube.sh -q 720 -f mkv https://www.youtube.com/@Canal1

# Directorio de backup personalizado
BACKUP_DIR=/mnt/backup bash scripts/backup_youtube.sh https://www.youtube.com/@Canal1
```

| Variable | Default | Descripción |
|----------|---------|-------------|
| `BACKUP_DIR` | `~/Backups/YouTube` | Directorio de backup |
| `MAX_QUALITY` | `1080` | Calidad máxima |
| `MERGE_FORMAT` | `mp4` | Formato de salida |

### Monitor de carpeta (compresión automática)

Vigila una carpeta y comprime vídeos nuevos automáticamente:

```bash
# Monitor con configuración por defecto
bash scripts/monitor_folder.sh ~/Downloads/videos

# Personalizar CRF, preset y destino
bash scripts/monitor_folder.sh -o /mnt/comp -c 23 -p medium ~/Videos/nuevos

# Con intervalo de polling personalizado
bash scripts/monitor_folder.sh --interval 60 ~/Videos/para_comprimir

# Solo procesar grabaciones terminadas, escalando a 720p (uso en pipeline)
bash scripts/monitor_folder.sh --completed-only -r 720 /ruta/a/vigilar
```

| Flag | Default | Descripción |
|------|---------|-------------|
| `-o, --output DIR` | `Videos/comprimidos` | Directorio de salida |
| `-c, --crf VALUE` | `28` | Calidad CRF (menor = mejor) |
| `-p, --preset NAME` | `fast` | Preset de velocidad |
| `--codec NAME` | `libx264` | Códec de vídeo |
| `-r, --resolution N` | sin reescalar | Escalar altura a N px (ej: `720`) |
| `--completed-only` | off | Procesar solo `*_completed.*` |
| `--interval SEGS` | `30` | Segundos entre comprobaciones |

#### Servicio `monitor` (pipeline)

El `docker-compose.yml` define el servicio **`monitor`** (`ffmpeg_monitor`), pensado para el pipeline "Grabar → Comprimir → Subir a Telegram":

```bash
docker compose build
docker compose up -d monitor      # arranca el monitor en background
docker compose logs -f monitor    # logs del monitor
docker compose stop monitor       # parar solo el monitor
```

Vigila `/home/jorge/dev/devjobs/test_videos/test` (donde TwitchRecorder deja los `*_completed.mp4`), comprime a **720p** y guarda en `/home/jorge/dev/devjobs/Videos/comprimidos`, que es la carpeta que vigila el `uploader` para subir a Telegram.

> Documentación completa del monitor: [ver `README_MONITOR.md`](README_MONITOR.md).

## Los 33 modos de midu.sh

| # | Modo | Descripción | Ejemplo |
|---|------|-------------|---------|
| 1 | `download` | Descargar de YouTube, Twitch, Kick, TikTok, +1000 sitios | `-d "URL"` |
| 2 | `cut` | Cortar vídeo sin perder calidad (lossless) | `--cut -ss 00:01:30 -e 00:03:45` |
| 3 | `convert` | Convertir/comprimir con presets por red social | `--convert -s telegram` |
| 4 | `gif` | Crear GIF animado | `--gif --gif-fps 15` |
| 5 | `thumbnail` | Extraer frame como imagen PNG | `--thumbnail --thumbnail-time 00:01:30` |
| 6 | `info` | Mostrar duración, codecs, resolución, bitrate | `--info` |
| 7 | `rotate` | Girar 90°, 180° o 270° | `--rotate 90` |
| 8 | `crop` | Recortar a tamaño específico | `--crop 640:480` |
| 9 | `fade` | Fade in/out automático | `--fade 2` |
| 10 | `normalize` | Equalizar volumen (loudnorm) | `--normalize` |
| 11 | `watermark` | Poner imagen encima del vídeo | `--watermark logo.png` |
| 12 | `deinterlace` | Quitar rayas de TV vieja | `--deinterlace` |
| 13 | `fps` | Cambiar frames por segundo | `--fps 60` |
| 14 | `speed` | Acelerar o ralentizar | `--speed 2.0` |
| 15 | `subtitles` | Embeber (soft) o quemar (hard) subtítulos | `-sh subs.srt` |
| 16 | `concat` | Unir varios vídeos en uno | `--concat v1.mkv v2.mkv` |
| 17 | `audio-only` | Extraer solo audio | `-ao "URL"` |
| 18 | `stabilize` | Quitar temblor (vidstab) | `--stabilize 5` |
| 19 | `adjust` | Ajustar brillo, contraste, saturación, gamma | `--adjust brightness=0.5 contrast=1.2` |
| 20 | `censor` | Pixelar regiones (caras, matrículas) | `--censor 100:50:200:150` |
| 21 | `denoise` | Reducir ruido | `--denoise 50` |
| 22 | `sharpen` | Enfocar vídeo borroso | `--sharpen 5` |
| 23 | `reverse` | Invertir vídeo (al revés) | `--reverse` |
| 24 | `scenes` | Detectar escenas y cortar automáticamente | `--scenes 0.3` |
| 25 | `keyframes` | Extraer todas las imágenes I-frame | `--keyframes` |
| 26 | `aspect` | Cambiar ratio de aspecto | `--aspect 16:9` |
| 27 | `metadata` | Editar título, autor, comentario | `--metadata title="Mi vídeo"` |
| 28 | `remux` | Cambiar contenedor sin re-encoding, selección interactiva de audio | `--remux` |
| 29 | `tracks` | Reordenar/renombrar pistas de vídeo, audio y subtítulos | `--tracks "v:0,a:1,s:0"` |
| 30 | `concat-smart` | Unir con auto-detección de compatibilidad + crossfade | `--concat-smart v1.mp4 v2.mp4` |
| 31 | `chain` | Pipeline encadenado: varios pasos en un solo comando | `--chain "cut=00:01:00:00:05:00" "convert=720"` |
| 32 | `compose` | Seleccionar vídeo + varias pistas de audio + subtítulos + codec por pista | `--compose` |
| 33 | `hls` | Preparar vídeo para streaming HLS (m3u8) con múltiples calidades | `--hls` |

### Pregunta al eliminar el original (modo convert)

Al terminar cada conversión, `midu.sh` pregunta en pantalla **¿Eliminar el archivo ORIGINAL? `[s/N]`** (solo en terminal interactiva; en modo automatizado/daemon no pregunta y conserva el original). Responde `s` para borrarlo o `Enter`/`n` para conservarlo.

## Selección de audio interactivo

Cuando un vídeo tiene varias pistas de audio (ej: español, inglés, commentary), los modos `remux`, `tracks` y `convert` muestran un menú interactivo:

```
Pistas de audio disponibles:
     1) Pista 0 — spa (aac)
     2) Pista 1 — eng (ac3)
     3) Pista 2 — Commentary (mp3)
     0) Primera pista (automático)
  → Selecciona audio [0-3]: 1
```

## Sub-modos de corte

```bash
# Cortar un trozo (mantener solo eso)
./midu.sh --cut -ss 00:01:00 -e 00:02:30

# Eliminar secciones (quitar partes del vídeo)
./midu.sh --cut --remove --clips 00:01:00-00:02:30,00:05:00-00:07:15

# Extraer clips y unirlos en un solo vídeo
./midu.sh --cut --extract --clips 00:01:00-00:02:30,00:05:00-00:07:15
```

## Presets de red social

| Plataforma | Resolución | Tamaño máx | Códec | Preset |
|------------|------------|------------|-------|--------|
| `whatsapp` | 720p | 1GB | h264 | web |
| `telegram` | 1080p | 2GB | hevc | default |
| `instagram` | 1080p | 0.5GB | h264 | default |
| `tiktok` | 1080p | 0.5GB | h264 | default |
| `youtube` | original | sin límite | h264 | archive |
| `twitter` | 720p | 0.5GB | h264 | web |
| `facebook` | 1080p | 1GB | h264 | default |

## Presets de calidad

| Preset | CRF | Velocidad | Uso |
|--------|-----|-----------|-----|
| `ultrafast` | 28 | ultrafast | Muy rápido, poco peso |
| `web` | 28 | fast | Rápido, buen balance |
| `default` | 23 | medium | Equilibrado |
| `archive` | 18 | slow | Alta calidad |
| `quality` | 15 | veryslow | Máxima calidad |

## Códecs de vídeo soportados

| Códec | Encoder | Notas |
|-------|---------|-------|
| `h264` | libx264 | Máxima compatibilidad |
| `hevc` | libx265 | Mejor calidad/menor tamaño |
| `av1` | libsvtav1 | Máxima eficiencia (muy lento) |
| `vp9` | libvpx-vp9 | Buen equilibrio para web |

## Aceleración por hardware

La GPU se detecta automáticamente y se aplica en **todos** los modos de edición:

- **NVENC** (NVIDIA): `nvidia-smi` disponible → usa `h264_nvenc` / `hevc_nvenc`
- **VAAPI** (Intel/AMD): `vainfo` disponible → usa `h264_vaapi` / `hevc_vaapi`
- **CPU**: fallback con libx264/libx265

| GPU | Speedup | Modos soportados |
|-----|---------|------------------|
| NVIDIA | 2-5x | Todos (stabilize, adjust, censor, denoise, sharpen, reverse, aspect, concat, convert) |
| Intel/AMD | 1.5-3x | Todos |
| CPU | 1x | Todos |

## Flags generales

| Flag | Descripción |
|------|-------------|
| `-n, --non-interactive` | Sin prompts, usa valores por defecto |
| `-c, --save-config` | Guarda configuración en conf.json |
| `-v, --verbose` | Muestra progreso línea por línea |
| `--two-pass` | Two-pass encoding (mejor calidad con --max-gb) |
| `--hw-accel` | Usar aceleración por hardware |
| `--dry-run` | Preview sin ejecutar (muestra comandos) |
| `--collision POLICY` | skip, rename o overwrite (default: overwrite) |
| `--notify` | Notificación al terminar (notify-send) |
| `--write-subs` | Descargar subtítulos con yt-dlp |
| `--sub-langs LANGS` | Idiomas de subtítulos (default: es,en) |
| `--container FMT` | Formato de contenedor de salida: mp4\|mkv (default: mp4) |
| `--audio-lang LANG` | Seleccionar pista de audio por idioma (spa, eng, und) |
| `--recursive` | Buscar en todas las subcarpetas (no solo 2 niveles) |
| `--checkpoint FILE` | Guardar progreso para resume |
| `--resume [FILE]` | Continuar desde checkpoint |
| `--retry` | Reintentar archivos fallidos al terminar |

## Flags de descarga

| Flag | Descripción |
|------|-------------|
| `-d, --download URL` | Descargar vídeo de URL |
| `-dq, --dl-quality QUALITY` | Calidad: best, 4k, 1080, 720, 480, audio-only |
| `-df, --dl-format FORMAT` | Formato: mp4, mkv, webm, best |
| `--playlist` | Descargar playlist completa |
| `--dl-subs-only` | Solo descargar subtítulos |
| `-ds, --dl-start TIME` | Inicio de descarga parcial |
| `-de, --dl-end TIME` | Fin de descarga parcial |
| `--download-archive FILE` | Guardar historial (no re-descargar) |
| `--dateafter DATE` | Solo vídeos posteriores a fecha (YYYYMMDD) |
| `--datebefore DATE` | Solo vídeos anteriores a fecha (YYYYMMDD) |
| `--playlist-items RANGE` | Seleccionar items (ej: 1-5, 1,3,5) |
| `--flat-playlist` | Listar títulos sin descargar |
| `--playlist-reverse` | Invertir orden de playlist |
| `--playlist-random` | Orden aleatorio de playlist |

## Flags de unión

| Flag | Descripción |
|------|-------------|
| `--concat FILE1 FILE2...` | Unir vídeos (stream copy si compatible) |
| `--concat-smart FILE1 FILE2...` | Unir con auto-detección + fallback re-encode |
| `--crossfade DURATION` | Crossfade entre clips (segundos) |

## Pipeline encadenado

```bash
# Formato: --chain "operación=arg1:arg2" "operación=arg2"
./midu.sh --chain "cut=00:01:00:00:05:00" "convert=720" "fade=2"

# Operaciones disponibles:
#   cut=START:END        Cortar vídeo
#   convert=RES          Convertir (720, 1080, 4k)
#   rotate=GRADOS        Rotar (90, 180, 270)
#   fade=SEGUNDOS        Fade in/out
#   reverse              Invertir vídeo
#   denoise=FUERZA       Reducir ruido (1-100)
#   sharpen=FUERZA       Enfocar (1-10)
#   normalize            Normalizar audio
```

## Compose (selección de pistas)

Selecciona qué pistas de vídeo, audio y subtítulos quieres en el archivo final:

```bash
./midu.sh --compose
```

Flujo:
1. Seleccionar pista de vídeo (copy o elegir otra)
2. Elegir varias pistas de audio (rango: 1-3 o selección múltiple 1,2,4)
3. Asignar codec individual por cada pista de audio (aac, copy, opus, ac3, eac3, flac)
4. Elegir subtítulos (opcional)
5. Seleccionar contenedor de salida (mkv, mp4, ts)

## HLS (streaming)

Prepara vídeos para streaming con múltiples calidades:

```bash
./midu.sh --hls
```

Genera:
- Múltiples calidades (360p a 4K)
- Segmentos configurables (default 4s)
- Playlist maestro adaptativo (master.m3u8)

## Variables del Preview Watcher

| Variable | Default | Descripción |
|----------|---------|-------------|
| `IDLE_TIMEOUT` | 600 | Segundos sin actividad antes de apagarse |
| `MIDU_CONTAINER_NAME` | yt_ffmpeg_downloader | Nombre del contenedor Docker |
| `MIDU_CONTAINER_MATCH` | `^(yt_ffmpeg_downloader\|ffmpeg-yt-dlp-downloader)` | Regex para detectar el contenedor |

## Variables de entorno (ntfy)

| Variable | Descripción |
|----------|-------------|
| `NTFY_URL` | URL del webhook de ntfy.sh para notificaciones push |

## Estructura

```
ffmpeg-yt-dlp/
├── docker-compose.yml     # servicio Docker (Alpine + ffmpeg + yt-dlp)
├── preview_watcher.sh     # abre vídeos en WSL/Windows (host)
├── .env.example           # plantilla de variables de entorno
├── scripts/
│   ├── backup_youtube.sh  # backup automático de canales de YouTube
│   └── monitor_folder.sh  # monitoreo y compresión automática
├── test_video/
│   ├── midu.sh            # script principal (~6000 líneas, 33 modos)
│   ├── optimizados/       # vídeos convertidos (por defecto)
│   └── test/              # vídeos de entrada (por defecto)
├── LICENSE                # MIT
└── README.md
```

## Flujo recomendado

```bash
# 1. Descargar
./midu.sh -d "https://youtube.com/watch?v=..."

# 2. Cortar (lossless, sin re-encoding)
./midu.sh --cut -ss 00:05:00 -e 00:10:00

# 3. Convertir para Telegram
./midu.sh --convert -s telegram
```

## Peculiaridades

- **Auto-setup**: El Dockerfile instala todas las dependencias automáticamente
- **Remux automático**: Si el vídeo ya es h264+aac y no necesita corte, se remuxa sin re-encoding
- **Detección de GPU**: Auto-detecta NVENC/VAAPI y usa aceleración por hardware
- **Reintentos**: Si el tamaño supera el límite, re-codifica con menor bitrate (hasta 2 intentos)
- **Panel de progreso**: Muestra progreso por archivo en tiempo real con hilos paralelos (max 4)
- **Checkpoint**: Guarda estado para reanudar si se interrumpe
- **Colisión**: Opciones skip/rename/overwrite para archivos existentes
- **Notificaciones**: Soporta notify-send (Linux) y ntfy.sh (push)

## Blog

- [FFmpeg + yt-dlp Pipeline: Conversor y Editor de Vídeo con 33 Modos](https://blog-jorbencas.vercel.app/proyectos/ffmpeg-yt-dlp/)
- [Guía de comandos de yt-dlp y ffmpeg](https://blog-jorbencas.vercel.app/posts/guia_ffmpeg_y_ÿt_dlp/)
- [Docker: ffmpeg y yt-dlp en Windows (WSL) y Ubuntu](https://blog-jorbencas.vercel.app/posts/docker-to-yt-ffmpeg_in-wls/)
