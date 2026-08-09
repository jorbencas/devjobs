# TODO — devjobs

## [descargador_capacitivo] Extractor de blobs y multimedia genérico

**Objetivo:** Crear herramienta CLI genérica que abra cualquier web en Chromium, detecte contenido multimedia (videos, audios, streams) y lo descargue localmente.

---

### Stack tecnológico

| Componente | Tecnología | Por qué |
|---|---|---|
| Navegador headless | **Playwright** (Python) | Ya usado en aula-downloader, mejor soporte async, más estable que DrissionPage |
| Descarga HLS/DASH | **ffmpeg** | Ya usado en hdfull-downloader, estándar para streams |
| HTTP requests | **httpx** | Async, mejor que requests para streams grandes |
| CLI | **click** | Argumentos, opciones, help automático |
| Terminal UI | **rich** | Progress bars, paneles, logs coloridos (ya usado en hdfull) |
| WebSocket (CDP) | **playwright._impl._cdp** | Comunicación directa con Chromium para hooks JS |
| YAML config | **pyyaml** | Perfiles de sitio (selectores, cookies, headers) |

** Dependencias del sistema:**
- Python 3.10+
- ffmpeg instalado
- Chromium (lo instala Playwright)

---

### Arquitectura modular

```
descargador_capacitivo/
├── main.py              # CLI入口 + orchestrator
├── browser.py           # Lanzamiento Chromium, stealth, hooks
├── detector.py          # Detección de media (DOM, regex, perf API, network)
├── extractor.py         # Extracción de blobs y streams
├── downloader.py        # Descarga HTTP, blob, HLS/DASH
├── config.py            # Perfiles de sitio, defaults
├── utils.py             # Helpers (naming, progress, logging)
├── profiles/            # YAML por sitio
│   ├── _default.yaml
│   ├── aula.yaml
│   ├── hdfull.yaml
│   └── generic.yaml
└── README.md
```

---

### Pasos de implementación

#### FASE 1 — Core engine (browser + hooks)

1. **`browser.py`** — Lanzar Chromium con Playwright
   - Headless opcional (`--visible` para depurar)
   - User-agent realista
   - Viewport 1920x1080
   - Directorio de perfil persistente (reutilizar cookies/sesión)
   - Timeout configurable

2. **Stealth** — Inyectar anti-detección antes de cada navegación
   - `navigator.webdriver = undefined`
   - `navigator.plugins` fake
   - `navigator.languages = ['es-ES', 'es']`
   - `hardwareConcurrency = 8`
   - `deviceMemory = 8`
   - Fonts canvas fingerprint noise
   - WebGL vendor/renderer spoofing
   - CDP `Page.addScriptToEvaluateOnNewDocument`

3. **Blob hook** — JS inyectado al cargar la página
   - Enganchar `URL.createObjectURL` → almacenar `{url, blob, timestamp}`
   - Enganchar `URL.revokeObjectURL` → limpiar del registro
   - Límite de 50 blobs en memoria (FIFO)
   - Exponer `window.__blobs` para acceso desde Python

4. **Network listener** — Interceptar tráfico de red
   - `page.route("**/*", handler)` o `page.on("response")`
   - Filtrar por Content-Type: `video/*`, `audio/*`, `application/dash+xml`, `application/x-mpegURL`
   - Filtrar por extensión: `.mp4`, `.m3u8`, `.mpd`, `.webm`, `.mp3`, `.ogg`, `.m4s`, `.ts`
   - Almacenar URLs + headers + cookies de la petición original

#### FASE 2 — Detector de media

5. **DOM scan** — Buscar en el árbol HTML
   - `<video src="...">`, `<video><source src="...">`
   - `<audio src="...">`, `<audio><source src="...">`
   - `<iframe src="...">` (recursivo si es mismo dominio)
   - `<embed>`, `<object data="...">`
   - Links directos: `<a href="*.mp4">`, `<a href="*.mp3">`

6. **Regex scan** — Buscar URLs en el HTML crudo
   - `https?://[^\s"'<>]+\.(mp4|m3u8|mpd|webm|mp3|ogg|m4s|ts)(\?[^\s"'<>]*)?`
   - `file\s*[:=]\s*["']([^"']+\.(mp4|m3u8|mpd)[^"']*)["']`
   - `src\s*[:=]\s*["']([^"']+\.(mp4|m3u8|mpd)[^"']*)["']`
   - `source\s*[:=]\s*["']([^"']+\.(mp4|m3u8|mpd)[^"']*)["']`

7. **Performance API scan** — URLs que no están en el DOM
   - `performance.getEntriesByType('resource')`
   - Filtrar por initiatorType: `xmlhttprequest`, `fetch`, `media`
   - Filtrar por extensión de media

