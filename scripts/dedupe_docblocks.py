#!/usr/bin/env python3
import sys
from pathlib import Path


def dedupe_file(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines(True)
    out = []
    i = 0
    n = len(lines)
    changed = False
    while i < n:
        line = lines[i]
        if line.lstrip().startswith(('"""', "'''")):
            # capture this docblock
            quote = '"""' if line.lstrip().startswith('"""') else "'''"
            j = i + 1
            while j < n and quote not in lines[j]:
                j += 1
            if j >= n:
                # unclosed; copy through
                out.append(line)
                i += 1
                continue
            block = lines[i:j+1]
            # check for immediate duplicate docblock following (ignoring blank lines)
            k = j + 1
            blanks = []
            while k < n and lines[k].strip() == '':
                blanks.append(lines[k])
                k += 1
            if k < n and lines[k].lstrip().startswith(('"""', "'''")):
                # drop the second consecutive docblock; keep only one and a single blank line
                out.extend(block)
                out.append('\n')
                # skip the duplicate block by advancing k to its end
                q2 = '"""' if lines[k].lstrip().startswith('"""') else "'''"
                m = k + 1
                while m < n and q2 not in lines[m]:
                    m += 1
                if m < n:
                    i = m + 1
                    changed = True
                    continue
            # normal path: emit block and continue
            out.extend(block)
            i = j + 1
            # preserve a single blank line after a docblock
            if i < n and lines[i].strip() == '':
                out.append('\n')
                while i < n and lines[i].strip() == '':
                    i += 1
            continue
        out.append(line)
        i += 1
    new = ''.join(out)
    if new != text:
        path.write_text(new, encoding='utf-8')
        return True
    return False


def main(paths):
    targets = []
    for p in paths:
        pth = Path(p)
        if pth.is_dir():
            for f in pth.rglob('*.py'):
                if 'routes' in f.parts:
                    targets.append(f)
        elif pth.suffix == '.py':
            targets.append(pth)
    for f in sorted(set(targets)):
        if dedupe_file(f):
            print(f'deduped: {f}')


if __name__ == '__main__':
    args = sys.argv[1:] or ['backend-services/routes']
    main(args)

