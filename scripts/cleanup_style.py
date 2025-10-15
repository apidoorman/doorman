import sys
import re
from pathlib import Path

def is_def_or_class(line: str) -> bool:
    s = line.lstrip()
    return s.startswith('def ') or s.startswith('class ')

def strip_inline_comment(line: str) -> str:
    s = line
    in_s = False
    in_d = False
    escape = False
    for i, ch in enumerate(s):
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == "'" and not in_d:
            in_s = not in_s
            continue
        if ch == '"' and not in_s:
            in_d = not in_d
            continue
        if ch == '#' and not in_s and not in_d:
            return s[:i].rstrip() + ("\n" if s.endswith('\n') else "")
    return line

def process_file(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines(keepends=True)

    keep_comment = [False] * len(lines)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith('#'):
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines) and is_def_or_class(lines[j]):
                k = i
                while k < j:
                    if lines[k].lstrip().startswith('#') or lines[k].strip() == '':
                        keep_comment[k] = True
                    k += 1
                i = j
                continue
        i += 1

    out_lines = []
    for idx, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith('#'):
            if keep_comment[idx]:
                out_lines.append(line)
            continue

        if '#' in line:
            line = strip_inline_comment(line)

        if line.endswith('\n'):
            line = line.rstrip() + '\n'
        else:
            line = line.rstrip()

        out_lines.append(line)

    collapsed = []
    blank_run = 0
    for l in out_lines:
        if l.strip() == '':
            blank_run += 1
            if blank_run <= 1:
                collapsed.append(l)
        else:
            blank_run = 0
            collapsed.append(l)

    new_text = ''.join(collapsed)
    if new_text != text:
        path.write_text(new_text, encoding='utf-8')

def main(argv: list[str]) -> int:
    include_all = False
    args = [a for a in argv[1:] if a]
    if args and args[0] == '--include-all':
        include_all = True
        args = args[1:]
    base = Path(args[0]) if args else Path('.')
    targets = []
    for p in base.rglob('*.py'):
        parts = set(p.parts)
        if not include_all:
            if 'tests' in parts or 'live-tests' in parts or 'generated' in parts or 'web-client' in parts:
                continue
        targets.append(p)

    for p in targets:
        process_file(p)

    return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
