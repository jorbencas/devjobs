# ✅ PENDIENTES — Pipeline "Grabar → Comprimir → Subir a Telegram"

Guía de lo que falta para que la automatización quede completamente funcional.
Cada paso requiere intervención manual (teléfono/código de Telegram o `sudo`).

---

## ⏱️ Mínimo imprescindible para probar esta noche

✅ **Ya está todo hecho**: sesión creada, `grupos.json` con los 36 grupos reales,
y el uploader corriendo. Falta **solo el Paso 5 (systemd)** para que arranque solo
al encender el PC (no bloquea la prueba).

**Prueba rápida:** copia un MP4 con extensión `_compressed.mp4` a
`/home/jorge/dev/devjobs/Videos/comprimidos/` → en ~60 s se sube a los grupos.

---

## Estado actual

| Pieza | Estado | Nota |
|-------|--------|------|
| Credenciales (`config.bin` + `secret.key`) | ✅ Listas | API ID/Hash cifrados ya configurados |
| Imagen Docker `downloader_telegram` | ✅ Construida | `docker compose build` hecho |
| Servicio `twitchrecorder` | ✅ Corriendo | Grabación de directos activa |
| Servicio `monitor` (`ffmpeg_monitor`) | ✅ Corriendo | Compresión a 720p activa |
| Config TwitchRecorder | ✅ Listo | `channels`, `start_time: 21:30`, `copy_to_test: true` |
| Sesión del uploader (`uploader.session`) | ✅ Autenticada | Loguin hecho, se reutiliza sin pedir credenciales |
| `grupos.json` con IDs reales | ✅ Listo | 32 canales + aliases + `default` "Jorge videos" |
| Ruteo por keyword (uploader) | ✅ Listo | Coincidencia flexible + alias + fallback |
| Servicio `uploader` | ✅ Corriendo | Vigila `/comprimidos` cada 60 s |
| systemd (auto-arranque al boot) | ✅ Habilitado | `enabled` + `active (exited)`, los 3 servicios arrancan al boot |

---

## Paso 1 — Crear la sesión del uploader

Genera `uploader.session` (se hace UNA SOLA vez; pide teléfono + código de Telegram).
Este paso es **interactivo, solo puede hacerlo tú** (la máquina no introduce el código).

```bash
cd /home/jorge/dev/devjobs/downloader_telegram
touch uploader.session   # crear el archivo vacío si no existe (si no, Docker lo monta como directorio y la sesión falla)
docker compose run --rm uploader python /app/subir_videos.py --setup
```

> Debe aparecer `✓ Sesión uploader creada`. Si no, revisa credenciales o reintenta.
> Un `.session` existe ≠ está autenticado: debe pasar por `--setup`. Si `--list-chats` pide teléfono, corre el login. Verifica con `--list-chats` que NO te pida teléfono.
> Recuerda: si `uploader.session` no existe, el `volumes:` lo monta como directorio vacío → error `unable to open database file`. Solución: `touch uploader.session` antes del `--setup`.
> La sesión queda en `downloader_telegram/uploader.session` (no se commitea).

---

## Paso 2 — Descubrir los IDs de tus grupos

Lista tus chats/grupos para anotar sus IDs:

```bash
docker compose run --rm uploader python /app/subir_videos.py --list-chats
```

Salida (tabla): `ID  Tipo  Nombre  Carpeta  ¿Creado por ti?`. Los **grupos/canales** suelen tener **ID negativo** (`-100...`).

Filtros opcionales:

```bash
docker compose run --rm uploader python /app/subir_videos.py --list-chats --folder "sendo"   # filtra por nombre de chat (o archivado/principal)
docker compose run --rm uploader python /app/subir_videos.py --list-chats --creados          # solo lo que creaste tú
```

---

## Paso 3 — Rellenar `grupos.json`

Edita `grupos.json` (`/home/jorge/dev/devjobs/downloader_telegram/grupos.json`)
sustituyendo los placeholders por tus grupos reales (**formato de ruteo por keyword**):

```json
{
    "default": -100999888777,
    "grupos": [
        { "nombre": "prueba", "id": -100111222333 },
        { "nombre": "sendo", "id": -100444555666 }
    ]
}
```

- `default`: grupo al que se sube si ninguna keyword coincide (recomendado ponerlo).
- `grupos`: cada entrada `{ "nombre", "id" }` — el `nombre` es la keyword que debe aparecer en el título del directo para enrutarlo ahí; el `id` es el chat ID negativo del grupo (de `--list-chats`).

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

- [x] `ls downloader_telegram/uploader.session` → existe y autenticada
- [x] `grupos.json` → contiene `default` + 36 grupos reales (no placeholders)
- [x] `docker ps` → `twitchrecorder`, `ffmpeg_monitor` y `telegram-uploader` arriba
- [x] `systemctl is-enabled twitch-stream-pipeline.service` → responde `enabled`

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