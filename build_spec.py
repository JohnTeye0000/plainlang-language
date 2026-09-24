"""
Assembles SPEC.md, the PlainLang language specification.

    python build_spec.py            # (re)write SPEC.md
    python build_spec.py --check    # exit 1 if SPEC.md is out of date

SPEC.md is generated, never hand-edited, from:
  * spec_content.py   the prose and the executable examples
  * grammar.ebnf      the syntactic grammar, included verbatim
  * plainlang.KEYWORDS the reserved words, straight from the tokenizer
so it cannot drift from the language. test_spec.py runs every example.
"""

import os
import sys

import plainlang as pl
import spec_content as sc

HERE = os.path.dirname(os.path.abspath(__file__))
TURTLE_WORDS = {"move", "forward", "backward", "back", "turn", "left", "right", "pen", "up", "down", "color", "wait"}


def keyword_table():
    core = sorted(k for k in pl.KEYWORDS if k not in TURTLE_WORDS)
    lines = []
    row = []
    for k in core:
        row.append(f"`{k}`")
        if len(row) == 8:
            lines.append(" ".join(row)); row = []
    if row:
        lines.append(" ".join(row))
    core_md = "  \n".join(lines)
    turtle_md = " ".join(f"`{k}`" for k in sorted(TURTLE_WORDS))
    return f"{core_md}\n\nThe browser's turtle vocabulary is reserved everywhere too, so a name means the same in every implementation: {turtle_md}."


def render_example(ex):
    out = ["```", ex["code"], "```"]
    if "expect" in ex:
        out += ["prints:", "```", *ex["expect"], "```"]
    else:
        out += [f"is an error, and the message contains *“{ex['error']}”*."]
    return "\n".join(out)


def generate():
    grammar = open(os.path.join(HERE, "grammar.ebnf"), encoding="utf-8").read().rstrip("\n")
    parts = [sc.INTRO, sc.LEXICAL.format(keywords=keyword_table()),
             "## 3. Syntax\n\nThe syntax is given by this grammar, in the notation described at its top. "
             "It is exactly [`grammar.ebnf`](grammar.ebnf).\n\n```ebnf\n" + grammar + "\n```\n",
             "## 4. Meaning\n"]
    for section in sc.SEMANTICS:
        parts.append(f"### {section['title']}\n")
        for statement, examples in section["rules"]:
            parts.append(statement + "\n")
            for ex in examples:
                parts.append(render_example(ex) + "\n")
    parts += [sc.TURTLE, sc.MODULES, sc.CONFORMANCE]
    return "\n".join(parts).rstrip("\n") + "\n"


def main(argv):
    path = os.path.join(HERE, "SPEC.md")
    text = generate()
    if "--check" in argv:
        current = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
        if current.replace("\r\n", "\n") != text:
            print("SPEC.md is out of date — run: python build_spec.py")
            return 1
        print("SPEC.md is up to date")
        return 0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote {path} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
