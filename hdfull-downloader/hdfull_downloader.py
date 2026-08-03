#!/usr/bin/env python3
import os
import sys
import time
import re
import json
import random
import subprocess
import urllib.parse

import requests

def _ensure_deps():
    for pkg, mod in [("rich", "rich"), ("DrissionPage", "DrissionPage")]:
        try:
            __import__(mod)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

_ensure_deps()

from DrissionPage import ChromiumPage, ChromiumOptions
from rich.console import Console
from rich.panel import Panel

console = Console()

BG = "blue"
FG = "green"

def styled_panel(content, title="", style=BG):
    return Panel(content, title=title, border_style=style, expand=True)

def log(msg):
    if any(k in msg.upper() for k in ["OK", "LISTO", "COMPLETO", "EXITO"]):
        console.print(f"  [bold green]✓[/bold green] {msg}", style=f"bold {FG}")
    elif any(k in msg.upper() for k in ["ERR", "FALLO", "FALLIDO", "NO SE"]):
        console.print(f"  [bold red]✗[/bold red] {msg}")
    elif any(k in msg.upper() for k in ["WARN", "PENDIENTE"]):
        console.print(f"  [bold yellow]⚠[/bold yellow] {msg}")
    else:
        console.print(f"  [bold blue]ℹ[/bold blue] {msg}")

OUT_DIR = os.environ.get("HDFULL_OUT", "/app/downloads")
HDFULL_USER = os.environ.get("HDFULL_USER", "").strip()
HDFULL_PASS = os.environ.get("HDFULL_PASS", "").strip()
TARGET_URL = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HDFULL_URL", "").strip()
if not TARGET_URL:
    print("ERROR: No se ha proporcionado URL. Usa argv[1] o variable HDFULL_URL.")
    sys.exit(1)
CAPTCHA_TIMEOUT = int(os.environ.get("HDFULL_CAPTCHA_TIMEOUT", "900"))

