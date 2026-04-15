import sys
import os

# --- Robust Fix for 'SixMetaPathImporter' error ---
if getattr(sys, 'frozen', False):
    import types
    # Fake the six.moves module if it's causing issues with botocore/boto3
    if 'six.moves' not in sys.modules:
        m = types.ModuleType('six.moves')
        sys.modules['six.moves'] = m
    # Pre-import botocore before any other potential conflicts
    try:
        import botocore  # noqa: F401
    except ImportError:
        pass

from PySide6.QtCore import QLockFile, QDir, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QLabel, QProgressBar

from qfluentwidgets import setTheme, Theme, setThemeColor, ProgressBar, SubtitleLabel, PrimaryPushButton, InfoBar, InfoBarPosition
from updater import CheckUpdateWorker, DownloadUpdateWorker, apply_update, restart_app

from ui_window import PLDLauncher
from ui_auth import AuthPage
from auth_manager import AuthManager

def resource_path(relative_path):
    """Resolve path for both dev and PyInstaller frozen mode."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)

class UpdateRedirectDialog(QDialog):
    """Thông báo người dùng cần chạy Update.exe để cập nhật."""
    def __init__(self, version, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PLD Launcher - Yêu cầu cập nhật")
        self.setFixedSize(400, 260)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.setStyleSheet("QDialog { background-color: #2d2d2d; color: white; border-radius: 12px; }")
        
        # Set icon for redirect dialog
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 20, 30, 30)
        lay.setSpacing(15)

        # Big Icon
        if os.path.exists(icon_path):
            from qfluentwidgets import IconWidget
            logo = IconWidget(icon_path, self)
            logo.setFixedSize(40, 40)
            lay.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)

        title = SubtitleLabel(f"Phiên bản mới: v{version}")
        title.setTextColor("white")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        desc = QLabel("Bạn đang khởi chạy trực tiếp Launcher.\nVui lòng chạy Update.exe để cập nhật bản mới nhất.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #bbbbbb;")
        lay.addWidget(desc)

        self.btn = PrimaryPushButton("MỞ UPDATE.EXE NGAY", self)
        self.btn.clicked.connect(self.launch_update_and_exit)
        lay.addWidget(self.btn)

    def launch_update_and_exit(self):
        update_exe = "bootstrapper.exe" if getattr(sys, 'frozen', False) else "bootstrapper.py"
        
        if getattr(sys, 'frozen', False):
            path = os.path.join(os.path.dirname(sys.executable), update_exe)
            if os.path.exists(path):
                subprocess.Popen([path])
        else:
            subprocess.Popen([sys.executable, update_exe])
            
        sys.exit(0)


def main():
    # --- Windows Taskbar Icon Fix ---
    if sys.platform == 'win32':
        import ctypes
        app_id = u'laiduc.pldlauncher.main.v1' # Arbitrary unique string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    # --- Cleanup Old Executable ---
    if getattr(sys, 'frozen', False):
        old_exe = sys.executable + ".old"
        if os.path.exists(old_exe):
            try:
                os.remove(old_exe)
            except Exception:
                pass

    app = QApplication(sys.argv)

    # --- Single Instance Lock ---
    global _LOCK_FILE
    lock_path = os.path.join(QDir.tempPath(), "pld_launcher.lock")
    _LOCK_FILE = QLockFile(lock_path)

    if not _LOCK_FILE.tryLock(100):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("PLD Launcher")
        msg.setText("Ứng dụng đã có một bản đang chạy!")
        msg.setInformativeText("Vui lòng kiểm tra lại khay hệ thống hoặc thanh tác vụ.")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        sys.exit(0)

    # --- Fluent Design Theme ---
    setTheme(Theme.DARK)
    setThemeColor('#8b5cf6')  # Violet primary accent

    font = QFont("Segoe UI Variable Display", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)

    auth_mgr = AuthManager()
    
    def launch_actual_app():
        if not auth_mgr.is_logged_in():
            auth_page = AuthPage()
            auth_page.auth_success.connect(lambda: [auth_page.close(), launch_main_window()])
            auth_page.show()
        else:
            launch_main_window()

    def launch_main_window():
        global main_window
        main_window = PLDLauncher()
        main_window.show()

    # --- Update Check ---
    update_checker = CheckUpdateWorker()

    def on_update_found(ver, url, log):
        dlg = UpdateRedirectDialog(ver)
        dlg.exec()
        sys.exit(0) # Exit launcher to force update

    update_checker.update_available.connect(on_update_found)
    update_checker.no_update.connect(launch_actual_app)
    update_checker.error.connect(launch_actual_app)
    
    update_checker.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()