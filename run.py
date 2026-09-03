import os
import sys
import time
import socket
import webbrowser
import threading
import subprocess
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

current_dir = Path(__file__).resolve().parent
backend_path = current_dir / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

try:
    from backend.config import HOST, PORT, APP_NAME
except ImportError:
    from config import HOST, PORT, APP_NAME

def free_port(port: int):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                if sys.platform == "win32":
                    cmd = f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"
                    subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
                    time.sleep(0.6)
    except Exception:
        pass

def open_browser():
    time.sleep(1.2)
    webbrowser.open(f"http://localhost:{PORT}")

if __name__ == "__main__":
    import uvicorn

    free_port(PORT)

    print(f"\n{APP_NAME}")
    print(f"Running on http://localhost:{PORT}\n")

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app:app", host="127.0.0.1", port=PORT, reload=False, app_dir=str(backend_path))
