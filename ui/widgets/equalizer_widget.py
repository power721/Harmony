"""
Audio equalizer widget for the music player UI.
"""
from typing import List, Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSlider,
    QLabel, QPushButton, QComboBox, QDialog,
    QGraphicsDropShadowEffect
)

from system.i18n import t
from system.theme import ThemeManager
from ui.icons import IconName, get_icon

if TYPE_CHECKING:
    from infrastructure.audio import AudioBackend


class EqualizerPreset:
    """Equalizer preset data class."""

    def __init__(self, key: str, label_key: str, bands: List[float]):
        """
        Initialize preset.

        Args:
            key: Preset stable key
            label_key: i18n key for display name
            bands: List of band values in dB (-12 to +12)
        """
        self.key = key
        self.label_key = label_key
        self.bands = bands


class EqualizerWidget(QWidget):
    """
    Equalizer widget with configurable frequency bands.

    Note: QAudioOutput doesn't have built-in EQ support in Qt6.
    This is a UI component that can be connected to audio processing.
    For actual EQ, you would need to integrate with libraries like
    GStreamer or implement custom audio processing.
    """

    preset_changed = Signal(str)  # Signal when preset changes
    band_changed = Signal(int, float)  # Signal when band changes (band_index, value)

    # Standard frequency bands (Hz)
    FREQUENCY_BANDS = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000]

    # Default presets
    PRESETS: List[EqualizerPreset] = [
        EqualizerPreset('flat', "eq_preset_flat", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        EqualizerPreset('bass_boost', "eq_preset_bass_boost", [6, 5, 4, 2, 0, 0, 0, 0, 0, 0]),
        EqualizerPreset('treble_boost', "eq_preset_treble_boost", [0, 0, 0, 0, 0, 2, 4, 6, 7, 7]),
        EqualizerPreset('vocal', "eq_preset_vocal", [-2, -2, -1, 0, 2, 4, 4, 2, 0, 0]),
        EqualizerPreset('rock', "eq_preset_rock", [5, 4, 3, 1, -1, 0, 2, 4, 5, 5]),
        EqualizerPreset('classical', "eq_preset_classical", [4, 3, 2, 1, 1, 1, 2, 3, 4, 4]),
        EqualizerPreset('electronic', "eq_preset_electronic", [4, 3, 1, -1, -2, 0, 2, 4, 5, 5]),
        EqualizerPreset('hip_hop', "eq_preset_hip_hop", [5, 4, 2, 0, -1, 0, 2, 4, 5, 5]),
    ]

    _PRESET_LABEL_STYLE = "color: %text_secondary%;"

    _COMBO_STYLE = ThemeManager.get_combobox_style()

    _BUTTON_STYLE = """
        QPushButton {
            background-color: %background_alt%;
            color: %text_secondary%;
            border: none;
            padding: 5px 15px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: %border%;
            color: %text%;
        }
    """

    _WIDGET_STYLE = """
        EqualizerWidget {
            background-color: %background%;
            border-radius: 8px;
        }
    """

    _FREQ_LABEL_STYLE = "color: %text_secondary%; font-size: 10px;"
    _VALUE_LABEL_STYLE = "color: %text%; font-size: 11px;"
    _SLIDER_STYLE = """
        QSlider::groove:vertical {
            width: 4px;
            background: %border%;
            border-radius: 2px;
        }
        QSlider::handle:vertical {
            width: 12px;
            height: 12px;
            background: %highlight%;
            border-radius: 6px;
            margin: 0 -4px;
        }
        QSlider::handle:vertical:hover {
            background: %highlight_hover%;
        }
    """

    def __init__(self, parent=None):
        """Initialize equalizer widget."""
        super().__init__(parent)

        self._bands = [0.0] * len(self.FREQUENCY_BANDS)
        self._current_preset = 'flat'
        self._backend: Optional["AudioBackend"] = None
        self._sliders: list[QSlider] = []
        self._value_labels: list[QLabel] = []

        self._setup_ui()
        self._apply_preset('flat')

        # Register with theme manager
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

    def _setup_ui(self):
        """Setup the user interface."""
        from system.theme import ThemeManager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Preset selector
        preset_layout = QHBoxLayout()

        preset_label = QLabel(t("eq_preset_label"))
        preset_label.setStyleSheet(ThemeManager.instance().get_qss(self._PRESET_LABEL_STYLE))
        preset_layout.addWidget(preset_label)

        self._preset_combo = QComboBox()
        for preset in self.PRESETS:
            self._preset_combo.addItem(t(preset.label_key), preset.key)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self._preset_combo.setStyleSheet(ThemeManager.instance().get_qss(self._COMBO_STYLE))
        preset_layout.addWidget(self._preset_combo)

        preset_layout.addStretch()

        # Reset button
        reset_btn = QPushButton(t("reset"))
        reset_btn.clicked.connect(lambda: self._apply_preset('flat'))
        reset_btn.setStyleSheet(ThemeManager.instance().get_qss(self._BUTTON_STYLE))
        preset_layout.addWidget(reset_btn)

        layout.addLayout(preset_layout)

        # Band sliders
        bands_layout = QHBoxLayout()
        bands_layout.setSpacing(8)

        for i, freq in enumerate(self.FREQUENCY_BANDS):
            band_widget = self._create_band_slider(i, freq)
            bands_layout.addWidget(band_widget)

        layout.addLayout(bands_layout)

        # Apply container style
        self.setStyleSheet(ThemeManager.instance().get_qss(self._WIDGET_STYLE))

    def _create_band_slider(self, index: int, frequency: int) -> QWidget:
        """Create a slider for a frequency band."""
        from system.theme import ThemeManager

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Frequency label
        freq_label = QLabel(self._format_frequency(frequency))
        freq_label.setAlignment(Qt.AlignCenter)
        freq_label.setStyleSheet(ThemeManager.instance().get_qss(self._FREQ_LABEL_STYLE))
        layout.addWidget(freq_label)

        # Value label
        value_label = QLabel('0')
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet(ThemeManager.instance().get_qss(self._VALUE_LABEL_STYLE))
        layout.addWidget(value_label)

        # Slider
        slider = QSlider(Qt.Vertical)
        slider.setRange(-12, 12)
        slider.setValue(0)
        slider.setFixedWidth(40)
        slider.setStyleSheet(ThemeManager.instance().get_qss(self._SLIDER_STYLE))
        slider.valueChanged.connect(
            lambda value, idx=index, lbl=value_label:
            self._on_band_changed(idx, value, lbl)
        )
        layout.addWidget(slider)
        self._sliders.append(slider)
        self._value_labels.append(value_label)

        return widget

    def _format_frequency(self, freq: int) -> str:
        """Format frequency for display."""
        if freq >= 1000:
            return f"{freq // 1000}k"
        return str(freq)

    def _apply_preset(self, preset_key: str):
        """Apply an equalizer preset."""
        for preset in self.PRESETS:
            if preset.key == preset_key:
                self._bands = preset.bands.copy()
                self._current_preset = preset_key

                # Update sliders/labels to reflect preset immediately.
                self._sync_sliders_from_bands()

                self.preset_changed.emit(preset_key)
                self._apply_to_backend()
                break

    def _on_preset_changed(self, _index: int):
        """Handle preset selection change."""
        preset_key = self._preset_combo.currentData()
        if preset_key:
            self._apply_preset(preset_key)

    def _on_band_changed(self, band_index: int, value: int, label: QLabel):
        """Handle band slider change."""
        self._bands[band_index] = float(value)
        label.setText(str(value))

        # Clear preset when manually adjusting
        self._current_preset = 'custom'

        self.band_changed.emit(band_index, float(value))
        self._apply_to_backend()

    def get_bands(self) -> List[float]:
        """Get current band values."""
        return self._bands.copy()

    def set_bands(self, bands: List[float]):
        """Set band values."""
        if len(bands) == len(self._bands):
            self._bands = bands.copy()
            self._sync_sliders_from_bands()
            self._apply_to_backend()

    def apply_to_backend(self, backend: "AudioBackend"):
        """Bind equalizer changes to an audio backend."""
        self._backend = backend
        self._apply_to_backend()

    def _apply_to_backend(self):
        """Apply current EQ values to backend if supported."""
        if self._backend is None:
            return
        try:
            self._backend.set_eq_bands(self._bands.copy())
        except Exception:
            # EQ is best-effort and should not break UI interaction.
            pass

    def _sync_sliders_from_bands(self):
        """Synchronize slider widget values with current internal bands."""
        if not self._sliders or not self._value_labels:
            return
        for i, band in enumerate(self._bands):
            value = int(round(float(band)))
            if i < len(self._sliders):
                slider = self._sliders[i]
                slider.blockSignals(True)
                slider.setValue(value)
                slider.blockSignals(False)
            if i < len(self._value_labels):
                self._value_labels[i].setText(str(value))

    def refresh_theme(self):
        """Refresh theme colors when theme changes."""
        from system.theme import ThemeManager

        # Update all styled widgets
        self.setStyleSheet(ThemeManager.instance().get_qss(self._WIDGET_STYLE))

        # Find and update all child widgets
        for child in self.findChildren(QLabel):
            if child.text() in [self._format_frequency(f) for f in self.FREQUENCY_BANDS]:
                child.setStyleSheet(ThemeManager.instance().get_qss(self._FREQ_LABEL_STYLE))
            elif child.text().isdigit() or child.text().startswith('-'):
                child.setStyleSheet(ThemeManager.instance().get_qss(self._VALUE_LABEL_STYLE))

        # Update combo box
        self._preset_combo.setStyleSheet(ThemeManager.instance().get_qss(self._COMBO_STYLE))

        # Update sliders
        for slider in self.findChildren(QSlider):
            slider.setStyleSheet(ThemeManager.instance().get_qss(self._SLIDER_STYLE))


class EqualizerDialog:
    """Standalone themed equalizer dialog with custom title bar."""

    _STYLE_TEMPLATE = """
        QWidget#dialogContainer {
            background-color: %background_alt%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 12px;
        }
        QWidget#dialogTitleBar {
            background-color: %background_alt%;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom: 1px solid %border%;
        }
        QLabel#dialogTitle {
            color: %text%;
            font-size: 14px;
            font-weight: bold;
        }
        QPushButton#dialogCloseBtn {
            background: transparent;
            border: none;
            color: %text_secondary%;
            border-radius: 4px;
        }
        QPushButton#dialogCloseBtn:hover {
            background-color: %selection%;
            color: %text%;
        }
    """

    def __init__(self, backend=None, parent=None):
        self._dialog = QDialog(parent)
        self._drag_pos = None
        self._setup_dialog(backend)

    @property
    def widget(self) -> QDialog:
        return self._dialog

    def show(self):
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def _setup_dialog(self, backend):
        dialog = self._dialog
        dialog.setWindowTitle(t("equalizer"))
        dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        dialog.setMinimumWidth(680)

        shadow = QGraphicsDropShadowEffect(dialog)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        dialog.setGraphicsEffect(shadow)

        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QWidget()
        title_bar.setObjectName("dialogTitleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(14, 10, 10, 10)

        title_label = QLabel(t("equalizer"))
        title_label.setObjectName("dialogTitle")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        close_btn = QPushButton()
        close_btn.setObjectName("dialogCloseBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setIcon(get_icon(IconName.TIMES, None, 14))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.clicked.connect(dialog.close)
        title_layout.addWidget(close_btn)

        layout.addWidget(title_bar)

        eq_widget = EqualizerWidget(dialog)
        if backend is not None:
            eq_widget.apply_to_backend(backend)
        layout.addWidget(eq_widget)

        self._eq_widget = eq_widget
        self._title_bar = title_bar
        self._title_label = title_label
        self._close_btn = close_btn

        title_bar.mousePressEvent = self._mouse_press
        title_bar.mouseMoveEvent = self._mouse_move
        title_bar.mouseReleaseEvent = self._mouse_release
        dialog.resizeEvent = self._resize_event

        self.refresh_theme()
        ThemeManager.instance().register_widget(self)

    def apply_to_backend(self, backend):
        self._eq_widget.apply_to_backend(backend)

    def refresh_theme(self):
        self._dialog.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))
        self._eq_widget.refresh_theme()

    def _resize_event(self, event):
        path = QPainterPath()
        path.addRoundedRect(self._dialog.rect(), 12, 12)
        self._dialog.setMask(QRegion(path.toFillPolygon().toPolygon()))
        QDialog.resizeEvent(self._dialog, event)

    def _mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._dialog.frameGeometry().topLeft()

    def _mouse_move(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self._dialog.move(event.globalPosition().toPoint() - self._drag_pos)

    def _mouse_release(self, _event):
        self._drag_pos = None
