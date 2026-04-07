# Unified Foundation Theme Styles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the theme system the single owner of common Qt foundation widget styles and shared wrapper component styles across host UI and built-in plugins.

**Architecture:** Expand the global stylesheet in `ui/styles.qss` so common Qt controls and shared wrappers are themed centrally, then add a small set of `ThemeManager` popup helper accessors for Qt surfaces that cannot be styled reliably through application-global QSS alone. Refactor host wrappers, host feature views, and built-in plugin UI to stop embedding base QSS for foundation controls and instead use object names, dynamic properties, and host-owned popup helpers.

**Tech Stack:** Python 3.11, PySide6, pytest, `uv`, Harmony `ThemeManager`, built-in plugin UI bridge

---

## File Map

- Create: `tests/test_system/test_theme_foundation_styles.py`
- Create: `tests/test_ui/test_dialog_title_bar.py`
- Create: `tests/test_ui/test_foundation_theme_cleanup.py`
- Modify: `system/theme.py`
- Modify: `ui/styles.qss`
- Modify: `system/plugins/plugin_sdk_ui.py`
- Modify: `plugins/builtin/qqmusic/lib/runtime_bridge.py`
- Modify: `ui/dialogs/dialog_title_bar.py`
- Modify: `ui/widgets/title_bar.py`
- Modify: `ui/widgets/toggle_switch.py`
- Modify: `ui/widgets/context_menus.py`
- Modify: `ui/views/cover_hover_popup.py`
- Modify: `ui/views/queue_view.py`
- Modify: `ui/dialogs/base_rename_dialog.py`
- Modify: `ui/dialogs/input_dialog.py`
- Modify: `ui/dialogs/settings_dialog.py`
- Modify: `ui/dialogs/edit_media_info_dialog.py`
- Modify: `ui/dialogs/lyrics_download_dialog.py`
- Modify: `ui/dialogs/base_cover_download_dialog.py`
- Modify: `ui/views/library_view.py`
- Modify: `ui/views/albums_view.py`
- Modify: `ui/views/artists_view.py`
- Modify: `ui/views/genres_view.py`
- Modify: `ui/views/cloud/cloud_drive_view.py`
- Modify: `ui/widgets/equalizer_widget.py`
- Modify: `plugins/builtin/qqmusic/lib/dialog_title_bar.py`
- Modify: `plugins/builtin/qqmusic/lib/login_dialog.py`
- Modify: `plugins/builtin/qqmusic/lib/settings_tab.py`
- Modify: `plugins/builtin/qqmusic/lib/online_music_view.py`
- Modify: `plugins/builtin/qqmusic/lib/context_menus.py`
- Modify: `plugins/builtin/qqmusic/lib/cover_hover_popup.py`
- Modify: `tests/test_system/test_plugin_ui_bridge.py`
- Modify: `tests/test_title_bar.py`
- Modify: `tests/test_plugins/test_qqmusic_plugin.py`

## Task 1: Lock In Theme API And Selector Contracts

**Files:**
- Create: `tests/test_system/test_theme_foundation_styles.py`
- Modify: `tests/test_system/test_plugin_ui_bridge.py`
- Test: `tests/test_system/test_theme_foundation_styles.py`
- Test: `tests/test_system/test_plugin_ui_bridge.py`

- [ ] **Step 1: Write the failing tests**

