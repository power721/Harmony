import ui.dialogs.rounded_mask_debounce_mixin as mixin_module


class _FakeSignal:
    def __init__(self):
        self._callback = None

    def connect(self, callback):
        self._callback = callback

    def emit(self):
        if self._callback:
            self._callback()


class _FakeTimer:
    def __init__(self, _parent=None):
        self.timeout = _FakeSignal()
        self.single_shot = False
        self.started_with = []

    def setSingleShot(self, enabled):
        self.single_shot = enabled

    def start(self, interval):
        self.started_with.append(interval)


class _Base:
    def __init__(self):
        self.resize_calls = 0

    def resizeEvent(self, _event):
        self.resize_calls += 1


class _Widget(mixin_module.RoundedMaskDebounceMixin, _Base):
    def __init__(self):
        super().__init__()
        self.mask_calls = 0

    def _apply_rounded_mask(self):
        self.mask_calls += 1


def test_rounded_mask_debounce_mixin_schedules_mask_update(monkeypatch):
    monkeypatch.setattr(mixin_module, "QTimer", _FakeTimer)

    widget = _Widget()
    widget.resizeEvent(object())
    widget.resizeEvent(object())

    assert widget.resize_calls == 2
    assert widget._rounded_mask_timer.single_shot is True
    assert widget._rounded_mask_timer.started_with == [100, 100]
    assert widget.mask_calls == 0

    widget._rounded_mask_timer.timeout.emit()
    assert widget.mask_calls == 1
