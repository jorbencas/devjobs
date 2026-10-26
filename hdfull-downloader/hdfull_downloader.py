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

# Dominios oficiales de hdfull (se obtienen de dominioshdfull.com)
HDFULL_DOMAINS = []


def fetch_hdfull_domains():
    """Obtiene la lista de dominios desde dominioshdfull.com."""
    global HDFULL_DOMAINS
    try:
        r = requests.get("https://dominioshdfull.com/", timeout=10,
                         headers={"User-Agent": "Mozilla/5.0"})
        # Extraer solo dominios hdfull.* del HTML
        domains = re.findall(r'(?:https?://)?((?:www\d?\.)?hdfull\.[a-z]+)', r.text, re.I)
        HDFULL_DOMAINS = list(dict.fromkeys(domains))  # uniq, preserve order
        log(f"Dominios obtenidos: {len(HDFULL_DOMAINS)} ({', '.join(HDFULL_DOMAINS[:5])}...)")
    except Exception as e:
        log(f"No se pudieron obtener dominios: {e}")
        HDFULL_DOMAINS = ["www3.hdfull.one", "hdfull.sbs", "hdfull.org"]


def find_working_domain(url):
    """Si el dominio de la URL no responde, prueba dominios alternativos."""
    if not HDFULL_DOMAINS:
        fetch_hdfull_domains()

    parsed = urllib.parse.urlparse(url)
    current_domain = parsed.netloc.lower().replace("www.", "")

    # Primero probar el dominio actual
    try:
        r = requests.get(f"https://{parsed.netloc}/", timeout=8, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 404:
            # Verificar que no sea solo Cloudflare (título "Just a moment...")
            if "just a moment" not in r.text[:2000].lower():
                log(f"Dominio actual {parsed.netloc} accesible (HTTP {r.status_code})")
                return url
            else:
                # No cambiar de dominio por Cloudflare: se resuelve en el navegador
                log(f"Dominio {parsed.netloc} tiene Cloudflare; lo resolverá el navegador")
                return url
    except Exception:
        pass

    log(f"Dominio {parsed.netloc} no responde, buscando alternativo...")

    # Probar dominios alternativos
    for domain in HDFULL_DOMAINS:
        if domain.lower().replace("www.", "") == current_domain:
            continue
        try:
            r = requests.get(f"https://{domain}/", timeout=8, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 404:
                if "just a moment" not in r.text[:2000].lower():
                    new_url = url.replace(parsed.netloc, domain)
                    log(f"Dominio alternativo encontrado: {domain} (HTTP {r.status_code})")
                    log(f"Nueva URL: {new_url}")
                    return new_url
        except Exception:
            continue

    log("No se encontró ningún dominio accesible, usando el primero de la lista")
    # Si todos tienen Cloudflare, usar el primer dominio (el que Cloudflare no bloquea)
    for domain in HDFULL_DOMAINS:
        try:
            r = requests.get(f"https://{domain}/", timeout=8, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 404:
                new_url = url.replace(parsed.netloc, domain)
                log(f"Usando dominio con Cloudflare: {domain} (HTTP {r.status_code})")
                log(f"Nueva URL: {new_url}")
                return new_url
        except Exception:
            continue

    return url

STEALTH = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
delete navigator.__proto__.webdriver;
Object.defineProperty(navigator, 'languages', {get: () => ['es-ES', 'es', 'en-US', 'en']});
Object.defineProperty(navigator, 'language', {get: () => 'es-ES'});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0});
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
  parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);
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
    # Forzar uso de X11 para que se vea en noVNC
    co.set_argument("--ozone-platform=x11")
    co.set_argument("--remote-allow-origins=*")
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--window-size=1400,900")
    co.set_argument("--start-maximized")
    co.set_argument("--force-device-scale-factor=1")
    co.set_argument("--lang=es-ES,es")
    co.set_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    # Necessary for running in container
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-dev-shm-usage")
    co.set_argument("--disable-gpu")
    co.set_argument("--disable-extensions")
    co.set_argument("--disable-infobars")
    page = ChromiumPage(co)
    page.run_cdp("Page.addScriptToEvaluateOnNewDocument", source=STEALTH)
    page.run_cdp("Page.addScriptToEvaluateOnNewDocument", source=BLOB_HOOK)
    page.run_cdp("Emulation.setTimezoneOverride", timezoneId="Europe/Madrid")
    return page


