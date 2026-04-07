from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from system.i18n import t


class PluginManagementTab(QWidget):
    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self._plugin_manager = plugin_manager
        self._list = QListWidget(self)
        self._url_input = QLineEdit(self)
        self._enable_btn = QPushButton(t("plugins_enabled"), self)
        self._disable_btn = QPushButton(t("plugins_disabled"), self)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._list)
        self._list.currentItemChanged.connect(lambda *_args: self._sync_action_buttons())

        state_controls = QHBoxLayout()
        self._enable_btn.clicked.connect(lambda: self._set_selected_plugin_enabled(True))
        self._disable_btn.clicked.connect(lambda: self._set_selected_plugin_enabled(False))
        state_controls.addWidget(self._enable_btn)
        state_controls.addWidget(self._disable_btn)
        layout.addLayout(state_controls)

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
        self._list.clear()
        for row in rows:
            status = t("plugins_enabled") if row["enabled"] else t("plugins_disabled")
            parts = [
                row["name"],
                row["version"],
                row["source"],
                status,
            ]
            if row["load_error"]:
                parts.append(row["load_error"])
            item = QListWidgetItem(" · ".join(parts))
            item.setData(0x0100, row)
            self._list.addItem(item)
        self._sync_action_buttons()

    def _set_selected_plugin_enabled(self, enabled: bool) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        row = item.data(0x0100) or {}
        plugin_id = row.get("id")
        if not plugin_id:
            return
        self._plugin_manager.set_plugin_enabled(plugin_id, enabled)
        self.refresh()
        self._restore_selection(plugin_id)

    def _restore_selection(self, plugin_id: str) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            row = item.data(0x0100) or {}
            if row.get("id") == plugin_id:
                self._list.setCurrentRow(index)
                break

    def _sync_action_buttons(self) -> None:
        item = self._list.currentItem()
        if item is None:
            self._enable_btn.setEnabled(False)
            self._disable_btn.setEnabled(False)
            return
        row = item.data(0x0100) or {}
        enabled = bool(row.get("enabled", True))
        self._enable_btn.setEnabled(not enabled)
        self._disable_btn.setEnabled(enabled)

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
