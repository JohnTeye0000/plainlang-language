"""
Tests for plainfmt.py, the code formatter.

Two properties matter more than exact output: formatting a program never
changes what it does, and formatting an already-formatted program is a
no-op (idempotent) — the two properties gofmt/prettier are graded on.

Run with:   python test_fmt.py
"""

import plainfmt as fmt
import plainlang as pl

PASS = FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}")


def run(source):
    out = []
    pl.run_source(source, on_output=out.append)
    return out


PROGRAMS = [
    'set   name  to "Alice"\nsay "Hi, " plus name',
    'if 3 is greater than 1   then\nsay "yes"\notherwise\nsay "no"\nend',
    'set a to 15\nif a is at least 18 then\nsay "adult"\notherwise if a is at least 13 then\nsay "teen"\notherwise\nsay "kid"\nend',
    'count i from 1 to 3\nsay (i multiplied by 2)\nend',
    'set xs to list of 1,2,  3 , 4\nsay xs',
    'define double with n\nreturn n multiplied by 2\nend\nsay double with 21',
    'match 2\nwhen 1 then\nsay "one"\nwhen 2 then\nsay "two"\notherwise\nsay "other"\nend',
    '# a comment\nsay "hi"   # trailing comment\n\n\nsay "bye"',
    'while  x is less than 3\nset x to x plus 1\nend',
]

print("Behavior preservation")
for i, src in enumerate(PROGRAMS):
    src_full = ("set x to 0\n" if "x is less than" in src else "") + src
    formatted = fmt.format_source(src_full)
    check(f"program {i}: output unchanged after formatting", run(src_full) == run(formatted))

print("Idempotence")
for i, src in enumerate(PROGRAMS):
    once = fmt.format_source(src)
    twice = fmt.format_source(once)
    check(f"program {i}: formatting a formatted program is a no-op", once == twice)

print("Formatting fixes")
check(
    "re-indents a block body",
    fmt.format_source('if true then\nsay "a"\nend') == 'if true then\n    say "a"\nend\n',
)
check(
    "otherwise sits back at the parent level",
    fmt.format_source('if true then\nsay "a"\notherwise\nsay "b"\nend')
    == 'if true then\n    say "a"\notherwise\n    say "b"\nend\n',
)
check(
    "collapses extra internal whitespace outside strings",
    fmt.format_source('set   x   to   1') == 'set x to 1\n',
)
check(
    "leaves whitespace inside string literals alone",
    fmt.format_source('say "a   b"') == 'say "a   b"\n',
)
check(
    "normalizes comma spacing",
    fmt.format_source('set xs to list of 1,2 ,3') == 'set xs to list of 1, 2, 3\n',
)
check(
    "preserves a trailing comment on its line",
    fmt.format_source('say "hi"   # note') == 'say "hi"  # note\n',
)
check(
    "collapses multiple blank lines to one",
    fmt.format_source('say "a"\n\n\n\nsay "b"') == 'say "a"\n\nsay "b"\n',
)
check(
    "already-formatted demo.plang is left byte-identical",
    (lambda src: fmt.format_source(src) == src)(open("demo.plang", encoding="utf-8").read()),
)

print("Property test on generated programs")
import random
import fuzz, fuzz_wasm


def outcome(source):
    """What a program does, ignoring how errors quote the source line (which the formatter
    legitimately re-indents)."""
    out = []
    ok, _ = pl.run_source(source, on_output=out.append)
    if ok:
        return True, out, None
    lines = [l.strip() for l in out[-1].strip().split("\n") if l.strip()]
    return False, out[:-1], lines[1] if len(lines) > 1 else lines[0]


changed, unstable, n = [], [], 0
for gen in (fuzz.Generator, fuzz_wasm.Generator):
    for k in range(400):
        src = gen(random.Random(k)).program()
        n += 1
        formatted = fmt.format_source(src)
        if outcome(formatted) != outcome(src):
            changed.append(k)
        if fmt.format_source(formatted) != formatted:
            unstable.append(k)
check(f"formatting never changes what any of {n} random programs does", not changed, changed[:5])
check(f"formatting is idempotent on all {n} random programs", not unstable, unstable[:5])

print(f"\n{PASS} passed, {FAIL} failed")
if FAIL:
    raise SystemExit(1)
