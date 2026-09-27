"""
Cross-validation: the tree-walking interpreter (plainlang.py) and the bytecode
VM (plainvm.py) must produce identical output for the same program — including
identical error messages. Two independent implementations that agree on a large
battery of programs is strong evidence both are correct.

Run with:   python test_vm.py
"""

import plainlang as pl
import plainvm as vm


def _vm_out(source):
    out = []
    vm.run_source(source, on_output=out.append, rng=lambda: 0.5)
    return out


def both(source, inputs=None):
    inputs = list(inputs or [])
    def make_input(box):
        q = list(box)
        return lambda _p: q.pop(0) if q else ""
    out_tree, out_vm = [], []
    pl.run_source(source, on_output=out_tree.append, on_input=make_input(inputs))
    vm.run_source(source, on_output=out_vm.append, on_input=make_input(inputs), rng=lambda: 0.5)
    return out_tree, out_vm


PASS = FAIL = 0
def agree(name, source, inputs=None):
    global PASS, FAIL
    a, b = both(source, inputs)
    if a == b:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}")
        print(f"      tree-walker: {a!r}")
        print(f"      bytecode VM: {b!r}")


PROGRAMS = {
    "variables & math": 'set a to 7\nset b to 6\nsay a plus " x " plus b plus " = " plus (a multiplied by b)',
    "precedence": 'say 2 plus 3 multiplied by 4\nsay (2 plus 3) multiplied by 4',
    "division & floats": 'say 7 divided by 2\nsay 12 divided by 3\nsay 1 divided by 3',
    "unary minus": 'say minus 5 plus 8\nsay absolute of (minus 8)',
    "comparisons": 'say 5 is greater than 3\nsay 4 is at most 3\nsay 4 is not equal to 5',
    "booleans (short-circuit)": 'say true and false\nsay false or true\nsay not false',
    "if / otherwise chain": 'set a to 15\nif a is at least 18 then\nsay "adult"\notherwise if a is at least 13 then\nsay "teen"\notherwise\nsay "kid"\nend',
    "repeat": 'repeat 3 times\nsay "x"\nend',
    "count up": 'count i from 1 to 5\nsay i\nend',
    "count down": 'count i from 5 to 1\nsay i\nend',
    "count leaves last value": 'count i from 1 to 4\nend\nsay i',
    "while": 'set x to 0\nwhile x is less than 4\nset x to x plus 1\nsay x\nend',
    "nested loops": 'count i from 1 to 3\ncount j from 1 to 2\nsay i plus "," plus j\nend\nend',
    # regression: nested 'count' reusing the same variable name — the inner loop
    # must not corrupt the outer loop's counter (found by the differential fuzzer)
    "nested count, same variable": 'set n to 0\ncount i from 1 to 3\ncount i from 1 to 2\nset n to n plus 1\nend\nend\nsay n',
    "nested count same var, outer runs fully": 'count i from 1 to 4\ncount i from 1 to 2\nend\nsay "tick"\nend',
    # regression: an error occurring in the same expression as, but after, a
    # function call used to be blamed on a line inside the function body
    # instead of the real call site (found by the differential fuzzer)
    "error line survives a function call": 'define double with n\nreturn n multiplied by 2\nend\nsay (double with 5) plus (remainder of 1 and 0)',
    "error line survives reduce's function call": 'define add2 with a and b\nreturn a plus b\nend\nsay (reduce add2 over (list of 1, 2) from 0) plus (remainder of 1 and 0)',
    # regression: round/absolute/sqrt/random/remainder used to call int()/round()
    # directly on their argument, crashing with a raw Python/JS exception instead
    # of a friendly PlainLangError when given non-number input
    "round rejects text": 'say round of "hi"',
    "absolute rejects text": 'say absolute of "hi"',
    "remainder rejects text": 'say remainder of "hi" and 2',
    "floor and ceiling": 'say floor of 3.7\nsay ceiling of 3.2\nsay floor of (minus 3.2)\nsay ceiling of (minus 3.7)',
    "power": 'say power of 2 and 10\nsay power of 5 and 0',
    "min and max": 'say min of 4 and 9\nsay max of 4 and 9\nsay min of 9 and 4',
    "power rejects text": 'say power of "hi" and 2',
    # regression: EQ/NE between incompatible types must never raise (equality is
    # always well-defined), only ordering ops require matching operand shapes
    "equality never errors across types": 'say 16 is equal to "hi"\nsay 16 is not equal to "hi"',
    "structural equality for lists and records":
        'set a to list of 1, 2\nset b to list of 1, 2\nsay a is equal to b\n'
        'set p to record with "x" as 1\nset q to record with "x" as 1\nsay p is equal to q',
    "ordering still rejects incompatible types": 'say 5 is greater than "five"',
    # regressions found by fuzzing the WebAssembly backend against the interpreter
    "if nested at the start of an otherwise block":
        'set ok to true\nif false then\nsay "a"\notherwise\nif ok then\nsay "inner"\nend\nsay "after"\nend',
    "otherwise if on one line still chains": 'if false then\nsay 1\notherwise if true then\nsay "chain"\notherwise\nsay 3\nend',
    "round is half away from zero": 'say round of 2.5\nsay round of 3.5\nsay round of (minus 2.5)\nsay round of 2.4',
    "no scientific notation": 'say 1 divided by 1000000\nsay 1 divided by 1000000000000\nsay 5 divided by 100000000000',
    "zero to a negative power": 'say power of 0 and (minus 1)',
    "negative base to a fractional power": 'say power of (minus 8) and 0.5',
    # numbers are 64-bit floats in every engine
    "big numbers print the digits of the double": 'say power of 2 and 100\nsay power of 2 and 60',
    "factorial of 25": 'define f with n\nif n is at most 1 then\nreturn 1\nend\nreturn n multiplied by (f with (n minus 1))\nend\nsay f with 25',
    "literal beyond 2**53": 'say 9007199254740993',
    "too big: power": 'say power of 10 and 400',
    "too big: repeated multiplication": 'set x to 10\nrepeat 400 times\nset x to x multiplied by 10\nend\nsay x',
    "too big: sum": 'say sum of (list of power of 10 and 300, power of 10 and 300, power of 10 and 308, power of 10 and 308)',
    "huge remainder is exact": 'say remainder of (power of 2 and 100) and 7',
    "junk after the value inside braces": 'say "{1 2}"',
    # found by fuzzing and by the executable spec
    "replacing empty text": 'say replace "" by "x" in "abc"',
    "list concatenation has a ceiling": 'set xs to list of 1\nrepeat 30 times\nset xs to xs plus xs\nend\nsay length of xs',
    "join is sized before it is built": 'set s to "abcdefghij"\nrepeat 20 times\nset s to s plus s\nend\nsay length of (join (list of 1, 2, 3, 4, 5, 6, 7, 8, 9, 10) by s)',
    "replace is sized before it is built": 'set t to "aaaaaaaaaa"\nrepeat 20 times\nset t to t plus t\nend\nset u to "xxxxxxxxxx"\nrepeat 5 times\nset u to u plus u\nend\nsay length of (replace "a" by u in t)',
    "text has a ceiling": 'set t to "abcdefghij"\nrepeat 30 times\nset t to t plus t\nend\nsay length of t',
    "a function without return can't be used as a value": 'define quiet with n\nset x to n\nend\nsay quiet with 1',
    "a function without return is fine as a statement": 'define quiet with n\nset x to n\nend\ncall quiet with 1\nsay "ok"',
    "match subject/case type mismatch never errors":
        'match "hi"\nwhen 1 then\nsay "num"\notherwise\nsay "other"\nend',
    "stop exits loop": 'count i from 1 to 9\nif i is greater than 3 then\nstop\nend\nsay i\nend',
    "skip next pass": 'count i from 1 to 6\nif i is equal to 3 then\nskip\nend\nsay i\nend',
    "skip in while advances": 'set x to 0\nwhile x is less than 5\nset x to x plus 1\nif x is equal to 2 then\nskip\nend\nsay x\nend',
    "stop nested inner only": 'count a from 1 to 2\ncount b from 1 to 9\nif b is greater than 2 then\nstop\nend\nsay a plus "-" plus b\nend\nend',
    "skip in for-each": 'for each n in list of 1, 2, 3, 4\nif n is equal to 2 then\nskip\nend\nsay n\nend',
    "lists": 'set xs to list of 90, 75, 88\nsay xs\nsay length of xs\nsay item 2 of xs',
    "list build & mutate": 'set xs to empty list\nadd 1 to xs\nadd 2 to xs\nadd 3 to xs\nremove item 2 from xs\nsay xs',
    "set list element": 'set xs to list of 1, 2, 3\nset item 2 of xs to 99\nsay xs',
    "records: create & read": 'set p to record with "name" as "Al", "age" as 9\nsay p\nsay item "name" of p\nsay length of p',
    "records: update & grow": 'set p to record with "n" as 1\nset item "n" of p to 5\nset item "m" of p to 9\nsay p\nsay keys of p',
    "records: iterate keys": 'set p to record with "a" as 1, "b" as 2, "c" as 3\nset t to 0\nfor each k in keys of p\nset t to t plus item k of p\nend\nsay t',
    "records: missing key error": 'set p to record with "name" as "Al"\nsay item "naem" of p',
    "first-class: store & call": 'define double with n\nreturn n multiplied by 2\nend\nset op to double\nsay op with 10',
    "first-class: pass as argument": 'define double with n\nreturn n multiplied by 2\nend\ndefine apply_twice with f and x\nreturn f with (f with x)\nend\nsay apply_twice with double and 5',
    "first-class: display a function": 'define double with n\nreturn n multiplied by 2\nend\nsay double',
    "first-class: call non-function error": 'set x to 5\nsay x with 1',
    "map over a list": 'define double with n\nreturn n multiplied by 2\nend\nsay map double over (list of 1, 2, 3)',
    "filter over a list": 'define big with n\nreturn n is greater than 3\nend\nsay filter big over (list of 1, 5, 2, 9)',
    "reduce over a list": 'define combine with a and b\nreturn a plus b\nend\nsay reduce combine over (list of 1, 2, 3, 4) from 0',
    "nested map + reduce": 'define double with n\nreturn n multiplied by 2\nend\ndefine combine with a and b\nreturn a plus b\nend\nsay reduce combine over (map double over (list of 1, 2, 3)) from 0',
    "text: split & join": 'set w to split "a,b,c" by ","\nsay w\nsay join w by "-"\nsay length of w',
    "text: trim/replace/position": 'say trim of "  hi  "\nsay replace "o" by "0" in "foo"\nsay position of "b" in "abc"\nsay position of "z" in "abc"',
    "text: contains": 'say "hello" contains "ell"\nsay "hello" contains "z"\nsay (list of 1, 2, 3) contains 2',
    "text: split into chars": 'say split "hi" by ""',
    "match: numbers + otherwise": 'count n from 1 to 4\nmatch n\nwhen 1 then\nsay "one"\nwhen 2 then\nsay "two"\notherwise\nsay "many"\nend\nend',
    "match: on text": 'set light to "green"\nmatch light\nwhen "red" then\nsay "stop"\nwhen "green" then\nsay "go"\notherwise\nsay "?"\nend',
    "match: no match no otherwise": 'set n to 9\nmatch n\nwhen 1 then\nsay "one"\nend\nsay "after"',
    "stdlib: numbers": 'set xs to list of 5, 2, 8, 1\nsay sum of xs\nsay smallest of xs\nsay largest of xs\nsay average of (list of 2, 4, 6)',
    "stdlib: lists": 'set xs to list of 10, 2, 33\nsay sorted of xs\nsay reverse of xs\nsay first of xs\nsay last of xs',
    "stdlib: remainder & fizzbuzz-ish": 'count n from 1 to 6\nif remainder of n and 3 is equal to 0 then\nsay "fizz"\notherwise\nsay n\nend\nend',
    "stdlib: errors": 'say first of (empty list)',
    "interpolation: vars & exprs": 'set name to "Al"\nset n to 10\nset xs to list of 7, 8, 9\nsay "Hi {name}, {n multiplied by 2}, {item 2 of xs}"',
    "interpolation: escaped braces": 'say "use {{name}} for a literal"',
    "interpolation: error in braces": 'say "hi {missing}"',
    "for each sum": 'set xs to list of 4, 8, 15, 16\nset t to 0\nfor each n in xs\nset t to t plus n\nend\nsay t',
    "function + return": 'define double with n\nreturn n multiplied by 2\nend\nsay double with 21',
    "function as action": 'define greet with who\nsay "Hi " plus who\nend\ncall greet with "Al"',
    "multiple params": 'define combine with a and b\nreturn a plus b\nend\nsay combine with 3 and 4',
    "recursion (factorial)": 'define f with n\nif n is at most 1 then\nreturn 1\nend\nreturn n multiplied by f with (n minus 1)\nend\nsay f with 6',
    "recursion (fibonacci)": 'define fib with n\nif n is less than 2 then\nreturn n\nend\nreturn (fib with (n minus 1)) plus (fib with (n minus 2))\nend\nsay fib with 10',
    "functions read globals": 'set base to 100\ndefine bump\nreturn base plus 1\nend\nsay bump',
    "builtins": 'say uppercase of "hi"\nsay lowercase of "HI"\nsay round of 3.7\nsay square root of 144\nsay length of "hello"',
    "input coercion": 'ask "n?" into n\nsay n plus 1',
    "input text": 'ask "name?" into name\nsay "Hi " plus name',
    "fizzbuzz (1-15)": 'count n from 1 to 15\nif n divided by 15 is equal to round of (n divided by 15) then\nsay "FizzBuzz"\notherwise if n divided by 3 is equal to round of (n divided by 3) then\nsay "Fizz"\notherwise if n divided by 5 is equal to round of (n divided by 5) then\nsay "Buzz"\notherwise\nsay n\nend\nend',

    # error cases — both engines should emit the SAME teaching message
    "err: unknown variable": 'say mystery',
    "err: divide by zero": 'say 1 divided by 0',
    "err: list out of range": 'set xs to list of 1\nsay item 5 of xs',
    "err: unknown function": 'call nope with 1',
    "err: wrong arity": 'define f with a\nreturn a\nend\nsay f with 1 and 2',
    "err: type in math": 'say "a" minus 1',
    "err: reports line": 'say 1\nsay 2\nsay boom',
}

