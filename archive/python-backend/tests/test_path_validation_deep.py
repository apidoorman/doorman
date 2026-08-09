import os
import pytest
from pathlib import Path
from routes.proto_routes import validate_path, PROJECT_ROOT

def test_validate_path_success():
    # Valid path within project root
    target = PROJECT_ROOT / "test_file.proto"
    assert validate_path(PROJECT_ROOT, target) is True

def test_validate_path_traversal():
    # Dangerous path attempting to go up
    target = PROJECT_ROOT / "../../../etc/passwd"
    assert validate_path(PROJECT_ROOT, target) is False

def test_validate_path_outside_allowed():
    # Path outside project and temp
    import tempfile
    outside = Path("/usr/bin/local")
    assert validate_path(PROJECT_ROOT, outside) is False

def test_validate_path_temp_dir():
    import tempfile
    temp_dir = Path(tempfile.gettempdir())
    target = temp_dir / "safe_temp.proto"
    assert validate_path(temp_dir, target) is True

def test_validate_path_complex_traversal():
    # Attempt to use symlink-like trickery or redundant separators
    target = PROJECT_ROOT / "subdir" / ".." / ".." / "etc" / "passwd"
    assert validate_path(PROJECT_ROOT, target) is False

def test_validate_path_same_dir():
    assert validate_path(PROJECT_ROOT, PROJECT_ROOT) is True

def test_validate_path_prefix_attack():
    # PROJECT_ROOT = /foo/bar
    # target = /foo/bar_extra/secret.txt
    # Simple startswith would fail here, but commonpath should handle it.
    parent = PROJECT_ROOT.parent
    sibling = parent / (PROJECT_ROOT.name + "_extra")
    target = sibling / "secret.txt"
    assert validate_path(PROJECT_ROOT, target) is False
