from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QEvent, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QStackedWidget, QWidget

from plugins.builtin.qqmusic.lib.online_music_view import OnlineMusicView
from plugins.builtin.qqmusic.lib.provider import QQMusicOnlineProvider
from system.theme import ThemeManager
from ui.windows.components.sidebar import Sidebar
from ui.windows.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_theme_singleton():
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture
def mock_config():
    config = Mock()
    config.get.return_value = "dark"
    config.get_ai_enabled.return_value = False
    return config


def test_sidebar_can_add_plugin_entry(qapp, mock_config):
    ThemeManager.instance(mock_config)
    sidebar = Sidebar(config_manager=mock_config)

    sidebar.add_plugin_entry(page_index=200, title="QQ Music", icon_name="GLOBE", title_provider=lambda: "QQ 音乐")

    assert any(index == 200 for index, _button in sidebar._nav_buttons)
    plugin_button = next(button for index, button in sidebar._nav_buttons if index == 200)
    assert plugin_button.styleSheet()


def test_sidebar_refresh_texts_updates_plugin_entry_title_provider(qapp, mock_config):
    ThemeManager.instance(mock_config)
    sidebar = Sidebar(config_manager=mock_config)
    sidebar.add_plugin_entry(page_index=200, title="QQ Music", icon_name="GLOBE", title_provider=lambda: "QQ 音乐")

    sidebar.refresh_texts()

    plugin_button = next(button for index, button in sidebar._nav_buttons if index == 200)
    assert plugin_button.text() == "QQ 音乐"


def test_sidebar_can_add_plugin_entry_with_custom_icon_path(qapp, mock_config, tmp_path):
    ThemeManager.instance(mock_config)
    sidebar = Sidebar(config_manager=mock_config)
    icon_path = tmp_path / "qqmusic-icon.png"
    icon_path.write_bytes(b"not-a-real-png-but-qicon-can-handle-empty")

    sidebar.add_plugin_entry(
        page_index=201,
        title="QQ Music",
        icon_path=str(icon_path),
        title_provider=lambda: "QQ 音乐",
    )

    plugin_button = next(button for index, button in sidebar._nav_buttons if index == 201)
    assert plugin_button.property("plugin_icon_path") == str(icon_path)


def test_sidebar_custom_svg_plugin_icon_updates_when_checked(qapp, mock_config, tmp_path):
    ThemeManager.instance(mock_config)
    sidebar = Sidebar(config_manager=mock_config)
    icon_path = tmp_path / "qqmusic-icon.svg"
    icon_path.write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        "<path fill='#000' d='M4 4h16v16H4z'/></svg>",
        encoding="utf-8",
    )

    sidebar.add_plugin_entry(
        page_index=202,
        title="QQ Music",
        icon_path=str(icon_path),
        title_provider=lambda: "QQ 音乐",
    )

    plugin_button = next(button for index, button in sidebar._nav_buttons if index == 202)
    default_key = plugin_button.icon().cacheKey()

    plugin_button.setChecked(True)

    assert plugin_button.icon().cacheKey() != default_key


def test_sidebar_custom_svg_plugin_icon_updates_on_hover(qapp, mock_config, tmp_path):
    ThemeManager.instance(mock_config)
    sidebar = Sidebar(config_manager=mock_config)
    icon_path = tmp_path / "qqmusic-icon.svg"
    icon_path.write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        "<path fill='#000' d='M4 4h16v16H4z'/></svg>",
        encoding="utf-8",
    )

    sidebar.add_plugin_entry(
        page_index=203,
        title="QQ Music",
        icon_path=str(icon_path),
        title_provider=lambda: "QQ 音乐",
    )

    plugin_button = next(button for index, button in sidebar._nav_buttons if index == 203)
    default_key = plugin_button.icon().cacheKey()

    QApplication.sendEvent(plugin_button, QEvent(QEvent.Enter))

    hover_key = plugin_button.icon().cacheKey()
    QApplication.sendEvent(plugin_button, QEvent(QEvent.Leave))

    assert hover_key != default_key


def test_main_window_mounts_plugin_pages(qapp, mock_config):
    ThemeManager.instance(mock_config)
    window = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(window)
    window._stacked_widget = QStackedWidget()
    window._sidebar = Sidebar(config_manager=mock_config)

    bootstrap = Mock()
    bootstrap.plugin_manager.registry.sidebar_entries.return_value = [
        type(
            "Spec",
            (),
            {
                "plugin_id": "qqmusic",
                "entry_id": "qqmusic.sidebar",
                "title": "QQ Music",
                "order": 80,
                "icon_name": "GLOBE",
                "page_factory": staticmethod(
                    lambda _context, _parent: QLabel("QQ Music View")
                ),
            },
        )()
    ]

    with patch("ui.windows.main_window.Bootstrap.instance", return_value=bootstrap):
        window._mount_plugin_pages()

    assert "qqmusic" in window._plugin_page_keys.values()
    assert window._stacked_widget.count() == 1


