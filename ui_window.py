"""
PLD Launcher — Main Window (PySide6 + QFluentWidgets Fluent Design)
Fully rewritten from PyQt6 to native Windows 11 Fluent UI.
"""
import os
import sys
import uuid
import shutil

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QStackedWidget, QSizePolicy, QFileDialog, QApplication,
    QInputDialog
)
from PySide6.QtCore import Qt, QTimer, QSize, Signal
from PySide6.QtGui import QPixmap, QFont, QIcon

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon as FIF,
    TitleLabel, SubtitleLabel, StrongBodyLabel, BodyLabel, CaptionLabel,
    PrimaryPushButton, PushButton, TransparentPushButton,
    TransparentToolButton,
    LineEdit, SearchLineEdit,
    ProgressBar,
    CardWidget, SimpleCardWidget,
    InfoBar, InfoBarPosition,
    MessageBox, MessageBoxBase,
    ScrollArea, FlowLayout,
    setTheme, Theme, setThemeColor, IconWidget
)

from config import APP_NAME, APP_VERSION
from sync_worker import (
    SyncDownWorker, SyncUpWorker, SyncSettingsWorker,
    DownloadSettingsWorker
)
from game_launcher import GameLaunchWorker
from updater import CheckUpdateWorker, DownloadUpdateWorker, apply_update, restart_app
from settings import get_game_exe, set_game_exe, get_save_dir, set_save_dir
from auth_manager import AuthManager
from cloud_manager import CloudManager


def resource_path(relative_path):
    """Resolve path for both dev and PyInstaller frozen mode."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


# ═══════════════════════════════════════════════════
#  Game Card Widget
# ═══════════════════════════════════════════════════
class GameCard(CardWidget):
    """A clickable game card for the library grid."""

    def __init__(self, gid, title, parent=None):
        super().__init__(parent)
        self.gid = gid
        self.setFixedSize(200, 270)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Banner Area ──
        banner = QFrame()
        banner.setFixedSize(200, 180)

        banner.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #4b3590, stop:1 #1a1540);"
        )
        il = QVBoxLayout(banner)
        il.setAlignment(Qt.AlignmentFlag.AlignCenter)
        iw = IconWidget(FIF.GAME, banner)
        iw.setFixedSize(48, 48)
        il.addWidget(iw, alignment=Qt.AlignmentFlag.AlignCenter)

        # Badge
        badge = CaptionLabel("INSTALLED", banner)
        badge.setStyleSheet(
            "background:#30b077; color:white; font-weight:bold; "
            "font-size:10px; padding:3px 8px; border-radius:4px;"
        )
        badge.move(8, 150)

        lay.addWidget(banner)

        # ── Info Area ──
        info = QWidget()
        il = QVBoxLayout(info)
        il.setContentsMargins(14, 10, 14, 14)
        il.setSpacing(4)

        name = StrongBodyLabel(title)
        name.setWordWrap(True)
        il.addWidget(name)

        sub = CaptionLabel("Ready to play")
        il.addWidget(sub)
        il.addStretch()

        lay.addWidget(info)


class AddGameCard(CardWidget):
    """'+' card to add a new game to the library."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 270)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(16)

        iw = IconWidget(FIF.ADD, self)
        iw.setFixedSize(40, 40)
        lay.addWidget(iw, alignment=Qt.AlignmentFlag.AlignCenter)

        lbl = BodyLabel("Add New Game")
        lay.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)


