# PDF Ninja Master

<p align="center">
  <strong>Desbloquea, une, divide y comprime PDFs con calidad original — sin
  reescribir el documento y con un menú interactivo en terminal.</strong>
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://github.com/jorbencas/devjobs"><img src="https://img.shields.io/badge/Self--hosted-Docker-blue.svg" alt="Self-hosted: Docker"></a>
  <a href="https://github.com/jorbencas/devjobs/tree/main/pdfmanager"><img src="https://img.shields.io/badge/Python-3.11-blue.svg?logo=python&logoColor=white" alt="Python 3.11"></a>
</p>

Gestor definitivo de documentos PDF: **desbloquear, unir, dividir y comprimir**,
directo desde tu terminal o en un contenedor Docker.

## 📑 Tabla de contenidos

- [Características](#características)
- [Instalación rápida](#instalación-rápida)
- [Uso](#uso)
- [Sin Docker](#sin-docker)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Dependencias](#dependencias)
- [Blog](#blog)
- [Contribuir](#contribuir)
- [Licencia](#licencia)

## Características

| Función | Menú | Qué hace |
|---|---|---|
| Desbloqueo Limpio | 1 | Elimina restricciones de seguridad **sin reescribir** el contenido (con `pikepdf`) |
| Desbloqueo + Compresión | 2 | Desbloquea y reduce el peso del documento |
| Unir PDFs | 3 | Combina varios PDFs en uno solo con interfaz interactiva |
| Dividir PDF | 4 | Separa un PDF en archivos individuales (`split_*.pdf`) |
| Imágenes a PDF | 5 | Convierte imágenes a un documento PDF |

## Instalación rápida

```bash
git clone https://github.com/jorbencas/devjobs.git
cd devjobs/pdfmanager
docker compose build
docker compose up
```

## Uso

Coloca los PDFs a procesar en `./pdfs_protegidos/`; los resultados salen en
`./pdfs_libres/`.

```
1. Desbloqueo Limpio
2. Desbloqueo + COMPRESIÓN
3. Herramienta: UNIR PDFs
4. Herramienta: DIVIDIR PDF
5. Imágenes a PDF
6. Salir
```

## Sin Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pymupdf rich inquirerpy tqdm readchar pikepdf Pillow
python desproteger_pdf.py
```

## Estructura del proyecto

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

## Contribuir

Los *issues* y *pull requests* son bienvenidos. Mantén el README al día con los
cambios y añade pruebas cuando aplique.

## Licencia

Distribuido bajo la **Licencia MIT**. Consulta [LICENSE](./LICENSE).