```python
from unittest.mock import Mock

from system.theme import ThemeManager


def _build_theme_manager():
    config = Mock()
    config.get.return_value = "dark"
    ThemeManager._instance = None
    return ThemeManager.instance(config)


def test_theme_manager_exposes_foundation_popup_helpers():
    tm = _build_theme_manager()

    completer_qss = tm.get_themed_completer_popup_style()
    popup_qss = tm.get_themed_popup_surface_style()

    assert "#121212" in completer_qss or "#282828" in completer_qss
    assert "QListView" in completer_qss
    assert "popupSurface" in popup_qss
    assert tm.current_theme.highlight in completer_qss


def test_theme_manager_global_stylesheet_covers_foundation_selectors(qapp):
    tm = _build_theme_manager()

    tm.apply_global_stylesheet()
    stylesheet = qapp.styleSheet()

    assert "QLineEdit" in stylesheet
    assert "QCheckBox::indicator" in stylesheet
    assert "QGroupBox" in stylesheet
    assert "QComboBox" in stylesheet
    assert "QDialog[shell=\"true\"]" in stylesheet
    assert "QWidget#dialogTitleBar" in stylesheet
```

```python
def test_plugin_context_ui_bridge_exposes_foundation_theme_helpers(tmp_path: Path):
    config = Mock()
    config.get.return_value = "dark"
    config.get_language.return_value = "zh"

    ThemeManager._instance = None
    ThemeManager.instance(config)

    registry = Mock()
    bootstrap = SimpleNamespace(
        _plugin_manager=SimpleNamespace(registry=registry),
        online_download_service=Mock(),
        playback_service=Mock(),
        library_service=Mock(),
        http_client=Mock(),
        event_bus=Mock(),
        config=config,
    )
    manifest = PluginManifest.from_dict(
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "api_version": "1",
            "entrypoint": "plugin_main.py",
            "entry_class": "QQMusicPlugin",
            "capabilities": ["sidebar"],
            "min_app_version": "0.1.0",
        }
    )

    context = BootstrapPluginContextFactory(bootstrap, tmp_path).build(manifest)

    assert callable(context.ui.theme.get_popup_surface_style)
    assert callable(context.ui.theme.get_completer_popup_style)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system/test_theme_foundation_styles.py tests/test_system/test_plugin_ui_bridge.py -v`
Expected: FAIL with `AttributeError` for missing theme helper methods and/or missing foundation selectors in the application stylesheet

- [ ] **Step 3: Write minimal implementation**

```python
class ThemeManager(QObject):
    @staticmethod
    def get_completer_popup_style() -> str:
        return """
            QListView {
                background-color: %background_alt%;
                border: 1px solid %border%;
                color: %text%;
                selection-background-color: %highlight%;
                selection-color: %background%;
                outline: none;
            }
            QListView::item {
                padding: 8px 12px;
            }
        """

    @staticmethod
    def get_popup_surface_style() -> str:
        return """
            QWidget[popupSurface="true"] {
                background-color: %background_alt%;
                border: 1px solid %border%;
                border-radius: 10px;
                color: %text%;
            }
        """

    def get_themed_completer_popup_style(self) -> str:
        return self.get_qss(self.get_completer_popup_style())

    def get_themed_popup_surface_style(self) -> str:
        return self.get_qss(self.get_popup_surface_style())
```

```python
class PluginThemeBridgeImpl:
    def get_popup_surface_style(self) -> str:
        from system.theme import ThemeManager
        return ThemeManager.instance().get_themed_popup_surface_style()

    def get_completer_popup_style(self) -> str:
        from system.theme import ThemeManager
        return ThemeManager.instance().get_themed_completer_popup_style()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_system/test_theme_foundation_styles.py tests/test_system/test_plugin_ui_bridge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_system/test_theme_foundation_styles.py tests/test_system/test_plugin_ui_bridge.py system/theme.py system/plugins/plugin_sdk_ui.py
git commit -m "统一主题基础样式接口"
```

## Task 2: Expand The Global Foundation Stylesheet

**Files:**
- Modify: `ui/styles.qss`
- Modify: `system/theme.py`
- Test: `tests/test_system/test_theme_foundation_styles.py`

- [ ] **Step 1: Write the failing test for concrete foundation selectors**

