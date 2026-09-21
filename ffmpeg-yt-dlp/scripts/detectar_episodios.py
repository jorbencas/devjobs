#!/usr/bin/env python3
"""Detectar episodios/temporada o película mediante OCR de la franja superior.

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
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from collections import Counter


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES Y PATRONES
# ═══════════════════════════════════════════════════════════════════════════════

# Palabras que NO forman parte del título de una película (stop words en español)
# Se excluyen del conteo de frecuencias para extraer el título real.
STOP = {
    # Términos de episodios/temporadas (no son parte del título)
    "episodio", "episodios", "capitulo", "capitulos", "capítulo", "capítulos",
    "temporada", "temp", "pelicula", "peliculas", "película", "películas",
    # Artículos, preposiciones y conjunciones comunes en español
    "la", "el", "los", "las", "de", "en", "y", "a", "que",
}

# Patrones regex para detectar episodios en texto OCR.
# Ordenados de más específico a más general para priorizar coincidencias.
# Cada patrone extrae uno o dos grupos: (episodio) o (temporada, episodio).
PATRONES_EP = [
    r"s(\d+)e(\d+)",           # Formato TV clásico: S01E02 → temp=1, ep=2
    r"(\d+)x(\d+)",            # Formato alternativo: 1x02 → temp=1, ep=2
    r"(?:episodio|episodios|ep|cap[ií]tulo|cap|chapter)\s*(\d+)",
    # "Episodio 5", "EP 12", "Capítulo 3", "chapter 7"
    r"(\d+)\s*(?:episodio|episodios|ep|cap[ií]tulo|cap|chapter)",
    # "5 episodio", "12 EP" (número antes de la palabra)
    r"(?:ep|cap)\s*\.?\s*(\d+)",  # "EP. 1", "EP1", "CAP. 3" (abreviaturas con punto)
    r"#\s*(\d+)",              # "#1", "#23" (formato numérico directo)
    # FUZZY: permite caracteres que OCR confunde con dígitos
    # Ejemplo: "EP o" → "EP 0", "CAP lS" → "CAP 15"
    r"(?:episodio|ep|cap[ií]tulo|cap|chapter)\s*([0-9oOoIlLzZsS&BSb]{1,3})",
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
    'g': '9',                      # g → nueve (cierre circular)
}

# Patrones regex para detectar temporadas en texto OCR.
PATRONES_TEMP = [
    r"(?:temporada|temp|season)\s*(\d+)",    # "Temporada 2", "Temp 1", "Season 3"
    r"(\d+)\s*(?:temporada|temp|season)",    # "2 Temporada" (número primero)
    r"s(\d+)e",  # S01E02 → temporada 1 (extraído del patrón de episodios)
]


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════════════════════

def _fuzzy_a_digito(texto: str) -> int | None:
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


def _ocr_texto(img_path: Path) -> str:
    """Ejecuta OCR en 3 modos PSM y devuelve el resultado más relevante.

    Tesseract tiene diferentes modos de segmentación (PSM):
      - PSM 3: página completa (el más general)
      - PSM 6: bloque de texto uniforme
      - PSM 7: línea única de texto

    Cada modo puede funcionar mejor según la tipografía y disposición
    del texto en el frame. Se ejecutan los 3 y se queda el que tenga
    más coincidencias de patrones de episodios (heurística).

    Returns:
        Texto OCR con más patrones de episodios encontrados.
    """
    textos = []
    for psm in ("3", "7", "6"):
        try:
            ocr = subprocess.run(
                ["tesseract", str(img_path), "stdout", "-l", "eng",
                 "--psm", psm],
                capture_output=True, text=True)
            if ocr.stdout:
                textos.append(ocr.stdout)
        except Exception:
            pass
    if not textos:
        return ""
    if len(textos) == 1:
        return textos[0]

    # Puntuar cada pasada OCR por nº de coincidencias de patrones relevantes.
    # La pasada con más coincidencias es la que mejor leyó el texto.
    def _puntos(txt: str) -> int:
        bajo = txt.lower()
        pts = len(re.findall(r"(?:episodio|ep|cap[ií]tulo|cap|chapter)\s*\S{0,4}\d", bajo))
        pts += len(re.findall(r"\d\s*[xX]\s*\d", bajo))      # Formato 1x02
        pts += len(re.findall(r"[sS]\d+[eE]\d+", bajo))       # Formato S01E02
        pts += len(re.findall(r"(?:temporada|temp|season)\s*\d+", bajo))
        pts += len(re.findall(r"pel[ií]cula", bajo))
        pts += len(re.findall(r"#\s*\d+", bajo))              # Formato #1
        return pts
    return max(textos, key=_puntos)


def _preprocess_image(img_path: Path) -> Path:
    """Preprocesa la imagen para mejorar la precisión del OCR.

    Pipeline de preprocesamiento:
      1. Convertir a escala de grises (reduce ruido de color)
      2. Aumentar contraste (2x) para separar texto de fondo
      3. Aplicar filtro de nitidez (sharpen)
      4. Binarizar con umbral 128 (texto negro sobre fondo blanco)

    Si Pillow (PIL) no está disponible, usa ffmpeg como fallback:
      eq=contrast=1.5:brightness=0.1,unsharp=5:5:1.5

    Returns:
        Path de la imagen preprocesada (misma carpeta temporal).
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        img = Image.open(img_path)
        img = img.convert('L')  # Escala de grises
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)  # Duplicar contraste
        img = img.filter(ImageFilter.SHARPEN)  # Nitidez
        img = img.point(lambda x: 0 if x < 128 else 255)  # Binarizar
        processed_path = img_path.parent / f"proc_{img_path.name}"
        img.save(processed_path)
        return processed_path
    except ImportError:
        # Fallback: usar ffmpeg si Pillow no está instalado
        processed_path = img_path.parent / f"proc_{img_path.name}"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(img_path),
             "-vf", "eq=contrast=1.5:brightness=0.1,unsharp=5:5:1.5",
             str(processed_path)],
            capture_output=True)
        return processed_path
    except Exception:
        return img_path  # Si todo falla, usar imagen original


