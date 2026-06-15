"""
Test suite for the PlainLang interpreter.

Run with:   python test_plainlang.py
Exits non-zero if any test fails, so it can gate CI.
"""

import plainlang as pl


def run(source, inputs=None):
    """Run a program and capture everything it prints as a list of lines."""
    out = []
    inputs = list(inputs or [])
    def on_output(s): out.append(s)
    def on_input(_): return inputs.pop(0) if inputs else ""
    ok, _ = pl.run_source(source, on_output=on_output, on_input=on_input)
    return ok, out


# ── tiny test framework ───────────────────────────────────────────────────────
PASS, FAIL = 0, 0
def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}   {detail}")

def expect_output(name, source, expected, inputs=None):
    ok, out = run(source, inputs)
    check(name, ok and out == expected, f"got {out!r}, expected {expected!r}")

def expect_error(name, source, fragment):
    ok, out = run(source)
    joined = "\n".join(out)
    check(name, (not ok) and fragment.lower() in joined.lower(),
          f"expected error containing {fragment!r}, got ok={ok} out={joined!r}")


# ── variables & arithmetic ────────────────────────────────────────────────────
print("Variables & math")
expect_output("set + say", 'set x to 5\nsay x', ["5"])
expect_output("string concat", 'set n to "Al"\nsay "Hi " plus n', ["Hi Al"])
expect_output("precedence: * before +", 'say 2 plus 3 multiplied by 4', ["14"])
expect_output("parentheses override", 'say (2 plus 3) multiplied by 4', ["20"])
expect_output("subtraction & division", 'say 10 minus 4\nsay 12 divided by 3', ["6", "4"])
expect_output("division keeps fractions", 'say 7 divided by 2', ["3.5"])
expect_output("unary minus", 'say minus 5 plus 8', ["3"])
expect_output("int formatting (no .0)", 'say 4 multiplied by 0.5 plus 8', ["10"])

# ── comparisons & booleans ────────────────────────────────────────────────────
print("Comparisons & booleans")
expect_output("greater than", 'if 5 is greater than 3 then\nsay "y"\nend', ["y"])
expect_output("at least (>=)", 'if 5 is at least 5 then\nsay "y"\nend', ["y"])
expect_output("at most (<=)", 'if 4 is at most 3 then\nsay "n"\notherwise\nsay "y"\nend', ["y"])
expect_output("is not equal", 'if 4 is not equal to 5 then\nsay "y"\nend', ["y"])
expect_output("and", 'if true and false then\nsay "n"\notherwise\nsay "y"\nend', ["y"])
expect_output("or", 'if false or true then\nsay "y"\nend', ["y"])
expect_output("not", 'if not false then\nsay "y"\nend', ["y"])
expect_output("boolean stored in var", 'set b to 5 is greater than 2\nsay b', ["true"])

# ── decisions ─────────────────────────────────────────────────────────────────
print("Decisions")
expect_output("otherwise-if chain",
    'set a to 15\nif a is at least 18 then\nsay "adult"\n'
    'otherwise if a is at least 13 then\nsay "teen"\notherwise\nsay "kid"\nend', ["teen"])

# ── loops ─────────────────────────────────────────────────────────────────────
print("Loops")
expect_output("repeat", 'repeat 3 times\nsay "x"\nend', ["x", "x", "x"])
expect_output("count up", 'count i from 1 to 3\nsay i\nend', ["1", "2", "3"])
expect_output("count down", 'count i from 3 to 1\nsay i\nend', ["3", "2", "1"])
expect_output("while", 'set x to 0\nwhile x is less than 3\nset x to x plus 1\nsay x\nend', ["1", "2", "3"])
expect_output("variable persists after loop",
    'set t to 0\ncount i from 1 to 4\nset t to t plus i\nend\nsay t', ["10"])

# ── loop control: stop / skip ──────────────────────────────────────────────────
print("Loop control (stop / skip)")
expect_output("stop exits a loop",
    'count i from 1 to 9\nif i is greater than 3 then\nstop\nend\nsay i\nend', ["1", "2", "3"])
expect_output("skip jumps to next pass",
    'count i from 1 to 5\nif i is equal to 3 then\nskip\nend\nsay i\nend', ["1", "2", "4", "5"])
expect_output("skip in a while still advances",
    'set x to 0\nwhile x is less than 5\nset x to x plus 1\nif x is equal to 2 then\nskip\nend\nsay x\nend', ["1", "3", "4", "5"])
expect_output("stop only exits the inner loop",
    'count a from 1 to 2\ncount b from 1 to 9\nif b is greater than 1 then\nstop\nend\nsay a plus "-" plus b\nend\nend', ["1-1", "2-1"])
expect_output("stop in for-each",
    'for each n in list of 5, 6, 7, 8\nif n is equal to 7 then\nstop\nend\nsay n\nend', ["5", "6"])
