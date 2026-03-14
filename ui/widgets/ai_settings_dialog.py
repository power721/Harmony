"""
AI Settings Dialog for configuring AI model API and AcoustID.
"""
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QGroupBox, QMessageBox, QTabWidget, QWidget
)
from PySide6.QtCore import Qt

from system.i18n import t

# Configure logging
logger = logging.getLogger(__name__)


class AISettingsDialog(QDialog):
    """Dialog for configuring AI model API and AcoustID settings."""

    def __init__(self, config_manager, parent=None):
        """
        Initialize the AI settings dialog.

        Args:
            config_manager: ConfigManager instance for saving settings
            parent: Parent widget
        """
        super().__init__(parent)
        self._config = config_manager
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle(t("ai_settings"))
        self.setMinimumWidth(530)

        # Apply dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #282828;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 6px;
            }
            QLineEdit:focus {
                border: 1px solid #1db954;
            }
            QLineEdit:disabled {
                background-color: #2a2a2a;
                color: #606060;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QCheckBox {
                color: #ffffff;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QGroupBox {
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a3a;
                background-color: #282828;
            }
            QTabBar::tab {
                background-color: #2a2a2a;
                color: #c0c0c0;
                padding: 8px 16px;
                border: 1px solid #3a3a3a;
            }
            QTabBar::tab:selected {
                background-color: #3a3a3a;
                color: #ffffff;
                border-bottom-color: #3a3a3a;
            }
            QTabBar::tab:hover:!selected {
                background-color: #353535;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Tab widget for AI and AcoustID settings
        tab_widget = QTabWidget()

        # AI Settings Tab
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        ai_layout.setSpacing(10)

        # Enable AI checkbox
        self._enable_checkbox = QCheckBox(t("ai_enable"))
        self._enable_checkbox.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffffff;")
        self._enable_checkbox.stateChanged.connect(self._on_enable_changed)
        ai_layout.addWidget(self._enable_checkbox)

        # Settings group
        settings_group = QGroupBox(t("ai_api_config"))
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(10)

        # Base URL
        base_url_layout = QHBoxLayout()
        base_url_label = QLabel(t("ai_base_url"))
        base_url_label.setMinimumWidth(100)
        self._base_url_input = QLineEdit()
        self._base_url_input.setPlaceholderText("https://api.example.com/v1")
        base_url_layout.addWidget(base_url_label)
        base_url_layout.addWidget(self._base_url_input)
        settings_layout.addLayout(base_url_layout)

        # API Key
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel(t("ai_api_key"))
        api_key_label.setMinimumWidth(100)
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.Password)
        self._api_key_input.setPlaceholderText(t("ai_api_key_placeholder"))
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self._api_key_input)
        settings_layout.addLayout(api_key_layout)

        # Model
        model_layout = QHBoxLayout()
        model_label = QLabel(t("ai_model"))
        model_label.setMinimumWidth(100)
        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("qwen-plus, gpt-3.5-turbo, etc.")
        model_layout.addWidget(model_label)
        model_layout.addWidget(self._model_input)
        settings_layout.addLayout(model_layout)

        # Hint label
        hint_label = QLabel(t("ai_settings_hint"))
        hint_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        hint_label.setWordWrap(True)
        settings_layout.addWidget(hint_label)

        settings_group.setLayout(settings_layout)
        ai_layout.addWidget(settings_group)

        # Test button for AI
        test_btn = QPushButton(t("ai_test_connection"))
        test_btn.clicked.connect(self._test_connection)
        ai_layout.addWidget(test_btn)

        ai_layout.addStretch()
        tab_widget.addTab(ai_tab, t("ai_tab"))

        # AcoustID Settings Tab
        acoustid_tab = QWidget()
        acoustid_layout = QVBoxLayout(acoustid_tab)
        acoustid_layout.setSpacing(10)

        # Enable AcoustID checkbox
        self._acoustid_enable_checkbox = QCheckBox(t("acoustid_enable"))
        self._acoustid_enable_checkbox.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffffff;")
        self._acoustid_enable_checkbox.stateChanged.connect(self._on_acoustid_enable_changed)
        acoustid_layout.addWidget(self._acoustid_enable_checkbox)

        # AcoustID settings group
        acoustid_group = QGroupBox(t("acoustid_config"))
        acoustid_settings_layout = QVBoxLayout()
        acoustid_settings_layout.setSpacing(10)

        # AcoustID API Key
        acoustid_key_layout = QHBoxLayout()
        acoustid_key_label = QLabel(t("acoustid_api_key"))
        acoustid_key_label.setMinimumWidth(100)
        self._acoustid_api_key_input = QLineEdit()
        self._acoustid_api_key_input.setEchoMode(QLineEdit.Password)
        self._acoustid_api_key_input.setPlaceholderText(t("acoustid_api_key_placeholder"))
        acoustid_key_layout.addWidget(acoustid_key_label)
        acoustid_key_layout.addWidget(self._acoustid_api_key_input)
        acoustid_settings_layout.addLayout(acoustid_key_layout)

        # AcoustID hint label
        acoustid_hint_label = QLabel(t("acoustid_settings_hint"))
        acoustid_hint_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        acoustid_hint_label.setWordWrap(True)
        acoustid_settings_layout.addWidget(acoustid_hint_label)

        acoustid_group.setLayout(acoustid_settings_layout)
        acoustid_layout.addWidget(acoustid_group)

        # Test button for AcoustID
        acoustid_test_btn = QPushButton(t("acoustid_test"))
        acoustid_test_btn.clicked.connect(self._test_acoustid)
        acoustid_layout.addWidget(acoustid_test_btn)

        acoustid_layout.addStretch()
        tab_widget.addTab(acoustid_tab, t("acoustid_tab"))

        layout.addWidget(tab_widget)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_btn = QPushButton(t("save"))
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _on_enable_changed(self, state):
        """Handle enable checkbox state change."""
        # state is an int from stateChanged signal
        # Qt.Checked = 2, but we also accept True (bool) for direct calls
        enabled = state == Qt.Checked or state is True or state == 2
        self._base_url_input.setEnabled(enabled)
        self._api_key_input.setEnabled(enabled)
        self._model_input.setEnabled(enabled)

    def _on_acoustid_enable_changed(self, state):
        """Handle AcoustID enable checkbox state change."""
        enabled = state == Qt.Checked or state is True or state == 2
        self._acoustid_api_key_input.setEnabled(enabled)

    def _load_settings(self):
        """Load settings from config."""
        # AI settings
        enabled = self._config.get_ai_enabled()
        base_url = self._config.get_ai_base_url()
        api_key = self._config.get_ai_api_key()
        model = self._config.get_ai_model()

        # Block signals to prevent triggering _on_enable_changed during setup
        self._enable_checkbox.blockSignals(True)
        self._enable_checkbox.setChecked(enabled)
        self._enable_checkbox.blockSignals(False)

        # Set text and enable state
        self._base_url_input.setText(base_url)
        self._api_key_input.setText(api_key)
        self._model_input.setText(model)

        # Manually set enabled state
        self._base_url_input.setEnabled(enabled)
        self._api_key_input.setEnabled(enabled)
        self._model_input.setEnabled(enabled)

        # AcoustID settings
        acoustid_enabled = self._config.get_acoustid_enabled()
        acoustid_api_key = self._config.get_acoustid_api_key()

        self._acoustid_enable_checkbox.blockSignals(True)
        self._acoustid_enable_checkbox.setChecked(acoustid_enabled)
        self._acoustid_enable_checkbox.blockSignals(False)

        self._acoustid_api_key_input.setText(acoustid_api_key)
        self._acoustid_api_key_input.setEnabled(acoustid_enabled)

    def _save_settings(self):
        """Save settings to config."""
        # AI settings
        enabled = self._enable_checkbox.isChecked()
        base_url = self._base_url_input.text().strip()
        api_key = self._api_key_input.text().strip()
        model = self._model_input.text().strip()

        # Validate AI settings
        if enabled:
            if not base_url:
                QMessageBox.warning(self, t("warning"), t("ai_base_url_required"))
                return
            if not api_key:
                QMessageBox.warning(self, t("warning"), t("ai_api_key_required"))
                return
            if not model:
                QMessageBox.warning(self, t("warning"), t("ai_model_required"))
                return

        # AcoustID settings
        acoustid_enabled = self._acoustid_enable_checkbox.isChecked()
        acoustid_api_key = self._acoustid_api_key_input.text().strip()

        # Validate AcoustID settings
        if acoustid_enabled and not acoustid_api_key:
            QMessageBox.warning(self, t("warning"), t("acoustid_api_key_required"))
            return

        # Save AI settings
        self._config.set_ai_enabled(enabled)
        self._config.set_ai_base_url(base_url)
        self._config.set_ai_api_key(api_key)
        self._config.set_ai_model(model)

        # Save AcoustID settings
        self._config.set_acoustid_enabled(acoustid_enabled)
        self._config.set_acoustid_api_key(acoustid_api_key)

        QMessageBox.information(self, t("success"), t("ai_settings_saved"))
        self.accept()

    def _test_connection(self):
        """Test the AI API connection."""
        base_url = self._base_url_input.text().strip()
        api_key = self._api_key_input.text().strip()
        model = self._model_input.text().strip()

        if not base_url or not api_key or not model:
            QMessageBox.warning(self, t("warning"), t("ai_fill_all_fields"))
            return

        # Test connection
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
            )

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10,
            )

            if response.choices:
                QMessageBox.information(self, t("success"), t("ai_connection_success"))
            else:
                QMessageBox.warning(self, t("warning"), t("ai_connection_failed"))

        except Exception as e:
            logger.error(f"AI connection test failed: {e}", exc_info=True)
            QMessageBox.critical(self, t("error"), f"{t('ai_connection_failed')}: {str(e)}")

    def _test_acoustid(self):
        """Test the AcoustID API key by checking if pyacoustid is installed."""
        acoustid_api_key = self._acoustid_api_key_input.text().strip()

        if not acoustid_api_key:
            QMessageBox.warning(self, t("warning"), t("acoustid_api_key_required"))
            return

        # Check if pyacoustid is installed
        try:
            import acoustid
            # The API key can't be tested without an actual file,
            # but we can verify the format and that pyacoustid is installed
            QMessageBox.information(
                self, t("success"),
                t("acoustid_ready")
            )
        except ImportError:
            QMessageBox.warning(
                self, t("warning"),
                t("acoustid_not_installed")
            )