def test_main_window_prewarms_plugin_page_during_mount(qapp, qtbot, mock_config):
    ThemeManager.instance(mock_config)
    window = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(window)
    window._stacked_widget = QStackedWidget()
    window._sidebar = Sidebar(config_manager=mock_config)
    window._library_view = Mock()
    window._plugin_prewarm_timer = None

    page_factory = Mock(return_value=QLabel("QQ Music View"))
    bootstrap = Mock()
    bootstrap.plugin_manager.registry.sidebar_entries.return_value = [
        type(
            "Spec",
            (),
            {
                "plugin_id": "qqmusic",
                "entry_id": "qqmusic.sidebar",
                "title": "QQ Music",
                "order": 80,
                "icon_name": "GLOBE",
                "icon_path": None,
                "page_factory": staticmethod(page_factory),
            },
        )()
    ]

    with patch("ui.windows.main_window.Bootstrap.instance", return_value=bootstrap):
        window._mount_plugin_pages()
        assert page_factory.call_count == 1

    assert window._plugin_pages[0].text() == "QQ Music View"


def test_main_window_passes_host_container_to_plugin_page_factory(qapp, mock_config):
    ThemeManager.instance(mock_config)
    window = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(window)
    window._stacked_widget = QStackedWidget()
    window._sidebar = Sidebar(config_manager=mock_config)
    window._plugin_page_loading = set()
    window._plugin_pages = {}

    captured = {}

    def _page_factory(_context, parent):
        captured["parent"] = parent
        return QLabel("QQ Music View")

    spec = type(
        "Spec",
        (),
        {
            "plugin_id": "qqmusic",
            "entry_id": "qqmusic.sidebar",
            "title": "QQ Music",
            "order": 80,
            "icon_name": "GLOBE",
            "icon_path": None,
            "page_factory": staticmethod(_page_factory),
        },
    )()

    host = QWidget(window)
    window._stacked_widget.addWidget(host)
    window._plugin_page_specs = {0: spec}

    with patch("ui.windows.main_window.Bootstrap.instance", return_value=Mock(plugin_manager=Mock())):
        window._ensure_plugin_page_loaded(0)

    assert captured["parent"] is host


def test_main_window_connects_plugin_online_music_signals(qapp, mock_config):
    ThemeManager.instance(mock_config)
    window = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(window)
    window._stacked_widget = QStackedWidget()
    window._sidebar = Sidebar(config_manager=mock_config)
    window._plugin_page_loading = set()
    window._plugin_pages = {}
    window._play_online_track = Mock()
    window._add_online_track_to_queue = Mock()
    window._insert_online_track_to_queue = Mock()
    window._add_multiple_online_tracks_to_queue = Mock()
    window._insert_multiple_online_tracks_to_queue = Mock()
    window._play_online_tracks = Mock()

    class _PluginPage(QWidget):
        play_online_track = Signal(str, str, object)
        add_to_queue = Signal(str, object)
        insert_to_queue = Signal(str, object)
        add_multiple_to_queue = Signal(list)
        insert_multiple_to_queue = Signal(list)
        play_online_tracks = Signal(int, list)

    page = _PluginPage()
    spec = type(
        "Spec",
        (),
        {
            "plugin_id": "qqmusic",
            "entry_id": "qqmusic.sidebar",
            "title": "QQ Music",
            "order": 80,
            "icon_name": None,
            "icon_path": None,
            "page_factory": staticmethod(lambda _context, _parent: page),
        },
    )()

    host = QWidget(window)
    window._stacked_widget.addWidget(host)
    window._plugin_page_specs = {0: spec}

    with patch("ui.windows.main_window.Bootstrap.instance", return_value=Mock(plugin_manager=Mock())):
        window._ensure_plugin_page_loaded(0)

    page.play_online_track.emit("mid-1", "/tmp/song.mp3", {"title": "Song 1"})
    page.add_to_queue.emit("mid-2", {"title": "Song 2"})
    page.insert_to_queue.emit("mid-3", {"title": "Song 3"})
    page.add_multiple_to_queue.emit([("mid-4", {"title": "Song 4"})])
    page.insert_multiple_to_queue.emit([("mid-5", {"title": "Song 5"})])
    page.play_online_tracks.emit(0, [("mid-6", {"title": "Song 6"})])

    window._play_online_track.assert_called_once_with("mid-1", "/tmp/song.mp3", {"title": "Song 1"})
    window._add_online_track_to_queue.assert_called_once_with("mid-2", {"title": "Song 2"})
    window._insert_online_track_to_queue.assert_called_once_with("mid-3", {"title": "Song 3"})
    window._add_multiple_online_tracks_to_queue.assert_called_once_with([("mid-4", {"title": "Song 4"})])
    window._insert_multiple_online_tracks_to_queue.assert_called_once_with([("mid-5", {"title": "Song 5"})])
    window._play_online_tracks.assert_called_once_with(0, [("mid-6", {"title": "Song 6"})])


