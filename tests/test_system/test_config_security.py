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


def test_qqmusic_credential_is_encrypted_at_rest(tmp_path):
    """QQ Music secrets should be encrypted when persisted."""
    repo = _FakeSettingsRepository()
    config = ConfigManager(repo, secret_store=SecretStore(tmp_path / "secret.key"))
    credential = {
        "musicid": "12345",
        "musickey": "qq-secret",
        "refresh_token": "refresh-secret",
        "login_type": 2,
    }

    config.set_qqmusic_credential(credential)

    assert repo.values[SettingKey.QQMUSIC_CREDENTIAL] != credential
    assert repo.values[SettingKey.QQMUSIC_MUSICKEY] != "qq-secret"
    assert config.get_qqmusic_credential()["musickey"] == "qq-secret"
    assert config.get_qqmusic_credential()["refresh_token"] == "refresh-secret"


def test_qqmusic_credential_keeps_legacy_plaintext_compatible(tmp_path):
    """Legacy plaintext settings should still be readable during migration."""
    repo = _FakeSettingsRepository()
    repo.values[SettingKey.QQMUSIC_MUSICID] = "legacy-id"
    repo.values[SettingKey.QQMUSIC_MUSICKEY] = "legacy-key"
    repo.values[SettingKey.QQMUSIC_LOGIN_TYPE] = 2

    config = ConfigManager(repo, secret_store=SecretStore(tmp_path / "secret.key"))

    credential = config.get_qqmusic_credential()

    assert credential["musicid"] == "legacy-id"
    assert credential["musickey"] == "legacy-key"


def test_plugin_settings_are_namespaced(tmp_path):
    repo = _FakeSettingsRepository()
    config = ConfigManager(repo, secret_store=SecretStore(tmp_path / "secret.key"))

    config.set_plugin_setting("qqmusic", "quality", "flac")

    assert repo.values["plugins.qqmusic.quality"] == "flac"
    assert config.get_plugin_setting("qqmusic", "quality") == "flac"
