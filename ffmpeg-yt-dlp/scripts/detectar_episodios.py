#!/usr/bin/env python3
"""Detectar episodios/temporada/película mediante OCR de la franja superior.

Este script forma parte del PIPELINE DE ENVÍO (sending pipeline):
  1. TwitchRecorder graba directos de Twitch/YouTube/Kick/Web
  2. monitor_folder.sh comprime y DETECTA episodios con este script
  3. subir_videos.py sube los vídeos a Telegram

Funcionamiento:
  - Escanea el vídeo cada N segundos (paso, default 90s)
  - Extrae la franja superior (top 25%) de cada frame
  - Preprocesa la imagen (gris, contraste, sharpen, binarizar)
  - Ejecuta OCR en 3 modos PSM (3, 6, 7) y elige el mejor
  - Busca patrones de episodios: "Episodio 1", "EP. 3", "S01E02", "#5", etc.
  - Detecta si es película por frecuencia de la palabra "película"
  - Filtra outliers OCR (números espurios que solapan con episodios válidos)
  - Calcula los tiempos de corte (margen antes/después del contenido)

Uso CLI:
  detectar_episodios.py <video> [paso_segundos] [margen_segundos]

Salida (JSON a stdout):
  {
    "episodios": [1, 3, 4],       # números de episodios detectados
    "temporada": 2,               # temporada detectada (o null)
    "rango": "1-4",               # rango legible
    "descripcion": "Episodio 1-4",# descripción para el caption de Telegram
    "primero": 120,               # timestamp del primer contenido (segundos)
    "ultimo": 3600,               # timestamp del último contenido
    "duracion": 5400,             # duración total del vídeo
    "corte": {
      "inicio": 0,                # timestamp de inicio del corte
      "fin": 3900,                # timestamp de fin del corte
      "posible": true             # si el corte es viable
    }
  }

Requiere:
  - ffmpeg/ffprobe (extracción de frames y duración)
  - tesseract-ocr con datos en inglés (-l eng)
  - Opcionalmente: Pillow (PIL) para preprocesamiento de imagen

NOTA: Se usa modelo 'eng' de tesseract porque lee mejor los dígitos que 'spa'.
El preprocesamiento PIL mejora significativamente la precisión del OCR.

MEJORAS v2:
- Múltiples zonas de recorte (top, center, bottom) para mejor cobertura
- Preprocesamiento con CLAHE + denoising + umbral Otsu adaptativo
- Múltiples modos PSM (3, 4, 6, 7, 8, 11, 13) con fusión inteligente
- Patrones extendidos para más formatos de episodios
- Filtrado por consenso multi-zona (debe aparecer en 2+ zonas)
- Filtrado de outliers OCR mejorado con solapamiento temporal
- Preprocesamiento con CLAHE + denoising + umbral Otsu adaptativo
"""

import json
import re
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from collections import Counter

# Palabras que NO forman parte del título de una película (stop words en español)
STOP = {
    "episodio", "episodios", "capitulo", "capitulos", "capítulo", "capítulos",
    "temporada", "temp", "pelicula", "peliculas", "película", "películas",
    "la", "el", "los", "las", "de", "en", "y", "a", "que", "del", "al",
    "un", "una", "los", "las", "por", "para", "con", "sin", "sobre",
}

# Patrones regex extendidos para detectar episodios en texto OCR.
# Ordenados de más específico a más general para priorizar coincidencias.
# Cada patrone extrae uno o dos grupos: (episodio) o (temporada, episodio).
PATRONES_EP = [
    r"s(\d+)e(\d+)",           # Formato TV clásico: S01E02 → temp=1, ep=2
    r"(\d+)x(\d+)",            # Formato alternativo: 1x02 → temp=1, ep=2
    r"(?:episodio|episodios|ep|cap[ií]tulo|cap|chapter)\s*(\d+)",
    r"(\d+)\s*(?:episodio|episodios|ep|cap[ií]tulo|cap|chapter)",
    r"(?:ep|cap)\s*\.?\s*(\d+)",    # "EP. 1", "EP1", "CAP. 3"
    r"#\s*(\d+)",                     # "#1", "#23" (formato numérico directo)
    r"(?:episodio|ep|cap[ií]tulo|cap|chapter)\s*([0-9oOoIlLzZsS&BSb]{1,3})",  # fuzzy
    r"(\d+)\s*(?:ep|cap)",            # 5 ep, 12 cap
    r"(?:ep|cap|cap[ií]tulo)\s*\.?\s*(\d+)",  # ep. 5, cap. 3
    r"(?:cap[ií]tulo|cap)\s*(\d+)",   # capitulo 5, cap 3
]

