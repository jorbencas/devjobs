# ==============================================================================
# INSTRUCCIONES:
# 1. Ve a my.telegram.org -> "API development tools" -> Crea una app.
# 2. Obtendrás api_id y api_hash. Cópialos cuando el script los pida.
# 3. El script creará 'ultimate_session.session' para no pedir login cada vez.
# ==============================================================================

#Notas importantes:
#El archivo .session: Telegram crea un archivo llamado ultimate_session.session. Este archivo ya contiene el token de acceso. Si quieres máxima seguridad, asegúrate de que nadie tenga acceso a ese archivo tampoco.
#getpass en IDEs: Si usas PyCharm o VS Code, a veces la consola interna no soporta getpass correctamente y parece que "se queda trabada". Si eso pasa, simplemente escribe y dale a Enter (aunque no veas nada), o ejecuta el script directamente en la terminal de Windows/Linux.
#Backup: Si borras secret.key, no podrás recuperar el config_segura.bin. ¡Guarda bien esa llave!


import os, sys, json, asyncio, subprocess, getpass, platform
from datetime import datetime
# --- INSTALADOR AUTOMÁTICO DE SISTEMA Y LIBRERÍAS ---
def sistema_auto_setup():
    print("[*] Verificando entorno y dependencias...")
    
    # Lista de librerías Python necesarias
    libs = ["telethon", "mtranslate", "cryptography", "cryptg"]
    
    # 1. Intentar instalar dependencias de sistema si es Linux (Ubuntu)
    if platform.system().lower() == "linux":
        try:
            # Verificamos si tenemos pip, si no, intentamos instalarlo
            subprocess.check_call(["python3", "-m", "pip", "--version"], stdout=subprocess.DEVNULL)
        except:
            print("[!] Pip no detectado. Instalando dependencias de sistema...")
            subprocess.check_call(["sudo", "apt", "update", "-y"])
            subprocess.check_call(["sudo", "apt", "install", "-y", "python3-pip", "python3-venv"])

    # 2. Instalar librerías de Python
    for lib in libs:
        try:
            __import__(lib if lib != "cryptography" else "feather") # Verificación simple
        except ImportError:
            print(f"[+] Instalando librería: {lib}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

# Ejecutar el instalador antes de cargar lo demás
sistema_auto_setup()

from telethon import TelegramClient, errors, events
from mtranslate import translate
from cryptography.fernet import Fernet

# --- CONFIGURACIÓN GLOBAL ---
CONFIG_FILE = 'config.bin'
CARPETA_BASE = 'Descargas_Telegram'
# Lista negra de spam y contenido inadecuado
SPAM_LIST = ["crypto", "ganar dinero", "casino", "poker", "estafa", "bet", "sex", "porn", "gore", "nude"]
# --- GESTIÓN DE LLAVE ---
# En un entorno real, la KEY debería ser una variable de entorno del sistema
# o guardarse en un archivo separado muy protegido.
KEY_FILE = "secret.key"

def cargar_o_generar_llave():
    if os.path.exists(KEY_FILE):
        return open(KEY_FILE, "rb").read()
    else:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        return key

# --- SISTEMA DE LOGS EN TIEMPO REAL ---
def log(tipo, mensaje):
    iconos = {"INFO": "ℹ️", "OK": "✅", "WARN": "⚠️", "ERR": "❌", "DB": "🚀", "SPAM": "🚫", "TRAD": "📝"}
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {iconos.get(tipo, '🔹')} {mensaje}")

# --- MÓDULO DE INTELIGENCIA (FILTRO Y TRADUCCIÓN) ---
def procesar_texto_inteligente(texto, activar_traduccion=False):
    if not texto: return None
    
    # Filtro de Spam/Indeseado
    if any(word in texto.lower() for word in SPAM_LIST):
        return "FILTERED_CONTENT"
    
    # Traducción automática
    if activar_traduccion:
        try:
            return translate(texto, "es")
        except:
            return texto
    return texto

# --- LÓGICA DE DESCARGA ROBUSTA (CON RESUME) ---
async def download_media_robust(client, message, folder):
    if not message or not message.media: return False
    
    file_name = message.file.name if message.file.name else f"file_{message.id}{message.file.ext}"
    full_path = os.path.join(folder, file_name)
    temp_path = full_path + ".part"

    if os.path.exists(full_path):
        log("INFO", f"Ya existe: {file_name}")
        return True

    try:
        log("DB", f"Bajando: {file_name}")
        # 'wb' es mejor para descargas multihilo (Turbo)
        with open(temp_path, 'wb') as f:
            def prog(c, t):
                print(f"    -> {file_name}: {(c/t)*100:.1f}%", end='\r')
            await client.download_media(message, file=f, progress_callback=prog)
        os.rename(temp_path, full_path)
        print() # Limpiar línea de progreso
        log("OK", f"Completado: {file_name}")
        return True
    except Exception as e:
        log("ERR", f"Fallo en descarga {file_name}: {e}")
        return False


async def modulo_descarga_masiva(client):
    log("INFO", "Iniciando Módulo de Descarga Masiva")
    print("\na) Enlace Único\nb) Rango de IDs (Ej: 100-200)\nc) Procesar enlaces.txt")
    sub_op = input("\nSelecciona: ").lower()
    trad = input("¿Traducir textos detectados? (s/n): ").lower() == 's'
    enlaces = []
    if sub_op == 'a':
        enlaces.append(input("Pega el enlace: ").strip())
    elif sub_op == 'b':
        if os.path.exists('enlaces.txt'):
            with open('enlaces.txt', 'r') as f:
                enlaces = [l.strip() for l in f if l.strip()]
        else:
            log("ERR", "No se encontró enlaces.txt")

    folder = os.path.join(CARPETA_BASE, "Masivo")
    os.makedirs(folder, exist_ok=True)

    peer_cache = {} # Para acelerar la resolución de canales
    for link in enlaces:
        try:
            partes = link.split('/')
            msg_id = int(partes[-1].split('?')[0])
            peer_str = partes[-2]
            
            # Si el canal no está en caché, lo buscamos
            if peer_str not in peer_cache:
                target = int('-100' + peer_str) if '/c/' in link else peer_str
                peer_cache[peer_str] = await client.get_input_entity(target)

            msg = await client.get_messages(peer_cache[peer_str], ids=msg_id) 
            if not msg: continue

            texto_listo = procesar_texto_inteligente(msg.text, trad)            
            if texto_listo == "FILTERED_CONTENT":
                log("SPAM", f"Mensaje {msg_id} bloqueado por filtro.")
                continue
            
            if trad and texto_listo: log("TRAD", f"ID {msg_id}: {texto_listo[:60]}...")
            if msg.media:
                await download_media_robust(client, msg, folder)
        except Exception as e:
            log("ERR", f"Error en enlace {link}: {e}")

async def modulo_clonacion(client):
    origen = input("ID/Username del canal ORIGEN: ")
    destino = input("ID/Username del canal DESTINO: ")
    limite = int(input("¿Cuántos mensajes clonar?: "))
    descargar = input("¿Descargar multimedia también? (s/n): ").lower() == 's'
    trad = input("¿Traducir contenido al clonar? (s/n): ").lower() == 's'
    
    cola_descarga = []
    log("INFO", f"Clonando {limite} mensajes...")

    async for message in client.iter_messages(origen, limit=limite, reverse=True):
        try:
            texto = procesar_texto_inteligente(message.text, trad)
            if texto == "FILTERED_CONTENT":
                log("SPAM", f"Saltando ID {message.id} (Contenido inadecuado)")
                continue

            # Clonar mensaje (si hay traducción, enviamos el texto traducido)
            if trad and texto:
                await client.send_message(destino, texto, file=message.media if not descargar else None)
            else:
                await client.send_message(destino, message)

            if descargar and message.media:
                cola_descarga.append(message)
            
            log("OK", f"Clonado ID: {message.id}")
            await asyncio.sleep(0.8)
        except Exception as e:
            log("ERR", f"Error en ID {message.id}: {e}")

    if descargar and cola_descarga:
        log("INFO", f"Se encontraron {len(cola_descarga)} archivos en la cola.")
        if input("¿Procesar descarga ahora? (s/n): ").lower() == 's':
            folder = os.path.join(CARPETA_BASE, "Clonados")
            os.makedirs(folder, exist1_ok=True)
            for msg in cola_descarga:
                await download_media_robust(client, msg, folder)

async def modulo_filtro_vigilante(client):
    log("INFO", "Modo Vigilante Activo. Ctrl+C para salir.")
    palabras = input("Palabras clave extra para alertas (separadas por coma): ").lower().split(',')
    
    @client.on(events.NewMessage)
    async def handler(event):
        texto = event.message.message
        # Usamos el filtro inteligente automático + palabras extra
        if procesar_texto_inteligente(texto) == "FILTERED_CONTENT" or any(p in texto.lower() for p in palabras):
            log("SPAM", f"¡Contenido detectado en un chat! -> {texto[:50]}...")
            await client.send_message('me', f"🔔 Alerta Vigilante:\n{texto}")

    await client.run_until_disconnected()

# --- INTERFAZ CLI PRINCIPAL ---
async def main():
    if not os.path.exists(CARPETA_BASE): os.makedirs(CARPETA_BASE)
    key = cargar_o_generar_llave()
    cipher = Fernet(key)
    def load_config():
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'rb') as f: 
                datos_cifrados = f.read()
                datos_planos = cipher.decrypt(datos_cifrados).decode('utf-8')
                return json.loads(datos_planos)
        return None

    config = load_config()
    if not config:
        print("\n--- CONFIGURACIÓN INICIAL ---")
        aid = input("API ID: ")
        ahash = getpass.getpass("API HASH (no se verá lo que escribas): ")
        config = json.dumps({'api_id': aid, 'api_hash': ahash})
        contenido_cifrado = cipher.encrypt(config.encode())
        with open(CONFIG_FILE, 'wb') as f:
            f.write(contenido_cifrado)

    client = TelegramClient(StringSession(), int(config['api_id']), config['api_hash'])
    
    try:
        # start() maneja: Teléfono -> Código -> Contraseña (2FA) automáticamente
        log("INFO", "Iniciando cliente... Si pide contraseña (2FA), escríbela en la terminal.")
        await client.start(phone=lambda: phone) 
        log("OK", "Conexión establecida con éxito.")
       # --- PARCHE DE SINCRONIZACIÓN ---
        # Forzamos una petición al servidor para que la sesión se rellene internamente
        await client.get_me() 
        
        # 2. Intentamos guardar la sesión
        session_string = client.session.save()
        
        if not session_string:
            # Reintento manual si el save() inicial falló
            log("WARN", "Sincronizando sesión manualmente...")
            # Accedemos al valor interno de la sesión si Telethon se pone terco
            if client.session.auth_key:
                session_string = client.session.save()

        if session_string:
            print(f"\n{'='*45}")
            log("OK", "¡SESIÓN CAPTURADA!")
            print(f"{'='*45}\n")
            print(session_string) # Aquí ya NO saldrá None
            print(f"\n{'='*45}")
            log("INFO", "Copia todo el texto de arriba para tus Secrets de GitHub.")
        else:
            log("ERR", "No se pudo generar el string. Verifica que el código fue correcto.")
    except errors.SessionPasswordNeededError:
        # Este error ocurre si client.start() no pudo pedirla por alguna razón o si usas una versión manual
        print("\n[!] Verificación en dos pasos activada.")
        pwd_2fa = getpass.getpass("Introduce tu contraseña de Cloud Password: ")
        await client.sign_in(password=pwd_2fa)
        log("OK", "Contraseña 2FA aceptada.")
    except Exception as e:
        log("ERR", f"Error crítico al iniciar sesión: {e}")
        return

    while True:
        print(f"\n{'='*45}\n   TELEGRAM ULTIMATE TOOLBOX CLI\n{'='*45}")
        print("1. Descargas Masivas (Enlace/Rango/TXT)")
        print("2. Clonación & Backup (Filtro + Traducción)")
        print("3. Modo Vigilante (Alertas por palabras)")
        print("4. Re-configurar / Salir")
        
        choice = input("\nOpción > ")

        if choice == '1':
            await modulo_descarga_masiva(client)
        elif choice == '2':
            await modulo_clonacion(client)
        elif choice == '3':
            try:
                await modulo_filtro_vigilante(client)
            except KeyboardInterrupt:
                log("INFO", "Modo Vigilante detenido.")
        elif choice == '4':
            log("INFO", "Cerrando sistema...")
            break

    await client.disconnect()

def save_config(api_id, api_hash):
    with open(CONFIG_FILE, 'w') as f: json.dump({'api_id': api_id, 'api_hash': api_hash}, f)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[!] Script finalizado por el usuario.")