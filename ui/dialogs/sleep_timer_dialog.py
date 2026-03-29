import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QRadioButton, QButtonGroup, QSpinBox, QComboBox,
    QCheckBox, QPushButton, QWidget, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QColor, QPainterPath, QRegion, QKeySequence

from services.playback.sleep_timer_service import SleepTimerConfig
from system.theme import ThemeManager
from system.i18n import t

logger = logging.getLogger(__name__)

class SleepTimerDialog(QDialog):
    """生产级 Sleep Timer 对话框，支持随时打开显示当前计时状态，高 DPI，快捷键，优化 QTimer"""

    def __init__(self, sleep_timer_service, parent=None):
        super().__init__(parent)
        self._sleep_timer = sleep_timer_service
        self._drag_pos = None

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._apply_styles()
        self._update_display()
        self._register_theme()

        # 如果计时器已经在运行，显示状态
        if self._sleep_timer.is_active:
            self._on_timer_started()

    # ----------------------- 窗口 & 阴影 -----------------------
    def _setup_window(self):
        self.setWindowTitle(t("sleep_timer"))
        self.setModal(True)
        self.setFixedSize(520, 450)  # 宽度加大
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        # 高 DPI 居中
        self._center_on_screen()

    def _center_on_screen(self):
        """自动居中对话框，支持多屏幕和高 DPI"""
        screen = self.screen() or self.window().windowHandle().screen()
        if not screen:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    def _register_theme(self):
        ThemeManager.instance().register_widget(self)

    # ----------------------- UI 构建 -----------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._container = QWidget(self)
        self._container.setObjectName("dialogContainer")
        self._container.setGeometry(0, 0, 400, 450)
        layout.addWidget(self._container)

        self._main_layout = QVBoxLayout(self._container)
        self._main_layout.setSpacing(16)
        self._main_layout.setContentsMargins(24, 24, 24, 24)

        self._add_title()
        self._add_mode_selection()
        self._add_time_inputs()
        self._add_track_inputs()
        self._add_action_selection()
        self._add_fade_option()
        self._add_status_label()
        self._add_buttons()

        # QTimer 更新显示
        self._display_timer = QTimer(self)
        self._display_timer.timeout.connect(self._update_display)

    def _add_title(self):
        title = QLabel(t("sleep_timer_title"))
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignCenter)
        self._main_layout.addWidget(title)

    def _add_mode_selection(self):
        self._time_radio = QRadioButton(t("countdown_mode"))
        self._track_radio = QRadioButton(t("track_count_mode"))
        self._time_radio.setChecked(True)

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._time_radio, 0)
        self._mode_group.addButton(self._track_radio, 1)

        group_widget = QWidget()
        vlayout = QVBoxLayout(group_widget)
        vlayout.setSpacing(8)
        vlayout.addWidget(self._time_radio)
        vlayout.addWidget(self._track_radio)

        self._main_layout.addWidget(group_widget)

    def _add_time_inputs(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 0, 0, 0)

        layout.addWidget(QLabel(t("countdown")))
        self._hours_spin = QSpinBox()
        self._hours_spin.setRange(0, 23)
        self._hours_spin.setSuffix(t("hours"))
        layout.addWidget(self._hours_spin)

        self._minutes_spin = QSpinBox()
        self._minutes_spin.setRange(0, 59)
        self._minutes_spin.setValue(30)
        self._minutes_spin.setSuffix(t("minutes"))
        layout.addWidget(self._minutes_spin)

        self._seconds_spin = QSpinBox()
        self._seconds_spin.setRange(0, 59)
        self._seconds_spin.setSuffix(t("seconds"))
        layout.addWidget(self._seconds_spin)

        layout.addStretch()
        self._main_layout.addWidget(widget)

    def _add_track_inputs(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 0, 0, 0)

        layout.addWidget(QLabel(t("track_count")))
        self._track_spin = QSpinBox()
        self._track_spin.setRange(1, 999)
        self._track_spin.setValue(5)
        self._track_spin.setSuffix(t("tracks"))
        layout.addWidget(self._track_spin)
        layout.addStretch()
        self._main_layout.addWidget(widget)

    def _add_action_selection(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.addWidget(QLabel(t("action")))

        self._action_combo = QComboBox()
        self._action_combo.addItem(t("stop_playback"), "stop")
        self._action_combo.addItem(t("quit_application"), "quit")
        self._action_combo.addItem(t("shutdown_computer"), "shutdown")
        layout.addWidget(self._action_combo)
        layout.addStretch()
        self._main_layout.addWidget(widget)

    def _add_fade_option(self):
        self._fade_checkbox = QCheckBox(t("fade_out_volume"))
        self._fade_checkbox.setChecked(True)
        self._main_layout.addWidget(self._fade_checkbox)

    def _add_status_label(self):
        self._status_label = QLabel()
        self._status_label.setObjectName("statusLabel")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setVisible(False)
        self._main_layout.addWidget(self._status_label)

    def _add_buttons(self):
        layout = QHBoxLayout()
        layout.setSpacing(12)

        self._start_btn = QPushButton(t("start"))
        self._cancel_btn = QPushButton(t("cancel_timer"))
        self._close_btn = QPushButton(t("close"))

        self._cancel_btn.setVisible(False)
        layout.addStretch()
        layout.addWidget(self._start_btn)
        layout.addWidget(self._cancel_btn)
        layout.addWidget(self._close_btn)
        layout.addStretch()
        self._main_layout.addLayout(layout)

    # ----------------------- 信号绑定 -----------------------
    def _connect_signals(self):
        self._mode_group.buttonClicked.connect(self._on_mode_changed)
        self._start_btn.clicked.connect(self._on_start)
        self._cancel_btn.clicked.connect(self._on_cancel_timer)
        self._close_btn.clicked.connect(self.close)

        self._sleep_timer.timer_started.connect(self._on_timer_started)
        self._sleep_timer.timer_stopped.connect(self._on_timer_stopped)
        self._sleep_timer.timer_triggered.connect(self._on_timer_triggered)

    # ----------------------- 样式 -----------------------
    def _apply_styles(self):
        style_template = """
#dialogContainer { background-color: %background_alt%; border-radius: 12px; }
#dialogTitle { font-size: 16px; font-weight: bold; color: %text%; }
QLabel { color: %text%; }

QRadioButton, QCheckBox { color: %text%; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 2px solid %border%; background-color: %background%; }
QRadioButton::indicator { width: 18px; height: 18px; border-radius: 9px; border: 2px solid %border%; background-color: %background%; }

QCheckBox::indicator:checked, QRadioButton::indicator:checked { background-color: %highlight%; border: 2px solid %highlight%; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: %highlight_hover%; }
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { border-color: %border%; background-color: %background_alt%; }
QSpinBox {
    background-color: %background%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 6px 12px;
    color: %text%;
    min-width: 80px;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 20px;
}
QComboBox { background-color: %background%; border: 1px solid %border%; border-radius: 6px; padding: 6px 12px; color: %text%; min-width: 120px; }
QComboBox::drop-down { border: none; width: 30px; }
QComboBox QAbstractItemView { background-color: %background_alt%; border: 1px solid %border%; selection-background-color: %highlight%; color: %text%; }
QPushButton { background-color: %highlight%; color: %background%; border: none; border-radius: 6px; padding: 8px 24px; font-size: 14px; min-width: 80px; }
QPushButton:hover { background-color: %highlight_hover%; }
QPushButton:pressed { background-color: %selection%; }
#statusLabel { color: %highlight%; font-size: 14px; font-weight: bold; padding: 8px; background-color: %background_hover%; border-radius: 6px; }
"""
        self.setStyleSheet(ThemeManager.instance().get_qss(style_template))

    # ----------------------- 核心逻辑 -----------------------
    def _on_mode_changed(self):
        time_mode = self._time_radio.isChecked()
        self._hours_spin.setEnabled(time_mode)
        self._minutes_spin.setEnabled(time_mode)
        self._seconds_spin.setEnabled(time_mode)
        self._track_spin.setEnabled(not time_mode)

    def _on_start(self):
        if self._sleep_timer.is_active:
            return

        mode = 'time' if self._time_radio.isChecked() else 'track'
        if mode == 'time':
            value = self._hours_spin.value() * 3600 + self._minutes_spin.value() * 60 + self._seconds_spin.value()
            if value == 0:
                return
        else:
            value = self._track_spin.value()

        action = self._action_combo.currentData()
        fade_out = self._fade_checkbox.isChecked()

        config = SleepTimerConfig(mode=mode, value=value, action=action, fade_out=fade_out)
        self._sleep_timer.start(config)

    def _on_cancel_timer(self):
        self._sleep_timer.cancel()

    def _on_timer_started(self):
        self._start_btn.setEnabled(False)
        self._cancel_btn.setVisible(True)
        self._status_label.setVisible(True)
        if not self._display_timer.isActive():
            self._display_timer.start(1000)
        self._update_display()

    def _on_timer_stopped(self):
        self._start_btn.setEnabled(True)
        self._cancel_btn.setVisible(False)
        self._status_label.setVisible(False)
        if self._display_timer.isActive():
            self._display_timer.stop()

    def _on_timer_triggered(self):
        self._on_timer_stopped()
        self.close()

    def _update_display(self):
        if not self._sleep_timer.is_active:
            return
        config = self._sleep_timer.config
        remaining = self._sleep_timer.remaining
        if config.mode == 'time':
            h = remaining // 3600
            m = (remaining % 3600) // 60
            s = remaining % 60
            self._status_label.setText(f"{t('remaining_time')} {h:02d}:{m:02d}:{s:02d}")
        else:
            self._status_label.setText(f"{t('remaining_tracks')} {remaining} {t('tracks')}")

    # ----------------------- 窗口圆角 & 拖动 -----------------------
    def resizeEvent(self, event):
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

    # ----------------------- 快捷键支持 -----------------------
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape,):
            self.close()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_start()
        elif event.matches(QKeySequence.Cancel):
            self._on_cancel_timer()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self._display_timer.isActive():
            self._display_timer.stop()
        super().closeEvent(event)