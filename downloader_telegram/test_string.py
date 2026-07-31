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
# --- RELLENA TUS DATOS AQUÍ ---
API_ID = '39937314'
API_HASH = 'be1b57db99dfe149a2a06db3b47d68c3'

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("\n✅ SESIÓN GENERADA CON ÉXITO:")
    print("--------------------------------------------------")
    print(client.session.save())
    print("--------------------------------------------------")
    print("\nCopia la cadena de arriba (es muy larga).")
    print("Esa es tu TELEGRAM_STRING_SESSION para los Secrets de GitHub.")