"""
Hot Reload Configuration Module

Enables runtime configuration reloading without restarting the server.
Supports SIGHUP signal handler and file-based configuration.

Usage:
    from utils.hot_reload_config import hot_config

    log_level = hot_config.get('LOG_LEVEL', 'INFO')

    # Register callback for config changes
    def on_log_level_change(old_value, new_value):
        logging.getLogger().setLevel(new_value)

    hot_config.register_callback('LOG_LEVEL', on_log_level_change)

    hot_config.reload()
"""

import os
import json
import yaml
import logging
import threading
from typing import Any, Dict, Callable, Optional
from pathlib import Path

logger = logging.getLogger('doorman.gateway')

class HotReloadConfig:
    """
    Thread-safe configuration manager with hot reload support.

    Supports:
    - Environment variables (always checked first)
    - YAML/JSON configuration files
    - Runtime updates via SIGHUP signal
    - Callbacks for configuration changes
    """

    def __init__(self, config_file: Optional[str] = None):
        self._lock = threading.RLock()
        self._config: Dict[str, Any] = {}
        self._callbacks: Dict[str, list] = {}
        self._config_file = config_file or os.getenv('DOORMAN_CONFIG_FILE')
        self._load_initial_config()

    def _load_initial_config(self):
        """Load initial configuration from environment and file"""
        with self._lock:
            self._config = {}

            if self._config_file and os.path.exists(self._config_file):
                try:
                    self._load_from_file(self._config_file)
                    logger.info(f'Loaded configuration from {self._config_file}')
                except Exception as e:
                    logger.error(f'Failed to load config file {self._config_file}: {e}')

            self._load_from_env()

    def _load_from_file(self, filepath: str):
        """Load configuration from YAML or JSON file"""
        path = Path(filepath)

        with open(filepath, 'r') as f:
            if path.suffix in ['.yaml', '.yml']:
                file_config = yaml.safe_load(f) or {}
            elif path.suffix == '.json':
                file_config = json.load(f)
            else:
                raise ValueError(f'Unsupported config file format: {path.suffix}')

        self._config.update(self._flatten_dict(file_config))

    def _load_from_env(self):
        """Load reloadable configuration from environment variables"""
        reloadable_keys = [
            'LOG_LEVEL',
            'LOG_FORMAT',
            'LOG_FILE',

            'GATEWAY_TIMEOUT',
            'UPSTREAM_TIMEOUT',
            'CONNECTION_TIMEOUT',

            'RATE_LIMIT_ENABLED',
            'RATE_LIMIT_REQUESTS',
            'RATE_LIMIT_WINDOW',

            'CACHE_TTL',
            'CACHE_MAX_SIZE',

            'CIRCUIT_BREAKER_ENABLED',
            'CIRCUIT_BREAKER_THRESHOLD',
            'CIRCUIT_BREAKER_TIMEOUT',

            'RETRY_ENABLED',
            'RETRY_MAX_ATTEMPTS',
            'RETRY_BACKOFF',

            'METRICS_ENABLED',
            'METRICS_INTERVAL',

            'FEATURE_REQUEST_REPLAY',
            'FEATURE_AB_TESTING',
            'FEATURE_COST_ANALYTICS',
        ]

        for key in reloadable_keys:
            value = os.getenv(key)
            if value is not None:
                self._config[key] = self._parse_value(value)

    def _flatten_dict(self, d: dict, parent_key: str = '', sep: str = '_') -> dict:
        """Flatten nested dictionary with separator"""
        items = []
        for k, v in d.items():
            new_key = f'{parent_key}{sep}{k}' if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key.upper(), v))
        return dict(items)

    def _parse_value(self, value: str) -> Any:
        """Parse string value to appropriate type"""
        if value.lower() in ['true', 'yes', '1']:
            return True
        if value.lower() in ['false', 'no', '0']:
            return False

        try:
            return int(value)
        except ValueError:
            pass

        try:
            return float(value)
        except ValueError:
            pass

        return value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.

        Checks in order:
        1. Environment variable (always fresh)
        2. In-memory config (from file or previous load)
        3. Default value
        """
        env_value = os.getenv(key)
        if env_value is not None:
            return self._parse_value(env_value)

        with self._lock:
            return self._config.get(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value"""
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f'Invalid integer value for {key}: {value}, using default: {default}')
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value"""
        value = self.get(key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f'Invalid float value for {key}: {value}, using default: {default}')
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value"""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ['true', 'yes', '1']
        return bool(value)

    def set(self, key: str, value: Any):
        """
        Set configuration value (in-memory only).

        Note: Does not modify environment or file.
        """
        with self._lock:
            old_value = self._config.get(key)
            self._config[key] = value

            if old_value != value:
                self._trigger_callbacks(key, old_value, value)

    def register_callback(self, key: str, callback: Callable[[Any, Any], None]):
        """
        Register callback for configuration changes.

        Callback signature: callback(old_value, new_value)
        """
        with self._lock:
            if key not in self._callbacks:
                self._callbacks[key] = []
            self._callbacks[key].append(callback)
            logger.debug(f'Registered callback for config key: {key}')

    def _trigger_callbacks(self, key: str, old_value: Any, new_value: Any):
        """Trigger callbacks for configuration change"""
        callbacks = self._callbacks.get(key, [])
        for callback in callbacks:
            try:
                callback(old_value, new_value)
            except Exception as e:
                logger.error(f'Error in config callback for {key}: {e}', exc_info=True)

    def reload(self):
        """
        Reload configuration from file and environment.

        Called by SIGHUP signal handler.
        """
        logger.info('Reloading configuration...')

        with self._lock:
            old_config = self._config.copy()

            if self._config_file and os.path.exists(self._config_file):
                try:
                    self._load_from_file(self._config_file)
                    logger.info(f'Reloaded configuration from {self._config_file}')
                except Exception as e:
                    logger.error(f'Failed to reload config file: {e}')

            self._load_from_env()

            for key in set(old_config.keys()) | set(self._config.keys()):
                old_value = old_config.get(key)
                new_value = self._config.get(key)
                if old_value != new_value:
                    logger.info(f'Config changed: {key} = {old_value} -> {new_value}')
                    self._trigger_callbacks(key, old_value, new_value)

        logger.info('Configuration reload complete')

    def dump(self) -> Dict[str, Any]:
        """Dump current configuration (for debugging)"""
        with self._lock:
            config = self._config.copy()
            for key in config.keys():
                env_value = os.getenv(key)
                if env_value is not None:
                    config[key] = self._parse_value(env_value)
            return config

