# hdfull-downloader

Descargador de películas de **HDFull** (`https://hdfull.sbs`) que automatiza Chromium dentro de Docker, resuelve el reCAPTCHA **manualmente** a través de noVNC y captura el stream real (MPEG-DASH/MP4) usando ffmpeg.

## Cómo funciona

```
Docker (Alpine + Xvfb + openbox + x11vnc + novnc + websockify + chromium + ffmpeg + DrissionPage)
        │
        ├── noVNC  (http://localhost:6080/vnc.html)  ← TÚ resuelves el captcha aquí
        ├── VNC    (localhost:5900)
        └── hdfull_downloader.py
                ├── login en hdfull.sbs
                ├── click en el botón de play del reproductor (powwideo.org)
                ├── espera a que superes el reCAPTCHA manual (default 900s)
                ├── extrae la URL real del vídeo (.mpd / .m3u8 / .mp4 / blob)
                └── descarga con ffmpeg / requests → /app/downloads
```

**Detalle clave:** el reproductor de powvideo no sirve un MP4 directo (el `720p.mp4` es un señuelo que devuelve 404 y el script lo ignora). El vídeo real es **MPEG-DASH** vía `manifest.mpd` de un CDN `pkcdn.org`, cuyos fragmentos (`fragment-*.m4s`) se unen con ffmpeg `-c copy` a un MP4.

## Requisitos

- Docker (Docker Desktop con WSL2 en Windows)
- Nada instalado en Windows: todo corre en el contenedor

## Configuración

1. Crea el archivo `.env` en la raíz del proyecto (ya está gitignoreado, nunca se commitea):

```env
HDFULL_USER=tu_usuario
HDFULL_PASS=tu_contraseña
```

2. Si existe un contenedor antiguo del servicio, elimínalo:

```sh
docker compose down
```

3. Construye la imagen:

```sh
docker compose build
```

## Uso

### Menú interactivo (recomendado)

```sh
./menu.sh
```

```
 1) Descargar película (logs en directo)
 2) Estado / últimos logs
 3) Abrir noVNC (resolver captcha)
 0) Salir
```

- La opción 1 pide la URL de la película (vacío = la de por defecto), construye la imagen la primera vez y lanza el contenedor en primer plano mostrando los logs; al terminar vuelve al menú. Para interrumpirla, `Ctrl+C`.
- La opción 2 muestra las descargas activas y las últimas líneas de `logs/ultimo_run.log`.
- La opción 3 abre el noVNC en el navegador para resolver el captcha.
- Los MP4 se guardan en `downloads/`.

### Comandos directos (alternativa)

```sh
docker compose run --rm --service-ports downloader

# con otra película:
docker compose run --rm --service-ports -e HDFULL_URL="https://hdfull.sbs/pelicula/otra-pelicula" downloader
```

Flujo:

1. El script hace login y carga la página de la película automáticamente.
2. Pulsa el botón de play y se quedará **esperando el captcha** (mensajes cada 30s en los logs).
3. Abre `http://localhost:6080/vnc.html` en el navegador y **resuelve el reCAPTCHA manualmente** sobre la página.
4. El script detecta que el captcha se superó, extrae el stream real y descarga el MP4 a `downloads/`.
5. Al terminar, el contenedor se detiene y se elimina (`--rm`); el MP4 queda en `downloads/`.

> `--service-ports` es necesario para exponer los puertos 6080/5900 de noVNC. La sesión de Chromium persiste en el volumen `profile`, así que el login y el captcha se mantienen entre ejecuciones.

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `HDFULL_USER` | — | Usuario de HDFull (obligatorio) |
| `HDFULL_PASS` | — | Contraseña de HDFull (obligatorio) |
| `HDFULL_URL` | `https://hdfull.sbs/pelicula/the-king-of-kings` | URL de la película (también acepta arg `argv[1]`) |
| `HDFULL_CAPTCHA_TIMEOUT` | `900` | Segundos máximo esperando el captcha manual |
| `HDFULL_OUT` | `/app/downloads` | Directorio de salida |

## Puertos

| Puerto | Servicio | Uso |
|---|---|---|
| `6080` | noVNC (websockify → VNC) | `http://localhost:6080/vnc.html` — resolver captcha |
| `5900` | x11vnc | Cliente VNC convencional |

## Cómo se descarga el vídeo

El script detecta el tipo de stream y elige el método:

| Tipo | Detección | Método |
|---|---|---|
| **DASH** (`.mpd`) | `performance.getEntriesByType('resource')`, HTML del frame, tráfico de red | ffmpeg `-c copy -f mp4` con `-t` (duración del MPD − 6s) |
| **HLS** (`.m3u8`) | Ídem | ffmpeg `-c copy -f mp4` |
| **MP4 directo** | HTML / `<video src>` / red (se ignora el señuelo `720p.mp4` del reproductor) | `requests` con cookies del navegador |
| **blob:** | Hook de `URL.createObjectURL` (sobrevive a la revocación) | Captura vía JS en el frame (fetch + base64 en chunks) |

### Robustez de la extracción

