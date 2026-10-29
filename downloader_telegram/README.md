# Telegram Ultimate Toolbox

<p align="center">
  <strong>Descargador masivo, clonador, vigilante y <u>subidor automático</u> de
  Telegram — con CLI consolidado, descarga de media (vídeo, foto, sticker, storys,
  transcribe voice) y pipeline de subida con ruteo por keyword.</strong>
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://github.com/jorbencas/devjobs"><img src="https://img.shields.io/badge/Self--hosted-Docker-blue.svg" alt="Self-hosted: Docker"></a>
  <a href="https://github.com/jorbencas/devjobs"><img src="https://img.shields.io/badge/Python-3.11-blue.svg?logo=python&logoColor=white" alt="Python 3.11"></a>
</p>

## Características

| Función | Detalle |
|---|---|
| 📥 Descarga masiva | Interactiva, enlace único, rango de IDs, canal completo, búsqueda, `enlaces.txt` |
| 🎨 Todos los media | vídeo, foto, audio, voice, documento, sticker, gif, encuesta, contacto y ubicación |
| 🌟 Storys y voice | Descarga storys activas y transcribe voice messages con whisper |
| 🖥️ CLI consolidada | Menú guiado, entradas blindadas, auditoría y export/import de backup |
| 👁️ Vigilante | Alertas en múltiples canales, reenvío a destinos y descarga de media |
| 📤 Uploader automático | Vigila `comprimidos/`, divide >2 GB, rutea por keyword a temas/grupos |

---

## 📑 Tabla de contenidos

