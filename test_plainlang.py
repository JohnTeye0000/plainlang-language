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
# floats round to 10 decimals so output is identical to the JavaScript engine
expect_output("non-terminating decimal", 'say 10 divided by 3', ["3.3333333333"])
expect_output("repeating decimal from average", 'say average of (list of 2, 4, 5)', ["3.6666666667"])

# ── string interpolation ────────────────────────────────────────────────────────
print("String interpolation")
expect_output("interpolate a variable", 'set name to "Al"\nsay "Hi {name}!"', ["Hi Al!"])
expect_output("interpolate several", 'set a to 3\nset b to 4\nsay "{a} and {b}"', ["3 and 4"])
expect_output("interpolate an expression", 'set n to 10\nsay "double is {n multiplied by 2}"', ["double is 20"])
expect_output("interpolate a list item", 'set xs to list of 7, 8, 9\nsay "second: {item 2 of xs}"', ["second: 8"])
expect_output("no braces is a plain string", 'say "nothing here"', ["nothing here"])
expect_output("escaped braces", 'say "a {{ and a }}"', ["a { and a }"])
expect_output("text around the value", 'set x to 5\nsay "[{x}]"', ["[5]"])
expect_error("unmatched brace", 'say "oops {name"', "no matching")
expect_error("empty braces", 'say "oops {}"', "empty")
expect_error("undefined var inside braces", 'say "hi {missing}"', "haven't heard of a variable")

# ── cross-engine consistency ────────────────────────────────────────────────────
print("Cross-engine consistency")
expect_error("turtle word reserved as a name", 'set color to 1', "expected a variable name")
expect_error("turtle statement explained at the CLI", 'move forward 100', "web playground")

# ── comparisons & booleans ────────────────────────────────────────────────────
print("Comparisons & booleans")
expect_output("greater than", 'if 5 is greater than 3 then\nsay "y"\nend', ["y"])
expect_output("at least (>=)", 'if 5 is at least 5 then\nsay "y"\nend', ["y"])
expect_output("at most (<=)", 'if 4 is at most 3 then\nsay "n"\notherwise\nsay "y"\nend', ["y"])
expect_output("is not equal", 'if 4 is not equal to 5 then\nsay "y"\nend', ["y"])
# regression: 'is equal to'/'is not equal to' between incompatible types used to
# raise (an accident of the original implementation), but equality is always
# well-defined -- it's simply false across types, like Python's own '=='
expect_output("equality never errors across types",
    'say 16 is equal to "hi"\nsay 16 is not equal to "hi"', ["false", "true"])
expect_output("structural equality for lists and records",
    'set a to list of 1, 2\nset b to list of 1, 2\nsay a is equal to b\n'
    'set p to record with "x" as 1\nset q to record with "x" as 1\nsay p is equal to q',
    ["true", "true"])
# regression: an 'if' on the line AFTER 'otherwise' is an ordinary statement inside
# the else-block, not an 'otherwise if' chain (newlines used to be invisible here)
expect_output("if nested at the start of an otherwise block",
    'set ok to true\nif false then\nsay "a"\notherwise\nif ok then\nsay "inner"\nend\nsay "after"\nend',
    ["inner", "after"])
expect_output("'otherwise if' on one line still chains",
    'if false then\nsay 1\notherwise if true then\nsay "chain"\notherwise\nsay 3\nend', ["chain"])
# regression: rounding is schoolbook (half away from zero) in every engine
expect_output("round is half away from zero",
    'say round of 2.5\nsay round of 3.5\nsay round of (minus 2.5)\nsay round of 2.4', ["3", "4", "-3", "2"])
# regression: numbers never print in scientific notation, and tiny values that
# round to zero print as 0 (not 0.0)
expect_output("no scientific notation",
    'say 1 divided by 1000000\nsay 1 divided by 1000000000000\nsay 5 divided by 100000000000',
    ["0.000001", "0", "0.0000000001"])
# regression: power used to crash (0 ** -1) or produce a complex number
expect_error("zero to a negative power", 'say power of 0 and (minus 1)', "negative power")
expect_error("negative base to a fractional power", 'say power of (minus 8) and 0.5', "fractional power")
# regression: numbers are 64-bit floats in every engine. Beyond 2**53 they print the
# exact digits of the double, and a number too big for a double is a friendly error
# (it used to crash Python's int->str conversion at 4300 digits, or print 'Infinity')
expect_output("big numbers print the digits of the double",
    'say power of 2 and 100\nsay power of 2 and 60', ["1267650600228229401496703205376", "1152921504606846976"])
