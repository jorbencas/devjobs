import cv2
import pytesseract
import subprocess
import tempfile
import time
import re
import json
from pathlib import Path

FUZZY_DIGIT = {
    'o': '0', 'O': '0', '}': '0', ']': '0', '{': '0', '[': '0',
    'l': '1', 'I': '1', 'i': '1', '|': '1', 'L': '1',
    'z': '2', 'Z': '2',
    's': '5', 'S': '5',
    '&': '8', 'B': '8', 'b': '8',
    'g': '9', 'q': '9',
}

PATRONES_EP = [
    r"s(\d+)e(\d+)",
    r"(\d+)x(\d+)",
    r"(?:episodio|episodios|ep|cap[ií]tulo|cap|chapter)\s*(\d+)",
    r"(\d+)\s*(?:episodio|episodios|ep|cap[ií]tulo|cap|chapter)",
    r"(?:ep|cap)\s*\.?\s*(\d+)",
    r"#\s*(\d+)",
    r"(?:temporada|temp|season)\s*(\d+)\s*[:\-]\s*(?:ep|ep\.?|ept|eft|epr|epi?)\s*(\d+)",
    r"(?:temporada|temp|season)\s*(\d+)\s*[:\-]\s*(\d+)",
    r"(?:\w+\s+)*(?:temporada|temp|season)\s*(\d+)\s*[:\-]\s*(?:ep|ep\.?|ept|eft|epr|epi?)\s*(\d+)",
    r"(?:\w+\s+)*(?:temporada|temp|season)\s*(\d+)\s*[:\-]\s*(\d+)",
    r"(?:ep|ep\.?|ept|eft|epr|epi?)\s*[:\-]?\s*(\d+)",
    r"(?:temporada|temp|season)\s*(\d+)\s*[:\-]\s*(?:ep|ep\.?|ept|eft|epr|epi?)\s+(\S+)",
    r"(?:\w+\s+)*(?:temporada|temp|season)\s*(\d+)\s*[:\-]\s*(?:ep|ep\.?|ept|eft|epr|epi?)\s+(\S+)",
    r"(?:ep|ep\.?|ept|eft|epr|epi?)\s+(\S+)",
]

def fuzzy_to_digit(text):
    if not text:
        return None
    limpio = ""
    for c in text:
        if c.isdigit():
            limpio += c
        elif c in FUZZY_DIGIT:
            limpio += FUZZY_DIGIT[c]
        else:
            return None
    try:
        num = int(limpio)
        return num if 1 <= num <= 999 else None
    except:
        return None

def extract_episodes(text):
    """Extract episodes from OCR text with space fixing."""
    # Fix spaced characters: "W I N X" -> "WINX"
    def fix_spaces(t):
        parts = t.split('  ')
        result = []
        for part in parts:
            cleaned = part.replace(' ', '')
            if cleaned:
                result.append(cleaned)
        return '  '.join(result)
    
    text = fix_spaces(text)
    
    episodios = set()
    temporadas = set()
    
    for patron in PATRONES_EP:
        for m in re.finditer(patron, text, re.IGNORECASE):
            groups = m.groups()
            if len(groups) == 2:
                try:
                    temp_num = int(groups[0])
                    ep_num = int(groups[1])
                    if 1 <= temp_num <= 50:
                        temporadas.add(temp_num)
                    if 1 <= ep_num <= 999:
                        episodios.add(ep_num)
                except ValueError:
                    try:
                        temp_num = int(groups[0])
                        if 1 <= temp_num <= 50:
                            temporadas.add(temp_num)
                    except:
                        pass
                    if groups[1]:
                        num = fuzzy_to_digit(groups[1][0])
                        if num:
                            episodios.add(num)
            else:
                if groups:
                    raw = groups[0]
                    digits = re.sub(r'[^\d]', '', raw)
                    if digits:
                        try:
                            num = int(digits)
                            if 1 <= num <= 999:
                                episodios.add(num)
                                continue
                        except:
                            pass
                    if raw:
                        num = fuzzy_to_digit(raw[0])
                        if num:
                            episodios.add(num)
    
    # Also check for "TEMPORADA" pattern
    for m in re.finditer(r"(?:temporada|temp|season)\s*(\d+)", text, re.IGNORECASE):
        try:
            num = int(m.group(1))
            if 1 <= num <= 50:
                temporadas.add(num)
        except:
            pass
    
    return episodios, temporadas

def process_video(video_path, max_time=30):
    """Process video for episode detection."""
    tmpdir = Path(tempfile.mkdtemp(prefix='ep_'))
    try:
        full_img = tmpdir / 'full.png'
        
        # Extract first frame
        subprocess.run([
            'ffmpeg', '-y', '-ss', '0', '-i', str(video_path), 
            '-frames:v', '1', '-q:v', '2', '-update', '1', str(full_img)
        ], capture_output=True, timeout=15)
        
        if not full_img.exists():
            return {"episodios": [], "rango": "", "primero": None, "ultimo": None}
        
        full_frame = cv2.imread(str(full_img))
        if full_frame is None:
            return {"episodios": [], "rango": "", "primero": None, "ultimo": None}
        
        h, w = full_frame.shape[:2]
        top_crop = full_frame[0:int(h*0.12), :]
        top_img = tmpdir / 'top.png'
        cv2.imwrite(str(top_img), top_crop)
        
        # Preprocess
        img = cv2.imread(str(top_img))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # OCR with OEM 0 (fast legacy)
        start = time.time()
        text = pytesseract.image_to_string(thresh, config='--psm 7 --oem 0 -l eng', timeout=10)
        elapsed = time.time() - start
        print(f"OCR took {elapsed:.2f}s: {repr(text)}")
        
        # If OEM 0 finds TEMPORADA/EPISODIO keywords, try OEM 2 for accuracy
        if any(kw in text.upper() for kw in ['TEMPORADA', 'EPISODIO', 'EPISODE', 'CAPITULO', 'CAPÍTULO']):
            start = time.time()
            text2 = pytesseract.image_to_string(thresh, config='--psm 7 --oem 2 -l eng', timeout=30)
            elapsed = time.time() - start
            print(f"OCR OEM 2 took {elapsed:.2f}s: {repr(text2)}")
            text = text2
        
        eps, temps = extract_episodes(text)
        
        if not eps:
            return {"episodios": [], "rango": "", "primero": None, "ultimo": None}
        
        nums = sorted(eps)
        return {
            "episodios": nums,
            "temporada": sorted(temps)[0] if temps else None,
            "rango": str(nums[0]) if len(nums) == 1 else f"{nums[0]}-{nums[-1]}",
            "primero": 0,
            "ultimo": 0,
        }
    except Exception as e:
        print(f"Error: {e}")
        return {"episodios": [], "rango": "", "primero": None, "ultimo": None}
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == "__main__":
    import sys
    video = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/app/data/pipeline/grabaciones/2026/09/sendosama_2026-09-24_22-07-21_KW_winx_club.mp4')
    result = process_video(video)
    print(json.dumps(result, ensure_ascii=False))
