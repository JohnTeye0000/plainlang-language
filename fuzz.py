"""
Differential fuzzer for PlainLang.

Generates thousands of random programs and runs each through BOTH backends — the
tree-walking interpreter (plainlang.py) and the bytecode VM (plainvm.py) — then
asserts they produce identical output. Any divergence is a real bug in one of the
engines (or the optimizer). This is how production compilers are stress-tested.

Because the two engines agree even on errors (divide-by-zero, etc.), generated
programs don't need to be error-free — they just need to behave the same in both.

Usage:
    python fuzz.py             # 2000 random programs
    python fuzz.py 20000       # more
    python fuzz.py 500 42      # 500 programs from seed 42 (reproducible)
"""

import random
import sys

import plainlang as pl
import plainvm as vm


class Generator:
    """Emits random numeric PlainLang programs: variables, arithmetic, if, loops."""
    OPS = ["plus", "minus", "multiplied by"]
    CMPS = ["is greater than", "is less than", "is at least", "is at most",
            "is equal to", "is not equal to"]

    def __init__(self, rng):
        self.rng = rng
        self.vars = []

    def program(self):
        lines = []
        for name in ("a", "b", "c"):
            lines.append(f"set {name} to {self.rng.randint(-5, 12)}")
            self.vars.append(name)
        for _ in range(self.rng.randint(3, 8)):
            lines.append(self.statement(0))
        return "\n".join(lines)

    def statement(self, depth):
        kinds = ["say", "say", "set"]
        if depth < 2:
            kinds += ["if", "count"]
        kind = self.rng.choice(kinds)
        if kind == "say":
            return f"say {self.expr(0)}"
        if kind == "set":
            return f"set {self.rng.choice(self.vars)} to {self.expr(0)}"
        if kind == "if":
            body = self.block(depth + 1)
            els = ("\notherwise\n" + self.block(depth + 1)) if self.rng.random() < 0.5 else ""
            return f"if {self.cond(0)} then\n{body}{els}\nend"
        # count loop (bounded so output stays small and it always terminates)
        v = self.rng.choice(["i", "j", "k"])
        lo = self.rng.randint(1, 3)
        hi = lo + self.rng.randint(0, 3)
        self.vars.append(v)
        body = self.block(depth + 1)
        self.vars.pop()
        return f"count {v} from {lo} to {hi}\n{body}\nend"

    def block(self, depth):
        return "\n".join(self.statement(depth) for _ in range(self.rng.randint(1, 3)))

    def expr(self, depth):
        if depth >= 3 or self.rng.random() < 0.45:
            if self.vars and self.rng.random() < 0.6:
                return self.rng.choice(self.vars)
            return str(self.rng.randint(-5, 20))
        op = "divided by" if self.rng.random() < 0.12 else self.rng.choice(self.OPS)
        return f"({self.expr(depth + 1)} {op} {self.expr(depth + 1)})"

    def cond(self, depth):
        c = f"{self.expr(depth + 1)} {self.rng.choice(self.CMPS)} {self.expr(depth + 1)}"
        if self.rng.random() < 0.3:
            joiner = self.rng.choice(["and", "or"])
            c = f"({c}) {joiner} ({self.expr(depth + 1)} {self.rng.choice(self.CMPS)} {self.expr(depth + 1)})"
        return c


def run_both(source):
    tree, vmout = [], []
    pl.run_source(source, on_output=tree.append)
    vm.run_source(source, on_output=vmout.append)
    return tree, vmout


def fuzz(n, seed=0):
    """Run n random programs; return (checked, first_failure_or_None)."""
    for k in range(n):
        rng = random.Random(seed * 1_000_003 + k)
        source = Generator(rng).program()
        tree, vmout = run_both(source)
        if tree != vmout:
            return k, (source, tree, vmout)
    return n, None


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    checked, failure = fuzz(n, seed)
    if failure is None:
        print(f"✓ {checked} random programs — both engines agreed on every one.")
        sys.exit(0)
    source, tree, vmout = failure
    print(f"✗ MISMATCH after {checked} programs. The two engines disagree:\n")
    print("--- program ---"); print(source)
    print("\n--- tree-walker ---"); print("\n".join(tree))
    print("\n--- bytecode VM ---"); print("\n".join(vmout))
    sys.exit(1)