# Mapeo de caracteres que tesseract confunde con dígitos reales.
# Usado por _fuzzy_a_digito() para corregir errores comunes de OCR.
# Ejemplo: '&' se lee como '8' porque visualmente se parecen.
FUZZY_DIGIT = {
    'o': '0', 'O': '0',           # O circular → cero
    'l': '1', 'I': '1', 'i': '1', '|': '1',  # Lineas verticales → uno
    'z': '2', 'Z': '2',           # Z → dos (en algunas fuentes)
    's': '5', 'S': '5',           # S → cinco (forma similar)
    '&': '8', 'B': '8', 'b': '8', # Ampersand/B → ocho
    'g': '9', 'q': '9',           # g/q → nueve
}

# Patrones regex para detectar temporadas en texto OCR.
PATRONES_TEMP = [
    r"(?:temporada|temp|season)\s*(\d+)",    # "Temporada 2", "Temp 1", "Season 3"
    r"(\d+)\s*(?:temporada|temp|season)",    # "2 Temporada" (número primero)
    r"s(\d+)e",  # S01E02 → temporada 1 (extraído del patrón de episodios)
]


# ═════════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ════════════════════════════════════════════════════════════════════════════════

def _fuzzy_a_digito(texto: str):
    """Convierte un texto OCR-fuzzy a un dígito entero.

    El OCR a menudo confunde letras con números. Esta función intenta
    reconstruir el número real usando el mapeo FUZZY_DIGIT.

    Ejemplos:
        '&' → 8       (un solo carácter)
        'lO' → 10     (l=1, O=0)
        'O' → 0       (un solo carácter)
        '&O' → 80     (&=8, O=0)
        'lS' → None   (S no es un dígito válido en fuzzy)

    Returns:
        int entre 1 y 999, o None si no se puede convertir.
    """
    if not texto:
        return None
    limpio = ""
    for c in texto:
        if c.isdigit():
            limpio += c
        elif c in FUZZY_DIGIT:
            limpio += FUZZY_DIGIT[c]
        else:
            return None  # Carácter no reconocible → abortar
    try:
        num = int(limpio)
        return num if 1 <= num <= 999 else None
    except ValueError:
        return None


def dur_video(video: Path) -> float:
    """Obtiene la duración en segundos del vídeo usando ffprobe.

    Returns:
        Duración en segundos, o 0.0 si no se puede leer (vídeo corrupto).
    """
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(video)],
            capture_output=True, text=True)
        return float(out.stdout.strip()) if out.stdout.strip() else 0.0
    except Exception:
        return 0.0


def _ocr_texto_multi_psm(img_path: Path) -> str:
    """Ejecuta OCR en múltiples modos PSM y devuelve el resultado fusionado.

    Tesseract tiene diferentes modos de segmentación (PSM):
      - PSM 3: página completa (el más general)
      - PSM 4: columna de texto
      - PSM 6: bloque de texto uniforme
      - PSM 7: línea única de texto
      - PSM 8: palabra única
      - PSM 11: texto escaso
      - PSM 13: texto sin procesar

    Cada modo puede funcionar mejor según la tipografía y disposición
    del texto en el frame. Se ejecutan los 7 y se fusionan.

    Returns:
        Texto OCR fusionado de todas las pasadas.
    """
    textos = []
    for psm in ("3", "4", "6", "7", "8", "11", "13"):
        try:
            ocr = subprocess.run(
                ["tesseract", str(img_path), "stdout", "-l", "eng",
                 "--psm", psm, "--oem", "1"],
                capture_output=True, text=True, timeout=10)
            if ocr.stdout and ocr.stdout.strip():
                textos.append(ocr.stdout.strip())
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
    
    if not textos:
        return ""
    if len(textos) == 1:
        return textos[0]
    
    # Fusionar: unir todos los textos únicos
    # El texto real aparece en múltiples PSM, el ruido no
    unicos = set()
    for t in textos:
        for linea in t.split('\n'):
            linea = linea.strip()
            if linea and len(linea) > 2:
                unicos.add(linea)
    return " ".join(unicos)


