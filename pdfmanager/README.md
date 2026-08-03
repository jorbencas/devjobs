# 🥷 PDF Ninja Master

Gestor definitivo de documentos PDF: desbloquear, unir, dividir y comprimir.



## Requisitos

- Docker

## Uso

### Con Docker (recomendado)

```bash
docker compose build
docker compose up
```

Los PDFs se procesan desde `./pdfs_protegidos/` y salen en `./pdfs_libres/`.

### Sin Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
python desproteger_pdf.py
```

## Menú interactivo

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
└── README.md
```

## Dependencias Docker

Se instalan automáticamente en la imagen:

- `PyMuPDF` (fitz) - Lectura y manipulación de PDFs
- `pikepdf` - Eliminación de restricciones de seguridad
- `rich` - Interfaz de terminal con colores
- `tqdm` - Barras de progreso
- `readchar` - Navegación con teclado
- `Pillow` - Conversión de imágenes
