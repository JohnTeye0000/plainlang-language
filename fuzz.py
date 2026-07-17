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
    """Emits random, type-correct PlainLang programs across the whole language:
    numbers, text, lists, booleans, arithmetic, string/list built-ins, if, count,
    match, and calls to a few helper functions (map/filter/reduce included)."""
    NUM_OPS = ["plus", "minus", "multiplied by"]
    CMPS = ["is greater than", "is less than", "is at least", "is at most",
            "is equal to", "is not equal to"]
    WORDS = ["hi", "world", "a,b,c", "", "x y", "Test", "one two three"]

    def __init__(self, rng):
        self.rng = rng
        self.vars = {}          # name -> type ("number" / "text" / "list" / "bool")

    def program(self):
        lines = [
            "define double with n\n    return (n multiplied by 2) plus 1\nend",   # number -> number
            "define add2 with a and b\n    return a plus b\nend",                 # for reduce
            "define big with n\n    return n is greater than 3\nend",             # for filter
        ]
        for name, typ in {"a": "number", "b": "number", "s": "text", "t": "text",
                          "xs": "list", "ys": "list"}.items():
            lines.append(f"set {name} to {self.expr(typ, 3)}")
            self.vars[name] = typ
        for _ in range(self.rng.randint(5, 11)):
            lines.append(self.statement(0))
        return "\n".join(lines)

    def vars_of(self, typ):
        return [n for n, t in self.vars.items() if t == typ]

    # — statements —
    def statement(self, depth):
        r = self.rng
        kinds = ["say", "say", "set"]
        if depth < 2:
            kinds += ["if", "count", "match"]
        kind = r.choice(kinds)
        if kind == "say":
            return f"say {self.expr(r.choice(['number', 'text', 'list', 'bool']), 0)}"
        if kind == "set":
            name = r.choice(list(self.vars))
            return f"set {name} to {self.expr(self.vars[name], 0)}"
        if kind == "if":
            body = self.block(depth + 1)
            els = ("\notherwise\n" + self.block(depth + 1)) if r.random() < 0.5 else ""
            return f"if {self.expr('bool', 0)} then\n{body}{els}\nend"
        if kind == "match":
            subj = self.expr("number", 0)
            cases = "\n".join(f"when {r.randint(1, 5)} then\n{self.block(depth + 1)}"
                              for _ in range(r.randint(1, 3)))
            els = ("\notherwise\n" + self.block(depth + 1)) if r.random() < 0.6 else ""
            return f"match {subj}\n{cases}{els}\nend"
        # count loop (bounded — always terminates, output stays small)
        v = r.choice(["i", "j", "k"])
        lo, hi = r.randint(1, 3), r.randint(1, 3) + r.randint(0, 3)
        prev = self.vars.get(v)
        self.vars[v] = "number"
        body = self.block(depth + 1)
        if prev is None:
            del self.vars[v]
        else:
            self.vars[v] = prev
        return f"count {v} from {lo} to {hi}\n{body}\nend"

    def block(self, depth):
        return "\n".join(self.statement(depth) for _ in range(self.rng.randint(1, 3)))

    # — typed expressions —
    def expr(self, typ, depth):
        r = self.rng
        shallow = depth >= 3 or r.random() < 0.4
        if typ == "number":
            if shallow:
                vs = self.vars_of("number")
                return r.choice(vs) if vs and r.random() < 0.5 else str(r.randint(-5, 20))
            c = r.choice(["op", "op", "length", "sum", "remainder", "round", "first", "call", "reduce"])
            e = lambda t: self.expr(t, depth + 1)
            if c == "op":
                op = "divided by" if r.random() < 0.12 else r.choice(self.NUM_OPS)
                return f"({e('number')} {op} {e('number')})"
            if c == "length":    return f"(length of {e(r.choice(['list', 'text']))})"
            if c == "sum":       return f"(sum of {e('list')})"
            if c == "remainder": return f"(remainder of {e('number')} and {e('number')})"
            if c == "round":     return f"(round of {e('number')})"
            if c == "first":     return f"(first of {e('list')})"
            if c == "call":      return f"(double with {e('number')})"
            if c == "reduce":    return f"(reduce add2 over {e('list')} from {e('number')})"
        if typ == "text":
            if shallow:
                vs = self.vars_of("text")
                return r.choice(vs) if vs and r.random() < 0.5 else '"' + r.choice(self.WORDS) + '"'
            c = r.choice(["concat", "concat", "upper", "trim", "join", "replace"])
            e = lambda t: self.expr(t, depth + 1)
            if c == "concat":
                other = r.choice(["number", "text"])
                return f"({e('text')} plus {e(other)})" if r.random() < 0.5 else f"({e(other)} plus {e('text')})"
            if c == "upper":   return f"(uppercase of {e(r.choice(['text', 'number']))})"
            if c == "trim":    return f"(trim of {e('text')})"
            if c == "join":    return f"(join {e('list')} by {e('text')})"
            if c == "replace": return f"(replace {e('text')} by {e('text')} in {e('text')})"
        if typ == "list":
            if shallow:
                vs = self.vars_of("list")
                if vs and r.random() < 0.5:
                    return r.choice(vs)
                return "list of " + ", ".join(str(r.randint(-3, 12)) for _ in range(r.randint(1, 4)))
            c = r.choice(["sorted", "reverse", "split", "map"])
            e = lambda t: self.expr(t, depth + 1)
            if c == "sorted":  return f"(sorted of {e('list')})"
            if c == "reverse": return f"(reverse of {e('list')})"
            if c == "split":   return f"(split {e('text')} by {e('text')})"
            if c == "map":     return f"(map double over {e('list')})"
        # bool
        if depth >= 3:
            return f"({self.expr('number', depth + 1)} {r.choice(self.CMPS)} {self.expr('number', depth + 1)})"
        e = lambda t: self.expr(t, depth + 1)
        c = r.choice(["numcmp", "numcmp", "textcmp", "contains", "logic", "not"])
        if c == "numcmp":   return f"({e('number')} {r.choice(self.CMPS)} {e('number')})"
        if c == "textcmp":  return f"({e('text')} {r.choice(['is equal to', 'is not equal to'])} {e('text')})"
        if c == "contains": return f"({e('text')} contains {e('text')})"
        if c == "logic":    return f"({e('bool')} {r.choice(['and', 'or'])} {e('bool')})"
        return f"(not {e('bool')})"


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