def is_logged_in(page):
    try:
        if page.ele('text:Mi cuenta', timeout=2):
            return True
        if page.ele('css:a[href*="logout"], a[href*="salir"]', timeout=2):
            return True
        if page.ele('css:.user-menu, .logged-in', timeout=2):
            return True
    except Exception:
        pass
    return False


def login(page, domain):
    if not HDFULL_USER or not HDFULL_PASS:
        log("FALTAN credenciales (HDFULL_USER / HDFULL_PASS)")
        return False
    # Comprobar si ya hay sesión
    try:
        page.get(f"https://{domain}/")
        time.sleep(6)
        if is_logged_in(page):
            log("LOGIN OK (sesión ya activa)")
            return True
    except Exception:
        pass
    login_url = f"https://{domain}/login"
    page.get(login_url)
    time.sleep(25)
    if is_logged_in(page):
        log("LOGIN OK (sesión ya activa)")
        return True
    # Intentar abrir modal de login si existe
    try:
        for txt in ["Acceder", "Iniciar sesión", "Entrar", "Login", "Mi cuenta"]:
            try:
                el = page.ele(f'text:{txt}', timeout=5)
                if el:
                    try:
                        el.click()
                        time.sleep(20)
                        break
                    except Exception:
                        pass
            except Exception:
                continue
    except Exception:
        pass
    try:
        user_el = page.ele('css:input[name=username], input[name=user], input[type=email]', timeout=10)
        pass_el = page.ele('css:input[name=password], input[type=password]', timeout=10)
        if user_el and pass_el:
            pass
    except Exception:
        pass
    for attempt in range(20):
        try:
            user_el = None
            pass_el = None
            for sel in [
                "css:#popup_login_form input[name=username]",
                "css:#login_form input[name=username]",
                "css:form[action*='login'] input[name=username]",
                "css:form[action*='usuario'] input[type=text]",
                "css:input[name=username]",
                "css:input[name='user']",
                "css:input[name='login']",
                "css:input[name='email']",
                "css:input[type=email]",
                "css:input[type=text][name*=user i]",
                "css:input[type=text][placeholder*=usuario i]",
                "css:input[type=text][placeholder*=Usuario i]",
                "css:input[type=text][placeholder*=email i]",
            ]:
                try:
                    user_el = page.ele(sel, timeout=2)
                    if user_el:
                        break
                except Exception:
                    continue
            for sel in [
                "css:#popup_login_form input[name=password]",
                "css:#login_form input[name=password]",
                "css:form[action*='login'] input[name=password]",
                "css:input[name=password]",
                "css:input[type=password]",
            ]:
                try:
                    pass_el = page.ele(sel, timeout=2)
                    if pass_el:
                        break
                except Exception:
                    continue
            if not user_el or not pass_el:
                # Debug: look for any inputs
                try:
                    inputs = page.eles('tag:input', timeout=2)
                    if inputs:
                        names = []
                        for inp in inputs[:15]:
                            try:
                                names.append(f"{inp.attr('name')}|{inp.attr('type')}|{inp.attr('id')}|{inp.attr('placeholder')}")
                            except Exception:
                                pass
                        log(f"login intento {attempt}: inputs encontrados: {names} (URL:{page.url[:80]})")
                    else:
                        log(f"login intento {attempt}: sin inputs (URL:{page.url[:80]})")
                    # Revisar si hay turnstile/captcha
                    try:
                        turn = page.ele('css:.cf-turnstile', timeout=1)
                        ifr = page.ele('css:iframe[src*="challenges.cloudflare.com"], iframe[src*="turnstile"]', timeout=1)
                        if turn or ifr:
                            log(f"LOGIN: Turnstile/Cloudflare detectado en formulario. Ábrelo en http://localhost:6080/vnc.html y resuélvelo manualmente. Esperando...")
                        cf_wait = 0
                        cf_timeout = 900
                        while cf_wait < cf_timeout:
                            if has_cf_clearance(page):
                                log("cf_clearance detectado")
                                break
                            try:
                                if not page.ele('css:.cf-turnstile', timeout=1) and not page.ele('css:iframe[src*="challenges.cloudflare.com"]', timeout=1):
                                    log("Turnstile parece resuelto")
                                    break
                            except Exception:
                                pass
                            # Comprobar si ya aparecen campos de login
                            try:
                                ue = page.ele('css:input[name=username], input[name=user], input[type=email]', timeout=1)
                                pe = page.ele('css:input[name=password], input[type=password]', timeout=1)
                                if ue and pe:
                                    log("Campos de login visibles")
                                    break
                            except Exception:
                                pass
                            if cf_wait % 30 == 0:
                                log(f"Esperando resolución... ({cf_wait}s / {cf_timeout}s)")
                            time.sleep(5)
                            cf_wait += 5
                        time.sleep(30)
                        # Ir a home y abrir login
                        try:
                            page.get(f"https://{domain}/")
                            time.sleep(30)
                            for txt in ["Acceder", "Iniciar sesión", "Entrar", "Login"]:
                                try:
                                    el = page.ele(f'text:{txt}', timeout=5)
                                    if el:
                                        el.click()
                                        time.sleep(30)
                                        break
                                except Exception:
                                    continue
                        except Exception:
                            pass
                        # Buscar campos con polling
                        user_el = None
                        pass_el = None
                        for _ in range(60):
                            try:
                                for sel in [
                                    "css:input[name=username]",
                                    "css:input[name=user]",
                                    "css:input[name='login']",
                                    "css:input[type=email]",
                                    "css:input[type=text][name*=user i]",
                                    "css:input[type=text]",
                                    "xpath://input[@type='text' or @type='email']",
                                ]:
                                    try:
                                        user_el = page.ele(sel, timeout=1)
                                        if user_el:
                                            break
                                    except Exception:
                                        continue
                                for sel in [
                                    "css:input[name=password]",
                                    "css:input[type=password]",
                                    "xpath://input[@type='password']",
                                ]:
                                    try:
                                        pass_el = page.ele(sel, timeout=1)
                                        if pass_el:
                                            break
                                    except Exception:
                                        continue
                                if user_el and pass_el:
                                    break
                            except Exception:
                                pass
                            try:
                                inputs = []
                                for inp in page.eles('css:input', timeout=1) or []:
                                    try:
                                        inputs.append(f"{inp.attr('name')}|{inp.attr('type')}|{inp.attr('id')}|{inp.attr('placeholder')}")
                                    except Exception:
                                        continue
                                if inputs and _ % 10 == 0:
                                    log(f"inputs ahora: {inputs} (URL:{page.url[:50]})")
                            except Exception:
                                pass
                            time.sleep(5)
                        if not (user_el and pass_el):
                            log("Sin campos aún tras polling, reintentando login desde /login")
                            try:
                                page.get(f"https://{domain}/login")
                                time.sleep(40)
                            except Exception:
                                pass
                            for _ in range(40):
                                try:
                                    for sel in [
                                        "css:input[name=username]", "css:input[name=user]", "css:input[name='login']", "css:input[type=email]",
                                        "css:input[type=text][name*=user i]", "css:input[type=text]", "xpath://input[@type='text' or @type='email']",
                                    ]:
                                        try:
                                            user_el = page.ele(sel, timeout=1)
                                            if user_el: break
                                        except Exception: continue
                                    for sel in ["css:input[name=password]", "css:input[type=password]", "xpath://input[@type='password']"]:
                                        try:
                                            pass_el = page.ele(sel, timeout=1)
                                            if pass_el: break
                                        except Exception: continue
                                    if user_el and pass_el: break
                                except Exception: pass
                                time.sleep(5)
                        if user_el and pass_el:
                            log("Campos encontrados, procediendo a login")
                        else:
                            log("Sin campos tras todos los intentos")
                            time.sleep(60)
                            continue
                    except Exception:
                        pass
                except Exception as e:
                    log(f"login intento {attempt}: no se encuentran campos de login (URL:{page.url[:60]}) err:{e}")
                    time.sleep(6)
                    continue
                time.sleep(6)
                continue
            try:
                user_el.clear()
            except Exception:
                pass
            try:
                pass_el.clear()
            except Exception:
                pass
            user_el.input(HDFULL_USER)
            time.sleep(0.8)
            pass_el.input(HDFULL_PASS)
            time.sleep(1)
            btn = None
            for sel in [
                "css:#popup_login_form a[onclick*=doLogin]",
                "css:#loginForm button[type=submit]",
                "css:form[action*=login] button[type=submit]",
                "css:button[type=submit]",
                "css:.btn-login",
                "css:a.btn[onclick*=login]",
            ]:
                try:
                    btn = page.ele(sel, timeout=2)
                    if btn:
                        break
                except Exception:
                    continue
            if btn:
                btn.click()
            else:
                try:
                    pass_el.input('\n')
                except Exception:
                    pass
            time.sleep(8)
            if is_logged_in(page):
                log("LOGIN OK")
                return True
            if "login" not in page.url.lower():
                log("LOGIN OK")
                return True
            res = None
            for sel in ["#popup_login_result", ".login-error", ".error-message", "#login-error"]:
                try:
                    res = page.ele(sel, timeout=2)
                    if res:
                        break
                except Exception:
                    continue
            if res and res.text:
                log(f"login intento {attempt}: {res.text[:100]}")
            else:
                log(f"login intento {attempt}: sin mensaje de error claro")
        except Exception as e:
            log(f"login intento {attempt} error: {e}")
        time.sleep(4)
    log("LOGIN FALLIDO")
    return False