```python
def test_theme_manager_global_stylesheet_includes_wrapper_variants(qapp):
    tm = _build_theme_manager()

    tm.apply_global_stylesheet()
    stylesheet = qapp.styleSheet()

    assert "QPushButton[role=\"primary\"]" in stylesheet
    assert "QLineEdit[variant=\"search\"]" in stylesheet
    assert "QComboBox[compact=\"true\"]" in stylesheet
    assert "QWidget#titleBar" in stylesheet
    assert "QPushButton#winBtn" in stylesheet
    assert "QPushButton#dialogCloseBtn" in stylesheet
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system/test_theme_foundation_styles.py::test_theme_manager_global_stylesheet_includes_wrapper_variants -v`
Expected: FAIL because the current `ui/styles.qss` does not yet define the required wrapper and variant selectors

- [ ] **Step 3: Write minimal stylesheet expansion**

```css
QDialog[shell="true"] {
    background-color: %background_alt%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 12px;
}

QLineEdit,
QTextEdit {
    background-color: %background_hover%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 8px;
    padding: 8px 12px;
}

QLineEdit[variant="search"] {
    padding-right: 30px;
}

QCheckBox,
QRadioButton,
QGroupBox,
QComboBox,
QSpinBox,
QProgressBar,
QMenu,
QWidget#titleBar,
QWidget#dialogTitleBar,
QPushButton#winBtn,
QPushButton#closeBtn,
QPushButton#dialogCloseBtn {
    color: %text%;
}

QPushButton#winBtn,
QPushButton#closeBtn,
QPushButton#dialogCloseBtn {
    background: transparent;
    border: none;
    min-width: 28px;
    min-height: 28px;
    border-radius: 6px;
}

QWidget#dialogTitleBar {
    background-color: %background_alt%;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid %border%;
}
```

```python
def apply_global_stylesheet(self):
    app = QApplication.instance()
    if not app:
        return

    if self._global_qss_template is None:
        qss_path = Path(__file__).parent.parent / "ui" / "styles.qss"
        self._global_qss_template = qss_path.read_text(encoding="utf-8")

    themed_qss = self.get_qss(self._global_qss_template)
    themed_qss += "\n" + self.get_themed_popup_surface_style()
    app.setStyleSheet(themed_qss)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_system/test_theme_foundation_styles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/styles.qss system/theme.py tests/test_system/test_theme_foundation_styles.py
git commit -m "扩展全局基础控件主题样式"
```

## Task 3: Refactor Shared Host Wrappers To Theme-Owned Styling

**Files:**
- Create: `tests/test_ui/test_dialog_title_bar.py`
- Modify: `tests/test_title_bar.py`
- Modify: `ui/dialogs/dialog_title_bar.py`
- Modify: `ui/widgets/title_bar.py`
- Modify: `ui/widgets/toggle_switch.py`
- Modify: `ui/widgets/context_menus.py`
- Modify: `ui/views/cover_hover_popup.py`
- Modify: `ui/views/queue_view.py`

- [ ] **Step 1: Write the failing wrapper tests**

```python
from PySide6.QtWidgets import QDialog, QVBoxLayout

from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout


def test_dialog_title_bar_uses_global_theme_selectors(qtbot):
    dialog = QDialog()
    qtbot.addWidget(dialog)
    container = QVBoxLayout(dialog)

    _, controller = setup_equalizer_title_layout(dialog, container, "Title")

    assert controller.title_bar.objectName() == "dialogTitleBar"
    assert controller.title_label.objectName() == "dialogTitle"
    assert controller.close_btn.objectName() == "dialogCloseBtn"
    assert controller.title_bar.styleSheet() == ""
    assert controller.close_btn.styleSheet() == ""
```

```python
def test_title_bar_relies_on_object_names_instead_of_local_qss(qtbot, patch_theme):
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    qtbot.addWidget(window)
    bar = TitleBar(window)

    assert bar.objectName() == "titleBar"
    assert bar._btn_min.objectName() == "winBtn"
    assert bar._btn_close.objectName() == "closeBtn"
    assert bar.styleSheet() == ""
```

