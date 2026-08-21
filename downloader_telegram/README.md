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
| 🖥️ CLI consolidado | Menú guiado, entradas blindadas, auditoría y export/import de backup |
| 👁️ Vigilante | Alertas en múltiples canales, reenvío a destinos y descarga de media |
| 📤 Uploader automático | Vigila `comprimidos/`, divide >2 GB, rutea por keyword a temas/grupos |

---

## 📑 Tabla de contenidos

- [Requisitos](#requisitos)
- [Despliegue](#despliegue)
- [Uploader a Telegram](#uploader-a-telegram-subir_videospy)
- [CLI consolidada](#cli-consolidada-tg_toolboxpy)
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
git clone https://github.com/jorge-bencas/devjobs.git
cd devjobs/downloader_telegram
cp .env.example .env
# Editar .env con tus credenciales de Telegram
docker compose build
docker compose up
```

### Generar sesión portátil

```bash
docker compose run --rm telegram python test_string.py
```

### Sin Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install telethon mtranslate cryptography cryptg rich inquirerpy
python test_download_protected_content_telegram.py
```

---

## 📤 Uploader a Telegram (`subir_videos.py`)

Última pieza del pipeline **"Grabar → Comprimir → Subir a Telegram"**. Vigila la carpeta de vídeos comprimidos y los sube a los grupos de Telegram configurados.

### Qué hace

1. Vigila `../data/comprimidos` (donde `monitor_folder.sh` deja los `*_compressed.mp4`).
2. Por cada `*_compressed.mp4` no enviado, lo sube a **todos** los grupos de `grupos.json`.
3. Si un archivo supera **2 GB** (límite de cuenta de Telegram), lo **divide en partes** con ffmpeg (`-c copy`, sin recompresión) y sube cada parte.
4. Registra los enviados en `enviados.json` y elimina el archivo local (y todos sus restos: sidecar `*_episodios.json`, original de `.processed`, logs `log_*.txt` y partes divididas).

Reutiliza las credenciales cifradas del proyecto (`config/config.bin` + `config/secret.key`), pero usa su **propia sesión** (`sessions/uploader.session`) para no entrar en conflicto con la sesión del cli (`sessions/tg_toolbox.session`). Así puedes correr el cli de descargas y el uploader **a la vez**.

#### `enviados.json` — registro de lo ya subido

`config/enviados.json` es la **memoria de "ya subido"** del daemon uploader:
una lista con las **rutas absolutas** de cada `*_compressed.mp4` que ya se subió a
Telegram. Cada archivo se añade al terminar de subir (`marcar_enviado`) y se usa
como guarda: antes de subir, el uploader comprueba `enviado(archivo)` — si ya está
en la lista, lo **salta** (no re-subiría aunque el `.mp4` volviera a aparecer, por
ej. tras reiniciar el contenedor).

> **Limpieza:** el archivo se **poda automáticamente**: solo conserva las
> **últimas 15 subidas** (las entradas más antiguas se descartan al añadir una
> nueva). El límite es configurable con `UPLOADER_MAX_ENVIADOS` (default `15`;
> `0` = sin límite). Si además quieres limpiarlo a mano (p. ej. para forzar una
> re-subida), borra las entradas o haz `[]`. No ejecutes el daemon mientras lo
> editas. Cada proyecto se lleva su propio registro.

> Es **exclusivo del daemon uploader**. El CLI (`tg_toolbox.py`) lleva su propio
> tracking en `data/logs/sync_cli.json` y **no toca** `enviados.json`.

### Cambiar credenciales o carpetas (sin tocar el código)

Todo es configurable con **variables de entorno** (en el bloque `environment` del servicio `uploader`):

| Variable | Qué cambia | Default |
|---|---|---|
| `UPLOADER_API_ID` | Cambia credenciales **sin** tocar `config.bin` | `config.bin` |
| `UPLOADER_API_HASH` | Ídem (deben ir las dos juntas) | `config.bin` |
| `UPLOADER_INTERVALO` | Segundos entre pasadas | `60` |
| `UPLOADER_SESION` | Ruta de la sesión Telethon | `sessions/uploader.session` |
| `UPLOADER_GRUPOS` | Ruta de `grupos.json` | `config/grupos.json` |
| `UPLOADER_ENVIADOS` | Ruta del registro de enviados | `config/enviados.json` |
| `UPLOADER_PARTES` | Carpeta de partes temporales | `partes/` |
| `UPLOADER_CONFIG` / `UPLOADER_KEY` | Rutas de credenciales cifradas | `config/config.bin` / `config/secret.key` |
| `UPLOADER_CARPETAS` | Carpetas a vigilar (separadas por `:`) | `/comprimidos` |
| `UPLOADER_FORWARD_CHANNEL` | Canal de **solo-reenvío** (forward) donde se copia cada vídeo de la keyword (vacío `""` desactiva) | `-1004359591062` |
| `UPLOADER_FORWARD_KEYWORD` | Keyword del directo que dispara el reenvío | `diarios_boticaria` |
| `UPLOADER_MAX_ENVIADOS` | Máx. entradas que conserva `enviados.json` (poda automática; `0` = sin límite) | `15` |

> También puedes crear/borrar un contenedor distinto cambiando `container_name:` en el `docker-compose.yml` (p. ej. un segundo `uploader` que vigile otra carpeta, con su propia `enviados.json`).

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

Opciones de filtro para reducir la lista:

- La columna **Carpeta** solo etiqueta: `Principal`, `Archivado`, o `#N` para carpetas personalizadas (Telethon no expone el título real de estas carpeta).
- `--folder <texto>` filtra por **nombre del chat** (subcadena) o por la etiqueta de carpeta (`archivado` / `principal`).

```bash
# Solo los chats cuyo nombre contenga "sendo" (o los de la carpeta Archivado)
docker compose run --rm uploader python /app/app/subir_videos.py --list-chats --folder "sendo"
docker compose run --rm uploader python /app/app/subir_videos.py --list-chats --folder archivado

# Solo los chats/grupos/canales que creaste tú (columna ¿Creado por ti? = sí)
docker compose run --rm uploader python /app/app/subir_videos.py --list-chats --creados

# Ambos a la vez
docker compose run --rm uploader python /app/app/subir_videos.py --list-chats --folder "sendo" --creados
```

#### 3. Rellenar `grupos.json`

```json
{
    "grupos": [
        { "nombre": "prueba", "id": -100111222333 }
    ],
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

- **`grupos`**: lista de `{ "nombre", "id" }`: **chats sueltos** (canales/grupos). El `nombre` es la keyword que debe aparecer en el título/descripción del directo para enrutar el vídeo a ese grupo. Hoy está vacío (`[]`). *(Opcional: si se omite o queda vacío, los vídeos solo se enrutan a los foros.)*
- **`foros`**: lista de grupos con **temas** (series). Cada foro:
  - **`id`**: id del chat con foro (negativo).
  - **`nombre`**: etiqueta (p. ej. `sendo`, `stream tecnologia`).
  - **`general`**: id del **tema general** → adonde van los vídeos de ese foro que **no se hayan podido categorizar/matchear**.
  - **`temas`**: `{ "nombre", "id" }` de las series del foro (misma coincidencia flexible).

> **El tema actúa como clave de canal.** No hay lista `canales` aparte: el ruteo
> compara el **canal del archivo** (primer token del nombre) contra los **nombres
> de los temas** de cada foro. Si coincide (p. ej. canal `midudev` ↔ tema `midu`),
> el vídeo va a ese foro/tema. Si ningún tema coincide, va al primer foro
> *catch-all* (sendo) y se matchea por keyword.

#### Ruteo automático por keyword/canal

1. `TwitchRecorder` lee el **título del directo** con yt-dlp y lo incrusta en el nombre del archivo: `sendosama_2026-08-13_20-15-00_KW_prueba.mp4`.
2. El monitor comprime y conserva el nombre → `..._KW_prueba_compressed.mp4`.
3. El uploader extrae el **canal** (primer token del nombre) y la **keyword** (`prueba`).
4. **Enrutado a foros:** se busca en todos los foros un **tema cuyo nombre coincida con el canal del archivo** (p. ej. `midudev` → tema `midu`). Si coincide, va a ese foro/tema. Si no, va al primer foro *catch-all* (sendo) y se busca un tema que coincida con la **keyword** (o episodios); si tampoco, al tema **`general`**.
5. **Enrutado a `grupos`:** se sube a los `grupos` cuyo `nombre` coincida con la keyword. No hay grupo `default` (solo foros).
6. Si no hay ningún destino → se omite.

Configuración actual del pipeline (2 foros):
- **`sendo`** (`-1004419994198`, foro *Sendo resubidos*): participa a **todos** los vídeos de sendosama (catch-all). Cada directo va a su serie si matchea la keyword; si no, al tema **General (id 1)**.
- **`stream tecnologia`** (`-1004332325883`, canal archivado): sus temas actúan de clave por canal — un directo de `midudev` va al tema `midu` (3) y de `mouredev` al tema `mouredev` (4); si no coincide, al tema **General (id 1)**.

**Coincidencia flexible (tolerante a cómo escriba sendo el título):**
- No exige el nombre exacto del tema/grupo. Compara normalizado (sin mayúsculas/tildes, espacios colapsados) y acepta:
  - **Substring** del nombre completo: `devil may cryyy` → tema `"devil may cry"`.
  - **Palabra significativa** del nombre (≥4 letras): `resident evily` → tema `"resident evil"`; `sendo sama` → `"sendo"`.
  - **Prefijo (singular/plural)**: `pelicula_el` → tema `"peliculas"`.
- Solo falla (y va al `general` del foro) cuando el nombre no aparece en absoluto (p. ej. un typo de letras como `residnet evil`).

Si el directo no tiene título/keyword y no se reconoce el canal, el vídeo va al **tema `general`** del foro catch-all.

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

> **El tema `General` de Telegram** (creado automáticamente al activar el foro) suele
> ser el id 1. Se usa como `general` del foro para todo lo no categorizable.

#### 2. Gestión de canales/foros con `gestion_canales.py`

Además del uploader, hay un script auxiliar (mismo `uploader.session`) para
crear/archivar canales, crear temas y migrar contenido:

```bash
# Crear un canal privado con foro (temas) y archivarlo
docker exec telegram-uploader python /app/gestion_canales.py --crear-canal "micanal" --foro
docker exec telegram-uploader python /app/gestion_canales.py --archivar -100999888777

# Crear temas en el foro
docker exec telegram-uploader python /app/gestion_canales.py --crear-temas=-100999888777:"General,serie1,serie2"

# Re-subida (sin borrar) de un canal origen a un tema de un foro concreto
docker exec telegram-uploader python /app/gestion_canales.py --migrar=-100999888777:123:-100111222333

# Borrar un canal (pide confirmación)
docker exec telegram-uploader python /app/gestion_canales.py --borrar-canal=-100111222333
```

**Migración:** el primer canal `midu`/`mouredev` se sustituyó por el foro
`stream tecnologia` (temas `midu`/`mouredev`), y los 2 canales originales se
borraron (estaban vacíos, no había nada que migrar).

**Películas:** si el contenido detectado es una película (el OCR/metadata genera
`Película · TÍTULO`), el vídeo intenta coincidir también con el tema del foro
`"peliculas"`; si no lo hay, va al `general`. El caption de la película será
`Película · TÍTULO`.

### Jerarquía de la descripción (caption) en Telegram

El texto (pie) que acompaña a cada vídeo en Telegram se elige en este orden:

1. **Rango de episodios** (metadata del monitor `<video>_episodios.json` generada
   por OCR, o el OCR propio del uploader si no hay metadata): `Episodio 1-4`,
   `Temporada 2 · Episodio 1-4`. En el **caption mostrado se quita la palabra
   "Episodio(s)"**: `Episodio 1-4` → `1-4`, `Temporada 2 · Episodio 1-4` →
   `Temporada 2 · 1-4`. (El enrutado a temas sigue usando el texto completo.)
   También se usa si la metadata es una **película**: `Película · TÍTULO`.
2. **Por defecto**: `🎬 Directo de <canal>` (el canal se saca del nombre del
   archivo). Esto incluye cuando la metadata es una **descripción libre** del
   canal (p. ej. la de YouTube con `"descripcion": true`): se **ignora** la
   descripción y se usa el **nombre** del canal.

> **Las descripciones propias del canal (p. ej. YouTube) NO se usan como caption.**
> Solo los rangos de episodios/película se muestran; todo lo demás cae al nombre
> del canal (`🎬 Directo de <canal>`).

Si un vídeo **supera los 2 GB** (límite de Telegram) y el uploader lo parte en
varias partes, cada parte añade el sufijo `(n/total)` al caption: `1-4 (1/2)` y
`1-4 (2/2)`.

### Ponerlo en marcha (modo automático)

```bash
docker compose up -d uploader
```

El servicio corre con `restart: unless-stopped`, vigila `/comprimidos` cada 60 s y sube a los grupos.

#### Modos del script

| Modo | Comando |
|---|---|
| Setup de sesión | `python /app/app/subir_videos.py --setup` |
| Listar chats | `python /app/app/subir_videos.py --list-chats [--folder <carpeta>] [--creados]` |
| Listar temas (foro) | `python /app/app/subir_videos.py --list-topics <grupo>` |
| Crear temas (foro) | `python /app/app/subir_videos.py --create-topics <grupo:Tít1,Tít2,...>` |
| Auto-upload (bucle) | `python /app/app/subir_videos.py --intervalo 60 /comprimidos` |
| Una pasada y salir | `python /app/app/subir_videos.py --once /comprimidos` |

### Docker y dos instancias sin conflicto

El `docker-compose.yml` define dos servicios:

| Servicio | Sesión | Uso |
|---|---|---|
| `telegram` | `sessions/tg_toolbox.session` | Cli interactivo (descargas manuales) |
| `uploader` | `sessions/uploader.session` | Subida automática del pipeline |

Cada uno monta su **propio** archivo de sesión, por lo que pueden ejecutarse simultáneamente sin pisarse.

### Límite de tamaño

Telegram permite archivos de hasta **~2 GB** por cuenta. `subir_videos.py` comprueba cada archivo antes de subir:
- `< 2 GB` → sube directo.
- `> 2 GB` → divide con `ffmpeg -f segment -segment_time 5400 -c copy` en partes de 1,5 h, y sube cada parte por separado.

Las partes temporales van a `partes/` (montado como volumen). El original marcado se elimina tras subir todas las partes.

### Manejo de errores

El script es robusto ante fallos de configuración o del entorno:

- **Faltan archivos** (`config.bin`, `grupos.json`): termina con un mensaje claro indicando qué configurar.
- **Credenciales corruptas**: avisa y sugiere reconﬁgurar (o usar `UPLOADER_API_ID`/`UPLOADER_API_HASH`).
- **`grupos.json` mal formado/vacío**: avisa para que lo revises.
- **Sesión invalidada/vencida**: muestra un aviso con el comando `--setup` para regenerarla.
- **Un grupo falla**: solo se marca el vídeo como enviado si llegó a todos los grupos; si falla alguno, se reintenta en la siguiente pasada.
- **`enviados.json` corrupto**: lo reinicia vacío sin romper el bucle.

### Arquitectura del pipeline

El `uploader` es la **tercera y última pieza** del pipeline
(`TwitchRecorder` → `ffmpeg-yt-dlp.monitor` → este servicio). Aquí solo se
documenta su papel: **lees `*_compressed.mp4` de `data/comprimidos/`, los subes a
Telegram y borras el residuo**. El flujo completo y el arranque están en el
`README.md` de la raíz de `devjobs` (sección *PIPELINE*).

> Documentación completa del pipeline en el `README.md` de la raíz de `devjobs` y en `docker_help.txt` (secciones *PIPELINE* y *PIPELINE VÍA SYSTEMD*).

### Reenvío automático a un canal de solo-reenvío

Cuando un vídeo es de la keyword `diarios_boticaria`, además de subirlo a su(s)
grupo(s), el uploader lo **REENVÍA** (forward) al canal `-1004359591062`
("Los diarios de la boticaria sendo"). Ese canal es **solo de reenvío**: NUNCA
se sube contenido directamente, solo llegan forwards.

- Se usa `forward_messages` (reenvío nativo de Telegram): es **instantáneo**
  (copia en el servidor, sin re-subir el archivo). Se verá la atribución
  "Reenviado de..." y el grupo/remitente original.
- Se reenvía una vez por parte subida (si el vídeo se dividió por >2 GB, cada
  parte se reenvía).
- Si el reenvío falla, se registra el error pero **no** rompe la subida normal.
- Configurable sin tocar código con `UPLOADER_FORWARD_CHANNEL` y
  `UPLOADER_FORWARD_KEYWORD`; poner `UPLOADER_FORWARD_CHANNEL=""` desactiva la
  función.

---

## 🖥️ CLI consolidada (`tg_toolbox.py`)

Menú interactivo único que reúne **toda** la gestión de Telegram en un solo sitio:
descargas, clonación, **chats y carpetas**, **canales / foros / temas**, **migración**
y **subida** (pipeline). **Independiente del daemon**: no importa `subir_videos.py`;
reutiliza la lógica compartida a través de `cli_base.py` (credenciales cifradas, ruteo
por keyword, `match_tema_foro`, `atributos_video` con ffprobe y subida con tracking propio).

```bash
# Forma recomendada (alias): contenedor efímero, se autodescarta al salir (--rm)
tg_menu

# O manual: primera vez inicia sesión (teléfono + código, y 2FA si aplica).
# Crea sessions/tg_toolbox.session
docker compose -f docker-compose.yml run --rm telegram

# O en un contenedor ya levantado
docker exec -it telegram-downloader python /app/app/tg_toolbox.py

# O sin Docker
python app/tg_toolbox.py
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

### 1️⃣ Descargas

| Opción | Qué hace |
|---|---|
| 🎯 Descarga interactiva | Origen → filtros (fechas/tipos de medio) → destino; descarga todo o 1 a 1 |
| 🔗 Enlace único | Descarga un mensaje concreto (`t.me/...`) con opción de subirlo a un canal propio |
| 📊 Rango de IDs | Descarga mensajes entre dos IDs de un chat |
| 📄 Procesar enlaces.txt | Lee enlaces (uno por línea) y los procesa en lote |
| 📺 Canal completo | Descarga todo el historial (con filtros opcionales de fechas y tipos) |
| 📈 Estadísticas | Resumen de un canal/tema: nº de mensajes, tipos de media, actividad |
| 🔎 Búsqueda por texto | Busca coincidencias en un chat y permite descargar lo encontrado |
| 🌟 Storys activas | Descarga las stories publicadas actualmente por un canal |
| 🎙️ Voice → texto | Transcribe voice messages con whisper local |
| ▶️ YouTube (yt-dlp) | Descarga mejor mp4 / solo audio mp3 / mkv; opcionalmente sube a un canal |

### 2️⃣ Clonar & Backup

| Opción | Qué hace |
|---|---|
| 🔀 Clonar canal → canal | Reenvía/re-subida completa con opciones: traducir, descargar media, quitar remitente ("Forwarded from"), quitar caption |
| 💾 Backup a archivo local | Exporta contenido a JSON en disco (opcional media) |
| ♻️ Restaurar backup | Sube un backup previo a cualquier chat; opciones de traducción/caption |

### 3️⃣ Chats y carpetas

| Opción | Qué hace |
|---|---|
| 📋 Listar chats | Con filtros: todos / míos / ajenos / de una carpeta |
| 🗄️ Archivar / Desarchivar | Archiva o desarchiva un chat (se aplica en Telegram) |
| 🏷️ Listar por carpeta | Muestra chats agrupados por carpeta de Telegram |
| 📁 Crear carpeta | Crea una carpeta nueva (respeta el límite de carpetas de la cuenta) |
| 📦 Mover chat a carpeta | Añade/quita un chat de una carpeta |
| 🔇 Silenciar / Desilenciar | Cambia el mute de un chat |
| 📌 Fijar / Desfijar chat | Fija o desfija el chat en la lista |
| ✏️ Renombrar / Mover archivos | Renombra o mueve archivos locales ya descargados |

### 4️⃣ Canales / Foros / Temas

| Opción | Qué hace |
|---|---|
| 📋 Ver mis canales/foros | Lista con filtro por nombre |
| ✨ Crear canal | Crea canal con foro habilitado |
| 📂 Archivar / Desarchivar | Igual que chats pero para canales |
| 🗂️ Gestionar temas | Crear tema · renombrar tema · **vaciar tema** (borra sus mensajes) |
| 📤 Migrar canal → tema | Re-subida completa de un canal al tema de un foro; opcionalmente **borra el origen** tras migrar |
| 🗑️ Borrar canal | Elimina el canal entero de Telegram |

### 5️⃣ Subida (pipeline)

| Opción | Qué hace |
|---|---|
| 🔄 Sync carpeta → Telegram | Sube lo nuevo de una carpeta local |
| 📄 Ver grupos.json | Muestra el ruteo keyword → foro/grupo configurado |
| 🚀 Subir pasada | Rutea archivos pendientes según `grupos.json` |
| 🎬 Subir archivo concreto | Elige un archivo y su destino exacto |
| ⏰ Subida diferida | Programa una subida para más tarde |
| 🏷️ Plantillas de caption | Ver / añadir / eliminar plantillas reutilizables |
| 💾 Exportar / Importar config | Backup y restauración de la configuración del pipeline |

### 6️⃣ Vigilante — configura alertas de canales con reenvío y descarga automática (desde cero, editar config existente o borrarla).

### 8️⃣ Modo guiado — recorre todo el flujo paso a paso (origen → filtros → traducción → descarga → subida).

### 9️⃣ Limpieza / Programación

| Opción | Qué hace |
|---|---|
| 📊 Estado de conversión | Progreso del monitor ffmpeg |
| 🧹 Limpiar temporales | Borra `.part`, `.jpg` y `.staging` huérfanos |
| 🗑️ Limpiar ya subidas | Borra descargas que el sync_cli ya marcó como subidas |
| ⏰ Programar sync automático | Lanza el sync cada N minutos |

### 🔟 Fijar mensajes — fijar (normal o silencioso), desfijar uno concreto o **todos**.

### 1️⃣1️⃣ Buscar fotos en Guardados — busca por tipo (foto/vídeo/cualquiera), lista resultados y descarga todos o por ID.

### 1️⃣2️⃣ Editar descripciones en Guardados — busca mensajes por texto/tipo, comprueba si el caption sigue editable (Telegram limita la edición por antigüedad) y **añade** texto sin sustituir el existente.

### Confirmaciones y seguridad

- **Acciones destructivas** (vaciar canal, borrar canal, vaciar tema, migración con borrado) usan el patrón unificado `_confirmar_destruccion()`:
  1. Aviso rojo con **estadísticas del chat** (~nº de mensajes y fecha del último) para detectar selecciones equivocadas
  2. Exige **escribir el nombre exacto** del chat/tema
  3. Confirmación final con default **No**
- Si el texto no coincide, la acción se cancela (fail-safe); en la migración se continúa *sin* borrar el origen.
- Todas estas acciones quedan registradas en el **log de auditoría** (`data/logs/tg_toolbox.log`, visible desde Config).

### Robustez (entradas blindadas)

El CLI está **blindado frente a fallos de uso**: entrada numérica validada,
tabla resumen + **confirmación antes de ejecutar** cualquier acción, reintentos
con backoff ante `FloodWait`/`ConnectionError`, comprobación de conexión previa,
rutas saneadas, **triple confirmación** en acciones destructivas (ver
[Confirmaciones y seguridad](#confirmaciones-y-seguridad)) y **log de auditoría** de todas las acciones en
`data/logs/tg_toolbox.log` (ver `⚙️ Config → Ver log de auditoría`).

### Límites de cuenta Telegram

Las acciones que tocan límites de la cuenta (crear carpetas, fijar chats, fijar
mensajes, mover a carpetas, silenciar) traducen los errores de límite RPC a un
mensaje legible en español: p. ej. *"límite de chats fijados alcanzado"*,
*límite de carpetas*, *se necesitan permisos de administrador*, etc. Si no se
reconoce el límite, se muestra el error crudo de la API.

### Sub-funcionalidades de cada módulo

```
📦 TELEGRAM TOOLBOX
 1  📥  Descargas               8 opciones (ver abajo)
 2  🔄  Clonar & Backup         clonar canal→canal · backup local · restaurar
 3  🗂️  Chats y carpetas        listar, archivar, carpetas, silenciar, fijar, mover
 4  🧭  Canales/Foros/Temas      ver, crear canal, archivar, gestionar temas, migrar, borrar
 5  🚚  Subida (pipeline)        sync, ver grupos, pasada, archivo, diferida, plantillas, export/import
 6  👁️  Vigilante               alertas, varios canales, reenvío, descarga de media
10  📌  Fijar / Desfijar         fijar/desfijar mensajes y tema
──────
 7  ⚙️  Config / Salir          credenciales, export/import backup, ver auditoría
 8  🧭  Modo guiado             todo el flujo paso a paso (blindado)
 9  🧹  Limpieza / Programación  estado conversión, limpiar temporales, programar sync
```

**📥 Módulo 1 · Descargas** — elige el tipo y confirma si traducir textos:

| Opción | Qué hace |
|---|---|
| 🎯 Descarga interactiva | Origen → destino (chat/canal/tema) con filtros |
| 🔗 Enlace único | Descarga un mensaje/enlace concreto |
| 📊 Rango de IDs | Descarga un rango de mensajes de un chat |
| 📄 Procesar `enlaces.txt` | Lee enlaces de un archivo de texto |
| 📺 Canal completo | Descarga todo un canal |
| 📈 Estadísticas de un canal/tema | Cuenta mensajes/media de un chat |
| 🔎 Búsqueda por texto | Busca por texto y descarga los resultados (dedup por nombre + retomar `.part`) |
| 🌟 Descargar storys activas | Baja las storys no expiradas de un canal (foto/vídeo) a `Descargas_Telegram/Storys/` |
| 🎙️ Transcribir voice messages | Descarga y transcribe audios de voz con whisper (`openai-whisper`, auto-instala si falta) → `.txt` |
| ▶️ Descarga de YouTube | Usa `yt-dlp` (mp4/audio/mkv), auto-instala si falta, con opción de re-subir |

**Tipos de medio soportados en descargas (filtro B3):** vídeo, foto, audio, voice, documento,
sticker, gif, encuesta, contacto y ubicación. Encuestas/contactos/ubicaciones no son archivos
descargables: se guarda un `.txt` legible (pregunta/opciones, datos de contacto o coordenadas
con enlace a Google Maps).

**🗂️ Módulo 3 · Chats y carpetas:**

| Opción | Qué hace |
|---|---|
| 📋 Listar chats | Con filtros interactivos (todos/solo creados/por carpeta) |
| 🗄️ Archivar / Desarchivar | Mueve un chat a Archivado o lo saca |
| 🏷️ Listar por carpeta | Filtra chats por nombre/carpeta |
| 📁 Crear carpeta | Crea una carpeta (folder) vacía para organizar chats |
| 📦 Mover chat a carpeta | Mueve un chat a un folder (0=Principal, 1=Archivado, otras) |
| 🔇 Silenciar / Desilenciar | Activa/desactiva notificaciones de un chat |
| 📌 Fijar / Desfijar chat | Fija arriba o quita de la lista de chats |
| ✏️ Renombrar / Mover | Renombra o mueve archivos locales |

**🔄 Módulo 2 · Clonar & Backup** (submenú):

| Opción | Qué hace |
|---|---|
| 🔀 Clonar canal → canal | Reenvía mensajes de un chat a otro (límite, multimedia, traducción, quitar remitente/descripción) |
| 💾 Backup a archivo local | Guarda mensajes (+media) en `Descargas_Telegram/Backups/<chat>_backup/*.json` |
| ♻️ Restaurar backup | Carga un JSON guardado y lo reenvía a un chat (con traducción y opción de quitar descripción) |

**🧭 Módulo 4 · Canales / Foros / Temas:**

| Opción | Qué hace |
|---|---|
| 📋 Ver canales/foros | Lista tus foros y canales (con filtros) |
| ✨ Crear canal | Crea canal, con opción de foro (temas) |
| 📂 Archivar / Desarchivar | Archiva o restaura un canal/foro |
| 🗂️ Gestionar temas | Lista temas de un foro y crea/renombra/vacía |
| 📤 Migrar canal → tema | Vuelve a publicar un canal dentro de un tema de foro |
| 🗑️ Borrar canal | Borra un canal (con confirmación) |

**🚚 Módulo 5 · Subida (pipeline), autónomo:**

| Opción | Qué hace |
|---|---|
| 🔄 Sync carpeta → Telegram | Sube solo lo nuevo de una carpeta con **dedup** (`sync_cli.json`) y eligiendo destino |
| 📄 Ver grupos.json | Muestra foros/grupos de ruteo actuales |
| 🚀 Subir pasada | Rutea por `grupos.json` (igual que el daemon) |
| 🎬 Subir un archivo concreto | Sube un archivo específico a un destino |
| ⏰ Subida diferida | Programa una subida para más tarde |
| 🏷️ Plantillas de caption | Gestiona plantillas de texto para el pie de los vídeos |
| 💾 Exportar / Importar config | Hace/restaura una copia de la configuración |

**👁️ Módulo 6 · Vigilante** — monitoriza mensajes **en tiempo real** (`NewMessage`).
Config **persistente** (se guarda en `config/vigilante.json` y se reutiliza), filtros
por tipo de medio, emisores, inclusión/exclusión de chats y temas, varios destinos,
cooldown anti-ráfagas, reconexión automática y resumen al detener.

| Opción | Qué hace |
|---|---|
| Chats vigilados | Vigilar TODOS o elegir lista; además **excluir** chats concretos |
| Solo temas | Vigilar solo ciertos temas de un foro |
| Tipos de medio | Reaccionar solo a vídeo/foto/voice/sticker/gif/encuesta/etc. |
| Emisores | Solo alertar si el mensaje es de ciertos remitentes |
| Palabras clave extra | Detecta además términos propios (separados por coma) |
| 🚚 Reenvío automático | Envía a **varios** destinos (o "Mensajes guardados"); opción de reenviar el original con media, quitar remitente y/o descripción, y **marcar qué disparó** la alerta |
| 💾 Descargar media | Guarda adjuntos de las alertas en `Vigilante_Media/` (dedup por nombre, retoma `.part`) |
| ⏳ Cooldown | Segundos de espera entre alertas del mismo chat (anti-ráfagas) |
| 📊 Resumen al salir | Al detener con Ctrl+C muestra alertas/reenvíos/media procesados |
| 🔄 Config persistente | Guarda/reusa la configuración; permite editar o borrarla |

**🗂️ Módulo 7 · Config** — cambiar credenciales/carpetas, **exportar/importar backup**
de la config (usa `data/backups/` por defecto) y **ver log de auditoría**.

**🧭 Módulo 8 · Modo guiado** — recorre todo el flujo paso a paso con confirmaciones:
**origen** (chat/tema) → **qué descargo** (filtro por fecha o rango) → **destino** →
**ejecutar**. Sin sorpresas: todo se confirma antes de tocar algo.

**🧹 Módulo 9 · Limpieza / Programación / Estado:**

| Acción | Qué hace |
|---|---|
| 📊 Estado de la conversión | Muestra en vivo qué se está comprimiendo y qué hay listo, leyendo directamente `data/comprimidos/` (sin depender de otros contenedores) |
| 🧹 Limpiar temporales | Borra `.part`, `.jpg` y restos de `.staging` |
| 🧹 Limpiar sync | Limpia el tracking de subidas ya hechas del CLI (`sync_cli.json`) |
| ⏰ Programar sync | Programa sync automático de carpetas cada N minutos |

**📌 Módulo 10 · Fijar / Desfijar mensajes** (chat, grupo o tema de foro):

| Opción | Qué hace |
|---|---|
| 📌 Fijar mensaje | Fija un mensaje (por ID o el último) |
| 📌 Fijar silencioso | Fija sin notificación a los miembros |
| 🔓 Desfijar mensaje | Desfija un mensaje concreto |
| 🗑️ Desfijar todos | Desfija todos los mensajes fijados del chat/tema |

Uso de `UpdatePinnedMessageRequest` / `UnpinAllMessagesRequest` (Telethon 1.44).

---

## Estructura

```
downloader_telegram/
├── app/                                      # código Python
│   ├── tg_toolbox.py                         # CLI unificada (menú interactivo)
│   ├── cli_base.py                           # utilidades autónomas del CLI (credenciales, ruteo, subida)
│   ├── subir_videos.py                       # uploader automático a grupos (pipeline)
│   ├── migrar_temas.py                       # migración de canales a temas de foros
│   ├── gestion_canales.py                    # crear/archivar canales + temas + migrar/borrar
│   └── test_download_protected_content_telegram.py  # descargador clásico (legacy)
├── config/                                   # (gitignored) credenciales + ruteo
│   ├── config.bin                            # credenciales cifradas (AES)
│   ├── secret.key                            # llave de cifrado
│   ├── grupos.json                           # ruteo por keyword: grupos + foros (temas/general)
│   └── enviados.json                         # registro de vídeos ya subidos (uploader)
├── sessions/                                 # (gitignored) sesiones de Telegram
│   ├── tg_toolbox.session                    # sesión del cli (toolbox)
│   └── uploader.session                      # sesión del daemon uploader
├── Descargas_Telegram/                       # (gitignored) carpeta de descargas del cli
├── Dockerfile                                # imagen Python + dependencias + ffmpeg
├── docker-compose.yml                        # servicios telegram (cli) + uploader
├── .env.example                              # plantilla de credenciales
├── LICENSE                                   # MIT
└── README.md
```

> Las rutas de `config/`, `sessions/` y `Descargas_Telegram/` se resuelven de forma
> relativa al repo (`.parent` del código), sobreescribibles con variables de entorno
> (`UPLOADER_*`, `TG_TOOLBOX_*`) y montadas como volúmenes en docker.

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
