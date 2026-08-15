# TwitchRecorder

Grabador automático de directos de **Twitch**, **YouTube** y **Kick** con Docker. Detecta cuándo un canal está en directo, graba con calidad original usando Streamlink/yt-dlp, reconecta si se cae y organiza los vídeos por fecha.

---

## ¿Por qué existe este proyecto?

Me encanta ver directos de Twitch, YouTube y Kick, pero siempre me pasa lo mismo: se me olvida que mi streamer favorito empieza a las 21:00, o empiezo a verlo y tengo que irme antes de que termine, o quiero verlo después pero el VOD se borra en 2 días.

Quería una forma de que se grabaran los directos automáticamente sin tener que estar pendiente. Si mi streamer favorito empieza a las 22:00 pero yo estoy ocupado, que se grabe solo. Cuando llegue a casa, lo veo cuando quiera. Y si se cae la conexión, que reconecte solo y siga grabando.

Probé con OBS programado, pero tiene problemas: necesitas tener el ordenador encendido, la ventana abierta, y si se cierra se para la grabación. Además, OBS re-codifica el vídeo (más CPU, menos calidad). Quería algo que grabara el stream tal cual sale de la plataforma, sin tocar nada.

---

## El problema

Grabar directos de Twitch manualmente es un fastidio. Siempre te pierdes el principio, o se te olvida darle a grabar, o tienes que tener OBS abierto todo el rato. La solución: un Docker que lo haga todo solo. Y no solo Twitch: también YouTube y Kick.

## Qué hace

TwitchRecorder detecta cuándo un canal entra en directo en Twitch, YouTube o Kick, graba el stream con calidad original (sin recompresión), y guarda el vídeo organizado por fecha. Si se pierde la conexión, reconecta automáticamente.

En resumen: arrancas el Docker y te olvidas. Cuando tu streamer favorito empiece, se graba solo.

---

## Requisitos

