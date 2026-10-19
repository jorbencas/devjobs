#!/bin/bash
# Instala opencode (CLI) de forma NORMAL (script oficial) en Ubuntu, incluidos
# los antiguos/EOL. No usa Docker ni nada raro.
#
# Uso:  bash servicios/instalar_opencode.sh
#
# Nota glibc: el binario nativo de opencode exige glibc >= 2.17 (versiones >= 1.15.4,
# ya con el fix). Las 1.14.49–1.15.3 pedían 2.29 y fallaban en distros viejas.
set -e

oc_bin=""
for d in "$HOME/.opencode/bin" "$HOME/.local/bin" "/usr/local/bin"; do
    [ -x "$d/opencode" ] && oc_bin="$d/opencode" && break
done

if [ -n "$oc_bin" ]; then
    echo "[i] opencode ya presente: $oc_bin"
fi

# glibc mínima (solo informativo).
if command -v ldd >/dev/null 2>&1; then
    glibc="$(ldd --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+$')"
    echo "[i] glibc detectada: ${glibc:-?}  (opencode necesita >= 2.17)"
fi

# Dependencias mínimas del instalador.
command -v curl >/dev/null 2>&1 || sudo apt-get install -y curl
command -v tar  >/dev/null 2>&1 || sudo apt-get install -y tar

echo "[→] Instalando/actualizando opencode (script oficial)..."
curl -fsSL https://opencode.ai/install | bash

# El instalador añade ~/.opencode/bin al PATH en ~/.bashrc; aquí garantizamos
# que el binario quede accesible para la verificación de ahora mismo.
for d in "$HOME/.opencode/bin" "$HOME/.local/bin"; do
    [ -d "$d" ] && export PATH="$d:$PATH"
done

echo "[→] Verificando arranque..."
if command -v opencode >/dev/null 2>&1; then
    opencode --version
    echo "[✓] opencode instalado. Abre una terminal nueva (o: source ~/.bashrc) y ejecuta: opencode"
else
    echo "[x] No encuentro 'opencode' en el PATH. Cierra sesión y vuelve a entrar, o ejecuta: source ~/.bashrc"
    exit 1
fi
