import sys
import os
import subprocess
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from qfluentwidgets import SubtitleLabel, CaptionLabel, PrimaryPushButton, setTheme, Theme, setThemeColor

from updater import CheckUpdateWorker, DownloadUpdateWorker, apply_update
from config import APP_NAME

def resource_path(relative_path):
    """Resolve path for both dev and PyInstaller frozen mode."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)

class Bootstrapper(QWidget):
    def __init__(self):
        super().__init__()
        self._init_ui()
        self._check_update()

    def _init_ui(self):
        setTheme(Theme.DARK)
        setThemeColor('#8b5cf6')
        
        self.setWindowTitle(f"{APP_NAME} - Checking for updates")
        self.setFixedSize(400, 220)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.setStyleSheet("QWidget { background-color: #202020; color: white; border-radius: 8px; }")

        # Set Window Icon
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        # Thêm Icon to trong giao diện
        if os.path.exists(icon_path):
            from qfluentwidgets import IconWidget
            logo = IconWidget(icon_path, self)
            logo.setFixedSize(48, 48)
            layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)

        self.title_lbl = SubtitleLabel("Đang kiểm tra cập nhật...")
        layout.addWidget(self.title_lbl)

        self.status_lbl = CaptionLabel("Vui lòng chờ trong giây lát...")
        layout.addWidget(self.status_lbl)

        self.progress = QProgressBar()
        self.progress.setStyleSheet("QProgressBar { background: #333; border: none; border-radius: 4px; height: 8px; text-align: center; } QProgressBar::chunk { background: #8b5cf6; border-radius: 4px; }")
        self.progress.hide()
        layout.addWidget(self.progress)

    def _check_update(self):
        # Đường dẫn file Launcher chính (Dùng os.path.abspath để chính xác)
        launcher_exe = "main.exe" if getattr(sys, 'frozen', False) else "main.py"
        self.launcher_path = os.path.join(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__)), launcher_exe)
        
        self.is_first_install = not os.path.exists(self.launcher_path)
        
        self.checker = CheckUpdateWorker()
        self.checker.update_available.connect(self._on_update_found)
        self.checker.latest_info.connect(self._on_latest_info_received)
        self.checker.no_update.connect(lambda: self._on_no_update_found())
        self.checker.error.connect(lambda e: self._launch_launcher() if not self.is_first_install else self.status_lbl.setText(f"Lỗi kết nối: {e}"))
        self.checker.start()

    def _on_latest_info_received(self, version, url, changelog):
        # Lưu lại thông tin mới nhất để dùng khi cần ép buộc tải
        self.latest_url = url
        self.latest_version = version

    def _on_no_update_found(self):
        if self.is_first_install:
            self.title_lbl.setText("Đang cài đặt dữ liệu gốc...")
            # Đợi một chút để tín hiệu latest_info tới (nếu nó tới sau - thực tế nó tới trước)
            QTimer.singleShot(500, lambda: self._on_update_found(self.latest_version, self.latest_url, "Cài đặt lần đầu"))
        else:
            self._launch_launcher()

    def _on_update_found(self, version, url, changelog):
        if self.is_first_install:
            self.title_lbl.setText(f"Đang cài đặt v{version}")
        else:
            self.title_lbl.setText(f"Cập nhật v{version}")
            
        self.status_lbl.setText("Đang chuẩn bị tải...")
        self.progress.show()
        
        self.downloader = DownloadUpdateWorker(url)
        self.downloader.progress.connect(self.progress.setValue)
        self.downloader.status.connect(self.status_lbl.setText)
        self.downloader.finished.connect(self._on_download_finished)
        self.downloader.start()

    def _on_download_finished(self, success, path_or_err):
        if success:
            self.status_lbl.setText("Đang cài đặt cập nhật...")
            ok, msg = apply_update(path_or_err)
            if ok:
                QTimer.singleShot(1000, self._launch_launcher)
            else:
                self.status_lbl.setText(f"Lỗi: {msg}")
        else:
            self.status_lbl.setText(f"Lỗi: {path_or_err}")
            QTimer.singleShot(2000, self._launch_launcher)

    def _launch_launcher(self):
        # Đường dẫn file Launcher (giả sử tên là main.exe khi bundle hoặc main.py khi dev)
        launcher_exe = "main.exe" if getattr(sys, 'frozen', False) else "main.py"
        
        if getattr(sys, 'frozen', False):
            # Nếu là file EXE đã đóng gói
            path = os.path.join(os.path.dirname(sys.executable), launcher_exe)
            if os.path.exists(path):
                subprocess.Popen([path])
        else:
            # Nếu đang chạy code dev
            subprocess.Popen([sys.executable, launcher_exe])
            
        sys.exit(0)

if __name__ == "__main__":
    if sys.platform == 'win32':
        import ctypes
        app_id = u'laiduc.pldlauncher.updater.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    app = QApplication(sys.argv)
    window = Bootstrapper()
    window.show()
    sys.exit(app.exec())
