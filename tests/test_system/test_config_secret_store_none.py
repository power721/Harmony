from system.config import ConfigManager


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


def test_get_secret_falls_back_to_plain_value_when_secret_store_missing():
    repo = _FakeSettingsRepository()
    repo.values["ai.api_key"] = "plain-secret"
    config = ConfigManager(repo, secret_store=None)
    config._secret_store = None

    assert config._get_secret("ai.api_key") == "plain-secret"
