#!/usr/bin/env python3
import sys
import re
import tokenize
from io import BytesIO
from pathlib import Path

def strip_inline_comments_python(code: str) -> str:
    out_tokens = []
    try:
        tok_iter = tokenize.tokenize(BytesIO(code.encode("utf-8")).readline)
        for tok in tok_iter:
            if tok.type == tokenize.COMMENT:

                if tok.start[1] == 0:
                    out_tokens.append(tok)

            else:
                out_tokens.append(tok)
        new_code = tokenize.untokenize(out_tokens).decode("utf-8")
    except Exception:

        new_lines = []
        for line in code.splitlines(True):
            if '#' in line:

                idx = line.find('#')
                if idx > 0 and line[:idx].strip():
                    line = line[:idx].rstrip() + ("\n" if line.endswith("\n") else "")
            new_lines.append(line)
        new_code = ''.join(new_lines)

    lines = new_code.splitlines()
    collapsed = []
    blank_run = 0
    for ln in lines:
        if ln.strip() == "":
            blank_run += 1
            if blank_run <= 1:
                collapsed.append("")
        else:
            blank_run = 0
            collapsed.append(ln.rstrip())
    return "\n".join(collapsed) + ("\n" if new_code.endswith("\n") else "")

def strip_inline_comments_ts(code: str) -> str:
    def remove_trailing_line_comment(s: str) -> str:
        i = 0
        n = len(s)
        in_single = False
        in_double = False
        in_backtick = False
        escape = False
        while i < n:
            ch = s[i]
            if escape:
                escape = False
                i += 1
                continue
            if ch == "\\":
                escape = True
                i += 1
                continue
            if not (in_single or in_double or in_backtick):
                if ch == '"':
                    in_double = True
                elif ch == "'":
                    in_single = True
                elif ch == "`":
                    in_backtick = True
                elif ch == "/" and i + 1 < n and s[i + 1] == "/":

                    prefix = s[:i]
                    if prefix.strip() == "":

                        return s
                    else:

                        return prefix.rstrip()
                elif ch == "/" and i + 1 < n and s[i + 1] == "*":

                    end = s.find("*/", i + 2)
                    if end != -1:
                        prefix = s[:i]
                        suffix = s[end + 2:]
                        if prefix.strip():

                            s = (prefix.rstrip() + (" " if suffix and suffix.strip().startswith(('+','-','*','/')) else "") + suffix.lstrip())

                            n = len(s)
                            i = len(prefix)
                            continue
                        else:

                            return s

            else:
                if in_double and ch == '"':
                    in_double = False
                elif in_single and ch == "'":
                    in_single = False
                elif in_backtick and ch == "`":
                    in_backtick = False
            i += 1
        return s.rstrip()

    processed = []
    for line in code.splitlines(True):

        newline = "\n" if line.endswith("\n") else ("\r\n" if line.endswith("\r\n") else "")
        core = line[:-len(newline)] if newline else line
        processed.append(remove_trailing_line_comment(core) + newline)

    lines = ''.join(processed).splitlines()
    collapsed = []
    blank_run = 0
    for ln in lines:
        stripped = ln.strip()
        # Remove stray JSX placeholders left by comment removal
        if stripped == "{}":
            continue
        if stripped == "":
            blank_run += 1
            if blank_run <= 1:
                collapsed.append("")
        else:
            blank_run = 0
            collapsed.append(ln.rstrip())
    return "\n".join(collapsed) + ("\n" if processed and processed[-1].endswith("\n") else "")

def main(paths):
    exts_py = {".py"}
    exts_ts = {".ts", ".tsx"}
    touched = []
    skip_dirs = {"node_modules", "venv", ".venv", ".git", "dist", "build"}
    for p in paths:
        path = Path(p)
        if path.is_dir():
            for f in path.rglob("*"):
                if not f.is_file():
                    continue
                # Skip files inside ignored directories
                parts = set(part for part in f.parts)
                if parts & skip_dirs:
                    continue
                if f.suffix in exts_py | exts_ts:
                    touched.append(f)
        else:
            if path.suffix in exts_py | exts_ts:
                touched.append(path)

    for f in sorted(set(touched)):
        try:
            original = f.read_text(encoding="utf-8")
        except Exception:
            continue
        if f.suffix in exts_py:
            cleaned = strip_inline_comments_python(original)
        else:
            cleaned = strip_inline_comments_ts(original)
        if cleaned != original:
            f.write_text(cleaned, encoding="utf-8")
            print(f"cleaned: {f}")

if __name__ == "__main__":
    args = sys.argv[1:] or ["."]
    main(args)
