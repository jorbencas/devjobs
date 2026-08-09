# HDFull Downloader

Descargador automatizado de películas de **HDFull** con Docker + noVNC. Detecta automáticamente dominios activos, resuelve reCAPTCHA **manualmente** a través de noVNC, y captura el stream real (MPEG-DASH/HLS/MP4) usando ffmpeg.

---

## ¿Por qué existe este proyecto?

Siempre me gustó HDFull para ver películas y series, pero hay un problema gordo: no puedo descargar nada para ver offline. El reproductor web tiene un captcha que impide cualquier automatización, los dominios cambian cada pocos meses, y Cloudflare protege todo con muros que las herramientas normales no pueden atravesar.

Quería ver películas en el móvil cuando viajaba en tren o avión, donde no hay internet. Las plataformas como Netflix permiten descargar, pero HDFull no tiene esa función. Y aunque pudiera descargar, el captcha y las protecciones lo hacen imposible con herramientas automáticas.

La solución tenía que ser un híbrido: que el ordenador hiciera todo el trabajo pesado (detectar dominios, lanzar navegador, capturar el stream), pero que yo solo tuviera que resolver el captcha manualmente desde el móvil o el navegador.

---

## El problema

HDFull protege sus streams con reCAPTCHA, Cloudflare y dominios que cambian periódicamente. El stream real está fragmentado en DASH o HLS, y el reproductor devuelve URLs falsas que terminan en error 404. Además, el captcha impide cualquier automatización directa.

## La solución

Un contenedor Docker que:
1. Detecta automáticamente los dominios activos desde `dominioshdfull.com`
2. Lanza Chromium con anti-detección de automatización
3. Expone noVNC en el navegador para que resuelvas el captcha manualmente
4. Captura el stream real (DASH/HLS/MP4/blob) con ffmpeg
5. Maneja automáticamente los señuelos y fragmentos fantasma

---

## Arquitectura

```
Docker (Alpine + Xvfb + openbox + x11vnc + novnc + chromium + ffmpeg + DrissionPage)
        │
        ├── noVNC  (http://localhost:6080/vnc.html)  ← TÚ resuelves el captcha
        ├── VNC    (localhost:5900)
        └── hdfull_downloader.py
                ├── obtiene dominios activos de dominioshdfull.com
                ├── prueba dominios hasta encontrar uno accesible
                ├── login en hdfull
                ├── click en el botón de play
                ├── inyecta hooks anti-detección (navigator.webdriver, plugins, etc.)
                ├── inyecta hook de blob URLs (URL.createObjectURL)
                ├── escucha tráfico de red (performance.getEntriesByType)
                ├── espera a que superes el reCAPTCHA (timeout configurable, default 900s)
                ├── extrae la URL real del vídeo (DASH/HLS/MP4/blob)
                └── descarga con ffmpeg → /app/downloads
```

---

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
docker compose build --no-cache
```

> IMPORTANTE: Usa `--no-cache` para asegurar que se instalan todas las dependencias (ffmpeg, chromium, etc.). Reconstruye la imagen tras cambios en el Dockerfile.

---

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

- La opción 1 pide la URL de la película, construye la imagen la primera vez y lanza el contenedor en primer plano mostrando los logs; al terminar vuelve al menú. Para interrumpirla, `Ctrl+C`.
- La opción 2 muestra las descargas activas y las últimas líneas de `logs/ultimo_run.log`.
- La opción 3 abre el noVNC en el navegador para resolver el captcha.
- Los MP4 se guardan en `downloads/`.

### Comandos directos (alternativa)

```sh
# URL como argumento (recomendado)
docker compose run --rm hdfull_downloader "https://hdfull.sbs/pelicula/otra-pelicula"

# URL como variable de entorno (fallback)
docker compose run --rm -e HDFULL_URL="https://hdfull.sbs/pelicula/otra-pelicula" hdfull_downloader

# Con perfil limpio (borrar cookies/sesión)
docker compose run --rm hdfull_downloader --clear-profile "https://hdfull.sbs/pelicula/otra-pelicula"
```

### Flujo de uso

1. **Configura credenciales** en `.env`
2. **Lanza el contenedor** con la URL de la película
3. **Abre noVNC** en `http://localhost:6080/vnc.html` y resuelve el captcha manualmente
4. **Descarga automática** — una vez superado el captcha, el script detecta la URL real del stream y descarga con ffmpeg

---

## Detección automática de dominios

Los dominios de HDFull cambian frecuentemente. El script obtiene la lista actualizada desde `dominioshdfull.com` en cada ejecución:

