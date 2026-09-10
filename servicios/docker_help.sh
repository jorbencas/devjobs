#!/bin/bash
# =============================================================================
#  docker_help — Muestra ayuda de todos los alias disponibles
# =============================================================================
cat << 'HELP'

╔══════════════════════════════════════════════════════════════════════╗
║                    DEVJOBS — Alias Disponibles                      ║
╚══════════════════════════════════════════════════════════════════════╝

PIPELINE (Directo → Telegram):
  pipe_up          Arranca los 3 daemons del pipeline
  pipe_down        Para los 3 daemons
  pipe_ps          Estado de los contenedores
  pipe_rebuild     Reconstruir y recrear los 3 daemons
  pipe_test        Copiar vídeo de prueba para verificar upload
  plogs            Logs de los 3 daemons a la vez
  pipe_setup       Autenticar sesión de Telegram (una vez)
  pipe_chats       Listar chats de Telegram
  pipe_topics      Listar topics de un grupo

TWITCHRECORDER:
  tw_logs          Ver logs del grabador
  tw_stop          Parar el grabador
  tw_restart       Reiniciar el grabador
  tw_run           Ejecutar grabador manualmente
  tw_dry           Dry-run (sin grabar)

FFMPEG-YT-DLP (Monitor):
  ff_logs          Ver logs del monitor
  ff_stop          Parar el monitor
  ff_restart       Reiniciar el monitor
  ff_midu          Ejecutar midu.sh (conversor interactivo)
  watcher          Preview watcher (host)
  watcher_daemon   Preview watcher como daemon

TELEGRAM BOT:
  tg_bot           Arrancar bot + ollama
  tg_bot_logs      Ver logs del bot
  tg_bot_stop      Parar bot + ollama
  tg_bot_restart   Reiniciar bot + ollama
  tg_bot_rebuild   Reconstruir bot

TELEGRAM CLI:
  tg_menu          Toolbox interactivo de Telegram
  tg_sessions      Gestionar sesiones
  tg_logs          Ver logs del uploader
  tg_stop          Parar el uploader

YT-TELEGRAM (Pipeline YouTube):
  yt_up            Arrancar pipeline
  yt_down          Parar pipeline
  yt_logs          Ver logs
  yt_restart       Reiniciar pipeline
  yt_rebuild       Reconstruir pipeline
  yt_ps            Estado del pipeline
  yt_download      Ejecutar solo descarga
  yt_convert       Ejecutar solo conversión
  yt_upload        Ejecutar solo subida

KICK.COM:
  kick_dl <url>    Descargar vídeo de Kick.com
                   Ejemplo: kick_dl https://kick.com/sendosama/videos/01a087f2-...

DISCORD (grabación automática):
  discord_monitor          Bot de Discord que graba streams/llamadas automáticamente
  discord_obs start [escena]  Iniciar grabación de OBS manualmente
  discord_obs stop         Parar grabación de OBS
  discord_obs status       Estado de OBS
  discord_obs scenes       Listar escenas de OBS

  Configuración: scripts/discord_config.json
  Requisitos: Discord bot token, OBS con obs-websocket, discord.py + obs-websocket-py

  Modos (record_mode):
    "stream"  - Solo streams (compartir pantalla)
    "call"    - Solo llamadas (unión al canal)
    "both"    - Ambos

  Configurar bot de Discord:
    1. Crear en https://discord.com/developers/applications
    2. Copiar token a discord_config.json
    3. Activar "Server Members Intent"
    4. Invitar con permisos: Connect, Speak, Use Voice Activity
    5. Abrir OBS → WebSocket → puerto 4455

HELP