# ═══════════════════════════════════════════════════
#  Settings Dialog (Fluent MessageBox)
# ═══════════════════════════════════════════════════
class SettingsDialog(MessageBoxBase):
    """Game configuration dialog built on Fluent MessageBoxBase."""

    deleteRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.titleLabel = SubtitleLabel("⚙️  Game Configuration")
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(12)

        # Name
        self.viewLayout.addWidget(CaptionLabel("TÊN GAME"))
        self.nameInput = LineEdit()
        self.nameInput.setPlaceholderText("Nhập tên trò chơi...")
        self.nameInput.setClearButtonEnabled(True)
        self.viewLayout.addWidget(self.nameInput)
        self.viewLayout.addSpacing(8)

        # Exe path
        self.viewLayout.addWidget(CaptionLabel("ĐƯỜNG DẪN GAME (.EXE)"))
        exe_row = QHBoxLayout()
        self.exeInput = LineEdit()
        self.exeInput.setPlaceholderText("Đường dẫn tới file thực thi")
        self.exeBrowse = PushButton(FIF.FOLDER, "Browse")
        self.exeBrowse.clicked.connect(self._browse_exe)
        exe_row.addWidget(self.exeInput, stretch=1)
        exe_row.addWidget(self.exeBrowse)
        self.viewLayout.addLayout(exe_row)
        self.viewLayout.addSpacing(8)

        # Save dir
        self.viewLayout.addWidget(CaptionLabel("THƯ MỤC SAVE GAME"))
        save_row = QHBoxLayout()
        self.saveInput = LineEdit()
        self.saveInput.setPlaceholderText("Nơi chứa file save của game")
        self.saveBrowse = PushButton(FIF.FOLDER, "Browse")
        self.saveBrowse.clicked.connect(self._browse_save)
        save_row.addWidget(self.saveInput, stretch=1)
        save_row.addWidget(self.saveBrowse)
        self.viewLayout.addLayout(save_row)
        self.viewLayout.addSpacing(8)



        # Zip name
        self.viewLayout.addWidget(CaptionLabel("TÊN FILE ZIP CLOUD"))
        self.zipInput = LineEdit()
        self.zipInput.setPlaceholderText("vd: mygame_save.zip")
        self.viewLayout.addWidget(self.zipInput)
        self.viewLayout.addSpacing(16)

        # Delete button
        self.deleteBtn = PushButton(FIF.DELETE, "Xoá Game")
        self.deleteBtn.clicked.connect(lambda: self.deleteRequested.emit())
        self.viewLayout.addWidget(self.deleteBtn)

        # Bottom buttons
        self.yesButton.setText("💾 Lưu cài đặt")
        self.cancelButton.setText("Hủy")

        self.widget.setMinimumWidth(520)

    def _browse_exe(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Chọn file .exe", "", "Game (*.exe)"
        )
        if p:
            self.exeInput.setText(p)

    def _browse_save(self):
        p = QFileDialog.getExistingDirectory(self, "Chọn thư mục Save")
        if p:
            self.saveInput.setText(p)



    def populate(self, data):
        """Fill inputs from game data dict."""
        self.nameInput.setText(data.get("name", ""))
        self.exeInput.setText(data.get("exe", ""))
        self.saveInput.setText(data.get("save_dir", ""))
        self.zipInput.setText(data.get("zip_name", ""))

    def get_data(self):
        """Return current input values as dict."""
        return {
            "name": self.nameInput.text().strip(),
            "exe": self.exeInput.text().strip(),
            "zip_name": self.zipInput.text().strip()
        }


