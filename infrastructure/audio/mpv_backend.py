"""mpv (python-mpv) implementation of AudioBackend."""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer, Signal

from .audio_backend import AudioBackend, AudioEffectsState, AudioEffectCapabilities

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
        self._effects_state = AudioEffectsState(
            enabled=True,
            eq_bands=[0.0] * len(self.FREQUENCY_BANDS),
        )

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

        self._visualizer_mode = "spectrum"
        self._visualizer_timer = QTimer(self)
        self._visualizer_timer.setInterval(33)
        self._visualizer_timer.timeout.connect(self._emit_visualizer_frame)

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
        self._set_visualizer_enabled(False)
        self._player.command("stop")
        self._emit_state_if_changed(force=self.STATE_STOPPED)

    def seek(self, position_ms: int):
        safe_ms = max(0, int(position_ms))
        if not self._media_ready and self._can_seek_without_media_loaded():
            self._media_ready = True
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
        self._effects_state.eq_bands = gains[:len(self.FREQUENCY_BANDS)]
        self._rebuild_audio_filter_chain()

    def supports_eq(self) -> bool:
        return True

    def set_audio_effects(self, effects: AudioEffectsState):
        self._effects_state.enabled = bool(effects.enabled)
        self._effects_state.bass_boost = self._clamp_effect(effects.bass_boost)
        self._effects_state.treble_boost = self._clamp_effect(effects.treble_boost)
        self._effects_state.reverb_level = self._clamp_effect(effects.reverb_level)
        self._effects_state.stereo_enhance = self._clamp_effect(effects.stereo_enhance)
        if effects.eq_bands:
            gains = [float(v) for v in effects.eq_bands]
            if len(gains) < len(self.FREQUENCY_BANDS):
                gains += [0.0] * (len(self.FREQUENCY_BANDS) - len(gains))
            self._effects_state.eq_bands = gains[:len(self.FREQUENCY_BANDS)]
        self._rebuild_audio_filter_chain()

    def supports_audio_effects(self) -> bool:
        return True

    def supports_visualizer(self) -> bool:
        return True

    def get_audio_effect_capabilities(self) -> AudioEffectCapabilities:
        return AudioEffectCapabilities.all_supported()

    def cleanup(self):
        self._set_polling_enabled(False)
        self._set_visualizer_enabled(False)
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

    def _can_seek_without_media_loaded(self) -> bool:
        """
        Best-effort readiness check when media_loaded signal is delayed/missed.

        Some mpv environments can report valid timeline properties while
        `media_loaded`/idle transition callback is not observed in time.
        """
        try:
            if not bool(self._safe_get_property("idle-active", True)):
                return True
            if float(self._safe_get_property("duration", 0.0) or 0.0) > 0:
                return True
            if float(self._safe_get_property("time-pos", 0.0) or 0.0) > 0:
                return True
        except Exception:
            return False
        return False

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

    def _set_visualizer_enabled(self, enabled: bool):
        if enabled:
            if not self._visualizer_timer.isActive():
                self._visualizer_timer.start()
            return

        if self._visualizer_timer.isActive():
            self._visualizer_timer.stop()

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
        self._set_visualizer_enabled(not is_idle)
        self._emit_state_if_changed()

    def _on_eof_observed(self, value):
        if bool(value) and not self._explicit_stop:
            self._emit_end_of_media_once()

    def _seek_now(self, position_ms: int):
        """Run a concrete seek command and absorb transient mpv errors."""
        sec = max(0, int(position_ms)) / 1000.0
        try:
            # mpv seek flags are passed as a single token (e.g. "absolute+exact").
            self._player.command("seek", sec, "absolute+exact")
        except Exception as exc:
            logger.debug("[MpvAudioBackend] exact seek failed at %.3fs: %s", sec, exc)
            try:
                # Fallback for mpv builds that reject exact flag.
                self._player.command("seek", sec, "absolute")
            except Exception as fallback_exc:
                logger.debug("[MpvAudioBackend] absolute seek failed at %.3fs: %s", sec, fallback_exc)
                # Keep pending seek for a later retry (e.g. right after loadfile).
                self._pending_seek_ms = int(position_ms)

    def _emit_end_of_media_once(self):
        if self._end_notified:
            return
        self._end_notified = True
        self.end_of_media.emit()

    def _emit_visualizer_frame(self):
        if not self._visualizer_timer.isActive():
            return
        position_ms = max(0, self.position())
        if self._visualizer_mode == "waveform":
            samples = self._build_waveform_samples(position_ms)
            frame = {"mode": "waveform", "samples": samples, "timestamp_ms": position_ms}
        else:
            bins = self._build_spectrum_bins(position_ms)
            frame = {"mode": "spectrum", "bins": bins, "timestamp_ms": position_ms}
        self.visualizer_frame.emit(frame)

    def _build_spectrum_bins(self, position_ms: int) -> list[float]:
        phase = (position_ms % 2000) / 2000.0
        bins: list[float] = []
        for i in range(24):
            value = abs((i / 24.0) - phase)
            bins.append(max(0.0, min(1.0, 1.0 - value)))
        return bins

    def _build_waveform_samples(self, position_ms: int) -> list[float]:
        phase = (position_ms % 1000) / 1000.0
        samples: list[float] = []
        for i in range(64):
            progress = i / 63.0
            amplitude = (progress * 2.0) - 1.0
            samples.append(amplitude * (1.0 - phase))
        return samples

    @staticmethod
    def _clamp_effect(value: float) -> float:
        try:
            as_float = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(100.0, as_float))

    def _rebuild_audio_filter_chain(self):
        if not self._effects_state.enabled:
            self._player.af = ""
            return

        filters: list[str] = []

        gains = [float(v) for v in self._effects_state.eq_bands]
        if len(gains) < len(self.FREQUENCY_BANDS):
            gains += [0.0] * (len(self.FREQUENCY_BANDS) - len(gains))
        gains = gains[:len(self.FREQUENCY_BANDS)]
        if any(abs(v) >= 0.01 for v in gains):
            for freq, gain in zip(self.FREQUENCY_BANDS, gains):
                filters.append(f"equalizer=f={freq}:width_type=o:w=1:g={gain:.2f}")

        bass_gain = self._effects_state.bass_boost * 0.12
        if bass_gain >= 0.01:
            filters.append(f"equalizer=f=100:width_type=o:w=2:g={bass_gain:.2f}")

        treble_gain = self._effects_state.treble_boost * 0.12
        if treble_gain >= 0.01:
            filters.append(f"equalizer=f=10000:width_type=o:w=1:g={treble_gain:.2f}")

        reverb_level = self._effects_state.reverb_level
        if reverb_level >= 0.01:
            delay_ms = 40 + reverb_level * 2.6
            decay = 0.05 + reverb_level * 0.008
            filters.append(f"lavfi=[aecho=0.8:0.88:{delay_ms:.0f}:{decay:.2f}]")

        stereo_level = self._effects_state.stereo_enhance
        if stereo_level >= 0.01:
            width = 1.0 + stereo_level * 0.015
            filters.append(f"lavfi=[extrastereo={width:.2f}]")

        self._player.af = ",".join(filters)
