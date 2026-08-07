import logging
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QCheckBox, QPushButton, QGroupBox, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence

import constants

logger = logging.getLogger("livedot.settings")

class HotkeyCaptureDialog(QDialog):
    """
    A dedicated dialog window that handles X11 keyboard grabs to capture
    global hotkey configurations reliably (compatible with GNOME Shell).
    """
    def __init__(self, target_name: str, state_manager, parent=None):
        super().__init__(parent)
        self.target_name = target_name  # "app" or "discord"
        self.state_manager = state_manager
        self.hotkey_str = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Capturar Atalho")
        self.setFixedSize(280, 120)
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
        
        self.label = QLabel("Pressione a combinação de teclas...\n\n(Esc para cancelar)")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.setLayout(layout)
        
    def showEvent(self, event):
        super().showEvent(event)
        self.grabKeyboard()
        
    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        # Ignore modifier-only key events
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return
            
        # Cancel key capture on Esc
        if key == Qt.Key.Key_Escape:
            logger.info("Hotkey capture cancelled by user.")
            self.releaseKeyboard()
            self.reject()
            return
            
        # Build modifiers string
        mods_list = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            mods_list.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            mods_list.append("Alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            mods_list.append("Shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            mods_list.append("Super")
            
        key_str = QKeySequence(key).toString()
        if not key_str:
            return
            
        # Format shortcut
        if mods_list:
            self.hotkey_str = "+".join(mods_list) + "+" + key_str
        else:
            self.hotkey_str = key_str
            
        logger.info(f"HotkeyCaptureDialog captured: {self.hotkey_str} for {self.target_name}")
        
        # Save straight to configuration
        if self.target_name == "app":
            self.state_manager.set_app_hotkey(self.hotkey_str)
        elif self.target_name == "discord":
            self.state_manager.set_discord_hotkey(self.hotkey_str)
            
        self.releaseKeyboard()
        self.accept()
        
    def mousePressEvent(self, event):
        button = event.button()
        modifiers = event.modifiers()
        
        # We capture thumb/side buttons: Back (Mouse8), Forward (Mouse9), Task (Mouse10)
        if button in (Qt.MouseButton.BackButton, Qt.MouseButton.ForwardButton, Qt.MouseButton.TaskButton):
            mods_list = []
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                mods_list.append("Ctrl")
            if modifiers & Qt.KeyboardModifier.AltModifier:
                mods_list.append("Alt")
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                mods_list.append("Shift")
            if modifiers & Qt.KeyboardModifier.MetaModifier:
                mods_list.append("Super")
                
            button_str = None
            if button == Qt.MouseButton.BackButton:
                button_str = "Mouse8"
            elif button == Qt.MouseButton.ForwardButton:
                button_str = "Mouse9"
            elif button == Qt.MouseButton.TaskButton:
                button_str = "Mouse10"
                
            if button_str:
                if mods_list:
                    self.hotkey_str = "+".join(mods_list) + "+" + button_str
                else:
                    self.hotkey_str = button_str
                    
                logger.info(f"HotkeyCaptureDialog captured mouse button: {self.hotkey_str} for {self.target_name}")
                
                # Save config
                if self.target_name == "app":
                    self.state_manager.set_app_hotkey(self.hotkey_str)
                elif self.target_name == "discord":
                    self.state_manager.set_discord_hotkey(self.hotkey_str)
                    
                self.releaseKeyboard()
                self.accept()
        else:
            super().mousePressEvent(event)
        
    def closeEvent(self, event):
        self.releaseKeyboard()
        super().closeEvent(event)


class SettingsDialog(QDialog):
    def __init__(self, state_manager, parent_window):
        super().__init__(parent_window)
        self.state_manager = state_manager
        self.parent_window = parent_window
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Livedot - Configurações")
        self.setFixedSize(360, 440)
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
        
        self.sound_cb = QCheckBox("Habilitar feedback sonoro")
        self.sound_cb.setChecked(self.state_manager.config["sound_enabled"])
        self.sound_cb.stateChanged.connect(self.on_sound_toggled)
        behavior_layout.addWidget(self.sound_cb)
        
        self.autostart_cb = QCheckBox("Iniciar junto com o sistema")
        self.autostart_cb.setChecked(self.state_manager.config["autostart_enabled"])
        self.autostart_cb.stateChanged.connect(self.on_autostart_toggled)
        behavior_layout.addWidget(self.autostart_cb)
        
        behavior_group.setLayout(behavior_layout)
        main_layout.addWidget(behavior_group)
        
        # Group 3: Keyboard Shortcuts
        hotkey_group = QGroupBox("Atalhos do Teclado")
        hotkey_layout = QVBoxLayout()
        hotkey_layout.setSpacing(10)
        
        # App Hotkey Control
        app_hk_layout = QHBoxLayout()
        app_hk_title = QLabel("Atalho do Livedot:")
        app_hk_title.setStyleSheet("font-weight: bold;")
        self.app_hk_val = QLabel(self.state_manager.config["app_hotkey"])
        self.app_hk_val.setStyleSheet("color: #e2e8f0; background-color: #1e293b; padding: 2px 6px; border-radius: 4px;")
        app_hk_btn = QPushButton("Definir")
        app_hk_btn.setObjectName("captureBtn")
        app_hk_btn.clicked.connect(self.capture_app_hotkey)
        app_hk_layout.addWidget(app_hk_title)
        app_hk_layout.addWidget(self.app_hk_val)
        app_hk_layout.addWidget(app_hk_btn)
        hotkey_layout.addLayout(app_hk_layout)
        
        # Discord Hotkey Control
        disc_hk_layout = QHBoxLayout()
        disc_hk_title = QLabel("Atalho do Discord:")
        disc_hk_title.setStyleSheet("font-weight: bold;")
        self.disc_hk_val = QLabel(self.state_manager.config["discord_hotkey"])
        self.disc_hk_val.setStyleSheet("color: #e2e8f0; background-color: #1e293b; padding: 2px 6px; border-radius: 4px;")
        disc_hk_btn = QPushButton("Definir")
        disc_hk_btn.setObjectName("captureBtn")
        disc_hk_btn.clicked.connect(self.capture_discord_hotkey)
        disc_hk_layout.addWidget(disc_hk_title)
        disc_hk_layout.addWidget(self.disc_hk_val)
        disc_hk_layout.addWidget(disc_hk_btn)
        hotkey_layout.addLayout(disc_hk_layout)
        
        hotkey_group.setLayout(hotkey_layout)
        main_layout.addWidget(hotkey_group)
        
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
        scale = val / 100.0
        self.scale_val_label.setText(f"{val}%")
        self.state_manager.set_scale(scale)
        self.parent_window.update_size_and_position()
        
    def on_opacity_changed(self, val):
        opacity = val / 100.0
        self.opacity_val_label.setText(f"{val}%")
        self.state_manager.set_opacity(opacity)

    def on_lock_toggled(self, state):
        self.state_manager.set_position_locked(self.lock_cb.isChecked())
        
    def on_sound_toggled(self, state):
        self.state_manager.set_sound_enabled(self.sound_cb.isChecked())
        
    def on_autostart_toggled(self, state):
        import autostart
        enabled = self.autostart_cb.isChecked()
        if autostart.set_autostart(enabled):
            self.state_manager.set_autostart_enabled(enabled)

    # Synchronous capture workflows
    def capture_app_hotkey(self):
        dial = HotkeyCaptureDialog("app", self.state_manager, self)
        if dial.exec() == QDialog.DialogCode.Accepted:
            self.app_hk_val.setText(self.state_manager.config["app_hotkey"])
        
    def capture_discord_hotkey(self):
        dial = HotkeyCaptureDialog("discord", self.state_manager, self)
        if dial.exec() == QDialog.DialogCode.Accepted:
            self.disc_hk_val.setText(self.state_manager.config["discord_hotkey"])

    def sync_checkboxes(self):
        """Synchronizes checkbox states if changed from the right click menu directly."""
        self.lock_cb.setChecked(self.state_manager.config["position_locked"])
        self.sound_cb.setChecked(self.state_manager.config["sound_enabled"])
        self.autostart_cb.setChecked(self.state_manager.config["autostart_enabled"])
        self.scale_slider.setValue(int(self.state_manager.config["scale"] * 100))
        self.opacity_slider.setValue(int(self.state_manager.config["opacity"] * 100))
        self.app_hk_val.setText(self.state_manager.config["app_hotkey"])
        self.disc_hk_val.setText(self.state_manager.config["discord_hotkey"])