def test_main_window_materializes_real_qqmusic_plugin_page(qapp, qtbot, mock_config):
    ThemeManager.instance(mock_config)
    window = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(window)
    window._stacked_widget = QStackedWidget()
    window._sidebar = Sidebar(config_manager=mock_config)
    window._plugin_page_loading = set()
    window._plugin_pages = {}

    settings = Mock()
    store = {
        "credential": "",
        "quality": "320",
        "search_history": [],
        "online_music_download_dir": "data/online_cache",
    }
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)
    context = Mock(settings=settings, logger=Mock())
    provider = QQMusicOnlineProvider(context)

    spec = type(
        "Spec",
        (),
        {
            "plugin_id": "qqmusic",
            "entry_id": "qqmusic.sidebar",
            "title": "QQ Music",
            "order": 80,
            "icon_name": None,
            "icon_path": None,
            "page_factory": staticmethod(lambda _context, parent: provider.create_page(context, parent)),
        },
    )()

    host = QWidget(window)
    window._stacked_widget.addWidget(host)
    window._plugin_page_specs = {0: spec}

    with patch("ui.windows.main_window.Bootstrap.instance", return_value=Mock(plugin_manager=Mock())):
        window._ensure_plugin_page_loaded(0)

    page = window._plugin_pages[0]

    assert isinstance(page, OnlineMusicView)

    page.close()


def test_main_window_passes_plugin_icon_path_to_sidebar(qapp, mock_config, tmp_path):
    ThemeManager.instance(mock_config)
    window = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(window)
    window._stacked_widget = QStackedWidget()
    window._sidebar = Mock()

    icon_path = tmp_path / "qqmusic-icon.png"
    icon_path.write_bytes(b"png")

    bootstrap = Mock()
    bootstrap.plugin_manager.registry.sidebar_entries.return_value = [
        type(
            "Spec",
            (),
            {
                "plugin_id": "qqmusic",
                "entry_id": "qqmusic.sidebar",
                "title": "QQ Music",
                "order": 80,
                "icon_name": None,
                "icon_path": str(icon_path),
                "page_factory": staticmethod(lambda _context, _parent: QLabel("QQ Music View")),
            },
        )()
    ]

    with patch("ui.windows.main_window.Bootstrap.instance", return_value=bootstrap):
        window._mount_plugin_pages()

    kwargs = window._sidebar.add_plugin_entry.call_args.kwargs
    assert kwargs["icon_path"] == str(icon_path)


def test_main_window_refreshes_plugin_pages_with_refresh_ui(qapp, mock_config):
    ThemeManager.instance(mock_config)
    window = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(window)
    window._plugin_pages = {10: Mock(refresh_ui=Mock()), 11: QLabel("static")}
    window._sidebar = Mock()
    window._lyrics_panel = Mock()
    window._player_controls = Mock()
    window._library_view = Mock()
    window._cloud_drive_view = Mock()
    window._playlist_view = Mock()
    window._queue_view = Mock()
    window._albums_view = Mock()
    window._artists_view = Mock()
    window._artist_view = Mock()
    window._album_view = Mock()
    window._genres_view = Mock()
    window._genre_view = Mock()
    window._title_bar = Mock()
    window._config = mock_config
    window.setWindowTitle = Mock()

    window._refresh_ui_texts()

    window._plugin_pages[10].refresh_ui.assert_called_once_with()


def test_main_window_show_event_schedules_plugin_page_prewarm(qapp, mock_config, monkeypatch):
    ThemeManager.instance(mock_config)
    window = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(window)
    window._plugin_page_specs = {10: Mock()}
    window._plugin_prewarm_scheduled = False
    window._plugin_prewarm_timer = None

    class _FakeTimer:
        def __init__(self, *_args, **_kwargs):
            self.started_with = None
            self._timeout = Mock(connect=Mock())

        @property
        def timeout(self):
            return self._timeout

        def setSingleShot(self, _value):
            return None

        def start(self, delay):
            self.started_with = delay

    monkeypatch.setattr("ui.windows.main_window.QTimer", _FakeTimer)

    window.showEvent(QShowEvent())

    assert window._plugin_prewarm_timer is not None
    assert window._plugin_prewarm_timer.started_with == 0
