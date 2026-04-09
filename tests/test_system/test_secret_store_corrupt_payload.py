from infrastructure.security.secret_store import SecretStore


def test_decrypt_returns_empty_string_for_corrupt_ciphertext(tmp_path):
    store = SecretStore(tmp_path / "secret.key")

    assert store.decrypt(f"{SecretStore.PREFIX}!!!") == ""
