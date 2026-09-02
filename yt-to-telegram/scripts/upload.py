#!/usr/bin/env python3
"""
upload.py — Sube vídeos convertidos a Telegram (grupo con temas).
Crea temas por canal y sube los vídeos.
"""
import json
import os
import subprocess
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("upload")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data/yt-pipeline"))
CONVERTED_DIR = DATA_DIR / "converted"
UPLOADED_DIR = DATA_DIR / "uploaded"
LOGS_DIR = DATA_DIR / "logs"

# Configuración de Telegram
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GROUP_ID = os.environ.get("TELEGRAM_GROUP_ID", "")
TOPICS_FILE = Path(__file__).parent.parent / "config" / "topics.json"

# Topics predefinidos (canal → topic_id)
# Se obtienen del grupo de Telegram existente
PREDEFINED_TOPICS = {
    "MoureDev": {"id": None, "name": "MoureDev"},
    "Midudev": {"id": None, "name": "Midudev"},
    "Carlos Azaustre": {"id": None, "name": "Carlos Azaustre"},
    "Linkfydev": {"id": None, "name": "Linkfydev"},
}

def load_topics():
    """Carga el mapping de canales a topics."""
    if TOPICS_FILE.exists():
        with open(TOPICS_FILE) as f:
            return json.load(f)
    return {}

def save_topics(topics):
    """Guarda el mapping de canales a topics."""
    with open(TOPICS_FILE, "w") as f:
        json.dump(topics, f, indent=2, ensure_ascii=False)

def get_topic_id(channel_name, topics):
    """Obtiene el topic_id para un canal."""
    # Buscar en topics predefinidos
    for key, topic in PREDEFINED_TOPICS.items():
        if key.lower() in channel_name.lower() or channel_name.lower() in key.lower():
            if topic["id"]:
                return topic["id"]
    
    # Buscar en topics existentes
    if channel_name in topics:
        return topics[channel_name]["id"]
    
    return None

def create_topic(channel_name, topics):
    """Crea un tema nuevo en el grupo de Telegram para un canal."""
    # Verificar si ya existe
    existing_id = get_topic_id(channel_name, topics)
    if existing_id:
        return existing_id
    
    logger.info(f"📝 Creando tema para canal: {channel_name}")
    
    # Usar la API de Telegram para crear el tema
    cmd = [
        "curl", "-s",
        "-X", "POST",
        f"https://api.telegram.org/bot{BOT_TOKEN}/createForumTopic",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({
            "chat_id": GROUP_ID,
            "name": channel_name[:128],  # Límite de Telegram
            "icon_color": 7322096  # Azul
        })
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        response = json.loads(result.stdout)
        
        if response.get("ok"):
            topic_id = response["result"]["message_thread_id"]
            topics[channel_name] = {
                "id": topic_id,
                "created_at": datetime.now().isoformat()
            }
            save_topics(topics)
            logger.info(f"  ✅ Tema creado: {channel_name} (ID: {topic_id})")
            return topic_id
        else:
            logger.error(f"  ❌ Error creando tema: {response.get('description', 'Unknown error')}")
            return None
    except Exception as e:
        logger.error(f"  ❌ Error creando tema: {e}")
        return None

def format_caption(video):
    """Formatea el caption con título y fecha de publicación."""
    title = video.get("title", video["filename"][:100])
    channel = video.get("channel", "Desconocido")
    publish_date = video.get("publish_date", "")
    
    caption = f"📺 <b>{title}</b>\n\n"
    caption += f"🔗 Canal: {channel}\n"
    
    if publish_date:
        caption += f"📅 Publicado: {publish_date}\n"
    
    return caption

def upload_video(video, topic_id):
    """Sube un vídeo a Telegram en un tema específico."""
    logger.info(f"⬆️  Subiendo: {video['filename'][:50]}...")
    
    caption = format_caption(video)
    
    # Usar telethon o python-telegram-bot para subir
    # Por ahora usamos curl como fallback
    cmd = [
        "curl", "-s",
        "-X", "POST",
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
        "-F", f"chat_id={GROUP_ID}",
        "-F", f"video=@{video['path']}",
        "-F", f"message_thread_id={topic_id}",
        "-F", f"caption={caption}",
        "-F", "parse_mode=HTML"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        response = json.loads(result.stdout)
        
        if response.get("ok"):
            logger.info(f"  ✅ Subido correctamente")
            return True
        else:
            logger.error(f"  ❌ Error subiendo: {response.get('description', 'Unknown error')}")
            return False
    except Exception as e:
        logger.error(f"  ❌ Error subiendo: {e}")
        return False

def move_to_uploaded(video):
    """Mueve un vídeo subido a la carpeta de históricos."""
    uploaded_channel_dir = UPLOADED_DIR / video["channel"]
    uploaded_channel_dir.mkdir(parents=True, exist_ok=True)
    
    source = Path(video["path"])
    destination = uploaded_channel_dir / video["filename"]
    
    if source.exists():
        source.rename(destination)
        logger.info(f"  📁 Movido a: {destination}")

def get_pending_videos():
    """Obtiene vídeos convertidos que aún no se han subido."""
    pending = []
    
    for channel_dir in CONVERTED_DIR.iterdir():
        if not channel_dir.is_dir():
            continue
        
        channel_name = channel_dir.name
        uploaded_channel_dir = UPLOADED_DIR / channel_name
        
        for video_file in channel_dir.glob("*.mp4"):
            # Verificar si ya se subió
            if uploaded_channel_dir.exists():
                uploaded_file = uploaded_channel_dir / video_file.name
                if uploaded_file.exists():
                    continue
            
            pending.append({
                "channel": channel_name,
                "path": str(video_file),
                "filename": video_file.name,
                "title": video_file.stem.replace("_", " ")[:100],
                "publish_date": video_file.stem.split("_")[0] if "_" in video_file.stem else ""
            })
    
    return pending

def main():
    """Función principal."""
    logger.info("🚀 Iniciando subida a Telegram")
    
    if not BOT_TOKEN or not GROUP_ID:
        logger.error("❌ BOT_TOKEN y TELEGRAM_GROUP_ID son requeridos")
        return
    
    # Crear directorios
    UPLOADED_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Cargar topics existentes
    topics = load_topics()
    
    # Obtener vídeos pendientes
    pending = get_pending_videos()
    logger.info(f"📹 {len(pending)} vídeos pendientes de subir")
    
    # Subir vídeos
    uploaded = []
    for video in pending:
        # Crear tema si no existe
        topic_id = create_topic(video["channel"], topics)
        if not topic_id:
            # Si no se puede crear tema, usar "General"
            logger.warning(f"  ⚠️  No se pudo crear tema para {video['channel']}, usando General")
            topic_id = get_topic_id("General", topics)
            if not topic_id:
                topic_id = create_topic("General", topics)
        
        # Subir vídeo
        if upload_video(video, topic_id):
            move_to_uploaded(video)
            uploaded.append(video)
    
    # Guardar log de subidas
    log_file = LOGS_DIR / f"uploads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w") as f:
        json.dump(uploaded, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ Subida completada: {len(uploaded)} vídeos")

if __name__ == "__main__":
    main()
