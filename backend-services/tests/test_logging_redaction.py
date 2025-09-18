import os
import time
import logging


def test_logging_redaction_filters_sensitive_values(tmp_path):
    # Use the configured doorman logger
    logger = logging.getLogger("doorman.gateway")
    # Write a unique log line with secrets
    secret = "supersecretvalue"
    logger.info(f"Authorization: Bearer {secret}; password=\"{secret}\"; access_token=\"{secret}\"")
    # Give handler a moment to flush
    time.sleep(0.05)
    # Locate log file
    base_dir = os.path.join(os.path.dirname(__file__), os.pardir)
    logs_dir = os.path.realpath(os.path.join(base_dir, "logs"))
    log_path = os.path.join(logs_dir, "doorman.log")
    with open(log_path, "r", encoding="utf-8") as f:
        tail = f.read()[-2000:]
    assert secret not in tail
    assert "[REDACTED]" in tail

