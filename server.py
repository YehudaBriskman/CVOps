"""
server.py
---------
Minimal server that serves the dashboard and handles folder/file picker actions.

Usage:
    pip install fastapi uvicorn python-multipart
    python server.py
    -> open http://localhost:8000
"""

import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

VIDEOS_DIR = Path("./videos")
VIDEOS_DIR.mkdir(exist_ok=True)


# ── Serve the dashboard HTML ──────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index():
    html_file = Path("dashboard.html")
    if not html_file.exists():
        return HTMLResponse("<h2>dashboard.html not found next to server.py</h2>", status_code=404)
    return HTMLResponse(html_file.read_text(encoding="utf-8"))


# ── Open a native folder picker and return the chosen path ───────────────────
@app.get("/api/pick-folder")
def pick_folder():
    """
    Opens the OS folder picker dialog and returns the selected path.
    Works on Windows (via PowerShell) and Linux/WSL (via zenity).
    """
    chosen = None

    if sys.platform == "win32":
        # Native Windows folder picker via PowerShell
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
            "$d.Description = 'Select video folder';"
            "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath }"
        )
        result = subprocess.run(
            ["powershell", "-Command", ps],
            capture_output=True, text=True
        )
        chosen = result.stdout.strip() or None

    else:
        # WSL / Linux: try PowerShell.exe (opens Windows dialog from WSL)
        try:
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
                "$d.Description = 'Select video folder';"
                "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath }"
            )
            result = subprocess.run(
                ["powershell.exe", "-Command", ps],
                capture_output=True, text=True, timeout=30
            )
            chosen = result.stdout.strip() or None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # fallback: zenity (Linux GUI)
            try:
                result = subprocess.run(
                    ["zenity", "--file-selection", "--directory", "--title=Select video folder"],
                    capture_output=True, text=True, timeout=30
                )
                chosen = result.stdout.strip() or None
            except FileNotFoundError:
                pass

    if chosen:
        return JSONResponse({"path": chosen})
    return JSONResponse({"path": None, "error": "No folder selected"})


# ── Upload video files sent from the dashboard ────────────────────────────────
@app.post("/api/upload-videos")
async def upload_videos(files: list[UploadFile] = File(...)):
    saved = []
    for f in files:
        dest = VIDEOS_DIR / f.filename
        dest.write_bytes(await f.read())
        saved.append(f.filename)
    return JSONResponse({"saved": saved, "count": len(saved)})


# ── List sessions (folders in ./frames/) ──────────────────────────────────────
@app.get("/api/sessions")
def list_sessions():
    frames_dir = Path("./frames")
    if not frames_dir.exists():
        return JSONResponse({"sessions": []})
    sessions = [d.name for d in frames_dir.iterdir() if d.is_dir()]
    return JSONResponse({"sessions": sessions})


if __name__ == "__main__":
    import uvicorn
    print("\n  datak dashboard → http://localhost:8000\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8050, reload=True)
