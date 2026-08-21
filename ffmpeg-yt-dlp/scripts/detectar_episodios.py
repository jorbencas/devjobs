#!/usr/bin/env python3
"""Detectar episodios/temporada o película (texto de la franja superior) de un vídeo.

Uso:
  detectar_episodios.py <video> [paso] [margen]

Escanea el vídeo con un paso de N segundos, hace OCR de la franja superior y:
  - Si aparece 'EPISODIO/CAPÍTULO N' (opcionalmente con 'TEMPORADA N' delante),
    recoge el primer y último instante en que aparece.
  - Si aparece la palabra 'película', captura el título de la franja por
    frecuencia de palabras y usa ese intervalo para el corte.

Salida: JSON a stdout con:
  {
    "episodios": [1, 3, 4] o [],
    "temporada": 2 o null,
    "rango": "1-4",
    "descripcion": "Episodio 1-4" | "Temporada 2 · Episodio 1-4" | "Película · Título",
    "primero": <ts>,      # primer instante con contenido
    "ultimo": <ts>,       # último instante con contenido
    "corte": {"inicio": <ts>, "fin": <ts>, "posible": bool}
  }

Requiere ffmpeg/ffprobe y tesseract-ocr con datos en inglés (-l eng).
NOTA: el modelo spa de tesseract lee peor los dígitos en alpine; eng es
más fiable.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from collections import Counter

# Palabras que no forman parte del título de una película
STOP = {
    "episodio", "episodios", "capitulo", "capitulos", "capítulo", "capítulos",
    "temporada", "temp", "pelicula", "peliculas", "película", "películas",
    "la", "el", "los", "las", "de", "en", "y", "a", "que",
}

# Patrones para detectar episodios (más flexibles)
# Incluye fuzzy para errores comunes de OCR: 8→&, 1→l/I, 0→O, 5→S, etc.
PATRONES_EP = [
    r"(?:episodio|ep|cap[ií]tulo|cap|chapter)\s*(\d+)",
    r"(\d+)\s*(?:episodio|ep|cap[ií]tulo|cap|chapter)",
    r"s(\d+)e(\d+)",  # S01E02 format
    r"(\d+)x(\d+)",   # 1x02 format
    # Fuzzy: permite caracteres que OCR confunde con dígitos
    r"(?:episodio|ep|cap[ií]tulo|cap|chapter)\s*([0-9oOoIlLzZsS&BSb]{1,3})",
]

# Mapeo de caracteres OCR confundidos → dígito real
FUZZY_DIGIT = {
    'o': '0', 'O': '0', 'o': '0',
    'l': '1', 'I': '1', 'i': '1', '|': '1',
    'z': '2', 'Z': '2',
    's': '5', 'S': '5',
    '&': '8', 'B': '8', 'b': '8',
    'g': '9',
}


def _fuzzy_a_digito(texto: str) -> int | None:
    """Convierte un texto OCR-fuzzy a un dígito entero.
    Ej: '&' → 8, 'lO' → 10, 'O' → 0, '&O' → 80."""
    if not texto:
        return None
    limpio = ""
    for c in texto:
        if c.isdigit():
            limpio += c
        elif c in FUZZY_DIGIT:
            limpio += FUZZY_DIGIT[c]
        else:
            return None  # Carácter no reconocible
    try:
        num = int(limpio)
        return num if 1 <= num <= 999 else None
    except ValueError:
        return None

# Patrones para detectar temporadas
PATRONES_TEMP = [
    r"(?:temporada|temp|season)\s*(\d+)",
    r"(\d+)\s*(?:temporada|temp|season)",
    r"s(\d+)e",  # S01E02 → temporada 1
]


def dur_video(video: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(video)],
            capture_output=True, text=True)
        return float(out.stdout.strip()) if out.stdout.strip() else 0.0
    except Exception:
        return 0.0


def _ocr_texto(img_path: Path) -> str:
    """OCR en 2 pasadas: normal (PSM 3) y línea única (PSM 7).
    Devuelve el texto con más coincidencias de patrones de episodio,
    lo que mitiga tipografías raras que confunden una de las pasadas."""
    textos = []
    for psm in ("3", "7"):
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
    # Puntuar: nº de coincidencias de patrones ep/temp/película
    def _puntos(txt: str) -> int:
        bajo = txt.lower()
        pts = len(re.findall(r"(?:episodio|ep|cap[ií]tulo|cap|chapter)\s*\S{0,4}\d", bajo))
        pts += len(re.findall(r"\d\s*[xX]\s*\d", bajo))
        pts += len(re.findall(r"[sS]\d+[eE]\d+", bajo))
        pts += len(re.findall(r"(?:temporada|temp|season)\s*\d+", bajo))
        pts += len(re.findall(r"pel[ií]cula", bajo))
        return pts
    return max(textos, key=_puntos)


def _preprocess_image(img_path: Path) -> Path:
    """Preprocesa la imagen para mejorar OCR: escala de grises, contraste, umbralización."""
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        img = Image.open(img_path)
        # Convertir a escala de grises
        img = img.convert('L')
        # Aumentar contraste
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        # Aplicar filtro de nitidez
        img = img.filter(ImageFilter.SHARPEN)
        # Umbralización para binarizar
        img = img.point(lambda x: 0 if x < 128 else 255)
        # Guardar imagen preprocesada
        processed_path = img_path.parent / f"proc_{img_path.name}"
        img.save(processed_path)
        return processed_path
    except ImportError:
        # Si PIL no está disponible, usar ffmpeg para preprocesar
        processed_path = img_path.parent / f"proc_{img_path.name}"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(img_path),
             "-vf", "eq=contrast=1.5:brightness=0.1,unsharp=5:5:1.5",
             str(processed_path)],
            capture_output=True)
        return processed_path
    except Exception:
        return img_path


def _titulo_pelicula(palabras: Counter, muestras: int):
    """Construye el título con las palabras que aparecen en >=25% de los
    frames (el ruido del OCR no es estable, el título sí)."""
    umbral = max(3, int(muestras * 0.25))
    seleccion = {w for w, c in palabras.items() if w not in STOP and c >= umbral}
    orden = [w for w, c in palabras.most_common() if w in seleccion]
    return " ".join(orden).upper()


def _extraer_numeros(texto: str):
    """Extrae números de episodios y temporadas del texto OCR.
    Maneja errores comunes de OCR con fuzzy matching."""
    episodios = set()
    temporadas = set()
    
    # Buscar episodios con múltiples patrones
    for patron in PATRONES_EP:
        for m in re.finditer(patron, texto, re.IGNORECASE):
            groups = m.groups()
            if len(groups) == 2:  # Formato S01E02 o 1x02
                try:
                    temp_num = int(groups[0])
                    ep_num = int(groups[1])
                    if 1 <= temp_num <= 50:
                        temporadas.add(temp_num)
                    if 1 <= ep_num <= 999:
                        episodios.add(ep_num)
                except ValueError:
                    pass
            else:  # Formato simple - puede ser fuzzy
                texto_num = groups[0]
                # Intentar conversión directa primero
                try:
                    num = int(texto_num)
                    if 1 <= num <= 999:
                        episodios.add(num)
                except ValueError:
                    # Si falla, usar fuzzy matching
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


def detectar(video: Path, paso: int, margen: int):
    dur = dur_video(video)
    if dur <= 0:
        return {"episodios": [], "rango": "", "primero": None, "ultimo": None}

    episodios = {}  # num -> [primero, ultimo, muestras]
    temporadas = {}  # num -> [primero, ultimo]
    pelicula_times = []        # instantes donde aparece la palabra 'película'
    palabras = Counter()       # palabra -> [conteo, primera_aparicion]
    muestras = 0
    tmpdir = Path(tempfile.mkdtemp(prefix="ep_"))
    n = 0
    t = 0
    try:
        while t < dur:
            img = tmpdir / f"f_{n}.png"
            try:
                # Extraer frame de la franja superior
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", str(t), "-i", str(video),
                     "-frames:v", "1", "-vf", "crop=iw:ih*0.2:0:0,scale=iw*2:-1",
                     "-q:v", "2", str(img)],
                    capture_output=True, text=True, check=True)
                
                # Preprocesar imagen para mejorar OCR
                proc_img = _preprocess_image(img)
                
                # Ejecutar OCR (2 pasadas: PSM 3 y PSM 7, se queda la mejor)
                texto = _ocr_texto(proc_img)
                texto_bajo = texto.lower()
                
                # Extraer episodios y temporadas
                eps_en_frame, temps_en_frame = _extraer_numeros(texto)
                
                for num in eps_en_frame:
                    if num not in episodios:
                        episodios[num] = [t, t, 1]
                    else:
                        episodios[num][1] = t
                        episodios[num][2] += 1
                
                for num in temps_en_frame:
                    if num not in temporadas:
                        temporadas[num] = [t, t]
                    else:
                        temporadas[num][1] = t
                
                if re.search(r"pel[ií]cula", texto_bajo):
                    pelicula_times.append(t)
                
                # Contar palabras para detectar título de película
                for w in re.finditer(r"[a-záéíóúñü]{3,}", texto_bajo):
                    w = w.group(0)
                    if w in STOP:
                        continue
                    if w in palabras:
                        palabras[w][0] += 1
                    else:
                        palabras[w] = [1, t]
                
                muestras += 1
                
                # Limpiar imagen procesada si es diferente
                if proc_img != img:
                    try:
                        proc_img.unlink(missing_ok=True)
                    except OSError:
                        pass
                        
            except Exception:
                pass
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

    es_pelicula = len(pelicula_times) >= 2

    if not episodios and not es_pelicula:
        return {"episodios": [], "rango": "", "primero": None, "ultimo": None}

    # Filtrar outliers OCR: un número mal leído ("9" que luego se corrige a
    # "8") o un dígito espurio aparece en pocas muestras Y su ventana temporal
    # SOLAPA con la de un episodio más estable (el error ocurre mientras el
    # banner real está visible). Episodios distintos nunca solapan.
    if len(episodios) > 1:
        ordenados = sorted(episodios.items(), key=lambda kv: -kv[1][2])
        firmes = dict(ordenados[:1])
        for num, v in ordenados[1:]:
            dominado = any(
                w[2] >= 2 * v[2]
                and v[0] <= w[1] + paso and w[0] <= v[1] + paso
                for w in firmes.values())
            if not dominado:
                firmes[num] = v
        if set(firmes) != set(episodios):
            episodios = firmes

    nums = sorted(episodios)
    primero = min(v[0] for v in episodios.values()) if episodios else min(pelicula_times)
    ultimo = max(v[1] for v in episodios.values()) if episodios else max(pelicula_times)
    rango = str(nums[0]) if len(nums) == 1 else f"{nums[0]}-{nums[-1]}" if nums else ""

    if es_pelicula:
        titulo = _titulo_pelicula(palabras, muestras)
        descripcion = f"Película · {titulo}" if titulo else "Película"
    else:
        temporada_num = sorted(temporadas)[0] if temporadas else None
        descripcion = f"Episodio {rango}"
        if temporada_num is not None:
            descripcion = f"Temporada {temporada_num} · {descripcion}"

    # Recorte de 5 min antes del primer contenido y 5 min después del último,
    # recortado a los límites reales del vídeo para que el corte siempre sea posible.
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


def main():
    video = Path(sys.argv[1])
    paso = int(sys.argv[2]) if len(sys.argv) > 2 else 180
    margen = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    print(json.dumps(detectar(video, paso, margen), ensure_ascii=False))


if __name__ == "__main__":
    main()
