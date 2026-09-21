import re
import logging
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QSlider,
                             QCheckBox, QPushButton, QGroupBox, QLineEdit)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence

logger = logging.getLogger("livedot.settings")

DEVELOPER_PORTAL_URL = "https://discord.com/developers/applications"

# A bare key would be swallowed system-wide once grabbed, so plain keys need a
# modifier. Function keys are the exception: nobody types with them.
BARE_KEY_ALLOWED = re.compile(r"F([1-9]|1[0-9]|2[0-4])")

CAPTURE_PROMPT = "Pressione a combinação de teclas\nou um botão lateral do mouse...\n\n(Esc para cancelar)"
CAPTURE_NEEDS_MODIFIER = "Use junto Ctrl, Alt, Shift ou Super\n(ou uma tecla F1–F24)\n\n(Esc para cancelar)"


def modifier_names(modifiers):
    names = []
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        names.append("Ctrl")
    if modifiers & Qt.KeyboardModifier.AltModifier:
        names.append("Alt")
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        names.append("Shift")
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        names.append("Super")
    return names


class HotkeyCaptureDialog(QDialog):
    """
    A dedicated dialog window that grabs the keyboard to capture the Livedot
    hotkey reliably (compatible with GNOME Shell).
    """
    def __init__(self, state_manager, parent=None):
        super().__init__(parent)
        self.state_manager = state_manager
        self.hotkey_str = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Capturar Atalho")
        self.setFixedSize(280, 130)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)

        # Vibrant purple border to indicate keyboard capture state
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
                border: 2px solid #8b5cf6;
                border-radius: 12px;
            }
            QLabel {
                font-size: 13px;
                color: #f8fafc;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)

        self.label = QLabel(CAPTURE_PROMPT)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def showEvent(self, event):
        super().showEvent(event)
        self.grabKeyboard()

    def keyPressEvent(self, event):
        key = event.key()

        # Ignore modifier-only key events
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta,
                   Qt.Key.Key_AltGr, Qt.Key.Key_Super_L, Qt.Key.Key_Super_R):
            return

        # Cancel key capture on Esc
        if key == Qt.Key.Key_Escape:
            logger.info("Hotkey capture cancelled by user.")
            self.releaseKeyboard()
            self.reject()
            return

        key_str = QKeySequence(key).toString()
        if not key_str:
            return

        mods_list = modifier_names(event.modifiers())
        if not mods_list and not BARE_KEY_ALLOWED.fullmatch(key_str):
            self.label.setText(CAPTURE_NEEDS_MODIFIER)
            return

        self.save("+".join(mods_list + [key_str]))

    def mousePressEvent(self, event):
        # We capture thumb/side buttons: Back (Mouse8), Forward (Mouse9), Task (Mouse10)
        button_names = {
            Qt.MouseButton.BackButton: "Mouse8",
            Qt.MouseButton.ForwardButton: "Mouse9",
            Qt.MouseButton.TaskButton: "Mouse10",
        }
        button_str = button_names.get(event.button())
        if button_str:
            self.save("+".join(modifier_names(event.modifiers()) + [button_str]))
        else:
            super().mousePressEvent(event)

    def save(self, hotkey_str):
        self.hotkey_str = hotkey_str
        logger.info(f"HotkeyCaptureDialog captured: {self.hotkey_str}")
        self.state_manager.set_app_hotkey(self.hotkey_str)
        self.releaseKeyboard()
        self.accept()

    def closeEvent(self, event):
        self.releaseKeyboard()
        super().closeEvent(event)


