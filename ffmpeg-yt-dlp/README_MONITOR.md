# README — Monitor de compresión (`monitor_folder.sh`)

Parte del pipeline **"Grabar → Comprimir → Subir a Telegram"**. Este servicio vigila una carpeta y comprime los vídeos nuevos automáticamente.

---

## Qué hace

1. Vigila una carpeta (por defecto `/home/jorge/dev/devjobs/data/grabaciones/test`, donde TwitchRecorder deja los `*_completed.mp4`,
   que pueden incluir la keyword del directo: `*_KW_<keyword>_completed.mp4`).
2. Detecta archivos que terminan en `*_completed.mp4`.
3. Los comprime a **720p** (H.264/libx264, CRF 23, preset medium, AAC 128k) — misma config que el preset "default" de midu.sh, para máxima compatibilidad.
   - **Garantía de tamaño <2 GB**: si el resultado de CRF 23 supera `TAMANO_MAX_MB` (default **1900 MB**, por el tope de Telegram), se re-codifica automáticamente en **2 pasadas** apuntando a ese tamaño. Así nunca supera 2 GB y no hay que partir el vídeo.
4. Guarda el resultado como `*_compressed.mp4` (conservando el prefijo, incluida la keyword)
   en `/home/jorge/dev/devjobs/data/comprimidos`.
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

> Atajo: con los alias instalados (`bash servicios/instalar_aliases.sh`), escribe
> **`ff_logs`** para seguir el `ffmpeg_monitor` en directo (igual que `plogs`
> muestra los 3 servicios del pipeline a la vez). Ver `docker_help.txt` sección 3.

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
| `-o, --output DIR` | Directorio de salida | `/home/jorge/dev/devjobs/data/comprimidos` |
| `-c, --crf VALUE` | Calidad CRF (menor = mejor) | `28` |
| `-p, --preset NAME` | Preset de velocidad | `fast` |
| `--codec NAME` | Códec de vídeo | `libx264` |
| `-r, --resolution N` | Escalar altura a `N`px (ej: `720`) | sin reescalar |
| `--completed-only` | Procesar solo `*_completed.*` | off |
| `--directo-completo` | **No cortar** inicio/fin del directo (mantener todo el vídeo) | off |
| `--interval SEGS` | Segundos entre comprobaciones | `30` |

### Variables de entorno

`RESOLUTION`, `COMPLETED_ONLY`, `DIRECTO_COMPLETO`, `CRF`, `PRESET`, `CODEC`, `AUDIO_CODEC`, `AUDIO_BITRATE`, `POLL_INTERVAL`, `OUTPUT_DIR`, `TAMANO_MAX_MB`, `OCR_STEP`, `CORTE_MARGEN`.

---

## Corte de inicio/fin del directo y `DIRECTO_COMPLETO`

Por defecto, antes de comprimir el monitor detecta los **episodios** (OCR de la
franja superior cada `OCR_STEP` segundos) y **recorta los extremos**: deja solo
la ventana entre el primer y el último episodio (con un margen de `CORTE_MARGEN`
segundos, default 300), descartando el pre-roll/espera y el final.

Esa detección también genera la metadata `*_episodios.json` (p. ej.
`"Episodio 1-4"`) que usa el uploader como pie/caption en Telegram.

Con **`DIRECTO_COMPLETO=true`** (o el flag `--directo-completo`) el monitor
**NO corta** el inicio/fin: se mantiene **todo el directo**. La detección de
episodios sigue ejecutándose (la metadata `*_episodios.json` para el caption
se sigue generando), pero el corte se ignora.

El servicio Docker `monitor` lo trae activo de fábrica:

```yaml
environment:
  - DIRECTO_COMPLETO=true
```

Para volver al comportamiento anterior (corte de extremos), ponlo a `false`
(o elimina la línea) en `docker-compose.yml` y recrea el contenedor:

```bash
docker compose up -d --force-recreate monitor
```

---

## Funcionamiento con el pipeline

```
TwitchRecorder → test/*_KW_<keyword>_completed.mp4  →  [este servicio]  →  comprimidos/*_KW_<keyword>_compressed.mp4  →  uploader (Telegram)
```

> Documentación completa del pipeline en el `README.md` de la raíz de `devjobs` y en `docker_help.txt` (sección *PIPELINE* y *PIPELINE VÍA SYSTEMD*).