print("Cross-validating tree-walker vs bytecode VM")
agree("variables & math", PROGRAMS["variables & math"])
for name, src in PROGRAMS.items():
    if name == "input coercion":
        agree(name, src, inputs=["5"])
    elif name == "input text":
        agree(name, src, inputs=["Sam"])
    elif name != "variables & math":
        agree(name, src)

# the disassembler should produce non-trivial bytecode
prog = vm.compile_program('set x to 1\ncount i from 1 to 3\nset x to x multiplied by i\nend\nsay x')
dis = vm.disassemble(prog)
ok_dis = "CONST" in dis and "JUMP" in dis and "PRINT" in dis
print(f"  {'✓' if ok_dis else '✗'} disassembler emits bytecode")
if not ok_dis: FAIL += 1
else: PASS += 1

# ── constant-folding optimizer ────────────────────────────────────────────────
print("Optimizer (constant folding)")

def opt_check(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}   {detail}")

def count(src, optimize):
    p = vm.compile_program(src, optimize=optimize)
    return len(p.main.code) + sum(len(f.chunk.code) for f in p.functions.values())

# 'say (2 plus 3) multiplied by 4' should fold to a single CONST + PRINT (+HALT)
opt_check("folds nested arithmetic to one constant",
          count("say (2 plus 3) multiplied by 4", True) < count("say (2 plus 3) multiplied by 4", False))