```python
HDFULL_DOMAINS = []

def fetch_hdfull_domains():
    """Obtiene la lista de dominios desde dominioshdfull.com."""
    global HDFULL_DOMAINS
    r = requests.get("https://dominioshdfull.com/", timeout=10,
                     headers={"User-Agent": "Mozilla/5.0"})
    domains = re.findall(r'(?:https?://)?((?:www\d?\.)?hdfull\.[a-z]+)', r.text, re.I)
    HDFULL_DOMAINS = list(dict.fromkeys(domains))
```

Flujo:
1. Descarga la página `dominioshdfull.com` y extrae los dominios `hdfull.*`
2. Prueba el dominio de la URL original
3. Si no responde, prueba los dominios alternativos hasta encontrar uno accesible
4. Reemplaza el dominio en la URL y continúa

---

## Detección de streams

El reproductor de HDFull usa diferentes métodos para servir el vídeo. El script detecta cada tipo y usa la estrategia de descarga adecuada:

| Tipo | Cómo lo detecta | Cómo lo descarga |
|------|-----------------|------------------|
| **DASH** (`.mpd`) | `performance.getEntriesByType('resource')` + regex en HTML | `ffmpeg -c copy -f mp4` con parseo de duración MPD |
| **HLS** (`.m3u8`) | Ídem | `ffmpeg -c copy -f mp4` |
| **MP4 directo** | HTML / `<video src>` / red (se ignora el señuelo `720p.mp4`) | `requests` con cookies del navegador |
| **blob:** | Hook de `URL.createObjectURL` → fetch + base64 en chunks | JS en el frame del navegador |

### Robustez de la extracción

- `performance.getEntriesByType('resource')` se evalúa con `JSON.stringify` y se parsea con `json.loads` (DrissionPage devuelve el string tal cual).
- El buffer de `performance` solo guarda ~150 entradas y puede **evictar el `manifest.mpd`**; si solo aparecen fragmentos (`.m4s`/`.ts`), el script **deriva el manifest** de la base del fragmento (`.../dash/<id>/manifest.mpd`) y lo verifica con una petición HTTP antes de usarlo.
- Los **señuelos** (`720p.mp4` y demás `.mp4` servidos desde el dominio del reproductor `powwideo.org`) se ignoran para no romper el bucle de extracción antes de encontrar el manifest real.
- El archivo de salida siempre se fuerza a **MP4** con `-f mp4` (si se llamara `manifest.mpd`, ffmpeg activaría el muxer DASH y generaría cientos de `chunk-stream*.m4s`).
- El nombre de salida se deriva de la URL de la página (p. ej. `episodio-3.mp4`, `otra-pelicula.mp4`).

---

## Cómo maneja los problemas

### Señuelos filtrados

El reproductor powwideo sirve URLs falsas como `720p.mp4` que devuelven 404. El script mantiene una lista de hosts señuelo:

```python
DECOY_HOSTS = ("powwideo.org", "powvideo.org")

def looks_like_decoy(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(h in host for h in DECOY_HOSTS)
```

### El problema del "fragmento fantasma"

El último fragmento del MPD (p. ej. el número 612) devuelve 404. Si ffmpeg lo intenta, el MP4 resultante queda corrupto (sin `moov`, no reproducible). Por eso se parsea `mediaPresentationDuration` del MPD y se corta en `duración − 6s` con `-t`:

```python
m = re.search(r'mediaPresentationDuration="PT(\d+(?:\.\d+)?)S"', xml)
if m:
    dur = float(m.group(1))
    cmd += ["-t", str(max(1, dur - 6))]
```

### Buffer de performance

Si el navegador evicta el manifest del buffer de performance, el script deriva la URL base del fragmento y comprueba si el manifest existe:

```python
mu = u[:u.rfind("/") + 1] + "manifest.mpd"
rsp = requests.get(mu, timeout=12, headers={"Referer": "https://powwideo.org/"})
ok = rsp.status_code == 200 and b"<MPD" in rsp.content[:2000]
```

### Anti-detección de automatización

Chromium se lanza con scripts CDP que ocultan las señales de automatización:

```javascript
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['es-ES', 'es']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
```

### Hook de blob URLs

Cuando el reproductor usa `URL.createObjectURL` para crear blobs, el script captura cada blob y lo almacena para descarga posterior:

```javascript
var orig = URL.createObjectURL;
URL.createObjectURL = function(obj){
    var u = orig.call(this, obj);
    window.__blobs.push({url: u, blob: obj});
    return u;
};
```

---

## Cloudflare Challenge

HDFull usa Cloudflare para proteger su sitio. Cuando el script detecta un Cloudflare challenge ("Just a moment..."):

