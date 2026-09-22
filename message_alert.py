"""Unread-message badge state.

Discord's RPC reports the notifications it shows but never when a message is
read, so "unread" here means "notified since the user last looked at
Discord": the badge clears when Discord's window comes to the front.
"""

import math
import logging

from PyQt6.QtCore import QObject, QTimer, QDateTime, pyqtSignal

import constants
import focus

logger = logging.getLogger("livedot.alert")


class MessageAlert(QObject):
    changed = pyqtSignal()   # badge appeared, changed or cleared
    popped = pyqtSignal()    # badge started its pop animation

    def __init__(self, discord):
        super().__init__()
        self.discord = discord
        self.count = 0
        self.direct = False      # any DM or mention among them
        self.last_title = ""     # Discord's notification title, e.g. "Name (#channel, Server)"
        self.last_channel = ""
        self.pop_start = None
        self.pop_from = 0.0      # badge scale the pop starts at

        self._focus_timer = QTimer(self)
        self._focus_timer.setInterval(constants.FOCUS_POLL_MS)
        self._focus_timer.timeout.connect(self._check_focus)

        self._remind_timer = QTimer(self)
        self._remind_timer.setSingleShot(True)
        self._remind_timer.timeout.connect(self._remind)

        discord.notified.connect(self._on_notified)
        discord.connection_changed.connect(lambda connected: connected or self.clear())

    @property
    def visible(self):
        return self.count > 0

    def tooltip(self):
        if not self.visible:
            return ""
        more = f"\n+{self.count - 1} outras" if self.count > 1 else ""
        return f"{self.last_title or 'Nova mensagem'}{more}"

    def pop_scale(self):
        """Badge size multiplier: overshoots, then settles at 1."""
        if not self.is_popping():
            return 1.0
        t = (QDateTime.currentMSecsSinceEpoch() - self.pop_start) / constants.BADGE_POP_MS
        peak = constants.BADGE_POP_PEAK
        if t < 0.4:
            return self.pop_from + (peak - self.pop_from) * math.sin(t / 0.4 * math.pi / 2)
        u = (t - 0.4) / 0.6
        return peak - (peak - 1.0) * u * u * (3.0 - 2.0 * u)

    def is_popping(self):
        return (self.pop_start is not None and
                QDateTime.currentMSecsSinceEpoch() - self.pop_start < constants.BADGE_POP_MS)

    def open(self):
        """Takes the user to the channel of the latest message."""
        if self.last_channel:
            self.discord.select_text_channel(self.last_channel)
        focus.raise_discord()
        self.clear()

    def clear(self):
        if not self.visible:
            return
        logger.info("Unread badge cleared.")
        self.count = 0
        self.direct = False
        self.last_title = ""
        self.last_channel = ""
        self._focus_timer.stop()
        self._remind_timer.stop()
        self.changed.emit()

    def _on_notified(self, channel_id, title, direct):
        if focus.discord_focused():
            logger.info("Notification ignored: Discord is in front.")
            return
        first = not self.visible
        upgraded = direct and not self.direct
        self.count += 1
        self.direct = self.direct or direct
        self.last_title = title
        self.last_channel = channel_id
        if first:
            self._focus_timer.start()
            self._remind_timer.start(constants.MESSAGE_REMIND_AFTER_MS)
        # Pop only when the badge appears or turns solid; one per message
        # would keep a busy channel twitching all day.
        if first or upgraded:
            self._pop(grow=first)
        logger.info(f"Unread badge: {self.count} notification(s), direct: {self.direct}")
        self.changed.emit()

    def _check_focus(self):
        if focus.discord_focused():
            self.clear()

    def _remind(self):
        self._pop()
        self._remind_timer.start(constants.MESSAGE_REMIND_EVERY_MS)

    def _pop(self, grow=False):
        """Swells the badge once; ``grow`` starts it from nothing."""
        self.pop_start = QDateTime.currentMSecsSinceEpoch()
        self.pop_from = 0.0 if grow else 1.0
        self.popped.emit()