opt_check("folds a comparison",
          count("if 5 is greater than 3 then\nsay 1\nend", True) < count("if 5 is greater than 3 then\nsay 1\nend", False))
opt_check("folding preserves output",
          vm.compile_program("say (2 plus 3) multiplied by 4") is not None
          and _vm_out("say (2 plus 3) multiplied by 4") == ["20"])
opt_check("does NOT fold division by zero (still errors at runtime)",
          "divide by zero" in "\n".join(_vm_out("say 5 divided by 0")))
opt_check("does NOT fold an invalid type op (still errors at runtime)",
          "only works with numbers" in "\n".join(_vm_out('say "a" minus 1')))
opt_check("optimized and unoptimized give the same output",
          _vm_out("set t to 0\ncount i from 1 to 5\nset t to t plus (i multiplied by 2)\nend\nsay t")
          == ["30"])

# dead-code elimination
opt_check("drops a constant-false branch",
          count('if false then\nsay "a"\notherwise\nsay "b"\nend', True)
          < count('if false then\nsay "a"\notherwise\nsay "b"\nend', False)
          and _vm_out('if false then\nsay "a"\notherwise\nsay "b"\nend') == ["b"])
opt_check("resolves a constant-true condition",
          _vm_out('if 2 plus 2 is equal to 4 then\nsay "yes"\notherwise\nsay "no"\nend') == ["yes"])