8. **Blob scan** — Capturar blobs del hook
   - `window.__blobs` → último blob válido
   - Re-crear URL con `URL.createObjectURL(blob)` si fue revocado
   - Descargar vía `fetch(blobUrl)` → `arrayBuffer()` → base64 chunks

9. **Iframe recursion** — Buscar en iframes embebidos
   - Listar todos los `<iframe>`
   - Para cada uno: DOM scan + regex scan + blob scan
   - Límite de profundidad (max 3 niveles)
   - Solo mismos dominio o whiteliste

#### FASE 3 — Downloader

10. **HTTP directo** — Para `.mp4`, `.mp3`, `.webm` directos
    - Descarga stream con progreso (`httpx` o `requests`)
    - Reanudable con `Range` headers
    - Cookies y headers de la sesión del navegador
    - Timeout configurable

11. **Blob download** — Para URLs `blob:`
    - JS `fetch(blobUrl)` → `arrayBuffer()` → chunks base64
    - Enviar chunks a Python vía CDP
    - Decodificar y guardar
    - Manejar blobs grandes (>100MB) con streaming

12. **HLS download** — Para `.m3u8`
    - ffmpeg `-i <url> -c copy -movflags +faststart output.mp4`
    - Headers: `Referer`, `Origin`, cookies
    - Progress parsing de output ffmpeg
    - Reintentos en fragmentos fallidos

13. **DASH download** — Para `.mpd`
    - ffmpeg `-i <url> -c copy output.mp4`
    - Parsear duración del XML para progress
    - Cortar último fragmento si está corrupto

14. **Reintentos** — Lógica de retry
    - Max 3 reintentos por archivo
    - Backoff exponencial
    - Si falla HTTP, intentar vía navegador (page.download)

#### FASE 4 — CLI y UX

15. **`main.py`** — Interfaz CLI con click
    ```
    descargador <URL> [opciones]
      --output, -o     Directorio de salida (default: ./downloads)
      --visible        Mostrar navegador (no headless)
      --profile        Perfil de sitio (yaml)
      --timeout        Timeout en segundos (default: 120)
      --cookie-file    Archivo con cookies (JSON/Netscape)
      --user-agent     User-agent personalizado
      --proxy          Proxy (http://host:port)
      --format         Formato forzado (mp4, mp3, webm)
      --name           Nombre del archivo de salida
      --list           Solo listar URLs encontradas (no descargar)
      --verbose, -v    Output detallado
    ```

16. **Progress bars** — Rich para descargas
    - Barra de progreso con MB descargados / total
    - ETA estimado
    - Velocidad actual (MB/s)
    - Colores por tipo de media

17. **Logging** — Rich console
    - `[green]✓[/green]` Éxito
    - `[red]✗[/red]` Error
    - `[yellow]⚠[/yellow]` Warning
    - `[blue]ℹ[/blue]` Info
    - Modo verbose: mostrar URLs encontradas, tiempo de cada paso

18. **Output naming** — Nombres inteligentes
    - Por defecto: `<titulo_pagina>_<timestamp>.mp4`
    - Si `--name`: usar ese nombre
    - Evitar sobreescritura: añadir `_1`, `_2`...
    - Mantener extensión correcta según tipo detectado

#### FASE 5 — Perfiles de sitio

19. **Sistema de perfiles YAML**
    ```yaml
    name: aula
    selectors:
      video: "video"
      iframe: "iframe[src*='embed']"
      play_button: ".play-button"
      login_form: "#login-form"
    patterns:
      media: ["*.mp4", "*.m3u8"]
    headers:
      Referer: "https://aula.com/"
    auth:
      type: form
      url: "/login"
      fields:
        username: "#email"
        password: "#password"
    ```

20. **Perfil `_default.yaml`** — Fallback genérico
    - Seletores CSS amplios
    - Todos los patrones de media
    - Sin autenticación

21. **Perfiles específicos** — `aula.yaml`, `hdfull.yaml`, etc.
    - Selectores específicos del reproductor
    - Headers necesarios
    - Lógica de login si aplica
    - Selectores de play/pause

#### FASE 6 — Features avanzadas

22. **Autenticación**
    - Login vía formulario (playwright fill + click)
    - Cookies importadas (JSON o Netscape format)
    - Token Bearer vía header

23. **Proxy support**
    - HTTP/HTTPS/SOCKS5
    - Proxy con autenticación
    - Rotación de proxy (opcional)

24. **Batch mode**
    - Lista de URLs en archivo (una por línea)
    - Procesar en paralelo (max 3 browsers)
    - Resume: saltar descargas completadas

