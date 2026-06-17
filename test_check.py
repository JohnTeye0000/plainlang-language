"""
Tests for the static analyzer (plaincheck.py). Run:  python test_check.py
"""

import plaincheck as pc


def diags(src):
    ds, _ = pc.check_source(src)
    return ds

def messages(src):
    return " || ".join(d.message for d in diags(src))

def severities(src):
    return [getattr(d, "severity", "error") for d in diags(src)]


PASS = FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ✓ {name}")
    else:
        FAIL += 1; print(f"  ✗ {name}   {detail}")

def has(name, src, needle, severity=None):
    ds = diags(src)
    found = any(needle in (d.message + " " + (d.hint or "")) and
                (severity is None or getattr(d, "severity", "error") == severity) for d in ds)
    check(name, found, f"no {severity or ''} diag containing {needle!r} in: {messages(src)!r}")

def clean(name, src):
    ds = diags(src)
    check(name, len(ds) == 0, f"expected no problems, got: {messages(src)!r}")


# ── clean programs must not be flagged (precision matters in a linter) ────────
print("No false positives")
clean("simple program", 'set x to 5\nsay x plus 1')
clean("for-each over a list", 'set xs to list of 1, 2, 3\nset t to 0\nfor each n in xs\nset t to t plus n\nend\nsay t')
clean("loop variable need not be used", 'count i from 1 to 3\nsay "hello"\nend')
clean("function parameter need not be used", 'define noop with n\nreturn 0\nend\nsay noop with 5')
clean("function may read a global", 'set base to 100\ndefine bump with x\nreturn base plus x\nend\nsay bump with 1')
clean("recursion is fine", 'define f with n\nif n is at most 1 then\nreturn 1\nend\nreturn n multiplied by f with (n minus 1)\nend\nsay f with 5')
clean("variable used only inside a function", 'set total to 0\ndefine show\nsay total\nend\ncall show')

# ── each kind of problem is detected ──────────────────────────────────────────
print("Detects problems")
has("undefined variable", 'set score to 1\nsay scor', "haven't heard of a variable", "error")
has("undefined offers suggestion", 'set score to 1\nsay scor', "Did you mean 'score'?")
has("unused variable", 'set keepme to 5\nset unused to 9\nsay keepme', "never use", "warning")
has("unknown function", 'say nope with 1', "don't know a function", "error")
has("arity too many", 'define f with a\nreturn a\nend\nsay f with 1 and 2', "expects 1", "error")
has("arity too few", 'define f with a and b\nreturn a\nend\nsay f with 1', "expects 2", "error")
has("unreachable code", 'define f with n\nreturn n\nsay "after"\nend\nsay f with 1', "can never run", "warning")
has("stop outside a loop", 'say "x"\nstop', "only be used inside a loop", "error")
has("skip outside a loop", 'skip', "only be used inside a loop", "error")
clean("stop inside a loop is fine", 'count i from 1 to 5\nif i is equal to 3 then\nstop\nend\nsay i\nend')
clean("function used as a first-class value", 'define f with n\nreturn n\nend\nset g to f\nsay g with 3')
clean("calling a function held in a variable is not flagged", 'define f with n\nreturn n\nend\nset g to f\nsay g with 3')

# ── multi-error reporting: many problems at once ──────────────────────────────
print("Multi-error reporting")
multi = 'set a to 1\nsay b\nsay c\ncall nope'
check("reports several problems in one pass", len(diags(multi)) >= 3, f"got {len(diags(multi))}: {messages(multi)!r}")
check("problems are sorted by line",
      [d.line for d in diags(multi)] == sorted(d.line for d in diags(multi)))

# ── a syntax error is reported (not crashed on) ──────────────────────────────
print("Syntax errors")
has("syntax error surfaces", 'if x is greater 3 then\nend', "expected the word 'than'", "error")

print(f"\n{PASS} passed, {FAIL} failed")
import sys
sys.exit(1 if FAIL else 0)