def _titulo_pelicula(palabras: Counter, muestras: int):
    """Extrae el título de una película del conteo de palabras OCR.

    Estrategia: las palabras que aparecen en >=25% de los frames son
    estables (el título real). El ruido del OCR es inestable (aparece
    y desaparece aleatoriamente).

    Returns:
        Título en mayúsculas, ej: "TITULO PELICULA".
    """
    umbral = max(3, int(muestras * 0.25))
    seleccion = {w for w, c in palabras.items() if w not in STOP and c >= umbral}
    orden = [w for w, c in palabras.most_common() if w in seleccion]
    return " ".join(orden).upper()


def _extraer_numeros(texto: str):
    """Extrae números de episodios y temporadas del texto OCR.

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
                num = _fuzzy_a_digito(m.group(1))
                if num is not None and 1 <= num <= 50:
                    temporadas.add(num)

    return episodios, temporadas


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
        lineas = [l.strip() for l in t.split("\n") if l.strip()]
        lineas_reales = [l for l in lineas if re.search(r"[a-zA-Záéíóúñü]", l)]
        if lineas_reales:
            textos_limpios.append(" ".join(lineas_reales))

    if not textos_limpios:
        return ""

    # Contar frecuencia y devolver el más común
    contador = Counter(textos_limpios)
    return contador.most_common(1)[0][0]


def __overlap_significativo(v1, v2, paso):
    """Comprueba si dos ventanas temporales se solapan significativamente.

    Se usa para filtrar outliers OCR: si un episodio espurio aparece
    en el mismo rango temporal que uno válido con 3x más muestras,
    se descarta el espurio.

    "Solape significativo" = el solape es >50% de la ventana más corta.

    Returns:
        True si el solape es significativo.
    """
    solap_ini = max(v1[0], v2[0])
    solap_fin = min(v1[1], v2[1])
    solap = max(0, solap_fin - solap_ini)
    dur_corta = min(v1[1] - v1[0], v2[1] - v2[0]) + paso
    if dur_corta <= 0:
        return False
    return solap > dur_corta * 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# DETECTOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def detectar(video: Path, paso: int, margen: int):
    """Detector principal de episodios/temporada/película.

    Flujo completo:
      1. Obtener duración del vídeo (ffprobe)
      2. Para cada frame cada `paso` segundos:
         a. Extraer franja superior (top 25%)
         b. Preprocesar imagen (mejorar OCR)
         c. Ejecutar OCR en 3 modos PSM
         d. Extraer episodios/temporadas con patrones regex
         e. Detectar si es película (palabra "película" en 2+ frames)
         f. Contar palabras para título de película
      3. Filtrar outliers OCR (solapamiento significativo)
      4. Calcular rango y descripción
      5. Calcular tiempos de corte (±margen del contenido)

    Returns:
        dict con episodios, rango, descripción, timestamps y corte.
    """
    dur = dur_video(video)
    if dur <= 0:
        return {"episodios": [], "rango": "", "primero": None, "ultimo": None}

    # Almacén de datos acumulados durante el escaneo
    episodios = {}     # num_ep -> [primero_ts, ultimo_ts, conteo_muestras]
    temporadas = {}    # num_temp -> [primero_ts, ultimo_ts]
    pelicula_times = []  # timestamps donde aparece "película"
    palabras = Counter() # palabra -> [conteo, primera_vez]
    textos_frames = []   # texto OCR crudo de cada frame (para elegir el mejor)
    muestras = 0
    tmpdir = Path(tempfile.mkdtemp(prefix="ep_"))
    n = 0
    t = 0
    try:
        while t < dur:
            img = tmpdir / f"f_{n}.png"
            try:
                # 1. Extraer frame: franja superior (25%) al doble de resolución
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", str(t), "-i", str(video),
                     "-frames:v", "1", "-vf", "crop=iw:ih*0.25:0:0,scale=iw*2:-1",
                     "-q:v", "2", str(img)],
                    capture_output=True, text=True, check=True)

                # 2. Preprocesar imagen para mejorar OCR
                proc_img = _preprocess_image(img)

                # 3. Ejecutar OCR (3 pasadas PSM, devuelve la mejor)
                texto = _ocr_texto(proc_img)
                texto_bajo = texto.lower()

                # Guardar texto crudo para elegir el más representativo
                textos_frames.append(texto.strip())

                # 4. Extraer episodios y temporadas del texto
                eps_en_frame, temps_en_frame = _extraer_numeros(texto)

                # Acumular episodios: guardar primera y última aparición
                for num in eps_en_frame:
                    if num not in episodios:
                        episodios[num] = [t, t, 1]
                    else:
                        episodios[num][1] = t  # Actualizar última aparición
                        episodios[num][2] += 1  # Incrementar conteo

                # Acumular temporadas
                for num in temps_en_frame:
                    if num not in temporadas:
                        temporadas[num] = [t, t]
                    else:
                        temporadas[num][1] = t

                # Detectar palabra "película" (para clasificar como película)
                if re.search(r"pel[ií]cula", texto_bajo):
                    pelicula_times.append(t)

                # Contar palabras para extraer título de película
                for w in re.finditer(r"[a-záéíóúñü]{3,}", texto_bajo):
                    w = w.group(0)
                    if w in STOP:
                        continue
                    if w in palabras:
                        palabras[w][0] += 1
                    else:
                        palabras[w] = [1, t]

                muestras += 1

                # Limpiar imagen procesada si es diferente a la original
                if proc_img != img:
                    try:
                        proc_img.unlink(missing_ok=True)
                    except OSError:
                        pass

            except Exception:
                pass  # Frames que fallan se saltan silenciosamente
            finally:
                try:
                    img.unlink(missing_ok=True)
                except OSError:
                    pass
            n += 1
            t = n * paso
    finally:
        try:
            tmpdir.rmdir()
        except OSError:
            pass

    # Clasificar: ¿es película o episodios?
    es_pelicula = len(pelicula_times) >= 2  # "película" apareció en 2+ frames

    if not episodios and not es_pelicula:
        return {"episodios": [], "rango": "", "primero": None, "ultimo": None}

    # Filtrar outliers OCR: un número mal leído aparece en pocas muestras
    # Y su ventana temporal SOLAPA con un episodio más estable.
    # Criterio: descartar si tiene 3x menos muestras Y solape >50%.
    if len(episodios) > 1:
        ordenados = sorted(episodios.items(), key=lambda kv: -kv[1][2])
        firmes = dict(ordenados[:1])  # El más frecuente siempre pasa
        for num, v in ordenados[1:]:
            dominado = any(
                w[2] >= 3 * v[2]
                and _overlap_significativo(v, w, paso)
                for w in firmes.values())
            if not dominado:
                firmes[num] = v
        episodios = firmes

    # Calcular rango y timestamps
    nums = sorted(episodios)
    primero = min(v[0] for v in episodios.values()) if episodios else min(pelicula_times)
    ultimo = max(v[1] for v in episodios.values()) if episodios else max(pelicula_times)
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


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Punto de entrada CLI: detectar_episodios.py <video> [paso] [margen]

    Argumentos:
        video:  Ruta al archivo de vídeo
        paso:   Segundos entre frames (default: 90)
        margen: Segundos de margen antes/después del contenido (default: 300)

    Salida: JSON a stdout con el resultado de la detección.
    """
    video = Path(sys.argv[1])
    paso = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    margen = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    print(json.dumps(detectar(video, paso, margen), ensure_ascii=False))


if __name__ == "__main__":
    main()
