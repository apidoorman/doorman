"""
MFA Utility Functions

Provides:
- TOTP secret generation
- QR code generation
- TOTP code verification
"""

import base64
import hashlib
import hmac
import io
import logging
import secrets
import struct
import time
import urllib.parse
from datetime import datetime, timezone

logger = logging.getLogger('doorman.gateway')


def generate_mfa_secret() -> str:
    """
    Generate a random base32 encoded MFA secret.
    
    Returns:
        Base32 string (16 chars)
    """
    # 10 bytes = 16 base32 chars
    random_bytes = secrets.token_bytes(10)
    return base64.b32encode(random_bytes).decode('ascii')


def generate_totp_uri(secret: str, username: str, issuer: str = 'Doorman') -> str:
    """
    Generate the otpauth URI for QR codes.
    
    Args:
        secret: Base32 secret
        username: User identifier
        issuer: Service name
        
    Returns:
        otpauth URI string
    """
    return f'otpauth://totp/{urllib.parse.quote(issuer)}:{urllib.parse.quote(username)}?secret={secret}&issuer={urllib.parse.quote(issuer)}&algorithm=SHA1&digits=6&period=30'


def verify_totp_code(secret: str, code: str, valid_window: int = 1) -> bool:
    """
    Verify a TOTP code against a secret.
    
    Args:
        secret: Base32 secret
        code: The code to verify (string or int)
        valid_window: Number of 30-sec windows to check (drift)
        
    Returns:
        True if valid
    """
    try:
        # Normalize code
        code = str(code).strip()
        if not code.isdigit() or len(code) != 6:
            return False
            
        # Decode secret
        try:
            # Add padding if needed
            missing_padding = len(secret) % 8
            if missing_padding:
                secret += '=' * (8 - missing_padding)
            key = base64.b32decode(secret, casefold=True)
        except Exception:
            logger.warning('Invalid base32 secret for MFA verification')
            return False
        
        # Current time step (30s)
        current_ts = int(time.time() // 30)
        
        # Check window
        for i in range(-valid_window, valid_window + 1):
            ts = current_ts + i
            generated = _generate_totp(key, ts)
            if generated == code:
                return True
                
        return False
        
    except Exception as e:
        logger.error(f'Error verifying TOTP: {e}')
        return False


def _generate_totp(key: bytes, time_step: int) -> str:
    """
    Generate TOTP code for a specific time step.
    
    Args:
        key: Raw secret bytes
        time_step: Integer time counter
        
    Returns:
        6-digit code string
    """
    # Pack time step as big-endian 8-byte integer
    msg = struct.pack('>Q', time_step)
    
    # HMAC-SHA1
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    
    # Dynamic truncation
    offset = digest[-1] & 0x0F
    binary = (
        ((digest[offset] & 0x7F) << 24) |
        ((digest[offset + 1] & 0xFF) << 16) |
        ((digest[offset + 2] & 0xFF) << 8) |
        (digest[offset + 3] & 0xFF)
    )
    
    otp = binary % 1000000
    return f'{otp:06d}'


def generate_qr_code_svg(uri: str) -> str:
    """
    Generate a simple SVG QR code for the URI.
    
    Note: For a real production app, use `qrcode` library.
    This is a stub to avoid adding dependencies if not available.
    
    Args:
        uri: otpauth URI
        
    Returns:
        SVG string
    """
    try:
        import qrcode
        import qrcode.image.svg
        
        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(uri, image_factory=factory)
        
        buffer = io.BytesIO()
        img.save(buffer)
        return buffer.getvalue().decode('utf-8')
    except ImportError:
        logger.warning('qrcode library not installed; cannot generate QR image')
        return f'<svg><text>Install qrcode library to view QR. URI: {uri}</text></svg>'
    except Exception as e:
        logger.error(f'Error generating QR: {e}')
        return '<svg><text>Error generating QR code</text></svg>'
