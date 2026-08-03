# 📦 Telegram Ultimate Toolbox

Descargador masivo, clonador y vigilante de contenido en Telegram.



## Requisitos

- Docker
- Cuenta de Telegram con API ID/Hash (obtener en [my.telegram.org](https://my.telegram.org))

## Uso

### Con Docker (recomendado)

```bash
docker compose build
docker compose up
```

### Sin Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
python test_download_protected_content_telegram.py
```

## Generador de sesiones portátiles

```bash
docker compose run --rm telegram python test_string.py
```

Genera una `StringSession` para ejecutar en la nube (GitHub Actions, Heroku) sin archivos `.session`.

## Menú principal

```
1. Descargas Masivas (Enlace/Rango/TXT)
2. Clonación & Backup (Filtro + Traducción)
3. Modo Vigilante (Alertas por palabras)
4. Re-configurar / Salir
```

## Estructura

```
downloader_telegram/
├── test_download_protected_content_telegram.py  # script principal
├── test_string.py                               # generador de sesiones
├── Dockerfile                                   # imagen Python + dependencias
├── docker-compose.yml                           # servicio con volúmenes
├── config.bin                                   # credenciales cifradas (AES)
├── secret.key                                   # llave de cifrado
├── ultimate_session.session                     # sesión de Telegram
├── Descargas_Telegram/                          # carpeta de descargas
└── README.md
```

## Seguridad

- Las credenciales (API ID/Hash) se cifran con AES en `config.bin`
- La llave de cifrado se guarda en `secret.key` (si la borras, pierdes acceso al config)
- El archivo `.session` contiene el token de persistencia
- **Nunca commitees** `config.bin`, `secret.key` ni `.session`

## Dependencias Docker

Se instalan automáticamente en la imagen:

- `Telethon` - Cliente de Telegram para Python
- `cryptography` (Fernet) - Cifrado AES de credenciales
- `mtranslate` - Traducción automática
- `cryptg` - Aceleración de descargas

## Blog

- [Telegram Ultimate Toolbox: Descargador Masivo y Vigilante](https://blog-jorbencas.vercel.app/proyectos/telegram-ultimate-toolbox/)
