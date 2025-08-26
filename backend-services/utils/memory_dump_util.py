"""
Utilities to dump and restore in-memory database state with encryption.
"""

import os
import json
import base64
from typing import Optional
from datetime import datetime

from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .database import database

DEFAULT_DUMP_PATH = os.getenv("MEM_DUMP_PATH", "generated/memory_dump.bin")


def _derive_key(key_material: str, salt: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"doorman-mem-dump-v1",
    )
    return hkdf.derive(key_material.encode("utf-8"))


def _encrypt_blob(plaintext: bytes, key_str: str) -> bytes:
    if not key_str or len(key_str) < 8:
        raise ValueError("MEM_ENCRYPTION_KEY must be set and at least 8 characters")
    salt = os.urandom(16)
    key = _derive_key(key_str, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext, None)
    # File format: b'DMP1' + salt(16) + nonce(12) + ciphertext+tag
    return b"DMP1" + salt + nonce + ct


def _decrypt_blob(blob: bytes, key_str: str) -> bytes:
    if not key_str or len(key_str) < 8:
        raise ValueError("MEM_ENCRYPTION_KEY must be set and at least 8 characters")
    if len(blob) < 4 + 16 + 12:
        raise ValueError("Invalid dump file")
    if blob[:4] != b"DMP1":
        raise ValueError("Unsupported dump format")
    salt = blob[4:20]
    nonce = blob[20:32]
    ct = blob[32:]
    key = _derive_key(key_str, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)


def _split_dir_and_stem(path_hint: Optional[str]) -> tuple[str, str]:
    """Return (directory, stem) for naming timestamped dump files.

    - If hint is a directory (or endswith '/'), use it and default stem 'memory_dump'.
    - If hint is a file path, use its directory and basename without extension as stem.
    - If hint is None, use DEFAULT_DUMP_PATH and derive as above.
    """
    hint = path_hint or DEFAULT_DUMP_PATH
    # Normalize paths
    if hint.endswith(os.sep):
        dump_dir = hint
        stem = "memory_dump"
    elif os.path.isdir(hint):
        dump_dir = hint
        stem = "memory_dump"
    else:
        dump_dir = os.path.dirname(hint) or "."
        base = os.path.basename(hint)
        stem, _ext = os.path.splitext(base)
        stem = stem or "memory_dump"
    return dump_dir, stem


def dump_memory_to_file(path: Optional[str] = None) -> str:
    if not database.memory_only:
        raise RuntimeError("Memory dump is only available in memory-only mode")
    dump_dir, stem = _split_dir_and_stem(path)
    os.makedirs(dump_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dump_path = os.path.join(dump_dir, f"{stem}-{ts}.bin")
    payload = {
        "version": 1,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "data": database.db.dump_data(),
    }
    plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    key = os.getenv("MEM_ENCRYPTION_KEY", "")
    blob = _encrypt_blob(plaintext, key)
    with open(dump_path, "wb") as f:
        f.write(blob)
    return dump_path


def restore_memory_from_file(path: Optional[str] = None) -> dict:
    if not database.memory_only:
        raise RuntimeError("Memory restore is only available in memory-only mode")
    dump_path = path or DEFAULT_DUMP_PATH
    if not os.path.exists(dump_path):
        raise FileNotFoundError("Dump file not found")
    key = os.getenv("MEM_ENCRYPTION_KEY", "")
    with open(dump_path, "rb") as f:
        blob = f.read()
    plaintext = _decrypt_blob(blob, key)
    payload = json.loads(plaintext.decode("utf-8"))
    data = payload.get("data", {})
    database.db.load_data(data)
    return {"version": payload.get("version", 1), "created_at": payload.get("created_at")}


def find_latest_dump_path(path_hint: Optional[str] = None) -> Optional[str]:
    """Return the most recent dump file path based on a hint.

    - If `path_hint` is a file and exists, return it.
    - If `path_hint` is a directory, search for .bin files and pick the newest.
    - If no hint or not found, try DEFAULT_DUMP_PATH, or its directory for .bin files.
    """
    def newest_bin_in_dir(d: str, stem: Optional[str] = None) -> Optional[str]:
        try:
            if not os.path.isdir(d):
                return None
            candidates = [
                os.path.join(d, f)
                for f in os.listdir(d)
                if f.lower().endswith('.bin') and os.path.isfile(os.path.join(d, f))
                and (stem is None or f.startswith(stem + '-'))
            ]
            if not candidates:
                return None
            candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            return candidates[0]
        except Exception:
            return None

    # Split hint into (dir, stem)
    dump_dir, stem = _split_dir_and_stem(path_hint)

    # 1) If hint is a file path, prefer the newest timestamped file with same stem in its dir
    # regardless of whether that exact hint exists.
    latest = newest_bin_in_dir(dump_dir, stem)
    if latest:
        return latest

    # 2) Try the default path
    def_dir, def_stem = _split_dir_and_stem(DEFAULT_DUMP_PATH)
    latest = newest_bin_in_dir(def_dir, def_stem)
    if latest:
        return latest

    # 3) Try scanning the default directory
    latest = newest_bin_in_dir(def_dir)
    return latest
