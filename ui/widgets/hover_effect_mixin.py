"""Reusable hover-style behavior for card-like widgets."""


class HoverEffectMixin:
    """Apply hover/normal styles to a target widget and keep hover state in sync."""

    _is_hovering: bool
    _style_normal: str
    _style_hover: str

    def _set_hover_target(self, target) -> None:
        self._hover_target = target

    def _build_hover_styles(self, theme, radius: int) -> tuple[str, str]:
        normal = (
            f"QFrame {{ background-color: {theme.background_hover}; border-radius: {radius}px; }}"
        )
        hover = (
            f"QFrame {{ background-color: {theme.background_hover}; border-radius: {radius}px; "
            f"border: 2px solid {theme.highlight}; }}"
        )
        return normal, hover

    def _apply_hover_style(self) -> None:
        target = getattr(self, "_hover_target", None)
        if target is None:
            return
        target.setStyleSheet(self._style_hover if self._is_hovering else self._style_normal)

    def enterEvent(self, event):
        self._is_hovering = True
        self._apply_hover_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovering = False
        self._apply_hover_style()
        super().leaveEvent(event)
