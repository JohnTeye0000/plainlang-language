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
clean("map/filter/reduce reference functions", 'define double with n\nreturn n multiplied by 2\nend\nset xs to list of 1, 2, 3\nsay map double over xs')
has("undefined variable inside string interpolation",
    'set score to 1\nsay "you got {scor}"', "haven't heard of a variable", "error")
clean("interpolation of a defined variable is fine", 'set name to "Al"\nsay "Hi {name}"')
clean("calling a function held in a variable is not flagged", 'define f with n\nreturn n\nend\nset g to f\nsay g with 3')

# ── gradual type checking ─────────────────────────────────────────────────────
print("Type checking")
has("text minus a number (literal)", 'say "a" minus 1', "only works with numbers", "error")
has("text variable used in arithmetic", 'set name to "Bob"\nsay name minus 1', "only works with numbers", "error")
has("square root of text", 'say square root of "x"', "needs a number", "error")
has("length of a number", 'say length of 5', "length of", "error")
has("compare a number with text", 'if 5 is greater than "a" then\nsay "x"\nend', "can't compare", "error")
has("map needs a function", 'say map 5 over (list of 1, 2)', "needs a function", "error")
has("sum of a number", 'say sum of 5', "needs a list", "error")
# gradual: unknown types are never flagged (no false positives)
clean("unknown parameter type is not flagged", 'define f with n\nsay n minus 1\nend\nsay f with 1')
clean("input (number-or-text) is not flagged", 'ask "age?" into a\nsay a plus 1')
clean("number variable in arithmetic is fine", 'set x to 5\nsay x minus 1')
clean("text concatenation with plus is fine", 'set name to "Al"\nsay name plus "!" plus 1')
clean("ask-assigned variable is defined", 'ask "name?" into who\nsay who')

# ── multi-error reporting: many problems at once ──────────────────────────────
print("Multi-error reporting")
multi = 'set a to 1\nsay b\nsay c\ncall nope'
check("reports several problems in one pass", len(diags(multi)) >= 3, f"got {len(diags(multi))}: {messages(multi)!r}")
check("problems are sorted by line",
      [d.line for d in diags(multi)] == sorted(d.line for d in diags(multi)))

# ── a syntax error is reported (not crashed on) ──────────────────────────────
print("Syntax errors")
has("syntax error surfaces", 'if x is greater 3 then\nend', "expected the word 'than'", "error")

# ── error recovery: several syntax errors in one pass ─────────────────────────
print("Error recovery")
_two = 'if a is greater 3 then\nsay "x"\nend\nif b is less 4 then\nsay "y"\nend'
check("reports several syntax errors at once (recovery)", len(diags(_two)) >= 2,
      f"got {len(diags(_two))}: {messages(_two)!r}")
clean("a valid program is still clean after recovery was added",
      'set x to 5\nif x is greater than 3 then\nsay "big"\nend')

# regression: 'plus' also joins text and lists, so an unknown + unknown is unknown, never "number"
clean("plus of two unknowns is not assumed to be a number",
      'define f with a and b\nreturn length of (a plus b)\nend\nsay f with "x" and "y"')

# ── property test: the README promises "correct programs are never flagged" ─────────
# Generate thousands of programs; whenever one RUNS CLEANLY, the checker must report no
# *errors* (warnings such as unused variables are fine). Found the bug above.
print("Precision, checked by fuzzing")
import random
import fuzz, fuzz_wasm
import plainlang as pl

checked = 0
false_positives = []
for gen in (fuzz.Generator, fuzz_wasm.Generator):
    for k in range(400):
        src = gen(random.Random(k)).program()
        out = []
        ok, _ = pl.run_source(src, on_output=out.append)
        if not ok:
            continue
        checked += 1
        errs = [d for d in diags(src) if getattr(d, "severity", "error") == "error"]
        if errs:
            false_positives.append((errs[0].message, src.split("\n")[(errs[0].line or 1) - 1][:100]))
check(f"no false-positive errors on {checked} programs that run cleanly", not false_positives, false_positives[:2])

print(f"\n{PASS} passed, {FAIL} failed")
import sys
sys.exit(1 if FAIL else 0)
