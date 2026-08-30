# 🔍 Auditoría vacaciones 22‑30 ago – unified summary

Aquí tienes los hallazgos más críticos de las 9 auditorías diarias, agrupados por proyecto. Cada sección enumera los errores/P0‑P1 más relevantes y la prioridad de corrección.

---

## 1. downloader_telegram
- **Bugs críticos**: `exist1_ok=True` (crash), paginación `limit=100` sin `offset_topic`, `random_id` basado en tiempo.
- **Seguridad**: credenciales cifradas pero `secret.key` junto a config.bin; Docker root por defecto; inyección via nombres de fichero.
- **Rendimiento**: reutilizar sesión Telethon, descargas paralelas `workers=4`, FloodWait error centralizado.
- **Plan prioritario**: P0: typo exist1_ok, filtro temas -100, condición muerta; P1: FloodWaitError + cliente reutilizable; P2: SQLite estado; P3: IA clasificación.

## 2. ffmpeg-yt-dlp
- **Errores Bash**: `return $count` trunca >255, aritmética sin validar decimales, `slice_args` duplicado, ffprobe falla → sube >2 GB, OCR keys duplicadas.
- **Seguridad**: inyección sidecar JSON, contenedor root + bind mount, `apk add`/`pip install` sin pinning.
- **Rendimiento/OCR**: sin `trap EXIT` ni locks → corrupción encodes simultáneos; OCR 2 procesos tesseract por muestra; template matching para publi; búsqueda binaria para precision de segundos.
- **Plan prioritario**: P0: inyección sidecar, `-maxdepth1`, passlogfile único, flock; P1: trap EXIT + timeout ffmpeg + check disco; P1: OCR batch una‑invocación + Otsu; P2: máquina estados SQLite + inotify; P3: template matching, Whisper capítulos.

## 3. hdfull-downloader (I)
- **Bugs**: `url.replace` corrompe query; `globals()["_mpd_dur"]` global persistente; credenciales en claro en `.env`.
- **Seguridad (CRÍTICO)**: `.env` con credenciales reales; VNC sin contraseña expuesto a LAN (`x11vnc -nopw`); `--remote-allow-origins=*`.
- **Rendimiento**: pool httpx/aiohttp + Semaphore(6) = 4‑8× velocidad; sesión requests nunca cerrada.
- **Plan prioritario**: P0: rotar credenciales .env + auditar historial; P0: quitar VNC -nopw y `network_mode:host`; P1: reintentos backoff + `.part` + rename atómico; P1: regex/balanceo llaves playerConfig; P2: quitar globals _mpd_dur; P2: ScraperBase + plugins + tests.

## 4. aula-downloader (II)
- **Bugs**: parsing playerConfig por marcador literal `"}}"script"`; `find('input',{name:'logintoken'})` sin check None; `split('id=')[1]` IndexError; contador global desincronizado; sin reintentos por segmento; concat no verifica nº segmentos; `menu.sh` opción 2 y `*` crash.
- **Seguridad**: heredado de hdfull (.env + VNC); `--remote-allow-origins=*`.
- **Rendimiento**: pool httpx/aiohttp + Semaphore(6) = 4‑8× velocidad; HTML caching del pre‑scan ✅; sesión requests nunca cerrada.
- **Plan prioritario**: P0: quitar `pip install` en runtime; P0: quitar VNC -nopw y `network_mode:host`; P1: regex/balanceo llaves playerConfig; P1: verificar nº segmentos antes de concat; P2: ScraperBase + plugins + tests; P3: IA embeddings catálogo.

## 5. TwitchRecorder
- **Bugs críticos**: doble prefijo streamlink Windows (`recorder.py:353`); `while True` sin try/except mata scheduler; SIGTERM sin manejo; sufijos `__parte2__parte3.mp4`; reencode completo libx264 para concatenar horas.
- **Seguridad**: secretos reales en `.env` locales (Google OAuth, Neon, JWT); JWT en `localStorage` vulnerable a XSS; JWT completo en `user_sessions` en claro; rate limit 100 req/15min agresivo; falta `trust proxy` detrás de Vercel.
- **Rendimiento**: post‑proceso reencodea horas dentro de stop() bloqueando scheduler; cache `is_live` y metadata 60‑120 s; SW: excluir `/api/*` de caché.
- **Plan prioritario**: P0: rotar GOOGLE_CLIENT_SECRET, Neon, JWT_SECRET; P0: sacar build/, coverage/, node_modules/; P0: quitar auto‑admin primer usuario; P1: hashear tokens sesión; P1: hosting WS real; P1: CRA→Vite + TS 5.x; P2: rutas URL reales + sitemap; P2: capa services backend; P3: H265 nocturno, Whisper capítulos.

