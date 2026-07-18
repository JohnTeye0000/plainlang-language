"""
plainfmt — a code formatter for PlainLang, in the spirit of gofmt/prettier.

Re-indents a program from its block structure (if/count/while/repeat/for/define/
match ... end) and normalizes whitespace, so every PlainLang file in a project
looks the same regardless of who wrote it. It does not touch string literals or
comments, and it never changes what a program *does* — only how it looks.

Usage:
    python plainfmt.py program.plang            # print the formatted result
    python plainfmt.py --write program.plang     # format the file in place
    python plainfmt.py --check program.plang     # exit 1 if the file isn't formatted
"""

import re
import sys

INDENT = "    "

BLOCK_OPENERS = {"if", "count", "while", "repeat", "for", "define", "match"}
MID_MARKERS = {"otherwise", "when"}
DEDENT_MARKERS = {"end"}

_STR_OR_REST = re.compile(r'"[^"]*"|[^"]+')
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _split_code_comment(line):
    """Split a source line into (code, comment) at the first '#' outside a string."""
    in_str = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_str = not in_str
        elif ch == "#" and not in_str:
            return line[:i], line[i:]
    return line, ""


def _normalize_code(code):
    """Collapse whitespace and fix punctuation spacing, without touching strings."""
    parts = []
    for chunk in _STR_OR_REST.findall(code):
        if chunk.startswith('"'):
            parts.append(chunk)
        else:
            chunk = re.sub(r"\s+", " ", chunk)
            chunk = re.sub(r"\s+,", ",", chunk)
            chunk = re.sub(r",(?=\S)", ", ", chunk)
            chunk = re.sub(r"\(\s+", "(", chunk)
            chunk = re.sub(r"\s+\)", ")", chunk)
            parts.append(chunk)
    return "".join(parts).strip()


def _first_word(code):
    m = _WORD.match(code)
    return m.group().lower() if m else None


def format_source(source):
    out_lines = []
    level = 0
    blank_run = 0

    for raw_line in source.splitlines():
        code, comment = _split_code_comment(raw_line)
        code = _normalize_code(code)
        comment = comment.strip()

        if not code and not comment:
            blank_run += 1
            if blank_run <= 1:
                out_lines.append("")
            continue
        blank_run = 0

        word = _first_word(code) if code else None
        this_level = level
        if word in DEDENT_MARKERS:
            level = max(0, level - 1)
            this_level = level
        elif word in MID_MARKERS:
            this_level = max(0, level - 1)

        text = f"{INDENT * this_level}{code}" if code else ""
        if comment:
            text = f"{text}  {comment}" if text else f"{INDENT * this_level}{comment}"
        out_lines.append(text)

        if word in BLOCK_OPENERS:
            level += 1

    while out_lines and out_lines[-1] == "":
        out_lines.pop()
    return "\n".join(out_lines) + "\n"


def main():
    args = sys.argv[1:]
    write = "--write" in args
    check = "--check" in args
    args = [a for a in args if a not in ("--write", "--check")]
    if not args:
        print("usage: python plainfmt.py [--write | --check] program.plang", file=sys.stderr)
        sys.exit(2)

    path = args[0]
    with open(path, encoding="utf-8") as f:
        source = f.read()
    formatted = format_source(source)

    if check:
        if source == formatted:
            print(f"{path} is already formatted.")
            sys.exit(0)
        print(f"{path} is NOT formatted.")
        sys.exit(1)

    if write:
        if source != formatted:
            with open(path, "w", encoding="utf-8") as f:
                f.write(formatted)
            print(f"formatted {path}")
        else:
            print(f"{path} is already formatted.")
        sys.exit(0)

    sys.stdout.write(formatted)


if __name__ == "__main__":
    main()
