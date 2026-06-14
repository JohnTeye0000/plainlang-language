"""
Cross-validation: the tree-walking interpreter (plainlang.py) and the bytecode
VM (plainvm.py) must produce identical output for the same program — including
identical error messages. Two independent implementations that agree on a large
battery of programs is strong evidence both are correct.

Run with:   python test_vm.py
"""

import plainlang as pl
import plainvm as vm


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
    "lists": 'set xs to list of 90, 75, 88\nsay xs\nsay length of xs\nsay item 2 of xs',
    "list build & mutate": 'set xs to empty list\nadd 1 to xs\nadd 2 to xs\nadd 3 to xs\nremove item 2 from xs\nsay xs',
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

print(f"\n{PASS} passed, {FAIL} failed")
import sys
sys.exit(1 if FAIL else 0)
