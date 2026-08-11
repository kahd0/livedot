import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QWidget, QMenu
from PyQt6.QtCore import Qt, QTimer, QDateTime, QPoint, QPointF, QSharedMemory
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QKeySequence

import constants
from state_manager import StateManager
from input_manager import InputManager
import sound_manager
from settings_dialog import SettingsDialog, HotkeyCaptureDialog

logger = logging.getLogger("livedot.main")

class OverlayWindow(QWidget):
    def __init__(self, state_manager: StateManager, input_manager: InputManager):
        super().__init__()
        self.state_manager = state_manager
        self.input_manager = input_manager
        
        # Connect state manager signals
        self.state_manager.visuals_updated.connect(self.update_visuals)
        self.state_manager.state_changed.connect(self.on_state_changed)
        
        # Local interactive state variables
        self.win_size = 64
        self.drag_offset = QPoint()
        self.is_capturing_hotkey = False
        self.capture_target = None  # "app" or "discord"
        self.capture_callback = None
        self.settings_dialog = None
        
        # Track time for animations
        self.last_anim_time = 0
        
        # Animation timer (runs at 60 FPS)
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(1000 // constants.FPS)
        self.anim_timer.timeout.connect(self.animate)
        
        # Init resources and layout
        sound_manager.initialize_sounds()
        self.init_ui()
        
    def init_ui(self):
        # Configure window flags for overlay behaviour
        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if sys.platform != "win32":
            # X11-only: bypasses the window manager so no reparenting or
            # decoration is applied. Windows has no equivalent concept.
            flags |= Qt.WindowType.BypassWindowManagerHint
        self.setWindowFlags(flags)
        
        # Translucent background flags to prevent X11 flicker or borders
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        
        # Scale and position initial setup
        self.update_size_and_position()
        
        x = self.state_manager.config["position_x"]
        y = self.state_manager.config["position_y"]
        
        # Auto-center relative to screen size on first install
        if not os.path.exists(constants.CONFIG_FILE):
            screen = QApplication.primaryScreen()
            if screen:
                screen_geom = screen.geometry()
                scale = self.state_manager.config["scale"]
                win_size = int(64 * scale)
                # Position near bottom left (x: 40px, y: 80px from screen bottom)
                x = 40
                y = screen_geom.height() - win_size - 80
                self.state_manager.config["position_x"] = x
                self.state_manager.config["position_y"] = y
                self.state_manager.save_config()
                
        self.move(x, y)
        self.show()
        self.raise_()
        
        # Ensure we draw initial state
        self.update()
        logger.info(f"OverlayWindow shown at coordinates ({x}, {y})")

    def update_size_and_position(self):
        """Resizes the bounding box of the overlay to account for current scale."""
        scale = self.state_manager.config["scale"]
        self.win_size = int(80 * scale)  # Bounding box of 80px scaled
        self.setFixedSize(self.win_size, self.win_size)
        self.update()

    def on_state_changed(self, is_muted: bool):
        """Called when microphone state changes. Updates rendering and plays audio."""
        if not is_muted:
            # When unmuting, run the auto-expand animation timer
            self.last_anim_time = QDateTime.currentMSecsSinceEpoch()
            self.anim_timer.start()
        else:
            # Muted (calma visual) drops active timer to conserve CPU
            self.anim_timer.stop()
            self.update()
            
        self.raise_()
        logger.info(f"Visual state synchronized. Muted: {is_muted}")

    def animate(self):
        """Advancement loop for active transitions and pulses."""
        current_time = QDateTime.currentMSecsSinceEpoch()
        dt_ms = current_time - self.last_anim_time
        self.last_anim_time = current_time
        
        # Advance timers inside state manager
        need_repaint = self.state_manager.advance_time(dt_ms)
        if need_repaint:
            self.update()

    def update_visuals(self):
        """Redraw wrapper."""
        self.update()

    # Paint event
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Completely clear window canvas
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        
        scale = self.state_manager.config["scale"]
        
        # Define color and size overrides based on keyboard capture state
        if self.is_capturing_hotkey:
            # Highlight dot in Violet during key combination capture
            size = constants.SIZE_UNMUTED * scale
            opacity = 1.0
            color_rgb = (139, 92, 246)  # Violet-500
        else:
            size = self.state_manager.current_size * scale
            opacity = self.state_manager.current_opacity
            color_rgb = self.state_manager.current_color
            
        center_x = self.win_size / 2.0
        center_y = self.win_size / 2.0
        radius = size / 2.0
        
        # Draw soft concentric glow rings if unmuted (breathing mode)
        if not self.state_manager.muted and not self.is_capturing_hotkey:
            glow_color = QColor(*constants.COLOR_UNMUTED)
            for i in range(3, 0, -1):
                glow_radius = radius + (i * 2.5 * scale)
                glow_opacity = opacity * 0.12 / i
                glow_color.setAlphaF(glow_opacity)
                painter.setBrush(QBrush(glow_color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(center_x, center_y), glow_radius, glow_radius)
                
        # Draw primary circle
        base_color = QColor(*color_rgb)
        base_color.setAlphaF(opacity)
        painter.setBrush(QBrush(base_color))
        
        # Delicate semi-transparent border hint
        border_color = QColor(*constants.COLOR_BORDER)
        border_color.setAlphaF(opacity * 0.4)
        painter.setPen(QPen(border_color, 1.2 * scale))
        
        painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

    # Mouse / Drag Events
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.state_manager.handle_mouse_press(event.globalPosition().toPoint())
            self.drag_offset = event.position().toPoint()
            
            # Cancel capturing hotkey if user left-clicks
            if self.is_capturing_hotkey:
                self.end_hotkey_capture()
        elif event.button() == Qt.MouseButton.RightButton:
            # Ignore clicks during active capture
            if not self.is_capturing_hotkey:
                self.show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            if self.state_manager.handle_mouse_move(global_pos):
                new_pos = global_pos - self.drag_offset
                self.move(new_pos)
                self.state_manager.set_position(new_pos.x(), new_pos.y())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            # If release is resolved as a click, play tone and toggle state
            self.state_manager.handle_mouse_release(global_pos)

    # Right-Click Menu
    def show_settings(self):
        """Displays the unified settings window."""
        if not self.settings_dialog:
            self.settings_dialog = SettingsDialog(self.state_manager, self)
        else:
            self.settings_dialog.sync_checkboxes()
        self.settings_dialog.exec()

    # Right-Click Menu
    def show_context_menu(self, global_pos: QPoint):
        menu = QMenu(self)
        
        # High aesthetics dark slate theme
        menu.setStyleSheet("""
            QMenu {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
            QMenu::item:disabled {
                color: #64748b;
                font-weight: bold;
                font-size: 11px;
                padding-bottom: 2px;
            }
            QMenu::separator {
                height: 1px;
                background-color: #1e293b;
                margin: 4px 0px;
            }
        """)
        
        # Surface hotkey problems here: a refused registration or a blocked
        # SendInput is otherwise indistinguishable from "the app does nothing".
        error = self.input_manager.status_error()
        if error:
            # QMenu does not wrap, so keep the row short and leave the full text
            # to the tooltip and the log.
            short = error if len(error) <= 60 else error[:57] + "..."
            warning = menu.addAction(f"⚠ {short}")
            warning.setToolTip(error)
            warning.setEnabled(False)
            menu.addSeparator()

        # Configurações
        settings_action = menu.addAction("Configurações")
        settings_action.triggered.connect(self.show_settings)
        menu.addSeparator()
        
        # Travar posição
        lock_action = menu.addAction("Travar posição")
        lock_action.setCheckable(True)
        lock_action.setChecked(self.state_manager.config["position_locked"])
        lock_action.triggered.connect(lambda: self.state_manager.set_position_locked(lock_action.isChecked()))
        
        # Alterar hotkey submenu
        hotkey_menu = menu.addMenu("Alterar hotkey")
        hotkey_menu.setStyleSheet(menu.styleSheet())
        
        app_action = hotkey_menu.addAction("Definir Atalho do App")
        app_action.triggered.connect(lambda: self.trigger_direct_capture("app"))
        
        disc_action = hotkey_menu.addAction("Definir Atalho do Discord")
        disc_action.triggered.connect(lambda: self.trigger_direct_capture("discord"))
        
        # Opacidade submenu
        opacity_menu = menu.addMenu("Opacidade")
        opacity_menu.setStyleSheet(menu.styleSheet())
        
        opacities = [("20%", 0.2), ("40%", 0.4), ("60%", 0.6), ("80%", 0.8), ("100%", 1.0)]
        for label, val in opacities:
            action = opacity_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(abs(self.state_manager.config["opacity"] - val) < 0.05)
            action.triggered.connect(lambda checked, v=val: self.state_manager.set_opacity(v))
            
        # Size scale submenu
        size_menu = menu.addMenu("Tamanho")
        size_menu.setStyleSheet(menu.styleSheet())
        
        sizes = [("Pequeno", 0.75), ("Padrão", 1.0), ("Grande", 1.5), ("Gigante", 2.0)]
        for label, val in sizes:
            action = size_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(abs(self.state_manager.config["scale"] - val) < 0.05)
            action.triggered.connect(lambda checked, v=val: self.change_scale(v))
            
        # Inicializar com sistema
        autostart_action = menu.addAction("Inicializar com sistema")
        autostart_action.setCheckable(True)
        autostart_action.setChecked(self.state_manager.config["autostart_enabled"])
        autostart_action.triggered.connect(self.toggle_autostart)
        
        menu.addSeparator()
        
        # Quit
        exit_action = menu.addAction("Sair")
        exit_action.triggered.connect(QApplication.quit)
        
        menu.exec(global_pos)

    def change_scale(self, val: float):
        self.state_manager.set_scale(val)
        self.update_size_and_position()

    def toggle_autostart(self, checked: bool):
        import autostart
        if autostart.set_autostart(checked):
            self.state_manager.set_autostart_enabled(checked)

    def trigger_direct_capture(self, target: str):
        """Launches the dedicated hotkey capture dialog."""
        dial = HotkeyCaptureDialog(target, self.state_manager, self)
        dial.exec()

def main():
    # Setup PyQt context
    app = QApplication(sys.argv)
    app.setApplicationName(constants.APP_NAME)
    
    # Configure logs
    os.makedirs(constants.LOG_DIR, exist_ok=True)
    handlers = [logging.FileHandler(constants.LOG_FILE, encoding="utf-8")]
    # A windowed PyInstaller build has no console attached, so sys.stdout is
    # None and a StreamHandler would fail on every record.
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers
    )
    
    logger.info("Starting Livedot overlay application...")
    
    # Single Instance Lock using Qt's QSharedMemory.
    # A crash or a hard kill (SIGTERM/SIGKILL) skips cleanup() and leaves the
    # shared-memory segment behind. Attaching then detaching frees an orphaned
    # segment (Qt removes it once no process stays attached), so a normal
    # restart isn't blocked by a stale lock. A genuinely running instance keeps
    # the segment attached, so create() below still fails as intended.
    shared_mem = QSharedMemory(constants.SINGLE_INSTANCE_KEY)
    if shared_mem.attach():
        shared_mem.detach()
    if not shared_mem.create(1):
        logger.warning("Another instance of Livedot is already running. Exiting.")
        sys.exit(0)
        
    state_manager = StateManager()
    input_manager = InputManager(state_manager)
    window = OverlayWindow(state_manager, input_manager)
    
    def cleanup():
        logger.info("Exiting Livedot. Cleaning up resources...")
        input_manager.close()
        shared_mem.detach()
        
    app.aboutToQuit.connect(cleanup)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
