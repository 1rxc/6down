import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
DOWNLOADS_DIR = BASE_DIR / "downloads"
TEMP_DIR = BASE_DIR / "temp"

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.getenv("HOST", "0.0.0.0")
default_port = "7860" if os.getenv("SPACE_ID") else "6060"
PORT = int(os.getenv("PORT", default_port))
APP_NAME = "6Down - Downloader 606 Web"
VERSION = "2.0.0"

PROXY_URL = os.getenv("PROXY_URL", "").strip() or None

COOKIES_PATH = None
env_cookie_path = os.getenv("COOKIES_PATH", "").strip()
if env_cookie_path and os.path.exists(env_cookie_path):
    COOKIES_PATH = env_cookie_path
else:
    for candidate in [BASE_DIR / "cookies.txt", BACKEND_DIR / "cookies.txt", BASE_DIR / "cookies" / "cookies.txt"]:
        if candidate.exists():
            COOKIES_PATH = str(candidate)
            break

cookies_content = os.getenv("COOKIES_CONTENT", "").strip()
if cookies_content:
    if "\\n" in cookies_content and "\n" not in cookies_content:
        cookies_content = cookies_content.replace("\\n", "\n")
    if "\\t" in cookies_content and "\t" not in cookies_content:
        cookies_content = cookies_content.replace("\\t", "\t")
    
    lines = []
    for line in cookies_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            lines.append(line)
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            parts = re.split(r'\s+', line, maxsplit=6)
        if len(parts) == 7:
            lines.append("\t".join(parts))
        else:
            lines.append(line)
    
    clean_text = "\n".join(lines) + "\n"
    env_cookie_file = TEMP_DIR / "env_cookies.txt"
    try:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        env_cookie_file.write_text(clean_text, encoding="utf-8")
        COOKIES_PATH = str(env_cookie_file)
    except Exception:
        pass

PO_TOKEN = os.getenv("PO_TOKEN", "").strip() or None
MAX_CONCURRENT_DOWNLOADS = max(1, int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2")))
FILE_RETENTION_SECONDS = int(os.getenv("FILE_RETENTION_HOURS", "1")) * 3600

FFMPEG_PATH = None
system_ffmpeg = shutil.which("ffmpeg")
if system_ffmpeg:
    FFMPEG_PATH = system_ffmpeg
else:
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(ffmpeg_exe):
            FFMPEG_PATH = ffmpeg_exe
    except Exception:
        pass