```python
def test_local_track_context_menu_uses_theme_owned_qmenu_styles(qtbot):
    menu = LocalTrackContextMenu().build_menu([], set())
    assert menu is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_dialog_title_bar.py tests/test_title_bar.py -v`
Expected: FAIL because shared title bars and wrappers still set local QSS templates directly

- [ ] **Step 3: Write minimal wrapper refactor**

```python
@dataclass
class DialogTitleBarController:
    dialog: QDialog
    title_bar: QWidget
    title_label: QLabel
    close_btn: QPushButton

    def refresh_theme(self):
        self.close_btn.setIcon(get_icon(IconName.TIMES, None, 14))
        for widget in (self.title_bar, self.title_label, self.close_btn):
            style = widget.style()
            if style is not None:
                style.unpolish(widget)
                style.polish(widget)
```

```python
class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self._title_label.setObjectName("titleLabel")
        self._btn_min.setObjectName("winBtn")
        self._btn_max.setObjectName("winBtn")
        self._btn_close.setObjectName("closeBtn")

    def refresh_theme(self):
        self._btn_min.setIcon(get_icon(IconName.MINIMIZE, None, 14))
        self._btn_max.setIcon(get_icon(IconName.MAXIMIZE, None, 14))
        self._btn_close.setIcon(get_icon(IconName.TIMES, None, 14))
        for widget in (self, self._title_label, self._btn_min, self._btn_max, self._btn_close):
            style = widget.style()
            if style is not None:
                style.unpolish(widget)
                style.polish(widget)
```

```python
class ToggleSwitch(QWidget):
    def refresh_theme(self):
        theme = ThemeManager.instance().current_theme
        self.bg_on = QColor(theme.highlight)
        self.bg_off = QColor(theme.border)
        self.bg_disabled = QColor(theme.background_hover)
        self.update()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_dialog_title_bar.py tests/test_title_bar.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui/test_dialog_title_bar.py tests/test_title_bar.py ui/dialogs/dialog_title_bar.py ui/widgets/title_bar.py ui/widgets/toggle_switch.py ui/widgets/context_menus.py ui/views/cover_hover_popup.py ui/views/queue_view.py
git commit -m "收敛宿主共享组件主题样式"
```

## Task 4: Remove Host Feature-Level Foundation QSS Overrides

**Files:**
- Create: `tests/test_ui/test_foundation_theme_cleanup.py`
- Modify: `ui/dialogs/base_rename_dialog.py`
- Modify: `ui/dialogs/input_dialog.py`
- Modify: `ui/dialogs/settings_dialog.py`
- Modify: `ui/dialogs/edit_media_info_dialog.py`
- Modify: `ui/dialogs/lyrics_download_dialog.py`
- Modify: `ui/dialogs/base_cover_download_dialog.py`
- Modify: `ui/views/library_view.py`
- Modify: `ui/views/albums_view.py`
- Modify: `ui/views/artists_view.py`
- Modify: `ui/views/genres_view.py`
- Modify: `ui/views/cloud/cloud_drive_view.py`
- Modify: `ui/widgets/equalizer_widget.py`

- [ ] **Step 1: Write the failing cleanup tests**

```python
from unittest.mock import Mock

from system.theme import ThemeManager
from ui.dialogs.input_dialog import InputDialog
from ui.views.albums_view import AlbumsView


def test_input_dialog_marks_shell_and_uses_unstyled_foundation_children(qtbot):
    config = Mock()
    config.get.return_value = "dark"
    ThemeManager._instance = None
    ThemeManager.instance(config)

    dialog = InputDialog("Title", "Prompt", "value")
    qtbot.addWidget(dialog)

    assert dialog.property("shell") is True
    assert dialog._input.styleSheet() == ""


def test_albums_view_search_input_uses_theme_variant_instead_of_local_qss(qtbot, mock_theme_config):
    ThemeManager._instance = None
    ThemeManager.instance(mock_theme_config)
    view = AlbumsView()
    qtbot.addWidget(view)

    assert view._search_input.property("variant") == "search"
    assert view._search_input.styleSheet() == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_foundation_theme_cleanup.py -v`