# ═══════════════════════════════════════════════════
#  Main Launcher Window
# ═══════════════════════════════════════════════════
class PLDLauncher(FluentWindow):
    def __init__(self):
        super().__init__()

        self._create_interfaces()
        self._setup_navigation()
        self._setup_window()

        self._refresh_home_grid()
        QTimer.singleShot(1000, self._sync_library_from_mongodb)

        # Auto-update check (2s after startup)
        QTimer.singleShot(2000, self._check_for_updates)

    # ══════════════════════════════════════════
    #  Window Setup
    # ══════════════════════════════════════════
    def _setup_window(self):
        self.setWindowTitle("PLD Launcher")
        self.resize(1100, 700)

        # Window icon
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Center on screen
        desktop = QApplication.primaryScreen().availableGeometry()
        self.move(
            (desktop.width() - self.width()) // 2,
            (desktop.height() - self.height()) // 2
        )

        # Windows 11 Mica backdrop effect
        try:
            self.setMicaEffectEnabled(True)
        except Exception:
            pass

    # ══════════════════════════════════════════
    #  Interfaces
    # ══════════════════════════════════════════
    def _create_interfaces(self):
        # Home interface contains an internal stack (grid ↔ detail)
        self.homeInterface = QWidget()
        self.homeInterface.setObjectName("homeInterface")
        home_lay = QVBoxLayout(self.homeInterface)
        home_lay.setContentsMargins(0, 0, 0, 0)

        self.homeStack = QStackedWidget()
        self.gridPage = self._build_grid_page()
        self.detailPage = self._build_detail_page()
        self.homeStack.addWidget(self.gridPage)
        self.homeStack.addWidget(self.detailPage)
        home_lay.addWidget(self.homeStack)

        # Profile interface
        self.profileInterface = self._build_profile_page()
        self.profileInterface.setObjectName("profileInterface")

    def _setup_navigation(self):
        self.addSubInterface(self.homeInterface, FIF.HOME, 'Library')

        self.addSubInterface(
            self.profileInterface, FIF.PEOPLE, 'Profile',
            position=NavigationItemPosition.BOTTOM
        )

        self.navigationInterface.addItem(
            routeKey='settings',
            icon=FIF.SETTING,
            text='Settings',
            onClick=self._toggle_settings,
            selectable=False,
            position=NavigationItemPosition.BOTTOM
        )

        self.navigationInterface.addItem(
            routeKey='logout',
            icon=FIF.POWER_BUTTON,
            text='Logout',
            onClick=self._handle_logout,
            selectable=False,
            position=NavigationItemPosition.BOTTOM
        )

    # ══════════════════════════════════════════
    #  Grid Page (Library)
    # ══════════════════════════════════════════
    def _build_grid_page(self):
        page = ScrollArea()
        page.setWidgetResizable(True)
        page.setStyleSheet("QScrollArea{border:none;background:transparent;}")

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        page.setWidget(container)

        self.gridMainLayout = QVBoxLayout(container)
        self.gridMainLayout.setContentsMargins(36, 20, 36, 36)
        self.gridMainLayout.setSpacing(0)

        # Header
        header = QHBoxLayout()
        txt_col = QVBoxLayout()
        txt_col.setSpacing(4)
        title = TitleLabel("My Library")
        sub = CaptionLabel("Manage and play your favorite titles")
        txt_col.addWidget(title)
        txt_col.addWidget(sub)
        header.addLayout(txt_col)
        header.addStretch()

        self.searchBox = SearchLineEdit()
        self.searchBox.setPlaceholderText("Search games...")
        self.searchBox.setFixedWidth(250)
        header.addWidget(self.searchBox, alignment=Qt.AlignmentFlag.AlignBottom)

        self.gridMainLayout.addLayout(header)
        self.gridMainLayout.addSpacing(24)

        # Grid
        self.gridWidget = QWidget()
        self.gridLayout = FlowLayout(self.gridWidget, needAni=True)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setHorizontalSpacing(20)
        self.gridLayout.setVerticalSpacing(20)

        self.gridMainLayout.addWidget(self.gridWidget)
        self.gridMainLayout.addStretch()

        return page

    # ══════════════════════════════════════════
    #  Detail Page (Game Info + Play)
    # ══════════════════════════════════════════
    def _build_detail_page(self):
        page = ScrollArea()
        page.setWidgetResizable(True)
        page.setStyleSheet("QScrollArea{border:none;background:transparent;}")

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        page.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(36, 16, 36, 30)
        layout.setSpacing(20)

        # ── Back Button ──
        back_btn = TransparentPushButton(FIF.RETURN, "Back to Library")
        back_btn.clicked.connect(self._show_home)
        layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # ── Banner Card ──
        self.detail_banner_card = CardWidget()
        banner_lay = QVBoxLayout(self.detail_banner_card)
        banner_lay.setContentsMargins(0, 0, 0, 24)
        banner_lay.setSpacing(12)

        self.detail_banner_img = QLabel()
        self.detail_banner_img.setFixedHeight(250)
        self.detail_banner_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_banner_img.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #3b3090, stop:1 #1a1540);"
        )
        banner_lay.addWidget(self.detail_banner_img)

        info_inner = QVBoxLayout()
        info_inner.setContentsMargins(24, 0, 24, 0)
        info_inner.setSpacing(6)

        self.detail_title = TitleLabel("Game Title")
        info_inner.addWidget(self.detail_title)

        self.detail_subtitle = CaptionLabel("☁  Cloud Sync  ·  Auto Save Management")
        info_inner.addWidget(self.detail_subtitle)

        banner_lay.addLayout(info_inner)
        layout.addWidget(self.detail_banner_card)

        # ── Action Buttons ──
        actions = QHBoxLayout()
        actions.setSpacing(12)

        self.btn_upload = PushButton(FIF.SYNC, "Upload Save")
        self.btn_upload.clicked.connect(self._manual_sync_up)
        actions.addWidget(self.btn_upload)

        self.btn_folder = PushButton(FIF.FOLDER, "Open Folder")
        self.btn_folder.clicked.connect(self._open_save_folder)
        actions.addWidget(self.btn_folder)

        self.btn_settings_detail = PushButton(FIF.SETTING, "Game Settings")
        self.btn_settings_detail.clicked.connect(self._open_settings)
        actions.addWidget(self.btn_settings_detail)

        actions.addStretch()
        layout.addLayout(actions)

        # ── System Info Card ──
        info_card = SimpleCardWidget()
        info_card_lay = QHBoxLayout(info_card)
        info_card_lay.setContentsMargins(24, 20, 24, 20)
        info_card_lay.setSpacing(40)

        def make_stat(label, value, color=None):
            col = QVBoxLayout()
            col.addWidget(CaptionLabel(label))
            val = StrongBodyLabel(value)
            if color:
                val.setStyleSheet(f"color:{color};")
            col.addWidget(val)
            return col

        info_card_lay.addLayout(make_stat("SAVE PATH", "Configured"))
        info_card_lay.addLayout(make_stat("CLOUD STATUS", "Connected", "#30b077"))
        info_card_lay.addLayout(make_stat("LAUNCHER", f"v{APP_VERSION}"))
        info_card_lay.addStretch()
        layout.addWidget(info_card)

        # ── Progress Bar ──
        self.progress = ProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # ── Status Label ──
        self.status_label = BodyLabel("⭐ Sẵn sàng")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # ── Play Button ──
        play_row = QHBoxLayout()
        play_row.addStretch()

        self.launch_btn = PrimaryPushButton(FIF.PLAY, "  PLAY NOW")
        self.launch_btn.setFixedSize(220, 50)
        f = self.launch_btn.font()
        f.setPointSize(14)
        f.setBold(True)
        self.launch_btn.setFont(f)
        self.launch_btn.clicked.connect(self._on_play)
        play_row.addWidget(self.launch_btn)

        layout.addLayout(play_row)
        return page

    # ══════════════════════════════════════════
    #  Profile Page
    # ══════════════════════════════════════════
    def _build_profile_page(self):
        page = ScrollArea()
        page.setWidgetResizable(True)
        page.setStyleSheet("QScrollArea{border:none;background:transparent;}")

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        page.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(60, 40, 60, 40)
        layout.setSpacing(24)

        layout.addWidget(TitleLabel("TÀI KHOẢN"))

        # Profile Card
        prof_card = SimpleCardWidget()
        pc_lay = QVBoxLayout(prof_card)
        pc_lay.setContentsMargins(32, 32, 32, 32)
        pc_lay.setSpacing(16)

        pc_lay.addWidget(CaptionLabel("EMAIL"))
        self.prof_email = StrongBodyLabel("---")
        pc_lay.addWidget(self.prof_email)

        pc_lay.addSpacing(8)

        pc_lay.addWidget(CaptionLabel("USER ID"))
        self.prof_id = StrongBodyLabel("---")
        pc_lay.addWidget(self.prof_id)

        pc_lay.addSpacing(16)

        # Cloud Status Card
        cloud_card = SimpleCardWidget()
        cc_lay = QHBoxLayout(cloud_card)
        cc_lay.setContentsMargins(20, 16, 20, 16)
        cc_lay.setSpacing(16)

        cloud_icon = IconWidget(FIF.CLOUD)
        cloud_icon.setFixedSize(40, 40)
        cc_lay.addWidget(cloud_icon)

        cloud_text = QVBoxLayout()
        cloud_text.addWidget(StrongBodyLabel("CẤU HÌNH CLOUD STORAGE"))
        self.lbl_drive_status = CaptionLabel("Sẵn sàng (Backblaze B2 Storage)")
        self.lbl_drive_status.setStyleSheet("color:#30b077;")
        cloud_text.addWidget(self.lbl_drive_status)
        cc_lay.addLayout(cloud_text, stretch=1)

        pc_lay.addWidget(cloud_card)
        layout.addWidget(prof_card)

        # Populate with session data
        session = AuthManager().session
        if session:
            self.prof_email.setText(session.get("email", "N/A"))
            self.prof_id.setText(session.get("id", "N/A"))

        layout.addStretch()
        return page

    # ══════════════════════════════════════════
    #  Navigation Logic
    # ══════════════════════════════════════════
    def _show_home(self):
        self.homeStack.setCurrentIndex(0)
        self._refresh_home_grid()
        self.switchTo(self.homeInterface)

    def _open_game_detail(self, gid):
        from settings import set_active_game_id
        set_active_game_id(gid)
        self.homeStack.setCurrentIndex(1)
        self._update_detail_page()

    def _update_detail_page(self):
        if not hasattr(self, 'detail_title'):
            return

        from settings import get_active_game
        g = get_active_game()
        if not g:
            return

        name = g.get("name", "Unknown")
        self.detail_title.setText(name.upper())

        self.detail_banner_img.setPixmap(QPixmap())
        self.detail_banner_img.setScaledContents(False)
        self.detail_banner_img.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #3b3090, stop:1 #1a1540);"
        )

    # ══════════════════════════════════════════
    #  Grid / Cards
    # ══════════════════════════════════════════
    def _refresh_home_grid(self):
        # Clear all cards
        while self.gridLayout.count():
            item = self.gridLayout.takeAt(0)
            if isinstance(item, QWidget):
                item.deleteLater()
            elif hasattr(item, 'widget') and item.widget():
                item.widget().deleteLater()

        from settings import get_games
        games = get_games()

        for gid, gdata in games.items():
            card = GameCard(
                gid,
                gdata.get("name", "Unknown")
            )
            card.clicked.connect(
                lambda g=gid: self._open_game_detail(g)
            )
            self.gridLayout.addWidget(card)

        add_card = AddGameCard()
        add_card.clicked.connect(self._add_new_game)
        self.gridLayout.addWidget(add_card)

    def _add_new_game(self):
        name, ok = QInputDialog.getText(self, "Thêm Game Mới", "Tên game:")
        if ok and name.strip():
            gid = "game_" + uuid.uuid4().hex[:6]
            from settings import add_update_game, set_active_game_id
            add_update_game(
                gid, name.strip(), "", "",
                f"{name.strip().replace(' ', '_').lower()}_save.zip"
            )
            set_active_game_id(gid)
            self._open_settings()
            self._refresh_home_grid()

    # ══════════════════════════════════════════
    #  Settings Dialog
    # ══════════════════════════════════════════
    def _toggle_settings(self):
        if self.homeStack.currentIndex() == 1:
            self._open_settings()
        else:
            InfoBar.warning(
                title="Thông báo",
                content="Vui lòng chọn 1 Game trước khi vào phần Cài đặt.",
                parent=self,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000
            )

    def _open_settings(self):
        from settings import get_active_game

        dialog = SettingsDialog(self)
        dialog.populate(get_active_game())
        dialog.deleteRequested.connect(
            lambda: self._delete_game_from_dialog(dialog)
        )

        if dialog.exec():
            self._save_settings(dialog.get_data())

    def _save_settings(self, data):
        from settings import get_active_game_id, add_update_game, set_active_game_id

        gid = get_active_game_id()
        if not gid:
            gid = "game_" + uuid.uuid4().hex[:6]
            set_active_game_id(gid)

        add_update_game(
            gid,
            data["name"] or "Unnamed Game",
            data.get("exe", ""),
            data.get("save_dir", ""),
            data.get("zip_name", "save.zip")
        )

        self._update_detail_page()
        self._refresh_home_grid()

        InfoBar.success(
            title="Đã lưu",
            content="Cài đặt game đã được lưu thành công.",
            parent=self,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000
        )

        self._sync_library_to_mongodb()

    def _delete_game_from_dialog(self, dialog):
        from settings import get_active_game_id, remove_game

        w = MessageBox("Xóa Game", "Bạn có chắc muốn xóa game này?", self)
        if w.exec():
            gid = get_active_game_id()
            remove_game(gid)
            dialog.reject()
            self._sync_library_to_mongodb()
            self._show_home()

    # ══════════════════════════════════════════
    #  Cloud Sync
    # ══════════════════════════════════════════
    def _sync_library_to_mongodb(self):
        """Push current games list to MongoDB Cloud."""
        from settings import get_games
        games = get_games()
        success, msg = AuthManager().update_cloud_library(games)
        if success:
            InfoBar.success(
                "Cloud", "Library đã đồng bộ lên Cloud.",
                parent=self, position=InfoBarPosition.TOP_RIGHT, duration=2000
            )
        else:
            InfoBar.error(
                "Cloud Sync", f"Lỗi: {msg}",
                parent=self, position=InfoBarPosition.TOP_RIGHT, duration=3000
            )

    def _sync_library_from_mongodb(self):
        """Fetch library from MongoDB and update local settings."""
        self._set_status("Đang tải thư viện từ Cloud...")
        lib_data = AuthManager().get_cloud_library()

        if lib_data is not None:
            from settings import add_update_game
            for gdata in lib_data:
                gid = gdata.pop("gid", None)
                if gid:
                    add_update_game(
                        gid, gdata.get("name"), gdata.get("exe"),
                        gdata.get("save_dir"), gdata.get("zip_name")
                    )

            self._refresh_home_grid()
            self._update_detail_page()

            InfoBar.success(
                "Cloud", "Đã cập nhật thư viện từ Cloud.",
                parent=self, position=InfoBarPosition.TOP_RIGHT, duration=2000
            )
        else:
            InfoBar.info(
                "Cloud", "Dùng dữ liệu cục bộ.",
                parent=self, position=InfoBarPosition.TOP_RIGHT, duration=2000
            )

        QTimer.singleShot(
            3000, lambda: self._set_status("Sẵn sàng")
        )



    # ══════════════════════════════════════════
    #  Game Actions
    # ══════════════════════════════════════════
    def _open_save_folder(self):
        save_dir = get_save_dir()
        if save_dir and os.path.exists(save_dir):
            os.startfile(save_dir)
        else:
            InfoBar.warning(
                "Lỗi", "Thư mục save không tồn tại.",
                parent=self, position=InfoBarPosition.TOP_RIGHT, duration=3000
            )

    def _manual_sync_up(self):
        w = MessageBox(
            "⚠  Cảnh báo Ghi đè",
            "Hành động này sẽ tải file save trên máy lên Cloud và "
            "TẤT CẢ save cũ trên Cloud sẽ bị thay thế.\n\n"
            "Bạn có chắc chắn muốn ghi đè?",
            self
        )
        w.yesButton.setText("Ghi đè")
        w.cancelButton.setText("Hủy")

        if w.exec():
            self.progress.setVisible(True)
            self.progress.setValue(0)
            self.launch_btn.setEnabled(False)
            self._set_status("Đang đẩy save lên Cloud…")

            self._up = SyncUpWorker()
            self._up.status.connect(lambda t: self._set_status(t))
            self._up.progress.connect(self.progress.setValue)
            self._up.finished.connect(self._after_sync_up)
            self._up.start()

    def _on_play(self):
        self.launch_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._set_status("Đang đồng bộ save…")

        self._down = SyncDownWorker()
        self._down.status.connect(lambda t: self._set_status(t))
        self._down.progress.connect(self.progress.setValue)
        self._down.finished.connect(self._after_sync_down)
        self._down.start()

    def _after_sync_down(self, ok, msg):
        if not ok:
            self._set_status(msg)

        self.progress.setVisible(False)
        self._set_status("Đang khởi chạy game…")

        self._game = GameLaunchWorker()
        self._game.started.connect(lambda: self._set_status("Đang chơi…"))
        self._game.finished.connect(self._after_game)
        self._game.start()

    def _after_game(self, exit_code):
        if exit_code < 0:
            self._set_status("Không tìm thấy game")
            self.launch_btn.setEnabled(True)
            return

        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._set_status("Đang đẩy save lên Cloud…")

        self._up = SyncUpWorker()
        self._up.status.connect(lambda t: self._set_status(t))
        self._up.progress.connect(self.progress.setValue)
        self._up.finished.connect(self._after_sync_up)
        self._up.start()

    def _after_sync_up(self, ok, msg):
        self.progress.setVisible(False)
        self.launch_btn.setEnabled(True)
        self._set_status(msg)

        if ok:
            InfoBar.success(
                "Cloud", msg,
                parent=self, position=InfoBarPosition.TOP_RIGHT, duration=3000
            )
        else:
            InfoBar.error(
                "Cloud", msg,
                parent=self, position=InfoBarPosition.TOP_RIGHT, duration=3000
            )

    def _set_status(self, text):
        if not hasattr(self, 'status_label'):
            return
        icon = "⚠" if any(k in text.lower() for k in ["lỗi", "không"]) else "⭐"
        self.status_label.setText(f"{icon}  {text}")

    # ══════════════════════════════════════════
    #  Auth
    # ══════════════════════════════════════════
    def _handle_logout(self):
        w = MessageBox("Đăng xuất", "Bạn có chắc muốn đăng xuất?", self)
        if w.exec():
            AuthManager().logout()
            restart_app()

    # ══════════════════════════════════════════
    #  Auto-Update
    # ══════════════════════════════════════════
    def _check_for_updates(self):
        self._update_checker = CheckUpdateWorker()
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.start()

    def _on_update_available(self, version, url, changelog):
        msg = (
            f"Phiên bản mới {version} đã sẵn sàng!\n\n"
            f"Vui lòng chạy Update.exe để cập nhật bản mới nhất nhằm đảm bảo tính ổn định."
        )
        w = MessageBox("🚀 Có bản cập nhật mới!", msg, self)
        w.yesButton.setText("Mở Update.exe")
        w.cancelButton.setText("Để sau")

        if w.exec():
            # Close app and open bootstrapper
            update_exe = "bootstrapper.exe" if getattr(sys, 'frozen', False) else "bootstrapper.py"
            import subprocess
            if getattr(sys, 'frozen', False):
                path = os.path.join(os.path.dirname(sys.executable), update_exe)
                if os.path.exists(path):
                    subprocess.Popen([path])
            else:
                subprocess.Popen([sys.executable, update_exe])
            sys.exit(0)

    def _start_update_download(self, url):
        # Show progress on detail page
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._set_status("Đang tải bản cập nhật…")

        self._updater = DownloadUpdateWorker(url)
        self._updater.progress.connect(self.progress.setValue)
        self._updater.status.connect(lambda t: self._set_status(t))
        self._updater.finished.connect(self._on_update_downloaded)
        self._updater.start()

    def _on_update_downloaded(self, success, result):
        if not success:
            self.progress.setVisible(False)
            InfoBar.error(
                "Cập nhật thất bại", result,
                parent=self, position=InfoBarPosition.TOP_RIGHT, duration=5000
            )
            self._set_status("Cập nhật thất bại")
            return

        self._set_status("Đang cài đặt bản cập nhật…")
        self.progress.setValue(98)

        ok, msg = apply_update(result)

        if ok:
            self.progress.setValue(100)
            InfoBar.success(
                "Cập nhật thành công!",
                "Ứng dụng sẽ khởi động lại sau 2 giây…",
                parent=self, position=InfoBarPosition.TOP_RIGHT, duration=2000
            )
            QTimer.singleShot(2000, restart_app)
        else:
            self.progress.setVisible(False)
            InfoBar.error(
                "Lỗi cài đặt", msg,
                parent=self, position=InfoBarPosition.TOP_RIGHT, duration=5000
            )
            self._set_status(msg)
