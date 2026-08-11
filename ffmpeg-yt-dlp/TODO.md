# TODO — ffmpeg-yt-dlp (midu.sh) — v5.0.0

## Funcionalidad (nueva)
- [ ] Cola de trabajos: encolar y ejecutar en serie con prioridades
- [ ] Modo pipe: recibir URLs por stdin para batch
- [ ] Presets personalizables: crear/editar/guardar presets propios
- [ ] Historial: últimas N operaciones para re-ejecutar
- [ ] Comparar antes/después: mostrar diferencia de tamaño al final
- [ ] Undo: deshacer última conversión (restaurar backup)
- [ ] Auto-naming: nombre inteligente según contenido/red social
- [ ] Folder output: organizar salida por fecha/tipo/plataforma
- [ ] Subtitle style: personalizar fuente, tamaño, color, posición
- [ ] Audio boost: amplificar audio bajo (ganancia configurable)
- [ ] HDR to SDR: convertir HDR a SDR con tone mapping
- [ ] SDR to HDR: convertir SDR a HDR fake
- [ ] Interpolación 60fps: minterpolate
- [ ] Slow motion con interpolación de frames
- [ ] Timelapse desde vídeo normal
- [ ] Mirror: efecto espejo horizontal/vertical
- [ ] Zoom/Ken Burns
- [ ] Vignette
- [ ] Picture in picture
- [ ] Side by side
- [ ] Collage: N vídeos en cuadrícula
- [ ] Transiciones: fade, wipe, slide, dissolve
- [ ] Film burn / Old film / Glitch
- [ ] LUT (.cube)
- [ ] Color grading: curvas + niveles + split toning
- [ ] Export/import presets a JSON

## Seguridad
- [ ] Hash verification post-proceso
- [ ] Input validation
- [ ] Command injection protection
- [ ] Temp file cleanup

## Tests
- [ ] Test por cada modo (33 modos)
- [ ] Test de descarga yt-dlp
- [ ] Test de colisión
- [ ] Test de checkpoint/resume
- [ ] Test de GPU detection
- [ ] Test de compose multi-track
- [ ] Test de HLS multi-quality

## Docker
- [ ] Multi-stage build
- [ ] Health check
- [ ] GPU support (NVIDIA/CUDA)
- [ ] Volumen entrada/salida persistente
- [ ] Imagen ARM (Raspberry Pi)
- [ ] Resource limits

## UX
- [ ] Progress bar real con ETA
- [ ] Colores adaptativos
- [ ] Atajos de teclado en menú
- [ ] Resumen antes de ejecutar
- [ ] Sonido al terminar (opcional)
- [ ] Búsqueda en menú

## Rendimiento
- [ ] Streaming de archivos grandes
- [ ] CPU affinity

## Integración
- [ ] ntfy.sh push
- [ ] Telegram bot
- [ ] Discord webhook

## Documentación
- [ ] Changelog v5.0.0
- [ ] Troubleshooting
- [ ] Roadmap visual

## Code quality
- [ ] Error handling consistente
- [ ] Logging estructurado (JSON)

## Ideas locas
- [ ] AI style transfer
- [ ] AI super resolution (Real-ESRGAN)
- [ ] AI frame interpolation (RIFE)
- [ ] AI subtitle generation (whisper)
- [ ] AI thumbnail generator
