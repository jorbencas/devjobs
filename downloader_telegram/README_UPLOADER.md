# README — Uploader a Telegram (`subir_videos.py`)

Última pieza del pipeline **"Grabar → Comprimir → Subir a Telegram"**. Vigila la carpeta de vídeos comprimidos y los sube a los grupos de Telegram configurados.

---

## Qué hace

1. Vigila `/home/jorge/dev/devjobs/Videos/comprimidos` (donde `monitor_folder.sh` deja los `*_compressed.mp4`).
2. Por cada `*_compressed.mp4` no enviado, lo sube a **todos** los grupos de `grupos.json`.
3. Si un archivo supera **2 GB** (límite de cuenta de Telegram), lo **divide en partes** con ffmpeg (`-c copy`, sin recompresión) y sube cada parte.
4. Registra los enviados en `enviados.json` y elimina el archivo local.

Reutiliza las credenciales cifradas del proyecto (`config.bin` + `secret.key`), pero usa su **propia sesión** (`uploader.session`) para no entrar en conflicto con la sesión del menú interactivo (`ultimate_session.session`). Así puedes correr el menú de descargas y el uploader **a la vez**.

---

## Cambiar credenciales o carpetas (sin tocar el código)

Todo es configurable con **variables de entorno** (en el bloque `environment` del servicio `uploader`):

| Variable | Qué cambia | Default |
|---|---|---|
| `UPLOADER_API_ID` | Cambia credenciales **sin** tocar `config.bin` | `config.bin` |
| `UPLOADER_API_HASH` | Ídem (deben ir las dos juntas) | `config.bin` |
| `UPLOADER_INTERVALO` | Segundos entre pasadas | `60` |
| `UPLOADER_SESION` | Ruta de la sesión Telethon | `uploader.session` |
| `UPLOADER_GRUPOS` | Ruta de `grupos.json` | `grupos.json` |
| `UPLOADER_ENVIADOS` | Ruta del registro de enviados | `enviados.json` |
| `UPLOADER_PARTES` | Carpeta de partes temporales | `partes/` |
| `UPLOADER_CONFIG` / `UPLOADER_KEY` | Rutas de credenciales cifradas | `config.bin` / `secret.key` |
| `UPLOADER_CARPETAS` | Carpetas a vigilar (separadas por `:`) | `/comprimidos` |

> También puedes crear/borrar un contenedor distinto cambiando `container_name:` en el `docker-compose.yml` (p. ej. un segundo `uploader` que vigile otra carpeta, con su propia `enviados.json`).

---

## Configuración inicial (importante — hacer ANTES del viaje)

### 1. Sesión del uploader (una sola vez)

```bash
cd /home/jorge/dev/devjobs/downloader_telegram
docker compose build
touch uploader.session   # si no existe, Docker lo montaría como un directorio y la sesión fallaría
docker compose run --rm uploader python /app/subir_videos.py --setup
```

Te pedirá teléfono + código. Crea `uploader.session` (solo se hace una vez).

> **Ojo 1 — verificación automática de sesión:** el script comprueba ANTES de cada uso si la sesión ya está autenticada. Si lo está, **no vuelve a pedir credenciales** (reutiliza `uploader.session`). Si no lo está:
> - `--list-chats` / autoupload: **no piden login**; avisan y salen indicando que ejecutes `--setup`.
> - `--setup`: es el único modo que inicia login (teléfono + código), y solo lo pedirá si la sesión no está autenticada. Si ya lo está, lo dice y sale sin preguntar.
>
> **Ojo 2 — archivo vs sesión autenticada:** un archivo `.session` por sí solo NO vale. Tiene que haber pasado por `--setup` (login con teléfono + código). Este paso **solo puede hacerlo tú** (es interactivo).
>
> **Ojo 3 — `uploader.session` inexistente:** si el archivo no existe, el `volumes:` de `docker-compose.yml` lo monta como un **directorio vacío** y Telethon falla con `unable to open database file`. Crea siempre el archivo vacío con `touch uploader.session` ANTES del primer `--setup`.

### 2. Descubrir tus grupos

```bash
docker compose run --rm uploader python /app/subir_videos.py --list-chats
```

Muestra `ID / Tipo / Nombre / Carpeta / ¿Creado por ti?` de tus chats. Copia los IDs (los grupos y canales suelen ser negativos) o los `@usernames`.

Opciones de filtro para reducir la lista:

- La columna **Carpeta** solo etiqueta: `Principal`, `Archivado`, o `#N` para carpetas personalizadas (Telethon no expone el título real de estas carpeta).
- `--folder <texto>` filtra por **nombre del chat** (subcadena) o por la etiqueta de carpeta (`archivado` / `principal`).

```bash
# Solo los chats cuyo nombre contenga "sendo" (o los de la carpeta Archivado)
docker compose run --rm uploader python /app/subir_videos.py --list-chats --folder "sendo"
docker compose run --rm uploader python /app/subir_videos.py --list-chats --folder archivado

# Solo los chats/grupos/canales que creaste tú (columna ¿Creado por ti? = sí)
docker compose run --rm uploader python /app/subir_videos.py --list-chats --creados

# Ambos a la vez
docker compose run --rm uploader python /app/subir_videos.py --list-chats --folder "sendo" --creados
```

