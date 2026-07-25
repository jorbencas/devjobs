# TwitchRecorder

Grabador automático de directos de Twitch con Docker.

## Requisitos

- Docker instalado ([docker.com](https://www.docker.com))

## Ejecutar en background (producción)

```bash
docker compose up -d
```

El contenedor se reinicia solo si el PC se reinicia (`restart: unless-stopped`).

## Parar

```bash
docker compose down
```

## Ejecutar una vez (test)

```bash
docker compose run --rm run
```

Ejecuta, graba para y muere. Ideal para probar.

## Logs

```bash
docker compose logs -f
```

## Reconstruir tras cambios en el código

```bash
docker compose build
```

## Configuración

Edita `config.json`:

```json
{
    "channels": ["sendosama"],
    "record_path": "/recordings",
    "days": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
    "start_time": "21:00",
    "check_every": 30,
    "max_duration": "24:00:00",
    "retry_interval": 60,
    "copy_to_test": true
}
```

| Campo | Descripción |
|-------|-------------|
| `channels` | Canales a grabar |
| `record_path` | Ruta donde se guardan los vídeos (dentro del contenedor) |
| `days` | Días de la semana en los que grabar |
| `start_time` | Hora a la que empezar a comprobar (HH:MM) |
| `check_every` | Intervalo de comprobación en segundos |
| `max_duration` | Duración máxima de grabación (HH:MM:SS). `"24:00:00"` = sin límite |
| `retry_interval` | Si se pierde la conexión pero el directo sigue, espera estos segundos antes de reconectar. Si el directo terminó, para. |
| `copy_to_test` | `true` = copia vídeos a `test/` después de grabar. `false` = no copia (modo test) |

## Ejecutar con config temporal

Para probar con otro canal sin modificar la config:

```bash
docker run --rm \
  -v ./config.json:/app/config.json:ro \
  -v /home/jorge/test_videos:/recordings \
  -e TZ=Europe/Madrid \
  twitchrecorder-run
```

## Estructura de grabaciones

```
grabaciones/
├── 2026/
│   └── 07/
│       ├── sendosama_2026-07-25_21-30-00.mp4
│       └── sendosama_2026-07-26_21-15-00.mp4
└── test/
    └── sendosama_2026-07-26_21-15-00.mp4
```

## Cambiar ruta de grabación

En `docker-compose.yml`, modifica la línea de volumes:

```yaml
volumes:
  - ./config.json:/app/config.json:ro
  - /ruta/local/en/tu/pc:/recordings
```