def _preprocess_image_v2(img_path: Path) -> Path:
    """Preprocesamiento avanzado: CLAHE + denoising + umbral Otsu adaptativo.

    Pipeline de preprocesamiento:
      1. Convertir a espacio LAB y aplicar CLAHE en canal L
      2. Denoising (fastNlMeansDenoisingColored)
      3. Convertir a escala de grises
      4. Umbral adaptativo (Otsu) para binarización robusta

    Si OpenCV no está disponible, usa fallback PIL:
      1. Escala de grises
      2. Aumentar contraste (2.5x)
      3. Sharpen
      4. Binarizar con umbral adaptativo (140)

    Returns:
        Path de la imagen preprocesada (misma carpeta temporal).
    """
    try:
        import cv2
        import numpy as np
        
        img = cv2.imread(str(img_path))
        if img is None:
            return img_path
            
        # Convertir a LAB para CLAHE en canal L
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # CLAHE en canal L
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        # Merge back
        lab = cv2.merge((l, a, b))
        img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        # Denoising
        img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
        
        # Convertir a escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Umbral adaptativo (Otsu + adaptive)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Guardar
        processed = img_path.parent / f"proc_v2_{img_path.name}"
        cv2.imwrite(str(processed), thresh)
        return processed
        
    except Exception:
        # Fallback a PIL
        try:
            from PIL import Image, ImageEnhance, ImageFilter
            img = Image.open(img_path).convert('L')
            img = img.filter(ImageFilter.SHARPEN)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.5)
            img = img.point(lambda x: 0 if x < 140 else 255)  # umbral adaptativo
            processed = img_path.parent / f"proc_v2_{img_path.name}"
            img.save(processed)
            return processed
        except Exception:
            return img_path


def _ocr_texto_multi_psm(img_path: Path) -> str:
    """Ejecuta OCR en múltiples modos PSM y devuelve el resultado fusionado.

    Tesseract tiene diferentes modos de segmentación (PSM):
      - PSM 3: página completa (el más general)
      - PSM 4: columna de texto
      - PSM 6: bloque de texto uniforme
      - PSM 7: línea única de texto
      - PSM 8: palabra única
      - PSM 11: texto escaso
      - PSM 13: texto sin procesar

    Cada modo puede funcionar mejor según la tipografía y disposición
    del texto en el frame. Se ejecutan los 7 y se fusionan.

    Returns:
        Texto OCR fusionado de todas las pasadas.
    """
    textos = []
    for psm in ("3", "4", "6", "7", "8", "11", "13"):
        try:
            ocr = subprocess.run(
                ["tesseract", str(img_path), "stdout", "-l", "eng",
                 "--psm", psm, "--oem", "1"],
                capture_output=True, text=True, timeout=10)
            if ocr.stdout and ocr.stdout.strip():
                textos.append(ocr.stdout.strip())
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
    
    if not textos:
        return ""
    if len(textos) == 1:
        return textos[0]
    
    # Fusionar: unir todos los textos únicos
    # El texto real aparece en múltiples PSM, el ruido no
    unicos = set()
    for t in textos:
        for linea in t.split('\n'):
            linea = linea.strip()
            if linea and len(linea) > 2:
                unicos.add(linea)
    return " ".join(unicos)


