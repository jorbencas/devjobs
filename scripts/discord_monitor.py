#!/usr/bin/env python3
"""
Monitor de Discord que detecta streams en canales de voz y lanza OBS para grabar.

Flujo:
  1. Bot se conecta a Discord
  2. Monitorea canales de voz específicos
  3. Cuando alguien comparte pantalla (stream) → lanza OBS grabando
  4. Cuando el stream termina → para OBS → pasa al pipeline

Requisitos:
  - pip install discord.py obs-websocket-py
  - Token de bot de Discord (https://discord.com/developers)
  - OBS Studio con obs-websocket habilitado

Uso:
  python discord_monitor.py
"""
import os
import sys
import json
import time
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime

try:
    import discord
    from discord.ext import commands, tasks
except ImportError:
    print("Instalando discord.py...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "discord.py", "-q"])
    import discord
    from discord.ext import commands, tasks

try:
    from obswebsocket import obsws, requests as obs_requests
except ImportError:
    print("Instalando obs-websocket-py...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "obs-websocket-py", "-q"])
    from obswebsocket import obsws, requests as obs_requests


# ============================================================================
#  CONFIGURACIÓN
# ============================================================================
SCRIPT_DIR = Path(__file__).parent
DEVJOBS = SCRIPT_DIR.parent
CONFIG_FILE = DEVJOBS / "TwitchRecorder" / "config.json"
DISCORD_CONFIG_FILE = SCRIPT_DIR / "discord_config.json"

# Valores por defecto
DEFAULT_OBS_HOST = "localhost"
DEFAULT_OBS_PORT = 4455
DEFAULT_OUTPUT_DIR = str(DEVJOBS / "data" / "discord-recordings")


def load_config() -> dict:
    """Carga la configuración de Discord."""
    if DISCORD_CONFIG_FILE.exists():
        with open(DISCORD_CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    """Guarda la configuración de Discord."""
    with open(DISCORD_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ============================================================================
#  CONTROL DE OBS
# ============================================================================
class OBSController:
    def __init__(self, host=DEFAULT_OBS_HOST, port=DEFAULT_OBS_PORT):
        self.host = host
        self.port = port
        self.ws = None

    def connect(self) -> bool:
        try:
            self.ws = obsws(self.host, self.port)
            self.ws.connect()
            return True
        except Exception as e:
            print(f"[OBS] Error conectando: {e}")
            return False

    def disconnect(self):
        if self.ws:
            try:
                self.ws.disconnect()
            except:
                pass

    def is_running(self) -> bool:
        try:
            if not self.ws:
                return self.connect()
            self.ws.call(obs_requests.GetVersion())
            return True
        except:
            return False

    def is_recording(self) -> bool:
        try:
            status = self.ws.call(obs_requests.GetRecordStatus())
            return status.getOutputActive()
        except:
            return False

    def start_recording(self, output_dir: str = None) -> bool:
        try:
            # Configurar carpeta de salida si se especifica
            if output_dir:
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"discord_{timestamp}"
                self.ws.call(obs_requests.SetRecordSettings(
                    filenameFormatting=str(Path(output_dir) / filename)
                ))

            self.ws.call(obs_requests.StartRecord())
            print(f"[OBS] Grabación iniciada")
            return True
        except Exception as e:
            print(f"[OBS] Error iniciando grabación: {e}")
            return False

    def stop_recording(self) -> str:
        try:
            self.ws.call(obs_requests.StopRecord())
            time.sleep(1)
            return self._find_last_recording()
        except Exception as e:
            print(f"[OBS] Error parando grabación: {e}")
            return ""

    def _find_last_recording(self) -> str:
        try:
            settings = self.ws.call(obs_requests.GetRecordSettings())
            output_path = settings.getRecordPath()
            output_dir = Path(output_path) if output_path else Path(DEFAULT_OUTPUT_DIR)

            extensions = ["*.mp4", "*.mkv", "*.flv", "*.mov"]
            files = []
            for ext in extensions:
                files.extend(output_dir.glob(ext))

            if files:
                latest = max(files, key=lambda f: f.stat().st_mtime)
                return str(latest)
        except:
            pass
        return ""

    def get_scenes(self) -> list:
        try:
            scenes = self.ws.call(obs_requests.GetSceneList())
            return [s.getName() for s in scenes.getScenes()]
        except:
            return []

    def set_scene(self, scene_name: str) -> bool:
        try:
            self.ws.call(obs_requests.SetCurrentProgramScene(scene_name))
            return True
        except:
            return False


# ============================================================================
#  BOT DE DISCORD
# ============================================================================
class DiscordMonitor(commands.Bot):
    def __init__(self, config: dict):
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.guilds = True
        intents.members = True

        super().__init__(command_prefix="!", intents=intents)

        self.config = config
        self.token = config.get("discord_token", "")
        self.monitor_channels = config.get("monitor_channels", [])
        self.obs_host = config.get("obs_host", DEFAULT_OBS_HOST)
        self.obs_port = config.get("obs_port", DEFAULT_OBS_PORT)
        self.output_dir = config.get("output_dir", DEFAULT_OUTPUT_DIR)
        self.record_scene = config.get("record_scene", None)

        self.obs = OBSController(self.obs_host, self.obs_port)
        self.is_recording = False
        self.current_streamer = None
        self.current_channel = None

    async def on_ready(self):
        print(f"[Discord] Bot conectado como {self.user}")
        print(f"[Discord] Monitoreando canales: {self.monitor_channels}")

        # Conectar a OBS
        if self.obs.connect():
            print(f"[OBS] Conectado a {self.obs_host}:{self.obs_port}")
        else:
            print(f"[OBS] No se pudo conectar. OBS no está corriendo?")

        # Iniciar monitoreo
        self.check_voice_states.start()

    @tasks.loop(seconds=10)
    async def check_voice_states(self):
        """Comprueba periódicamente si hay streams o llamadas activas."""
        record_mode = self.config.get("record_mode", "stream")  # stream, call, both

        for guild in self.guilds:
            for channel in guild.voice_channels:
                if channel.id not in self.monitor_channels and channel.name not in self.monitor_channels:
                    continue

                # Buscar usuarios en el canal
                members_in_channel = [m for m in channel.members if m.voice]
                streamers = [m for m in members_in_channel if m.voice.self_stream]

                should_record = False
                trigger_member = None
                trigger_reason = ""

                if record_mode in ("stream", "both") and streamers:
                    should_record = True
                    trigger_member = streamers[0]
                    trigger_reason = "stream"
                elif record_mode in ("call", "both") and len(members_in_channel) >= self.config.get("min_users_for_call", 1):
                    should_record = True
                    trigger_member = members_in_channel[0]
                    trigger_reason = "call"

                if should_record:
                    if not self.is_recording:
                        await self._start_recording(trigger_member, channel, trigger_reason)
                    return

                # Si había grabación activo pero ya no hay trigger
                if self.is_recording:
                    any_active = False
                    if record_mode in ("stream", "both"):
                        any_active = any(m.voice.self_stream for m in members_in_channel)
                    if not any_active and record_mode in ("call", "both"):
                        any_active = len(members_in_channel) >= self.config.get("min_users_for_call", 1)
                    if not any_active:
                        await self._stop_recording()

    async def _start_recording(self, member: discord.Member, channel: discord.VoiceChannel, reason: str = "stream"):
        """Inicia la grabación cuando se detecta un stream o llamada."""
        label = "Stream" if reason == "stream" else "Llamada"
        print(f"[Discord] {label} detectado: {member.display_name} en {channel.name}")

        self.current_streamer = member.display_name
        self.current_channel = channel.name

        # Conectar a OBS si no está conectado
        if not self.obs.is_running():
            if not self.obs.connect():
                print("[OBS] No se pudo conectar. Reintentando en 10s...")
                return

        # Iniciar grabación
        if self.obs.start_recording(self.output_dir):
            self.is_recording = True
            print(f"[Discord] Grabación iniciada para {member.display_name}")

            # Guardar metadata
            self._save_metadata(member, channel)

    async def _stop_recording(self):
        """Para la grabación cuando el stream termina."""
        print(f"[Discord] Stream terminado de {self.current_streamer}")

        if self.obs.is_recording():
            output = self.obs.stop_recording()
            if output:
                print(f"[Discord] Grabación guardada: {output}")
                # Aquí se podría integrar con el pipeline
                self._process_recording(output)

        self.is_recording = False
        self.current_streamer = None
        self.current_channel = None

    def _save_metadata(self, member: discord.Member, channel: discord.VoiceChannel, reason: str = "stream"):
        """Guarda metadata del stream/llamada para el pipeline."""
        metadata = {
            "streamer": member.display_name,
            "channel": channel.name,
            "guild": channel.guild.name,
            "started_at": datetime.now().isoformat(),
            "platform": "discord",
            "trigger": reason,  # "stream" o "call"
        }
        metadata_file = Path(self.output_dir) / "current_stream.json"
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def _process_recording(self, recording_path: str):
        """Procesa la grabación: mover al pipeline y comprimir."""
        try:
            # Mover a la carpeta de grabaciones del pipeline
            pipeline_dir = DEVJOBS / "data" / "pipeline" / "grabaciones" / "discord"
            pipeline_dir.mkdir(parents=True, exist_ok=True)

            source = Path(recording_path)
            dest = pipeline_dir / source.name

            import shutil
            shutil.move(str(source), str(dest))
            print(f"[Pipeline] Movido a {dest}")

            # Copiar a test/ para que ffmpeg_monitor lo procese
            test_dir = DEVJOBS / "data" / "pipeline" / "grabaciones" / "test"
            test_dir.mkdir(parents=True, exist_ok=True)
            test_file = test_dir / f"discord_{source.stem}_completed.mp4"
            shutil.copy2(str(dest), str(test_file))
            print(f"[Pipeline] Copiado a {test_file}")

        except Exception as e:
            print(f"[Pipeline] Error procesando grabación: {e}")

    async def on_message(self, message):
        if message.author == self.user:
            return

        # Comandos del bot
        if message.content.startswith("!discord_status"):
            status = "grabando" if self.is_recording else "esperando"
            if self.is_recording:
                await message.reply(f"🎙️ Grabando: {self.current_streamer} en #{self.current_channel}")
            else:
                await message.reply(f"⏳ Esperando streams. Canales monitoreados: {len(self.monitor_channels)}")

        elif message.content.startswith("!discord_stop"):
            if self.is_recording:
                await self._stop_recording()
                await message.reply("⏹️ Grabación parada")
            else:
                await message.reply("No hay grabación activa")

        elif message.content.startswith("!discord_help"):
            await message.reply(
                "**Comandos Discord Monitor:**\n"
                "`!discord_status` — Estado actual\n"
                "`!discord_stop` — Parar grabación\n"
                "`!discord_help` — Esta ayuda"
            )


def main():
    config = load_config()

    if not config.get("discord_token"):
        print("Error: No hay token de Discord configurado.")
        print(f"Configura en: {DISCORD_CONFIG_FILE}")
        print("\nEjemplo de configuración:")
        print(json.dumps({
            "discord_token": "TU_TOKEN_AQUI",
            "monitor_channels": ["ID_O_NOMBRE_DEL_CANAL"],
            "obs_host": "localhost",
            "obs_port": 4455,
            "output_dir": DEFAULT_OUTPUT_DIR,
        }, indent=2))
        sys.exit(1)

    bot = DiscordMonitor(config)

    try:
        bot.run(config["discord_token"])
    except discord.LoginFailure:
        print("Error: Token de Discord inválido")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBot detenido")


if __name__ == "__main__":
    main()
