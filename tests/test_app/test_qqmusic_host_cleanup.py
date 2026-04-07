from pathlib import Path


def test_main_entry_no_longer_mentions_qqmusic_api():
    source = Path("main.py").read_text(encoding="utf-8")

    assert "QQMusicApiCachePathInjector" not in source
    assert "qqmusic_api.utils.device" not in source


def test_packaging_scripts_no_longer_collect_qqmusic_api():
    build_source = Path("build.py").read_text(encoding="utf-8")
    release_source = Path("release.sh").read_text(encoding="utf-8")

    assert "qqmusic_api" not in build_source
    assert "qqmusic_api" not in release_source


def test_online_download_service_no_longer_imports_plugin_qqmusic_impl():
    source = Path("services/online/download_service.py").read_text(encoding="utf-8")

    assert "plugins.builtin.qqmusic" not in source


def test_online_music_view_is_legacy_compat_shim():
    source = Path("ui/views/online_music_view.py").read_text(encoding="utf-8")

    assert "legacy_online_music_view" in source
    assert "Compatibility shim" in source


def test_legacy_online_music_view_is_now_a_plugin_compat_shim():
    source = Path("ui/views/legacy_online_music_view.py").read_text(encoding="utf-8")

    assert "plugins.builtin.qqmusic.lib.online_music_view" in source
    assert "Compatibility shim" in source


def test_host_online_views_are_plugin_compat_shims():
    for relative_path in (
        "ui/views/online_detail_view.py",
        "ui/views/online_grid_view.py",
        "ui/views/online_tracks_list_view.py",
    ):
        source = Path(relative_path).read_text(encoding="utf-8")

        assert "plugins.builtin.qqmusic.lib" in source
        assert "Compatibility shim" in source


def test_plugin_root_view_uses_plugin_local_online_views():
    source = Path("plugins/builtin/qqmusic/lib/root_view.py").read_text(encoding="utf-8")

    assert "from .online_grid_view import OnlineGridView" in source
    assert "from .online_tracks_list_view import OnlineTracksListView" in source
    assert "from ui.views.online_grid_view import OnlineGridView" not in source
    assert "from ui.views.online_tracks_list_view import OnlineTracksListView" not in source


def test_plugin_provider_now_uses_legacy_online_music_view_entry():
    source = Path("plugins/builtin/qqmusic/lib/provider.py").read_text(encoding="utf-8")

    assert "from .online_music_view import OnlineMusicView" in source
    assert "from .root_view import QQMusicRootView" not in source
    assert "return OnlineMusicView(" in source


def test_online_track_context_menu_lives_in_plugin_module():
    source = Path("ui/widgets/context_menus.py").read_text(encoding="utf-8")

    assert "plugins.builtin.qqmusic.lib.context_menus" in source
    assert "class OnlineTrackContextMenu" not in source


def test_qqmusic_plugin_has_private_translation_files():
    assert Path("plugins/builtin/qqmusic/translations/en.json").exists()
    assert Path("plugins/builtin/qqmusic/translations/zh.json").exists()


def test_qqmusic_plugin_modules_use_plugin_local_i18n():
    for relative_path in (
        "plugins/builtin/qqmusic/lib/context_menus.py",
        "plugins/builtin/qqmusic/lib/login_dialog.py",
        "plugins/builtin/qqmusic/lib/online_detail_view.py",
        "plugins/builtin/qqmusic/lib/online_grid_view.py",
        "plugins/builtin/qqmusic/lib/online_music_view.py",
        "plugins/builtin/qqmusic/lib/online_tracks_list_view.py",
        "plugins/builtin/qqmusic/lib/root_view.py",
        "plugins/builtin/qqmusic/lib/settings_tab.py",
    ):
        source = Path(relative_path).read_text(encoding="utf-8")
        assert "system.i18n" not in source
        assert "from .i18n import" in source or "from .i18n import t" in source


def test_qqmusic_plugin_no_longer_imports_host_online_models_or_widgets():
    for relative_path in (
        "plugins/builtin/qqmusic/lib/root_view.py",
        "plugins/builtin/qqmusic/lib/online_music_view.py",
        "plugins/builtin/qqmusic/lib/online_detail_view.py",
        "plugins/builtin/qqmusic/lib/online_grid_view.py",
        "plugins/builtin/qqmusic/lib/online_tracks_list_view.py",
    ):
        source = Path(relative_path).read_text(encoding="utf-8")
        assert "domain.online_music" not in source
        assert "ui.widgets.recommend_card" not in source
        assert "ui.views.cover_hover_popup" not in source


def test_online_services_no_longer_expose_qqmusic_service_parameter_names():
    online_service_source = Path("services/online/online_music_service.py").read_text(encoding="utf-8")
    download_service_source = Path("services/online/download_service.py").read_text(encoding="utf-8")
    bootstrap_source = Path("app/bootstrap.py").read_text(encoding="utf-8")

    assert "qqmusic_service" not in online_service_source
    assert "qqmusic_service" not in download_service_source
    assert "qqmusic_service" not in bootstrap_source


def test_online_services_no_longer_store_private_qqmusic_field_names():
    online_service_source = Path("services/online/online_music_service.py").read_text(encoding="utf-8")
    download_service_source = Path("services/online/download_service.py").read_text(encoding="utf-8")

    assert "self._qqmusic =" not in online_service_source
    assert "self._qqmusic =" not in download_service_source


def test_plugin_page_modules_do_not_directly_import_host_layers():
    forbidden_prefixes = (
        "from app.",
        "import app.",
        "from domain",
        "import domain",
        "from infrastructure",
        "import infrastructure",
        "from services.",
        "import services.",
        "from system.",
        "import system.",
        "from ui.",
        "import ui.",
        "from utils",
        "import utils",
    )

    for relative_path in (
        "plugins/builtin/qqmusic/lib/context_menus.py",
        "plugins/builtin/qqmusic/lib/cover_hover_popup.py",
        "plugins/builtin/qqmusic/lib/recommend_card.py",
        "plugins/builtin/qqmusic/lib/root_view.py",
        "plugins/builtin/qqmusic/lib/online_detail_view.py",
        "plugins/builtin/qqmusic/lib/online_grid_view.py",
        "plugins/builtin/qqmusic/lib/online_music_view.py",
        "plugins/builtin/qqmusic/lib/online_tracks_list_view.py",
        "plugins/builtin/qqmusic/lib/login_dialog.py",
        "plugins/builtin/qqmusic/lib/settings_tab.py",
    ):
        source = Path(relative_path).read_text(encoding="utf-8")
        assert not any(prefix in source for prefix in forbidden_prefixes), relative_path
