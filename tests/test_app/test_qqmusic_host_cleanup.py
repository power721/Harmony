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
    assert not Path("services/online/download_service.py").exists()


def test_host_qqmusic_compatibility_view_modules_are_removed():
    for relative_path in (
        "ui/views/online_music_view.py",
        "ui/views/legacy_online_music_view.py",
        "ui/views/online_detail_view.py",
        "ui/views/online_grid_view.py",
        "ui/views/online_tracks_list_view.py",
    ):
        assert not Path(relative_path).exists(), relative_path


def test_host_qqmusic_runtime_helpers_are_removed():
    assert not Path("system/plugins/qqmusic_runtime_helpers.py").exists()


def test_plugin_root_view_module_has_been_removed():
    assert not Path("plugins/builtin/qqmusic/lib/root_view.py").exists()


def test_plugin_provider_now_uses_plugin_online_music_view_entry():
    source = Path("plugins/builtin/qqmusic/lib/provider.py").read_text(encoding="utf-8")

    assert "from .online_music_view import OnlineMusicView" in source
    assert "from .root_view import QQMusicRootView" not in source
    assert "return OnlineMusicView(" in source


def test_online_track_context_menu_lives_in_plugin_module():
    source = Path("ui/widgets/context_menus.py").read_text(encoding="utf-8")

    assert "plugins.builtin.qqmusic.lib.context_menus" not in source


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
        "plugins/builtin/qqmusic/lib/settings_tab.py",
    ):
        source = Path(relative_path).read_text(encoding="utf-8")
        assert "system.i18n" not in source
        assert "from .i18n import" in source or "from .i18n import t" in source


def test_qqmusic_plugin_no_longer_imports_host_online_models_or_widgets():
    for relative_path in (
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
    bootstrap_source = Path("app/bootstrap.py").read_text(encoding="utf-8")

    assert not Path("services/online/online_music_service.py").exists()
    assert not Path("services/online/download_service.py").exists()
    assert "qqmusic_service" not in bootstrap_source


def test_online_services_no_longer_store_private_qqmusic_field_names():
    assert not Path("services/online/online_music_service.py").exists()
    assert not Path("services/online/download_service.py").exists()


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
        "plugins/builtin/qqmusic/lib/online_detail_view.py",
        "plugins/builtin/qqmusic/lib/online_grid_view.py",
        "plugins/builtin/qqmusic/lib/online_music_view.py",
        "plugins/builtin/qqmusic/lib/online_tracks_list_view.py",
        "plugins/builtin/qqmusic/lib/login_dialog.py",
        "plugins/builtin/qqmusic/lib/settings_tab.py",
    ):
        source = Path(relative_path).read_text(encoding="utf-8")
        assert not any(prefix in source for prefix in forbidden_prefixes), relative_path


def test_qqmusic_plugin_legacy_directory_is_removed():
    assert not Path("plugins/builtin/qqmusic/lib/legacy").exists()


def test_qqmusic_plugin_modules_do_not_import_legacy_package():
    for path in Path("plugins/builtin/qqmusic/lib").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "from .legacy import" not in source, str(path)
        assert "from .legacy." not in source, str(path)
        assert "import .legacy" not in source, str(path)


def test_host_quality_modules_are_removed():
    assert not Path("services/download/quality.py").exists()
    assert not Path("services/online/quality.py").exists()


def test_online_download_gateway_no_longer_contains_host_http_download_logic():
    source = Path("services/download/online_download_gateway.py").read_text(encoding="utf-8")

    assert "HttpClient" not in source
    assert "get_playback_url_info" not in source
    assert "download_track(" in source


def test_download_manager_redownload_entry_is_provider_driven():
    source = Path("services/download/download_manager.py").read_text(encoding="utf-8")

    assert "def redownload_online_track(" in source
    assert "provider_id" in source
    assert "TrackSource.QQ" not in source
