# YouTube → Telegram Pipeline

Pipeline independiente para descargar vídeos de canales de YouTube, convertirlos a 720p y subirlos a un grupo de Telegram con temas organizados por canal.

## Características

| Función | Detalle |
|---|---|
| 📥 Descarga automática | Descarga vídeos de 158 canales de YouTube |
| 🔄 Conversión 720p | Convierte a H.264/AAC compatible con Telegram |
| 📤 Subida a Telegram | Sube a grupo con temas (topics) por canal |
| 🎯 Límite por canal | Máximo 2 vídeos por canal a la vez |
| 🗑️ Limpieza automática | Elimina vídeos después de subirlos |
| 📊 Organización | Carpetas por canal en cada etapa |

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
│ - Guarda en     │     │ - Guarda en     │     │ - Mueve a       │
│   downloads/    │     │   converted/    │     │   uploaded/     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
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
"-vf", "scale='trunc(ow/2)*2:trunc(oh/2)*2'",
```

Por ejemplo, para 1080p:

```python
"-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
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