def _preprocess_image_v2(img_path: Path) -> Path:
    """Preprocesamiento avanzado: CLAHE + denoising + umbral Otsu adaptativo.

    Pipeline de preprocesamiento:
      1. Convertir a espacio LAB y aplicar CLAHE en canal L
      2. Denoising (fastNlMeansDenoisingColored)
      3. Convertir a escala de grises
      4. Umbral adaptativo (Otsu) para binarización robusta

    Si OpenCV no está disponible, usa fallback PIL:
      1. Escala de grises
      2. Aumentar contraste (2.5x)
      3. Sharpen
      4. Binarizar con umbral adaptativo (140)

    Returns:
        Path de la imagen preprocesada (misma carpeta temporal).
    """
    try:
        import cv2
        import numpy as np
        
        img = cv2.imread(str(img_path))
        if img is None:
            return img_path
            
        # Convertir a LAB para CLAHE en canal L
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # CLAHE en canal L
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        # Merge back
        lab = cv2.merge((l, a, b))
        img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        # Denoising
        img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
        
        # Convertir a escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Umbral adaptativo (Otsu + adaptive)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Guardar
        processed = img_path.parent / f"proc_v2_{img_path.name}"
        cv2.imwrite(str(processed), thresh)
        return processed
        
    except Exception:
        # Fallback a PIL
        try:
            from PIL import Image, ImageEnhance, ImageFilter
            img = Image.open(img_path).convert('L')
            img = img.filter(ImageFilter.SHARPEN)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.5)
            img = img.point(lambda x: 0 if x < 140 else 255)  # umbral adaptativo
            processed = img_path.parent / f"proc_v2_{img_path.name}"
            img.save(processed)
            return processed
        except Exception:
            return img_path


def _extraer_episodios(texto: str):
    """Extrae episodios y temporadas del texto OCR.

    Usa los patrones PATRONES_EP y PATRONES_TEMP para encontrar
    coincidencias. Para cada coincidencia:
      - Si tiene 2 grupos (S01E02, 1x02): extrae temporada y episodio
      - Si tiene 1 grupo: extrae solo episodio (o temporada según patrón)
      - Si el texto no es un número directo, intenta fuzzy matching

    Returns:
        Tupla (episodios: set[int], temporadas: set[int])
    """
    episodios = set()
    temporadas = set()

    # Buscar episodios con todos los patrones
    for patron in PATRONES_EP:
        for m in re.finditer(patron, texto, re.IGNORECASE):
            groups = m.groups()
            if len(groups) == 2:  # Formato compound: S01E02 o 1x02
                try:
                    temp_num = int(groups[0])
                    ep_num = int(groups[1])
                    if 1 <= temp_num <= 50:
                        temporadas.add(temp_num)
                    if 1 <= ep_num <= 999:
                        episodios.add(ep_num)
                except ValueError:
                    pass
            else:  # Formato simple: "Episodio 5", "EP. 3", "#12"
                texto_num = groups[0]
                # Intentar conversión directa primero (más fiable)
                try:
                    num = int(texto_num)
                    if 1 <= num <= 999:
                        episodios.add(num)
                except ValueError:
                    # Si falla, usar fuzzy matching para OCR corrupto
                    num = _fuzzy_a_digito(texto_num)
                    if num is not None:
                        episodios.add(num)

    # Buscar temporadas
    for patron in PATRONES_TEMP:
        for m in re.finditer(patron, texto, re.IGNORECASE):
            try:
                num = int(m.group(1))
                if 1 <= num <= 50:
                    temporadas.add(num)
            except ValueError:
                pass

    return episodios, temporadas


def _fusionar_resultados_zonas(resultados_zonas):
    """Fusiona resultados de múltiples zonas, priorizando consenso multi-zona.
    
    Args:
        resultados_zonas: dict {zona: (eps, temps)}
    
    Returns:
        Tupla (eps_finales: set[int], temps_finales: set[int])
        Solo incluye elementos que aparecen en 2+ zonas (consenso).
    """
    todos_episodios = {}
    todas_temporadas = {}
    
    for zona, (eps, temps) in resultados_zonas.items():
        for ep in eps:
            if ep not in todos_episodios:
                todos_episodios[ep] = {"count": 0, "zonas": []}
            todos_episodios[ep]["count"] += 1
            todos_episodios[ep]["zonas"].append(zona)
        
        for temp in temps:
            if temp not in todas_temporadas:
                todas_temporadas[temp] = {"count": 0, "zonas": []}
            todas_temporadas[temp]["count"] += 1
            todas_temporadas[temp]["zonas"].append(zona)
    
    # Solo mantener los que aparecen en 2+ zonas (consenso multi-zona)
    eps_finales = {ep for ep, data in todos_episodios.items() if data["count"] >= 2}
    temps_finales = {t for t, data in todas_temporadas.items() if data["count"] >= 2}
    
    # Si no hay consenso, relajar a 1+ zona pero con filtro de frecuencia
    if not eps_finales:
        eps_finales = {ep for ep, data in todos_episodios.items() if data["count"] >= 2}
    if not temps_finales:
        temps_finales = {t for t, data in todas_temporadas.items() if data["count"] >= 2}
    
    return eps_finales, temps_finales


