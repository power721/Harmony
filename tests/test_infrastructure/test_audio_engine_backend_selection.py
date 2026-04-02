"""Tests for backend selection and fallback policy in PlayerEngine."""

from __future__ import annotations

import types

import pytest

from infrastructure.audio import audio_engine


def test_create_backend_falls_back_to_qt_when_enabled(monkeypatch):
    class _BrokenMpvBackend:
        def __init__(self, parent=None):
            raise RuntimeError("mpv unavailable")

    class _FakeQtBackend:
        def __init__(self, parent=None):
            self.parent = parent

    fake_qt_module = types.SimpleNamespace(QtAudioBackend=_FakeQtBackend)

    monkeypatch.setenv("HARMONY_ENABLE_QT_FALLBACK", "1")
    monkeypatch.setattr(audio_engine, "MpvAudioBackend", _BrokenMpvBackend)
    monkeypatch.setattr(
        audio_engine.importlib,
        "import_module",
        lambda name: fake_qt_module if name == "infrastructure.audio.qt_backend" else None,
    )

    engine = audio_engine.PlayerEngine.__new__(audio_engine.PlayerEngine)
    backend = audio_engine.PlayerEngine._create_backend(
        engine, audio_engine.PlayerEngine.BACKEND_MPV
    )

    assert isinstance(backend, _FakeQtBackend)
    assert backend.parent is engine


def test_create_backend_raises_when_qt_fallback_disabled(monkeypatch):
    class _BrokenMpvBackend:
        def __init__(self, parent=None):
            raise RuntimeError("mpv unavailable")

    monkeypatch.setenv("HARMONY_ENABLE_QT_FALLBACK", "0")
    monkeypatch.setattr(audio_engine, "MpvAudioBackend", _BrokenMpvBackend)

    engine = audio_engine.PlayerEngine.__new__(audio_engine.PlayerEngine)
    with pytest.raises(RuntimeError, match="Qt fallback is disabled"):
        audio_engine.PlayerEngine._create_backend(engine, audio_engine.PlayerEngine.BACKEND_MPV)
