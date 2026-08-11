# TODO — pdfmanager

## Funcionalidad
- [ ] Modo batch: procesar todos los PDFs de una carpeta sin menú interactivo
- [ ] Renombrado automático: extraer nombre del contenido del PDF para salida
- [ ] Log de operaciones: guardar qué se hizo a cada archivo y cuándo
- [ ] Modo silencioso: sin progreso, sin colores, solo resultado (para scripts)
- [ ] Extracción de texto: sacar texto de PDFs escaneados con OCR (tesseract)
- [ ] Conversión a Word: exportar PDFs a DOCX editables
- [ ] Conversión a imágenes: PDF a JPG/PNG página por página
- [ ] Combinación selectiva: elegir páginas específicas de varios PDFs para unir
- [ ] Rotación de páginas: girar páginas individuales dentro de un PDF
- [ ] Marcadores: añadir/eliminar marcadores (bookmarks) en el PDF
- [ ] Watermark masivo: poner marca de agua en todos los PDFs de una carpeta
- [ ] Proteger con contraseña: añadir contraseña de apertura a PDFs libres
- [ ] Eliminar páginas: quitar páginas específicas de un PDF
- [ ] Extraer páginas: sacar páginas específicas a un PDF nuevo
- [ ] Mezclar PDFs: intercalar páginas de dos PDFs (1 de A, 1 de B, etc.)
- [ ] Añadir numeración: poner números de página automáticamente
- [ ] Redimensionar páginas: cambiar tamaño de papel (A4, Letter, etc.)
- [ ] OCR batch: procesar varios PDFs escaneados de golpe
- [ ] Reparar PDFs corruptos: intentar recuperar datos de PDFs dañados
- [ ] Comparar PDFs: mostrar diferencias entre dos versiones
- [ ] Extraer imágenes: sacar todas las imágenes de un PDF
- [ ] Añadir cabecera/pie: poner texto fijo en todas las páginas
- [ ] Modo watch: monitoring de carpeta, procesar nuevos PDFs automáticamente
- [ ] Interfaz web: panel en el navegador para arrastrar y soltar PDFs
- [ ] API REST: endpoint para procesar PDFs vía HTTP
- [ ] Plugin system: permitir añadir operaciones personalizadas
- [ ] Cola de trabajos: encolar múltiples operaciones y ejecutar en serie
- [ ] Reintentos: si falla un PDF, reintentar N veces antes de skippear
- [ ] Notificación push: avisar por ntfy.sh cuando termina el procesamiento
- [ ] Estadísticas: mostrar resumen al final (X desbloqueados, Y comprimidos, etc.)
- [ ] Backup automático: copiar PDFs originales antes de modificar
- [ ] Perfiles: guardar configuraciones de procesamiento
- [ ] Soporte PDF/A: convertir a formato de archivo PDF/A
- [ ] Eliminar metadata: limpiar información personal de los PDFs
- [ ] Extraer metadata: mostrar autor, título, fechas, software usado
- [ ] Firma digital: verificar si un PDF está firmado digitalmente
- [ ] Merge por bookmarks: unir PDFs manteniendo los bookmarks como separadores
- [ ] Dividir por bookmarks: separar un PDF en varios según sus bookmarks
- [ ] Compresión por lotes: comprimir todos los PDFs de una carpeta
- [ ] Eliminar restricciones en lote: desbloquear varios PDFs de golpe
- [ ] Historial: recordar los últimos 50 PDFs procesados
- [ ] Undo: deshacer la última operación (restaurar desde backup)
- [ ] Soporte PDF protegido con owner password
- [ ] Verificar integridad: comprobar si un PDF está dañado antes de procesarlo
- [ ] Convertir HTML a PDF: renderizar páginas web a PDF
- [ ] Convertir Markdown a PDF: renderizar MD a PDF con estilos
- [ ] Plantillas: crear PDFs desde plantillas con campos rellenables
- [ ] Formularios: rellenar campos de formularios PDF automáticamente
- [ ] Filtros por tamaño: procesar solo PDFs mayores/menores de X MB
- [ ] Filtros por fecha: procesar solo PDFs modificados en un rango
- [ ] Modo dry-run: mostrar qué se haría sin ejecutar
- [ ] Exportar log a CSV

## Tests
- [ ] Test de desbloqueo con PDF protegido por owner password
- [ ] Test de desbloqueo con PDF protegido por opening password
- [ ] Test de unión de PDFs
- [ ] Test de división de PDFs
- [ ] Test de compresión
- [ ] Test de conversión de imágenes a PDF
- [ ] Test de PDF corrupto
- [ ] Test de PDF vacío
- [ ] Test de PDF con 0 páginas
- [ ] Test de PDF con 1000+ páginas
- [ ] Test de modo batch
- [ ] Test de renombrado automático
- [ ] Test de OCR
- [ ] Test de extracción de texto
- [ ] Test de rendimiento con archivos grandes

## Docker
- [ ] Multi-stage build
- [ ] Health check
- [ ] Variables de entorno para rutas y opciones
- [ ] Imagen ARM (Raspberry Pi)
- [ ] Imagen minimalista (Alpine)
- [ ] Watch mode en Docker
- [ ] Resource limits (mem/cpu)

## UX
- [ ] Barra de progreso real con tqdm
- [ ] Colores adaptativos
- [ ] Soporte terminal sin TTY
- [ ] Mensajes de error con sugerencias
- [ ] Atajos de teclado en menú
- [ ] Modo verbose/debug
- [ ] Confirmación antes de sobrescribir
- [ ] Resumen antes de ejecutar
- [ ] Tiempo estimado
- [ ] Sonido al terminar (opcional)

## Seguridad
- [ ] Verificar integridad (hash SHA256)
- [ ] No sobrescribir originales por defecto
- [ ] Audit log

## Documentación
- [ ] Ejemplos reales (certificados, títulos, contratos)
- [ ] Troubleshooting
- [ ] Changelog

## Rendimiento
- [ ] Procesamiento paralelo (multiprocess)
- [ ] Cache de resultados
- [ ] Streaming de archivos grandes

## Integración
- [ ] ntfy.sh push
- [ ] Telegram bot

## Ideas locas
- [ ] PDF to comic (CBR)
- [ ] PDF to audiobook (TTS)
- [ ] PDF translator (LLM)
- [ ] PDF summarizer (IA)