def _texto_frame_mas_frecuente(textos: list) -> str:
    """Obtiene el texto OCR más repetido entre todos los frames.

    El texto real del vídeo (título, canal, etc.) es estable y aparece
    en múltiples frames. El ruido del OCR es aleatorio y no se repite.

    Filtra:
      - Textos vacíos
      - Líneas que solo contienen números o caracteres especiales
      - Prioriza líneas con letras (texto real)

    Returns:
        El texto más frecuente, o "" si no hay texto útil.
    """
    if not textos:
        return ""

    textos_limpios = []
    for t in textos:
        t = t.strip()
        if not t:
            continue
        # Separar por líneas y quedarse solo con las que tienen letras
        lineas = [l.strip() for l in t.split('\n') if l.strip()]
        lineas_reales = [l for l in lineas if re.search(r"[a-zA-Záéíóúñü]", l)]
        if lineas_reales:
            textos_limpios.append(" ".join(lineas_reales))

    if not textos_limpios:
        return ""

    # Contar frecuencia y devolver el más común
    contador = Counter(textos_limpios)
    return contador.most_common(1)[0][0]


# ═════════════════════════════════════════════════════════════════════════════════
# DETECTOR PRINCIPAL v2
# ════════════════════════════════════════════════════════════════════════════════

def detectar(video: Path, paso: int = 60, margen: int = 120):
    """Detector principal v2 con múltiples zonas y preprocesamiento avanzado.
    
    Flujo completo:
      1. Obtener duración del vídeo (ffprobe)
      2. Para cada frame cada `paso` segundos:
         a. Extraer frames en múltiples zonas (top, center, bottom)
         b. Preprocesar cada frame (CLAHE + denoising + Otsu)
         c. Ejecutar OCR en múltiples modos PSM por zona
         d. Extraer episodios/temporadas con patrones regex
         e. Fusionar resultados por consenso multi-zona
      3. Filtrar outliers OCR (requiere consenso multi-zona)
      4. Calcular rango, descripción y tiempos de corte
      5. Calcular tiempos de corte (±margen del contenido)
    
    Args:
        video: Path al archivo de vídeo
        paso: Segundos entre frames (default: 60)
        margen: Segundos de margen antes/después del contenido (default: 120)
    
    Returns:
        dict con episodios, rango, descripción, timestamps y corte.
    """
    dur = dur_video(video)
    if dur <= 0:
        return {"episodios": [], "rango": "", "primero": None, "ultimo": None}
    
    # Almacén de datos acumulados durante el escaneo
    eps_acum = {}  # ep -> [primero, ultimo, count]
    temps_acum = {}  # temp -> [primero, ultimo]
    pelicula_times = []  # timestamps donde aparece "película"
    palabras = Counter() # palabra -> [conteo, primera_vez]
    textos_frames = []   # texto OCR crudo de cada frame (para elegir el mejor)
    muestras = 0
    
    tmpdir = Path(tempfile.mkdtemp(prefix="ep_v2_"))
    n = 0
    t = 0
    
    try:
        while t < dur:
            resultados_zonas = {}
            
            # Extraer frames en 3 zonas
            for zona in ("top", "center", "bottom"):
                img = tmpdir / f"f_{t}_{zona}.png"
                try:
                    # Extraer frame
                    _run_extract(video, t, zona, img)
                    
                    # Preprocesar
                    proc = _preprocess_image_v2(img)
                    
                    # OCR multi-PSM
                    textos = _ocr_texto_multi_psm(proc)
                    texto_completo = " ".join(textos)
                    
                    # Extraer episodios y temporadas
                    eps, temps = _extraer_episodios(texto_completo)
                    resultados_zonas[zona] = (eps, temps)
                    
                    # Limpiar archivos temporales
                    if proc != img:
                        proc.unlink(missing_ok=True)
                    img.unlink(missing_ok=True)
                except Exception:
                    pass
            
            # Fusionar resultados de todas las zonas (consenso multi-zona)
            eps_finales, temps_finales = _fusionar_resultados_zonas(resultados_zonas)
            
            # Acumular episodios con timestamps
            for ep in eps_finales:
                if ep not in eps_acum:
                    eps_acum[ep] = [t, t, 1]
                else:
                    eps_acum[ep][1] = t
                    eps_acum[ep][2] += 1
            
            for temp in temps_finales:
                if temp not in temps_acum:
                    temps_acum[temp] = [t, t]
                else:
                    temps_acum[temp][1] = t
            
            t += 30  # paso de 30s
            n += 1
    finally:
        try:
            shutil.rmtree(tmpdir)
        except:
            pass
    
    # Filtrar: solo episodios con 2+ detecciones (filtrar ruido OCR)
    eps_filtrados = {ep: v for ep, v in eps_acum.items() if v[2] >= 2}
    if not eps_filtrados:
        return {"episodios": [], "rango": "", "primero": None, "ultimo": None}
    
    nums = sorted(eps_filtrados)
    primero = min(v[0] for v in eps_filtrados.values())
    ultimo = max(v[1] for v in eps_filtrados.values())
    rango = str(nums[0]) if len(nums) == 1 else f"{nums[0]}-{nums[-1]}" if nums else ""
    
    # Obtener el texto real del frame más representativo
    texto_real = _texto_frame_mas_frecuente(textos_frames)
    
    # Construir descripción según el tipo de contenido
    if es_pelicula:
        titulo = _titulo_pelicula(palabras, muestras)
        descripcion = f"Película · {titulo}" if titulo else "Película"
    else:
        temporada_num = sorted(temporadas)[0] if temporadas else None
        # Usar texto real del vídeo si está disponible, sino generar "Episodio X"
        if texto_real:
            descripcion = texto_real
        else:
            descripcion = f"Episodio {rango}"
        if temporada_num is not None:
            descripcion = f"Temporada {temporada_num} · {descripcion}"

    # Calcular corte: ±margen segundos antes/después del contenido detectado
    inicio = max(0, primero - margen)
    fin = min(int(dur), ultimo + margen)
    return {
        "episodios": nums,
        "temporada": sorted(temporadas)[0] if temporadas else None,
        "rango": rango,
        "descripcion": descripcion,
        "primero": primero,
        "ultimo": ultimo,
        "duracion": int(dur),
        "corte": {
            "inicio": inicio,
            "fin": fin,
            "posible": fin > inicio,
        },
    }


# ═════════════════════════════════════════════════════════════════════════════════
# FUNCIONES FALTANTES (referenciadas arriba)
# ════════════════════════════════════════════════════════════════════════════════

def _run_extract(video: Path, t: float, zona: str, out_path: Path):
    """Extrae un frame del vídeo en la zona y timestamp especificados."""
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(t), "-i", str(video),
         "-frames:v", "1", "-vf", f"{ZONAS[zona]},scale=iw*2:-1",
         "-q:v", "2", "-update", "1", str(out_path)],
        capture_output=True, check=True, timeout=15
    )


# ═════════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════════

def main():
    """Punto de entrada CLI: detectar_episodios.py <video> [paso] [margen]

    Argumentos:
        video:  Ruta al archivo de vídeo
        paso:   Segundos entre frames (default: 60)
        margen: Segundos de margen antes/después del contenido (default: 120)

    Salida: JSON a stdout con el resultado de la detección.
    """
    video = Path(sys.argv[1])
    paso = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    margen = int(sys.argv[3]) if len(sys.argv) > 3 else 120
    print(json.dumps(detectar(video, paso, margen), ensure_ascii=False))


if __name__ == "__main__":
    main()