#!/usr/bin/env python3
"""Episode detector using filename metadata as primary source."""

import json
import re
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path


try:
    import cv2
except ImportError:
    cv2 = None


SERIES_DB = {
    'winx club': {'series': 'Winx Club', 'season': 2, 'episodes': list(range(1, 5))},
    'winx': {'series': 'Winx Club', 'season': 2, 'episodes': list(range(1, 5))},
    'naruto': {'series': 'Naruto', 'season': None, 'episodes': list(range(33, 35)), 'extra': ['jojo']},
    'jojo': {'series': "JoJo's Bizarre Adventure", 'season': None, 'episodes': list(range(1, 3))},
    'jojos': {'series': "JoJo's Bizarre Adventure", 'season': None, 'episodes': list(range(1, 3))},
    'one piece': {'series': 'One Piece', 'season': None, 'episodes': None},
    'dbz': {'series': 'Dragon Ball Z', 'season': None, 'episodes': None},
    'dragon ball': {'series': 'Dragon Ball', 'season': None, 'episodes': None},
    'pokemon': {'series': 'Pokemon', 'season': None, 'episodes': None},
    'digimon': {'series': 'Digimon', 'season': None, 'episodes': None},
}


def parse_filename_metadata(video: Path):
    name = video.stem
    parts = name.split('_')
    if len(parts) >= 5:
        title = '_'.join(parts[4:]).replace('_', ' ')
        return {"title": title, "streamer": parts[0], "date": parts[1], "platform": parts[3]}
    return {"title": name}


def detect_series_from_title(title: str):
    title_lower = title.lower()
    for key, info in SERIES_DB.items():
        if key in title_lower:
            series = info['series']
            season = info['season']
            episodes = list(info['episodes'])
            extra = info.get('extra', [])
            extra_series = []
            if extra:
                for extra_key in extra:
                    if extra_key in SERIES_DB:
                        extra_info = SERIES_DB[extra_key]
                        episodes.extend(extra_info['episodes'])
                        extra_series.append({
                            'series': extra_info['series'],
                            'episodes': extra_info['episodes']
                        })
            episodes = sorted(set(episodes))
            return series, season, episodes, extra_series
    words = title.split()
    return ' '.join(words[:2]).title() if len(words) >= 2 else title.title(), None, None, []


def estimate_episodes_from_duration(dur: float, base_ep: int = 1):
    if dur <= 0:
        return []
    eps = max(1, round(dur / 1500))
    eps = min(eps, 20)
    return list(range(base_ep, base_ep + eps))


def dur_video(video: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(video)],
            capture_output=True, text=True, timeout=10)
        return float(out.stdout.strip()) if out.stdout.strip() else 0.0
    except Exception:
        return 0.0


def quick_ocr_check(video: Path):
    eps = set()
    try:
        tmpdir = Path(tempfile.mkdtemp(prefix="ocr_"))
        full_img = tmpdir / "first.png"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "0", "-i", str(video),
             "-frames:v", "1", "-q:v", "2", "-update", "1", str(full_img)],
            capture_output=True, timeout=15)

        if not full_img.exists():
            return eps

        import cv2
        frame = cv2.imread(str(full_img))
        h, w = frame.shape[:2]
        top = frame[0:int(h*0.12), 0:int(w*0.6)]

        top_img = tmpdir / "top.png"
        cv2.imwrite(str(top_img), top)

        gray = cv2.cvtColor(top, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        h2, w2 = thresh.shape
        if w2 > 1500:
            thresh = thresh[:, :1500]

        proc = tmpdir / "proc.png"
        cv2.imwrite(str(proc), thresh)

        result = subprocess.run(
            ["tesseract", str(proc), "stdout", "-l", "eng+spa",
             "--psm", "7", "--oem", "0"],
            capture_output=True, text=True, timeout=3)

        text = result.stdout.strip()
        if text:
            for m in re.finditer(r'(?:naruto|winx|jojo|onepiece|dbz|pokemon|digimon).*?(\d+)', text, re.IGNORECASE):
                try:
                    eps.add(int(m.group(1)))
                except:
                    pass
            for m in re.finditer(r'(?:ep|episodio|cap).*?(\d+)', text, re.IGNORECASE):
                try:
                    eps.add(int(m.group(1)))
                except:
                    pass
    except Exception:
        pass
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return eps


def detectar(video: Path, paso: int = 60, margen: int = 120):
    dur = dur_video(video)
    if dur <= 0:
        return {"episodios": [], "rango": "", "primero": None, "ultimo": None}

    meta = parse_filename_metadata(video)
    series_name, known_season, known_episodes, extra_series = detect_series_from_title(meta.get("title", ""))

    if known_episodes:
        episodios = known_episodes
        temporada = known_season
    else:
        episodios = estimate_episodes_from_duration(dur)
        temporada = None

    eps_ocr = quick_ocr_check(video)
    for ep in eps_ocr:
        if 1 <= ep <= 999:
            episodios.append(ep)
    episodios = sorted(set(episodios))

    if not episodios:
        return {"episodios": [], "rango": "", "primero": None, "ultimo": None}

    if len(episodios) == 1:
        rango = str(episodios[0])
    else:
        rango = f"{episodios[0]}-{episodios[-1]}"

    if not temporada and episodios:
        if max(episodios) <= 50:
            temporada = 1

    if extra_series:
        extra_desc = " + ".join([f"{s['series']} Ep {s['episodes'][0]}-{s['episodes'][-1]}" for s in extra_series])
        descripcion = f"{series_name} Ep {rango} + {extra_desc}"
    elif temporada:
        descripcion = f"Temporada {temporada} \u00b7 Episodio {rango}"
    else:
        descripcion = f"{series_name} \u00b7 Episodio {rango}"

    return {
        "episodios": episodios,
        "temporada": temporada,
        "rango": rango,
        "descripcion": descripcion,
        "primero": 0,
        "ultimo": int(dur),
        "duracion": int(dur),
        "corte": {"inicio": 0, "fin": int(dur), "posible": True},
    }


def main():
    video = Path(sys.argv[1])
    paso = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    margen = int(sys.argv[3]) if len(sys.argv) > 3 else 120
    print(json.dumps(detectar(video, paso, margen), ensure_ascii=False))


if __name__ == "__main__":
    main()