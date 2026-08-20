# TODO — downloader_telegram

## Funcionalidad
- [ ] Reintentos automáticos
- [ ] Barra de progreso real
- [ ] Filtros por fecha
- [ ] Filtros por tipo (texto, fotos, vídeos, documentos)
- [ ] Filtros por tamaño
- [x] Exportar a JSON (backup local en `Clonar & Backup`)
- [ ] Exportar a CSV
- [ ] Rate limiting configurable
- [ ] Deduplicación
- [ ] Resume: continuar descarga desde donde se quedó
- [x] Modo espejo: clonar y mantener sincronizado
- [ ] Búsqueda en canales
- [ ] Filtros por usuario
- [ ] Filtros por reply
- [ ] Filtros por forwarded
- [ ] Filtros por media group
- [x] Descarga de storys
- [x] Descarga de polls (como `.txt` legible)
- [x] Descarga de contactos (como `.txt` legible)
- [x] Descarga de ubicaciones (coordenadas + Google Maps en `.txt`)
- [x] Descarga de voice messages (transcribir con whisper)
- [x] Descarga de stickers
- [x] Descarga de GIFs
- [ ] Notificación push (ntfy.sh)
- [x] Modo watch: monitorear canal (Vigilante ampliado)
- [ ] Webhook HTTP
- [ ] API REST
- [ ] Database SQLite
- [ ] Stats del canal
- [ ] Backup programado
- [x] Multi-canales simultáneos (Vigilante)
- [x] Filtros por palabra clave (Vigilante)
- [x] Vigilante: filtro por tipo de medio, emisores, excluir chats y temas
- [x] Vigilante: múltiples destinos, marcar razón, cooldown, resumen, config persistente
- [x] Auto-translate al descargar
- [ ] Hash verification
- [ ] Modo dry-run
- [ ] Exportar a Markdown/HTML/PDF
- [ ] OCR automático de imágenes
- [ ] Audio transcription con whisper
- [ ] Smart naming
- [ ] Folder structure automático

## Extra (añadido)
- [x] Módulo 10: Fijar / Desfijar mensajes (pin/unpin, chat y tema de foro)
- [x] Chats: crear carpeta, mover a carpeta, silenciar, fijar chat
- [x] Backup/restaurar de clonación en archivo local

## Seguridad
- [ ] Cifrado de descargas (AES)
- [ ] Audit log
- [ ] Rate limit por canal
- [ ] Session rotation
- [ ] Backup de session

## Tests
- [ ] Test de descarga de mensaje simple
- [ ] Test de descarga de multimedia
- [ ] Test de clonación de canal
- [ ] Test de filtros
- [ ] Test de deduplicación
- [ ] Test de resume
- [ ] Test de sesión cifrada
- [ ] Test de exportación JSON/CSV

## Docker
- [ ] Multi-stage build
- [ ] Health check
- [ ] Variables de entorno para todo
- [ ] Imagen ARM
- [ ] Resource limits

## UX
- [ ] Menú con submenús navegables
- [ ] Búsqueda en menú
- [ ] Historial de comandos
- [ ] Preview de primeros mensajes
- [ ] Confirmación masiva (>100 mensajes)
- [ ] Help contextual

## Rendimiento
- [ ] Descarga paralela
- [ ] Chunked download
- [ ] Connection pooling
- [ ] Cache de metadata

## Integración
- [ ] ntfy.sh push
- [ ] Telegram bot
- [ ] Discord webhook
- [ ] Plex/Jellyfin auto-add

## Documentación
- [ ] Guía paso a paso
- [ ] Troubleshooting
- [ ] Changelog

## Ideas locas
- [ ] AI caption generator
- [ ] Sentiment analysis
- [ ] Word cloud
- [ ] Analytics dashboard
