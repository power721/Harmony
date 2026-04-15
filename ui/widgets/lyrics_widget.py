import re
from typing import List

from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget

from system.i18n import t
from utils.lrc_parser import LyricLine, LyricWord, detect_and_parse


# =============================
# LRC解析
# =============================

class LrcParser:
    TIME_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")

    @staticmethod
    def parse(lrc: str) -> List[LyricLine]:
        """
        解析LRC歌词文本，支持标准LRC格式、逐字歌词格式和YRC格式。

        使用统一的detect_and_parse函数来自动检测格式。
        """
        return detect_and_parse(lrc)


# =============================
# 歌词组件
# =============================

class LyricsWidget(QWidget):
    seekRequested = Signal(int)

    def __init__(self, parent=None):

        super().__init__(parent)

        self.lines: List[LyricLine] = []

        self.current_time = 0
        self.current_index = 0

        self.scroll_y = 0
        self.target_scroll = 0

        self.line_height = 44

        self.state = "no_lyrics"

        self.margin_x = 20

        self.font_normal = QFont()
        self.font_normal.setFamilies(["Noto Sans SC", "Inter"])
        self.font_normal.setPointSize(15)

        self.font_current = QFont()
        self.font_current.setFamilies(["Noto Sans SC", "Inter"])
        self.font_current.setPointSize(18)
        self.font_current.setBold(True)

        self.color_normal = QColor(150, 150, 150)
        self.color_current = QColor(255, 255, 255)

        self.hover_index = -1

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)

        self.setMouseTracking(True)

    # =============================
    # API
    # =============================

    def set_lyrics(self, lrc_text: str):

        self.lines = LrcParser.parse(lrc_text)

        if not self.lines:
            self.state = "no_lyrics"
            self.timer.stop()
        else:
            self.state = "lyrics"

        self.current_index = 0
        self.scroll_y = 0
        self.target_scroll = 0

        self.update()

    def set_error(self):

        self.state = "error"
        self.timer.stop()
        self.update()

    def update_position(self, seconds: float):

        self.current_time = seconds

        if not self.lines:
            return

        # Start timer if not already running
        if not self.timer.isActive():
            self.timer.start(16)

        # Handle reset to beginning (e.g., track loop)
        # When position jumps back significantly, reset to first line
        if seconds < self.lines[0].time and self.current_index > 0:
            self.current_index = 0
            self.scroll_y = 0
            self.target_scroll = 0
            return

        for i in range(len(self.lines) - 1):

            if self.lines[i].time <= seconds < self.lines[i + 1].time:

                if self.current_index != i:
                    self.current_index = i
                    self.target_scroll = i * self.line_height

                break

        if seconds >= self.lines[-1].time:
            self.current_index = len(self.lines) - 1
            self.target_scroll = self.current_index * self.line_height

    # =============================
    # 动画
    # =============================

    def _animate(self):

        diff = self.target_scroll - self.scroll_y

        if abs(diff) < 0.1:
            self.scroll_y = self.target_scroll
            self.timer.stop()
            return

        self.scroll_y += diff * 0.12

        self.update()

    # =============================
    # 绘制
    # =============================

    def paintEvent(self, e):

        p = QPainter(self)

        p.fillRect(self.rect(), QColor(0, 0, 0))

        if self.state == "no_lyrics":
            self._draw_center(p, t("no_lyrics"))
            return

        if self.state == "error":
            self._draw_center(p, t("lyrics_load_error"))
            return

        center_y = self.height() / 2

        for i, line in enumerate(self.lines):

            y = center_y + (i * self.line_height - self.scroll_y)

            if y < -60 or y > self.height() + 60:
                continue

            if i == self.current_index:

                p.setFont(self.font_current)
                p.setPen(self.color_current)

                progress = self._line_progress(i)

                # 传递逐字歌词数据
                self._draw_progress_text(p, line.text, y, progress, line.words)

            else:

                if i == self.hover_index:
                    p.setPen(QColor(220, 220, 220))
                else:
                    p.setPen(self.color_normal)

                p.setFont(self.font_normal)

                self._draw_text(p, line.text, y)

    # =============================
    # 行进度
    # =============================

    def _line_progress(self, i):

        if i >= len(self.lines) - 1:
            return 1

        start = self.lines[i].time
        end = self.lines[i + 1].time

        dur = end - start

        if dur <= 0:
            return 1

        return max(0, min(1, (self.current_time - start) / dur))

    # =============================
    # 绘制渐变高亮
    # =============================

    def _draw_progress_text(self, p, text, y, progress, words=None):
        """
        绘制当前行的进度高亮。

        如果有逐字歌词数据，使用逐字高亮；
        否则使用行级别的进度高亮。
        """
        # 如果有逐字歌词，使用逐字高亮
        if words:
            self._draw_word_progress(p, text, y, words)
            return

        # 否则使用行级别进度高亮
        metrics = QFontMetrics(self.font_current)

        text_width = metrics.horizontalAdvance(text)

        x = self.width() / 2 - text_width / 2

        base_rect = QRectF(x, y - 20, text_width, 40)

        p.setPen(self.color_normal)
        p.drawText(base_rect, Qt.AlignCenter, text)

        clip = QRectF(x, y - 20, text_width * progress, 40)

        p.save()

        p.setClipRect(clip)

        p.setPen(self.color_current)
        p.drawText(base_rect, Qt.AlignCenter, text)

        p.restore()

    def _draw_word_progress(self, p, text, y, words: List[LyricWord]):
        """
        绘制逐字高亮效果。

        根据当前时间，已唱的字显示高亮色，未唱的字显示普通色。
        """
        metrics = QFontMetrics(self.font_current)

        # 计算每个字的 x 位置
        char_positions = []
        current_x = self.width() / 2 - metrics.horizontalAdvance(text) / 2

        for word in words:
            char_width = metrics.horizontalAdvance(word.text)
            char_positions.append((current_x, char_width, word))
            current_x += char_width

        # 绘制每个字
        for x, char_width, word in char_positions:
            # 判断该字是否已唱
            word_end_time = word.time + word.duration

            if self.current_time >= word_end_time:
                # 已唱完 - 高亮色
                color = self.color_current
            elif self.current_time >= word.time:
                # 正在唱 - 渐变高亮
                progress = (self.current_time - word.time) / word.duration if word.duration > 0 else 1
                color = self._interpolate_color(self.color_normal, self.color_current, progress)
            else:
                # 未唱 - 普通色
                color = self.color_normal

            p.setPen(color)
            rect = QRectF(x, y - 20, char_width, 40)
            p.drawText(rect, Qt.AlignCenter, word.text)

    def _interpolate_color(self, color1: QColor, color2: QColor, t: float) -> QColor:
        """在两个颜色之间插值"""
        r = int(color1.red() + (color2.red() - color1.red()) * t)
        g = int(color1.green() + (color2.green() - color1.green()) * t)
        b = int(color1.blue() + (color2.blue() - color1.blue()) * t)
        return QColor(r, g, b)

    def _draw_text(self, p, text, y):

        rect = QRectF(
            self.margin_x,
            y - self.line_height / 2,
            self.width() - self.margin_x * 2,
            self.line_height
        )

        p.drawText(
            rect,
            Qt.AlignHCenter | Qt.AlignVCenter,
            text
        )

    def _draw_center(self, p, text):

        p.setPen(QColor(120, 120, 120))
        p.setFont(self.font_normal)

        p.drawText(
            self.rect(),
            Qt.AlignCenter,
            text
        )

    # =============================
    # 鼠标
    # =============================

    def mouseMoveEvent(self, e):

        if not self.lines:
            return

        center_y = self.height() / 2

        for i in range(len(self.lines)):

            y = center_y + (i * self.line_height - self.scroll_y)

            rect = QRectF(0, y - 20, self.width(), 40)

            if rect.contains(e.pos()):
                self.hover_index = i
                self.setCursor(Qt.CursorShape.PointingHandCursor)

                self.update()
                return

        self.hover_index = -1
        self.unsetCursor()

        self.update()

    def mousePressEvent(self, e):

        if e.button() == Qt.LeftButton and self.hover_index >= 0:
            t = self.lines[self.hover_index].time * 1000
            self.seekRequested.emit(int(t))

        super().mousePressEvent(e)
