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


def dur_video(video: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(video)],
            capture_output=True, text=True)
        return float(out.stdout.strip()) if out.stdout.strip() else 0.0
    except Exception:
        return 0.0


def _titulo_pelicula(palabras: Counter, muestras: int):
    """Construye el título con las palabras que aparecen en >=25% de los
    frames (el ruido del OCR no es estable, el título sí)."""
    umbral = max(3, int(muestras * 0.25))
    seleccion = {w for w, c in palabras.items() if w not in STOP and c >= umbral}
    orden = [w for w, c in palabras.most_common() if w in seleccion]
    return " ".join(orden).upper()


def detectar(video: Path, paso: int, margen: int):
    dur = dur_video(video)
    if dur <= 0:
        return {"episodios": [], "rango": "", "primero": None, "ultimo": None}

    episodios = {}
    temporadas = {}
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
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", str(t), "-i", str(video),
                     "-frames:v", "1", "-vf", "crop=iw:ih*0.2:0:0,scale=iw*2:-1",
                     "-q:v", "2", str(img)],
                    capture_output=True, text=True, check=True)
                ocr = subprocess.run(
                    ["tesseract", str(img), "stdout", "-l", "eng"],
                    capture_output=True, text=True)
                texto = ocr.stdout
                texto_bajo = texto.lower()
                for m in re.finditer(r"(?:episodio|cap[ií]tulo)\s*(\d+)", texto, re.IGNORECASE):
                    num = int(m.group(1))
                    if num not in episodios:
                        episodios[num] = [t, t]
                    else:
                        episodios[num][1] = t
                for m in re.finditer(r"(?:temporada|temp)[a-z]*\s*(\d+)", texto, re.IGNORECASE):
                    num = int(m.group(1))
                    if num not in temporadas:
                        temporadas[num] = [t, t]
                    else:
                        temporadas[num][1] = t
                if re.search(r"pel[ií]cula", texto_bajo):
                    pelicula_times.append(t)
                for w in re.finditer(r"[a-záéíóúñü]{3,}", texto_bajo):
                    w = w.group(0)
                    if w in STOP:
                        continue
                    if w in palabras:
                        palabras[w][0] += 1
                    else:
                        palabras[w] = [1, t]
                muestras += 1
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
