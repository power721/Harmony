"""
Audio equalizer widget for the music player UI.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSlider,
    QLabel, QPushButton, QComboBox
)
from PySide6.QtCore import Qt, Signal
from typing import List


class EqualizerPreset:
    """Equalizer preset data class."""

    def __init__(self, name: str, bands: List[float]):
        """
        Initialize preset.

        Args:
            name: Preset name
            bands: List of band values in dB (-12 to +12)
        """
        self.name = name
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
        EqualizerPreset('Flat', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        EqualizerPreset('Bass Boost', [6, 5, 4, 2, 0, 0, 0, 0, 0, 0]),
        EqualizerPreset('Treble Boost', [0, 0, 0, 0, 0, 2, 4, 6, 7, 7]),
        EqualizerPreset('Vocal', [-2, -2, -1, 0, 2, 4, 4, 2, 0, 0]),
        EqualizerPreset('Rock', [5, 4, 3, 1, -1, 0, 2, 4, 5, 5]),
        EqualizerPreset('Classical', [4, 3, 2, 1, 1, 1, 2, 3, 4, 4]),
        EqualizerPreset('Electronic', [4, 3, 1, -1, -2, 0, 2, 4, 5, 5]),
        EqualizerPreset('Hip Hop', [5, 4, 2, 0, -1, 0, 2, 4, 5, 5]),
    ]

    def __init__(self, parent=None):
        """Initialize equalizer widget."""
        super().__init__(parent)

        self._bands = [0.0] * len(self.FREQUENCY_BANDS)
        self._current_preset = 'Flat'

        self._setup_ui()
        self._apply_preset('Flat')

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Preset selector
        preset_layout = QHBoxLayout()

        preset_label = QLabel('Preset:')
        preset_label.setStyleSheet("color: #b3b3b3;")
        preset_layout.addWidget(preset_label)

        self._preset_combo = QComboBox()
        self._preset_combo.addEntries([p.name for p in self.PRESETS])
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        self._preset_combo.setStyleSheet("""
            QComboBox {
                background-color: #282828;
                color: #ffffff;
                border: none;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QComboBox:hover {
                background-color: #383838;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                color: #b3b3b3;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #404040;
                selection-background-color: #1db954;
                selection-color: #ffffff;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                color: #ffffff;
                padding: 6px 12px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #383838;
                color: #ffffff;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #1db954;
                color: #ffffff;
            }
        """)
        preset_layout.addWidget(self._preset_combo)

        preset_layout.addStretch()

        # Reset button
        reset_btn = QPushButton('Reset')
        reset_btn.clicked.connect(lambda: self._apply_preset('Flat'))
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #282828;
                color: #b3b3b3;
                border: none;
                padding: 5px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #404040;
                color: #ffffff;
            }
        """)
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
        self.setStyleSheet("""
            EqualizerWidget {
                background-color: #181818;
                border-radius: 8px;
            }
        """)

    def _create_band_slider(self, index: int, frequency: int) -> QWidget:
        """Create a slider for a frequency band."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Frequency label
        freq_label = QLabel(self._format_frequency(frequency))
        freq_label.setAlignment(Qt.AlignCenter)
        freq_label.setStyleSheet("color: #b3b3b3; font-size: 10px;")
        layout.addWidget(freq_label)

        # Value label
        value_label = QLabel('0')
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet("color: #ffffff; font-size: 11px;")
        layout.addWidget(value_label)

        # Slider
        slider = QSlider(Qt.Vertical)
        slider.setRange(-12, 12)
        slider.setValue(0)
        slider.setFixedWidth(40)
        slider.setStyleSheet("""
            QSlider::groove:vertical {
                width: 4px;
                background: #4d4d4d;
                border-radius: 2px;
            }
            QSlider::handle:vertical {
                width: 12px;
                height: 12px;
                background: #1db954;
                border-radius: 6px;
                margin: 0 -4px;
            }
            QSlider::handle:vertical:hover {
                background: #1ed760;
            }
        """)
        slider.valueChanged.connect(
            lambda value, idx=index, lbl=value_label:
            self._on_band_changed(idx, value, lbl)
        )
        layout.addWidget(slider)

        return widget

    def _format_frequency(self, freq: int) -> str:
        """Format frequency for display."""
        if freq >= 1000:
            return f"{freq // 1000}k"
        return str(freq)

    def _apply_preset(self, preset_name: str):
        """Apply an equalizer preset."""
        for preset in self.PRESETS:
            if preset.name == preset_name:
                self._bands = preset.bands.copy()
                self._current_preset = preset_name

                # Update sliders
                # Note: In a full implementation, you'd store slider references
                # and update them here

                self.preset_changed.emit(preset_name)
                break

    def _on_preset_changed(self, preset_name: str):
        """Handle preset selection change."""
        self._apply_preset(preset_name)

    def _on_band_changed(self, band_index: int, value: int, label: QLabel):
        """Handle band slider change."""
        self._bands[band_index] = float(value)
        label.setText(str(value))

        # Clear preset when manually adjusting
        self._current_preset = 'Custom'

        self.band_changed.emit(band_index, float(value))

    def get_bands(self) -> List[float]:
        """Get current band values."""
        return self._bands.copy()

    def set_bands(self, bands: List[float]):
        """Set band values."""
        if len(bands) == len(self._bands):
            self._bands = bands.copy()


class EqualizerDialog:
    """
    Standalone equalizer dialog.

    This would be shown as a separate window or panel.
    """

    def __init__(self, parent=None):
        """Initialize equalizer dialog."""
        # In a full implementation, this would be a QDialog
        # For now, the widget is integrated into the main window
        pass
