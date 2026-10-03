"""Chromium-family cookie extraction for TweetHoarder."""

import hashlib
import sqlite3
import sys
from pathlib import Path


def extract_chrome_cookies(db_path: Path, browser: str = "chrome") -> dict[str, str]:
    """Extract X session cookies from a Chromium-family Cookies database."""
    with sqlite3.connect(db_path) as conn:
        try:
            database_version = int(
                conn.execute("SELECT value FROM meta WHERE key='version'").fetchone()[0]
            )
        except (sqlite3.OperationalError, TypeError):
            database_version = 0
        cursor = conn.execute(
            """
            SELECT host_key, name, value, encrypted_value
            FROM cookies
            WHERE name IN ('auth_token', 'ct0', 'twid')
              AND host_key IN ('x.com', '.x.com', 'twitter.com', '.twitter.com')
            ORDER BY CASE WHEN host_key IN ('x.com', '.x.com') THEN 0 ELSE 1 END
            """
        )
        rows = cursor.fetchall()

    cookies: dict[str, str] = {}
    encryption_key: bytes | None = None
    for host, name, value, encrypted_value in rows:
        if name in cookies:
            continue
        if encrypted_value:
            if encrypted_value.startswith(b"v11") and encryption_key is None:
                encryption_key = get_chrome_encryption_key(browser)
            decrypted = decrypt_chrome_cookie(
                encrypted_value,
                encryption_key,
                host=host,
                require_domain_hash=database_version >= 24,
            )
            if decrypted:
                cookies[name] = decrypted
        elif value:
            cookies[name] = value
    return cookies


def decrypt_chrome_cookie(
    encrypted_value: bytes,
    key: bytes | None = None,
    *,
    host: str | None = None,
    require_domain_hash: bool = False,
) -> str:
    """Decrypt a Linux Chromium cookie using its v10 or v11 key."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    version = encrypted_value[:3]
    if version not in (b"v10", b"v11"):
        return ""

    if key is None:
        if version == b"v11":
            return ""
        if sys.platform == "linux":
            key = _derive_encryption_key(b"peanuts")
        elif sys.platform == "darwin":
            key = get_chrome_encryption_key()
        else:
            return ""

    ciphertext = encrypted_value[3:]
    if not ciphertext or len(ciphertext) % 16:
        return ""
    iv = b" " * 16  # Chrome uses space padding for IV

    try:
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        # Validate and remove PKCS7 padding.
        padding_length = padded_plaintext[-1]
        if (
            not 1 <= padding_length <= 16
            or padded_plaintext[-padding_length:] != bytes([padding_length]) * padding_length
        ):
            return ""
        plaintext = padded_plaintext[:-padding_length]
        if host:
            domain_hash = hashlib.sha256(host.encode("utf-8")).digest()
            if plaintext.startswith(domain_hash):
                plaintext = plaintext[len(domain_hash) :]
            elif require_domain_hash:
                return ""
        return plaintext.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return ""


def _derive_encryption_key(password: bytes) -> bytes:
    """Derive Chromium's Linux AES-128 key from its keyring password."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=16,
        salt=b"saltysalt",
        iterations=1,
    )
    return kdf.derive(password)


def get_chrome_encryption_key(browser: str = "chrome") -> bytes | None:
    """Get a Chromium-family v11 encryption key from GNOME keyring."""
    import secretstorage

    connection = secretstorage.dbus_init()
    collection = secretstorage.get_default_collection(connection)

    items = list(collection.search_items({"application": browser}))
    if not items:
        return None

    return _derive_encryption_key(items[0].get_secret())


def find_chrome_cookies_db(
    home_dir: Path, profile: str | None = None, browser: str = "chrome"
) -> Path | None:
    """Find a Chromium-family Cookies database file."""
    profile_name = profile or "Default"
    user_data_dirs = {
        "brave": home_dir / ".config" / "BraveSoftware" / "Brave-Browser",
        "chrome": home_dir / ".config" / "google-chrome",
        "chromium": home_dir / ".config" / "chromium",
    }
    user_data_dir = user_data_dirs.get(browser)
    if user_data_dir is None:
        return None

    profile_dir = user_data_dir / profile_name
    for cookies_path in (profile_dir / "Network" / "Cookies", profile_dir / "Cookies"):
        if cookies_path.exists():
            return cookies_path
    return None
