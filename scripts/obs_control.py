#!/usr/bin/env python3
"""
Control de OBS Studio vía obs-websocket.
Inicia/para grabación, configura escena, y gestiona OBS automáticamente.

Requisitos:
  - OBS Studio 28+ (obs-websocket integrado)
  - pip install obs-websocket-py

Uso:
  python obs_control.py start [escena]     # Iniciar grabación
  python obs_control.py stop               # Parar grabación
  python obs_control.py status             # Estado actual
  python obs_control.py scenes             # Listar escenas
"""
import sys
import time
import json
from pathlib import Path

try:
    from obswebsocket import obsws, requests as obs_requests
except ImportError:
    print("Instalando obs-websocket-py...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "obs-websocket-py", "-q"])
    from obswebsocket import obsws, requests as obs_requests


DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4455
DEFAULT_PASSWORD = ""  # Vacío si no tienes password configurado


class OBSController:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, password=DEFAULT_PASSWORD):
        self.host = host
        self.port = port
        self.password = password
        self.ws = None

    def connect(self) -> bool:
        try:
            self.ws = obsws(self.host, self.port, self.password)
            self.ws.connect()
            return True
        except Exception as e:
            print(f"Error conectando a OBS: {e}")
            return False

    def disconnect(self):
        if self.ws:
            try:
                self.ws.disconnect()
            except:
                pass

    def is_running(self) -> bool:
        """Comprueba si OBS está corriendo (websocket responde)."""
        try:
            if not self.ws:
                return self.connect()
            self.ws.get_version()
            return True
        except:
            return False

    def get_version(self) -> str:
        try:
            version = self.ws.call(obs_requests.GetVersion())
            return f"OBS {version.getObsVersion()}"
        except:
            return "Desconocido"

    def get_status(self) -> dict:
        """Estado actual de OBS."""
        try:
            stats = self.ws.call(obs_requests.GetStats())
            return {
                "running": True,
                "version": self.get_version(),
                "active_profile": stats.getActiveProfile() if hasattr(stats, 'getActiveProfile') else "",
                "recording": self.is_recording(),
                "streaming": self.is_streaming(),
            }
        except Exception as e:
            return {"running": False, "error": str(e)}

    def is_recording(self) -> bool:
        try:
            status = self.ws.call(obs_requests.GetRecordStatus())
            return status.getOutputActive()
        except:
            return False

    def is_streaming(self) -> bool:
        try:
            status = self.ws.call(obs_requests.GetStreamStatus())
            return status.getOutputActive()
        except:
            return False

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
        except Exception as e:
            print(f"Error cambiando escena: {e}")
            return False

    def start_recording(self, scene: str = None) -> bool:
        """Inicia grabación. Opcionalmente cambia de escena."""
        try:
            if scene:
                self.set_scene(scene)

            # Configurar formato de grabación
            settings = self.ws.call(obs_requests.GetRecordSettings())
            # Usar settings por defecto de OBS

            self.ws.call(obs_requests.StartRecord())
            print(f"Grabación iniciada")
            return True
        except Exception as e:
            print(f"Error iniciando grabación: {e}")
            return False

    def stop_recording(self) -> str:
        """Para grabación y devuelve la ruta del archivo grabado."""
        try:
            self.ws.call(obs_requests.StopRecord())
            time.sleep(1)  # Esperar a que OBS termine de escribir

            # Obtener último archivo grabado
            replay = self.ws.call(obs_requests.GetLastReplayBufferReplay())
            if hasattr(replay, 'getSavedReplayPath'):
                return replay.getSavedReplayPath()

            # Fallback: buscar en la carpeta de grabaciones de OBS
            return self._find_last_recording()
        except Exception as e:
            print(f"Error parando grabación: {e}")
            return ""

    def _find_last_recording(self) -> str:
        """Busca el último archivo grabado en la carpeta de OBS."""
        try:
            settings = self.ws.call(obs_requests.GetRecordSettings())
            output_path = settings.getRecordPath()
            output_dir = Path(output_path) if output_path else Path.home() / "Videos"

            # Buscar archivos recientes
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

    def set_profile_settings(self, output_path: str = None):
        """Configura OBS para grabar en la ruta especificada."""
        try:
            if output_path:
                Path(output_path).mkdir(parents=True, exist_ok=True)
                self.ws.call(obs_requests.SetRecordSettings(
                    filenameFormatting=str(Path(output_path) / "%CCYY-%MM-%DD_%hh-%mm-%ss")
                ))
        except Exception as e:
            print(f"Error configurando OBS: {e}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    host = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_HOST
    port = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_PORT

    obs = OBSController(host, port)

    if not obs.connect():
        print("No se pudo conectar a OBS. ¿Está abierto con obs-websocket habilitado?")
        sys.exit(1)

    try:
        if command == "start":
            scene = sys.argv[4] if len(sys.argv) > 4 else None
            obs.start_recording(scene)

        elif command == "stop":
            output = obs.stop_recording()
            if output:
                print(f"Grabación guardada: {output}")
            else:
                print("Grabación parada (no se pudo obtener la ruta del archivo)")

        elif command == "status":
            status = obs.get_status()
            print(json.dumps(status, indent=2))

        elif command == "scenes":
            scenes = obs.get_scenes()
            for s in scenes:
                print(f"  - {s}")

        else:
            print(f"Comando desconocido: {command}")
            print(__doc__)
            sys.exit(1)

    finally:
        obs.disconnect()


if __name__ == "__main__":
    main()