- [Requisitos](#requisitos)
- [Despliegue](#despliegue)
- [Bot API interactivo](#bot-api-interactivo-telegram_botpy)
- [Uploader a Telegram](#uploader-a-telegram-subir_videospy)
- [CLI consolidada (`tg_toolbox`)](#cli-consolidada-tg_toolbox)
- [Estructura](#estructura)
- [Seguridad](#seguridad)
- [Dependencias](#dependencias)
- [Blog](#blog)

---

Descargador masivo, clonador, vigilante de contenido y **subidor automático de vídeos a grupos** en Telegram.

## Requisitos

- Docker
- Cuenta de Telegram con API ID/Hash (crear en https://my.telegram.org/apps)

## Despliegue

```bash
git clone https://github.com/jorbencas/devjobs.git
cd devjobs/downloader_telegram
cp .env.example .env
# Editar .env con tus credenciales de Telegram
docker compose build
docker compose up
```

### 🐳 Arrancar cada contenedor

Los servicios del `docker-compose.yml` son `telegram` (CLI), `uploader` (daemon) y `telegram_bot` (Bot API). Puedes arrancarlos por separado:

```bash
cd downloader_telegram

# CLI interactivo (contenedor telegram-downloader)
docker compose up -d telegram

# Daemon uploader (contenedor telegram-uploader-sendo)
docker compose up -d uploader

# Bot API (contenedor telegram-bot)
docker compose up -d telegram_bot

# Todos a la vez
docker compose up -d
```

Comandos útiles por contenedor:

```bash
# Estado
docker ps --filter name=telegram-downloader
docker ps --filter name=telegram-uploader-sendo
docker ps --filter name=telegram-bot

# Logs
docker compose logs -f telegram
docker compose logs -f uploader
docker compose logs -f telegram_bot

# Parar / reiniciar
docker compose stop telegram
docker compose restart uploader
docker compose stop telegram_bot

# Parar y eliminar todos los contenedores del compose
docker compose down
```

> El servicio `telegram` se queda vivo (`tail -f /dev/null`) para poder entrar con `docker exec` (ver comando `tg_menu` más abajo). El `uploader` y el `telegram_bot` se levantan como daemons con `restart: unless-stopped`.

### 🔑 Credenciales de un equipo nuevo (token propio, sin conflictos)

Si este proyecto se despliega en un **equipo/máquina nuevo**, genera credenciales propias. No reutilices el `.env`, las sesiones ni el `config.bin` de otro equipo: dos instancias con el mismo token de bot se pisan y una sesión copiada reutiliza el login de otra cuenta.

| Credencial | Dónde se genera | Contenedor que la usa | Se guarda en |
|---|---|---|---|
| `BOT_TOKEN` | Telegram → **@BotFather** | `telegram_bot` | `.env` |
| `API_ID` + `API_HASH` | https://my.telegram.org/apps | `telegram` / `uploader` (Telethon) | `config/config.bin` |
| Sesión `.session` | Login con teléfono + código + 2FA | `uploader` / CLI | `sessions/*.session` |

#### 1. Bot propio (`BOT_TOKEN`)

1. En Telegram, abre **@BotFather** y ejecuta `/newbot`.
2. Elige nombre y usuario terminado en `bot` (p. ej. `mi_equipo_devjobs_bot`).
3. Guarda el token **solo** en este proyecto:

   ```bash
   cd downloader_telegram
   printf '\nBOT_TOKEN=%s\n' '123456789:AA...' >> .env
   ```

   La variable que lee `docker-compose.yml` es **`BOT_TOKEN`**; `TELEGRAM_BOT_TOKEN` no se usa en el bot.
4. Arranca el bot y añádelo al grupo como **administrador** (para crear temas):

   ```bash
   docker compose up -d telegram_bot
   docker compose logs -f telegram_bot
   ```

> **Conflictos:** un `BOT_TOKEN` debe tener una sola instancia de `telegram-bot` haciendo polling. Si otro equipo arranca el mismo token, los mensajes solo llegan a uno. Si se filtra: @BotFather → `/mybots` → tu bot → **API Token** → **Revoke**, actualiza el `.env` y reinicia.

#### 2. API ID/Hash del uploader (`config.bin`)

El uploader **no usa `BOT_TOKEN`**: sube con una cuenta de Telegram vía Telethon. Para un equipo nuevo:

1. Entra en https://my.telegram.org/apps con la cuenta de Telegram de ese equipo y crea una app.
2. Guarda `api_id` y `api_hash` cifrados con Fernet en `config/config.bin` (la clave va en `config/secret.key`). Desde `downloader_telegram/`:

   ```bash
   read -rp "API ID: " API_ID
   read -rsp "API HASH: " API_HASH; echo
   docker compose run --rm -T -e API_ID -e API_HASH telegram python -c '
   import json, os
   from pathlib import Path
   from cryptography.fernet import Fernet
   d = Path("config"); d.mkdir(exist_ok=True)
   k = d / "secret.key"
   key = k.read_bytes() if k.exists() else Fernet.generate_key()
   if not k.exists():
       k.write_bytes(key)
   data = json.dumps({"api_id": os.environ["API_ID"], "api_hash": os.environ["API_HASH"]}).encode()
   (d / "config.bin").write_bytes(Fernet(key).encrypt(data))
   print("OK: config/config.bin + config/secret.key")
   '
   ```

3. Crea la sesión del uploader (login interactivo, solo una vez):

   ```bash
   touch sessions/uploader.session
   bash ../servicios/pipe_setup.sh
   ```

4. Comprueba credenciales, `grupos.json` y sesión sin subir nada:

   ```bash
   bash ../servicios/pipe_verificar.sh
   ```

> **No mezcles equipos:** `config.bin`, `secret.key` y `*.session` son el login de una cuenta concreta. Cada equipo debe generar los suyos. Si migras **la misma cuenta** a otra máquina, copia los ficheros y usa `bash ../servicios/pipe_setup.sh --reset` si la sesión no valida.
>
> El CLI (`telegram`) usa `sessions/tg_toolbox.session` y el daemon usa `sessions/uploader.session`: son sesiones distintas para poder correr a la vez sin conflictos.

### Generar sesión portátil

```bash
docker compose run --rm telegram python -c "
import asyncio
from telethon import TelegramClient
import os, sys
sys.path.insert(0, 'app')
from tg_toolbox.cli_base import cargar_credenciales
api_id, api_hash = cargar_credenciales()
client = TelegramClient('tg_menu', api_id, api_hash)
asyncio.run(client.start())
print('Sesión creada')
"
```

### Sin Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install telethon mtranslate cryptography cryptg rich inquirerpy
python -c "
import sys
sys.path.insert(0, 'app')
from tg_toolbox.tg_toolbox import main
main()
"
```

---

## 🤖 Bot API interactivo (`app/bot/telegram_bot.py`)

Bot de Telegram con **comandos**, **botones inline** y **descarga de vídeos**. Un solo bot que genera contenido IA y descarga vídeos de cualquier plataforma.

### Características

| Función | Detalle |
|---|---|
| 💡 Contenido IA | Tips de programación, conceptos con código, herramientas AI |
| 📥 Descarga vídeos | Descarga de cualquier plataforma via yt-dlp (YouTube, Twitch, etc.) |
| 🎬 Conversión automática | Convierte a MP4 H.264/AAC, genera thumbnail, envía como vídeo |
| 📰 Noticias | Muestra las últimas noticias scrapeadas |
| ⬆️ Botones inline | Navegación por botones en cada respuesta |

### Comandos disponibles

| Comando | Descripción | Botones |
|---|---|---|
| `/start` | Mensaje de bienvenida | — |
| `/ayuda` | Pantalla de ayuda completa | — |
| `/ping` | Comprobar conexión del bot | — |
| `/tip` | Tip de programación (Gemini + DB) | 🔄 Otro tip, 💡 Concepto, 🛠 Tool |
| `/concepto` | Concepto con código de ejemplo | 🔄 Otro, 💡 Tip, 🛠 Tool |
| `/tool` | Herramienta AI (Gemini + DB) | 🔄 Otro, 💡 Tip, 📖 Concepto |
| `/noticias` | Últimas noticias scrapeadas | 📰 Más noticias, 💡 Tip |
| `/descarga URL` | Descargar vídeo de cualquier plataforma | — |
| `/download URL` | Alias de /descarga | — |

### Descarga de vídeos

El bot descarga vídeos de cualquier plataforma soportada por yt-dlp + HLS fallback:

```
Usuario: /descarga https://www.youtube.com/watch?v=...
Bot: 📥 Descargando...
Bot: 🎬 [Vídeo enviado con thumbnail]
```

**Flujo:**
1. Descarga el vídeo con yt-dlp (formato `bv+ba/b` para YouTube)
2. Si yt-dlp falla → busca streams HLS en la página y los descarga
3. Convierte a MP4 H.264/AAC (compatible con Telegram)
4. Genera thumbnail
5. Envía como vídeo con preview
6. Elimina el archivo local

**Timeout:** 30 minutos (para vídeos largos o conexiones lentas)

**Plataformas soportadas:** YouTube, ok.ru, Twitch, TikTok, Dailymotion, Vimeo, +1000 sitios

**Funciona en:**
- Chat privado: envía cualquier URL
- Grupos: menciona al bot con una URL (`@jorbencas_bot URL`)

### Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `BOT_TOKEN` | Token del bot (de @BotFather) | **requerido** |
| `GEMINI_API_KEY` | API key de Google Gemini | para tips/tools |
| `BOT_ADMINS` | IDs de admins (separados por coma) | vacío |
| `TEST_GH_DIR` | Ruta a test_githubActions | `/data/.test_githubActions` |
| `DOWNLOAD_DIR` | Ruta de descargas | `/data/descargas` |

### Arrancar el bot

```bash
cd downloader_telegram

# Configurar variables
export BOT_TOKEN="tu-token-de-BotFather"
export GEMINI_API_KEY="tu-api-key"

# Arrancar bot
docker compose up -d telegram_bot

# Ver logs
docker compose logs -f telegram_bot
```

---

## 📤 Uploader a Telegram (`subir_videos.py`)

Última pieza del pipeline **"Grabar → Comprimir → Subir a Telegram"**. Vigila la carpeta de vídeos comprimidos y los sube a los grupos de Telegram configurados.

### Qué hace

1. Vigila `/srv/devjobs-data/comprimidos` (donde `monitor_folder.sh` deja los `*_compressed.mp4`).
2. Por cada `*_compressed.mp4` no enviado, lo sube a **todos** los grupos de `grupos.json`.
3. Si un archivo supera **2 GB** (límite de cuenta de Telegram), lo **divide en partes** con ffmpeg (`-c copy`, sin recompresión) y sube cada parte.
4. Marca los enviados **en memoria**, elimina el comprimido local (y todos sus restos: logs `log_*.txt` y partes divididas) y borra la **grabación original** de `grabaciones/` cuando todas las partes se han subido a todos los destinos.

Reutiliza las credenciales cifradas del proyecto (`config/config.bin` + `config/secret.key`), pero usa su **propia sesión** (`sessions/uploader.session`) para no entrar en conflicto con la sesión del cli (`sessions/tg_toolbox.session`). Así puedes correr el cli de descargas y el uploader **a la vez**.

### Estado "ya subido" (sin ficheros)

El uploader **no crea ningún fichero de estado**. Lleva en **memoria** (`enviado(archivo)` / `marcar_enviado`) la lista de lo subido en la ejecución actual y, al terminar de subir un vídeo a todos sus destinos, **borra el propio comprimido** (`*_compressed.mp4`) y la **grabación original** correspondiente en `/srv/devjobs-data/grabaciones/`. Así, la presencia del fichero en `/srv/devjobs-data/comprimidos` es la única fuente de verdad: si ya no está, ya se subió. No hay `enviados.json` que podar ni que limpiar.

### Configuración inicial (importante — hacer ANTES del viaje)

#### 1. Sesión del uploader (una sola vez)

```bash
cd downloader_telegram
docker compose build
touch sessions/uploader.session   # si no existe, Docker lo montaría como un directorio y la sesión fallaría
docker compose run --rm uploader python /app/app/subir_videos.py --setup
```

Te pedirá teléfono + código. Crea `sessions/uploader.session` (solo se hace una vez).

> **Ojo 1 — verificación automática de sesión:** el script comprueba ANTES de cada uso si la sesión ya está autenticada. Si lo está, **no vuelve a pedir credenciales** (reutiliza `uploader.session`). Si no lo está:
> - `--list-chats` / autoupload: **no piden login**; avisan y salen indicando que ejecutes `--setup`.
> - `--setup`: es el único modo que inicia login (teléfono + código), y solo lo pedirá si la sesión no está autenticada. Si ya lo está, lo dice y sale sin preguntar.
>
> **Ojo 2 — archivo vs sesión autenticada:** un archivo `.session` por sí solo NO vale. Tiene que haber pasado por `--setup` (login con teléfono + código). Este paso **solo puede hacerlo tú** (es interactivo).
>
> **Ojo 3 — `uploader.session` inexistente:** si el archivo no existe, el `volumes:` de `docker-compose.yml` lo monta como un **directorio vacío** y Telethon falla con `unable to open database file`. Crea siempre el archivo vacío con `touch sessions/uploader.session` ANTES del primer `--setup`.

#### 2. Descubrir tus grupos

```bash
docker compose run --rm uploader python /app/app/subir_videos.py --list-chats
```

Muestra `ID / Tipo / Nombre / Carpeta / ¿Creado por ti? / ¿Foro?` de tus chats. Copia los IDs (los grupos y canales suelen ser negativos) o los `@usernames`.

> La columna **¿Foro?** indica si el grupo tiene **temas** activados (grupo con foro). Esos grupos pueden alojar las series como temas — mira la sección *Grupo con temas (series)* más abajo.

#### 3. Rellenar `grupos.json`

```json
{
  "grupos": [],
  "foros": [
    {
      "id": -100999888777,
      "nombre": "sendo",
      "general": 1,
      "temas": [
        { "nombre": "devil may cry", "id": 123 },
        { "nombre": "resident evil", "id": 456 }
      ]
    }
  ]
}
```

- **`grupos`**: lista de `{ "nombre", "id" }`: **chats sueltos** (canales/grupos). El `nombre` es la keyword que debe aparecer en el título/descripción del directo para enrutar el vídeo a ese grupo. *(Opcional: si se omite o queda vacío, los vídeos solo se enrutan a los foros.)*
- **`foros`**: lista de grupos con **temas** (series). Cada foro:
  - **`id`**: id del chat con foro (negativo).
  - **`nombre`**: etiqueta (p. ej. `sendo`, `stream tecnologia`).
  - **`general`**: id del **tema general** → adonde van los vídeos de ese foro que **no se hayan podido categorizar/matchear**.
  - **`temas`**: `{ "nombre", "id" }` de las series del foro (misma coincidencia flexible).

> **El tema actúa como clave de canal.** No hay lista `canales` aparte: el ruteo compara el **canal del archivo** (primer token del nombre) contra los **nombres de los temas** de cada foro. Si coincide (p. ej. canal `midudev` ↔ tema `midu`), el vídeo va a ese foro/tema. Si no, va al primer foro *catch-all* (sendo) y se matchea por keyword.

### Ruteo automático por keyword/canal

1. `TwitchRecorder` lee el **título del directo** con yt-dlp y lo incrusta en el nombre del archivo: `sendosama_2026-08-13_20-15-00_KW_prueba.mp4`.
2. El monitor comprime y conserva el nombre → `..._KW_prueba_compressed.mp4`.
3. El uploader extrae el **canal** (primer token del nombre) y la **keyword** (`prueba`).
   - **Agrupación de partes**: si el nombre trae sufijos `__parteN` (p. ej. `sendosama_..._KW_prueba__parte2_compressed.mp4`), se **eliminan antes de extraer la keyword** (`keyword_from_filename` en `subir_videos.py`). Así todas las partes del mismo directo se rutearon al mismo grupo/tema.
4. **Enrutado a foros:** se busca en todos los foros un **tema cuyo nombre coincida con el canal del archivo** (p. ej. `midudev` → tema `midu`). Si coincide, va a ese foro/tema. Si no, va al primer foro *catch-all* (sendo) y se busca un tema que coincida con la **keyword** (o episodios); si tampoco, al tema **`general`**.
5. **Enrutado a `grupos`:** se sube a los `grupos` cuyo `nombre` coincida con la keyword. No hay grupo `default` (solo foros).
6. Si no hay ningún destino → se omite.

### Grupo con temas (series)

Cada foro de `foros` puede tener N temas de series. El tema **`general`** es el destinatario por defecto cuando la keyword/canal no matchea ninguna serie de ese foro.

#### 1. Descubrir el canal con foro y sus temas

```bash
# El canal con foro sale con '¿Foro? = sí' en --list-chats
docker compose run --rm uploader python /app/app/subir_videos.py --list-chats

# Lista los temas (series) del canal con foro
docker compose run --rm uploader python /app/app/subir_videos.py --list-topics -100999888777
```

`--list-topics <grupo>` imprime `ID / Título` de cada tema. Esos `ID` son los que se ponen en `temas` (y en `general`).

> **El tema `General` de Telegram** (creado automáticamente al activar el foro) suele ser el id 1. Se usa como `general` del foro para todo lo no categorizable.

#### 2. Gestión de canales/foros con `gestion_canales.py`

Además del uploader, hay un script auxiliar (mismo `uploader.session`) para crear/archivar canales, crear temas y migrar contenido:

```bash
# Crear un canal privado con foro (temas) y archivarlo
docker exec telegram-uploader-sendo python /app/gestion_canales.py --crear-canal "micanal" --foro
docker exec telegram-uploader-sendo python /app/gestion_canales.py --archivar -100999888777

# Crear temas en el foro
docker exec telegram-uploader-sendo python /app/gestion_canales.py --crear-temas=-100999888777:"General,serie1,serie2"

# Re-subida (sin borrar) de un canal origen a un tema de un foro concreto
docker exec telegram-uploader-sendo python /app/gestion_canales.py --migrar=-100999888777:123:-100111222333

# Borrar un canal (pide confirmación)
docker exec telegram-uploader-sendo python /app/gestion_canales.py --borrar-canal=-100111222333
```

---

## 🤖 Bot API interactivo (`app/bot/telegram_bot.py`)

Bot de Telegram con **comandos**, **botones inline** y **descarga de vídeos**. Un solo bot que genera contenido IA y descarga vídeos de cualquier plataforma.

### Características

| Función | Detalle |
|---|---|
| 💡 Contenido IA | Tips de programación, conceptos con código, herramientas AI |
| 📥 Descarga vídeos | Descarga de cualquier plataforma via yt-dlp (YouTube, Twitch, etc.) |
| 🎬 Conversión automática | Convierte a MP4 H.264/AAC, genera thumbnail, envía como vídeo |
| 📰 Noticias | Muestra las últimas noticias scrapeadas |
| ⬆️ Botones inline | Navegación por botones en cada respuesta |

### Comandos disponibles

| Comando | Descripción | Botones |
|---|---|---|
| `/start` | Mensaje de bienvenida | — |
| `/ayuda` | Pantalla de ayuda completa | — |
| `/ping` | Comprobar conexión del bot | — |
| `/tip` | Tip de programación (Gemini + DB) | 🔄 Otro tip, 💡 Concepto, 🛠 Tool |
| `/concepto` | Concepto con código de ejemplo | 🔄 Otro, 💡 Tip, 🛠 Tool |
| `/tool` | Herramienta AI (Gemini + DB) | 🔄 Otro, 💡 Tip, 📖 Concepto |
| `/noticias` | Últimas noticias scrapeadas | 📰 Más noticias, 💡 Tip |
| `/descarga URL` | Descargar vídeo de cualquier plataforma | — |
| `/download URL` | Alias de /descarga | — |

### Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `BOT_TOKEN` | Token del bot (de @BotFather) | **requerido** |
| `GEMINI_API_KEY` | API key de Google Gemini | para tips/tools |
| `BOT_ADMINS` | IDs de admins (separados por coma) | vacío |
| `TEST_GH_DIR` | Ruta a test_githubActions | `/data/.test_githubActions` |
| `DOWNLOAD_DIR` | Ruta de descargas | `/data/descargas` |

---

## 🖥️ CLI consolidada (`tg_toolbox`)

Menú interactivo único que reúne **toda** la gestión de Telegram en un solo sitio: descargas, clonación, **chats y carpetas**, **canales / foros / temas**, **migración** y **subida** (pipeline). **Independiente del daemon**: no importa `subir_videos.py`; reutiliza la lógica compartida a través de `cli_base.py` (credenciales cifradas, ruteo por keyword, `match_tema_foro`, `atributos_video` con ffprobe y subida con tracking propio).

```bash
# Forma recomendada (alias): contenedor efímero, se autodescarta al salir (--rm)
tg_menu

# O manual: primera vez inicia sesión (teléfono + código, y 2FA si aplica).
# Crea sessions/tg_toolbox.session
docker compose -f docker-compose.yml run --rm telegram

# O en un contenedor ya levantado
docker exec -it telegram-downloader python /app/app/tg_toolbox/tg_toolbox.py

# O sin Docker
python app/tg_toolbox/tg_toolbox.py
```

> **Sesión propia:** usa `sessions/tg_toolbox.session` (no pisa la del daemon `uploader`).
> Si la borras o cambias de contenedor, vuelve a pedir login la primera vez.

### Menú principal

| Opción | Módulo |
|---|---|
| 📥 **1** | Descargas |
| 🔄 **2** | Clonar & Backup |
| 🗂️ **3** | Chats y carpetas |
| 🧭 **4** | Canales / Foros / Temas |
| 🚚 **5** | Subida (pipeline) |
| 👁️ **6** | Vigilante |
| ⚙️ **7** | Config / Salir |
| 🧭 **8** | Modo guiado (todo el flujo) |
| 🧹 **9** | Limpieza / Programación |
| 📌 **10** | Fijar / Desfijar mensajes |
| 🔎 **11** | Buscar fotos en Guardados |
| ✏️ **12** | Editar descripciones en Guardados |

### Módulos principales

| Módulo | Qué hace |
|---|---|
| 📥 **1** | Descargas (interactiva, enlace, rango IDs, `enlaces.txt`, canal completo, búsqueda, storys, voice→texto, YouTube) |
| 🔄 **2** | Clonar & Backup (clonar canal→canal, backup local, restaurar) |
| 🗂️ **3** | Chats y carpetas (listar, archivar, carpetas, silenciar, fijar, mover) |
| 🧭 **4** | Canales / Foros / Temas (ver, crear, archivar, gestionar temas, migrar, borrar) |
| 🚚 **5** | Subida (pipeline) — sync, ver grupos, pasada, archivo, diferida, plantillas, export/import |
| 👁️ **6** | Vigilante — alertas, reenvío, descarga media, cooldown |
| 🧭 **8** | Modo guiado — todo el flujo paso a paso (blindado) |
| 🧹 **9** | Limpieza / Programación (estado conversión, limpiar temporales, programar sync) |
| 📌 **10** | Fijar / Desfijar mensajes (chat, grupo, tema) |
| 🔎 **11** | Buscar fotos en Guardados |
| ✏️ **12** | Editar descripciones en Guardados (añade sin sustituir) |

---

## 📤 Uploader a Telegram (`subir_videos.py`)

Última pieza del pipeline **"Grabar → Comprimir → Subir a Telegram"**. Vigila la carpeta de vídeos comprimidos y los sube a los grupos de Telegram configurados.

### Qué hace

1. Vigila `/srv/devjobs-data/comprimidos` (donde `monitor_folder.sh` deja los `*_compressed.mp4`).
2. Por cada `*_compressed.mp4` no enviado, lo sube a **todos** los grupos de `grupos.json`.
3. Si un archivo supera **2 GB** (límite de cuenta de Telegram), lo **divide en partes** con ffmpeg (`-c copy`, sin recompresión) y sube cada parte.
4. Marca los enviados **en memoria**, elimina el comprimido local (y todos sus restos: logs `log_*.txt` y partes divididas) y borra la **grabación original** de `grabaciones/` cuando todas las partes se han subido a todos los destinos.

Reutiliza las credenciales cifradas del proyecto (`config/config.bin` + `config/secret.key`), pero usa su **propia sesión** (`sessions/uploader.session`) para no entrar en conflicto con la sesión del cli (`sessions/tg_toolbox.session`). Así puedes correr el cli de descargas y el uploader **a la vez**.

### Configuración `grupos.json` (schedule por platform)

```json
{
  "grupos": [],
  "foros": [
    {
      "id": -100999888777,
      "nombre": "sendo",
      "general": 1,
      "temas": [
        { "nombre": "devil may cry", "id": 123 },
        { "nombre": "resident evil", "id": 456 }
      ]
    }
  ]
}
```

**Novedad:** Cada platform en `platform[]` tiene su propio `schedule` (días/horas). Si un platform no tiene `schedule` → se ignora (no se vigila). Así cada canal decide cuándo y qué vigilar.

### Configuración inicial (importante — hacer ANTES del viaje)

#### 1. Sesión del uploader (una sola vez)

```bash
cd downloader_telegram
docker compose build
touch sessions/uploader.session   # si no existe, Docker lo montaría como un directorio y la sesión fallaría
docker compose run --rm uploader python /app/app/subir_videos.py --setup
```

Te pedirá teléfono + código. Crea `sessions/uploader.session` (solo se hace una vez).

#### 2. Descubrir tus grupos

```bash
docker compose run --rm uploader python /app/app/subir_videos.py --list-chats
```

#### 3. Rellenar `grupos.json` (schedule por platform)

```json
{
  "platform": [
    {
      "platform": "web",
      "url": "https://watch.sendosama.net/",
      "detectar": true,
      "corte": false,
      "schedule": [
        {"days": ["Sunday"], "time": "19:00"},
        {"days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], "time": "21:30"}
      ]
    },
    {
      "platform": "twitch",
      "detectar": false,
      "corte": false,
      "schedule": []
    }
  ]
}
```

**Novedad:** Cada platform tiene su `schedule` (días/horas). Si `schedule: []` → se ignora (no se vigila).

---

## Estructura

```
downloader_telegram/
├── app/                                      # código Python
│   ├── bot/                                  # Bot API interactivo
│   │   ├── telegram_bot.py                   # Bot API (comandos + botones + @mención)
│   │   ├── bot_commands.py                   # Handlers de comandos (/status, /tip, etc.)
│   │   ├── bot_callbacks.py                  # Handlers de botones inline
│   │   └── bot_inline_keyboards.py           # Teclados inline reutilizables
│   ├── tg_toolbox/                           # CLI consolidada (nuevo directorio)
│   │   ├── __init__.py
│   │   ├── cli_base.py                       # utilidades autónomas (credenciales, ruteo, subida)
│   │   └── tg_toolbox.py                     # CLI principal (menú interactivo)
│   ├── bot/                                  # Bot API interactivo
│   │   ├── telegram_bot.py
│   │   ├── bot_commands.py
│   │   ├── bot_callbacks.py
│   │   ├── bot_inline_keyboards.py
│   ├── subir_videos.py                       # uploader automático a grupos (pipeline)
│   ├── pipeline_bridge.py                    # IPC: status.json + control.json + logs.json
│   ├── migrar_temas.py                       # migración de canales a temas de foros
│   ├── gestion_canales.py                    # crear/archivar canales + temas + migrar/borrar
│   ├── get_channel_id.py                     # helper para obtener channel_id
│   ├── subir_videos.py                       # uploader automático a grupos (pipeline)
│   ├── pipeline_bridge.py                    # IPC: status.json + control.json + logs.json
│   ├── migrar_temas.py                       # migración de canales a temas de foros
│   ├── gestion_canales.py                    # crear/archivar canales + temas + migrar/borrar
├── config/                                   # (gitignored) credenciales + ruteo
│   ├── config.bin                            # credenciales cifradas (AES)
│   ├── secret.key                            # llave de cifrado
│   └── grupos.json                           # ruteo por keyword: grupos + foros (temas/general)
├── tg_toolbox/                               # CLI consolidada (nuevo directorio)
│   ├── __init__.py
│   ├── cli_base.py                           # utilidades autónomas (credenciales, ruteo, subida)
│   └── tg_toolbox.py                         # CLI principal (menú interactivo)
├── sessions/                                 # (gitignored) sesiones de Telegram
│   ├── tg_toolbox.session                    # sesión del cli (toolbox)
│   └── uploader.session                      # sesión del daemon uploader
├── Descargas_Telegram/                       # (gitignored) carpeta de descargas del cli
├── Dockerfile                                # imagen Python + dependencias + ffmpeg
├── Dockerfile.bot                            # imagen del bot API
├── docker-compose.yml                        # servicios telegram (cli) + uploader + bot
├── requirements_bot.txt                      # dependencias del bot API
├── .env.example                              # plantilla de credenciales
├── LICENSE                                   # MIT
└── README.md
```

---

## Seguridad

- Las credenciales (API ID/Hash) se cifran con AES en `config.bin`
- La llave de cifrado se guarda en `secret.key`
- El archivo `.session` contiene el token de persistencia
- **Nunca commitees** `config.bin`, `secret.key`, `.session` ni `.env`

## Dependencias

Se instalan automáticamente en la imagen Docker:

- `Telethon` — Cliente de Telegram para Python
- `cryptography` (Fernet) — Cifrado AES de credenciales
- `mtranslate` — Traducción automática
- `cryptg` — Aceleración de descargas
- `ffmpeg` — División de vídeos >2 GB en el uploader

## Blog

- [Telegram Ultimate Toolbox: Descargador Masivo, Clonador, Vigilante y Uploader](https://blog-jorbencas.vercel.app/proyectos/telegram-ultimate-toolbox/)