from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.message_dialog import MessageDialog
from ui.widgets.toggle_switch import ToggleSwitch


class _PluginNameCell(QWidget):
    def __init__(self, name: str, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(0)

        name_label = QLabel(name, self)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)


class PluginManagementTab(QWidget):
    _COLUMN_NAME = 0
    _COLUMN_VERSION = 1
    _COLUMN_SOURCE = 2
    _COLUMN_ERROR = 3
    _COLUMN_ENABLED = 4
    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self._plugin_manager = plugin_manager
        self._table = QTableWidget(self)
        self._url_input = QLineEdit(self)
        self._theme_manager = self._resolve_theme_manager()
        if self._theme_manager is not None:
            self._theme_manager.register_widget(self)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table.setObjectName("pluginManagementTable")
        self._table.setProperty("variant", "panel")
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            [
                t("plugins_tab"),
                t("version"),
                t("source"),
                t("plugins_load_error"),
                t("plugins_enabled"),
            ]
        )
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.setWordWrap(True)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(56)
        self._table.verticalHeader().setMinimumSectionSize(56)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(self._COLUMN_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(self._COLUMN_VERSION, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self._COLUMN_SOURCE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self._COLUMN_ERROR, QHeaderView.Stretch)
        header.setSectionResizeMode(self._COLUMN_ENABLED, QHeaderView.Fixed)
        self._table.setColumnWidth(self._COLUMN_ENABLED, 68)
        self._table.setColumnWidth(self._COLUMN_ERROR, 180)
        self.refresh_theme()

        layout.addWidget(self._table)

        warning_label = QLabel(t("plugins_install_warning"), self)
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        controls = QHBoxLayout()
        self._url_input.setPlaceholderText("https://example.com/plugin.zip")
        install_zip_btn = QPushButton(t("plugins_install_zip"), self)
        install_zip_btn.clicked.connect(self._install_zip)
        install_url_btn = QPushButton(t("plugins_install_url"), self)
        install_url_btn.clicked.connect(self._install_url)
        controls.addWidget(self._url_input)
        controls.addWidget(install_zip_btn)
        controls.addWidget(install_url_btn)
        layout.addLayout(controls)

    def refresh(self) -> None:
        rows = self._plugin_manager.list_plugins()
        self._table.setRowCount(len(rows))

        for index, row in enumerate(rows):
            self._table.setCellWidget(
                index,
                self._COLUMN_NAME,
                _PluginNameCell(row["name"], self._table),
            )

            self._set_text_item(index, self._COLUMN_VERSION, row["version"])
            self._set_text_item(index, self._COLUMN_SOURCE, self._source_label(row.get("source", "")))

            load_error = row.get("load_error") or ""
            self._set_text_item(index, self._COLUMN_ERROR, load_error)
            error_item = self._table.item(index, self._COLUMN_ERROR)
            if error_item is not None and load_error:
                error_item.setToolTip(load_error)

            plugin_id = row.get("id", "")
            toggle = ToggleSwitch(bool(row.get("enabled", True)), self._table)
            toggle.setObjectName(f"pluginToggle:{plugin_id}")
            status = t("plugins_enabled") if row.get("enabled", True) else t("plugins_disabled")
            toggle.setToolTip(status)
            toggle.toggled.connect(
                lambda enabled, plugin_id=plugin_id: self._set_plugin_enabled(plugin_id, enabled)
            )

            toggle_cell = QWidget(self._table)
            toggle_layout = QHBoxLayout(toggle_cell)
            toggle_layout.setContentsMargins(0, 0, 0, 0)
            toggle_layout.addStretch()
            toggle_layout.addWidget(toggle)
            toggle_layout.addStretch()
            self._table.setCellWidget(index, self._COLUMN_ENABLED, toggle_cell)

            self._table.setRowHeight(index, 56)

    def _set_text_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._table.setItem(row, column, item)

    def _source_label(self, source: str) -> str:
        key = {
            "builtin": "plugins_source_builtin",
            "external": "plugins_source_external",
        }.get(source)
        return t(key) if key else source

    def _set_plugin_enabled(self, plugin_id: str, enabled: bool) -> None:
        if not plugin_id:
            return
        result = self._plugin_manager.set_plugin_enabled(plugin_id, enabled)
        if isinstance(result, dict) and result.get("requires_restart"):
            MessageDialog.information(
                self,
                t("info"),
                t("plugins_restart_required_after_toggle"),
            )
        self.refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._table.resizeRowsToContents()
        for row in range(self._table.rowCount()):
            self._table.setRowHeight(row, max(56, self._table.rowHeight(row)))

    def refresh_theme(self) -> None:
        return

    def _resolve_theme_manager(self):
        try:
            return ThemeManager.instance()
        except ValueError:
            return None

    def _install_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("plugins_install_zip"),
            "",
            "Zip Files (*.zip)",
        )
        if path:
            self._plugin_manager.install_zip(path)
            self.refresh()

    def _install_url(self) -> None:
        url = self._url_input.text().strip()
        if url:
            self._plugin_manager.install_from_url(url)
            self.refresh()
