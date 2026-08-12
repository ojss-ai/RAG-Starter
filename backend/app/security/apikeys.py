import hashlib
import secrets

KEY_PREFIX = "rgs_"


def generate_api_key() -> tuple[str, str]:
    """Returns (plaintext, sha256-hash). Plaintext is shown exactly once."""
    plaintext = KEY_PREFIX + secrets.token_urlsafe(32)
    return plaintext, hash_api_key(plaintext)


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()
