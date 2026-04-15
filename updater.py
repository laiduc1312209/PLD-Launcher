"""
PLD Launcher — Auto-Update System (GitHub Releases)

Flow:
  1. CheckUpdateWorker  → Fetch version.json from GitHub raw
  2. DownloadUpdateWorker → Download .zip from GitHub Release
  3. apply_update()     → Extract zip, overwrite local files, restart app
"""
import os
import sys
import json
import shutil
import zipfile
import tempfile
import subprocess
from urllib.request import urlopen, Request
from urllib.error import URLError

from PySide6.QtCore import QThread, Signal

from config import APP_VERSION, GITHUB_REPO


# ═══════════════════════════════════════════════════
#  Version Comparison
# ═══════════════════════════════════════════════════
def _parse_version(v: str):
    """Convert '1.2.3' to tuple (1, 2, 3) for comparison."""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0, 0, 0)


def is_newer(remote: str, local: str = APP_VERSION) -> bool:
    return _parse_version(remote) > _parse_version(local)


# ═══════════════════════════════════════════════════
#  Check Update Worker
# ═══════════════════════════════════════════════════
class CheckUpdateWorker(QThread):
    """Fetch version.json from GitHub and compare with local version."""

    # Signals: (remote_version, download_url, changelog)
    update_available = Signal(str, str, str)
    no_update = Signal()
    error = Signal(str)
    
    # New signal to always get info (for fresh install)
    latest_info = Signal(str, str, str)

    def run(self):
        try:
            url = (
                f"https://raw.githubusercontent.com/"
                f"{GITHUB_REPO}/main/version.json"
            )
            req = Request(url, headers={"User-Agent": "PLD-Launcher"})
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            remote_ver = data.get("version", "0.0.0")
            download_url = data.get("download_url", "")
            changelog = data.get("changelog", "")

            # Always emit latest info
            self.latest_info.emit(remote_ver, download_url, changelog)

            if is_newer(remote_ver):
                self.update_available.emit(remote_ver, download_url, changelog)
            else:
                self.no_update.emit()

        except URLError as e:
            self.error.emit(f"Không thể kết nối: {e.reason}")
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════
#  Download Update Worker
# ═══════════════════════════════════════════════════
class DownloadUpdateWorker(QThread):
    """Download the update zip from GitHub Release."""

    progress = Signal(int)          # 0-100
    status = Signal(str)
    finished = Signal(bool, str)    # (success, zip_path_or_error)

    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url

    def run(self):
        try:
            self.status.emit("Đang tải bản cập nhật…")
            self.progress.emit(5)

            req = Request(self.download_url, headers={"User-Agent": "PLD-Launcher"})
            with urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                # Save to temp file
                tmp = os.path.join(
                    tempfile.gettempdir(), "pld_update.zip"
                )

                downloaded = 0
                chunk_size = 65536
                with open(tmp, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = int(downloaded / total * 90) + 5
                            self.progress.emit(min(pct, 95))

            self.progress.emit(95)
            self.status.emit("Tải xong!")
            self.finished.emit(True, tmp)

        except Exception as e:
            self.finished.emit(False, f"Lỗi tải: {e}")


# ═══════════════════════════════════════════════════
#  Apply Update (extract + restart)
# ═══════════════════════════════════════════════════
# Files/dirs to NEVER overwrite during update
_SKIP = {
    "settings.json", "auth_session.json",
    ".git", "__pycache__", "assets",
    "venv", ".venv",
}

# Only overwrite these file extensions
_ALLOWED_EXT = {".py", ".txt", ".md", ".json", ".spec", ".ico", ".bat"}


def apply_update(zip_path: str) -> tuple[bool, str]:
    """
    Extract update zip and overwrite local project files or current executable.
    Returns (success, message).
    """
    try:
        # ---- 1A. FROZEN MODE (.EXE) ----
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            
            with zipfile.ZipFile(zip_path, "r") as zf:
                exe_found = False
                for member in zf.infolist():
                    if member.filename.lower().endswith(".exe"):
                        exe_found = True
                        target_path = os.path.join(exe_dir, member.filename)
                        
                        # If the target is the currently running exe, use .old trick
                        if os.path.normpath(target_path) == os.path.normpath(sys.executable):
                            old_exe = target_path + ".old"
                            if os.path.exists(old_exe):
                                try: os.remove(old_exe)
                                except: pass
                            os.rename(target_path, old_exe)
                        
                        # Extract the new exe
                        with zf.open(member) as src, open(target_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                
                if not exe_found:
                    return False, "Không tìm thấy file thực thi (.exe) trong bản cập nhật."

        # ---- 1B. SOURCE DEV MODE (.PY) ----
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                root_prefix = ""
                if names and "/" in names[0]:
                    first_part = names[0].split("/")[0] + "/"
                    if all(n.startswith(first_part) for n in names):
                        root_prefix = first_part

                for member in zf.infolist():
                    if member.is_dir():
                        continue

                    rel_path = member.filename
                    if root_prefix and rel_path.startswith(root_prefix):
                        rel_path = rel_path[len(root_prefix):]

                    if not rel_path:
                        continue

                    top_level = rel_path.split("/")[0].split("\\")[0]
                    if top_level in _SKIP or rel_path == "version.json":
                        continue

                    _, ext = os.path.splitext(rel_path)
                    if ext.lower() not in _ALLOWED_EXT:
                        continue

                    dest = os.path.join(app_dir, rel_path)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)

                    with zf.open(member) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)

        # Clean up zip
        try:
            os.remove(zip_path)
        except Exception:
            pass

        return True, "Cập nhật thành công!"

    except Exception as e:
        return False, f"Lỗi cập nhật: {e}"


def restart_app():
    """Restart the application after update."""
    python = sys.executable
    # Use Popen to start a fresh detached process on Windows
    subprocess.Popen([python] + sys.argv, creationflags=subprocess.CREATE_NEW_CONSOLE if not getattr(sys, 'frozen', False) else 0)
    os._exit(0)