## 6. Netflix_Anime (frontend)
- **Errores críticos**: `getApiToken.tokwn` sobre función + top‑level await rompe CJS; `search()` devuelve `undefined` siempre; Blob + `URL.createObjectURL` sin `revokeObjectURL` → fuga de memoria; `useEffect []` no reacciona a `filePath`; reducers con cadena if/else y acciones string.
- **Vulnerabilidades**: CSP laxa con `script-src https:` comodín; Disqus tercero sin load diferido; tags duplicados por capitalización; contraste justo en límite; `h2` como logo rompe jerarquía.
- **SEO**: cero `prefers-reduced-motion`; tags duplicados SEO; `h2` logo.
- **Plan prioritario**: P0: parametrizar SQL (SQLi); P0: corregir bypass auth + timing‑safe compare; P0: no devolver telegramToken; P1: fix tokwn/search()/BASEURL env; P1: actualizar Next/Express; P2: suite tests + LHCI + axe; P3: compresión H265/AV1 nocturna; P3: RAG chatbot Workers.

## 7. Netflix_Anime_Api
- **SQLi generalizada**: `OFFSET ${first} LIMIT ${last}`, `WHERE anime = '${anime}'`, `WHERE e.anime = ${siglas}`; `getOne()` sin await devuelve vacío; `pg` singleton sin Pool; `uncaughtException` handler que deja BD desconectada; `createMyStreamFile` sin Range; `writeFileSync` bloquea event loop; `scanFolders` recursión descontrolada; regexes con escape defectuoso; path traversal posible `/media`; `telegramToken` devuelto en JSON; bypass auth `isLocalHost`; body parser sin límite DoS; Socket.IO sin sanitizar XSS; `forEach(async…)` sin esperar; `start` script apunta a `.dist` distinto.
- **Plan prioritario**: P0: parametrizar todas SQL; P0: corregir bypass auth + timing‑safe; P0: no devolver telegramToken; P1: fix doble prefijo streamlink; P1: SIGTERM + scheduler; P1: pg.Pool + quitar uncaughtException; P1: HTTP Range servidor; P1: fix tokwn/search()/BASEURL; P2: limpiar repos + fusionar monorepo; P2: suite tests + CI; P3: H265 nocturno; P3: recomendador pgvector.

## 8. test_githubActions
- **Errores críticos**: send_telegram_workflow.yml caché nunca guarda → dedup rota; clean_news.yml mezcla v3/v4 y checkout v3/v4; scraper_workflow.yml `sleep 3600` semanal; scraper_workflow.yml `git add .` indiscriminado; dashboard_update.yml detección `HEAD~1` + shallow checkout; eixam_scrape.yml `git push` sin pull‑rebase; daily_tips.yml vs docstring contradicción cadencia; tests.yml Python 3.12 vs 3.11.
- **Race conditions**: 6 workflows commitean a master sin `concurrency` en clean_news.yml y eixam_scrape.yml; `noticias_historico.json` escrito por 3 workflows → rebase roto.
- **Seguridad**: token Surge como arg CLI visible en ps aux; sin `permissions:` restrictivos; `curl ollama.com/install.sh | sh` ×3; secrets duplicados 3 nombres; BLOG_TOKEN PAT cross‑repo; .env histórico.
- **Coste Actions**: >13 000 min/mes vs 2 000 free tier. Palancas: bot IA 30 min, cron consolidado matinal, composite action shared.
- **Plan prioritario**: P0: cache/save en send_telegram; P0: concurrency master‑push en clean_news y eixam; P0: notificaciones fallo; P0: permissions mínimas + token Surge env; P1: bot IA 30 min + MAX_EDAD; P1: homogeneizar action versions; P1: quitar sleep 3600 y git add .; P1: composite action shared; P2: actionlint+yamllint+zizmor; P2: workflow_run en vez de HEAD~1.

## 9. pdfmanager
- **Errores críticos**: pip install en runtime (antipatrón); bare `except:` silencia PDFs corruptos; bug UI fusión (vista selección muestra TODOS como COLA); fitz.save sobre archivo in‑place lanza excepción; imágenes→PDF carga TODO en RAM; sobrescritura silenciosa; dividir acepta hasta<desde; `.pdf` case‑sensitive.
- **Seguridad**: parseo PDFs no confiables = entrada hostil a librerías C/C++; eliminación DRM/protecciones aviso; contraseñas por prompt en memoria sin borrado.
- **Rendimiento**: fusión mantiene doc destino en RAM; paralelizar lotes ProcessPoolExecutor (PyMuPDF mejor por procesos); compresión actual solo garbage+deflate; scripts pipe_* duplican ROOT/cd.
- **Plan prioritario**: P0: fix guardado in‑place fitz; P0: fix render vistas selección/cola; P0: requirements.txt pinned, fuera pip‑en‑runtime; P0: quitar bare except; P1: hardening unit User≠root + MemoryMax + NoNewPrivileges; P1: plantilla .service.in + fin de sed sobre repo; P1: non‑root + cap_drop + network none; P2: --batch CLI + confirmaciones; P2: generadores imágenes→PDF; P3: ghostscript 3 niveles + ocrmypdf + RAG local.

