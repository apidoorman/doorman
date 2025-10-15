"""
Repo-wide cleanup for style cohesion:
- Remove inline comments from Python and TS/TSX (safe string-aware pass)
- Remove full-line // comments in TS/TSX
- Collapse multiple blank lines to a single blank line

Notes:
- Python: strips trailing '#' comments not inside string literals; keeps full-line
  comments (lines starting with '#').
- TS/TSX: strips trailing '//' comments not inside string/ template strings, and
  drops full-line '//' comments. Does not alter block comments '/* ... */'.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]

def strip_python_inline_comment(line: str) -> str:
    """Remove trailing inline comment starting with #, respecting strings."""
    s_quote = False
    d_quote = False
    esc = False
    i = 0
    while i < len(line):
        ch = line[i]
        if esc:
            esc = False
            i += 1
            continue
        if ch == "\\":
            esc = True
            i += 1
            continue
        if not d_quote and ch == "'":
            s_quote = not s_quote
            i += 1
            continue
        if not s_quote and ch == '"':
            d_quote = not d_quote
            i += 1
            continue
        if not s_quote and not d_quote and ch == '#':
            return line[:i].rstrip()
        i += 1
    return line.rstrip()

def is_ts_full_line_comment(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith('//')

def strip_ts_inline_comment(line: str) -> str:
    """Strip trailing // comments in TS/TSX respecting quotes and template strings."""
    in_s = False
    in_d = False
    in_bt = False
    esc = False
    i = 0
    while i < len(line):
        ch = line[i]
        if esc:
            esc = False
            i += 1
            continue
        if ch == "\\":
            esc = True
            i += 1
            continue
        if not in_d and not in_bt and ch == "'":
            in_s = not in_s
            i += 1
            continue
        if not in_s and not in_bt and ch == '"':
            in_d = not in_d
            i += 1
            continue
        if not in_s and not in_d and ch == '`':
            in_bt = not in_bt
            i += 1
            continue
        if not in_s and not in_d and not in_bt and ch == '/' and i + 1 < len(line) and line[i + 1] == '/':
            return line[:i].rstrip()
        i += 1
    return line.rstrip()

def collapse_blank_runs(lines: Iterable[str]) -> list[str]:
    out: list[str] = []
    blank = 0
    for raw in lines:
        line = raw.rstrip('\n')
        if line.strip() == "":
            blank += 1
            if blank > 1:
                continue
            out.append("")
        else:
            blank = 0
            out.append(line.rstrip())
    while out and out[-1] == "":
        out.pop()
    return out

def process_file(path: Path) -> bool:
    text = path.read_text(encoding='utf-8', errors='replace').splitlines()
    changed = False
    out: list[str] = []

    if path.suffix == '.py':
        for ln in text:
            if ln.lstrip().startswith('#'):
                if ln.startswith(' '):
                    changed = True
                    continue
                out.append(ln.rstrip())
            else:
                stripped = strip_python_inline_comment(ln)
                if stripped != ln.rstrip():
                    changed = True
                out.append(stripped)
    elif path.suffix in {'.ts', '.tsx', '.js', '.jsx'}:
        for ln in text:
            if is_ts_full_line_comment(ln):
                changed = True
                continue
            stripped = strip_ts_inline_comment(ln)
            if stripped != ln.rstrip():
                changed = True
            out.append(stripped)
    else:
        return False

    out = collapse_blank_runs(out)
    if '\n'.join(out) != '\n'.join([l.rstrip() for l in text]).rstrip():
        changed = True
    if changed:
        path.write_text('\n'.join(out) + '\n', encoding='utf-8')
    return changed

def gather_targets() -> list[Path]:
    patterns = [
        ('backend-services', ('.py',)),
        ('web-client/src', ('.ts', '.tsx', '.js', '.jsx')),
    ]
    files: list[Path] = []
    for rel, exts in patterns:
        root = ROOT / rel
        if not root.exists():
            continue
        for p in root.rglob('*'):
            if any(seg in p.parts for seg in ('venv', '.venv', 'env', '.env', 'node_modules', '.pytest_cache', '__pycache__')):
                continue
            if p.is_file() and p.suffix in exts:
                files.append(p)
    return files

def main() -> int:
    targets = gather_targets()
    changed = 0
    for f in targets:
        try:
            if process_file(f):
                changed += 1
        except Exception as e:
            print(f"WARN: Failed to process {f}: {e}")
    print(f"Processed {len(targets)} files; modified {changed}.")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