expect_error("stop outside a loop is an error", 'say "hi"\nstop', "only be used inside a loop")

# ── lists ─────────────────────────────────────────────────────────────────────
print("Lists")
expect_output("list literal & length", 'set xs to list of 1, 2, 3\nsay length of xs', ["3"])
expect_output("indexing (1-based)", 'set xs to list of 10, 20, 30\nsay item 2 of xs', ["20"])
expect_output("for each", 'set xs to list of 1, 2, 3\nset s to 0\nfor each x in xs\nset s to s plus x\nend\nsay s', ["6"])
expect_output("add to list", 'set xs to empty list\nadd 1 to xs\nadd 2 to xs\nsay xs', ["[1, 2]"])
expect_output("remove from list", 'set xs to list of 1, 2, 3\nremove item 2 from xs\nsay xs', ["[1, 3]"])
expect_output("list display", 'say list of "a", "b"', ["[a, b]"])
expect_output("set list element", 'set xs to list of 1, 2, 3\nset item 2 of xs to 99\nsay xs', ["[1, 99, 3]"])

# ── records (dictionaries) ─────────────────────────────────────────────────────
print("Records")
expect_output("create & read", 'set p to record with "name" as "Al", "age" as 9\nsay item "name" of p', ["Al"])
expect_output("length is key count", 'set p to record with "a" as 1, "b" as 2\nsay length of p', ["2"])
expect_output("keys of", 'set p to record with "a" as 1, "b" as 2\nsay keys of p', ["[a, b]"])
expect_output("set a field (update)", 'set p to record with "n" as 1\nset item "n" of p to 5\nsay item "n" of p', ["5"])
expect_output("set a field (new key)", 'set p to empty record\nset item "x" of p to 7\nsay p', ["{x: 7}"])
expect_output("iterate keys", 'set p to record with "a" as 1, "b" as 2\nset t to 0\nfor each k in keys of p\nset t to t plus item k of p\nend\nsay t', ["3"])
expect_output("record display", 'say record with "a" as 1, "b" as "two"', ["{a: 1, b: two}"])
expect_error("missing key", 'set p to record with "name" as "Al"\nsay item "naem" of p', "no key")
expect_error("missing key suggests", 'set p to record with "name" as "Al"\nsay item "naem" of p', "Did you mean 'name'?")

# ── functions & recursion ─────────────────────────────────────────────────────
print("Functions & recursion")
expect_output("function with return",
    'define double with n\nreturn n multiplied by 2\nend\nsay double with 21', ["42"])
expect_output("function as action (call)",
    'define greet with who\nsay "Hi " plus who\nend\ncall greet with "Al"', ["Hi Al"])
expect_output("multiple parameters",
    'define combine with a and b\nreturn a plus b\nend\nsay combine with 3 and 4', ["7"])
expect_output("recursion (factorial)",
    'define f with n\nif n is at most 1 then\nreturn 1\nend\n'
    'return n multiplied by f with (n minus 1)\nend\nsay f with 5', ["120"])

# ── built-in helpers ──────────────────────────────────────────────────────────
print("Built-ins")
expect_output("uppercase", 'say uppercase of "hi"', ["HI"])
expect_output("lowercase", 'say lowercase of "HI"', ["hi"])
expect_output("round", 'say round of 3.7', ["4"])
expect_output("absolute", 'say absolute of (minus 8)', ["8"])
expect_output("square root", 'say square root of 144', ["12"])
expect_output("length of text", 'say length of "hello"', ["5"])

# ── input ─────────────────────────────────────────────────────────────────────
print("Input")
expect_output("ask reads & coerces numbers",
    'ask "n?" into n\nsay n plus 1', ["6"], inputs=["5"])
expect_output("ask keeps text",
    'ask "name?" into name\nsay "Hi " plus name', ["Hi Sam"], inputs=["Sam"])

# ── friendly errors ───────────────────────────────────────────────────────────
print("Friendly errors")
expect_error("unknown variable", 'say mystery', "haven't heard of a variable")
expect_error("divide by zero", 'say 1 divided by 0', "divide by zero")
expect_error("list index out of range", 'set xs to list of 1\nsay item 5 of xs', "no item 5")
expect_error("unknown function", 'call nope with 1', "don't know a function")
expect_error("wrong argument count",
    'define f with a\nreturn a\nend\nsay f with 1 and 2', "expects 1")
expect_error("type error in math", 'say "a" minus 1', "only works with numbers")
expect_error("missing keyword (syntax)", 'if 5 is greater 3 then\nsay "x"\nend', "expected the word 'than'")
expect_error("error reports line number", 'say 1\nsay 2\nsay boom', "line 3")

# ── summary ───────────────────────────────────────────────────────────────────
print(f"\n{PASS} passed, {FAIL} failed")
import sys
sys.exit(1 if FAIL else 0)
