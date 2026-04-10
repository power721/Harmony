"""Security-focused tests for ConfigManager secret handling."""

from infrastructure.security.secret_store import SecretStore
from system.config import ConfigManager, SettingKey


class _FakeSettingsRepository:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value
        return True

    def delete(self, key):
        self.values.pop(key, None)
        return True


def test_ai_api_key_is_encrypted_at_rest(tmp_path):
    """AI API keys should not be stored in plaintext."""
    repo = _FakeSettingsRepository()
    config = ConfigManager(repo, secret_store=SecretStore(tmp_path / "secret.key"))

    config.set_ai_api_key("ai-secret")

    assert repo.values[SettingKey.AI_API_KEY] != "ai-secret"
    assert config.get_ai_api_key() == "ai-secret"


def test_acoustid_api_key_is_encrypted_at_rest(tmp_path):
    """AcoustID keys should not be stored in plaintext."""
    repo = _FakeSettingsRepository()
    config = ConfigManager(repo, secret_store=SecretStore(tmp_path / "secret.key"))

    config.set_acoustid_api_key("acoustid-secret")

    assert repo.values[SettingKey.ACOUSTID_API_KEY] != "acoustid-secret"
    assert config.get_acoustid_api_key() == "acoustid-secret"


def test_plugin_settings_are_namespaced(tmp_path):
    repo = _FakeSettingsRepository()
    config = ConfigManager(repo, secret_store=SecretStore(tmp_path / "secret.key"))

    config.set_plugin_setting("qqmusic", "quality", "flac")

    assert repo.values["plugins.qqmusic.quality"] == "flac"
    assert config.get_plugin_setting("qqmusic", "quality") == "flac"


def test_plugin_secret_is_encrypted_at_rest(tmp_path):
    repo = _FakeSettingsRepository()
    config = ConfigManager(repo, secret_store=SecretStore(tmp_path / "secret.key"))

    config.set_plugin_secret("qqmusic", "credential", '{"musicid":"1","musickey":"secret"}')

    assert repo.values["plugins.qqmusic.credential"] != '{"musicid":"1","musickey":"secret"}'
    assert config.get_plugin_secret("qqmusic", "credential") == '{"musicid":"1","musickey":"secret"}'


def test_config_manager_no_longer_exposes_qqmusic_specific_helpers(tmp_path):
    repo = _FakeSettingsRepository()
    config = ConfigManager(repo, secret_store=SecretStore(tmp_path / "secret.key"))

    assert not hasattr(config, "get_qqmusic_credential")
    assert not hasattr(config, "set_qqmusic_credential")
    assert not hasattr(config, "clear_qqmusic_credential")
    assert not hasattr(config, "get_qqmusic_nick")
    assert not hasattr(config, "set_qqmusic_nick")
    assert not hasattr(config, "get_qqmusic_quality")
    assert not hasattr(config, "set_qqmusic_quality")


def test_set_volume_clamps_to_valid_range(tmp_path):
    repo = _FakeSettingsRepository()
    config = ConfigManager(repo, secret_store=SecretStore(tmp_path / "secret.key"))

    config.set_volume(150)
    assert repo.values[SettingKey.PLAYER_VOLUME] == 100

    config.set_volume(-10)
    assert repo.values[SettingKey.PLAYER_VOLUME] == 0


def test_set_audio_effects_clamps_effect_values_and_normalizes_bands(tmp_path):
    repo = _FakeSettingsRepository()
    config = ConfigManager(repo, secret_store=SecretStore(tmp_path / "secret.key"))

    config.set_audio_effects(
        {
            "enabled": True,
            "eq_bands": [1, "2.5", "bad"],
            "bass_boost": 150,
            "treble_boost": -20,
            "reverb_level": 75.5,
            "stereo_enhance": 300,
        }
    )

    effects = config.get_audio_effects()
    assert len(effects["eq_bands"]) == 10
    assert effects["eq_bands"][:3] == [1.0, 2.5, 0.0]
    assert effects["bass_boost"] == 100.0
    assert effects["treble_boost"] == 0.0
    assert effects["reverb_level"] == 75.5
    assert effects["stereo_enhance"] == 100.0
