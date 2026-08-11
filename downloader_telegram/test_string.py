from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os, sys, subprocess, platform

# --- TU SISTEMA DE INSTALACIÓN ---
def sistema_auto_setup():
    print("[*] Verificando entorno y dependencias para la sesión...")
    
    # Para generar la sesión solo necesitamos telethon
    libs = ["telethon"]
    
    if platform.system().lower() == "linux":
        try:
            subprocess.check_call(["python3", "-m", "pip", "--version"], stdout=subprocess.DEVNULL)
        except:
            print("[!] Pip no detectado. Instalando...")
            subprocess.check_call(["sudo", "apt", "update", "-y"])
            subprocess.check_call(["sudo", "apt", "install", "-y", "python3-pip"])

    for lib in libs:
        try:
            __import__(lib)
        except ImportError:
            print(f"[+] Instalando librería: {lib}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

# Ejecutar instalador
sistema_auto_setup()

def load_credentials():
    api_id = os.environ.get("API_ID")
    api_hash = os.environ.get("API_HASH")
    if api_id and api_hash:
        return api_id, api_hash
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("API_ID="):
                    api_id = line.split("=", 1)[1].strip()
                elif line.startswith("API_HASH="):
                    api_hash = line.split("=", 1)[1].strip()
        if api_id and api_hash:
            return api_id, api_hash
    api_id = input("API_ID: ").strip()
    api_hash = input("API_HASH: ").strip()
    return api_id, api_hash

API_ID, API_HASH = load_credentials()

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("\n✅ SESIÓN GENERADA CON ÉXITO:")
    print("--------------------------------------------------")
    print(client.session.save())
    print("--------------------------------------------------")
    print("\nCopia la cadena de arriba (es muy larga).")
    print("Esa es tu TELEGRAM_STRING_SESSION para los Secrets de GitHub.")