import os
import re
import sys
import time
import shutil
import logging
import threading
from typing import Dict, Any, Optional
from pathlib import Path
import yt_dlp

backend_path = Path(__file__).resolve().parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

try:
    from config import (
        BASE_DIR, FFMPEG_PATH, TEMP_DIR, DOWNLOADS_DIR,
        PROXY_URL, COOKIES_PATH, PO_TOKEN,
        MAX_CONCURRENT_DOWNLOADS, FILE_RETENTION_SECONDS
    )
except ImportError:
    from backend.config import (
        BASE_DIR, FFMPEG_PATH, TEMP_DIR, DOWNLOADS_DIR,
        PROXY_URL, COOKIES_PATH, PO_TOKEN,
        MAX_CONCURRENT_DOWNLOADS, FILE_RETENTION_SECONDS
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("6DownEngine")

active_tasks: Dict[str, Dict[str, Any]] = {}
download_semaphore = threading.BoundedSemaphore(MAX_CONCURRENT_DOWNLOADS)

def normalize_youtube_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    url = re.sub(r'[?&]list=[^&]+', '', url)
    url = re.sub(r'[?&]index=[^&]+', '', url)
    url = re.sub(r'[?&]start_radio=[^&]+', '', url)
    url = re.sub(r'[?&]si=[^&]+', '', url)
    url = re.sub(r'\?&', '?', url)
    url = re.sub(r'\?$', '', url)
    return url

def clean_error_message(err: Exception) -> str:
    msg = str(err)
    if "Private video" in msg:
        return "This video is private."
    if "Video unavailable" in msg:
        return "This video is unavailable or has been removed."
    if "Sign in to confirm your age" in msg:
        return "This video is age-restricted."
    if "Sign in to confirm you're not a bot" in msg or "429" in msg:
        return "YouTube cloud rate limit reached. Configure COOKIES_PATH or PROXY_URL in environment."
    if "Errno 22" in msg:
        return "Filesystem path error. Please try again."
    msg = re.sub(r'^ERROR:\s*', '', msg)
    msg = re.sub(r'\[youtube\]\s*', '', msg)
    msg = re.sub(r'\[youtube:tab\]\s*', '', msg)
    return msg[:200] if len(msg) > 200 else msg

def sanitize_filename(name: str) -> str:
    if not name:
        return "6Down_Media"
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = "".join(ch for ch in name if ord(ch) >= 32)
    name = re.sub(r"\s+", " ", name).strip().rstrip("._ ")
    return name[:120] if len(name) > 120 else (name or "6Down_Media")

def format_bytes(size: Optional[float]) -> str:
    if size is None or size <= 0:
        return "0 MB"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"

def format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def cleanup_old_files():
    try:
        now = time.time()
        for f in DOWNLOADS_DIR.iterdir():
            if f.is_file() and (now - f.stat().st_mtime) > FILE_RETENTION_SECONDS:
                try:
                    f.unlink()
                except Exception:
                    pass
        if len(active_tasks) > 80:
            keys_to_remove = list(active_tasks.keys())[:-50]
            for k in keys_to_remove:
                active_tasks.pop(k, None)
    except Exception:
        pass

def build_base_ydl_opts() -> Dict[str, Any]:
    extractor_args: Dict[str, Any] = {
        'youtubetab': {'skip': ['authcheck']},
    }
    if PO_TOKEN:
        extractor_args['youtube'] = {'po_token': [PO_TOKEN]}

    opts: Dict[str, Any] = {
        'quiet': True,
        'no_warnings': True,
        'cachedir': False,
        'noplaylist': True,
        'nocheckcertificate': True,
        'windowsfilenames': True,
        'socket_timeout': 30,
        'js_runtimes': {'node': {}},
        'extractor_args': extractor_args,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    if FFMPEG_PATH:
        opts['ffmpeg_location'] = FFMPEG_PATH

    cookie_file = COOKIES_PATH
    if not cookie_file or not os.path.exists(cookie_file):
        for candidate in [BASE_DIR / "cookies" / "cookies.txt", BASE_DIR / "cookies.txt"]:
            if candidate.exists():
                cookie_file = str(candidate)
                break

    if cookie_file and os.path.exists(cookie_file):
        opts['cookiefile'] = cookie_file

    if PROXY_URL:
        opts['proxy'] = PROXY_URL

    return opts

def execute_with_fallback(base_opts: Dict[str, Any], url: str, download: bool = False) -> Dict[str, Any]:
    strategies = []

    # Strategy 1: Combined iOS & Android clients (Bypasses bot checks for BOTH standard & official music/VEVO videos)
    s1 = dict(base_opts)
    s1['extractor_args'] = {
        'youtube': {'player_client': ['ios', 'android']},
        'youtubetab': {'skip': ['authcheck']}
    }
    if download and 'format' in s1 and not s1['format'].endswith('/best'):
        s1['format'] = s1['format'] + '/best'
    strategies.append(s1)

    # Strategy 2: Base options with cookies
    strategies.append(dict(base_opts))

    # Strategy 3: Clean Request without cookies
    if base_opts.get('cookiefile'):
        s3 = dict(base_opts)
        s3.pop('cookiefile', None)
        strategies.append(s3)

    last_error = None
    for idx, opts in enumerate(strategies):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=download)
                if info:
                    return info
        except Exception as e:
            last_error = e
            logger.warning(f"Strategy {idx + 1} failed: {e}")
            continue

    if last_error:
        raise last_error
    raise ValueError("Could not extract video information.")

def extract_info(url: str) -> Dict[str, Any]:
    url = normalize_youtube_url(url)
    ydl_opts = build_base_ydl_opts()
    ydl_opts.update({
        'skip_download': True,
        'extract_flat': False,
    })

    try:
        info = execute_with_fallback(ydl_opts, url, download=False)
        if not info:
            raise ValueError("Could not retrieve video information.")

        formats = info.get('formats', [])
        video_qualities = set()
        
        for f in formats:
            vcodec = f.get('vcodec', 'none')
            height = f.get('height')
            if height and vcodec != 'none':
                video_qualities.add(height)

        sorted_heights = sorted(list(video_qualities), reverse=True)
        quality_map = {
            2160: "4K Ultra HD (2160p)",
            1440: "2K Quad HD (1440p)",
            1080: "Full HD (1080p 60fps)",
            720: "HD (720p)",
            480: "SD (480p)",
            360: "Standard (360p)",
            240: "Low (240p)",
            144: "Mobile (144p)"
        }
        
        available_video = []
        for h in sorted_heights:
            available_video.append({
                "height": h,
                "label": quality_map.get(h, f"{h}p"),
                "format_id": f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
            })

        if not available_video:
            available_video.append({
                "height": 1080,
                "label": "Full HD (1080p 60fps)",
                "format_id": "bestvideo+bestaudio/best"
            })

        audio_presets = [
            {"bitrate": "320", "format": "mp3", "label": "MP3 - 320 kbps (Studio Master)", "badge": "320k HQ"},
            {"bitrate": "256", "format": "mp3", "label": "MP3 - 256 kbps (High Quality)", "badge": "256k HQ"},
            {"bitrate": "192", "format": "mp3", "label": "MP3 - 192 kbps (Standard)", "badge": "192k"},
            {"bitrate": "128", "format": "mp3", "label": "MP3 - 128 kbps (Fast)", "badge": "128k"},
            {"bitrate": "0", "format": "m4a", "label": "M4A - Original AAC Stream", "badge": "AAC"},
            {"bitrate": "0", "format": "wav", "label": "WAV - Lossless Uncompressed", "badge": "WAV"}
        ]

        thumbnails = info.get('thumbnails', [])
        best_thumb = info.get('thumbnail')
        if thumbnails:
            best_thumb = thumbnails[-1].get('url', best_thumb)

        return {
            "id": info.get('id'),
            "url": url,
            "title": info.get('title', 'YouTube Media'),
            "uploader": info.get('uploader') or info.get('channel', 'Unknown Creator'),
            "channel_url": info.get('uploader_url') or info.get('channel_url'),
            "duration": info.get('duration', 0),
            "duration_formatted": format_duration(info.get('duration')),
            "view_count": f"{info.get('view_count', 0):,}" if info.get('view_count') else "0",
            "thumbnail": best_thumb,
            "description": (info.get('description') or "")[:250],
            "video_formats": available_video,
            "audio_formats": audio_presets,
            "is_live": info.get('is_live', False)
        }
    except Exception as e:
        raise ValueError(clean_error_message(e))

def start_download_job(task_id: str, url: str, media_type: str, quality: str, audio_format: str = "mp3") -> None:
    cleanup_old_files()
    url = normalize_youtube_url(url)
    
    active_tasks[task_id] = {
        "task_id": task_id,
        "status": "queued",
        "progress": 0,
        "speed": "Waiting for slot...",
        "eta": "--:--",
        "downloaded_bytes": 0,
        "total_bytes": 0,
        "filename": "",
        "filepath": "",
        "error": None,
        "title": "Queued in download engine...",
        "type": media_type
    }

    with download_semaphore:
        active_tasks[task_id]["status"] = "starting"
        active_tasks[task_id]["speed"] = "Connecting..."

        stream_index = 0
        accumulated_prev_bytes = 0
        estimated_total_bytes = 0

        def progress_hook(d):
            nonlocal stream_index, accumulated_prev_bytes, estimated_total_bytes
            
            if d['status'] == 'downloading':
                stream_total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                stream_downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed')
                eta = d.get('eta')

                if media_type == "video":
                    if stream_index == 0:
                        stream_pct = (stream_downloaded / stream_total) if stream_total > 0 else 0
                        real_pct = stream_pct * 75.0
                    else:
                        stream_pct = (stream_downloaded / stream_total) if stream_total > 0 else 0
                        real_pct = 75.0 + (stream_pct * 15.0)
                else:
                    stream_pct = (stream_downloaded / stream_total) if stream_total > 0 else 0
                    real_pct = stream_pct * 85.0

                total_downloaded = accumulated_prev_bytes + stream_downloaded
                if estimated_total_bytes == 0 and stream_total > 0:
                    estimated_total_bytes = int(stream_total * 1.15) if media_type == "video" else stream_total

                speed_str = f"{format_bytes(speed)}/s" if speed else "Calculating..."
                eta_str = f"{eta}s" if eta else "--:--"

                active_tasks[task_id].update({
                    "status": "downloading",
                    "progress": min(round(real_pct, 1), 95.0),
                    "speed": speed_str,
                    "eta": eta_str,
                    "downloaded_bytes": total_downloaded,
                    "total_bytes": max(estimated_total_bytes, total_downloaded)
                })
                
            elif d['status'] == 'finished':
                accumulated_prev_bytes += d.get('total_bytes') or d.get('downloaded_bytes', 0)
                stream_index += 1
                active_tasks[task_id].update({
                    "status": "processing",
                    "progress": 92.0 if media_type == "video" else 88.0,
                    "speed": "Merging & Transcoding...",
                    "eta": "Almost ready"
                })

        try:
            task_temp_dir = TEMP_DIR / task_id
            task_temp_dir.mkdir(parents=True, exist_ok=True)
            
            outtmpl = str(task_temp_dir / "stream_file.%(ext)s")

            ydl_opts = build_base_ydl_opts()
            ydl_opts.update({
                'outtmpl': outtmpl,
                'progress_hooks': [progress_hook],
                'noplaylist': True,
                'updatetime': False,
            })

            if media_type == "audio":
                bitrate = quality if quality in ["320", "256", "192", "128"] else "320"
                target_format = audio_format.lower() if audio_format else "mp3"
                
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': target_format,
                        'preferredquality': bitrate,
                    },
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    }
                ]
            else:
                height = int(quality) if quality.isdigit() else 1080
                ydl_opts['format'] = f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={height}]+bestaudio/best[height<={height}]/best'
                ydl_opts['merge_output_format'] = 'mp4'
                ydl_opts['postprocessors'] = [
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    }
                ]

            active_tasks[task_id]["status"] = "downloading"
            info = execute_with_fallback(ydl_opts, url, download=True)
            raw_title = info.get('title', '6Down_Media')
            active_tasks[task_id]["title"] = raw_title

            generated_files = [f for f in task_temp_dir.iterdir() if f.is_file() and not f.name.endswith(('.jpg', '.png', '.webp', '.part', '.ytdl'))]
            if not generated_files:
                generated_files = [f for f in task_temp_dir.iterdir() if f.is_file() and not f.name.endswith(('.part', '.ytdl'))]

            if not generated_files:
                raise FileNotFoundError("Processing completed, but output file was not found.")

            src_file = generated_files[0]
            ext = src_file.suffix
            
            clean_title = sanitize_filename(raw_title)
            final_filename = f"{clean_title}{ext}"
            dest_file = DOWNLOADS_DIR / f"{task_id}_{final_filename}"
            
            if dest_file.exists():
                dest_file.unlink()
            shutil.move(str(src_file), str(dest_file))
            
            try:
                shutil.rmtree(str(task_temp_dir), ignore_errors=True)
            except Exception:
                pass

            active_tasks[task_id].update({
                "status": "completed",
                "progress": 100.0,
                "filename": final_filename,
                "filepath": str(dest_file),
                "file_size": format_bytes(dest_file.stat().st_size),
                "downloaded_bytes": dest_file.stat().st_size,
                "total_bytes": dest_file.stat().st_size,
                "speed": "Completed",
                "eta": "0s"
            })
            logger.info(f"Task {task_id} ready: {final_filename}")

        except Exception as e:
            err_msg = clean_error_message(e)
            logger.error(f"Task {task_id} failed: {err_msg}")
            active_tasks[task_id].update({
                "status": "error",
                "error": err_msg,
                "speed": "Failed",
                "progress": 0
            })
