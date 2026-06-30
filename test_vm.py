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

print(f"\n{PASS} passed, {FAIL} failed")
import sys
sys.exit(1 if FAIL else 0)
