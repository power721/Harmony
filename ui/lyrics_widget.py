from PySide6.QtWidgets import QListView, QStyledItemDelegate
from PySide6.QtCore import (
    Qt,
    QAbstractListModel,
    QModelIndex,
    QSize,
    QPropertyAnimation,
    Signal
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QBrush,
    QStaticText
)

import bisect


# =========================
# LyricsModel
# =========================

class LyricsModel(QAbstractListModel):

    NORMAL = 0
    EMPTY = 1
    ERROR = 2

    def __init__(self):
        super().__init__()
        self._lyrics = []
        self._state = self.EMPTY

    def set_lyrics(self, lyrics):

        self.beginResetModel()

        if lyrics is None:
            self._state = self.ERROR
            self._lyrics = []

        elif len(lyrics) == 0:
            self._state = self.EMPTY
            self._lyrics = []

        else:
            self._state = self.NORMAL
            self._lyrics = lyrics

            for l in self._lyrics:
                l.static_text = QStaticText(l.text)
                l.static_text.prepare()

        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):

        if self._state != self.NORMAL:
            return 1

        return len(self._lyrics)

    def data(self, index, role):

        if not index.isValid():
            return None

        if self._state == self.EMPTY:
            if role == Qt.DisplayRole:
                return "暂无歌词"
            return None

        if self._state == self.ERROR:
            if role == Qt.DisplayRole:
                return "歌词加载失败"
            return None

        line = self._lyrics[index.row()]

        if role == Qt.DisplayRole:
            return line.text

        if role == Qt.UserRole:
            return line.time

        if role == Qt.UserRole + 1:
            return line

        return None


# =========================
# Delegate
# =========================

class LyricsDelegate(QStyledItemDelegate):

    def __init__(self):

        super().__init__()

        self.active_row = -1
        self.progress = 0

        self.font_normal = QFont("Microsoft YaHei", 12)
        self.font_active = QFont("Microsoft YaHei", 16)
        self.font_active.setBold(True)

        self.font_hint = QFont("Microsoft YaHei", 13)

        self.color_normal = QColor("#777777")
        self.color_active = QColor("#ffffff")
        self.color_hint = QColor("#555555")

        self.karaoke_color = QColor("#1db954")

    def set_active_row(self, row):
        self.active_row = row

    def set_progress(self, p):
        self.progress = p

    def paint(self, painter, option, index):

        painter.save()

        rect = option.rect
        model = index.model()
        text = index.data(Qt.DisplayRole)

        if model._state != model.NORMAL:

            painter.setPen(self.color_hint)
            painter.setFont(self.font_hint)

            painter.drawText(
                rect,
                Qt.AlignCenter | Qt.TextWordWrap,
                text
            )

            painter.restore()
            return

        line = index.data(Qt.UserRole + 1)
        row = index.row()

        if row == self.active_row:

            painter.setFont(self.font_active)
            painter.setPen(self.color_active)

        else:

            painter.setFont(self.font_normal)
            painter.setPen(self.color_normal)

        draw_rect = rect.adjusted(30, 0, -30, 0)

        # 普通歌词
        if not line.words:

            painter.drawText(
                draw_rect,
                Qt.AlignCenter | Qt.TextWordWrap,
                line.text
            )

        else:
            # 逐字歌词

            fm = QFontMetrics(painter.font())

            x = draw_rect.left()
            y = draw_rect.center().y() + fm.ascent() / 2

            current_time = self.progress

            for start, dur, word in line.words:

                if current_time >= start + dur:
                    painter.setPen(self.karaoke_color)

                elif current_time >= start:
                    painter.setPen(self.karaoke_color)

                else:
                    painter.setPen(self.color_active)

                painter.drawText(x, y, word)

                x += fm.horizontalAdvance(word)

        painter.restore()

    def sizeHint(self, option, index):

        text = index.data(Qt.DisplayRole)

        fm = QFontMetrics(self.font_normal)

        width = option.rect.width() - 60

        if width <= 0:
            width = 400

        rect = fm.boundingRect(
            0,
            0,
            width,
            2000,
            Qt.TextWordWrap,
            text
        )

        return QSize(0, rect.height() + 18)


# =========================
# LyricsWidget
# =========================

class LyricsWidget(QListView):

    seekRequested = Signal(float)

    def __init__(self):

        super().__init__()

        self.setStyleSheet("""
        QListView{
            background:black;
            border:none;
        }
        """)

        self.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.setSelectionMode(QListView.NoSelection)
        self.setFocusPolicy(Qt.NoFocus)

        self.setSpacing(10)

        self.model_ = LyricsModel()
        self.delegate_ = LyricsDelegate()

        self.setModel(self.model_)
        self.setItemDelegate(self.delegate_)

        self._lyrics = []
        self._times = []
        self._current = -1

        self.anim = QPropertyAnimation(
            self.verticalScrollBar(),
            b"value"
        )

        self.anim.setDuration(300)

    # =========================
    # 设置歌词
    # =========================

    def set_lyrics(self, lyrics):

        if lyrics:

            self._lyrics = lyrics
            self._times = [l.time for l in lyrics]

        else:

            self._lyrics = []
            self._times = []

        self._current = -1

        self.model_.set_lyrics(lyrics)

    # =========================
    # 播放器同步
    # =========================

    def update_position(self, seconds):

        if not self._lyrics:
            return

        idx = self._find_index(seconds)

        if idx != self._current:

            self._current = idx
            self.delegate_.set_active_row(idx)

            self._smooth_scroll(idx)

        line = self._lyrics[idx]

        progress = seconds - line.time

        self.delegate_.set_progress(progress)

        self.viewport().update()

    # =========================
    # 二分查找
    # =========================

    def _find_index(self, seconds):

        pos = bisect.bisect_right(self._times, seconds) - 1

        if pos < 0:
            return 0

        if pos >= len(self._lyrics):
            return len(self._lyrics) - 1

        return pos

    # =========================
    # 平滑滚动
    # =========================

    def _smooth_scroll(self, index):

        rect = self.visualRect(
            self.model_.index(index)
        )

        center = self.viewport().height() / 2

        target = rect.center().y()

        scroll = self.verticalScrollBar().value() + target - center

        self.anim.stop()

        self.anim.setStartValue(
            self.verticalScrollBar().value()
        )

        self.anim.setEndValue(scroll)

        self.anim.start()

    # =========================
    # 点击跳转播放
    # =========================

    def mousePressEvent(self, event):

        index = self.indexAt(event.pos())

        if index.isValid():

            time = index.data(Qt.UserRole)

            self.seekRequested.emit(time)

        super().mousePressEvent(event)

    # =========================
    # 渐隐遮罩
    # =========================

    def paintEvent(self, event):

        super().paintEvent(event)

        painter = QPainter(self.viewport())

        h = self.viewport().height()

        gradient = QLinearGradient(0, 0, 0, h)

        gradient.setColorAt(0.0, QColor(0, 0, 0, 255))
        gradient.setColorAt(0.15, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.85, QColor(0, 0, 0, 0))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 255))

        painter.fillRect(
            self.viewport().rect(),
            QBrush(gradient)
        )