Expected: FAIL because dialogs and views still assign local `QLineEdit`, `QComboBox`, `QCheckBox`, `QGroupBox`, and shell styles

- [ ] **Step 3: Write minimal host cleanup**

```python
self.setProperty("shell", True)
self._input.setProperty("variant", "form")
self._search_input.setProperty("variant", "search")
self._quality_combo.setProperty("variant", "settings")
self._effects_enabled_checkbox.setProperty("variant", "settings")
self._effects_group.setProperty("variant", "settings")
```

```python
def refresh_theme(self):
    for widget in (
        self,
        self._input,
        self._search_input,
        self._quality_combo,
        self._effects_enabled_checkbox,
        self._effects_group,
    ):
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_foundation_theme_cleanup.py tests/test_ui/test_cover_download_dialog.py tests/test_ui/test_equalizer_widget.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui/test_foundation_theme_cleanup.py ui/dialogs/base_rename_dialog.py ui/dialogs/input_dialog.py ui/dialogs/settings_dialog.py ui/dialogs/edit_media_info_dialog.py ui/dialogs/lyrics_download_dialog.py ui/dialogs/base_cover_download_dialog.py ui/views/library_view.py ui/views/albums_view.py ui/views/artists_view.py ui/views/genres_view.py ui/views/cloud/cloud_drive_view.py ui/widgets/equalizer_widget.py
git commit -m "移除页面级基础控件样式重复定义"
```

## Task 5: Unify Plugin Foundation Styles Through The Host Theme Bridge

**Files:**
- Modify: `system/plugins/plugin_sdk_ui.py`
- Modify: `plugins/builtin/qqmusic/lib/runtime_bridge.py`
- Modify: `plugins/builtin/qqmusic/lib/dialog_title_bar.py`
- Modify: `plugins/builtin/qqmusic/lib/login_dialog.py`
- Modify: `plugins/builtin/qqmusic/lib/settings_tab.py`
- Modify: `plugins/builtin/qqmusic/lib/online_music_view.py`
- Modify: `plugins/builtin/qqmusic/lib/context_menus.py`
- Modify: `plugins/builtin/qqmusic/lib/cover_hover_popup.py`
- Modify: `tests/test_plugins/test_qqmusic_plugin.py`

- [ ] **Step 1: Write the failing plugin tests**

```python
def test_root_view_search_input_uses_theme_variant_and_host_popup_helpers(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "search_history": [],
        "ranking_view_mode": "table",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    assert view._search_input.property("variant") == "search"
    assert view._search_input.styleSheet() == ""
    assert view._completer.popup().styleSheet()
```

```python
def test_login_dialog_uses_host_owned_dialog_title_bar_and_shell_property(qtbot):
    context = Mock()
    dialog = QQMusicLoginDialog(context)
    qtbot.addWidget(dialog)

    assert dialog.property("shell") is True
    assert dialog._title_bar_controller.title_bar.styleSheet() == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py::test_root_view_search_input_uses_theme_variant_and_host_popup_helpers tests/test_plugins/test_qqmusic_plugin.py::test_login_dialog_uses_host_owned_dialog_title_bar_and_shell_property -v`
Expected: FAIL because plugin UI still embeds local `QLineEdit`, `QComboBox`, popup, and dialog title bar templates

- [ ] **Step 3: Write minimal plugin bridge refactor**

```python
def get_popup_surface_style() -> str:
    return _ui_module().get_popup_surface_style()


def get_completer_popup_style() -> str:
    return _ui_module().get_completer_popup_style()
```

