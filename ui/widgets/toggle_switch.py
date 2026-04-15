import sys

from PySide6.QtCore import Qt, Property, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget, QSizePolicy, QGraphicsDropShadowEffect, QApplication

from system.theme import ThemeManager


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)

        # ✅ 自适应布局
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(22)
        self.setMinimumWidth(46)

        # 状态
        self._checked = checked
        self._circle_pos = 0

        # 动画
        self.anim = QPropertyAnimation(self, b"circle_pos", self)
        self.anim.setDuration(180)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

        # 主题
        self.bg_on = QColor(ThemeManager.instance().current_theme.highlight)
        self.bg_off = QColor("#3f3f46")
        self.bg_disabled = QColor("#2a2a2a")
        self.circle_color = QColor("#ffffff")

        # 阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ========= Property =========
    def get_circle_pos(self):
        return self._circle_pos

    def set_circle_pos(self, pos):
        self._circle_pos = pos
        self.update()

    circle_pos = Property(float, get_circle_pos, set_circle_pos)

    # ========= 状态 =========
    def isChecked(self):
        return self._checked

    def setChecked(self, checked, animate=True):
        if self._checked == checked:
            return

        self._checked = checked

        end_pos = self._end_pos()

        if animate:
            self.anim.stop()
            self.anim.setStartValue(self._circle_pos)
            self.anim.setEndValue(end_pos)
            self.anim.start()
        else:
            self._circle_pos = end_pos
            self.update()

        self.toggled.emit(self._checked)

    def toggle(self):
        self.setChecked(not self._checked)

    # ========= 位置计算 =========
    def margin(self):
        # 根据高度动态计算边距
        return max(2, int(self.height() * 0.13))

    def diameter(self):
        return self.height() - self.margin() * 2

    def _end_pos(self):
        return self.width() - self.diameter() - self.margin() if self._checked else self.margin()

    # ========= 点击事件 =========
    def mousePressEvent(self, event):
        if not self.isEnabled():
            return
        if event.button() == Qt.LeftButton:
            self.toggle()

    # ========= Resize 自动修正 =========
    def resizeEvent(self, event):
        # 保证尺寸变化时滑块位置正确
        if self._checked:
            self._circle_pos = self._end_pos()
        else:
            self._circle_pos = self._end_pos()

    # ========= 绘制 =========
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        m = self.margin()
        d = self.diameter()

        # 背景
        if not self.isEnabled():
            bg_color = self.bg_disabled
        else:
            bg_color = self.bg_on if self._checked else self.bg_off

        painter.setBrush(bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), self.height() / 2, self.height() / 2)

        # 滑块阴影（轻微模拟）
        painter.setBrush(QColor(0, 0, 0, 30))
        painter.drawEllipse(int(self._circle_pos), m + 1, d, d)

        # 滑块
        painter.setBrush(self.circle_color)
        painter.drawEllipse(int(self._circle_pos), m, d, d)


# ========= Demo =========
if __name__ == "__main__":
    app = QApplication(sys.argv)
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    w = QWidget()
    w.resize(300, 150)
    layout = QVBoxLayout(w)

    toggle1 = ToggleSwitch(True)
    toggle2 = ToggleSwitch(False)
    toggle3 = ToggleSwitch(True)

    layout.addWidget(toggle1)
    layout.addWidget(toggle2)
    layout.addWidget(toggle3)

    w.show()
    sys.exit(app.exec())
