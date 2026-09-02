# TwitchRecorder

Grabador automático de directos de Twitch/YouTube/Kick. Forma parte del pipeline de grabación → compresión → subida a Telegram.

## Configuración (`config.json`)

### Estructura básica

```json
{
  "channels": {
    "nombre_canal": {
      "platform": [...],
      "start_time": {...},
      "dias_plataforma": {...}
    }
  }
}
```

### Campos por canal

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `platform` | list/dict | Fuentes de streaming en orden de prioridad |
| `start_time` | dict | Hora de inicio por día |
| `dias_plataforma` | dict | Plataformas activas por día |

### `dias_plataforma`

Define qué plataformas se comprueban para cada día. Si no existe, se usan todas las plataformas todos los días.

```json
"dias_plataforma": {
  "Sunday": ["youtube", "twitch", "web", "kick"],
  "*": ["web", "twitch", "kick"]
}
```

- `"*"` = todos los demás días (lunes a sábado)
- Si el campo no existe o no hay match, se comprueban todas las plataformas

### `start_time`

Hora de inicio de grabación por día:

```json
"start_time": {
  "Sunday": "19:00",
  "*": "21:30"
}
```

- `"*"` = valor por defecto para días no especificados

### Plataformas soportadas

| Plataforma | Ejemplo |
|------------|---------|
| `twitch` | `"platform": "twitch"` |
| `youtube` | `"platform": "youtube", "channel": "nombre"` |
| `kick` | `"platform": "kick", "detectar": true` |
| `web` | `"platform": "web", "url": "https://...", "detectar": true` |

## Uso

```bash
# Arrancar (daemon normal)
docker compose up -d twitchrecorder

# Ver logs
docker compose logs -f twitchrecorder

# Rebuild + recreate
docker compose build twitchrecorder && docker compose up -d --force-recreate twitchrecorder
```

## Notas

- El scheduler comprueba cada 30s si algún canal está en directo
- Solo graba si es después de la `start_time` del canal para el día actual
- Las grabaciones se guardan en `data/grabaciones/YYYY/MM/`
- Formato: `<canal>_<fecha>_<hora>_KW_<keyword>.mp4`
- Cuando termina, se renombra a `*_completed.mp4` para que ffmpeg_monitor lo comprima
