# 🥷 devjobs: Ultimate Automation Suite

Repositorio de herramientas avanzadas para la gestión de activos digitales, automatización de Telegram y procesamiento de documentos legales.

---

## 🛠️ Herramientas del Ecosistema

### 1. `desproteger_pdf.py` (PDF Ninja Master)
Herramienta definitiva para liberar y optimizar certificados o títulos académicos.
* **Desbloqueo Híbrido**: Sistema de doble intento. Si falla el acceso rápido (`PyMuPDF`), activa el acceso profundo (`pikepdf`).
* **Salto Inteligente**: Detecta archivos ya procesados en la carpeta de salida para evitar duplicar trabajo.
* **Unión Interactiva**: Permite elegir el orden de unión uno a uno (modo "carrito") o realizar una unión alfabética total.
* **Compresión y Limpieza**: Reduce el peso de los archivos (ideal para pasar de 21MB a tamaños menores) sin romper la validez del documento.
* **Interfaz Persistente**: Logs de colores que no se borran para poder auditar el peso inicial y final de cada archivo.

### 2. `test_download_protected_content_telegram.py` (The Collector)
Script robusto para la extracción y respaldo de contenido en Telegram.
* **Clonación & Backup**: Copia canales enteros con opción de traducción automática al español mediante `mtranslate`.
* **Filtro Vigilante**: Sistema de alertas por palabras clave y limpieza automática de Spam/Contenido indeseado.
* **Descarga con Resumen**: Gestión de descargas pesadas con barra de progreso y verificación de integridad.
* **Seguridad AES**: Almacena tus credenciales (API ID/Hash) de forma cifrada en un archivo binario.

### 3. `test_string.py` (Session Generator)
Generador de sesiones portátiles para entornos volátiles.
* **StringSession**: Genera una cadena de texto única que permite ejecutar los scripts en la nube (GitHub Actions, Heroku, etc.) sin necesidad de arrastrar archivos `.session`.

---

## 📦 Protocolo de Instalación

Todos los scripts incluyen un sistema de **Auto-Setup**. Al ejecutarlos por primera vez, detectarán tu sistema operativo (Windows/Linux) e instalarán las dependencias necesarias automáticamente:

```bash
# Para gestionar tus documentos PDF
python desproteger_pdf.py

# Para iniciar el recolector de Telegram
python test_download_protected_content_telegram.py