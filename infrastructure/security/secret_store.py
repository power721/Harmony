"""Helpers for encrypting secrets before persisting them locally."""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from threading import Lock

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import platformdirs

logger = logging.getLogger(__name__)


class SecretStore:
    """Encrypt and decrypt small secrets using a local AES-GCM master key."""

    PREFIX = "enc:v1:"
    KEY_SIZE = 32
    NONCE_SIZE = 16
    TAG_SIZE = 16

    def __init__(self, key_path: str | Path):
        self._key_path = Path(key_path)
        self._lock = Lock()

    @classmethod
    def default(cls) -> "SecretStore":
        """Create a store using Harmony's per-user config directory."""
        config_dir = Path(platformdirs.user_config_dir("Harmony", "HarmonyPlayer"))
        return cls(config_dir / "secret.key")

    @classmethod
    def is_encrypted(cls, value: str | None) -> bool:
        """Whether a stored value uses the encrypted payload format."""
        return bool(value) and str(value).startswith(cls.PREFIX)

    def encrypt(self, plaintext: str | None) -> str:
        """Encrypt plaintext for local persistence."""
        if not plaintext:
            return ""
        if self.is_encrypted(plaintext):
            return str(plaintext)

        key = self._get_or_create_key()
        cipher = AES.new(key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(str(plaintext).encode("utf-8"))
        payload = bytes(cipher.nonce) + tag + ciphertext
        encoded = base64.urlsafe_b64encode(payload).decode("ascii")
        return f"{self.PREFIX}{encoded}"

    def decrypt(self, stored_value: str | None) -> str:
        """Decrypt a stored value, keeping legacy plaintext values compatible."""
        if not stored_value:
            return ""
        if not self.is_encrypted(stored_value):
            return str(stored_value)

        try:
            payload = base64.urlsafe_b64decode(str(stored_value)[len(self.PREFIX):].encode("ascii"))
            nonce = payload[:self.NONCE_SIZE]
            tag = payload[self.NONCE_SIZE:self.NONCE_SIZE + self.TAG_SIZE]
            ciphertext = payload[self.NONCE_SIZE + self.TAG_SIZE:]

            cipher = AES.new(self._get_or_create_key(), AES.MODE_GCM, nonce=nonce)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
            return plaintext.decode("utf-8")
        except (ValueError, IndexError, UnicodeDecodeError) as exc:
            logger.warning("Failed to decrypt stored secret: %s", exc)
            return ""

    def _get_or_create_key(self) -> bytes:
        with self._lock:
            if self._key_path.exists():
                return self._key_path.read_bytes()

            self._key_path.parent.mkdir(parents=True, exist_ok=True)
            key = get_random_bytes(self.KEY_SIZE)
            fd = os.open(self._key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(key)
            finally:
                try:
                    os.chmod(self._key_path, 0o600)
                except OSError:
                    pass
            return key