1. Espera hasta 900 segundos a que lo resuelvas en noVNC
2. **No recarga la página** — si la recarga, Cloudflare genera un captcha nuevo
3. Comprueba el título de la página cada 5 segundos
4. Cuando el título cambia de "Just a moment...", continúa automáticamente

> Si ayer funcionaba y hoy no, puede ser que Cloudflare esté bloqueando más agresivamente. Prueba con `--clear-profile` para empezar con una sesión limpia.

---

## Persistencia de sesión

El volumen `profile` almacena el perfil de Chromium. Esto significa que:
- El login se mantiene entre ejecuciones
- Si ya resolviste el captcha antes, no vuelves a necesitarlo
- Los cookies y localStorage se preservan

### Borrar perfil (limpiar cookies/sesión)

Si necesitas limpiar las credenciales guardadas o empezar desde cero, usa el flag `--clear-profile`:

```bash
# Con docker compose directamente (URL como argumento)
docker compose run --rm hdfull_downloader --clear-profile "https://hdfull.sbs/pelicula/swimming-pool"

# Con docker compose y URL por variable de entorno
docker compose run --rm -e HDFULL_URL="https://hdfull.sbs/pelicula/swimming-pool" hdfull_downloader --clear-profile

# Con el menú interactivo
./menu.sh --clear-profile
```

Esto borra el contenido completo del volumen `profile` antes de arrancar Chromium. La próxima ejecución pedirá login de nuevo en HDFull.

---

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `HDFULL_USER` | — | Usuario de HDFull (obligatorio) |
| `HDFULL_PASS` | — | Contraseña de HDFull (obligatorio) |
| `HDFULL_URL` | — | URL de la película (fallback si no se pasa como argumento) |
| `HDFULL_CAPTCHA_TIMEOUT` | `900` | Segundos máximo esperando el captcha manual |
| `HDFULL_OUT` | `/app/downloads` | Directorio de salida |

La URL se puede pasar de dos formas:
- **Argumento positional** (recomendado): `hdfull_downloader "https://hdfull.sbs/pelicula/..."`
- **Variable de entorno** (fallback): `HDFULL_URL="https://hdfull.sbs/pelicula/..." hdfull_downloader`

## Puertos

| Puerto | Servicio | Uso |
|---|---|---|
| `6080` | noVNC (websockify → VNC) | `http://localhost:6080/vnc.html` — resolver captcha |
| `5900` | x11vnc | Cliente VNC convencional |

> Con `network_mode: host`, los puertos están directamente en localhost sin necesidad de mapeo.

---

## Comandos rápidos

```bash
# Construir imagen (IMPORTANTE: usar --no-cache tras cambios)
docker compose build --no-cache

# Ejecutar (URL como argumento)
docker compose run --rm hdfull_downloader "https://hdfull.sbs/pelicula/swimming-pool"

# Ejecutar (URL como variable de entorno)
docker compose run --rm -e HDFULL_URL="https://hdfull.sbs/pelicula/swimming-pool" hdfull_downloader

# Ejecutar con perfil limpio (borrar cookies/sesión)
docker compose run --rm hdfull_downloader --clear-profile "https://hdfull.sbs/pelicula/swimming-pool"

# Menú interactivo
./menu.sh

# Menú interactivo con perfil limpio
./menu.sh --clear-profile

# Ver logs
docker compose logs -f

# Parar
docker compose down
```

---

## Logs

Los logs muestran el progreso en tiempo real:

```
  ℹ Dominios obtenidos: 12 (www3.hdfull.one, hdfull.love, hdfull.help, hdfull.cv, hdfull.monster...)
  ℹ Dominio hdfull.sbs no accesible, buscando alternativo...
  ℹ Dominio alternativo encontrado: www3.hdfull.one (HTTP 403)
  ℹ Nueva URL: https://www3.hdfull.one/pelicula/swimming-pool
  ℹ URL objetivo: https://www3.hdfull.one/pelicula/swimming-pool
  ✓ LOGIN OK
  ℹ Página: https://www3.hdfull.one/pelicula/swimming-pool | Swimming Pool
  ℹ Reproductor: https://powwideo.org/embed/swimming-pool
  ✓ Play pulsado; esperando captcha...
  ℹ PENDIENTE: Cloudflare challenge activo (0s / 120s) - resuélvelo en http://localhost:6080/vnc.html
  ℹ PENDIENTE: Cloudflare challenge activo (10s / 120s) - resuélvelo en http://localhost:6080/vnc.html
  ✓ Captcha superado -> navegando a la página de video
  ℹ DASH detectado, descargando con ffmpeg: https://.../manifest.mpd
  ℹ   duración MPD: 5421.3s (cortando en 5415.3s para evitar fragmento fantasma)
  ℹ   ffmpeg 0:45 / 90:21
  ✓ LISTO: /app/downloads/swimming-pool.mp4 (1847MB)
  ✓ PROCESO COMPLETO: /app/downloads/swimming-pool.mp4 (1847MB)
```