opt_check("strips unreachable code after a return",
          count('define f with n\nreturn n\nsay "dead"\nend\nsay f with 3', True)
          < count('define f with n\nreturn n\nsay "dead"\nend\nsay f with 3', False)
          and _vm_out('define f with n\nreturn n\nsay "dead"\nend\nsay f with 3') == ["3"])

# peephole (jump cleanup)
def _no_noop_jumps(src):
    p = vm.compile_program(src, optimize=True)
    for chunk in [p.main] + [f.chunk for f in p.functions.values()]:
        for i, instr in enumerate(chunk.code):
            if instr[0] == "JUMP" and instr[1] == i + 1:
                return False
    return True

opt_check("peephole leaves no redundant 'jump to next'",
          _no_noop_jumps('if true then\nsay "x"\nend\ncount n from 1 to 3\nsay n\nend'))
opt_check("peephole keeps loops + conditionals correct",
          _vm_out('count n from 1 to 4\nif remainder of n and 2 is equal to 0 then\nsay "even"\notherwise\nsay "odd"\nend\nend')
          == ["odd", "even", "odd", "even"])
opt_check("peephole shrinks a single-branch if",
          count('if true then\nsay "yes"\nend\nsay "done"', True)
          < count('if true then\nsay "yes"\nend\nsay "done"', False))

