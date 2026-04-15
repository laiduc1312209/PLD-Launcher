"""
PLD Launcher — Authentication UI (PySide6 + QFluentWidgets Fluent Design)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget
)
from PySide6.QtCore import Qt, Signal

from qfluentwidgets import (
    LineEdit, PasswordLineEdit,
    PrimaryPushButton, TransparentPushButton, TransparentToolButton,
    SubtitleLabel, CaptionLabel, CardWidget,
    InfoBar, InfoBarPosition,
    FluentIcon as FIF, IconWidget
)

from auth_manager import AuthManager


import os
import sys

def resource_path(relative_path):
    """Resolve path for both dev and PyInstaller frozen mode."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)

class AuthPage(QWidget):
    auth_success = Signal()

    def __init__(self):
        super().__init__()
        self.auth_mgr = AuthManager()
        self._drag_pos = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("PLD Launcher")
        self.setFixedSize(420, 560)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("AuthPage { background-color: #202020; border-radius: 12px; }")
        
        # Set Window Icon
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)

        # ── Main Panel Card ──
        self.panel = CardWidget()
        self.panel.setStyleSheet(
            "CardWidget { background-color: #2d2d2d; border: 1px solid #3a3a3a; border-radius: 12px; }"
        )
        panel_lay = QVBoxLayout(self.panel)
        panel_lay.setContentsMargins(36, 32, 36, 40)
        panel_lay.setSpacing(0)

        # Close button (top-right)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = TransparentToolButton(FIF.CLOSE)
        close_btn.setFixedSize(32, 32)
        close_btn.clicked.connect(self.close)
        close_row.addWidget(close_btn)
        panel_lay.addLayout(close_row)

        panel_lay.addSpacing(4)

        # Logo
        if os.path.exists(icon_path):
            logo = IconWidget(icon_path)
            logo.setFixedSize(64, 64)
            panel_lay.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)

        panel_lay.addSpacing(14)

        # Title
        title = SubtitleLabel("PLD LAUNCHER")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_lay.addWidget(title)

        sub = CaptionLabel("Advanced Game Management")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_lay.addWidget(sub)

        panel_lay.addSpacing(28)

        # ── Login / Register Stack ──
        self.stack = QStackedWidget()
        self.loginView = self._create_login_view()
        self.registerView = self._create_register_view()
        self.stack.addWidget(self.loginView)
        self.stack.addWidget(self.registerView)
        panel_lay.addWidget(self.stack)

        panel_lay.addStretch()
        main_lay.addWidget(self.panel)

    # ── Login View ──
    def _create_login_view(self):
        view = QWidget()
        lay = QVBoxLayout(view)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        self.li_email = LineEdit()
        self.li_email.setPlaceholderText("Email")
        self.li_email.setClearButtonEnabled(True)
        lay.addWidget(self.li_email)

        self.li_pass = PasswordLineEdit()
        self.li_pass.setPlaceholderText("Mật khẩu")
        lay.addWidget(self.li_pass)

        lay.addSpacing(8)

        btn_login = PrimaryPushButton(FIF.ACCEPT, "ĐĂNG NHẬP")
        btn_login.setFixedHeight(44)
        btn_login.clicked.connect(self._handle_login)
        lay.addWidget(btn_login)

        switch = TransparentPushButton("Chưa có tài khoản? Nhấn để Đăng ký")
        switch.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        lay.addWidget(switch, alignment=Qt.AlignmentFlag.AlignCenter)

        return view

    # ── Register View ──
    def _create_register_view(self):
        view = QWidget()
        lay = QVBoxLayout(view)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        self.re_email = LineEdit()
        self.re_email.setPlaceholderText("Email")
        self.re_email.setClearButtonEnabled(True)
        lay.addWidget(self.re_email)

        self.re_pass = PasswordLineEdit()
        self.re_pass.setPlaceholderText("Mật khẩu")
        lay.addWidget(self.re_pass)

        self.re_pass2 = PasswordLineEdit()
        self.re_pass2.setPlaceholderText("Nhập lại mật khẩu")
        lay.addWidget(self.re_pass2)

        lay.addSpacing(8)

        btn_reg = PrimaryPushButton(FIF.ADD, "TẠO TÀI KHOẢN")
        btn_reg.setFixedHeight(44)
        btn_reg.clicked.connect(self._handle_register)
        lay.addWidget(btn_reg)

        switch = TransparentPushButton("Đã có tài khoản? Đăng nhập ngay")
        switch.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        lay.addWidget(switch, alignment=Qt.AlignmentFlag.AlignCenter)

        return view

    # ── Auth Handlers ──
    def _handle_login(self):
        email = self.li_email.text().strip()
        pw = self.li_pass.text().strip()

        if not all([email, pw]):
            InfoBar.warning(
                title="Thiếu thông tin",
                content="Vui lòng nhập Email và Mật khẩu.",
                parent=self, position=InfoBarPosition.TOP, duration=3000
            )
            return

        success, msg = self.auth_mgr.login(email, pw)
        if success:
            self.auth_success.emit()
        else:
            InfoBar.error(
                title="Đăng nhập thất bại", content=msg,
                parent=self, position=InfoBarPosition.TOP, duration=4000
            )

    def _handle_register(self):
        email = self.re_email.text().strip()
        pw = self.re_pass.text().strip()
        pw2 = self.re_pass2.text().strip()

        if not all([email, pw, pw2]):
            InfoBar.warning(
                title="Thiếu thông tin",
                content="Vui lòng nhập đầy đủ thông tin.",
                parent=self, position=InfoBarPosition.TOP, duration=3000
            )
            return

        if pw != pw2:
            InfoBar.warning(
                title="Lỗi", content="Mật khẩu nhập lại không khớp.",
                parent=self, position=InfoBarPosition.TOP, duration=3000
            )
            return

        success, msg = self.auth_mgr.register(email, pw)
        if success:
            self.auth_mgr.login(email, pw)
            self.auth_success.emit()
        else:
            InfoBar.error(
                title="Đăng ký thất bại", content=msg,
                parent=self, position=InfoBarPosition.TOP, duration=4000
            )

    # ── Drag to Move ──
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
