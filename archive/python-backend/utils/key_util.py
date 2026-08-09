"""
Key Management Utility

Provides support for:
- Multiple active keys (key rotation)
- HS256 and RS256 algorithms
- Key loading from environment/config
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, NamedTuple

logger = logging.getLogger('doorman.gateway')


class KeyInfo(NamedTuple):
    kid: str
    algorithm: str
    signing_key: str
    verification_key: str
    active: bool


# Default fallback key for development
DEFAULT_DEV_KEY = KeyInfo(
    kid='dev-key-1',
    algorithm='HS256',
    signing_key=os.getenv('JWT_SECRET_KEY', 'insecure-test-key'),
    verification_key=os.getenv('JWT_SECRET_KEY', 'insecure-test-key'),
    active=True,
)

_cached_keys: list[KeyInfo] = []
_last_load_time: float = 0
_KEY_CACHE_TTL = 300  # Reload keys max every 5 mins


def load_keys(force_reload: bool = False) -> list[KeyInfo]:
    """
    Load JWT keys from configuration.
    
    Supports:
    - JWT_KEYS env var (JSON list of key configs)
    - Legacy JWT_SECRET_KEY env var (fallback)
    
    Returns:
        List of KeyInfo objects
    """
    global _cached_keys, _last_load_time
    
    current_time = datetime.now(timezone.utc).timestamp()
    if not force_reload and _cached_keys and (current_time - _last_load_time < _KEY_CACHE_TTL):
        return _cached_keys
    
    keys = []
    
    # Check for JWT_KEYS JSON config
    jwt_keys_json = os.getenv('JWT_KEYS')
    if jwt_keys_json:
        try:
            configs = json.loads(jwt_keys_json)
            if not isinstance(configs, list):
                if isinstance(configs, dict) and 'keys' in configs:
                    configs = configs['keys']
                else:
                    configs = [configs]
            
            for cfg in configs:
                try:
                    kid = cfg.get('kid')
                    alg = cfg.get('algorithm', 'HS256')
                    active = cfg.get('active', True)
                    
                    if not kid:
                        continue
                        
                    signing_key = None
                    verification_key = None
                    
                    if alg == 'HS256':
                        secret = cfg.get('secret') or cfg.get('key')
                        if secret:
                            signing_key = secret
                            verification_key = secret
                    elif alg == 'RS256':
                        # Load PEM keys
                        priv_path = cfg.get('private_key_path')
                        pub_path = cfg.get('public_key_path')
                        
                        if priv_path and os.path.exists(priv_path):
                            with open(priv_path, 'r') as f:
                                signing_key = f.read()
                        elif cfg.get('private_key'):
                            signing_key = cfg.get('private_key')
                            
                        if pub_path and os.path.exists(pub_path):
                            with open(pub_path, 'r') as f:
                                verification_key = f.read()
                        elif cfg.get('public_key'):
                            verification_key = cfg.get('public_key')
                    
                    if verification_key:
                        keys.append(KeyInfo(
                            kid=kid,
                            algorithm=alg,
                            signing_key=signing_key,  # Might be None if verifier-only
                            verification_key=verification_key,
                            active=active
                        ))
                except Exception as e:
                    logger.error(f'Error loading key config: {e}')
                    
        except json.JSONDecodeError:
            logger.error('Invalid JSON in JWT_KEYS environment variable')
    
    # Legacy fallback
    if not keys:
        secret = os.getenv('JWT_SECRET_KEY')
        if secret:
            keys.append(KeyInfo(
                kid='legacy-key',
                algorithm='HS256',
                signing_key=secret,
                verification_key=secret,
                active=True
            ))
        else:
            # Development fallback
            keys.append(DEFAULT_DEV_KEY)
    
    _cached_keys = keys
    _last_load_time = current_time
    return keys


def get_signing_key(kid: str | None = None) -> KeyInfo | None:
    """
    Get the best key for signing new tokens.
    
    Args:
        kid: Optional specific key ID to request
        
    Returns:
        KeyInfo or None
    """
    keys = load_keys()
    
    if kid:
        for k in keys:
            if k.kid == kid and k.signing_key:
                return k
        return None
    
    # Return first active signing key
    for k in keys:
        if k.active and k.signing_key:
            return k
            
    return None


def get_verification_key(kid: str | None = None) -> KeyInfo | None:
    """
    Get key for verifying a token.
    
    Args:
        kid: Key ID from token header
        
    Returns:
        KeyInfo or None
    """
    keys = load_keys()
    
    # If no kid specified, and only one key exists, use it (legacy mode)
    if not kid and len(keys) == 1:
        return keys[0]
        
    if kid:
        for k in keys:
            if k.kid == kid:
                return k
    
    # If no kid provided but we have keys, try the legacy key if present
    if not kid:
        for k in keys:
            if k.kid == 'legacy-key':
                return k
                
    return None