hot_config = HotReloadConfig()

# Convenience functions for common config patterns
def get_timeout_config() -> Dict[str, int]:
    """Get all timeout configurations"""
    return {
        'gateway_timeout': hot_config.get_int('GATEWAY_TIMEOUT', 30),
        'upstream_timeout': hot_config.get_int('UPSTREAM_TIMEOUT', 30),
        'connection_timeout': hot_config.get_int('CONNECTION_TIMEOUT', 10),
    }

def get_rate_limit_config() -> Dict[str, Any]:
    """Get rate limiting configuration"""
    return {
        'enabled': hot_config.get_bool('RATE_LIMIT_ENABLED', True),
        'requests': hot_config.get_int('RATE_LIMIT_REQUESTS', 100),
        'window': hot_config.get_int('RATE_LIMIT_WINDOW', 60),
    }

def get_cache_config() -> Dict[str, Any]:
    """Get cache configuration"""
    return {
        'ttl': hot_config.get_int('CACHE_TTL', 300),
        'max_size': hot_config.get_int('CACHE_MAX_SIZE', 1000),
    }

def get_circuit_breaker_config() -> Dict[str, Any]:
    """Get circuit breaker configuration"""
    return {
        'enabled': hot_config.get_bool('CIRCUIT_BREAKER_ENABLED', True),
        'threshold': hot_config.get_int('CIRCUIT_BREAKER_THRESHOLD', 5),
        'timeout': hot_config.get_int('CIRCUIT_BREAKER_TIMEOUT', 60),
    }

def get_retry_config() -> Dict[str, Any]:
    """Get retry configuration"""
    return {
        'enabled': hot_config.get_bool('RETRY_ENABLED', True),
        'max_attempts': hot_config.get_int('RETRY_MAX_ATTEMPTS', 3),
        'backoff': hot_config.get_float('RETRY_BACKOFF', 1.0),
    }
