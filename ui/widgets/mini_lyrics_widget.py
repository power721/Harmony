from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QFont
from PySide6.QtWidgets import QWidget


class MiniLyricsWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        from utils.lrc_parser import detect_and_parse
        self.detect_and_parse = detect_and_parse

        self.lines = []
        self.current_time = 0
        self.current_index = 0

        # 字体（固定像素，避免DPI坑）
        self.font = QFont()
        self.font.setFamilies(["Noto Sans SC", "Inter"])
        self.font.setPixelSize(12)

        # 滚动系统（高级版）
        self.scroll_x = 0
        self.target_scroll_x = 0
        self.velocity = 0  # 惯性

        self.max_scroll_x = 0
        self.pause_timer = 0  # 行切换停顿

        # 动效
        self.gradient_shift = 0

        self.setFixedHeight(24)
        self.setMinimumWidth(150)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

        self._last_line_index = -1

    # =====================================================
    # API
    # =====================================================

    def set_lyrics(self, text):
        self.lines = self.detect_and_parse(text)
        self.current_index = 0
        self.scroll_x = 0
        self.target_scroll_x = 0

    def update_position(self, t):
        self.current_time = t

        if not self.lines:
            return

        for i in range(len(self.lines) - 1):
            if self.lines[i].time <= t < self.lines[i + 1].time:
                self.current_index = i
                return

        # Last line: if time >= last line's time
        if t >= self.lines[-1].time:
            self.current_index = len(self.lines) - 1

    # =====================================================
    # 动画核心（高级滚动）
    # =====================================================

    def _tick(self):

        # 行切换检测 → 停顿
        if self.current_index != self._last_line_index:
            self.pause_timer = 8  # ≈ 120ms 停顿
            self._last_line_index = self.current_index

        # 👉 停顿阶段（网易云那种“稳一下”）
        if self.pause_timer > 0:
            self.pause_timer -= 1
        else:
            # 👉 惯性滚动（核心）
            diff = self.target_scroll_x - self.scroll_x

            # 弹簧 + 阻尼
            self.velocity += diff * 0.08
            self.velocity *= 0.75

            self.scroll_x += self.velocity

        # 渐变动画
        self.gradient_shift += 2

        self.update()

    # =====================================================
    # 绘制
    # =====================================================

    def paintEvent(self, e):

        if not self.lines:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)

        line = self.lines[self.current_index]

        p.setFont(self.font)
        fm = QFontMetrics(self.font)

        full_width = fm.horizontalAdvance(line.text)

        # 👉 是否需要滚动
        if full_width > self.width():
            self.max_scroll_x = full_width - self.width()
        else:
            self.max_scroll_x = 0

        words = line.words

        # fallback（普通LRC）
        if not words:
            p.setPen(QColor(220, 220, 220))
            p.drawText(self.rect(), Qt.AlignVCenter | Qt.AlignLeft, line.text)
            return

        # =====================================================
        # 🎯 核心：根据当前唱到位置 → 计算滚动目标
        # =====================================================

        current_x = 0
        for w in words:
            w_width = fm.horizontalAdvance(w.text)

            if self.current_time >= w.time:
                current_x += w_width
            else:
                break

        # 👉 居中偏左（网易云风格）
        self.target_scroll_x = max(0, min(
            current_x - self.width() * 0.35,
            self.max_scroll_x
        ))

        # =====================================================
        # 🎯 绘制（带滚动）
        # =====================================================

        x = -self.scroll_x

        for w in words:

            w_width = fm.horizontalAdvance(w.text)

            if self.current_time >= w.time + w.duration:
                color = self._gradient(x)

            elif self.current_time >= w.time:
                progress = (self.current_time - w.time) / w.duration if w.duration else 1

                # 灰底
                p.setPen(QColor(200, 200, 200))
                p.drawText(QRectF(x, 0, w_width, self.height()),
                           Qt.AlignVCenter, w.text)

                # 高亮覆盖
                p.save()
                p.setClipRect(QRectF(x, 0, w_width * progress, self.height()))
                p.setPen(self._gradient(x))
                p.drawText(QRectF(x, 0, w_width, self.height()),
                           Qt.AlignVCenter, w.text)
                p.restore()

                x += w_width
                continue
            else:
                color = QColor(200, 200, 200)

            p.setPen(color)
            p.drawText(QRectF(x, 0, w_width, self.height()),
                       Qt.AlignVCenter, w.text)

            x += w_width

    # =====================================================
    # 渐变色
    # =====================================================

    def _gradient(self, x):

        colors = [
            QColor("#00F5FF"),
            QColor("#7A5CFF"),
            QColor("#FF4D9D"),
        ]

        t = (x + self.gradient_shift) % self.width() / self.width()

        i = int(t * (len(colors) - 1))
        c1 = colors[i]
        c2 = colors[min(i + 1, len(colors) - 1)]

        t2 = t * (len(colors) - 1) - i

        return QColor(
            int(c1.red() + (c2.red() - c1.red()) * t2),
            int(c1.green() + (c2.green() - c1.green()) * t2),
            int(c1.blue() + (c2.blue() - c1.blue()) * t2),
        )
