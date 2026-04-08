"""
QQ Music encryption and decryption utilities.
Ported from https://github.com/ygkth/qq-music-api
"""

import hashlib
import base64
import zlib
import json
import logging

from Crypto.Cipher import DES3

logger = logging.getLogger(__name__)


def generate_sign(request_data: dict) -> str:
    """
    Generate request signature for QQ Music API.

    Args:
        request_data: Request data dictionary

    Returns:
        Signature string in format "zzc..."
    """
    # Use json.dumps with separators to match JavaScript's JSON.stringify
    json_str = json.dumps(request_data, separators=(',', ':'), ensure_ascii=False)
    sha1_hash = hashlib.sha1(json_str.encode()).hexdigest().upper()

    # Part 1: specific indexes
    part1_indexes = [23, 14, 6, 36, 16, 39, 7, 19]
    part1 = ''.join(sha1_hash[i] if i < 40 else '' for i in part1_indexes)

    # Part 2: specific indexes
    part2_indexes = [16, 1, 32, 12, 19, 27, 8, 5]
    part2 = ''.join(sha1_hash[i] if i < 40 else '' for i in part2_indexes)

    # Part 3: XOR with scramble values and base64 encode
    scramble_values = [
        89, 39, 179, 150, 218, 82, 58, 252, 177, 52, 186, 123, 120, 64, 242,
        133, 143, 161, 121, 179
    ]
    part3_bytes = bytearray(20)
    for i in range(len(scramble_values)):
        hex_value = int(sha1_hash[i*2:i*2+2], 16)
        part3_bytes[i] = scramble_values[i] ^ hex_value

    b64_part = base64.b64encode(bytes(part3_bytes)).decode()
    # Remove URL-unsafe characters
    b64_part = b64_part.replace('/', '').replace('\\', '').replace('+', '').replace('=', '')

    return f"zzc{part1}{b64_part}{part2}".lower()


def qrc_decrypt(encrypted_qrc_hex: str) -> str:
    """
    Decrypt QRC (encrypted lyrics) using TripleDES and zlib decompression.

    Args:
        encrypted_qrc_hex: Encrypted QRC data as hex string

    Returns:
        Decrypted and decompressed lyrics string
    """
    if not encrypted_qrc_hex:
        return ""

    try:
        # Convert hex to bytes
        encrypted_qrc = bytes.fromhex(encrypted_qrc_hex)

        # TripleDES key
        key = b"!@#)(*$%123ZXC!@!@#)(NHL"

        # Create cipher
        cipher = DES3.new(key, DES3.MODE_ECB)

        # Decrypt in 8-byte blocks
        decrypted = bytearray()
        for i in range(0, len(encrypted_qrc), 8):
            chunk = encrypted_qrc[i:i+8]
            if len(chunk) < 8:
                break
            decrypted.extend(cipher.decrypt(chunk))

        # Decompress using zlib
        try:
            return zlib.decompress(bytes(decrypted)).decode('utf-8')
        except zlib.error:
            # Try raw deflate
            return zlib.decompress(bytes(decrypted), -15).decode('utf-8')

    except Exception as e:
        logger.error(f"QRC decryption failed: {e}")
        return ""


def calc_md5(*inputs) -> str:
    """
    Calculate MD5 hash of inputs.

    Args:
        *inputs: Strings or bytes to hash

    Returns:
        MD5 hash as hexadecimal string
    """
    data = bytearray()
    for item in inputs:
        if isinstance(item, str):
            data.extend(item.encode('utf-8'))
        elif isinstance(item, bytes):
            data.extend(item)
    return hashlib.md5(bytes(data)).hexdigest()


def hash33(s: str, h: int = 0) -> int:
    """
    Hash33 algorithm used by QQ Music.

    Args:
        s: String to hash
        h: Initial hash value

    Returns:
        Hash value
    """
    for c in s:
        h = (h << 5) + h + ord(c)
    return 2147483647 & h
