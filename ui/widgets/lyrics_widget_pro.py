# lyrics_widget_pro.py
import sys
import bisect
from typing import List

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from system import t
from utils.lrc_parser import LyricLine, LyricWord, detect_and_parse, detect_format


# =========================================================
# 歌词引擎（高性能）
# =========================================================

class LyricsEngine:

    def __init__(self):
        self.lines: List[LyricLine] = []
        self.times: List[float] = []
        self.current_index = 0

    def set_lyrics(self, lines):
        self.lines = lines
        self.times = [l.time for l in lines]
        self.current_index = 0

    def update(self, time_sec):

        if not self.lines:
            return 0

        i = bisect.bisect_right(self.times, time_sec) - 1
        i = max(0, min(i, len(self.lines) - 1))

        self.current_index = i
        return i


# =========================================================
# 歌词 Widget
# =========================================================

class LyricsWidget(QWidget):

    seekRequested = Signal(int)

    def __init__(self, parent=None):

        super().__init__(parent)

        self.engine = LyricsEngine()

        self.current_time = 0
        self.current_index = 0

        self.scroll_y = 0
        self.target_scroll = 0

        self.line_height = 60

        self.gradient_shift = 0
        self.hover_index = -1

        self.margin_x = 40

        self.is_yrc = False
        self.is_qrc = False

        # 字体
        self.font_normal = QFont("Microsoft YaHei", 18)
        self.font_current = QFont("Microsoft YaHei", 26, QFont.Bold)

        # 颜色
        self.color_normal = QColor(150, 150, 150)
        self.color_current = QColor(255, 255, 255)

        # 动画
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(16)

        self.setMouseTracking(True)

    # =====================================================
    # API
    # =====================================================

    def set_lyrics(self, lrc_text):

        fmt = detect_format(lrc_text)
        self.is_qrc = (fmt == 'qrc')
        self.is_yrc = (fmt == 'yrc')

        lines = detect_and_parse(lrc_text)

        self.engine.set_lyrics(lines)

        self.scroll_y = 0
        self.target_scroll = 0

        self.update()

    def update_position(self, sec):

        self.current_time = sec

        index = self.engine.update(sec)

        if index != self.current_index:
            self.current_index = index
            self.target_scroll = index * self.line_height

    # =====================================================
    # 动画
    # =====================================================

    def _animate(self):

        diff = self.target_scroll - self.scroll_y
        self.scroll_y += diff * 0.12

        self.gradient_shift += 2
        if self.gradient_shift > self.width():
            self.gradient_shift = 0

        self.update()

    # =====================================================
    # 绘制
    # =====================================================

    def paintEvent(self, e):

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        p.fillRect(self.rect(), QColor(10, 10, 10))

        if self.is_qrc:
            self._draw_qrc_badge(p)
        elif self.is_yrc:
            self._draw_yrc_badge(p)

        lines = self.engine.lines

        if not lines:
            p.setPen(QColor(120, 120, 120))
            p.setFont(self.font_normal)
            p.drawText(self.rect(), Qt.AlignCenter, t("no_lyrics"))
            return

        center_y = self.height() / 2

        for i, line in enumerate(lines):

            y = center_y + (i * self.line_height - self.scroll_y)

            if y < -100 or y > self.height() + 100:
                continue

            if i == self.current_index:
                self._draw_current_line(p, line, y)
            else:
                self._draw_normal_line(p, line.text, y, i)

    # =====================================================
    # 标记
    # =====================================================

    def _draw_yrc_badge(self, p):
        p.setPen(QColor(100, 200, 255))
        p.setFont(QFont("Segoe UI Emoji", 12))
        p.drawText(self.width() - 30, 25, "🇾")

    def _draw_qrc_badge(self, p):
        p.setPen(QColor(255, 180, 100))
        p.setFont(QFont("Segoe UI Emoji", 12))
        p.drawText(self.width() - 30, 25, "🇶")

    # =====================================================
    # 普通行
    # =====================================================

    def _draw_normal_line(self, p, text, y, index):

        distance = abs(index - self.current_index)

        scale = max(0.7, 1 - distance * 0.15)
        opacity = max(0.3, 1 - distance * 0.25)

        font = QFont(self.font_normal)
        font.setPointSizeF(self.font_normal.pointSizeF() * scale)

        p.setOpacity(opacity)
        p.setFont(font)

        p.setPen(self.color_normal)

        rect = QRectF(self.margin_x, y - 30, self.width() - self.margin_x * 2, 60)
        p.drawText(rect, Qt.AlignCenter, text)

        p.setOpacity(1)

    # =====================================================
    # 当前行
    # =====================================================

    def _draw_current_line(self, p, line: LyricLine, y):

        words = line.words

        # ✅ fallback（关键）
        if not words or len(words) == 0:
            next_line = None
            if self.current_index < len(self.engine.lines) - 1:
                next_line = self.engine.lines[self.current_index + 1]

            words = self._build_fake_words(line, next_line)

        metrics = QFontMetrics(self.font_current)
        text = "".join(w.text for w in words)

        text_width = metrics.horizontalAdvance(text)
        x = self.width() / 2 - text_width / 2

        self._draw_word_by_word(p, words, x, y, metrics)

    def _build_fake_words(self, line, next_line):

        text = line.text

        units = list(text)

        start = line.time
        end = next_line.time if next_line else start + 3

        total = max(0.1, end - start)
        dur = total / max(len(units), 1)

        words = []
        t = start

        for u in units:
            words.append(LyricWord(t, dur, u))
            t += dur

        return words

    # =====================================================
    # 逐字渲染（核心）
    # =====================================================

    def _draw_word_by_word(self, p, words, x, y, metrics):

        p.setFont(self.font_current)

        total_width = max(1, self.width())
        cur_x = x

        for w in words:

            width = max(1, metrics.horizontalAdvance(w.text))

            start = w.time
            end = w.time + w.duration
            scale = 1.0
            if start <= self.current_time <= end:
                scale = 1.1

            # =========================
            # 1. 未开始
            # =========================
            if self.current_time < start:
                color = QColor(180, 180, 180)

            # =========================
            # 2. 已完成（扫光完成）
            # =========================
            elif self.current_time >= end:
                color = self._gradient_color(cur_x, total_width)

            # =========================
            # 3. 正在播放（扫光动画）
            # =========================
            else:
                progress = 0 if w.duration <= 0 else (self.current_time - start) / w.duration

                # 👉 扫光宽度
                sweep_width = width * progress
                font = QFont(self.font_current)
                font.setPointSizeF(self.font_current.pointSizeF() * scale)
                p.setFont(font)

                # 先画灰色底
                p.setPen(QColor(180, 180, 180))
                p.drawText(QRectF(cur_x, y - 30, width, 60), Qt.AlignCenter, w.text)

                # 再画“扫光层”
                clip_rect = QRectF(cur_x, y - 30, sweep_width, 60)

                p.save()
                p.setClipRect(clip_rect)

                color = self._gradient_color(cur_x, total_width)
                p.setPen(color)
                p.drawText(QRectF(cur_x, y - 30, width, 60), Qt.AlignCenter, w.text)

                p.restore()

                cur_x += width
                continue

            # 普通绘制
            p.setPen(color)
            p.drawText(QRectF(cur_x, y - 30, width, 60), Qt.AlignCenter, w.text)

            cur_x += width

    def _gradient_color(self, x, total_width):

        pos = (x + self.gradient_shift) % total_width
        ratio = pos / total_width

        colors = [
            QColor("#00F5FF"),
            QColor("#00C3FF"),
            QColor("#7A5CFF"),
            QColor("#FF4D9D"),
        ]

        idx = ratio * (len(colors) - 1)
        i = int(idx)
        t = idx - i

        if i >= len(colors) - 1:
            return colors[-1]

        return self._interpolate_color(colors[i], colors[i + 1], t)

    def _interpolate_color(self, c1, c2, t):
        r = int(c1.red() + (c2.red() - c1.red()) * t)
        g = int(c1.green() + (c2.green() - c1.green()) * t)
        b = int(c1.blue() + (c2.blue() - c1.blue()) * t)
        return QColor(r, g, b)


# =========================================================
# Demo
# =========================================================

demo_yrc = """
[1000,3000](0,500,0)青(500,500,0)花(1000,500,0)瓷(1500,500,0)瓷
[5000,4000](0,800,0)周(800,800,0)杰(1600,800,0)伦(2400,800,0)唱
"""


class DemoWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.resize(900, 600)

        layout = QVBoxLayout(self)

        self.lyrics = LyricsWidget()
        layout.addWidget(self.lyrics)

        self.lyrics.set_lyrics(demo_yrc)

        self.time = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(100)

    def tick(self):
        self.time += 0.1
        self.lyrics.update_position(self.time)


if __name__ == "__main__":

    app = QApplication(sys.argv)

    win = DemoWindow()
    win.show()

    sys.exit(app.exec())