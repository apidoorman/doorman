"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger('doorman.gateway')


def _derive_key_from_components(email: str, username: str, vault_key: str) -> bytes:
    """
    Derive a Fernet-compatible encryption key from email, username, and vault key.

    Args:
        email: User's email address
        username: User's username
        vault_key: VAULT_KEY from environment

    Returns:
        bytes: 32-byte key suitable for Fernet encryption
    """
    # Combine all components to create a unique salt
    combined = f'{email}:{username}:{vault_key}'
    salt = hashlib.sha256(combined.encode()).digest()

    # Use PBKDF2 to derive a key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend(),
    )

    # Derive key from the vault_key
    key = kdf.derive(vault_key.encode())

    # Encode to base64 for Fernet compatibility
    return base64.urlsafe_b64encode(key)


def encrypt_vault_value(value: str, email: str, username: str) -> str:
    """
    Encrypt a vault value using email, username, and VAULT_KEY from environment.

    Args:
        value: The plaintext value to encrypt
        email: User's email address
        username: User's username

    Returns:
        str: Base64-encoded encrypted value

    Raises:
        RuntimeError: If VAULT_KEY is not configured
        ValueError: If encryption fails
    """
    vault_key = os.getenv('VAULT_KEY')
    if not vault_key:
        raise RuntimeError('VAULT_KEY is not configured in environment variables')

    try:
        # Derive encryption key
        encryption_key = _derive_key_from_components(email, username, vault_key)

        # Create Fernet cipher
        cipher = Fernet(encryption_key)

        # Encrypt the value
        encrypted_bytes = cipher.encrypt(value.encode('utf-8'))

        # Return as base64 string
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f'Encryption failed: {str(e)}')
        raise ValueError(f'Failed to encrypt vault value: {str(e)}') from e


def decrypt_vault_value(encrypted_value: str, email: str, username: str) -> str:
    """
    Decrypt a vault value using email, username, and VAULT_KEY from environment.

    Args:
        encrypted_value: The base64-encoded encrypted value
        email: User's email address
        username: User's username

    Returns:
        str: Decrypted plaintext value

    Raises:
        RuntimeError: If VAULT_KEY is not configured
        ValueError: If decryption fails
    """
    vault_key = os.getenv('VAULT_KEY')
    if not vault_key:
        raise RuntimeError('VAULT_KEY is not configured in environment variables')

    try:
        # Derive encryption key
        encryption_key = _derive_key_from_components(email, username, vault_key)

        # Create Fernet cipher
        cipher = Fernet(encryption_key)

        # Decrypt the value
        decrypted_bytes = cipher.decrypt(encrypted_value.encode('utf-8'))

        # Return as string
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f'Decryption failed: {str(e)}')
        raise ValueError(f'Failed to decrypt vault value: {str(e)}') from e


def is_vault_configured() -> bool:
    """
    Check if VAULT_KEY is configured in environment variables.

    Returns:
        bool: True if VAULT_KEY is set, False otherwise
    """
    return bool(os.getenv('VAULT_KEY'))
