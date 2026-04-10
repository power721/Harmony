from types import SimpleNamespace

from ui.widgets.hover_effect_mixin import HoverEffectMixin


class _Target:
    def __init__(self):
        self.styles = []

    def setStyleSheet(self, style):
        self.styles.append(style)


class _Base:
    def __init__(self):
        self.enter_events = 0
        self.leave_events = 0

    def enterEvent(self, event):
        self.enter_events += 1

    def leaveEvent(self, event):
        self.leave_events += 1


class _HoverWidget(HoverEffectMixin, _Base):
    def __init__(self):
        super().__init__()
        self._is_hovering = False
        self.target = _Target()
        self._set_hover_target(self.target)
        theme = SimpleNamespace(background_hover="#202020", highlight="#1db954")
        self._style_normal, self._style_hover = self._build_hover_styles(theme, 8)
        self._apply_hover_style()


def test_hover_effect_mixin_applies_hover_and_normal_styles():
    widget = _HoverWidget()

    widget.enterEvent(object())
    widget.leaveEvent(object())

    assert widget.target.styles[0] == widget._style_normal
    assert widget.target.styles[1] == widget._style_hover
    assert widget.target.styles[2] == widget._style_normal
    assert widget.enter_events == 1
    assert widget.leave_events == 1
