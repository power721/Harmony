from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from system.i18n import t


class PluginManagementTab(QWidget):
    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self._plugin_manager = plugin_manager
        self._table = QTableWidget(0, 5, self)
        self._url_input = QLineEdit(self)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._table.setHorizontalHeaderLabels(
            [
                t("name"),
                t("version"),
                t("source"),
                t("status"),
                t("plugins_load_error"),
            ]
        )
        layout.addWidget(self._table)

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
        for row_index, row in enumerate(rows):
            self._table.setItem(row_index, 0, QTableWidgetItem(row["name"]))
            self._table.setItem(row_index, 1, QTableWidgetItem(row["version"]))
            self._table.setItem(row_index, 2, QTableWidgetItem(row["source"]))
            status = t("plugins_enabled") if row["enabled"] else t("plugins_disabled")
            self._table.setItem(row_index, 3, QTableWidgetItem(status))
            self._table.setItem(row_index, 4, QTableWidgetItem(row["load_error"] or ""))

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
