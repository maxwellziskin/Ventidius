"""
Ziskin Field Systems - Encryption Utility

Handles encryption/decryption of sensitive data like camera credentials.
"""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import structlog

logger = structlog.get_logger(__name__)

# Key derivation salt (should be stored securely in production)
DEFAULT_SALT = b'zfs_edge_device_salt_v1'


def derive_key(password: str, salt: bytes = DEFAULT_SALT) -> bytes:
    """Derive an encryption key from a password."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def get_device_key() -> bytes:
    """Get or generate device-specific encryption key."""
    key_file = "/opt/ziskin/.device_key"

    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()

    # Generate new key
    key = Fernet.generate_key()

    # Save key (ensure directory exists)
    os.makedirs(os.path.dirname(key_file), exist_ok=True)
    with open(key_file, 'wb') as f:
        f.write(key)

    # Set restrictive permissions
    os.chmod(key_file, 0o600)

    logger.info("Generated new device encryption key")
    return key


def encrypt(data: str, key: bytes = None) -> str:
    """Encrypt a string value."""
    if key is None:
        key = get_device_key()

    fernet = Fernet(key)
    encrypted = fernet.encrypt(data.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt(encrypted_data: str, key: bytes = None) -> str:
    """Decrypt an encrypted string value."""
    if key is None:
        key = get_device_key()

    fernet = Fernet(key)
    data = base64.urlsafe_b64decode(encrypted_data.encode())
    decrypted = fernet.decrypt(data)
    return decrypted.decode()


def is_encrypted(value: str) -> bool:
    """Check if a value appears to be encrypted."""
    try:
        # Encrypted values are base64-encoded and start with 'gAAAAA'
        decoded = base64.urlsafe_b64decode(value.encode())
        return decoded.startswith(b'gAAAAA')
    except Exception:
        return False


def encrypt_config_passwords(config: dict, key: bytes = None) -> dict:
    """Encrypt all password fields in a configuration dictionary."""
    result = config.copy()

    if 'cameras' in result:
        for camera in result['cameras']:
            if 'password' in camera and not is_encrypted(camera['password']):
                camera['password'] = encrypt(camera['password'], key)

    return result


def decrypt_config_passwords(config: dict, key: bytes = None) -> dict:
    """Decrypt all password fields in a configuration dictionary."""
    result = config.copy()

    if 'cameras' in result:
        for camera in result['cameras']:
            if 'password' in camera and is_encrypted(camera['password']):
                try:
                    camera['password'] = decrypt(camera['password'], key)
                except Exception as e:
                    logger.error(
                        "Failed to decrypt camera password",
                        camera_id=camera.get('id'),
                        error=str(e)
                    )

    return result
