import re
from typing import List

from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget

from system.i18n import t
from utils.lrc_parser import LyricLine, parse_lrc


# =============================
# LRC解析
# =============================

class LrcParser:

    TIME_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")

    @staticmethod
    def parse(lrc: str) -> List[LyricLine]:
        """
        解析LRC歌词文本，支持标准LRC格式和逐字歌词格式。

        使用统一的parse_lrc函数来处理所有格式。
        """
        # 使用改进的parse_lrc函数，支持所有格式
        return parse_lrc(lrc)


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

        self.font_normal = QFont("Microsoft YaHei", 15)
        self.font_current = QFont("Microsoft YaHei", 18, QFont.Bold)

        self.color_normal = QColor(150, 150, 150)
        self.color_current = QColor(255, 255, 255)

        self.hover_index = -1

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(16)

        self.setMouseTracking(True)

    # =============================
    # API
    # =============================

    def set_lyrics(self, lrc_text: str):

        self.lines = LrcParser.parse(lrc_text)

        if not self.lines:
            self.state = "no_lyrics"
        else:
            self.state = "lyrics"

        self.current_index = 0
        self.scroll_y = 0
        self.target_scroll = 0

        self.update()

    def set_error(self):

        self.state = "error"
        self.update()

    def update_position(self, seconds: float):

        self.current_time = seconds

        if not self.lines:
            return

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

                self._draw_progress_text(p, line.text, y, progress)

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

    def _draw_progress_text(self, p, text, y, progress):

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
                self.setCursor(Qt.PointingHandCursor)

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