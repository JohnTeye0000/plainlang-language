"""
Tests for the diagnostics system: caret underlines, source excerpts, and
"did you mean?" suggestions. Run with:  python test_diagnostics.py
"""

import plainlang as pl


def render(source):
    out = []
    pl.run_source(source, on_output=out.append)
    return "\n".join(out)


PASS = FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ✓ {name}")
    else:
        FAIL += 1; print(f"  ✗ {name}   {detail}")

def contains(name, source, *needles):
    text = render(source)
    missing = [n for n in needles if n not in text]
    check(name, not missing, f"missing {missing!r} in:\n{text}")

def excludes(name, source, needle):
    text = render(source)
    check(name, needle not in text, f"unexpectedly found {needle!r}")


# ── suggest() / edit distance unit tests ──────────────────────────────────────
print("Suggestion engine")
check("levenshtein basic", pl._levenshtein("kitten", "sitting") == 3)
check("suggest close match", pl.suggest("scor", ["score", "total"]) == "score")
check("suggest picks nearest", pl.suggest("totl", ["score", "total"]) == "total")
check("suggest rejects far", pl.suggest("xyzzy", ["score", "total"]) is None)
check("suggest deterministic on ties",
      pl.suggest("aa", ["ab", "ac"]) == pl.suggest("aa", ["ac", "ab"]))

# ── caret underline + source excerpt ──────────────────────────────────────────
print("Caret underlines")
contains("excerpt shows the source line", 'set score to 1\nsay scor', "say scor")
contains("caret underlines the token", 'set score to 1\nsay scor', "^^^^")
contains("syntax error gets a caret", 'set x to 5\nif x is greater 3 then\nend', "^")

# ── did-you-mean suggestions ──────────────────────────────────────────────────
print("Did-you-mean")
contains("unknown variable", 'set score to 90\nsay scor', "Did you mean 'score'?")
contains("unknown function",
         'define greet with who\nreturn who\nend\nsay gret with "x"', "Did you mean 'greet'?")
contains("mistyped statement keyword", 'saay "hello"', "Did you mean 'say'?")
contains("mistyped 'set'", 'sett x to 5', "Did you mean 'set'?")
excludes("no false suggestion for far-off name", 'say qqq', "Did you mean")

# ── the suggestion is correct, not just present ──────────────────────────────
print("Correctness")
contains("suggests the actual variable in scope",
         'set apple to 1\nset banana to 2\nsay aple', "Did you mean 'apple'?")

print(f"\n{PASS} passed, {FAIL} failed")
import sys
sys.exit(1 if FAIL else 0)
