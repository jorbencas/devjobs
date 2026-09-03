# YouTube → Telegram Pipeline

Pipeline independiente para descargar vídeos de canales de YouTube, convertirlos a 720p y subirlos a un grupo de Telegram con temas organizados por canal.

## Características

| Función | Detalle |
|---|---|
| 📥 Descarga automática | Descarga vídeos de 158 canales de YouTube |
| 🎬 Vídeos, Shorts y Directos | Incluye todos los tipos de contenido |
| 🔄 Conversión 720p | Convierte a H.264/AAC compatible con Telegram |
| 📤 Subida a Telegram | Sube a grupo con temas (topics) por canal |
| 🎯 Límite por canal | Máximo 2 vídeos por canal a la vez |
| 🗑️ Limpieza automática | Elimina vídeos después de subirlos |
| 📊 Organización | Carpetas por canal en cada etapa |
| 🏷️ Caption enriquecido | Título + fecha de publicación + canal |

## Estructura

```
data/yt-pipeline/
├── downloads/          ← Vídeos descargados (por canal)
│   ├── midudev/
│   ├── mouredev/
│   └── ...
├── converted/          ← Vídeos convertidos a 720p
│   ├── midudev/
│   └── ...
├── uploaded/           ← Vídeos ya subidos (histórico)
│   ├── midudev/
│   └── ...
└── logs/               ← Logs de cada operación
    ├── downloads_*.json
    ├── conversions_*.json
    └── uploads_*.json
```

## Configuración

### 1. Variables de entorno

```bash
# En .env
BOT_TOKEN="tu-token-de-bot"
TELEGRAM_GROUP_ID="-100xxxxxxxxxx"  # ID del grupo con temas
```

### 2. Canales

Editar `config/channels.json` para habilitar/deshabilitar canales:

```json
[
  {
    "name": "Midudev",
    "url": "https://www.youtube.com/@midudev/videos",
    "enabled": true,
    "max_videos": 2
  },
  ...
]
```

### 3. Topics

Los topics se crean automáticamente en `config/topics.json` cuando se sube el primer vídeo de un canal.

**Topics preconfigurados:**
- MoureDev
- Midudev
- Carlos Azaustre
- Linkfydev

Los canales sin tema propio van a **General**.

## Uso

### Ejecutar pipeline completo

```bash
cd yt-to-telegram
docker compose up -d yt-pipeline
```

### Ejecutar pasos individuales

```bash
# Solo descargar
docker compose up -d yt-download

# Solo convertir
docker compose up -d yt-convert

# Solo subir
docker compose up -d yt-upload
```

### Ejecutar sin Docker

```bash
cd yt-to-telegram/scripts

# Instalar dependencias
pip install yt-dlp

# Ejecutar pipeline
python pipeline.py

# O pasos individuales
python download.py
python convert.py
python upload.py
```

## Flujo

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   download.py   │ ──► │   convert.py    │ ──► │    upload.py    │
│                 │     │                 │     │                 │
│ - Lista vídeos  │     │ - Convierte     │     │ - Crea temas    │
│ - Descarga 2/canal│   │ - 720p H.264   │     │ - Sube vídeos   │
│ - Shorts/Lives  │     │ - Shorts intactos│    │ - Caption con   │
│ - Guarda en     │     │ - Guarda en     │     │   título+fecha  │
│   downloads/    │     │   converted/    │     │ - Mueve a       │
│                 │     │                 │     │   uploaded/     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Tipos de contenido

| Tipo | Descripción | Conversión |
|---|---|---|
| 📹 Vídeo | Vídeo normal del canal | 720p H.264 |
| 🩳 Short | Vídeo vertical (<60s) | Sin redimensionar |
| 🔴 Live | Directo finalizado | 720p H.264 |

## Caption de ejemplo

```
📺 Título del vídeo

🔗 Canal: Midudev
📅 Publicado: 2026-09-01
```

## Límites

- **2 vídeos por canal** a la vez (configurable en `channels.json`)
- **720p** máxima resolución (compatible con Telegram)
- **Eliminación automática** después de subir
- **158 canales** incluidos por defecto

## Personalización

### Cambiar número de vídeos por canal

Editar `config/channels.json`:

```json
{
  "name": "Midudev",
  "max_videos": 5  // Cambiar a 5
}
```

### Añadir nuevos canales

Añadir al array en `config/channels.json`:

```json
{
  "name": "Nuevo Canal",
  "url": "https://www.youtube.com/@nuevocanal/videos",
  "enabled": true,
  "max_videos": 2
}
```

### Cambiar calidad de vídeo

Editar `scripts/convert.py` y cambiar la línea:

```python
"-vf", "scale=-2:720",
```

Por ejemplo, para 1080p:

```python
"-vf", "scale=-2:1080",
```

## Troubleshooting

### Error: "BOT_TOKEN y TELEGRAM_GROUP_ID son requeridos"

Asegúrate de que las variables de entorno están configuradas en `.env`.

### Error: "No se pudo crear tema"

El bot necesita permisos de administrador en el grupo para crear temas.

### Error: "Timeout descargando"

Algunos vídeos son muy largos. Se puede aumentar el timeout en `download.py`.

### Vídeos no se eliminan

La eliminación es automática después de subir. Si falla la subida, el vídeo se mantiene en `converted/`.

## Independencia

Este pipeline es **completamente independiente** del pipeline de TwitchRecorder:
- No comparten carpetas
- No comparten configuración
- No afectan entre sí
- Se pueden ejecutar simultáneamente

## Cron (automático diario)

El pipeline se ejecuta automáticamente cada día de 01:00 a 18:00:

```bash
# Cron configurado (01:00 → 18:00 mismo día)
0 1 * * * /home/jorge/dev/devjobs/yt-to-telegram/scripts/run_pipeline_cron.sh
```

**Flujo del cron:**
1. **01:00** → `docker compose up -d yt-pipeline` (arranca el servicio)
2. **18:00** → `docker compose down` (para el servicio, mismo día)
3. Comprueba cada 5 min si el contenedor sigue activo
4. Si el contenedor para inesperadamente, sale del bucle
5. Registra videos pendientes en `data/yt-pipeline/logs/pending_videos.log`

**Gestión manual:**
```bash
# Ver estado del cron
crontab -l

# Ejecutar manualmente ahora
bash /home/jorge/dev/devjobs/yt-to-telegram/scripts/run_pipeline_cron.sh

# Parar el pipeline manualmente
cd yt-to-telegram && docker compose down
```

**Logs:**
- `data/yt-pipeline/logs/cron_YYYYMMDD.log` — logs diarios del cron
- `data/yt-pipeline/logs/pending_videos.log` — videos pendientes entre ejecuciones