class SettingsDialog(QDialog):
    def __init__(self, state_manager, discord, parent_window):
        super().__init__(parent_window)
        self.state_manager = state_manager
        self.discord = discord
        self.parent_window = parent_window
        self.init_ui()
        self.discord.status_changed.connect(self.show_discord_status)

    def init_ui(self):
        self.setWindowTitle("Livedot - Configurações")
        self.setFixedWidth(360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Visual Styling - Sleek Dark Theme matching the right-click menu
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QLabel {
                color: #f8fafc;
                font-size: 12px;
            }
            QLabel#hint {
                color: #94a3b8;
                font-size: 11px;
            }
            QGroupBox {
                border: 1px solid #1e293b;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 12px;
                color: #94a3b8;
                font-weight: bold;
                font-size: 11px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #1e293b;
                height: 6px;
                background: #1e293b;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #3b82f6;
                width: 14px;
                height: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #60a5fa;
            }
            QCheckBox {
                color: #f8fafc;
                font-size: 12px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #334155;
                border-radius: 4px;
                background-color: #1e293b;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                border: 1px solid #3b82f6;
            }
            QLineEdit {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
            QPushButton {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #334155;
                border-color: #475569;
            }
            QPushButton#primaryBtn {
                background-color: #3b82f6;
                border: 1px solid #2563eb;
            }
            QPushButton#primaryBtn:hover {
                background-color: #2563eb;
            }
            QPushButton#captureBtn {
                background-color: #1e293b;
                border: 1px solid #334155;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton#captureBtn:hover {
                background-color: #334155;
                border-color: #3b82f6;
            }
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(16, 8, 16, 16)

        # Header title
        title_label = QLabel("CONFIGURAÇÕES DO OVERLAY")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #3b82f6; letter-spacing: 1px;")
        main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Group 1: Visual Sliders
        visual_group = QGroupBox("Aparência")
        visual_layout = QVBoxLayout()
        visual_layout.setSpacing(10)

        # Scale Control
        scale_label_layout = QHBoxLayout()
        scale_title = QLabel("Tamanho (Escala):")
        self.scale_val_label = QLabel(f"{int(self.state_manager.config['scale'] * 100)}%")
        self.scale_val_label.setStyleSheet("color: #3b82f6; font-weight: bold;")
        scale_label_layout.addWidget(scale_title)
        scale_label_layout.addWidget(self.scale_val_label, alignment=Qt.AlignmentFlag.AlignRight)
        visual_layout.addLayout(scale_label_layout)

        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setMinimum(50)
        self.scale_slider.setMaximum(200)
        self.scale_slider.setValue(int(self.state_manager.config["scale"] * 100))
        self.scale_slider.valueChanged.connect(self.on_scale_changed)
        visual_layout.addWidget(self.scale_slider)

        # Opacity Control
        opacity_label_layout = QHBoxLayout()
        opacity_title = QLabel("Opacidade Base:")
        self.opacity_val_label = QLabel(f"{int(self.state_manager.config['opacity'] * 100)}%")
        self.opacity_val_label.setStyleSheet("color: #3b82f6; font-weight: bold;")
        opacity_label_layout.addWidget(opacity_title)
        opacity_label_layout.addWidget(self.opacity_val_label, alignment=Qt.AlignmentFlag.AlignRight)
        visual_layout.addLayout(opacity_label_layout)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(10)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(int(self.state_manager.config["opacity"] * 100))
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        visual_layout.addWidget(self.opacity_slider)

        visual_group.setLayout(visual_layout)
        main_layout.addWidget(visual_group)

        # Group 2: Behaviors Checkboxes
        behavior_group = QGroupBox("Comportamento")
        behavior_layout = QVBoxLayout()
        behavior_layout.setSpacing(8)

        self.lock_cb = QCheckBox("Travar posição na tela")
        self.lock_cb.setChecked(self.state_manager.config["position_locked"])
        self.lock_cb.stateChanged.connect(self.on_lock_toggled)
        behavior_layout.addWidget(self.lock_cb)

        self.autostart_cb = QCheckBox("Iniciar junto com o sistema")
        self.autostart_cb.setChecked(self.state_manager.config["autostart_enabled"])
        self.autostart_cb.stateChanged.connect(self.on_autostart_toggled)
        behavior_layout.addWidget(self.autostart_cb)

        behavior_group.setLayout(behavior_layout)
        main_layout.addWidget(behavior_group)

        # Group 3: Hotkey
        hotkey_group = QGroupBox("Atalho")
        hotkey_layout = QHBoxLayout()

        app_hk_title = QLabel("Atalho do Livedot:")
        app_hk_title.setStyleSheet("font-weight: bold;")
        self.app_hk_val = QLabel(self.state_manager.config["app_hotkey"])
        self.app_hk_val.setStyleSheet("color: #e2e8f0; background-color: #1e293b; padding: 2px 6px; border-radius: 4px;")
        app_hk_btn = QPushButton("Definir")
        app_hk_btn.setObjectName("captureBtn")
        app_hk_btn.clicked.connect(self.capture_app_hotkey)
        hotkey_layout.addWidget(app_hk_title)
        hotkey_layout.addWidget(self.app_hk_val)
        hotkey_layout.addWidget(app_hk_btn)

        hotkey_group.setLayout(hotkey_layout)
        main_layout.addWidget(hotkey_group)

        # Group 4: Discord connection
        discord_group = QGroupBox("Discord")
        discord_layout = QVBoxLayout()
        discord_layout.setSpacing(8)

        fields = QGridLayout()
        fields.setHorizontalSpacing(8)
        fields.setVerticalSpacing(6)
        self.client_id_edit = QLineEdit(self.state_manager.config["discord_client_id"])
        self.client_id_edit.setPlaceholderText("ID do aplicativo")
        self.client_secret_edit = QLineEdit(self.state_manager.config["discord_client_secret"])
        self.client_secret_edit.setPlaceholderText("Secret do aplicativo")
        self.client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        fields.addWidget(QLabel("Client ID:"), 0, 0)
        fields.addWidget(self.client_id_edit, 0, 1)
        fields.addWidget(QLabel("Client Secret:"), 1, 0)
        fields.addWidget(self.client_secret_edit, 1, 1)
        discord_layout.addLayout(fields)

        hint = QLabel(f'Crie um aplicativo em <a href="{DEVELOPER_PORTAL_URL}" '
                      f'style="color: #60a5fa;">discord.com/developers</a> '
                      f'(passo a passo no README).')
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hint.setOpenExternalLinks(True)
        discord_layout.addWidget(hint)

        status_layout = QHBoxLayout()
        self.discord_status = QLabel()
        self.discord_status.setObjectName("hint")
        self.discord_status.setWordWrap(True)
        connect_btn = QPushButton("Conectar")
        connect_btn.setObjectName("captureBtn")
        connect_btn.clicked.connect(self.on_connect_clicked)
        status_layout.addWidget(self.discord_status, 1)
        status_layout.addWidget(connect_btn)
        discord_layout.addLayout(status_layout)
        self.show_discord_status(self.discord.status)

        discord_group.setLayout(discord_layout)
        main_layout.addWidget(discord_group)

        # Footer Action Button
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        close_btn = QPushButton("Fechar")
        close_btn.setObjectName("primaryBtn")
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(close_btn)
        main_layout.addLayout(footer_layout)

        self.setLayout(main_layout)

    # Change event callbacks
    def on_scale_changed(self, val):
        self.scale_val_label.setText(f"{val}%")
        self.parent_window.change_scale(val / 100.0)

    def on_opacity_changed(self, val):
        opacity = val / 100.0
        self.opacity_val_label.setText(f"{val}%")
        self.state_manager.set_opacity(opacity)

    def on_lock_toggled(self, state):
        self.state_manager.set_position_locked(self.lock_cb.isChecked())

    def on_autostart_toggled(self, state):
        import autostart
        enabled = self.autostart_cb.isChecked()
        if autostart.set_autostart(enabled):
            self.state_manager.set_autostart_enabled(enabled)

    def on_connect_clicked(self):
        self.state_manager.set_discord_credentials(self.client_id_edit.text().strip(),
                                                   self.client_secret_edit.text().strip())
        self.discord.reconnect()

    def show_discord_status(self, status):
        self.discord_status.setText(f"Status: {status}" if status else "")

    # Synchronous capture workflow
    def capture_app_hotkey(self):
        dial = HotkeyCaptureDialog(self.state_manager, self)
        if dial.exec() == QDialog.DialogCode.Accepted:
            self.app_hk_val.setText(self.state_manager.config["app_hotkey"])

    def sync_checkboxes(self):
        """Synchronizes widget states if changed from the right click menu directly."""
        self.lock_cb.setChecked(self.state_manager.config["position_locked"])
        self.autostart_cb.setChecked(self.state_manager.config["autostart_enabled"])
        self.scale_slider.setValue(int(self.state_manager.config["scale"] * 100))
        self.opacity_slider.setValue(int(self.state_manager.config["opacity"] * 100))
        self.app_hk_val.setText(self.state_manager.config["app_hotkey"])
        self.client_id_edit.setText(self.state_manager.config["discord_client_id"])
        self.client_secret_edit.setText(self.state_manager.config["discord_client_secret"])
        self.show_discord_status(self.discord.status)
