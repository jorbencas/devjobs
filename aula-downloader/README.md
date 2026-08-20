# AULA Downloader

<p align="center">
  <strong>Descarga los vídeos protegidos de <u>Moodle + Vimeo privado</u> sin
  navegador — solo Python y requests, incluso cuando yt-dlp falla con 403.</strong>
</p>

<p align="center">
  <a href="https://github.com/jorbencas/devjobs"><img src="https://img.shields.io/badge/Self--hosted-Docker-blue.svg" alt="Self-hosted: Docker"></a>
  <a href="https://github.com/jorbencas/devjobs"><img src="https://img.shields.io/badge/Python-3.11-blue.svg?logo=python&logoColor=white" alt="Python 3.11"></a>
</p>

Descargador de vídeos de **aula.pmoposiciones.com** (plataforma Moodle con Vimeo privado).

No necesita navegador — usa requests + Python puro para extraer URLs HLS del `playerConfig` de Vimeo.

---

## 📑 Tabla de contenidos

- [¿Por qué existe este proyecto?](#por-qué-existe-este-proyecto)
- [El problema](#el-problema)
- [La solución](#la-solución)
- [Características](#características)
- [Configuración](#configuración)
- [Uso con Docker](#uso-con-docker-recomendado)
- [Cómo funciona](#cómo-funciona)
- [Comparativa: AULA vs HDFull](#comparativa-aula-vs-hdfull)
- [Tecnologías](#tecnologías)
- [Contribuir](#contribuir)
- [Licencia](#licencia)

---

## ¿Por qué existe este proyecto?

Estaba estudiando oposiciones y tenía todos los vídeos de las clases en aula.pmoposiciones.com. El problema es que esos vídeos están embebidos en Vimeo con protección de privacidad: no hay botón de descarga, si intentas acceder directamente te da error 403, y herramientas como yt-dlp no funcionan porque el contenido está protegido.

Necesitaba descargar las clases para poder verlas offline en el móvil, en el tren o cuando no tenía internet. Verlas online una y otra vez consumía muchísimos datos y a veces la conexión fallaba a mitad de clase.

Probé todas las herramientas existentes y ninguna funcionaba. Investigando cómo funciona el reproductor de Vimeo por dentro, descubrí que, aunque el vídeo esté protegido, el HTML del reproductor contiene toda la información necesaria para descargarlo.

---

## El problema

Los vídeos de aula están embebidos en iframes de Vimeo con protección de privacidad. Cuando intentas acceder directamente al player de Vimeo, devuelve error 403. Las herramientas estándar (yt-dlp, wget, curl) no pueden descargarlos porque necesitan:

1. Autenticación en Moodle para acceder a la página
2. Carga del iframe de Vimeo dentro del navegador
3. Ejecución de JavaScript para obtener las URLs reales

## La solución

Un enfoque diferente: en lugar de usar un navegador, extraemos directamente el `playerConfig` del HTML que Vimeo devuelve al player. Este JSON contiene todas las URLs de vídeo (HLS, DASH, MP4) firmadas con tokens temporales.

```
Docker (Python slim + ffmpeg + requests + beautifulsoup4)
        │
        └── aula_downloader_funciona.py
                ├── login en aula.pmoposiciones.com (requests)
                ├── pre-escanea carpetas y cachea HTML
                ├── extrae iframes de Vimeo
                ├── para cada vídeo:
                │   ├── obtiene el player HTML de Vimeo
                │   ├── extrae window.playerConfig del HTML
                │   ├── parsea las URLs HLS/DASH/MP4
                │   ├── descarga segmentos video + audio
                │   ├── concatena segmentos
                │   └── mezcla con ffmpeg → MP4 final
                └── guarda en ./descargas/CURSO/
```

---

## Características

- **Sin navegador** — Solo requests + Python, sin Chromium
- **Audio + Vídeo** — Descarga pistas por separado y mezcla con ffmpeg
- **Logs mejorados** — Progreso en tiempo real, ETA, resumen final
- **Multi-carpeta** — Descarga múltiples carpetas en un solo comando
- **Organización automática** — Vídeos organizados por nombre de curso

---

## Requisitos

- Docker
- Cuenta en aula.pmoposiciones.com

## Configuración

La autenticación se configura con **variables de entorno** (en el servicio `aula_downloader` del `docker-compose.yml` o pasadas con `-e`):

| Variable | Descripción | Default |
|---|---|---|
| `AULA_USER` | Usuario de aula | `REDACTED` |
| `AULA_PASS` | Contraseña de aula | `REDACTED` |

Las descargas salen a `./descargas/`, organizadas por curso (`./descargas/CURSO/`).

## Uso con Docker (Recomendado)

```bash
cd aula-downloader

# Construir imagen
docker compose build

# Descargar una carpeta
docker compose run --rm aula_downloader python3 /app/aula_downloader_funciona.py \
  "https://aula.pmoposiciones.com/mod/folder/view.php?id=4189"

# Descargar múltiples carpetas
docker compose run --rm aula_downloader python3 /app/aula_downloader_funciona.py \
  "https://aula.pmoposiciones.com/mod/folder/view.php?id=4189" \
  "https://aula.pmoposiciones.com/mod/folder/view.php?id=4184" \
  "https://aula.pmoposiciones.com/mod/folder/view.php?id=4194" \
  "https://aula.pmoposiciones.com/mod/folder/view.php?id=4127"

# Menú interactivo
docker compose run --rm aula_downloader
```

---

## Cómo funciona

### 1. Login sin navegador

```python
session = requests.Session()
resp = session.get("https://aula.pmoposiciones.com/login/index.php")
soup = BeautifulSoup(resp.text, 'html.parser')
token = soup.find('input', {'name': 'logintoken'}).get('value', '')

resp = session.post("https://aula.pmoposiciones.com/login/index.php", data={
    'username': username, 'password': password,
    'logintoken': token, 'anchor': ''
})
```

### 2. Pre-escaneo y cache de HTML

```python
# Pre-escanea todas las carpetas y cachea el HTML
folder_html = {}
for folder_url in urls:
    resp = session.get(folder_url)
    folder_html[folder_url] = resp.text
    soup = BeautifulSoup(resp.text, 'html.parser')
    count = len(soup.find_all('iframe', src=re.compile(r'vimeo\.com')))
    total_expected += count

# Luego reutiliza el HTML cacheado (sin requests duplicados)
soup = BeautifulSoup(folder_html[folder_url], 'html.parser')
```

### 3. Obtener playerConfig del HTML

```python
resp = session.get(f"https://player.vimeo.com/video/{video_id}", params={
    'title': '0', 'byline': '0', 'portrait': '0', 'pip': '0', 'dnt': '1'
})

# El playerConfig está en una etiqueta <script>
start_pos = resp.text.find("window.playerConfig = ") + len("window.playerConfig = ")
pos = resp.text.find("}}</script>", start_pos)
config = json.loads(resp.text[start_pos:pos+2])
```

### 4. Descargar segmentos HLS (video + audio)

```python
# Obtener playlist maestra
hls_url = config['request']['files']['hls']['cdns']['akfire_interconnect_quic']['avc_url']
resp = session.get(hls_url)
playlists = parse_master_m3u8(resp.text, hls_url)

# Descargar video por separado
video_init, video_segments = parse_m3u8(resp.text, playlists['video'])
# Descargar audio por separado
audio_init, audio_segments = parse_m3u8(resp.text, playlists['audio'])

# Mezclar con ffmpeg
subprocess.run(['ffmpeg', '-y',
    '-i', 'video_only.mp4',
    '-i', 'audio_only.m4s',
    '-c:v', 'copy', '-c:a', 'copy',
    '-movflags', '+faststart',
    'output.mp4'
])
```

---

## Logs de salida

```
ℹ Pre-escaneando carpetas...
ℹ   4189: 4 vídeos
ℹ   4184: 1 vídeos
ℹ Total esperado: 5 vídeos en 2 carpetas

[1/5] Vídeo 1214033153 (carpeta 1/2, 1/4)
  Vídeo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:05:23
  Audio ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:03:53
✓ [1/5] 01_LEY_ORGANICA...mp4 (100 MB) en 9m 28s (180 KB/s)
ℹ Quedan 4 vídeos | Total: 9m 28s | ETA: ~37m 52s

╭──────── Resumen ────────╮
│ Vídeos: 5/5 descargados │
│ Tamaño total: 1.2 GB    │
│ Tiempo total: 47m 12s   │
│ Velocidad media: 442 KB/s│
╰─────────────────────────╯
```

---

## Estructura de salida

```
descargas/
├── PSI-ESP_CLASES/
│   ├── 01_LEY_ORGANICA_12004_...mp4
│   ├── 02_LEY_ORGANICA_12004_...mp4
│   ├── 03_LEY_ORGANICA_12004_...mp4
│   └── 04_LEY_ORGANICA_12004_...mp4
├── PSI-ESP_TUTORIAS_GRUPALES/
│   └── 01_TUTORIA_PSICO_220726.mp4
└── ...
```

---

## Comparativa: AULA vs HDFull

| Aspecto | HDFull | AULA |
|---------|--------|------|
| Protección | reCAPTCHA manual | Vimeo privado (403) |
| Descarga | ffmpeg captura stream del navegador | Python descarga segmentos HLS |
| Navegador | Sí (Chromium + noVNC) | No (solo requests) |
| Audio | Incluido en stream | Pista separada, mezcla con ffmpeg |
| Complejidad | Resolución manual de captcha | Extracción de playerConfig + m3u8 |

HDFull usa el navegador para reproducir el vídeo y capturar el stream. AULA extrae las URLs directamente del HTML sin necesidad de navegador, pero requiere más pasos de procesamiento (parseo de m3u8, descarga de segmentos de video y audio por separado, concatenación y mezcla con ffmpeg).

---

## Simplificación del código

El script fue optimizado eliminando:

- **Código muerto**: ~200 líneas de una segunda ruta de código duplicada
- **Imports locales redundantes**: `import re` dentro de funciones cuando ya estaba importado globalmente
- **Requests duplicados**: Pre-escaneo que cachea HTML y reutiliza en el loop principal
- **Headers repetidos**: Constantes `HEADERS_AULA` y `HEADERS_VIMEO` en lugar de duplicar en cada petición

Resultado: de 720 a 516 líneas (-28%) con las mismas funcionalidades.

---

## Tecnologías

- **Python 3.11** — Lenguaje principal
- **requests** — HTTP client para login y descargas
- **BeautifulSoup4** — Parsing HTML de Moodle
- **Rich** — Terminal con colores, barras de progreso y tiempo
- **InquirerPy** — Menú interactivo
- **ffmpeg** — Mezcla de pistas de audio y vídeo
- **Docker** — Contenedor ligero (python:3.11-slim + ffmpeg)

## Archivos

- `aula_downloader_funciona.py` — Script principal
- `requirements.txt` — Dependencias
- `Dockerfile` — Configuración Docker (python:3.11-slim + ffmpeg)
- `docker-compose.yml` — Orquestación Docker
- `start.sh` — Script de inicio
- `menu.sh` — Menú interactivo
- `descargas/` — Salida organizada por curso

## Contribuir

Los *issues* y *pull requests* son bienvenidos. Si tu plataforma Moodle usa otro
proveedor de vídeo, abre un *issue* con el HTML del reproductor para adaptarlo.