PLAYER_KEYWORDS = ("embed", "player", "/video", "/watch", "/ver", "video/",
                   "stream", "server", "reproduc", "vidsrc", "/tv/", "/ep/",
                   "gounlimited", "streamtape", "dood", "mixdrop", "filemoon",
                   "voe", "netu", "uqload", "sendvid", "fembed", "vev.io")


def find_player_frame(page):
    clicked = False
    for _ in range(6):
        try:
            ifs = page.eles("tag:iframe", timeout=4)
            for f in ifs:
                src = (f.attr("src") or f.attr("data-src") or "").strip()
                if any(k in src.lower() for k in PLAYER_KEYWORDS):
                    fr = page.get_frame(f, timeout=15)
                    if fr:
                        return fr
            # Fallback: si hay iframes pero ninguno coincide, probar el primero con src
            for f in ifs:
                if (f.attr("src") or "").strip():
                    fr = page.get_frame(f, timeout=10)
                    if fr:
                        return fr
            # Fallback: video ya incrustado directamente en la página principal
            if page.eles("tag:video", timeout=1):
                return page
        except Exception:
            pass
        if not clicked:
            clicked = True
            try_click_play(page)
        time.sleep(3)
    return None


def try_click_play(page):
    for sel in (".play-box", "#play", "#play-button", ".playbtn", ".play-btn",
                ".btn-play", "#btn-play", "a[data-play]", "a[href*='player']",
                "a[href*='player.php']", ".choose-player a", "a[href*='/ver/']",
                "a[href*='reproducir']", "[onclick*='player' i]",
                "[onclick*='play' i]"):
        try:
            el = page.ele(f"css:{sel}", timeout=1.5)
            if el:
                el.click()
                log(f"click play: {sel}")
                time.sleep(4)
                return True
        except Exception:
            pass
    return False


