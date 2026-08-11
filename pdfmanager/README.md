# PDF Ninja Master

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Gestor definitivo de documentos PDF: desbloquear, unir, dividir y comprimir.

## Requisitos

- Docker

## Despliegue

```bash
git clone https://github.com/jorge-bencas/devjobs.git
cd devjobs/pdfmanager
docker compose build
docker compose up
```

### Sin Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pymupdf rich inquirerpy tqdm readchar pikepdf Pillow
python desproteger_pdf.py
```

## Uso

Los PDFs se procesan desde `./pdfs_protegidos/` y salen en `./pdfs_libres/`.

### Menú interactivo

```
1. Desbloqueo Limpio
2. Desbloqueo + COMPRESIÓN
3. Herramienta: UNIR PDFs
4. Herramienta: DIVIDIR PDF
5. Imágenes a PDF
6. Salir
```

## Estructura

```
pdfmanager/
├── desproteger_pdf.py    # script principal
├── Dockerfile            # imagen Python + dependencias
├── docker-compose.yml    # servicio con volúmenes
├── pdfs_protegidos/      # coloca aquí los PDFs a procesar
├── pdfs_libres/          # aquí salen los resultados
├── LICENSE               # MIT
└── README.md
```

## Dependencias

Se instalan automáticamente en la imagen Docker:

- `PyMuPDF` (fitz) — Lectura y manipulación de PDFs
- `pikepdf` — Eliminación de restricciones de seguridad
- `rich` — Interfaz de terminal con colores
- `tqdm` — Barras de progreso
- `readchar` — Navegación con teclado
- `Pillow` — Conversión de imágenes

## Blog

- [PDF Ninja Master: Gestor de PDFs con Docker](https://blog-jorbencas.vercel.app/proyectos/pdf-ninja-master/)
