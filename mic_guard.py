"""Automatic mic rules on top of Discord's voice state: join calls muted, mute
a mic left open in silence, and the hotkey's tap/hold behaviour."""

import time
import logging

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

import constants

logger = logging.getLogger("livedot.guard")


class MicGuard(QObject):
    auto_muted = pyqtSignal()   # a mic left open in silence was just muted

    def __init__(self, state_manager, discord):
        super().__init__()
        self.state_manager = state_manager
        self.discord = discord
        self._press_time = None
        self._press_voice = None  # (mute, deaf) when the hotkey went down

        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle)

        discord.call_joined.connect(self._on_call_joined)
        discord.speaking_changed.connect(lambda _: self._watch_idle(restart=True))
        discord.voice_changed.connect(lambda *_: self._watch_idle())
        discord.call_changed.connect(lambda _: self._watch_idle())
        discord.connection_changed.connect(lambda _: self._watch_idle())
        state_manager.config_saved.connect(self._watch_idle)

    # Join muted
    def _on_call_joined(self):
        d = self.discord
        if self.state_manager.config["join_muted"] and not (d.mute or d.deaf):
            logger.info("Joined a voice channel with the mic open: muting.")
            d.set_voice(True, False)

    # Forgotten open mic
    def _watch_idle(self, restart=False):
        """Counts down while the mic is open in a call and nothing is being
        transmitted. Silence starts over whenever the user stops talking."""
        d = self.discord
        minutes = self.state_manager.config["idle_mute_minutes"]
        if not (minutes > 0 and d.ready and d.in_call
                and not (d.mute or d.deaf) and not d.speaking):
            self._idle_timer.stop()
            return
        interval = minutes * 60_000
        if restart or not self._idle_timer.isActive() or self._idle_timer.interval() != interval:
            self._idle_timer.start(interval)

    def _on_idle(self):
        d = self.discord
        if d.ready and d.in_call and not (d.mute or d.deaf) and not d.speaking:
            logger.info("Mic open without speaking for too long: muting.")
            d.set_voice(True, False)
            self.auto_muted.emit()

    # Hotkey: a tap flips the mic, a hold flips it only while held
    @pyqtSlot()
    def hotkey_pressed(self):
        d = self.discord
        self._press_time = time.monotonic()
        self._press_voice = (d.mute, d.deaf) if d.ready else None
        d.toggle_mute()

    @pyqtSlot()
    def hotkey_released(self):
        if self._press_time is None:
            return
        held_ms = (time.monotonic() - self._press_time) * 1000
        voice, self._press_voice, self._press_time = self._press_voice, None, None
        if voice is not None and held_ms >= constants.HOLD_THRESHOLD_MS:
            logger.info(f"Hotkey held for {held_ms:.0f} ms: restoring the previous mic state.")
            self.discord.set_voice(*voice)
