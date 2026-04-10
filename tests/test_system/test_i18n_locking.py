import system.i18n as i18n


class _LockCheckingTranslations(dict):
    def __contains__(self, key):
        assert i18n._state_lock.locked()
        return super().__contains__(key)

    def __getitem__(self, key):
        assert i18n._state_lock.locked()
        return super().__getitem__(key)


def test_translate_reads_language_state_under_lock(monkeypatch):
    monkeypatch.setattr(
        i18n,
        "_translations",
        _LockCheckingTranslations({"en": {"hello": "Hello"}}),
    )
    monkeypatch.setattr(i18n, "_current_language", "en")

    assert i18n.t("hello") == "Hello"


def test_set_language_logs_invalid_language_fallback(caplog, monkeypatch):
    monkeypatch.setattr(i18n, "_current_language", "zh")

    i18n.set_language("fr")

    assert i18n.get_language() == "en"
    assert "Invalid language" in caplog.text
