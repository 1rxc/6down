import os
import re
import sys
import uuid
import asyncio
import threading
import urllib.parse
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import HOST, PORT, APP_NAME, VERSION, FFMPEG_PATH, FRONTEND_DIR, DOWNLOADS_DIR
from downloader import extract_info, start_download_job, active_tasks

app = FastAPI(title=APP_NAME, version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoInfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    media_type: str = "video"
    quality: str = "1080"
    format: str = "mp4"

@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "app": APP_NAME,
        "version": VERSION,
        "ffmpeg_available": FFMPEG_PATH is not None,
        "ffmpeg_path": FFMPEG_PATH
    }

@app.post("/api/info")
async def get_video_info(req: VideoInfoRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="Please provide a valid YouTube URL.")
    
    url = req.url.strip()
    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, extract_info, url)
        return {"success": True, "data": info}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "detail": str(e)})

@app.post("/api/download")
async def trigger_download(req: DownloadRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty.")
    
    task_id = str(uuid.uuid4())
    url = req.url.strip()
    media_type = req.media_type.lower()
    quality = str(req.quality).strip()
    target_format = req.format.lower().strip()

    thread = threading.Thread(
        target=start_download_job,
        args=(task_id, url, media_type, quality, target_format),
        daemon=True
    )
    thread.start()

    return {
        "success": True,
        "task_id": task_id,
        "message": "Download task queued successfully"
    }

@app.get("/api/progress/{task_id}")
async def get_task_progress(task_id: str):
    task = active_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or expired.")
    return task

@app.get("/api/progress/stream/{task_id}")
async def stream_progress(task_id: str):
    async def event_generator():
        import json
        while True:
            task = active_tasks.get(task_id)
            if not task:
                yield f"data: {json.dumps({'status': 'error', 'error': 'Task not found'})}\n\n"
                break
            
            yield f"data: {json.dumps(task)}\n\n"
            
            if task.get("status") in ["completed", "error"]:
                break
            await asyncio.sleep(0.35)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@app.get("/api/file/{task_id}")
@app.get("/api/file/{task_id}/{filename}")
async def download_file(task_id: str, filename: Optional[str] = None):
    task = active_tasks.get(task_id)
    filepath = None
    if task and task.get("filepath"):
        filepath = Path(task.get("filepath"))
    
    if not filepath or not filepath.exists():
        candidates = list(DOWNLOADS_DIR.glob(f"{task_id}_*"))
        if candidates:
            filepath = candidates[0]
            
    if not filepath or not filepath.exists():
        raise HTTPException(status_code=404, detail="Processed file was not found on server.")
    
    final_filename = filename or (task.get("filename") if task else None) or filepath.name.replace(f"{task_id}_", "")

    ext = filepath.suffix.lower()
    safe_ascii = re.sub(r'[^\x20-\x7E]', '_', final_filename).replace('"', '').strip()
    if not safe_ascii or safe_ascii.endswith('.'):
        safe_ascii = f"download_{task_id[:8]}{ext}"
    elif not safe_ascii.endswith(ext):
        safe_ascii += ext
        
    encoded_filename = urllib.parse.quote(final_filename, encoding='utf-8')
    content_disposition = f'attachment; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded_filename}'
    media_type = "video/mp4" if ext == ".mp4" else ("audio/mpeg" if ext == ".mp3" else "application/octet-stream")

    return FileResponse(
        path=str(filepath),
        media_type=media_type,
        headers={
            "Content-Disposition": content_disposition,
            "Access-Control-Expose-Headers": "Content-Disposition",
            "Content-Length": str(filepath.stat().st_size)
        }
    )

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    import uvicorn
    print(f"[+] Starting {APP_NAME} on http://localhost:{PORT}")
    uvicorn.run("app:app", host=HOST, port=PORT, reload=True)
