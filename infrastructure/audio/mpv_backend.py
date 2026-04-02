"""mpv (python-mpv) implementation of AudioBackend."""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer, Signal

from .audio_backend import AudioBackend

logger = logging.getLogger(__name__)


class MpvAudioBackend(AudioBackend):
    """libmpv-backed audio engine via python-mpv."""

    STATE_STOPPED = 0
    STATE_PLAYING = 1
    STATE_PAUSED = 2

    _position_observed = Signal(object)
    _duration_observed = Signal(object)
    _pause_observed = Signal(object)
    _idle_observed = Signal(object)
    _eof_observed = Signal(object)

    FREQUENCY_BANDS = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000]

    def __init__(self, parent=None):
        super().__init__(parent)

        try:
            import mpv  # type: ignore
        except ImportError as exc:
            raise RuntimeError("python-mpv is not installed") from exc

        self._player = mpv.MPV(video=False, ytdl=False)
        self._source_path = ""
        self._last_state = self.STATE_STOPPED
        self._explicit_stop = False
        self._media_ready = False
        self._pending_seek_ms: int | None = None
        self._end_notified = False

        self._position_observed.connect(self._on_position_observed)
        self._duration_observed.connect(self._on_duration_observed)
        self._pause_observed.connect(self._on_pause_observed)
        self._idle_observed.connect(self._on_idle_observed)
        self._eof_observed.connect(self._on_eof_observed)

        self._observe_property("time-pos", self._position_observed)
        self._observe_property("duration", self._duration_observed)
        self._observe_property("pause", self._pause_observed)
        self._observe_property("idle-active", self._idle_observed)
        self._observe_property("eof-reached", self._eof_observed)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)
        self._poll_timer.timeout.connect(self._poll_position)

    def set_source(self, file_path: str):
        self._source_path = file_path or ""
        self._explicit_stop = False
        self._media_ready = False
        self._pending_seek_ms = None
        self._end_notified = False
        self._set_polling_enabled(False)
        self._player.command("loadfile", self._source_path, "replace", "pause=yes")

    def play(self):
        self._explicit_stop = False
        # At EOF mpv may stay idle; unpausing alone won't restart.
        if bool(self._safe_get_property("eof-reached", False)):
            self.seek(0)
        self._player.pause = False
        self._emit_state_if_changed()

    def pause(self):
        self._player.pause = True
        self._emit_state_if_changed()

    def stop(self):
        self._explicit_stop = True
        self._pending_seek_ms = None
        self._set_polling_enabled(False)
        self._player.command("stop")
        self._emit_state_if_changed(force=self.STATE_STOPPED)

    def seek(self, position_ms: int):
        safe_ms = max(0, int(position_ms))
        if not self._media_ready:
            self._pending_seek_ms = safe_ms
            return
        self._seek_now(safe_ms)

    def position(self) -> int:
        value = self._safe_get_property("time-pos", 0.0)
        return int(float(value or 0.0) * 1000)

    def duration(self) -> int:
        value = self._safe_get_property("duration", 0.0)
        return int(float(value or 0.0) * 1000)

    def is_playing(self) -> bool:
        return self._compute_state() == self.STATE_PLAYING

    def is_paused(self) -> bool:
        return self._compute_state() == self.STATE_PAUSED

    def get_source_path(self) -> str:
        return self._source_path

    def set_volume(self, volume: int):
        self._player.volume = max(0, min(100, int(volume)))

    def get_volume(self) -> int:
        value = self._safe_get_property("volume", 0)
        return int(float(value or 0))

    def set_eq_bands(self, bands: list[float]):
        if not self.supports_eq():
            return
        gains = [float(v) for v in bands]
        if len(gains) < len(self.FREQUENCY_BANDS):
            gains += [0.0] * (len(self.FREQUENCY_BANDS) - len(gains))
        gains = gains[:len(self.FREQUENCY_BANDS)]

        if all(abs(v) < 0.01 for v in gains):
            self._player.af = ""
            return

        filters = []
        for freq, gain in zip(self.FREQUENCY_BANDS, gains):
            filters.append(f"equalizer=f={freq}:width_type=o:w=1:g={gain:.2f}")
        self._player.af = ",".join(filters)

    def supports_eq(self) -> bool:
        return True

    def cleanup(self):
        self._set_polling_enabled(False)
        try:
            self._player.command("stop")
        except Exception:
            pass
        terminate = getattr(self._player, "terminate", None)
        if callable(terminate):
            try:
                terminate()
            except Exception:
                pass

    def _observe_property(self, prop: str, bridge_signal: Signal):
        def callback(*args):
            # python-mpv callback payload can vary by version.
            if len(args) >= 2:
                value = args[1]
            elif args:
                value = args[0]
            else:
                value = None
            bridge_signal.emit(value)

        self._player.observe_property(prop, callback)

    def _safe_get_property(self, prop: str, default):
        try:
            return getattr(self._player, prop)
        except Exception:
            return default

    def _compute_state(self) -> int:
        idle = bool(self._safe_get_property("idle-active", True))
        if idle:
            return self.STATE_STOPPED
        paused = bool(self._safe_get_property("pause", False))
        return self.STATE_PAUSED if paused else self.STATE_PLAYING

    def _emit_state_if_changed(self, force: int | None = None):
        state = force if force is not None else self._compute_state()
        if state != self._last_state:
            self._last_state = state
            self.state_changed.emit(state)

    def _set_polling_enabled(self, enabled: bool):
        if enabled:
            if not self._poll_timer.isActive():
                self._poll_timer.start()
            return

        if self._poll_timer.isActive():
            self._poll_timer.stop()

    def _poll_position(self):
        self.position_changed.emit(self.position())
        self._emit_state_if_changed()

    def _on_position_observed(self, value):
        if value is None:
            return
        try:
            self.position_changed.emit(int(float(value) * 1000))
        except (TypeError, ValueError):
            return

    def _on_duration_observed(self, value):
        if value is None:
            return
        try:
            self.duration_changed.emit(int(float(value) * 1000))
        except (TypeError, ValueError):
            return

    def _on_pause_observed(self, _value):
        self._emit_state_if_changed()

    def _on_idle_observed(self, value):
        is_idle = bool(value)
        if not is_idle and not self._media_ready:
            self._media_ready = True
            if self._pending_seek_ms is not None:
                self._seek_now(self._pending_seek_ms)
                self._pending_seek_ms = None
            self.media_loaded.emit()
        elif is_idle and self._media_ready and not self._explicit_stop:
            # Fallback for environments where eof-reached callback is unreliable.
            self._emit_end_of_media_once()
        self._set_polling_enabled(not is_idle)
        self._emit_state_if_changed()

    def _on_eof_observed(self, value):
        if bool(value) and not self._explicit_stop:
            self._emit_end_of_media_once()

    def _seek_now(self, position_ms: int):
        """Run a concrete seek command and absorb transient mpv errors."""
        sec = max(0, int(position_ms)) / 1000.0
        try:
            self._player.command("seek", sec, "absolute", "exact")
        except Exception as exc:
            logger.debug("[MpvAudioBackend] seek failed at %.3fs: %s", sec, exc)
            # Keep pending seek for a later retry (e.g. right after loadfile).
            self._pending_seek_ms = int(position_ms)

    def _emit_end_of_media_once(self):
        if self._end_notified:
            return
        self._end_notified = True
        self.end_of_media.emit()
