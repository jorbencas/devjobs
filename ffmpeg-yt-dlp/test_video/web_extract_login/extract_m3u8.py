#!/usr/bin/env python3
"""
Extrae stream HLS (m3u8) de una página web con login usando DrissionPage.
Uso: python3 extract_m3u8.py <URL> <usuario> <contraseña> [dominio]
Salida: imprime "M3U8_FOUND:<url>" si encuentra el stream
"""

import sys
import time
import re
import threading
from DrissionPage import ChromiumPage, ChromiumOptions


def extract_m3u8_with_login(url, user, passw, domain=None):
    """Extrae URL m3u8 de una página web con login."""
    print(f"DEBUG: Starting extract for {url}", file=sys.stderr, flush=True)
    
    co = ChromiumOptions()
    co.set_browser_path("/usr/bin/chromium")
    co.headless(True)
    co.set_user_data_path("/tmp/drission_profile")
    co.set_local_port(9312)
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-dev-shm-usage")
    co.set_argument("--remote-allow-origins=*")
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--window-size=1400,900")
    co.set_argument("--start-maximized")
    co.set_argument("--force-device-scale-factor=1")
    co.set_argument("--lang=es-ES,es")
    co.set_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    co.set_argument("--headless=new")

    print("DEBUG: Creating ChromiumPage...", file=sys.stderr, flush=True)
    try:
        page = ChromiumPage(co)
        print("DEBUG: ChromiumPage created", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"DEBUG: Failed to create ChromiumPage: {e}", file=sys.stderr, flush=True)
        return None
    page.run_cdp("Page.addScriptToEvaluateOnNewDocument", source="""Object.defineProperty(navigator, 'webdriver', {get: () => undefined});""")
    page.run_cdp("Emulation.setTimezoneOverride", timezoneId="Europe/Madrid")

    print(f"DEBUG: Navigating to {url}", file=sys.stderr, flush=True)
    try:
        page.get(url, timeout=30)
    except Exception as e:
        print(f"DEBUG: Navigation error: {e}", file=sys.stderr, flush=True)
    time.sleep(3)
    print("DEBUG: Page loaded", file=sys.stderr, flush=True)

    print("DEBUG: Detecting login form...", file=sys.stderr, flush=True)
    # Detectar formulario de login con timeout manual
    import concurrent.futures
    
    def find_element_with_timeout(page, css_selector, timeout=2):
        """Find element with custom timeout using threading"""
        result = [None]
        def find_elem():
            try:
                result[0] = page.ele(css_selector, timeout=2)
            except:
                result[0] = None
        
        result = [None]
        thread = threading.Thread(target=lambda: result.__setitem__(0, page.ele(css_selector, timeout=2)))
        thread.start()
        thread.join(timeout=2)
        if thread.is_alive():
            # Timeout - can't easily kill the thread, but we'll return None
            return None
        return result[0]
    
    print("DEBUG: Detecting login form...", file=sys.stderr, flush=True)
    # Detectar formulario de login con timeout manual
    try:
        user_el = find_element_with_timeout(page, "css:input[name=username], input[name=username], input[id*=user], input[type=email]", 2)
        pass_el = page.ele("css:input[name=password], input[name=pass], input[type=password]", timeout=2)
        print(f"DEBUG: user_el={user_el is not None}, pass_el={pass_el is not None}", file=sys.stderr, flush=True)
        if user_el and pass_el:
            user_el.input(user)
            time.sleep(0.5)
            pass_el.input(passw)
            time.sleep(0.5)
            btn = page.ele("css:button[type=submit], input[type=submit], button[type=submit], .btn-login, .btn-primary, button:contains(Entrar), button:contains(Login), button:contains(Acceder)", timeout=2)
            if btn:
                btn.click()
            else:
                from DrissionPage import Keys
                pass_el.input(Keys.ENTER)
            time.sleep(3)
    except Exception as e:
        print(f"DEBUG: Login error: {e}", file=sys.stderr, flush=True)

    print("DEBUG: Waiting for page load after login...", file=sys.stderr, flush=True)
    time.sleep(2)

    print("DEBUG: Starting network listener...", file=sys.stderr, flush=True)
    page.listen.start()
    time.sleep(2)  # Esperar a que carguen recursos
    
    m3u8_url = None
    start_time = time.time()
    timeout = 10  # 10 second timeout for network listener
    
    try:
        while time.time() - start_time < 10:
            # Usar steps con timeout muy corto
            try:
                for req in page.listen.steps(1):
                    if ".m3u8" in req.url:
                        print(f"M3U8_FOUND:{req.url}")
                        return req.url
                time.sleep(0.5)
            except Exception as e:
                print(f"DEBUG: Listener step error: {e}", file=sys.stderr, flush=True)
                break
            
            if time.time() - start_time > 10:
                break
    except Exception as e:
        print(f"DEBUG: Error in network listener: {e}", file=sys.stderr, flush=True)
    
    # Si no se encontró en requests, buscar en HTML
    html = page.html
    m3u8_matches = re.findall(r'https?://[^"\'<>]+\.m3u8[^"\'<>]*', html)
    for m in m3u8_matches:
        print(f"M3U8_FOUND:{m}")
        return m

    return None


def main():
    if len(sys.argv) < 4:
        print("Uso: python3 extract_m3u8.py <URL> <usuario> <contraseña> [dominio]")
        sys.exit(1)

    url = sys.argv[1]
    user = sys.argv[2]
    passw = sys.argv[3]
    domain = sys.argv[4] if len(sys.argv) > 4 else None

    try:
        import re
        m3u8_url = extract_m3u8_with_login(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
        if m3u8_url:
            print(f"M3U8_FOUND:{m3u8_url}")
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import sys
    import time
    import re
    from DrissionPage import ChromiumPage, ChromiumOptions
    main()