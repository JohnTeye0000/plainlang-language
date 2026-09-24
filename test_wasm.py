"""
Tests for plainwasm.py, the WebAssembly backend.

Every program here is run twice -- through the tree-walking interpreter and as
a real .wasm binary executed by Node's WebAssembly engine -- and the output
must match exactly, including the point where a runtime error stops it. Then a
seeded differential fuzz run, and checks that unsupported features are refused
clearly instead of miscompiled.

Skips itself (exit 0) if Node isn't installed.

Run with:   python test_wasm.py
"""

import shutil
import sys

import fuzz_wasm
import plainlang as pl
import plainwasm as pw

if shutil.which("node") is None:
    print("node not found -- skipping WebAssembly tests")
    sys.exit(0)

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def both(source):
    tree_out, tree_err = fuzz_wasm.interp(source)
    out, err = pw.run_wasm(source)
    return (tree_out, tree_err), (out, err is not None)


def agree(name, source):
    a, b = both(source)
    check(name, a == b, f"\n      interpreter: {a}\n      wasm:        {b}")


print("Binary format")
wasm = pw.compile_wasm('say "hi"')
check("starts with the wasm magic number and version 1", wasm[:8] == b"\x00asm\x01\x00\x00\x00", wasm[:8])
check("the module is valid WebAssembly (Node's validator accepts it)",
      pw.run_wasm_batch([wasm])[0]["error"] is None)
check("LEB128 encodes multi-byte values", pw.uleb(624485) == bytes([0xE5, 0x8E, 0x26]))
check("signed LEB128 encodes negatives", pw.sleb(-123456) == bytes([0xC0, 0xBB, 0x78]))

print("Arithmetic and printing")
agree("integer arithmetic and precedence", "say 2 plus 3 multiplied by 4\nsay (2 plus 3) multiplied by 4")
agree("division gives fractions", "say 7 divided by 2\nsay 12 divided by 3\nsay 1 divided by 3")
agree("negative numbers", "say minus 5 plus 8\nsay absolute of (minus 8)")
agree("floor, ceiling, round (banker's)", "say floor of 3.7\nsay ceiling of 3.2\nsay round of 2.5\nsay round of 3.5\nsay round of (minus 2.5)")
agree("floored remainder, incl. negatives", "say remainder of 17 and 5\nsay remainder of (minus 7) and 3\nsay remainder of 7 and (minus 3)")
agree("min, max, power, square root", "say min of 4 and 9\nsay max of 4 and 9\nsay power of 2 and 10\nsay square root of 144")
agree("tiny fractions never print in scientific notation", "say 1 divided by 1000000\nsay 5 divided by 100000000000")
agree("booleans print as true/false", "say 5 is greater than 3\nsay 5 is less than 3\nsay not false")
agree("text built from literals and values", 'set n to 3\nsay "n is " plus n plus "!"\nsay "half: " plus (n divided by 2)')
agree("string interpolation", 'set who to 4\nsay "value {who} and {who plus 1}"')

print("Control flow")
agree("if / otherwise if / otherwise",
      "set a to 15\nif a is at least 18 then\nsay 1\notherwise if a is at least 13 then\nsay 2\notherwise\nsay 3\nend")
agree("an if inside an otherwise block",
      "set ok to true\nif false then\nsay 1\notherwise\nif ok then\nsay 2\nend\nsay 3\nend")
