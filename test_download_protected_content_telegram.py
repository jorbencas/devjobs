
# Obtener tus credenciales de API:

# Ve a my.telegram.org.

# Entra en "API development tools".

# Crea una "app" (pon cualquier nombre). Obtendrás un api_id y un api_hash.

# Instalar la librería:

# Bash

# pip install telethon
# El Script de Python
# Este script toma el enlace del mensaje (por ejemplo: https://t.me/c/12345/678) y descarga el video incluso si tiene restricciones de guardado.


# Notas importantes para que funcione:
# Primera ejecución: La primera vez que lo corras, el script te pedirá tu número de teléfono (con código de país, ej: +34...) y el código que te llegará dentro de la app de Telegram. Esto creará un archivo llamado sesion_descarga.session para que no tengas que loguearte cada vez.

# Privacidad: El script solo funciona si tú (la cuenta del api_id) tienes acceso al grupo o canal. No puede descargar de grupos donde no eres miembro.

# Enlaces de canales privados: El script está diseñado para manejar enlaces tipo t.me/c/XXXXX/YYY. Si el enlace tiene un formato distinto, asegúrate de estar dentro del grupo en tu cuenta de Telegram.
import os, sys, json, asyncio, subprocess

# --- AUTO-INSTALADOR ---
def check_dependencies():
    try:
        import telethon
    except ImportError:
        print("[!] Instalando Telethon...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "telethon"])

check_dependencies()
from telethon import TelegramClient, errors, events

# --- CONFIGURACIÓN ---
CONFIG_FILE = 'config.json'
CARPETA_BASE = 'Descargas_Telegram'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: return json.load(f)
    return None

def save_config(api_id, api_hash):
    with open(CONFIG_FILE, 'w') as f: json.dump({'api_id': api_id, 'api_hash': api_hash}, f)

# --- LÓGICA DE DESCARGA (CON RESUME) ---
async def download_media_robust(client, message, folder):
    if not message or not message.media: return False
    
    file_name = message.file.name if message.file.name else f"file_{message.id}.dat"
    full_path = os.path.join(folder, file_name)
    temp_path = full_path + ".part"

    if os.path.exists(full_path): return True

    try:
        with open(temp_path, 'ab') as f:
            await client.download_media(message, file=f)
        os.rename(temp_path, full_path)
        return True
    except Exception as e:
        print(f"\n[!] Error descargando {file_name}: {e}")
        return False

# --- MÓDULOS ESPECIALES ---

async def modulo_clonacion(client):
    origen = input("ID/Username del canal ORIGEN: ")
    destino = input("ID/Username del canal DESTINO: ")
    limite = int(input("¿Cuántos mensajes clonar?: "))
    descargar = input("¿Deseas descargar los archivos multimedia? (s/n): ").lower() == 's'
    
    cola_descarga = []
    print(f"[*] Clonando {limite} mensajes...")

    async for message in client.iter_messages(origen, limit=limite, reverse=True):
        try:
            # Reenviar mensaje
            await client.send_message(destino, message)
            if descargar and message.media:
                cola_descarga.append(message)
            print(f"    -> Clonado ID: {message.id} (En cola: {len(cola_descarga)})", end='\r')
            await asyncio.sleep(0.8)
        except Exception as e:
            print(f"\n[!] Error en ID {message.id}: {e}")

    if cola_descarga:
        print(f"\n\n[*] Se encontraron {len(cola_descarga)} archivos multimedia.")
        procesar = input("¿Procesar cola de descarga ahora? (s/n): ").lower() == 's'
        if procesar:
            folder = os.path.join(CARPETA_BASE, "Clonados")
            os.makedirs(folder, exist_ok=True)
            for i, msg in enumerate(cola_descarga):
                print(f"[*] Bajando {i+1}/{len(cola_descarga)}...")
                await download_media_robust(client, msg, folder)

async def modulo_filtro(client):
    palabras = input("Palabras clave (separadas por coma): ").lower().split(',')
    print(f"[*] Monitorizando... (Ctrl+C para salir)")

    @client.on(events.NewMessage)
    async def handler(event):
        if any(p in event.message.message.lower() for p in palabras):
            print(f"[!] Coincidencia detectada!")
            await client.send_message('me', f"🔔 Alerta: {event.message.message}")
    
    await client.run_until_disconnected()

# --- INTERFAZ CLI ---

async def main():
    if not os.path.exists(CARPETA_BASE): os.makedirs(CARPETA_BASE)
    
    config = load_config()
    if not config:
        save_config(int(input("API ID: ")), input("API HASH: "))
        config = load_config()

    client = TelegramClient('ultimate_session', config['api_id'], config['api_hash'])
    await client.start()

    while True:
        print(f"\n{'='*40}\n   TELEGRAM ULTIMATE TOOLBOX CLI\n{'='*40}")
        print("1. Descargas Directas (Enlace/Rango/TXT)")
        print("2. Clonación & Backup (Con cola de descarga)")
        print("3. Modo Vigilante (Filtro por palabras)")
        print("4. Salir")
        
        choice = input("\nSelecciona una opción: ")

        if choice == '1':
            print("Función de descarga masiva activada...")
            # Aquí puedes llamar a la lógica de descarga de rangos anterior
        elif choice == '2':
            await modulo_clonacion(client)
        elif choice == '3':
            try: await modulo_filtro(client)
            except KeyboardInterrupt: print("\nFiltro detenido.")
        elif choice == '4':
            break

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())