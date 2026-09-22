import sys
import os
import getpass
import math
import logging
from logging.handlers import RotatingFileHandler
from PyQt6.QtWidgets import QApplication, QWidget, QMenu
from PyQt6.QtCore import Qt, QTimer, QDateTime, QPoint, QPointF, QSharedMemory
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

import constants
import autostart
from state_manager import StateManager
from input_manager import InputManager
from discord_rpc import DiscordRPC
from mic_guard import MicGuard
from message_alert import MessageAlert
from settings_dialog import SettingsDialog, HotkeyCaptureDialog

logger = logging.getLogger("livedot.main")

class OverlayWindow(QWidget):
    def __init__(self, state_manager: StateManager, input_manager: InputManager,
                 discord: DiscordRPC, alert: MessageAlert):
        super().__init__()
        self.state_manager = state_manager
        self.input_manager = input_manager
        self.discord = discord
        self.alert = alert

        # Connect state manager signals
        self.state_manager.visuals_updated.connect(self.update)
        self.state_manager.state_changed.connect(self.on_state_changed)
        self.alert.changed.connect(self.on_alert_changed)
        self.alert.popped.connect(self.start_animation)

        # Re-check the position when a monitor goes away. Deferred so Qt has
        # finished updating its screen list first.
        app = QApplication.instance()
        if app:
            app.screenRemoved.connect(self.on_screens_changed)
            app.primaryScreenChanged.connect(self.on_screens_changed)

        # Local interactive state variables
        self.win_size = constants.WINDOW_SIZE
        self.drag_offset = QPoint()
        self.press_on_badge = False
        self.settings_dialog = None

        # Track time for animations
        self.last_anim_time = 0
        self.flash_start = None  # set by flash()
        self.flash_blinks = 0

        # Animation timer (runs at constants.FPS)
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(1000 // constants.FPS)
        self.anim_timer.timeout.connect(self.animate)

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
        # The overlay never takes focus, and Qt skips tooltips of inactive windows.
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)

        self.update_size()
        self.ensure_valid_position()

        self.show()
        self.raise_()
        logger.info(f"OverlayWindow shown at coordinates ({self.x()}, {self.y()})")

    def on_screens_changed(self, screen=None):
        """Called when display configuration changes (e.g., monitor disconnected)."""
        logger.info("Screen configuration changed. Validating window position...")
        QTimer.singleShot(500, self.ensure_valid_position)

    def ensure_valid_position(self):
        """
        Brings the dot back when its center is on no connected screen, e.g.
        after the monitor it lived on was unplugged. Anywhere else is left
        alone: panels and taskbars are good spots for it, and a dot straddling
        two monitors is still visible.
        """
        x = self.state_manager.config["position_x"]
        y = self.state_manager.config["position_y"]
        center = QPoint(x + self.win_size // 2, y + self.win_size // 2)

        primary = QApplication.primaryScreen()
        if QApplication.screenAt(center) is None and primary is not None:
            avail = primary.availableGeometry()
            new_x = avail.x() + 40
            new_y = avail.y() + avail.height() - self.win_size - 40
            logger.info(f"Position ({x}, {y}) is off-screen. Moving to ({new_x}, {new_y}).")
            x, y = new_x, new_y
            self.state_manager.config["position_x"] = x
            self.state_manager.config["position_y"] = y
            self.state_manager.save_config()

        self.move(x, y)

    def update_size(self):
        """Resizes the bounding box of the overlay to account for current scale."""
        scale = self.state_manager.config["scale"]
        self.win_size = int(constants.WINDOW_SIZE * scale)
        self.setFixedSize(self.win_size, self.win_size)
        self.update()

    def on_state_changed(self):
        """Called when the voice, call or connection state changes."""
        if self.state_manager.active:
            # Mic open: run the auto-expand and breathing animation
            self.start_animation()
        elif not (self.is_flashing() or self.alert.is_popping()):
            # Muted or disconnected (calma visual) drops the timer to conserve CPU
            self.anim_timer.stop()
        self.update()
        self.raise_()

    def on_alert_changed(self):
        self.setToolTip(self.alert.tooltip())
        self.update()
        self.raise_()

    def start_animation(self):
        if not self.anim_timer.isActive():
            self.last_anim_time = QDateTime.currentMSecsSinceEpoch()
            self.anim_timer.start()

    def animate(self):
        """Advancement loop for active transitions, pulses and the flash."""
        current_time = QDateTime.currentMSecsSinceEpoch()
        dt_ms = current_time - self.last_anim_time
        self.last_anim_time = current_time

        # Advance timers inside state manager
        if (self.state_manager.advance_time(dt_ms) or self.is_flashing()
                or self.alert.is_popping()):
            self.update()
        else:
            # The flash or pop just ended on a static dot: draw it at rest
            self.anim_timer.stop()
            self.update()

    def flash(self, blinks=constants.FLASH_BLINKS):
        """Blinks an amber ring around the dot to draw the eye to it."""
        self.flash_start = QDateTime.currentMSecsSinceEpoch()
        self.flash_blinks = blinks
        self.ensure_valid_position()
        self.show()
        self.raise_()
        self.start_animation()
        self.update()

    def is_flashing(self):
        return (self.flash_start is not None and
                QDateTime.currentMSecsSinceEpoch() - self.flash_start
                < constants.FLASH_PERIOD_MS * self.flash_blinks)

    # Paint event
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Completely clear window canvas
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        center = QPointF(self.win_size / 2.0, self.win_size / 2.0)
        if not self.state_manager.connected:
            self.paint_disconnected(painter, center)
        elif not self.state_manager.in_call:
            self.paint_idle(painter, center)
        else:
            self.paint_dot(painter, center)
        if self.alert.visible:
            self.paint_badge(painter, center)
        if self.is_flashing():
            self.paint_flash(painter, center)

    def paint_disconnected(self, painter, center):
        """Hollow gray ring: the real mic state is unknown."""
        scale = self.state_manager.config["scale"]
        ring_color = QColor(*constants.COLOR_DISCONNECTED)
        ring_color.setAlphaF(constants.OPACITY_DISCONNECTED * self.state_manager.config["opacity"])
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(ring_color, 2.0 * scale))
        radius = constants.SIZE_MUTED * scale / 2.0
        painter.drawEllipse(center, radius, radius)

    def paint_idle(self, painter, center):
        """Faint speck: outside a voice channel nobody can hear the mic, so
        its state is left out rather than shown in red."""
        scale = self.state_manager.config["scale"]
        color = QColor(*constants.COLOR_IDLE)
        color.setAlphaF(constants.OPACITY_IDLE * self.state_manager.config["opacity"])
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        radius = constants.SIZE_IDLE * scale / 2.0
        painter.drawEllipse(center, radius, radius)

    def badge_center(self, center):
        """Up and to the right of the dot, clear of its resting size. The
        pulse is ignored so the badge stays put."""
        state = self.state_manager
        if not state.in_call:
            dot_size = constants.SIZE_IDLE
        elif state.active:
            dot_size = constants.SIZE_UNMUTED
        else:
            dot_size = constants.SIZE_MUTED
        offset = (dot_size / 2.0 + constants.BADGE_OFFSET) * state.config["scale"] * math.sqrt(0.5)
        return QPointF(center.x() + offset, center.y() - offset)

    def paint_badge(self, painter, center):
        """Blurple satellite: solid for a DM or mention, a ring otherwise."""
        scale = self.state_manager.config["scale"]
        radius = constants.SIZE_BADGE * scale / 2.0 * self.alert.pop_scale()
        if radius <= 0:
            return
        opacity = self.state_manager.config["opacity"]
        color = QColor(*constants.COLOR_MESSAGE)
        color.setAlphaF(opacity)
        if self.alert.direct:
            border = QColor(*constants.COLOR_BORDER)
            border.setAlphaF(opacity * 0.7)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(border, 1.0 * scale))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(color, 2.0 * scale))
        painter.drawEllipse(self.badge_center(center), radius, radius)

    def is_on_badge(self, pos: QPointF):
        if not self.alert.visible:
            return False
        center = QPointF(self.win_size / 2.0, self.win_size / 2.0)
        hit = (constants.SIZE_BADGE / 2.0 + constants.BADGE_HIT_SLOP) * self.state_manager.config["scale"]
        delta = pos - self.badge_center(center)
        return math.hypot(delta.x(), delta.y()) <= hit

    def paint_flash(self, painter, center):
        """Amber ring, on for the first half of each blink. Drawn at full
        opacity so the dot can be found even at the lowest base opacity."""
        period = constants.FLASH_PERIOD_MS
        elapsed = QDateTime.currentMSecsSinceEpoch() - self.flash_start
        if elapsed % period >= period / 2:
            return
        scale = self.state_manager.config["scale"]
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(*constants.COLOR_FLASH), 3.0 * scale))
        radius = constants.SIZE_EXPAND_PEAK * scale / 2.0
        painter.drawEllipse(center, radius, radius)

    def paint_dot(self, painter, center):
        state = self.state_manager
        scale = state.config["scale"]
        base_opacity = state.config["opacity"]
        radius = state.current_size * scale / 2.0
        opacity = state.current_opacity * base_opacity
        color_rgb = constants.COLOR_UNMUTED if state.active else constants.COLOR_MUTED

        # Draw soft concentric glow rings if unmuted (breathing mode)
        if state.active:
            glow_color = QColor(*constants.COLOR_UNMUTED)
            for i in range(3, 0, -1):
                glow_radius = radius + (i * 2.5 * scale)
                glow_color.setAlphaF(opacity * 0.12 / i)
                painter.setBrush(QBrush(glow_color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(center, glow_radius, glow_radius)

        # Draw primary circle
        base_color = QColor(*color_rgb)
        base_color.setAlphaF(opacity)
        painter.setBrush(QBrush(base_color))

        # Delicate semi-transparent border hint
        border_color = QColor(*constants.COLOR_BORDER)
        border_color.setAlphaF(opacity * 0.4)
        painter.setPen(QPen(border_color, 1.2 * scale))

        painter.drawEllipse(center, radius, radius)

        if state.deafened:
            # Second ring: not hearing anyone either
            ring_color = QColor(*color_rgb)
            ring_color.setAlphaF(opacity)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(ring_color, 1.5 * scale))
            ring_radius = radius + constants.DEAF_RING_GAP * scale
            painter.drawEllipse(center, ring_radius, ring_radius)

    # Mouse / Drag Events
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.state_manager.handle_mouse_press(event.globalPosition().toPoint())
            self.drag_offset = event.position().toPoint()
            self.press_on_badge = self.is_on_badge(event.position())
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.state_manager.request_deaf_toggle()
        elif event.button() == Qt.MouseButton.RightButton:
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
            # A click (not a drag) on the badge opens the message, anywhere
            # else it asks Discord to toggle the mic
            if self.state_manager.handle_mouse_release(event.globalPosition().toPoint()):
                if self.press_on_badge:
                    self.alert.open()
                else:
                    self.state_manager.request_toggle()

    def show_settings(self):
        """Displays the unified settings window."""
        if not self.settings_dialog:
            self.settings_dialog = SettingsDialog(self.state_manager, self.discord, self)
        else:
            self.settings_dialog.sync_checkboxes()
        self.settings_dialog.exec()

    # Right-Click Menu
    def show_context_menu(self, global_pos: QPoint):
        self.build_context_menu().exec(global_pos)

    def build_context_menu(self) -> QMenu:
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

        # Surface problems here: a missing Discord connection or a refused
        # hotkey is otherwise indistinguishable from "the app does nothing".
        problems = []
        if not self.discord.ready:
            problems.append(f"Discord: {self.discord.status}")
        hotkey_error = self.input_manager.status_error()
        if hotkey_error:
            problems.append(hotkey_error)
        for problem in problems:
            # QMenu does not wrap, so keep the row short and leave the full text
            # to the tooltip and the log.
            short = problem if len(problem) <= 60 else problem[:57] + "..."
            warning = menu.addAction(f"⚠ {short}")
            warning.setToolTip(problem)
            warning.setEnabled(False)

        if not self.discord.ready:
            if self.discord.configured:
                connect_action = menu.addAction("Conectar ao Discord")
                connect_action.triggered.connect(self.discord.reconnect)
            else:
                setup_action = menu.addAction("Configurar Discord…")
                setup_action.triggered.connect(self.show_settings)
        if problems:
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

        # Atalho
        hotkey_action = menu.addAction("Definir atalho")
        hotkey_action.triggered.connect(self.capture_hotkey)

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

        return menu

    def change_scale(self, val: float):
        self.state_manager.set_scale(val)
        self.update_size()
        self.ensure_valid_position()

    def toggle_autostart(self, checked: bool):
        if autostart.set_autostart(checked):
            self.state_manager.set_autostart_enabled(checked)

    def capture_hotkey(self):
        """Launches the dedicated hotkey capture dialog."""
        HotkeyCaptureDialog(self.state_manager, self).exec()


def sync_autostart(state_manager: StateManager):
    """Treats the system as the source of truth for autostart. Rewriting an
    existing entry keeps it pointing at this copy of the app, in case it was
    moved or a new version was downloaded somewhere else."""
    enabled = autostart.is_autostart_enabled()
    if enabled:
        autostart.set_autostart(True)
    if state_manager.config["autostart_enabled"] != enabled:
        state_manager.set_autostart_enabled(enabled)


def instance_server_name():
    """Per-user name of the local socket the running instance listens on."""
    name = f"{constants.INSTANCE_SERVER_NAME}-{getpass.getuser()}"
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if sys.platform != "win32" and runtime_dir:
        # Private per-user directory; a bare name would land in /tmp.
        return os.path.join(runtime_dir, name)
    return name


def notify_running_instance():
    """Asks the instance that is already running to flash its dot. The
    connection itself is the message."""
    sock = QLocalSocket()
    sock.connectToServer(instance_server_name())
    if sock.waitForConnected(1000):
        sock.disconnectFromServer()
    else:
        logger.warning(f"Could not reach the running instance: {sock.errorString()}")


def start_instance_server(on_launch):
    """Listens for later launches of the app and calls on_launch for each."""
    name = instance_server_name()
    server = QLocalServer(QApplication.instance())
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    # Only the instance holding the single-instance lock gets here, so any
    # existing socket file is a leftover from a crash.
    QLocalServer.removeServer(name)
    if not server.listen(name):
        logger.warning(f"Could not listen on {name}: {server.errorString()}")
        return server

    def on_new_connection():
        while server.hasPendingConnections():
            server.nextPendingConnection().deleteLater()
        on_launch()

    server.newConnection.connect(on_new_connection)
    return server


def main():
    # Setup PyQt context
    app = QApplication(sys.argv)
    app.setApplicationName(constants.APP_NAME)

    # Configure logs
    os.makedirs(constants.LOG_DIR, exist_ok=True)
    handlers = [RotatingFileHandler(constants.LOG_FILE, maxBytes=constants.LOG_MAX_BYTES,
                                    backupCount=1, encoding="utf-8")]
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
        logger.warning("Another instance of Livedot is already running. Asking it to flash and exiting.")
        notify_running_instance()
        sys.exit(0)

    state_manager = StateManager()
    sync_autostart(state_manager)
    input_manager = InputManager(state_manager)
    discord = DiscordRPC(state_manager)

    # Discord is the single source of truth: clicks and the hotkey only ask it
    # to toggle, and the dot changes when Discord reports the new state.
    discord.voice_changed.connect(state_manager.set_voice)
    discord.call_changed.connect(state_manager.set_in_call)
    discord.connection_changed.connect(state_manager.set_connected)
    state_manager.toggle_requested.connect(discord.toggle_mute)
    state_manager.deaf_toggle_requested.connect(discord.toggle_deaf)
    guard = MicGuard(state_manager, discord)
    input_manager.pressed.connect(guard.hotkey_pressed)
    input_manager.released.connect(guard.hotkey_released)

    alert = MessageAlert(discord)
    window = OverlayWindow(state_manager, input_manager, discord, alert)
    discord.call_joined.connect(lambda: window.flash(constants.JOIN_FLASH_BLINKS))
    guard.auto_muted.connect(window.flash)

    def on_launched_again():
        logger.info("App launched again: flashing the dot.")
        window.flash()
    instance_server = start_instance_server(on_launched_again)
    discord.start()

    def cleanup():
        logger.info("Exiting Livedot. Cleaning up resources...")
        input_manager.close()
        discord.close()
        state_manager.flush()
        instance_server.close()
        shared_mem.detach()

    app.aboutToQuit.connect(cleanup)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