expect_output("factorial of 25 is a double, not an exact integer",
    'define f with n\nif n is at most 1 then\nreturn 1\nend\nreturn n multiplied by (f with (n minus 1))\nend\nsay f with 25', ["15511210043330986055303168"])
expect_output("a literal beyond 2**53 rounds like a double", 'say 9007199254740993', ["9007199254740992"])
expect_error("too big to hold: power", 'say power of 10 and 400', "too big")
expect_error("too big to hold: repeated multiplication",
    'set x to 10\nrepeat 400 times\nset x to x multiplied by 10\nend\nsay x', "too big")
expect_output("remainder stays exact for huge operands", 'say remainder of (power of 2 and 100) and 7', ["2"])
# regression: {braces} in text must hold exactly one expression (the parsers used to
# silently drop anything after the first one -- found by differential testing the grammar)
expect_error("junk after the value inside braces", 'say "{1 2}"', "after the value")
expect_output("a well-formed interpolation still works", 'say "sum {1 plus 2}!"', ["sum 3!"])
# regression: found by fuzzing -- replacing "" in a loop grew text quadratically until Python
# raised MemoryError; the engines also disagreed about what replacing "" even means
expect_error("replacing empty text", 'say replace "" by "x" in "abc"', "can't be empty")
expect_error("text has a ceiling",
    'set t to "abcdefghij"\nrepeat 30 times\nset t to t plus t\nend\nsay length of t', "too long")
# regression: lists have a ceiling, and join is sized BEFORE it is built (found by the
# Python-vs-JavaScript fuzzer: a huge separator times a long list ran out of memory)
expect_error("list concatenation has a ceiling", 'set xs to list of 1\nrepeat 30 times\nset xs to xs plus xs\nend\nsay length of xs', "too long")
expect_error("join is sized before it is built", 'set s to "abcdefghij"\nrepeat 20 times\nset s to s plus s\nend\nsay length of (join (list of 1, 2, 3, 4, 5, 6, 7, 8, 9, 10) by s)', "too long")
expect_error("replace is sized before it is built", 'set t to "aaaaaaaaaa"\nrepeat 20 times\nset t to t plus t\nend\nset u to "xxxxxxxxxx"\nrepeat 5 times\nset u to u plus u\nend\nsay length of (replace "a" by u in t)', "too long")
expect_output("a normal join still works", 'say join (list of 1, 2, 3) by "-"', ["1-2-3"])
expect_error("a function without return can't be used as a value",
    'define quiet with n\nset x to n\nend\nsay quiet with 1', "didn't 'return'")
expect_error("ordering still rejects incompatible types",
    'say 5 is greater than "five"', "I can't compare")
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

# ── first-class functions ──────────────────────────────────────────────────────
print("First-class functions")
expect_output("store a function in a variable",
    'define double with n\nreturn n multiplied by 2\nend\nset op to double\nsay op with 10', ["20"])
expect_output("pass a function as an argument",
    'define double with n\nreturn n multiplied by 2\nend\n'
    'define apply_twice with f and x\nreturn f with (f with x)\nend\nsay apply_twice with double and 5', ["20"])
expect_output("a function is a value you can display",
    'define double with n\nreturn n multiplied by 2\nend\nsay double', ["function double"])
expect_error("calling a non-function variable",
    'set x to 5\nsay x with 1', "not a function")

# ── map / filter / reduce ──────────────────────────────────────────────────────
print("Map / filter / reduce")
_dbl = 'define double with n\nreturn n multiplied by 2\nend\n'
_big = 'define is_big with n\nreturn n is greater than 3\nend\n'
_sum = 'define combine with a and b\nreturn a plus b\nend\n'
expect_output("map", _dbl + 'say map double over (list of 1, 2, 3)', ["[2, 4, 6]"])
expect_output("filter", _big + 'say filter is_big over (list of 1, 5, 2, 9)', ["[5, 9]"])
expect_output("reduce", _sum + 'say reduce combine over (list of 1, 2, 3, 4) from 0', ["10"])
expect_output("map with a stored function",
    _dbl + 'set f to double\nsay map f over (list of 10, 20)', ["[20, 40]"])
expect_output("nested map + reduce",
    _dbl + _sum + 'say reduce combine over (map double over (list of 1, 2, 3)) from 0', ["12"])
expect_error("map needs a function", 'set x to 5\nsay map x over (list of 1, 2)', "needs a function")