---

## Estructura del proyecto

```
hdfull-downloader/
├── .env                  # credenciales (gitignoreado)
├── .gitignore            # .env, __pycache__, downloads/, logs/
├── Dockerfile            # imagen: Alpine + chromium + xvfb + novnc + ffmpeg + openbox + DrissionPage
├── docker-compose.yml    # servicio con network_mode: host, volumen de perfil, montaje ./:/app
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

---

## Troubleshooting

| Síntoma | Causa | Solución |
|---|---|---|
| Pantalla negra en noVNC | Falta WM/`xsetroot` o Chromium minimizado | El `start.sh` ya lanza `openbox` + `xsetroot -solid darkgray` y Chromium con `--start-maximized`; si pasa, re-construye: `docker compose build --no-cache && docker compose run --rm hdfull_downloader` |
| El captcha "no es visible" | Un popup de anuncio tapa la pestaña real | `close_popups()` cierra pestañas secundarias automáticamente cada minuto |
| `ElementLostError` en el bucle | El frame del reproductor se pierde al navegar | El script re-adquiere el frame con `find_player_frame()` cuando lo detecta |
| MP4 corrupto / sin `moov` | Fragmento fantasma 404 al final del MPD | Ya resuelto con `-t (duración − 6s)` en `download_hls_dash()` |
| Descarga falla con 404 al usar `720p.mp4` | El `720p.mp4` del reproductor es un señuelo | Ya filtrado por `looks_like_decoy()` (dominio del reproductor) |
| Salida como `manifest.mpd` + cientos de `chunk-stream*.m4s` | ffmpeg eligió el muxer DASH por la extensión `.mpd` | Ya resuelto con `-f mp4` forzado |
| No se detecta el manifest aunque haya fragmentos | El buffer de `performance` evictó el `.mpd` | Ya resuelto: el manifest se deriva de la base del fragmento y se verifica |
| `LOGIN FALLIDO` | Credenciales erróneas o petición bloqueada | Revisa `.env`; el script reintenta 4 veces |
| `Tiempo de captcha agotado` | No resolviste el captcha en 900s | Sube `HDFULL_CAPTCHA_TIMEOUT` o resuelve antes |
| `Cloudflare challenge no resuelto` | Cloudflare está bloqueando agresivamente | Prueba `--clear-profile` para sesión limpia; resuelve el captcha en noVNC sin que el script recargue la página |
| Sin URL de vídeo | Stream no cargado aún | Mira `/app/diagnostics.txt` (dump de diagnóstico: perf entries, blobs hook) |
| Dominio no accesible | Los dominios hdfull cambian frecuentemente | El script obtiene dominios automáticos de dominioshdfull.com y prueba hasta encontrar uno accesible |

### Diagnóstico

Si una descarga falla, el script escribe `/app/diagnostics.txt` con:
- URL y HTML del frame y de la página principal
- `performance.getEntriesByType('resource')` (ahí aparece el `manifest.mpd`/fragmentos)
- Estado del `<video>` (src, currentSrc, paused)
- Contador del hook de blobs (`window.__blobs`)

---

## Notas de seguridad

- `.env` contiene credenciales y está en el `.gitignore` raíz (`devjobs/.gitignore`). No lo commitees.
- El contenedor expone VNC sin contraseña (`-nopw`); úsalo solo en local (puertos `localhost`).
- No tocar el proyecto hermano `ffmpeg-yt-dlp`: todo el flujo vive en este directorio.

---

## Tecnologías

- **Python 3** — Lenguaje principal
- **DrissionPage** — Control de Chromium sin WebDriver (anti-detección)
- **ffmpeg** — Descarga y remux de streams DASH/HLS
- **Docker** — Contenedor con Alpine + Chromium + Xvfb + noVNC
- **requests** — HTTP client para login y detección de dominios
- **Rich** — Terminal con colores y logs

## Archivos

- `hdfull_downloader.py` — Script principal (676 líneas)
- `Dockerfile` — Imagen Docker completa
- `docker-compose.yml` — Orquestación con network_mode: host
- `start.sh` — Arranque de Xvfb, openbox, x11vnc, websockify
- `menu.sh` — Menú interactivo
- `requirements.txt` — Dependencias Python
- `.env` — Credenciales (gitignoreado)
