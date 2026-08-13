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
docker compose run --rm uploader python /app/subir_videos.py --setup
```

Te pedirá teléfono + código. Crea `uploader.session` (solo se hace una vez).

### 2. Descubrir tus grupos

```bash
docker compose run --rm uploader python /app/subir_videos.py --list-chats
```

Muestra `ID / tipo / nombre` de tus chats. Copia los IDs (los grupos suelen ser negativos) o los `@usernames`.

### 3. Rellenar `grupos.json`

```json
{
    "grupos": [
        "@mi_grupo_publico",
        -1001234567890
    ]
}
```

Acepta IDs numéricos (con `-` para grupos/canales) y `@usernames`.

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
| Listar chats | `python /app/subir_videos.py --list-chats` |
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