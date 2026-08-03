# 🎥 FFmpeg + yt-dlp Pipeline

Conversor, descargador y editor de vídeo con ffmpeg, yt-dlp y preview watcher para WSL.



## Requisitos

- Docker
- (Opcional) VLC en Windows para previsualización desde WSL

## Uso

### Ejecutar midu.sh (interactivo)

```bash
docker compose build
docker compose up
```

Al ejecutar, `midu.sh` arranca un menú interactivo con 27 modos.

### Ejecutar midu.sh (CLI)

```bash
# Dentro del contenedor o con yt-dlp + ffmpeg instalados
./midu.sh -d "URL"                              # Descargar
./midu.sh --cut -ss 00:01:30 -e 00:03:45        # Cortar (lossless)
./midu.sh --convert -s telegram                  # Convertir para Telegram
./midu.sh --convert -p web -g 1.5               # Comprimir a 1.5GB
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

## Los 27 modos de midu.sh

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
| 20 | `censur` | Pixelar regiones (caras, matrículas) | `--censor 100:50:200:150` |
| 21 | `denoise` | Reducir ruido | `--denoise 50` |
| 22 | `sharpen` | Enfocar vídeo borroso | `--sharpen 5` |
| 23 | `reverse` | Invertir vídeo (al revés) | `--reverse` |
| 24 | `scenes` | Detectar escenas y cortar automáticamente | `--scenes 0.3` |
| 25 | `keyframes` | Extraer todas las imágenes I-frame | `--keyframes` |
| 26 | `aspect` | Cambiar ratio de aspecto | `--aspect 16:9` |
| 27 | `metadata` | Editar título, autor, comentario | `--metadata title="Mi vídeo"` |

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

- **NVENC** (NVIDIA): `nvidia-smi` disponible → usa `h264_nvenc`
- **VAAPI** (Intel/AMD): `vainfo` disponible → usa `h264_vaapi`
- **CPU**: fallback con libx264/libx265

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
| `--checkpoint FILE` | Guardar progreso para resume |
| `--resume [FILE]` | Continuar desde checkpoint |
| `--retry` | Reintentar archivos fallidos al terminar |

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

## Configuración persistente (conf.json)

```json
{
  "inputDir": ".",
  "outputDir": "./optimizados",
  "extensions": "avi,webm,mkv,mp4,flv",
  "verbose": true,
  "modes": {
    "convert": {
      "social": "",
      "preset": "default",
      "videoCodec": "h264",
      "audioCodec": "aac",
      "audioBitrate": "128k",
      "resolution": "720",
      "maxSize": "1.5"
    }
  }
}
```

La configuración se guarda con `-c` y se carga automáticamente al iniciar.

## Estructura

```
ffmpeg-yt-dlp/
├── conf.json              # configuración de conversión
├── docker-compose.yml     # servicio Docker (Alpine + ffmpeg + yt-dlp)
├── preview_watcher.sh     # abre vídeos en WSL/Windows (host)
└── test_video/
    ├── midu.sh            # script principal (4797 líneas, 27 modos)
    ├── optimizados/       # vídeos convertidos (por defecto)
    └── test/              # vídeos de entrada (por defecto)
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

- [FFmpeg + yt-dlp Pipeline: Conversor y Editor de Vídeo con 27 Modos](https://blog-jorbencas.vercel.app/proyectos/ffmpeg-yt-dlp/)
- [Guía de comandos de yt-dlp y ffmpeg](https://blog-jorbencas.vercel.app/posts/guia_ffmpeg_y_ÿt_dlp/)
- [Docker: ffmpeg y yt-dlp en Windows (WSL) y Ubuntu](https://blog-jorbencas.vercel.app/posts/docker-to-yt-ffmpeg_in-wls/)
