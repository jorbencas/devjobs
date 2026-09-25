#!/usr/bin/env python3
"""
Extrae stream HLS (m3u8) de una página web con login usando DrissionPage.
Uso: python3 extract_m3u8.py <URL> <usuario> <contraseña> [dominio]
Salida: imprime "M3U8_FOUND:<url>" si encuentra el stream
"""

import sys
import time
import json
import os
import re
from DrissionPage import ChromiumPage, ChromiumOptions

def extract_m3u8_with_login(url, user, passw, domain=None):
    """Extrae URL m3u8 de una página con login."""
    co = ChromiumOptions()
    co.set_browser_path("/usr/bin/chromium")
    co.headless(False)
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

    page = ChromiumPage(co)
    page.run_cdp("Page.addScriptToEvaluateOnNewDocument", source="""Object.defineProperty(navigator, 'webdriver', {get: () => undefined});""")
    page.run_cdp("Emulation.setTimezoneOverride", timezoneId="Europe/Madrid")

    # Navegar a la URL
    page.get(url)
    time.sleep(3)

    # Detectar formulario de login
    try:
        user_el = page.ele("css:input[name=username], input[name=username], input[id*=user], input[type=email]", timeout=5)
        pass_el = page.ele("css:input[name=password], input[name=pass], input[type=password]", timeout=5)
        if user_el and pass_el:
            user_el.input(user)
            time.sleep(0.5)
            pass_el.input(passw)
            time.sleep(0.5)
            btn = page.ele("css:button[type=submit], input[type=submit], button[type=submit], .btn-login, .btn-primary, button:contains(Entrar), button:contains(Login), button:contains(Acceder)", timeout=3)
            if btn:
                btn.click()
            else:
                from DrissionPage import Keys
                pass_el.input(Keys.ENTER)
            time.sleep(3)
    except:
        pass

    # Esperar a que cargue la página tras login
    time.sleep(5)

    # Buscar m3u8 en la página (en requests de red o en HTML)
    m3u8_urls = set()
    for req in page.listen.wait_for_new_request(10):
        if ".m3u8" in req.url:
            print(f"M3U8_FOUND:{req.url}")
            return req.url

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