### 3. Rellenar `grupos.json`

```json
{
    "default": -100999888777,
    "grupos": [
        { "nombre": "prueba", "id": -100111222333 },
        { "nombre": "sendo", "id": -100444555666 }
    ]
}
```

- **`default`**: grupo al que se sube cuando ningún `nombre` coincide con la keyword del directo. Si lo omites y no hay coincidencia, el vídeo no se sube.
- **`grupos`**: lista de `{ "nombre", "id" }`. El `nombre` es la keyword que debe aparecer en el título/descripción del directo para enrutar el vídeo a ese grupo; el `id` es el chat ID numérico (negativo) del grupo, obtenido con `--list-chats`.

### Ruteo automático por keyword

1. `TwitchRecorder` lee el **título del directo** con yt-dlp y lo incrusta en el nombre del archivo: `sendosama_2026-08-13_20-15-00_KW_prueba.mp4`.
2. El monitor comprime y conserva el nombre → `..._KW_prueba_compressed.mp4`.
3. El uploader extrae la keyword (`prueba`) y sube el vídeo **solo al grupo cuyo `nombre` coincida**.
4. Si ninguna coincidencia → se sube al **`default`**.

**Coincidencia flexible (tolerante a cómo escriba sendo el título):**
- No exige el nombre exacto del grupo. Compara normalizado (sin mayúsculas/tildes, espacios colapsados) y acepta:
  - **Substring** del nombre completo: `devil may cryyy` → grupo `"devil may cry"`.
  - **Palabra significativa** del nombre (≥4 letras): `resident evily` → grupo `"resident evil"`; `sendo sama` → `"sendo"`.
- Solo falla (y va al `default`) cuando el nombre del grupo no aparece en absoluto en el título (p. ej. un typo de letras como `residnet evil`).

**Aliases (una misma palabra puede apuntar al mismo canal):** varias entradas de `grupos` pueden compartir `id`. Ejemplos configurados:
- `sendokai` y `jojo` → mismo canal.
- `solo leveling` y `hazbin hotel` → mismo canal.
- `db kai` y `db daima` → mismo canal.
- `avatar` y `korra` → mismo canal.

Si un título coincide con varias keywords del mismo canal, **se deduplica** (sube una sola vez a ese canal).

Si el directo no tiene título/keyword, se aplica el mismo fallback al `default`.

---

## Ponerlo en marcha (modo automático)

```bash
docker compose up -d uploader
```

El servicio corre con `restart: unless-stopped`, vigila `/comprimidos` cada 60 s y sube a los grupos.

### Modos del script

| Modo | Comando |
|---|---|
| Setup de sesión | `python /app/subir_videos.py --setup` |
| Listar chats | `python /app/subir_videos.py --list-chats [--folder <carpeta>] [--creados]` |
| Auto-upload (bucle) | `python /app/subir_videos.py --intervalo 60 /comprimidos` |
| Una pasada y salir | `python /app/subir_videos.py --once /comprimidos` |

---

## Docker y dos instancias sin conflicto

El `docker-compose.yml` define dos servicios:

| Servicio | Sesión | Uso |
|---|---|---|
| `telegram` | `ultimate_session.session` | Menú interactivo (descargas manuales) |
| `uploader` | `uploader.session` | Subida automática del pipeline |

Cada uno monta su **propio** archivo de sesión, por lo que pueden ejecutarse simultáneamente sin pisarse.

---

## Límite de tamaño

Telegram permite archivos de hasta **~2 GB** por cuenta. `subir_videos.py` comprueba cada archivo antes de subir:
- `< 2 GB` → sube directo.
- `> 2 GB` → divide con `ffmpeg -f segment -segment_time 5400 -c copy` en partes de 1,5 h, y sube cada parte por separado.

Las partes temporales van a `partes/` (montado como volumen). El original marcado se elimina tras subir todas las partes.

---

## Manejo de errores

El script es robusto ante fallos de configuración o del entorno:

- **Faltan archivos** (`config.bin`, `grupos.json`): termina con un mensaje claro indicando qué configurar.
- **Credenciales corruptas**: avisa y sugiere reconﬁgurar (o usar `UPLOADER_API_ID`/`UPLOADER_API_HASH`).
- **`grupos.json` mal formado/vacío**: avisa para que lo revises.
- **Sesión invalidada/vencida**: muestra un aviso con el comando `--setup` para regenerarla.
- **Un grupo falla**: solo se marca el vídeo como enviado si llegó a todos los grupos; si falla alguno, se reintenta en la siguiente pasada.
- **`enviados.json` corrupto**: lo reinicia vacío sin romper el bucle.

---

## Arquitectura del pipeline

```
TwitchRecorder → test/*_completed.mp4 → monitor_folder.sh → comprimidos/*_compressed.mp4 → [este servicio] → grupos de Telegram
```

> Documentación completa del pipeline en el `README.md` de la raíz de `devjobs` y en `docker_help.txt` (secciones *PIPELINE* y *AUTO-ARRANQUE*).