- `performance.getEntriesByType('resource')` se evalúa con `JSON.stringify` y se parsea con `json.loads` (DrissionPage devuelve el string tal cual).
- El buffer de `performance` solo guarda ~150 entradas y puede **evictar el `manifest.mpd`**; si solo aparecen fragmentos (`.m4s`/`.ts`), el script **deriva el manifest** de la base del fragmento (`.../dash/<id>/manifest.mpd`) y lo verifica con una petición HTTP antes de usarlo.
- Los **señuelos** (`720p.mp4` y demás `.mp4` servidos desde el dominio del reproductor `powwideo.org`) se ignoran para no romper el bucle de extracción antes de encontrar el manifest real.
- El archivo de salida siempre se fuerza a **MP4** con `-f mp4` (si se llamara `manifest.mpd`, ffmpeg activaría el muxer DASH y generaría cientos de `chunk-stream*.m4s`).
- El nombre de salida se deriva de la URL de la página (p. ej. `episodio-3.mp4`, `the-king-of-kings.mp4`).

### El problema del "fragmento fantasma"

El último fragmento del MPD (p. ej. el número 612) devuelve 404. Si ffmpeg lo intenta, el MP4 resultante queda corrupto (sin `moov`, no reproducible). Por eso se parsea `mediaPresentationDuration` del MPD y se corta en `duración − 6s` con `-t`.

## Estructura del proyecto

```
hdfull-downloader/
├── .env                  # credenciales (gitignoreado)
├── .gitignore            # .env, __pycache__, downloads/, logs/
├── Dockerfile            # imagen: Alpine + chromium + xvfb + novnc + ffmpeg + openbox + DrissionPage
├── docker-compose.yml    # servicio, puertos, volumen de perfil, montaje ./:/app
├── start.sh              # arranque de Xvfb, openbox, x11vnc, websockify y el script
├── menu.sh               # menú interactivo (URL, logs, estado, noVNC)
├── hdfull_downloader.py  # script principal
├── downloads/            # MP4 descargados (+ un .url con la fuente)
├── logs/                 # logs de las ejecuciones del menú
└── README.md
```

### Componentes del Dockerfile

- `chromium` → navegador automatizado por DrissionPage
- `xvfb` → pantalla virtual `:99` (1400x900x24)
- `openbox` + `xsetroot` → WM necesario para que Chromium pinte la ventana (sin esto, pantalla negra)
- `x11vnc` + `novnc` + `websockify` → acceso VNC en el navegador
- `ffmpeg` → descarga y remux DASH/HLS
- `drissionpage` (venv `/venv`) → control de Chromium (API tipo Selenium, sin WebDriver)

## Troubleshooting

| Síntoma | Causa | Solución |
|---|---|---|
| Pantalla negra en noVNC | Falta WM/`xsetroot` o Chromium minimizado | El `start.sh` ya lanza `openbox` + `xsetroot -solid darkgray` y Chromium con `--start-maximized`; si pasa, re-construye: `docker compose build && docker compose run --rm --service-ports downloader` |
| El captcha "no es visible" | Un popup de anuncio tapa la pestaña real | `close_popups()` cierra pestañas secundarias automáticamente cada minuto |
| `ElementLostError` en el bucle | El frame del reproductor se pierde al navegar | El script re-adquiere el frame con `find_player_frame()` cuando lo detecta |
| MP4 corrupto / sin `moov` | Fragmento fantasma 404 al final del MPD | Ya resuelto con `-t (duración − 6s)` en `download_hls_dash()` |
| Descarga falla con 404 al usar `720p.mp4` | El `720p.mp4` del reproductor es un señuelo | Ya filtrado por `looks_like_decoy()` (dominio del reproductor) |
| Salida como `manifest.mpd` + cientos de `chunk-stream*.m4s` | ffmpeg eligió el muxer DASH por la extensión `.mpd` | Ya resuelto con `-f mp4` forzado |
| No se detecta el manifest aunque haya fragmentos | El buffer de `performance` evictó el `.mpd` | Ya resuelto: el manifest se deriva de la base del fragmento y se verifica |
| `LOGIN FALLIDO` | Credenciales erróneas o petición bloqueada | Revisa `.env`; el script reintenta 4 veces |
| `Tiempo de captcha agotado` | No resolviste el captcha en 900s | Sube `HDFULL_CAPTCHA_TIMEOUT` o resuelve antes |
| Sin URL de vídeo | Stream no cargado aún | Mira `/app/diagnostics.txt` (dump de diagnóstico: perf entries, blobs hook) |

### Diagnóstico

Si una descarga falla, el script escribe `/app/diagnostics.txt` con:
- URL y HTML del frame y de la página principal
- `performance.getEntriesByType('resource')` (ahí aparece el `manifest.mpd`/fragmentos)
- Estado del `<video>` (src, currentSrc, paused)
- Contador del hook de blobs (`window.__blobs`)

## Notas de seguridad

- `.env` contiene credenciales y está en el `.gitignore` raíz (`devjobs/.gitignore`). No lo commitees.
- El contenedor expone VNC sin contraseña (`-nopw`); úsalo solo en local (puertos `localhost`).
- No tocar el proyecto hermano `ffmpeg-yt-dlp`: todo el flujo vive en este directorio.