def raw_html_frame_url(page, url):
    """Intenta sacar el iframe del reproductor del HTML crudo, usando
    las cookies del navegador (bypasa el render JS que se cuelga)."""
    try:
        ck = {c["name"]: c["value"] for c in page.cookies(all_domains=True)}
        r = requests.get(url, timeout=15, allow_redirects=True, cookies=ck,
                         headers={"User-Agent":
                                  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/125.0.0.0 Safari/537.36",
                                  "Referer": url})
        html = r.text
        if "just a moment" in html[:2000].lower():
            log("raw html: bloqueado por Cloudflare (usando página del navegador)")
            return None
        for tag in re.findall(r"<iframe[^>]*>", html, flags=re.I):
            m = re.search(r'\b(?:src|data-src|data-lazy-src)\s*=\s*"([^"]+)"',
                          tag, flags=re.I)
            if not m:
                continue
            u = m.group(1)
            if any(k in u.lower() for k in PLAYER_KEYWORDS):
                return u if u.startswith("http") else urllib.parse.urljoin(url, u)
        return None
    except Exception as e:
        log(f"raw html frame ERR: {e}")
        return None


def dump_diag_no_frame(page):
    import json
    lines = []
    try:
        lines.append(f"page.url: {page.url}")
    except Exception as e:
        lines.append(f"page.url ERR: {e}")
    try:
        lines.append(f"page.title: {page.title}")
    except Exception as e:
        lines.append(f"page.title ERR: {e}")
    try:
        probe = page.run_js("""(() => {
          const ifr=[...document.querySelectorAll('iframe')].map(f=>(
            {src:f.src||'', data:f.getAttribute('data-src')||'', id:f.id, cls:(f.className||'')}));
          const play=[...document.querySelectorAll('a,button,div,span')]
            .filter(e=>/play|reproduc|ver video|ver pel|descargar|download/i.test(
              ((e.id||'')+' '+(e.className||'')+' '+(e.textContent||'').trim()).slice(0,120)))
            .slice(0,25).map(e=>({tag:e.tagName,id:(e.id||'')[:40],cls:(e.className||'')[:60],
              text:(e.textContent||'').trim()[:50]}));
          const host=[...document.querySelectorAll(
            '[id*="player" i],[class*="player" i],[id*="reproduc" i],[id*="video" i],[class*="reproduc" i]')]
            .slice(0,15).map(e=>({tag:e.tagName,id:(e.id||'')[:40],cls:(e.className||'')[:60]}));
          return JSON.stringify({ifr, play, host,
            ready: document.readyState,
            ifrCountDoc: document.querySelectorAll('iframe').length});
        })()""", as_expr=True)
        lines.append("probe: " + str(probe))
    except Exception as e:
        lines.append(f"probe ERR: {e}")
    try:
        page.get_screenshot(path="/app/diagnostics.png", full_page=True)
        lines.append("screenshot guardado en /app/diagnostics.png")
    except Exception as e:
        lines.append(f"screenshot ERR: {e}")
    with open("/app/diagnostics.txt", "w") as fh:
        fh.write("\n".join(str(x) for x in lines))
    log("Diagnóstico (sin frame) en /app/diagnostics.txt (mira la captura diagnostics.png)")


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