- Docker instalado ([docker.com](https://www.docker.com))
- Un canal de Twitch, YouTube o Kick que quieras grabar
- Un PC o servidor que pueda estar encendido cuando empiece el directo

---

## Configuración

Edita `config.json`:

```json
{
    "channels": {
        "sendosama": { "platform": "twitch" },
        "MrBeast": { "platform": "youtube" },
        "adin": { "platform": "kick" }
    },
    "record_path": "/recordings",
    "days": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
    "start_time": "21:30",
    "check_every": 30,
    "max_duration": "24:00:00",
    "retry_interval": 60,
    "copy_to_test": true,
    "test_path": "/recordings/test"
}
```

### Plataformas soportadas

| Plataforma | `platform` | Herramienta | Ejemplo |
|---|---|---|---|
| Twitch | `twitch` | Streamlink | `sendosama` |
| YouTube | `youtube` | yt-dlp | `MrBeast` |
| Kick | `kick` | yt-dlp | `adin` |
| Web (URL propia) | `web` | yt-dlp | `watch.sendosama.net` |

### Varias fuentes por canal (prioridad + fallback)

`platform` admite un **str** (una sola fuente) o una **lista** de fuentes en orden de
**prioridad**: se graba de la primera que esté en directo. Cada elemento es un str
(plataforma) o un dict `{"platform": "web", "url": "..."}` para una web.

```json
"channels": {
    "sendosama": {
        "platform": [
            { "platform": "web", "url": "https://watch.sendosama.net/" },
            "twitch",
            "kick"
        ]
    }
}
```

En este ejemplo, si la web del streamer está emitiendo (su servidor, que muestra
el directo real y los capítulos) se graba de ahí; si no, se prueba Twitch
(lo normal) y luego Kick.

> **Ojo — la web suele estar CAÍDA.** Es un servidor propio que Sendo enciende
> solo cuando quiere mostrar los capítulos (normalmente emite en Twitch y la
> web no responde). Por eso la comprobación web hace un pre-check HTTP rápido
> (~4 s) y, si no responde, pasa directo a la siguiente fuente.

### Autotest automático de la web

La primera vez que se detecta la web **en directo**, el recorder ejecuta solo
una prueba de captura (equivale a `yt-dlp -F`) y deja un informe en
`<record_path>/web_probe.log` con los formatos encontrados y el veredicto
`CAPTURABLE / NO CAPTURABLE`. Así se verifica el primer directo por la web sin
tener que estar pendiente. Se vuelve a probar si la web se detecta caída y
luego reaparece en directo.

### Campos de configuración

| Campo | Descripción |
|---|---|
| `channels` | Diccionario con canales. Cada uno indica su plataforma: `twitch`, `youtube` o `kick` |
| `record_path` | Ruta dentro del contenedor donde se guardan los vídeos |
| `days` | Días de la semana en los que se comprueba si hay directo |
| `start_time` | Hora mínima para empezar a comprobar (no desperdicia recursos antes) |
| `check_every` | Cada cuántos segundos se comprueba si el canal está en directo |
| `max_duration` | Duración máxima de grabación en formato `HH:MM:SS` |
| `retry_interval` | Si se pierde la conexión, espera estos segundos antes de reconectar |
| `copy_to_test` | Si `true`, al terminar un directo mueve la grabación a `test_path` renombrada a `*_completed.mp4` |
| `test_path` | Carpeta donde van los `*_completed.mp4` (para el pipeline de compresión/subida) |

> **Nota:** `copy_to_test` con el PC tal cual monta el contenedor (`/home/jorge/dev/devjobs/data/grabaciones:/recordings`) escribe los `*_completed.mp4` en `/home/jorge/dev/devjobs/data/grabaciones/test/`. Esa carpeta es la que vigila `monitor_folder.sh` del pipeline (ver sección [Pipeline completo](#pipeline-completo-grabar--comprimir--subir-a-telegram)).

---

## Uso

### Ejecutar en background (producción)

```bash
docker compose up -d
```

El contenedor se reinicia solo si el PC se reinicia (`restart: unless-stopped`).

### Ejecutar una vez (test)

```bash
docker compose run --rm run
```

### Dry-run (sin grabar)

```bash
docker compose run --rm run --dry-run
```

Detecta el directo pero no graba. Ideal para verificar que la config funciona.

### Ver logs

```bash
docker compose logs -f
```

Los logs muestran timestamp: `17:35:28 [sendosama] Grabación iniciada`

### Parar

```bash
docker compose down
```

### Reconstruir tras cambios

```bash
docker compose build
```

### Ejecutar con config temporal

```bash
docker run --rm \
  -v ./config.json:/app/config.json:ro \
  -v /home/jorge/dev/devjobs/data/grabaciones:/recordings \
  -e TZ=Europe/Madrid \
  twitchrecorder-run
```

---

## Cómo funciona

```
Docker arranca
    │
    ▼
¿Hoy es día programado?
    │
    NO → Espera al siguiente día
    │
    SÍ
    ▼
¿Ya es hora de start_time?
    │
    NO → Espera (sin consumir CPU)
    │
    SÍ
    ▼
¿El canal está en directo?
    │
    NO → Espera check_every segundos
    │
    SÍ
    ▼
Inicia grabación con Streamlink/yt-dlp
    │
    ▼
Monitor comprueba cada 5 segundos:
    │
    ├── ¿Sigue online? → Sigue grabando
    ├── ¿Se cayó pero sigue en directo? → Reconecta en retry_interval segundos
    ├── ¿El directo terminó? → Para y guarda
    └── ¿Pasó max_duration? → Para y guarda
    │
    ▼
Espera al siguiente directo
```

---

## Tecnologías

- **Python** — orquestador del sistema. Controla horarios, comprobaciones, inicio/fin de grabación y organización de archivos.
- **Streamlink** — obtiene el stream de Twitch directamente. Sin navegador, sin Selenium, sin calidad reducida. Es lo que usa `vlc` por debajo.
- **yt-dlp** — obtiene el stream de YouTube y Kick. La misma herramienta que usas para descargar vídeos de YouTube.
- **Docker** — contenedor portátil. Una vez construido, funciona igual en cualquier máquina con Docker instalado.
- **FFmpeg** — dentro del contenedor, Streamlink y yt-dlp lo usan internamente para manejar el stream.

### Por qué no usar OBS

OBS es fantástico para grabar tu pantalla, pero para este caso de uso tiene problemas:

- Necesita tener la ventana abierta
- Consume más CPU (decodifica y vuelve a codificar)
- Si se cierra, se para la grabación
- No puedes programarlo fácilmente

Streamlink descarga el stream tal cual sale de Twitch. Sin recompresión, sin pérdida de calidad, sin CPU de más.

### Qué es Streamlink

Streamlink es una herramienta de línea de comandos que extrae streams de más de 100 plataformas de streaming y los reproduce directamente en un reproductor local (VLC, MPV, etc.) o los guarda en un archivo. Nació en 2016 como fork de Livestreamer.

| | Navegador | Streamlink |
|---|---|---|
| RAM | 2-4 GB | < 100 MB |
| CPU | 30-50% | Mínimo |
| Calidad | Recompresión | Directa (sin pérdida) |
| Dependencias | Flash, JS, cookies | Solo Python |

**Otros usos de Streamlink:**
- `streamlink twitch.tv/canal best` — abre el stream directamente en VLC
- `streamlink twitch.tv/canal best -o grabacion.mp4` — graba a archivo
- `best`, `worst`, `720p`, `1080p60`, `audio_only` — selectable calidad
- `--twitch-low-latency` — baja latencia

### Qué es yt-dlp

yt-dlp es un fork de youtube-dl, la herramienta más popular para descargar vídeos de YouTube. Soporta más de 1000 sitios web.

**Otros usos de yt-dlp:**
- `yt-dlp URL` — descarga el mejor formato
- `yt-dlp -f bestaudio URL` — extrae solo el audio
- `yt-dlp URL.playlist` — descarga toda la lista
- `yt-dlp --write-subs URL` — descarga subtítulos

---

## Recuperación automática

| Escenario | Qué hace |
|---|---|
| Stream pierde conexión | Espera y reconecta |
| Streamlink/yt-dlp devuelve error | Reintenta en 60 segundos |
| PC pierde Internet | Espera y continúa |
| Directo termina | Guarda el archivo y espera al siguiente |

---

## Organización de archivos

```
grabaciones/
├── 2026/
│   └── 07/
│       ├── sendosama_2026-07-25_21-30-00.mp4
│       ├── MrBeast_2026-07-26_21-15-00.mp4
│       └── adin_2026-07-27_22-00-00.mp4
└── test/
    └── sendosama_2026-07-26_21-15-00_completed.mp4
```

**Nombre del archivo:** `canal_YYYY-MM-DD_HH-MM-SS.mp4`
**Cuando `copy_to_test` está activo:** al terminar el directo, la grabación se **mueve** a `test/` y se renombra a `canal_..._completed.mp4` (marcada como lista para el pipeline).

### Keyword del directo (para ruteo a grupos)

Al detectar el directo, TwitchRecorder lee su **título** con yt-dlp y extrae una `keyword` normalizada, que incrusta en el nombre del archivo:

```
sendosama_2026-08-13_20-15-00_KW_prueba.mp4
```

> **Título real vs genérico**: algunos canales de Twitch dejan el título genérico
> (`"<canal> (live)"`) en el campo `title`, y el título real va en la descripción
> (p. ej. `"📗 LOS DIARIOS DE LA BOTICARIA..."`). Si se detecta un título genérico,
> TwitchRecorder usa la **descripción** como fuente del título, para que el
> keyword sea el correcto (ej. `diarios_boticaria` y no `sendosama_live`).

Esa keyword viaja intacta por todo el pipeline (`*_completed.mp4` → `*_compressed.mp4`). El servicio `uploader` la usa para decidir a qué grupo de Telegram subir el vídeo: **al grupo cuyo `nombre` coincida con la keyword**, o al `default` si no hay coincidencia. Ver `downloader_telegram/README_UPLOADER.md`.

---

## Pipeline completo: grabar → comprimir → subir a Telegram

TwitchRecorder es la **primera pieza** de un pipeline automático. Las tres piezas:

| Pieza | Proyecto | Hace |
|---|---|---|
| 1. Grabar | `TwitchRecorder` | Graba el directo y deja `*_completed.mp4` en `test/` |
| 2. Comprimir | `ffmpeg-yt-dlp` (servicio `monitor`) | Convierte a 720p → `comprimidos/*_compressed.mp4` |
| 3. Subir | `downloader_telegram` (servicio `uploader`) | Sube a los grupos de Telegram |

**Arranque del pipeline:**
```bash
# TwitchRecorder (esta carpeta)
docker compose up -d twitchrecorder
# ffmpeg-yt-dlp
cd ../ffmpeg-yt-dlp && docker compose up -d monitor
# downloader_telegram
cd ../downloader_telegram && docker compose up -d uploader
```

**Arranque MANUAL (no automático al boot):** los tres servicios NO se levantan
solos al encender el PC (a propósito). Se arrancan a mano con `pipe_up` o
`sudo systemctl start twitch-stream-pipeline.service`. Si algún día se quiere
auto-arranque al boot: `sudo systemctl enable .../twitch-stream-pipeline.service`.
Ver la sección *PIPELINE VÍA SYSTEMD* en `docker_help.txt`.

> Documentación completa del pipeline en `README.md` de la raíz de `devjobs`.

---

## Bugs encontrados durante el desarrollo

### 1. URL saltada al usar binario streamlink

En Linux, el binario `streamlink` se instala en `/usr/local/bin/streamlink`. Al usarlo directamente, el código construía mal el comando y se saltaba la URL del canal:

```python
# Mal — cmd[1:] se salta la URL
cmd = ["https://www.twitch.tv/canal", "best", "-o", "archivo.mp4", "--force"]
self.process = subprocess.Popen([sl_exe] + cmd[1:], ...)

# Bien
self.process = subprocess.Popen([sl_exe] + cmd, ...)
```

### 2. Buffer de stdout lleno

Streamlink escribe mucha información a stderr. Si usas `stdout=subprocess.PIPE`, el buffer se llena y el proceso se bloquea:

```python
# Mal — el buffer se llena y el proceso muere
stdout=subprocess.PIPE, stderr=subprocess.PIPE

# Bien — redirige a /dev/null
stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
```

---

## Estructura del proyecto

```
TwitchRecorder/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── config.json
├── requirements.txt
├── main.py
├── utils/
│   ├── __init__.py
│   ├── config.py         # Carga y valida config.json
│   ├── twitch.py         # Comprueba si un canal está en directo (Twitch)
│   ├── youtube.py        # Comprueba si un canal está en directo (YouTube)
│   ├── kick.py           # Comprueba si un canal está en directo (Kick)
│   ├── web.py            # Comprueba una URL propia (yt-dlp genérico, ej. watch.sendosama.net)
│   ├── recorder.py       # Graba el stream con Streamlink o yt-dlp
│   ├── scheduler.py      # Controla horarios y comprobaciones
│   ├── files.py          # Organiza archivos por fecha
│   └── logger.py         # Log con timestamps
├── tests/
└── README.md
```

### Dockerfile

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /recordings
ENTRYPOINT ["python", "-u", "main.py"]
CMD []
```

**`python:3.12-slim`** en lugar de `python:3.12` completa (~150MB vs ~900MB). **`-u`** en el CMD desactiva el buffer de Python para ver logs en tiempo real.

---

## Resumen de comandos

| Comando | Qué hace |
|---|---|
| `docker compose up -d twitchrecorder` | Arranca el daemon en background |
| `docker compose down` | Para todo |
| `docker compose run --rm run` | Ejecuta una vez |
| `docker compose run --rm run --dry-run` | Simula sin grabar |
| `docker compose logs -f` | Muestra logs en tiempo real |
| `docker compose build` | Reconstruye la imagen |

---

## Lo que aprendimos

1. **Streamlink es fantástico** para Twitch. Sin navegador, sin dependencias, sin complicaciones.
2. **yt-dlp es la navaja suiza** para YouTube y Kick. La misma herramienta para detectar y grabar.
3. **Los buffers de subprocess** son una fuente infinita de bugs. Siempre usar `DEVNULL`.
4. **Docker facilita todo**. Una vez que funciona local, encapsularlo es trivial.
5. **Un config.json bien pensado** ahorra mucho trabajo.