## 10. servicios
- **Errores críticos**: unit `User=root` innecesario; `Type=oneshot+RemainAfterExit` sin watchdog; rutas absolutas hardcodeadas parcheadas con `sed -i` sobre repo; typo `API_IS` (debería API_ID); `pipeline_logs.sh` `kill 0` mata propio shell; `pipe_ps.sh` asume nombres exactos; `bootstrap_instalar.sh` muta repo clonado; `instalar_aliases.sh` heredoc sin comillas expande $DEVJOBS.
- **Seguridad**: unit systemd sin hardening (falta `NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp`, `MemoryMax`); secretos en árbol repo + grupos.json versionado; `curl get.docker.com | sh` sin checksum; restart policies oneshot no reinicia nada.
- **Rendimiento**: fusión mantiene doc en RAM; paralelizar lotes ProcessPoolExecutor; compresión actual solo garbage+deflate; scripts pipe_* duplican ROOT/cd.
- **Plan prioritario**: P0: quitar `User=root` + añadir `MemoryMax`, `NoNewPrivileges`; P0: plantilla `.service.in` con `@DEVJOBS@`, fin de `sed` sobre repo; P0: hardening systemd; P1: `shellcheck` en CI + fix typo `API_IS`; P1: non‑root + cap_drop + network none; P2: `--batch` CLI + confirmaciones; P2: generadores imágenes→PDF; P3: ghostscript 3 niveles + ocrmypdf + RAG local.

## 11. blog (Astro + Svelte + Tailwind)
- **Errores críticos**: `<a>` anidado inválido en Card.astro; tests inexistentes (`tests/` no existe); filtro redundante `!draft && draft===false`; 71 MB índice Pagefind duplicado; `pubDate` por defecto mutante; navegación móvil sin `aria-expanded`/`aria-controls` ni cierre Escape; búsqueda teclado `classList.toggle` con dos clases como un token.
- **SEO/a11y**: cero `prefers-reduced-motion`; tags duplicados por capitalización (diluyen SEO); contraste justo en límite; `h2`logo rompe jerarquía.
- **Rendimiento**: imágenes sin pipeline (1,1 MB servidos tal cual); blur placeholder depende de onload inline; logo.png 1,4 MB (debería <20 KB); audio 59 MB (→ Vercel Blob); pagefind 71 MB duplicado; fuente TTF 136 KB → WOFF2 ~40 % menos.
- **Plan prioritario**: P0: fix `<a>` anidado + onclick inútil; P0: añadir linkedin.svg; P0: sanitizar innerHTML RSS (XSS); P0: resolver CORS RSS; P0: quitar .env trackeado; P1: astro:assets Picture + comprimir; P1: aria hamburguesa + Escape + reduced‑motion; P1: views.ts → Vercel Blob/KV; P2: normalizar tags duplicados; P2: Playwright specs + LHCI + axe; P3: RAG chatbot Workers; P3: related content por embeddings.

## 12. porfolio.github.io
- **Errores críticos**: `Math.max(items.length, 5)` debería ser `Math.min` → crash si <5 ítems; `img/linkedin.svg` NO EXISTE; fetch cross‑origin al RSS sin CORS; `script.js` archivo muerto (proxy tercero); fuente fantasma declarada pero nunca cargada; CSS `!important` sistemático + `will‑change` permanentes.
- **Seguridad**: XSS real por `innerHTML` (title/description RSS); proxy CORS HTTP (`http://server.chverma.com:8080`); email en texto plano (harvesting).
- **Rendimiento**: LCP invisible al preload scanner (background‑image inline); `backdrop-filter: blur(20‑25px)` caro en móvil; sin minificación.
- **SEO/a11y**: sin favicon/apple‑touch‑icon/manifest/canonical/robots/sitemap; `og:image` HTTP, dims 620×630 (debería 1200×630 HTTPS); sin `twitter:card`; menú hamburguesa con `aria‑expanded`/`aria‑controls` pero falta trampa de foco, Escape, `prefers-reduced-motion`; estados carga/error colores hardcodeados e inline.
- **Plan prioritario**: P0: fix `Math.max` → `Math.min`; P0: añadir linkedin.svg; P0: sanitizar innerHTML RSS; P0: resolver CORS RSS; P0: quitar .env trackeado; P1: `<a>` anidado + onclick inútil; P1: astro:assets Picture + comprimir; P1: aria hamburguesa + Escape + reduced‑motion; P1: views.ts → Vercel Blob/KV; P2: normalizar tags duplicados; P2: Playwright specs + LHCI + axe; P3: RAG chatbot Workers; P3: favicon/apple‑touch‑icon/canonical/robots/sitemap.