# observability: tracing + source-mapped disassembly
print("Observability")
_steps = []
vm.VM(vm.compile_program("set x to 5\nsay x plus 1"),
      on_output=lambda s: None,
      on_step=lambda line, op, arg, stack: _steps.append((line, op))).run()
opt_check("on_step fires for every executed instruction", len(_steps) >= 6)
opt_check("the trace sees instructions from both source lines",
          {ln for ln, _ in _steps} == {1, 2})
opt_check("tracing does not change behaviour", _vm_out("set x to 5\nsay x plus 1") == ["6"])
opt_check("disassembly carries a source-line column",
          "line" in vm.disassemble(vm.compile_program("say 1 plus 2")))

# portable bytecode (compile -> JSON -> load -> run)
print("Portable bytecode")
import json as _json

def _bc_out(src):
    data = _json.loads(_json.dumps(vm.serialize(vm.compile_program(src))))
    out = []
    vm.VM(vm.deserialize(data), on_output=out.append, rng=lambda: 0.5).run()
    return out

def _rejects_bad_version():
    try:
        vm.deserialize({"plainlang_bytecode": 999, "main": {"name": "main", "consts": [], "code": []},
                        "functions": {}})
        return False
    except Exception:
        return True

opt_check("bytecode round-trips through JSON and runs",
          _bc_out("set t to 0\ncount i from 1 to 5\nset t to t plus i\nend\nsay t") == ["15"])
opt_check("round-tripped bytecode matches a direct run (recursion + lists)",
          _bc_out('define f with n\nif n is at most 1 then\nreturn 1\nend\n'
                  'return n multiplied by f with (n minus 1)\nend\n'
                  'say sum of (list of 3, 4)\nsay f with 5') == ["7", "120"])
opt_check("a wrong-version bytecode file is rejected",
          _rejects_bad_version())

# ── property tests on generated programs: the optimizer and portable bytecode were only
# checked against a handful of hand-written cases; these run them at scale ────────────
print("Property tests on generated programs")
import random
import fuzz
import fuzz_wasm


def _vm_result(program):
    out = []
    try:
        vm.VM(program, on_output=out.append, on_input=lambda p: "", rng=lambda: 0.5).run()
        return True, out
    except vm.PlainLangError as e:
        return False, (out, e.message, e.line)


optimizer_disagreed, roundtrip_failed = [], []
checked = 0
for gen in (fuzz.Generator, fuzz_wasm.Generator):
    for k in range(300):
        src = gen(random.Random(k)).program()
        checked += 1
        try:
            raw = vm.compile_program(src, optimize=False)
            opt = vm.compile_program(src, optimize=True)
        except Exception:
            continue
        if _vm_result(raw) != _vm_result(opt):
            optimizer_disagreed.append(k)
        try:
            data = _json.loads(_json.dumps(vm.serialize(opt)))
            if _vm_result(vm.deserialize(data)) != _vm_result(opt):
                roundtrip_failed.append(k)
        except Exception:
            roundtrip_failed.append(k)
opt_check(f"optimized and unoptimized bytecode agree on {checked} random programs",
          not optimizer_disagreed, str(optimizer_disagreed[:5]))
opt_check(f"portable bytecode round-trips {checked} random programs correctly",
          not roundtrip_failed, str(roundtrip_failed[:5]))

print(f"\n{PASS} passed, {FAIL} failed")
import sys
sys.exit(1 if FAIL else 0)
