# ✅ PENDIENTES — Pipeline "Grabar → Comprimir → Subir a Telegram"

Guía de lo que falta para que la automatización quede completamente funcional.
Cada paso requiere intervención manual (teléfono/código de Telegram o `sudo`).

---

## ⏱️ Mínimo imprescindible para probar esta noche

Solo **2 pasos**, ambos necesitan tu teléfono (código de Telegram):

1. **Paso 1** — Crear la sesión del uploader (`--setup`).
2. **Pasos 2 + 3** — Descubrir los IDs (`--list-chats`) y rellenar `grupos.json`.

Después: **Paso 4** `docker compose up -d uploader`. Ya sube.

**Prueba rápida:** copia un MP4 con extensión `_compressed.mp4` a
`/home/jorge/dev/devjobs/Videos/comprimidos/` → en ~60 s se sube a los grupos.

**Para probar NO es necesario:** el **Paso 5 (systemd)** — solo hace falta para
que arranque solo al encender el PC; no bloquea la prueba de esta noche.

---

## Estado actual

| Pieza | Estado | Nota |
|-------|--------|------|
| Credenciales (`config.bin` + `secret.key`) | ✅ Listas | API ID/Hash cifrados ya configurados |
| Imagen Docker `downloader_telegram` | ✅ Construida | `docker compose build` hecho |
| Servicio `twitchrecorder` | ✅ Corriendo | Grabación de directos activa |
| Servicio `monitor` (`ffmpeg_monitor`) | ✅ Corriendo | Compresión a 720p activa |
| Script uploader (`subir_videos.py`) | ✅ Listo | Funciona, falta solo la sesión |
| Config TwitchRecorder | ✅ Listo | `channels`, `start_time: 21:30`, `copy_to_test: true` |
| Sesión del uploader (`uploader.session`) | ❌ Pendiente | Requiere `--setup` (teléfono + código) |
| `grupos.json` con IDs reales | ❌ Pendiente | Tiene placeholders |
| Servicio `uploader` | ❌ Pendiente | No está arrancado |
| systemd (auto-arranque al boot) | ❌ Pendiente | No habilitado, requiere `sudo` |

---

## Paso 1 — Crear la sesión del uploader

Genera `uploader.session` (se hace UNA SOLA vez; pide teléfono + código de Telegram).

```bash
cd /home/jorge/dev/devjobs/downloader_telegram
docker compose run --rm uploader python /app/subir_videos.py --setup
```

> Debe aparecer `✓ Sesión uploader creada`. Si no, revisa credenciales o reintenta.
> La sesión queda en `downloader_telegram/uploader.session` (no se commitea).

---

## Paso 2 — Descubrir los IDs de tus grupos

Lista tus chats/grupos para anotar sus IDs:

```bash
docker compose run --rm uploader python /app/subir_videos.py --list-chats
```

Salida (tabla): `ID  Tipo  Nombre`. Los **grupos** suelen tener **ID negativo** (`-100...`).

---

## Paso 3 — Rellenar `grupos.json`

Edita `grupos.json` (`/home/jorge/dev/devjobs/downloader_telegram/grupos.json`)
sustituyendo los placeholders por tus grupos reales:

```json
{
    "grupos": [
        "@mi_grupo_publico",
        -1001234567890
    ]
}
```

Aceptan IDs numéricos (con `-` para grupos/canales) y `@usernames`. Debe ser una lista no vacía.

---

## Paso 4 — Arrancar el uploader

```bash
cd /home/jorge/dev/devjobs/downloader_telegram
docker compose up -d uploader
docker compose logs -f uploader     # comprobar que vigila y no da errores
```

El servicio corre con `restart: unless-stopped`. Vigila `/comprimidos` cada 60 s
y sube los `*_compressed.mp4` a los grupos de `grupos.json`.

---

## Paso 5 — Habilitar el auto-arranque al encender el PC

Habilita el servicio systemd (requiere `sudo`):

```bash
sudo systemctl enable /home/jorge/dev/devjobs/servicios/twitch-stream-pipeline.service
```

Comprobación opcional:

```bash
sudo systemctl start   twitch-stream-pipeline.service
sudo systemctl status  twitch-stream-pipeline.service
```

Con esto, al encender el PC se levantan solos los 3 servicios del pipeline.

---

## Verificación final (checklist)

- [ ] `ls downloader_telegram/uploader.session` → existe
- [ ] `grupos.json` → contiene los IDs/@usuarios reales (no los placeholders)
- [ ] `docker ps` → aparecen `twitchrecorder`, `ffmpeg_monitor` y `telegram-uploader` arriba
- [ ] `systemctl is-enabled twitch-stream-pipeline.service` → responde `enabled`

---

## Rutas útiles

| Concepto | Ruta |
|----------|------|
| Grabaciones terminadas | `/home/jorge/dev/devjobs/test_videos/test/` (`*_completed.mp4`) |
| Videos comprimidos | `/home/jorge/dev/devjobs/Videos/comprimidos/` (`*_compressed.mp4`) |
| Grupos destino | `downloader_telegram/grupos.json` |
| Sesión del uploader | `downloader_telegram/uploader.session` |
| Servicio systemd | `servicios/twitch-stream-pipeline.service` |

> Documentación completa: `README.md` (raíz), `README_UPLOADER.md`, `README_MONITOR.md`, `docker_help.txt`.