25. **Detección automática de tipo**
    - Si es `.mp4` directo → HTTP download
    - Si es `.m3u8` → HLS con ffmpeg
    - Si es `.mpd` → DASH con ffmpeg
    - Si es `blob:` → JS fetch + base64
    - Si es iframe → recursión

26. **Manejo de errores**
    - Cloudflare challenge → pausar + mostrar URL para resolver manual
    - CAPTCHA → pausar + mostrar instrucciones
    - Rate limiting → backoff + reintentar
    - Video privado/auth required → sugerir cookies/login

#### FASE 7 — Manejo de publicidad y anti-detección

27. **Bloqueo de anuncios a nivel de red** (más efectivo)
    - Interceptar peticiones con `page.route("**/*", handler)`
    - Bloquear dominios de ads: `doubleclick.net`, `googlesyndication.com`, `ads.`, `pubmatic.com`, `moatads.com`, `adsafeprotected.com`, `spotx.`, `vindicosuite.com`
    - Bloquear por Content-Type: `text/html` de frame publicitario
    - Bloquear por patrón de URL: `/adserver/`, `/vast/`, `/vpaid/`, `/preroll`
    - Resultado: el player carga el vídeo directo sin esperar ads

28. **Extracción vía API directa** (el más fiable para Mediaset y similares)
    - Muchas webs grandes tienen una API interna que devuelve la URL del vídeo sin pasar por el player
    - Ejemplo Mediaset: `feed.entertainment.tv.theplatform.eu/f/PR1GhC/mediatek?byId=<ID>`
    - Detectar patrones de API en el JS del player o en las peticiones de red
    - Si se encuentra la API → saltarse player, ads y CAPTCHA completamente
    - Patrones comunes a buscar:
      - `feed.theplatform.eu`, `api.*.com/video`, `/manifest?`
      - `playerConfig`, `videoUrl`, `streamUrl`, `mediaUrl` en el JS
      - `window.__INITIAL_STATE__` o `window.__NEXT_DATA__` con datos del vídeo

29. **Filtro de manifest HLS/DASH** (evitar ads en streams)
    - HLS: los ads vienen en `#EXT-X-DISCONTINUITY` o como sub-m3u8 referenciados
    - DASH: los ads están en `<Period>` separados del contenido real
    - Solución ffmpeg HLS: mapear solo tracks de contenido
      ```bash
      ffmpeg -i master.m3u8 -map 0:v:0 -map 0:a:0 -c copy output.mp4
      ```
    - Solución ffmpeg DASH: filtrar period del contenido
      ```bash
      ffmpeg -i manifest.mpd -c copy -movflags +faststart output.mp4
      ```
    - Si el m3u8 maestro tiene múltiples quality levels, seleccionar el mejor

30. **Anti-detección de adblocker**
    - Algunas webs detectan si bloqueas ads y muestran pantalla de error
    - Inyectar JS que neutralice la detección:
      ```javascript
      window.__adsLoaded = true;
      window.__adBlockDetected = false;
      // Neutralizar createElement para ads
      document.createElement = (function(orig) {
          return function(tag) {
              if (tag === 'div' && arguments[1] === 'ad') {
                  return { style: {}, appendChild: ()=>{}, innerHTML: '' };
              }
              return orig.apply(this, arguments);
          };
      })(document.createElement);
      ```
    - Fake de elementos DOM que el player espera para confirmar que ads cargaron
    - Neutralizar `MutationObserver` que vigila la presencia de nodos de ads

31. **Flujo completo para webs con publicidad**
    ```
    1. Abrir página
    2. Inyectar STEALTH + anti-adblock + BLOB_HOOK
    3. Configurar route() para bloquear ads en red
    4. Esperar a que cargue el player
    5. Buscar API directa (patrones feed.theplatform.eu, api.mediaset, etc.)
    6. Si hay API → descargar directo (sin player ni ads)
    7. Si no hay API → escanear DOM + perf API + network listener
    8. Identificar .m3u8/.mpd del CONTENIDO (no el de ads)
    9. Descargar con ffmpeg filtrando segmentos de ads
    ```

32. **Detección de tipo de publicidad**
    - **VAST** (Video Ad Serving Template): anuncio lineal antes del vídeo → bloquear petición
    - **VMAP** (Video Multi-ad Playlist): múltiples insertos → filtrar del manifest
    - **VPAID** (Video Player-Ad Interface): ads interactivos → bloquear JS del ad unit
    - Detectar patrones en URLs: `/vast?`, `/vmap?`, `/vpaid/`, `/preroll?`, `/midroll?`