# ── text / string library ──────────────────────────────────────────────────────
print("Text library")
expect_output("split", 'say split "a,b,c" by ","', ["[a, b, c]"])
expect_output("split into characters", 'say split "hi" by ""', ["[h, i]"])
expect_output("join", 'say join (list of "a", "b", "c") by "-"', ["a-b-c"])
expect_output("split then join round-trips",
    'set w to split "the quick fox" by " "\nsay join w by " "', ["the quick fox"])
expect_output("trim", 'say "[" plus trim of "  hi  " plus "]"', ["[hi]"])
expect_output("replace", 'say replace "o" by "0" in "foo boo"', ["f00 b00"])
expect_output("position found", 'say position of "world" in "hello world"', ["7"])
expect_output("position not found", 'say position of "z" in "hello"', ["0"])
expect_output("contains text (true)", 'say "hello" contains "ell"', ["true"])
expect_output("contains text (false)", 'say "hello" contains "xyz"', ["false"])
expect_output("contains list item", 'say (list of 1, 2, 3) contains 2', ["true"])
expect_output("length of text", 'say length of "hello"', ["5"])

# ── pattern matching ───────────────────────────────────────────────────────────
print("Pattern matching")
_m = ('match n\nwhen 1 then\nsay "one"\nwhen 2 then\nsay "two"\notherwise\nsay "many"\nend')
expect_output("match first case", 'set n to 1\n' + _m, ["one"])
expect_output("match middle case", 'set n to 2\n' + _m, ["two"])
expect_output("match otherwise", 'set n to 9\n' + _m, ["many"])
expect_output("match on text",
    'set light to "green"\nmatch light\nwhen "red" then\nsay "stop"\nwhen "green" then\nsay "go"\nend', ["go"])
expect_output("match no case, no otherwise (nothing happens)",
    'set n to 5\nmatch n\nwhen 1 then\nsay "one"\nend\nsay "done"', ["done"])
expect_output("match inside a loop",
    'count n from 1 to 3\nmatch n\nwhen 2 then\nsay "even"\notherwise\nsay "odd"\nend\nend', ["odd", "even", "odd"])

# ── numbers & lists toolbox ────────────────────────────────────────────────────
print("Numbers & lists toolbox")
expect_output("sum of", 'say sum of (list of 5, 2, 8, 1)', ["16"])
expect_output("average of (exact)", 'say average of (list of 2, 4, 6)', ["4"])
expect_output("smallest / largest", 'say smallest of (list of 5, 2, 8)\nsay largest of (list of 5, 2, 8)', ["2", "8"])
expect_output("first / last", 'say first of (list of 5, 2, 8)\nsay last of (list of 5, 2, 8)', ["5", "8"])
expect_output("sorted numbers", 'say sorted of (list of 10, 2, 33, 4)', ["[2, 4, 10, 33]"])
expect_output("sorted text", 'say sorted of (list of "pear", "apple", "fig")', ["[apple, fig, pear]"])
expect_output("reverse a list", 'say reverse of (list of 1, 2, 3)', ["[3, 2, 1]"])
expect_output("reverse text", 'say reverse of "hello"', ["olleh"])
expect_output("remainder", 'say remainder of 17 and 5', ["2"])
expect_output("remainder for divisibility", 'say remainder of 10 and 5', ["0"])
expect_error("sum needs numbers", 'say sum of (list of "a", "b")', "needs a list of numbers")
expect_error("first of empty", 'say first of (empty list)', "empty list")
expect_error("remainder by zero", 'say remainder of 5 and 0', "dividing by zero")

# ── built-in helpers ──────────────────────────────────────────────────────────
print("Built-ins")
expect_output("uppercase", 'say uppercase of "hi"', ["HI"])
expect_output("lowercase", 'say lowercase of "HI"', ["hi"])
expect_output("round", 'say round of 3.7', ["4"])
expect_output("absolute", 'say absolute of (minus 8)', ["8"])
expect_output("square root", 'say square root of 144', ["12"])
expect_output("length of text", 'say length of "hello"', ["5"])
expect_output("floor", 'say floor of 3.7\nsay floor of (minus 3.2)', ["3", "-4"])
expect_output("ceiling", 'say ceiling of 3.2\nsay ceiling of (minus 3.7)', ["4", "-3"])
expect_output("power", 'say power of 2 and 10', ["1024"])
expect_output("min", 'say min of 4 and 9\nsay min of 9 and 4', ["4", "4"])
expect_output("max", 'say max of 4 and 9\nsay max of 9 and 4', ["9", "9"])
expect_error("floor rejects text", 'say floor of "hi"', "only works with numbers")
expect_error("power rejects text", 'say power of "hi" and 2', "only works with numbers")

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