```python
class CustomQCompleter(QCompleter):
    def _apply_theme(self):
        self.popup().setStyleSheet(get_completer_popup_style())
```

```python
self.setProperty("shell", True)
self._search_input.setProperty("variant", "search")
self._combo.setProperty("variant", "settings")
self.setProperty("popupSurface", True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add system/plugins/plugin_sdk_ui.py plugins/builtin/qqmusic/lib/runtime_bridge.py plugins/builtin/qqmusic/lib/dialog_title_bar.py plugins/builtin/qqmusic/lib/login_dialog.py plugins/builtin/qqmusic/lib/settings_tab.py plugins/builtin/qqmusic/lib/online_music_view.py plugins/builtin/qqmusic/lib/context_menus.py plugins/builtin/qqmusic/lib/cover_hover_popup.py tests/test_plugins/test_qqmusic_plugin.py
git commit -m "统一插件基础控件主题入口"
```

## Task 6: Focused And Broad Verification

**Files:**
- Test: `tests/test_system/test_theme_foundation_styles.py`
- Test: `tests/test_ui/test_dialog_title_bar.py`
- Test: `tests/test_ui/test_foundation_theme_cleanup.py`
- Test: `tests/test_system/test_plugin_ui_bridge.py`
- Test: `tests/test_plugins/test_qqmusic_plugin.py`

- [ ] **Step 1: Run focused verification**

Run: `uv run pytest tests/test_system/test_theme_foundation_styles.py tests/test_ui/test_dialog_title_bar.py tests/test_ui/test_foundation_theme_cleanup.py tests/test_system/test_plugin_ui_bridge.py tests/test_plugins/test_qqmusic_plugin.py -v`
Expected: PASS

- [ ] **Step 2: Run regression coverage for nearby UI surfaces**

Run: `uv run pytest tests/test_ui/test_cover_download_dialog.py tests/test_ui/test_equalizer_widget.py tests/test_ui/test_online_music_view_focus.py tests/test_ui/test_plugin_settings_tab.py -v`
Expected: PASS

- [ ] **Step 3: Run lint on touched files**

Run: `uv run ruff check system/theme.py system/plugins/plugin_sdk_ui.py ui/dialogs/dialog_title_bar.py ui/widgets/title_bar.py ui/widgets/toggle_switch.py ui/widgets/context_menus.py ui/views/cover_hover_popup.py ui/dialogs/base_rename_dialog.py ui/dialogs/input_dialog.py ui/dialogs/settings_dialog.py ui/dialogs/edit_media_info_dialog.py ui/dialogs/lyrics_download_dialog.py ui/dialogs/base_cover_download_dialog.py ui/views/library_view.py ui/views/albums_view.py ui/views/artists_view.py ui/views/genres_view.py ui/views/cloud/cloud_drive_view.py ui/widgets/equalizer_widget.py plugins/builtin/qqmusic/lib/runtime_bridge.py plugins/builtin/qqmusic/lib/dialog_title_bar.py plugins/builtin/qqmusic/lib/login_dialog.py plugins/builtin/qqmusic/lib/settings_tab.py plugins/builtin/qqmusic/lib/online_music_view.py plugins/builtin/qqmusic/lib/context_menus.py plugins/builtin/qqmusic/lib/cover_hover_popup.py`
Expected: PASS

- [ ] **Step 4: Review diff**

Run: `git diff --stat HEAD~5..HEAD`
Expected: only theme-system, host wrapper, host view cleanup, plugin bridge, and related test files are present

- [ ] **Step 5: Commit final verification if needed**

```bash
git add tests/test_system/test_theme_foundation_styles.py tests/test_ui/test_dialog_title_bar.py tests/test_ui/test_foundation_theme_cleanup.py tests/test_system/test_plugin_ui_bridge.py tests/test_plugins/test_qqmusic_plugin.py
git commit -m "验证统一基础主题样式改造"
```
