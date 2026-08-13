# README — Monitor de compresión (`monitor_folder.sh`)

Parte del pipeline **"Grabar → Comprimir → Subir a Telegram"**. Este servicio vigila una carpeta y comprime los vídeos nuevos automáticamente.

---

## Qué hace

1. Vigila una carpeta (por defecto `/home/jorge/dev/devjobs/test_videos/test`, donde TwitchRecorder deja los `*_completed.mp4`,
   que pueden incluir la keyword del directo: `*_KW_<keyword>_completed.mp4`).
2. Detecta archivos que terminan en `*_completed.mp4`.
3. Los comprime a **720p** (H.264, CRF 28, preset fast, AAC 128k).
4. Guarda el resultado como `*_compressed.mp4` (conservando el prefijo, incluida la keyword)
   en `/home/jorge/dev/devjobs/Videos/comprimidos`.
5. Mueve el original a `$OUTPUT_DIR/.processed`.
6. Repite cada `POLL_INTERVAL` segundos.

Salida → es la carpeta que vigila el servicio `uploader` de `downloader_telegram` para subir a Telegram.

---

## Servicio Docker `monitor`

Definido en `docker-compose.yml` del proyecto `ffmpeg-yt-dlp`. Corre con `restart: unless-stopped`.

### Arrancar

```bash
cd /home/jorge/dev/devjobs/ffmpeg-yt-dlp
docker compose build        # reconstruir tras cambios
docker compose up -d monitor
```

### Ver estado / logs

```bash
docker compose ps
docker compose logs -f monitor
```

### Parar

```bash
docker compose stop monitor   # o docker compose down
```

---

## Uso directo (host, sin Docker)

```bash
bash scripts/monitor_folder.sh --completed-only -r 720 /ruta/a/vigilar
```

### Flags

| Flag | Descripción | Default |
|---|---|---|
| `-o, --output DIR` | Directorio de salida | `/home/jorge/dev/devjobs/Videos/comprimidos` |
| `-c, --crf VALUE` | Calidad CRF (menor = mejor) | `28` |
| `-p, --preset NAME` | Preset de velocidad | `fast` |
| `--codec NAME` | Códec de vídeo | `libx264` |
| `-r, --resolution N` | Escalar altura a `N`px (ej: `720`) | sin reescalar |
| `--completed-only` | Procesar solo `*_completed.*` | off |
| `--interval SEGS` | Segundos entre comprobaciones | `30` |

### Variables de entorno

`RESOLUTION`, `COMPLETED_ONLY`, `CRF`, `PRESET`, `CODEC`, `AUDIO_CODEC`, `AUDIO_BITRATE`, `POLL_INTERVAL`, `OUTPUT_DIR`.

---

## Funcionamiento con el pipeline

```
TwitchRecorder → test/*_KW_<keyword>_completed.mp4  →  [este servicio]  →  comprimidos/*_KW_<keyword>_compressed.mp4  →  uploader (Telegram)
```

> Documentación completa del pipeline en el `README.md` de la raíz de `devjobs` y en `docker_help.txt` (sección *PIPELINE* y *AUTO-ARRANQUE*).