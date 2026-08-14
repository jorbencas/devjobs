#!/usr/bin/env python3
"""
AULA Downloader - Versión final que funciona
Descarga segmentos HLS con sub-playlists de audio/video por separado
Uso: python aula_downloader_funciona.py [URL1] [URL2] ...
"""

import os
import re
import json
import sys
import time
import shutil
import subprocess
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn

console = Console()

HEADERS_AULA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
HEADERS_VIMEO = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://vimeo.com/'}


def styled_info(msg):
    console.print(f"  [bold blue]ℹ[/bold blue] {msg}")

def styled_success(msg):
    console.print(f"  [bold green]✓[/bold green] {msg}")

def styled_error(msg):
    console.print(f"  [bold red]✗[/bold red] {msg}")

def styled_warning(msg):
    console.print(f"  [bold yellow]![/bold yellow] {msg}")


def format_time(seconds):
    """Format seconds to human readable time"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s:02d}s"
    else:
        h, remainder = divmod(int(seconds), 3600)
        m, s = divmod(remainder, 60)
        return f"{h}h {m:02d}m {s:02d}s"


def format_size(bytes_size):
    """Format bytes to human readable size"""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"


def parse_m3u8(content, base_url):
    """Parse M3U8 playlist - returns (init_url, segments)"""
    segments = []
    init_url = None
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Extract init segment from #EXT-X-MAP:URI="..."
        if line.startswith('#EXT-X-MAP:'):
            uri_match = re.search(r'URI="([^"]+)"', line)
            if uri_match:
                init_url = urljoin(base_url, uri_match.group(1))
            continue
        if line.startswith('#'):
            continue
        full_url = urljoin(base_url, line)
        segments.append(full_url)
    return init_url, segments


def parse_master_m3u8(content, base_url):
    """Parse master M3U8 and extract audio/video/subtitle playlist URLs"""
    result = {'audio': None, 'video': None, 'subtitle': None}
    current_type = None
    
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('#EXT-X-MEDIA:'):
            # Extract URI from the same line (Vimeo format)
            uri_match = re.search(r'URI="([^"]+)"', line)
            if uri_match:
                full_url = urljoin(base_url, uri_match.group(1))
                if 'TYPE=AUDIO' in line:
                    result['audio'] = full_url
                elif 'TYPE=SUBTITLES' in line:
                    result['subtitle'] = full_url
            else:
                # URI on next line (standard format)
                if 'TYPE=AUDIO' in line:
                    current_type = 'audio'
                elif 'TYPE=SUBTITLES' in line:
                    current_type = 'subtitle'
                else:
                    current_type = None
        elif line.startswith('#EXT-X-STREAM-INF:'):
            current_type = 'video'
        elif line and not line.startswith('#'):
            full_url = urljoin(base_url, line)
            if current_type in result:
                result[current_type] = full_url
            current_type = None
    
    return result


def download_file(url, output_file, session):
    """Download a file"""
    try:
        resp = session.get(url, timeout=60)
        if resp.status_code == 200:
            with open(output_file, 'wb') as f:
                f.write(resp.content)
            return True
        else:
            return False
    except Exception as e:
        styled_error(f"  Error descargando: {e}")
        return False


def concat_with_python(segment_files, output_file):
    """Concatenate files using Python"""
    with open(output_file, 'wb') as outfile:
        for seg_file in segment_files:
            with open(seg_file, 'rb') as infile:
                outfile.write(infile.read())
    return os.path.getsize(output_file) > 0


def main():
    console.print()
    console.print(Panel(
        "[bold white]AULA Downloader[/bold white]\n"
        "[bold green]Descarga de vídeos Vimeo embebidos[/bold green]",
        title="📚 AULA",
        border_style="blue"
    ))
    console.print()

    # Check for command-line arguments
    urls = sys.argv[1:] if len(sys.argv) > 1 else []

    if urls:
        # Non-interactive mode: URLs from arguments.
        # Credenciales SOLO desde variables de entorno (nunca hardcodeadas).
        username = os.environ.get('AULA_USER')
        password = os.environ.get('AULA_PASS')
        if not username or not password:
            styled_error("Modo no-interactivo requiere AULA_USER y AULA_PASS "
                         "(variables de entorno).")
            styled_info("Ejemplo: AULA_USER=... AULA_PASS=... python aula_downloader_funciona.py URL")
            return
        styled_info(f"Modo no-interactivo: {len(urls)} URLs")
    else:
        # Interactive mode
        from InquirerPy import inquirer
        username = inquirer.text(message="Usuario:").execute()
        password = inquirer.secret(message="Contraseña:").execute()
        folder_url = inquirer.text(
            message="URL carpeta:",
            default="https://aula.pmoposiciones.com/mod/folder/view.php?id=4189"
        ).execute()
        urls = [folder_url]

    # Login
    styled_info("Login con requests...")
    session = requests.Session()
    session.headers.update(HEADERS_AULA)

    resp = session.get("https://aula.pmoposiciones.com/login/index.php")
    soup = BeautifulSoup(resp.text, 'html.parser')
    token = soup.find('input', {'name': 'logintoken'}).get('value', '')

    resp = session.post("https://aula.pmoposiciones.com/login/index.php", data={
        'username': username,
        'password': password,
        'logintoken': token,
        'anchor': ''
    })

    if "login/index.php" in resp.url:
        styled_error("Login falló")
        return

    styled_success("Login OK")

    # Create output dir
    out_dir = "descargas"
    os.makedirs(out_dir, exist_ok=True)

    # Pre-scan: count total videos and cache HTML
    styled_info("Pre-escaneando carpetas...")
    total_expected = 0
    folder_html = {}
    for folder_url in urls:
        resp = session.get(folder_url)
        folder_html[folder_url] = resp.text
        soup = BeautifulSoup(resp.text, 'html.parser')
        count = len(soup.find_all('iframe', src=re.compile(r'vimeo\.com')))
        total_expected += count
        styled_info(f"  {folder_url.split('id=')[1]}: {count} vídeos")

    styled_info(f"Total esperado: {total_expected} vídeos en {len(urls)} carpetas")
    console.print()

    # Start timer
    global_start = time.time()
    downloaded_videos = []
    failed_videos = []

    # Process each URL
    total_videos = 0
    for url_idx, folder_url in enumerate(urls):
        console.print()
        styled_info(f"Procesando carpeta [{url_idx+1}/{len(urls)}]: {folder_url}")

        # Use cached HTML from pre-scan
        soup = BeautifulSoup(folder_html[folder_url], 'html.parser')
        iframes = soup.find_all('iframe', src=re.compile(r'vimeo\.com'))

        # Extract course name from page title
        title_tag = soup.find('title')
        course_name = title_tag.text.split('|')[0].strip() if title_tag else f"curso_{url_idx+1}"
        # Clean course name for filesystem
        course_name = re.sub(r'[^\w\s-]', '', course_name).strip()
        course_name = re.sub(r'\s+', '_', course_name)[:50]

        styled_info(f"  Curso: {course_name}")
        styled_info(f"  Encontrados {len(iframes)} vídeos Vimeo")

        if not iframes:
            styled_error("  No hay vídeos en esta carpeta")
            continue

        # List videos
        videos = []
        for i, iframe in enumerate(iframes):
            src = iframe.get('src', '')
            match = re.search(r'video/(\d+)', src)
            video_id = match.group(1) if match else None
            h_match = re.search(r'h=([a-f0-9]+)', src)
            h_param = h_match.group(1) if h_match else None
            if video_id:
                videos.append((video_id, h_param))

        # Create course directory
        course_dir = os.path.join(out_dir, course_name)
        os.makedirs(course_dir, exist_ok=True)

        # Process each video
        for i, (video_id, h_param) in enumerate(videos):
            global_count = total_videos + i + 1
            video_start = time.time()
            styled_info(f"\n  [{global_count}/{total_expected}] Vídeo {video_id} (carpeta {url_idx+1}/{len(urls)}, {i+1}/{len(videos)})")

            # Get player HTML
            player_url = f"https://player.vimeo.com/video/{video_id}"
            params = {'title': '0', 'byline': '0', 'portrait': '0', 'pip': '0', 'dnt': '1'}
            if h_param:
                params['h'] = h_param

            resp = session.get(player_url, params=params, headers={
                **HEADERS_AULA,
                'Referer': 'https://aula.pmoposiciones.com/',
            })

            # Extract playerConfig
            start_marker = "window.playerConfig = "
            start_pos = resp.text.find(start_marker)
            if start_pos == -1:
                styled_error("  No se encontró playerConfig")
                continue

            start_pos += len(start_marker)
            end_patterns = ["}}</script>", "}};</script>"]
            config = None
            for pattern in end_patterns:
                pos = resp.text.find(pattern, start_pos)
                if pos != -1:
                    raw_json = resp.text[start_pos:pos+2]
                    try:
                        config = json.loads(raw_json)
                    except:
                        pass
                    break

            if not config:
                styled_error("  Error parseando playerConfig")
                continue

            styled_success("  playerConfig encontrado")

            # Get video title from config
            video_title = config.get('video', {}).get('title', f'video_{video_id}')
            video_title = re.sub(r'[^\w\s-]', '', video_title).strip()
            video_title = re.sub(r'\s+', '_', video_title)[:80]

            # Get HLS URL
            hls = config.get('request', {}).get('files', {}).get('hls', {})
            cdns = hls.get('cdns', {})
            hls_url = None
            for cdn_name, cdn_data in cdns.items():
                hls_url = cdn_data.get('avc_url')
                if hls_url:
                    break

            if not hls_url:
                styled_error("  No se encontró URL HLS")
                continue

            styled_info(f"  URL HLS obtenida")

            # Get master m3u8
            resp = session.get(hls_url, headers=HEADERS_VIMEO)

            if resp.status_code != 200:
                styled_error(f"  Error obteniendo m3u8: {resp.status_code}")
                continue

            # Parse master playlist
            playlists = parse_master_m3u8(resp.text, hls_url)

            # Create segment dir (unique per video to avoid conflicts)
            seg_dir = os.path.join(course_dir, f"_seg_{video_id}_{i}")
            if os.path.exists(seg_dir):
                shutil.rmtree(seg_dir, ignore_errors=True)
            os.makedirs(seg_dir, exist_ok=True)

            all_files = []

            # Download video segments
            video_init = None
            if playlists['video']:
                styled_info("  Descargando pistas de vídeo...")
                resp = session.get(playlists['video'], headers=HEADERS_VIMEO)
                if resp.status_code == 200:
                    video_init, video_segments = parse_m3u8(resp.text, playlists['video'])
                    styled_info(f"  {len(video_segments)} segmentos de vídeo, init={'Sí' if video_init else 'No'}")

                    # Download init segment first
                    if video_init:
                        init_file = os.path.join(seg_dir, "video_init.mp4")
                        if download_file(video_init, init_file, session):
                            all_files.append(init_file)
                            styled_info("  Init video descargado")

                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        TimeElapsedColumn(),
                        TimeRemainingColumn(),
                        console=console
                    ) as progress:
                        task = progress.add_task("  Vídeo", total=len(video_segments))
                        for j, seg_url in enumerate(video_segments):
                            seg_file = os.path.join(seg_dir, f"video_{j:04d}.m4s")
                            if download_file(seg_url, seg_file, session):
                                all_files.append(seg_file)
                            progress.update(task, advance=1)

            # Download audio segments
            audio_init = None
            audio_files = []
            if playlists['audio']:
                styled_info("  Descargando pistas de audio...")
                resp = session.get(playlists['audio'], headers=HEADERS_VIMEO)
                if resp.status_code == 200:
                    audio_init, audio_segments = parse_m3u8(resp.text, playlists['audio'])
                    styled_info(f"  {len(audio_segments)} segmentos de audio, init={'Sí' if audio_init else 'No'}")

                    if audio_init:
                        init_file = os.path.join(seg_dir, "audio_init.mp4")
                        if download_file(audio_init, init_file, session):
                            audio_files.append(init_file)
                            styled_info("  Init audio descargado")

                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        TimeElapsedColumn(),
                        TimeRemainingColumn(),
                        console=console
                    ) as progress:
                        task = progress.add_task("  Audio", total=len(audio_segments))
                        for j, seg_url in enumerate(audio_segments):
                            seg_file = os.path.join(seg_dir, f"audio_{j:04d}.m4s")
                            if download_file(seg_url, seg_file, session):
                                audio_files.append(seg_file)
                            progress.update(task, advance=1)

            # Concatenate video
            output_video = os.path.join(seg_dir, "video_only.mp4")
            styled_info("  Concatenando vídeo...")
            video_files = [f for f in all_files if 'video_init' in os.path.basename(f) or 'video_' in os.path.basename(f)]
            if concat_with_python(video_files, output_video):
                styled_success(f"  Vídeo concat: {os.path.getsize(output_video) / 1024 / 1024:.1f} MB")
            else:
                styled_error("  Error concatenando vídeo")

            # Concatenate audio
            output_audio = os.path.join(seg_dir, "audio_only.m4s")
            if audio_files:
                styled_info("  Concatenando audio...")
                if concat_with_python(audio_files, output_audio):
                    styled_success(f"  Audio concat: {os.path.getsize(output_audio) / 1024 / 1024:.1f} MB")
                else:
                    styled_error("  Error concatenando audio")

            # Merge audio + video with ffmpeg if both exist
            final_output = os.path.join(course_dir, f"{i+1:02d}_{video_title}.mp4")

            if os.path.exists(output_video) and os.path.exists(output_audio) and os.path.getsize(output_audio) > 0:
                styled_info("  Mezclando audio + vídeo con ffmpeg...")
                try:
                    subprocess.run([
                        'ffmpeg', '-y',
                        '-i', output_video,
                        '-i', output_audio,
                        '-c:v', 'copy',
                        '-c:a', 'copy',
                        '-movflags', '+faststart',
                        final_output
                    ], capture_output=True, check=True)
                    total_videos += 1
                except (subprocess.CalledProcessError, FileNotFoundError, Exception):
                    styled_warning("  ffmpeg no disponible, guardando solo vídeo")
                    shutil.copy2(output_video, final_output)
                    total_videos += 1
            elif os.path.exists(output_video):
                shutil.copy2(output_video, final_output)
                total_videos += 1
            else:
                styled_error("  No se pudo guardar el vídeo")
                failed_videos.append((video_id, "No se pudo guardar"))
                continue

            # Clean up
            shutil.rmtree(seg_dir, ignore_errors=True)

            # Per-video summary
            video_elapsed = time.time() - video_start
            file_size = os.path.getsize(final_output) if os.path.exists(final_output) else 0
            speed = file_size / video_elapsed if video_elapsed > 0 else 0
            remaining = total_expected - global_count
            global_elapsed = time.time() - global_start
            eta = (global_elapsed / global_count * remaining) if global_count > 0 else 0

            downloaded_videos.append({
                'id': video_id,
                'file': final_output,
                'size': file_size,
                'time': video_elapsed,
            })

            styled_success(
                f"  [{global_count}/{total_expected}] "
                f"{os.path.basename(final_output)} "
                f"({format_size(file_size)}) "
                f"en {format_time(video_elapsed)} "
                f"({format_size(speed)}/s)"
            )
            styled_info(
                f"  Quedan {remaining} vídeos | "
                f"Total: {format_time(global_elapsed)} | "
                f"ETA: ~{format_time(eta)}"
            )

    # Final summary
    global_elapsed = time.time() - global_start
    total_size = sum(v['size'] for v in downloaded_videos)
    avg_speed = total_size / global_elapsed if global_elapsed > 0 else 0

    console.print()
    console.print(Panel(
        f"[bold green]Descarga completada[/bold green]\n\n"
        f"  [bold]Vídeos:[/bold] {total_videos}/{total_expected} descargados"
        + (f", {len(failed_videos)} fallidos" if failed_videos else "") + "\n"
        f"  [bold]Tamaño total:[/bold] {format_size(total_size)}\n"
        f"  [bold]Tiempo total:[/bold] {format_time(global_elapsed)}\n"
        f"  [bold]Velocidad media:[/bold] {format_size(avg_speed)}/s\n"
        f"  [bold]Ubicación:[/bold] {os.path.abspath(out_dir)}",
        title="📚 Resumen",
        border_style="green"
    ))

    if failed_videos:
        console.print()
        styled_warning("Vídeos fallidos:")
        for vid, reason in failed_videos:
            styled_error(f"  {vid}: {reason}")

    return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelado[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        sys.exit(1)