33. **Bypass de pantallas de "Ad blocker detected"**
    - Muchas webs muestran modal bloqueando el contenido si detectan adblock
    - Estrategias:
      - Ocultar el modal vía JS: `document.querySelector('.adblock-modal')?.remove()`
      - Neutralizar la clase CSS que bloquea el scroll: `document.body.style.overflow = 'auto'`
      - Eliminar overlays: `document.querySelectorAll('[class*="overlay"]').forEach(e => e.remove())`
      - Si el check es por XMLHttpRequest abortado → falsificar respuesta OK
    - Detectar patrones comunes: `.adb-overlay`, `.adblock-warning`, `[data-adblock]`, `#adblock-modal`

34. **Gestión de popups y pestañas nuevas**
    - Los players suelen abrir pestañas/pops al hacer clic en play
    - Playwright: `page.on("popup")` → cerrar automáticamente
    - O bloquear apertura: `await page.route("**/*", ...)` para URLs de ads
    - Cerrar pestañas que no sean la principal antes de buscar media
    - Pattern: si `tab_id != main_tab_id` → cerrar

35. **Manejo de CAPTCHA en ads**
    - Algunos players requieren resolver CAPTCHA antes de mostrar el vídeo
    - Estrategias:
      - Si `--visible`: pausar y mostrar instrucciones al usuario
      - Si headless: intentar con servicio de resolución (2captcha, anticaptcha)
      - Detectar si el CAPTCHA es del contenido o del ad → si es del ad, bloquear la petición del ad
    - Patrones de CAPTCHA: `recaptcha`, `hcaptcha`, `captcha`, `challenge`, `verify`

36. **Whitelist de dominios de contenido vs ads**
    - Mantener lista de dominios conocidos de video hosting legítimo:
      ```
      # CDNs de vídeo
      *.cloudfront.net (con paths de media)
      *.akamaihd.net
      *.edgesuite.net
      *.cdn*.brightcove.com
      *.llnw.net
      *.bitgravity.com

      # Plataformas legítimas
      *.youtube.com/embed
      *.vimeo.com
      *.dailymotion.com
      *.twitch.tv

      # APIs de Mediaset/RTVE/etc
      feed.entertainment.tv.theplatform.eu
      api.rtve.es
      ```
    - Si la URL pertenece a un dominio de contenido → descargar sin dudar
    - Si es dominio desconocido → analizar antes de descargar

37. **Anti-fingerprinting avanzado**
    - Canvas fingerprint: añadir noise al canvas
    - WebGL: spoofear vendor y renderer
    - AudioContext: distorsionar ligeramente el output
    - Font detection:Fonts: ocultar fonts del sistema que deliten el SO
    - Screen: spoofear resolución y color depth
    - Timezone: forzar zona horaria consistente (la del usuario real)
    - Playwright: `page.emulate({ timezoneId, locale, geolocation })`

38. **Prevención de memory leaks**
    - Los hooks de blobs acumulan objetos en memoria
    - Límite estricto: max 50 blobs, FIFO
    - `URL.revokeObjectURL()` después de descargar cada blob
    - Cerrar frames/iframes que ya no se necesiten
    - `page.close()` al terminar, no solo `page.quit()`

39. **Logging y diagnóstico**
    - Guardar screenshot automático si falla la extracción
    - Guardar HTML del player para depuración
    - Exportar HAR de las peticiones de red (playwright `page.route_from_har`)
    - Log de todas las URLs de media encontradas (para análisis posterior)
    - Flag `--debug` que active todo lo anterior

---

### Componentes reutilizables de `hdfull-downloader`

| Línea | Componente | Reutilizable |
|---|---|---|
| 137-150 | `BLOB_HOOK` | ✅ Directamente |
| 128-135 | `STEALTH` | ✅ Adaptar |
| 235-259 | `find_media_urls()` | ✅ Adaptar |
| 273-285 | `fresh_blob_url()` | ✅ Directamente |
| 327-367 | `download_hls_dash()` | ✅ Adaptar |
| 399-429 | `download_blob()` | ✅ Adaptar |
| 496 | `page.listen.start()` | ✅ Adaptar |
| 556 | Performance API scan | ✅ Directamente |

### NO reutilizable (específico de hdfull)

- `fetch_hdfull_domains()` / `find_working_domain()` → dominios rotativos
- `login()` → formulario hdfull específico
- `find_player_frame()` → selectores hdfull
- `close_popups()` → popups hdfull
- Lógica de CAPTCHA hdfull

---

### Archivos de referencia

- `hdfull-downloader/hdfull_downloader.py` — 676 líneas, blob hook + download
- `aula-downloader/` — base Playwright existente
- `ffmpeg-yt-dlp/test_video/midu.sh` — ffmpeg patterns, progreso

---

**Estado:** Pendiente
**Dificultad:** Alta
**Tiempo estimado:** 2-3 semanas
