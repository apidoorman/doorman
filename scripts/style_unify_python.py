#!/usr/bin/env python3
import sys
import re
import tokenize
from io import BytesIO
from pathlib import Path

INTERNAL_PREFIXES = {
    "models",
    "services",
    "routes",
    "utils",
    "doorman",
    "generated",
}


def normalize_quotes(code: str) -> str:
    out = []
    try:
        tokens = list(tokenize.tokenize(BytesIO(code.encode("utf-8")).readline))
        for tok in tokens:
            if tok.type == tokenize.STRING:
                s = tok.string
                # Skip triple-quoted strings (likely docstrings)
                low = s.lower()
                if "'''" in s or '"""' in s:
                    out.append(tok)
                    continue
                # Extract prefix (e.g., r, u, f, fr)
                m = re.match(r"^([rubfRUBF]*)([\'\"])(.*)([\'\"])$", s, re.S)
                if not m:
                    out.append(tok)
                    continue
                prefix, q1, body, q2 = m.groups()
                if q1 != q2:
                    out.append(tok)
                    continue
                quote = q1
                # Only convert double to single when safe (no single quotes inside)
                if quote == '"' and "'" not in body:
                    new_s = f"{prefix}'{body}'"
                    out.append(tokenize.TokenInfo(tok.type, new_s, tok.start, tok.end, tok.line))
                else:
                    out.append(tok)
            else:
                out.append(tok)
        new_code = tokenize.untokenize(out).decode("utf-8")
        return new_code
    except Exception:
        return code


def reorder_imports_with_headers(lines: list[str]) -> list[str]:
    i = 0
    n = len(lines)

    # Skip shebang/encoding
    while i < n and (lines[i].lstrip().startswith('#!') or lines[i].lstrip().startswith('# -*-')):
        i += 1

    # Preserve initial blank lines
    start = i
    while i < n and lines[i].strip() == "":
        i += 1

    # Skip initial module docstring (triple quotes)
    doc_start = i
    if i < n and lines[i].lstrip().startswith(('"""', "'''")):
        quote = '"""' if lines[i].lstrip().startswith('"""') else "'''"
        i += 1
        while i < n and quote not in lines[i]:
            i += 1
        if i < n:
            i += 1
        # Skip any following blank lines
        while i < n and lines[i].strip() == "":
            i += 1

    import_start = i
    # Collect contiguous import block
    imports = []
    while i < n and (
        lines[i].lstrip().startswith('import ')
        or lines[i].lstrip().startswith('from ')
        or lines[i].strip().startswith('#')
        or lines[i].strip() == ''
    ):
        imports.append(lines[i])
        i += 1

    if not imports:
        return lines

    # Split imports into actual import lines, ignore existing section comments
    import_lines = [ln for ln in imports if ln.lstrip().startswith(('import ', 'from '))]

    def classify(line: str) -> str:
        s = line.strip()
        if s.startswith('from '):
            mod = s[5:].split('import', 1)[0].strip()
            if mod.startswith('.'):
                return 'internal'
        elif s.startswith('import '):
            mod = s[7:].split(' as ', 1)[0].split(',', 1)[0].strip()
        else:
            return 'other'
        root = mod.split('.')[0]
        return 'internal' if root in INTERNAL_PREFIXES else 'external'

    external = []
    internal = []
    for ln in import_lines:
        (internal if classify(ln) == 'internal' else external).append(ln.rstrip())

    # De-duplicate while preserving ordering
    def dedupe(seq):
        seen = set()
        out = []
        for item in seq:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out

    external = dedupe(external)
    internal = dedupe(internal)

    new_block = []
    if external:
        new_block.append('# External imports')
        new_block.extend(external)
    if internal:
        if new_block:
            new_block.append('')
        new_block.append('# Internal imports')
        new_block.extend(internal)
    new_block.append('')

    # Reconstruct file
    result = []
    result.extend(lines[:import_start])
    result.extend([ln + ('' if ln.endswith('\n') else '\n') for ln in new_block])
    # Skip original imports and any trailing blank lines in that region
    j = i
    while j < n and lines[j].strip() == "":
        j += 1
    result.extend(lines[j:])
    return result


def process_file(path: Path):
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        return False
    # Normalize quotes first
    new_text = normalize_quotes(text)
    # Reorder imports with headers
    new_lines = reorder_imports_with_headers(new_text.splitlines(True))
    final = ''.join(new_lines)
    if final != text:
        path.write_text(final, encoding='utf-8')
        print(f"styled: {path}")
        return True
    return False


def main(paths):
    touched = []
    for p in paths:
        pth = Path(p)
        if pth.is_dir():
            for f in pth.rglob('*.py'):
                # Skip common non-source dirs
                if any(part in {'.git', 'venv', '.venv', '__pycache__', 'generated'} for part in f.parts):
                    continue
                touched.append(f)
        elif pth.suffix == '.py':
            touched.append(pth)
    for f in sorted(set(touched)):
        process_file(f)


if __name__ == '__main__':
    args = sys.argv[1:] or ['backend-services']
    main(args)