## 13. jorbencas (profile README)
- **Errores críticos**: inyección texto usuario en README sin escapar Markdown/HTML (`<img src=externo>` renderiza); filtro anti‑trolls trivialmente burlable; badges CI apuntan a OTRO repo; muro feedback sin límite crecimiento.
- **Seguridad**: inyección contenido tercero vía issues; mitigable whitelist `[A-Za-z0-9 áéíóúñ.,!?¿-]` + escape Markdown.
- **Plan prioritario**: P0: sanitizar feedback (whitelist + escape markdown); P0: límite muro + script extraído/testeado + checkout v4 + badges correctas; P1: sección ayuda + CONTRIBUTING mínimo; P2: resumen mensual muro como post blog.

## 14. mecano_prueba_web
- **Errores críticos**: repo versionando 1.911 ficheros de build/, coverage/, server/node_modules/; primer usuario = admin automático; `JWT_EXPIRATION` 24h inconsistente con login local 7 días; `express.static` maxAge `'1y'` también a `index.html`; caché usuarios Map sin límite; `SOCKET_URL = window.location.origin` → WS imposible en Vercel; service‑worker cachea `/api/*` con datos personales; IDs letras `Date.now()+Math.random()` colisiones; docs desfasadas; doble infraestructura docker.
- **Seguridad (CRÍTICO)**: secretos reales en `.env` locales (Google OAuth `GOCSPX-…`, Neon `npg_…`, `JWT_SECRET`); JWT en `localStorage` vulnerable XSS; JWT completo en claro en `user_sessions`; rate limit 100 req/15min agresivo + falta `trust proxy`; CSP con `imgSrc https:` y `styleSrc unsafe-inline`; service‑worker cachea respuestas autenticadas.
- **Rendimiento**: bundle ~50 chunks; `source‑map‑explorer` sin presupuesto; niveles JSON importados estáticamente → `import()` dinámico; Recharts+Framer+licode solapados (~100‑200 kB gzip ahorro); Map sin LRU → fuga lenta.
- **Plan prioritario**: P0: rotar GOOGLE_CLIENT_SECRET, Neon, JWT_SECRET; P0: sacar build/, coverage/, node_modules/; P0: quitar auto‑admin primer usuario; P1: hashear tokens sesión; P1: hosting WS real (Render/Railway/PartyKit/Liveblocks); P1: SW excluir `/api/*` de caché; P1: CRA→Vite + TS 5.x; P2: capas services backend; P2: consolidar duplicados; P3: IA coach semanal; P3: notificaciones ntfy/Discord.

## 15. the_simpson_test
- **Errores críticos**: sin `DOWNLOADER_API_TOKEN` app arranca sin avisar; regex acepta URLs sin esquema y con mayúsculas `YouTube.COM`; `datetime.utcnow()` deprecado Python 3.12; `'format': 'bestvideo+bestaudio/best'` fuerza merge ffmpeg innecesario; `nocheckcertificate: True` debilita TLS; falta `noplaylist=True` → playlist dispara extracción masiva (DoS); test dependiente de red real; `pytest` sin path; README desfasada (`token en query string` vs header `X-API-Key`).
- **Seguridad**: token predecible `SHA256(secreto+fecha)` ventana 48 h (acepta ayer); CORS `*` contradictorio; `nocheckcertificate` + `geo_bypass`; keep‑alive expone URL pública; rate limit por IP puede agotarse; cada `/download` hace scraping completo YouTube 10/min × N IPs.
- **Plan prioritario**: P0: token HMAC/aleatorio + `noplaylist`; P0: yt‑dlp fuera event loop + timeouts; P1: keep‑alive 30 min o cron externo + corregir README; P1: mocks en tests; P2: diseñar mini página HTML `/` con formulario prueba token.

---

*Fin de la auditoría unificada. Los informes detallados por día (22‑30 ago) siguen disponibles en `/home/jorge/dev/.informes_vacaciones/`.*