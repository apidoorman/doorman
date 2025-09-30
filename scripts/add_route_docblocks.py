#!/usr/bin/env python3
import re
from pathlib import Path
import sys


ROUTE_DECORATOR_RE = re.compile(r"^\s*@\s*\w*_router\.")
DEF_RE = re.compile(r'^\s*async\s+def\s+\w+\s*\(')


def extract_description(block: str):
    # Find description='...' or "..."
    m = re.search(r"description\s*=\s*(['\"])(.*?)\1", block, re.S)
    if m:
        return m.group(2).strip()
    return None


def has_docblock_before(lines: list[str], start_index: int) -> bool:
    # Look immediately above the decorator block for a triple-quoted block
    i = start_index - 1
    while i >= 0 and lines[i].strip() == "":
        i -= 1
    if i >= 0:
        s = lines[i].strip()
        return s.startswith('"""') or s.startswith("'''")
    return False


def build_docblock(desc: str) -> list[str]:
    return [
        '"""\n',
        f"{desc}\n",
        '\n',
        'Request:\n',
        '{}\n',
        'Response:\n',
        '{}\n',
        '"""\n',
        '\n',
    ]


def process_file(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines(True)
    i = 0
    changed = False
    n = len(lines)
    while i < n:
        if ROUTE_DECORATOR_RE.match(lines[i]):
            # capture decorator block (may span lines until a line that does not start with @ or whitespace/closing paren)
            start = i
            # consume consecutive decorator lines and following paren block if needed
            # We'll continue until we hit a line that starts with 'async def'
            j = i + 1
            while j < n and not DEF_RE.match(lines[j]):
                j += 1
            # now j points to async def (or EOF)
            if j < n:
                # If a misplaced docblock exists between decorators and def, relocate it above decorators
                k = start
                moved = False
                while k < j:
                    if lines[k].lstrip().startswith(('"""', "'''")):
                        # find end of triple-quoted block
                        quote = '"""' if lines[k].lstrip().startswith('"""') else "'''"
                        m = k + 1
                        while m < j and quote not in lines[m]:
                            m += 1
                        if m < j:
                            block = lines[k:m+1]
                            del lines[k:m+1]
                            lines[start:start] = block + ['\n']
                            # adjust indices after insertion/removal
                            shift = (m+1 - k)
                            j -= shift
                            n = len(lines)
                            moved = True
                            break
                        else:
                            break
                    k += 1

                if not has_docblock_before(lines, start):
                    desc = extract_description(''.join(lines[start:j])) or 'Endpoint'
                    doc = build_docblock(desc)
                    lines[start:start] = doc
                    n = len(lines)
                    i = j + len(doc) + 1
                    changed = True
                    continue
                else:
                    i = j + 1
                    continue
            else:
                break
        i += 1
    if changed:
        path.write_text(''.join(lines), encoding='utf-8')
    return changed


def main(paths):
    targets = []
    for p in paths:
        pth = Path(p)
        if pth.is_dir():
            for f in pth.rglob('*.py'):
                if 'routes' not in f.parts:
                    continue
                if any(part in {'.git', 'venv', '.venv', '__pycache__', 'generated'} for part in f.parts):
                    continue
                targets.append(f)
        elif pth.suffix == '.py':
            targets.append(pth)
    for f in sorted(set(targets)):
        if process_file(f):
            print(f"docblock: {f}")


if __name__ == '__main__':
    args = sys.argv[1:] or ['backend-services/routes']
    main(args)