def page_title(page):
    try:
        return (page.title or "")[:200]
    except Exception:
        return ""


def has_cf_clearance(page):
    try:
        cookies = page.cookies()
        for c in cookies:
            name = str(c.get('name') or c.get('Name') or '').lower()
            if name == 'cf_clearance':
                return True
        try:
            cookies_all = page.cookies(all_domains=True)
            for c in cookies_all:
                name = str(c.get('name') or c.get('Name') or '').lower()
                if name == 'cf_clearance':
                    return True
        except Exception:
            pass
    except Exception:
        pass
    return False


def main():
    global TARGET_URL
    TARGET_URL = find_working_domain(TARGET_URL)
    domain = urllib.parse.urlparse(TARGET_URL).netloc
    log(f"URL objetivo: {TARGET_URL}")
    os.makedirs(OUT_DIR, exist_ok=True)
    page = launch()

    # Resolver Cloudflare del dominio original ANTES de hacer login
    log("Comprobando Cloudflare...")
    page.get(TARGET_URL)
    time.sleep(12)
    cf_wait = 0
    cf_timeout = int(os.environ.get("HDFULL_CF_TIMEOUT", "300"))
    while cf_wait < cf_timeout:
        title = page_title(page)
        t = title.lower()
        if has_cf_clearance(page):
            log("cf_clearance detectado - Cloudflare resuelto")
            break
        if "just a moment" not in t and "checking your browser" not in t and "cloudflare" not in t and "challenge" not in t:
            break
        # Intentar click en checkbox/radio si aparece
        try:
            cb = page.ele('css:input[type=checkbox]', timeout=1)
            if cb:
                try:
                    cb.click()
                    log("Intentando resolver Cloudflare (click en checkbox)")
                    time.sleep(4)
                    continue
                except Exception:
                    pass
        except Exception:
            pass
        try:
            for f in page.get_frames():
                try:
                    cb2 = f.ele('css:input[type=checkbox], .cb-lb, #challenge-stage input', timeout=1)
                    if cb2:
                        cb2.click()
                        log("Intentando resolver Cloudflare (click en iframe)")
                        time.sleep(4)
                        break
                except Exception:
                    continue
        except Exception:
            pass
        if cf_wait % 15 == 0:
            log(f"Esperando Cloudflare... ({cf_wait}s / {cf_timeout}s) - usa noVNC si pide verificación manual")
        time.sleep(5)
        cf_wait += 5
    if not has_cf_clearance(page):
        title = page_title(page)
        if "just a moment" in title.lower() or "checking your browser" in title.lower():
            log("Cloudflare sin cf_clearance aún; continúa (con perfil guardado suele pasar)")

    if not login(page, domain):
        page.quit()
        sys.exit(1)

    page.get(TARGET_URL)
    time.sleep(12)

    title = page_title(page)
    log(f"Página: {page.url[:100]} | {title[:70]}")

    # Esperar a que se resuelva Cloudflare challenge si está presente
    cf_wait = 0
    cf_timeout = int(os.environ.get("HDFULL_CF_TIMEOUT", "300"))
    title = page_title(page)
    while cf_wait < cf_timeout:
        t = title.lower()
        if has_cf_clearance(page):
            log("cf_clearance detectado tras navegación")
            break
        if "just a moment" not in t and "checking your browser" not in t and "cloudflare" not in t and "challenge" not in t:
            break
        try:
            cb = page.ele('css:input[type=checkbox]', timeout=1)
            if cb:
                try:
                    cb.click()
                    time.sleep(4)
                    continue
                except Exception:
                    pass
        except Exception:
            pass
        try:
            for f in page.get_frames():
                try:
                    cb2 = f.ele('css:input[type=checkbox]', timeout=1)
                    if cb2:
                        cb2.click()
                        time.sleep(4)
                        break
                except Exception:
                    continue
        except Exception:
            pass
        if cf_wait % 15 == 0:
            log(f"Esperando Cloudflare challenge... ({cf_wait}s / {cf_timeout}s)")
        time.sleep(5)
        cf_wait += 5
        title = page_title(page)

    if not has_cf_clearance(page):
        title = page_title(page)
        if "just a moment" in title.lower() or "checking your browser" in title.lower():
            log("Cloudflare challenge persiste; abre noVNC http://localhost:6080/vnc.html para resolverlo")

    log(f"Página cargada: {title[:70]}")

    frame = find_player_frame(page)
    if not frame:
        raw = raw_html_frame_url(page, TARGET_URL)
        if raw:
            log(f"Reproductor (HTML crudo): {raw[:90]}")
            try:
                page.get(raw)
                time.sleep(8)
                frame = find_player_frame(page)
            except Exception as e:
                log(f"navegar al embed falló: {e}")
    if not frame:
        dump_diag_no_frame(page)
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