STEALTH = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['es-ES', 'es']});
Object.defineProperty(navigator, 'language', {get: () => 'es-ES'});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
"""

BLOB_HOOK = """
(function(){
  var orig = URL.createObjectURL;
  if (window.__blobs_hooked) return;
  window.__blobs_hooked = true;
  window.__blobs = [];
  URL.createObjectURL = function(obj){
    var u = orig.call(this, obj);
    try { window.__blobs.push({url: u, blob: obj}); } catch(e){}
    if (window.__blobs.length > 30) window.__blobs.shift();
    return u;
  };
})();
"""


def launch():
    co = ChromiumOptions()
    co.set_browser_path("/usr/bin/chromium")
    co.headless(False)
    co.set_user_data_path("/profile")
    co.set_local_port(9312)
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-dev-shm-usage")
    co.set_argument("--remote-allow-origins=*")
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--window-size=1400,900")
    co.set_argument("--start-maximized")
    co.set_argument("--force-device-scale-factor=1")
    co.set_argument("--lang=es-ES,es")
    co.set_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    page = ChromiumPage(co)
    page.run_cdp("Page.addScriptToEvaluateOnNewDocument", source=STEALTH)
    page.run_cdp("Page.addScriptToEvaluateOnNewDocument", source=BLOB_HOOK)
    page.run_cdp("Emulation.setTimezoneOverride", timezoneId="Europe/Madrid")
    return page


def login(page):
    if not HDFULL_USER or not HDFULL_PASS:
        log("FALTAN credenciales (HDFULL_USER / HDFULL_PASS)")
        return False
    for attempt in range(4):
        try:
            page.get("https://hdfull.sbs/login")
            time.sleep(6)
            page.ele("css:#popup_login_form input[name=username]", timeout=8).input(HDFULL_USER)
            page.ele("css:#popup_login_form input[name=password]", timeout=5).input(HDFULL_PASS)
            time.sleep(1)
            page.ele("css:#popup_login_form a[onclick*=doLogin]", timeout=5).click()
            time.sleep(6)
            if "login" not in page.url.lower():
                log("LOGIN OK")
                return True
            res = page.ele("#popup_login_result", timeout=3)
            log(f"login intento {attempt}: {res.text[:80] if res else '?'}")
        except Exception as e:
            log(f"login intento {attempt} error: {e}")
        time.sleep(3)
    log("LOGIN FALLIDO")
    return False


def find_player_frame(page):
    for _ in range(6):
        try:
            ifs = page.eles("tag:iframe", timeout=4)
            for f in ifs:
                src = f.attr("src") or ""
                if "embed" in src or "video" in src or "player" in src:
                    fr = page.get_frame(f, timeout=15)
                    if fr:
                        return fr
        except Exception:
            pass
        time.sleep(3)
    return None


def close_popups(page):
    try:
        main = page.tab_id
        for tid in page.tab_ids:
            if tid == main:
                continue
            try:
                page.browser.get_tab(tid).close()
                log("popup cerrado")
            except Exception:
                pass
        time.sleep(0.5)
        page.activate_tab(main)
    except Exception as e:
        log(f"gestión de pestañas: {e}")


def find_media_urls(page, frame):
    urls = set()
    try:
        html = frame.html
    except Exception:
        html = ""
    if html:
        for m in re.findall(r"[a-zA-Z0-9_\-]+\.(?:mp4|m3u8|mpd)(?:\?[^\"' ]*)?", html):
            urls.add(m if m.startswith("http") else urllib.parse.urljoin(frame.url, m))
        # configuraciones tipo file:/src:
        for m in re.findall(r"(?:file|src|source)\s*[:=]\s*[\"']([^\"']+\.(?:mp4|m3u8|mpd)[^\"']*)[\"']", html, flags=re.I):
            urls.add(m if m.startswith("http") else urllib.parse.urljoin(frame.url, m))
    try:
        vids = frame.eles("tag:video", timeout=2)
    except Exception:
        vids = []
    for v in vids:
        src = v.attr("src")
        if src:
            urls.add(src)
        for s in v.eles("tag:source", timeout=1):
            src = s.attr("src")
            if src:
                urls.add(src)
    return list(urls)


DECOY_HOSTS = ("powwideo.org", "powvideo.org")


def looks_like_decoy(url):
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return True
    return any(h in host for h in DECOY_HOSTS)


def fresh_blob_url(frame):
    js = """(() => {
      if (window.__blobs && window.__blobs.length) {
        var b = window.__blobs[window.__blobs.length - 1];
        try { return URL.createObjectURL(b.blob); } catch(e){ return 'ERR:' + e; }
      }
      return null;
    })()"""
    try:
        return frame.run_js(js, as_expr=True)
    except Exception as e:
        log(f"fresh blob error: {e}")
        return None


def dump_diag(page, frame):
    import json
    lines = []
    for nombre, ctx in (("frame", frame), ("top", page)):
        try:
            lines.append(f"{nombre}.url: " + str(ctx.url))
        except Exception as e:
            lines.append(f"{nombre}.url ERR: {e}")
        try:
            lines.append(f"{nombre}.html: " + str(ctx.html)[:3000])
        except Exception as e:
            lines.append(f"{nombre}.html ERR: {e}")
        try:
            perf = ctx.run_js(
                "JSON.stringify(performance.getEntriesByType('resource').map(e=>[e.name,e.initiatorType]))",
                as_expr=True)
            lines.append(f"{nombre}.perf: " + json.dumps(perf))
        except Exception as e:
            lines.append(f"{nombre}.perf ERR: {e}")
    try:
        vinfo = frame.run_js(
            "JSON.stringify({src:(document.querySelector('video')||{}).src,"
            "currentSrc:(document.querySelector('video')||{}).currentSrc,"
            "readyState:(document.querySelector('video')||{}).readyState,"
            "paused:(document.querySelector('video')||{}).paused})", as_expr=True)
        lines.append("video: " + str(vinfo))
    except Exception as e:
        lines.append("video ERR: " + str(e))
    try:
        bl = frame.run_js("window.__blobs ? window.__blobs.length : 0", as_expr=True)
        lines.append("blobs_hook_count: " + str(bl))
    except Exception:
        pass
    path = "/app/diagnostics.txt"
    with open(path, "w") as fh:
        fh.write("\n".join(str(x) for x in lines))
    log(f"Diagnóstico guardado en {path}")


def download_hls_dash(url, dest):
    import subprocess
    kind = "DASH" if url.lower().endswith(".mpd") else "HLS"
    log(f"{kind} detectado, descargando con ffmpeg: {url[:110]}")
    log(f"  -> {dest}")
    cmd = ["ffmpeg", "-y", "-loglevel", "info",
           "-headers", "Referer: https://powwideo.org/\r\n",
           "-i", url, "-c", "copy", "-movflags", "+faststart", "-f", "mp4"]
    if url.lower().endswith(".mpd"):
        try:
            import requests as _r
            xml = _r.get(url, timeout=30, headers={"Referer": "https://powwideo.org/"}).text
            m = re.search(r'mediaPresentationDuration="PT(\d+(?:\.\d+)?)S"', xml)
            if m:
                dur = float(m.group(1))
                globals()["_mpd_dur"] = dur
                cmd += ["-t", str(max(1, dur - 6))]
                log(f"  duración MPD: {dur:.1f}s (cortando en {dur - 6:.1f}s para evitar fragmento fantasma)")
        except Exception as e:
            log(f"  no se pudo parsear MPD: {e}")
    cmd.append(dest)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    total_s = globals().get("_mpd_dur", 0)
    last = 0
    for line in proc.stdout:
        m = re.search(r"time=(\d+):(\d+):(\d+)", line)
        if m:
            secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            if time.time() - last > 5:
                if total_s:
                    log(f"  ffmpeg {secs // 60}:{secs % 60:02d} / {int(total_s) // 60}:{int(total_s) % 60:02d}")
                else:
                    log(f"  ffmpeg {secs // 60}:{secs % 60:02d}")
                last = time.time()
    proc.wait()
    log(f"ffmpeg exit {proc.returncode}")
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        log(f"LISTO: {dest} ({os.path.getsize(dest) // 1048576}MB)")
        return dest
    return None


def download_file(url, dest, cookies=None):
    import requests
    if url.lower().endswith((".m3u8", ".mpd")):
        return download_hls_dash(url, dest)
    log(f"DESCARGANDO {url[:120]}")
    log(f"  -> {dest}")
    with requests.get(url, stream=True, timeout=60, cookies=cookies,
                      headers={"Referer": "https://powwideo.org/"}) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        last = 0
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1024 * 512):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                now = time.time()
                if now - last > 2:
                    if total:
                        log(f"  {done * 100 // total}% ({done // 1048576}MB / {total // 1048576}MB)")
                    else:
                        log(f"  {done // 1048576}MB")
                    last = now
    log(f"LISTO: {dest} ({done // 1048576}MB)")
    return dest


def download_blob(frame, blob_url, dest):
    import json
    log(f"BLOB detectado, capturando vía JS en el frame: {blob_url[:80]}")
    js = r"""((url) => {
      return fetch(url).then(r => r.arrayBuffer()).then(buf => {
        var CHUNK = 4 * 1024 * 1024;
        var u8 = new Uint8Array(buf);
        var parts = [];
        for (var i = 0; i < u8.length; i += CHUNK) {
          var bin = '';
          for (var j = i; j < Math.min(i + CHUNK, u8.length); j++) bin += String.fromCharCode(u8[j]);
          parts.push(btoa(bin));
        }
        return parts;
      }).catch(e => 'ERR:' + (e && e.message ? e.message : e));
    })(""" + json.dumps(blob_url) + """)"""
    chunks = frame.run_js(js, as_expr=True)
    if not chunks:
        log("fallo blob: run_js devolvió None (blob revocado o frame perdido)")
        return None
    if isinstance(chunks, str) and chunks.startswith("ERR:"):
        log(f"fallo blob: {chunks}")
        return None
    import base64
    with open(dest, "wb") as fh:
        for i, c in enumerate(chunks):
            fh.write(base64.b64decode(c))
            if i % 8 == 0:
                log(f"  chunk {i + 1}/{len(chunks)}")
    log(f"LISTO: {dest} ({os.path.getsize(dest) // 1048576}MB)")
    return dest


def save_meta(url, dest):
    with open(dest, "w") as fh:
        fh.write(url + "\n")
    log(f"META: {url}")


def main():
    log(f"URL objetivo: {TARGET_URL}")
    os.makedirs(OUT_DIR, exist_ok=True)
    page = launch()

    if not login(page):
        page.quit()
        sys.exit(1)

    page.get(TARGET_URL)
    time.sleep(8)
    log(f"Página: {page.url[:100]} | {page.title[:70]}")

    frame = find_player_frame(page)
    if not frame:
        log("No se encontró el frame del reproductor")
        page.quit()
        sys.exit(1)
    log(f"Reproductor: {frame.url[:90]}")

    play = frame.ele("css:.play-box", timeout=12)
    if play:
        play.hover()
        time.sleep(random.uniform(0.5, 1.2))
        play.click()
        log("Play pulsado; esperando captcha...")
    time.sleep(5)
    close_popups(page)
    page.listen.start([r".*\.(mp4|m3u8|mpd|m4s|ts)(\?.*)?$", r".*video-.*", r".*fragment.*\.m4s$", r".*manifest\.mpd$"], is_regex=True)
    log("Escuchando tráfico de red (mp4/m3u8)...")

    # Si no hay captcha auto-resuelto, avisar al usuario para resolverlo en noVNC
    solved = False
    start = time.time()
    while time.time() - start < CAPTCHA_TIMEOUT:
        time.sleep(6)
        if frame is None:
            frame = find_player_frame(page)
            if not frame:
                continue
        try:
            cur = frame.url
        except Exception:
            frame = None
            continue
        if "/video-" in cur or re.search(r"/video|/watch|/player", cur):
            log("Captcha superado -> navegando a la página de video")
            solved = True
            break
        try:
            vids = frame.eles("tag:video", timeout=1)
            src = vids[0].attr("src") if vids else None
        except Exception:
            src = None
        if src:
            solved = True
            break
        if int(time.time() - start) % 30 < 6:
            log("PENDIENTE: abre http://localhost:6080/vnc.html y resuelve el captcha "
                f"({int(time.time() - start)}s / {CAPTCHA_TIMEOUT}s)")
        if int(time.time() - start) % 60 < 6:
            close_popups(page)

    if not solved:
        log("Tiempo de captcha agotado")
        page.quit()
        sys.exit(1)

    log("Captcha superado; extrayendo video...")
    time.sleep(3)
    if frame is None:
        frame = find_player_frame(page)

    # disparar play del reproductor (gesto confiable via CDP)
    for sel in [".play-box", ".vjs-big-play-button", ".vjs-play-control",
                ".jw-icon-display", "button[aria-label*='play' i]",
                "button[aria-label*='Play' i]", ".mejs__play"]:
        try:
            el = frame.ele(f"css:{sel}", timeout=1.2)
            if el:
                el.click()
                log(f"play click: {sel}")
                break
        except Exception:
            pass

    media = []
    manifest = None
    perf_js = "JSON.stringify(performance.getEntriesByType('resource').map(e => e.name))"
    vsrc_js = "(document.querySelector('video')||{}).src || ''"
    deadline = time.time() + 60
    fr = frame
    while time.time() < deadline:
        try:
            found = find_media_urls(page, fr)
            names = fr.run_js(perf_js, as_expr=True) or []
            if isinstance(names, str):
                try:
                    names = json.loads(names)
                except Exception:
                    names = []
            vsrc = fr.run_js(vsrc_js, as_expr=True) or ""
        except Exception:
            log("frame perdido; re-adquiriendo...")
            fr = find_player_frame(page)
            time.sleep(2)
            continue
        for u in found:
            if u not in media:
                media.append(u)
                log(f"  html: {u[:130]}")
        for n in names:
            if re.search(r"\.(mpd|mp4|m3u8|m4s|ts|webm)(\?|$)", n) and n not in media:
                media.append(n)
                log(f"  perf: {n[:130]}")
        if vsrc.startswith("blob:") and vsrc not in media:
            media.append(vsrc)
            log(f"  video.src: {vsrc[:60]}")
        for u in media:
            if re.search(r"\.(mpd|m3u8)(\?|$)", u):
                manifest = u
                break
        # si solo hay fragmentos (.m4s/.ts) y no hay manifest, derivarlo de la
        # base del fragmento (el manifest suele quedar fuera del buffer de perf)
        if not manifest:
            for u in media:
                if re.search(r"(fragment[-_]|\.m4s(\?|$)|\.ts(\?|$))", u, flags=re.I):
                    mu = u[:u.rfind("/") + 1] + "manifest.mpd"
                    try:
                        rsp = requests.get(mu, timeout=12,
                                           headers={"Referer": "https://powwideo.org/"})
                        ok = rsp.status_code == 200 and b"<MPD" in rsp.content[:2000]
                    except Exception:
                        ok = False
                    if ok:
                        if mu not in media:
                            media.append(mu)
                            log(f"  manifest derivado (ok): {mu[:130]}")
                        manifest = mu
                    else:
                        log(f"  manifest derivado inválido: {mu[:110]}")
                    break
        if manifest:
            break
        if any(re.search(r"\.mp4(\?|$)", u) and not u.startswith("blob:")
               and not looks_like_decoy(u) for u in media):
            break
        time.sleep(3)

    if not media:
        dump_diag(page, fr)
        log("No se encontró URL de video")
        page.quit()
        sys.exit(1)

    if manifest:
        url = manifest
    else:
        mp4s = [u for u in media if re.search(r"\.mp4(\?|$)", u) and not u.startswith("blob:")
                and not looks_like_decoy(u)]
        blobs = [u for u in media if u.startswith("blob:")]
        url = (mp4s or blobs or media)[0]

    if url.lower().endswith((".m3u8", ".mpd")):
        p = urllib.parse.urlparse(TARGET_URL).path.strip("/")
        seg = p.split("/")[-1] if p else "video"
        base = (seg or "video") + ".mp4"
    else:
        base = os.path.basename(urllib.parse.urlparse(url).path) or "video.mp4"
        if not base.lower().endswith((".mp4", ".m3u8", ".mpd")):
            base = "video.mp4"
    dest = os.path.join(OUT_DIR, base)
    meta = os.path.join(OUT_DIR, base + ".url")
    save_meta(url, meta)

    ok = None
    try:
        if url.startswith("blob:"):
            ok = download_blob(fr, url, dest)
        else:
            cookies = {c["name"]: c["value"] for c in page.cookies(all_domains=True)}
            ok = download_file(url, dest, cookies=cookies)
    except Exception as e:
        log(f"descarga falló ({e}); probando descarga vía navegador...")
        try:
            page.set.download_path(OUT_DIR)
            page.download(url, rename=base)
            time.sleep(5)
            ok = dest if os.path.exists(dest) and os.path.getsize(dest) > 0 else None
        except Exception as e2:
            log(f"descarga vía navegador falló: {e2}")

    try:
        if os.path.exists(meta):
            os.remove(meta)
            log(f"Eliminado meta: {meta}")
    except Exception as e:
        log(f"no se pudo eliminar meta ({e})")

    if ok and os.path.exists(ok):
        log(f"PROCESO COMPLETO: {ok} ({os.path.getsize(ok) // 1048576}MB)")
    else:
        log("PROCESO TERMINADO SIN DESCARGA COMPLETA")
        dump_diag(page, fr)
    page.quit()


if __name__ == "__main__":
    main()
