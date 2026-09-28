import cv2
import subprocess
import tempfile
from pathlib import Path
import json
import re
from collections import Counter

# This will be the new OCR approach for the detectar_episodios.py

def extract_text_from_frame(frame, region='top'):
    """Extract text from a frame using robust OCR."""
    h, w = frame.shape[:2]
    
    if region == 'top':
        crop = frame[0:int(h*0.12), 0:int(w*0.6)]
    elif region == 'mid':
        crop = frame[int(h*0.35):int(h*0.65), 0:int(w*0.6)]
    else:
        crop = frame[int(h*0.85):h, 0:int(w*0.6)]
    
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    
    # Best preprocessing found: Otsu threshold
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Save to temp file
    tmpdir = Path(tempfile.mkdtemp(prefix='ocr_'))
    try:
        img_path = tmpdir / 'frame.png'
        cv2.imwrite(str(img_path), thresh)
        
        # Run tesseract with strict timeout
        result = subprocess.run([
            'tesseract', str(img_path), 'stdout', 
            '-l', 'eng+spa', '--psm', '6', '--oem', '0'
        ], capture_output=True, text=True, timeout=8)
        
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

def parse_filename_metadata(video_path: Path):
    """Extract metadata from filename: {streamer}_{date}_{time}_{platform}_{title}.mp4"""
    name = video_path.stem
    parts = name.split('_')
    if len(parts) >= 5:
        streamer = parts[0]
        date = parts[1]
        time = parts[2]
        platform = parts[3]
        title = '_'.join(parts[4:]).replace('_', ' ')
        return {
            'streamer': streamer,
            'date': date,
            'time': time,
            'platform': platform,
            'title': title
        }
    return {}

def parse_title_for_episodes(title: str):
    """Parse stream title for series and episode info."""
    title_lower = title.lower()
    
    # Common patterns in Spanish stream titles
    patterns = [
        # "naruto examenes" -> Naruto, exam episodes
        # "winx club" -> Winx Club
        # "one piece 1000" -> One Piece episode 1000
        # "dbz capitulo 5" -> DBZ capitulo 5
        r'(\w+(?:\s+\w+)?)\s+(?:ep|episodio|cap[ií]tulo|cap)\.?\s*(\d+)',
        r'(\w+(?:\s+\w+)?)\s+(\d+)\s*(?:ep|episodio|cap)',
        r'(\w+(?:\s+\w+)?)\s+temp(?:orada)?\.?\s*(\d+)\s*(?:ep|episodio)?\.?\s*(\d+)?',
    ]
    
    series = None
    episodes = []
    season = None
    
    for pattern in patterns:
        matches = re.finditer(pattern, title_lower)
        for m in matches:
            groups = m.groups()
            if len(groups) >= 2:
                if series is None:
                    series = groups[0].title()
                try:
                    ep = int(groups[-1])
                    if 1 <= ep <= 999:
                        episodes.append(ep)
                except:
                    pass
                if len(groups) >= 3 and groups[1].isdigit():
                    season = int(groups[1])
    
    # If no pattern matched, try to identify series from title
    if series is None:
        # Known series keywords
        known_series = {
            'naruto': 'Naruto',
            'winx': 'Winx Club',
            'one piece': 'One Piece',
            'dbz': 'Dragon Ball Z',
            'dragon ball': 'Dragon Ball',
        }
        for key, val in known_series.items():
            if key in title_lower:
                series = val
                break
        if series is None:
            # Use first 2 words as series name
            words = title.split()
            series = ' '.join(words[:2]).title() if len(words) >= 2 else title.title()
    
    return {
        'series': series,
        'episodes': episodes,
        'season': season
    }

# Test with our videos
videos = [
    Path('/app/data/pipeline/grabaciones/2026/09/sendosama_2026-09-24_22-07-21_KW_winx_club.mp4'),
    Path('/app/data/pipeline/grabaciones/2026/09/sendosama_2026-09-25_22-19-26_KW_naruto_exámenes.mp4'),
]

for video in videos:
    print(f"\n=== {video.name} ===")
    meta = parse_filename_metadata(video)
    print(f"Metadata: {json.dumps(meta, indent=2)}")
    
    title_info = parse_title_for_episodes(meta.get('title', ''))
    print(f"Title parsing: {json.dumps(title_info, indent=2)}")