agree("match with fallthrough", "match 3\nwhen 1 then\nsay 10\nwhen 3 then\nsay 30\notherwise\nsay 99\nend")
agree("match otherwise", "match 8\nwhen 1 then\nsay 10\notherwise\nsay 99\nend")
agree("repeat", "set n to 0\nrepeat 4 times\nset n to n plus 2\nend\nsay n")
agree("while", "set x to 0\nwhile x is less than 4\nset x to x plus 1\nsay x\nend")
agree("count up", "count i from 1 to 5\nsay i\nend")
agree("count down", "count i from 5 to 1\nsay i\nend")
agree("count leaves its last value behind", "count i from 1 to 4\nend\nsay i")
agree("nested count reusing a variable", "count i from 1 to 3\ncount i from 1 to 2\nsay i\nend\nend")
agree("stop leaves a loop", "count i from 1 to 9\nif i is greater than 3 then\nstop\nend\nsay i\nend")
agree("skip jumps to the next pass", "count i from 1 to 6\nif i is equal to 3 then\nskip\nend\nsay i\nend")
agree("skip inside while still advances", "set x to 0\nwhile x is less than 5\nset x to x plus 1\nif x is equal to 2 then\nskip\nend\nsay x\nend")
agree("stop only leaves the inner loop",
      "count a from 1 to 2\ncount b from 1 to 9\nif b is greater than 2 then\nstop\nend\nsay a plus b\nend\nend")

print("Functions")
agree("a function call", "define double with n\nreturn n multiplied by 2\nend\nsay double with 21")
agree("recursion (factorial)",
      "define fact with n\nif n is at most 1 then\nreturn 1\nend\nreturn n multiplied by fact with (n minus 1)\nend\nsay fact with 10")
agree("mutual use of two functions",
      "define sq with n\nreturn n multiplied by n\nend\ndefine cube with n\nreturn n multiplied by (sq with n)\nend\nsay cube with 3")
agree("a function returning true/false",
      "define big with n\nreturn n is greater than 3\nend\nsay big with 5\nsay big with 1")
agree("a function that reads and writes a global",
      "set total to 0\ndefine bump with n\nset total to total plus n\nend\ncall bump with 5\ncall bump with 7\nsay total")
agree("parameters shadow globals", "set n to 100\ndefine f with n\nreturn n plus 1\nend\nsay f with 1\nsay n")

print("Runtime errors match the interpreter")
agree("divide by zero stops the program", "say 1\nsay 1 divided by 0\nsay 2")
agree("remainder by zero", "say 5\nsay remainder of 5 and 0")
agree("square root of a negative", "say 1\nsay square root of (minus 4)")
agree("zero to a negative power", "say power of 0 and (minus 1)")
agree("negative base, fractional power", "say power of (minus 8) and 0.5")
agree("too big to hold (power)", "say power of 10 and 400")
agree("too big to hold (repeated multiplication)", "set x to 10\nrepeat 400 times\nset x to x multiplied by 10\nend\nsay x")
agree("big numbers print the digits of the double", "say power of 2 and 100\nsay power of 2 and 60")
agree("huge remainder is exact", "say remainder of (power of 2 and 100) and 7\nsay remainder of (minus (power of 2 and 100)) and 7")
agree("output before an error in a loop is kept", "count i from 1 to 5\nsay 10 divided by (i minus 3)\nend")

print("Unsupported features are refused, not miscompiled")
for name, src in [
    ("lists", "set xs to list of 1, 2, 3\nsay length of xs"),
    ("records", 'set p to record with "a" as 1\nsay p'),
    ("text variables", 'set s to "hi"\nsay s'),
    ("ask", 'ask "n?" into n\nsay n'),
    ("for each", "for each n in list of 1, 2\nsay n\nend"),
    ("comparing text", 'say "a" is equal to "a"'),
]:
    try:
        pw.compile_wasm(src)
        check(f"refuses {name}", False, "compiled without complaint")
    except pw.WasmUnsupported as e:
        check(f"refuses {name}", "WebAssembly" in str(e) or "text" in str(e), str(e))

print("Differential fuzzing (interpreter vs real WebAssembly)")
bad = fuzz_wasm.fuzz(300, seed=1)
check("300 random programs agree (seed 1)", bad is None, bad and bad[0])
bad = fuzz_wasm.fuzz(300, seed=2)
check("300 random programs agree (seed 2)", bad is None, bad and bad[0])

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
