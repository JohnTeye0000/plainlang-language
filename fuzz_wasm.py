"""
Differential fuzzer for the WebAssembly backend.

Generates random programs inside the subset plainwasm.py supports (numbers,
true/false, say with text, if/match/count/repeat/while, stop/skip, functions
including recursion) and checks that the tree-walking interpreter and real
WebAssembly (run under Node) produce identical output -- and fail the same
way when a program hits a runtime error like division by zero.

    python fuzz_wasm.py            # 500 programs
    python fuzz_wasm.py 2000 7     # 2000 programs from seed 7
"""

import random
import re
import sys

import plainlang as pl
import plainwasm as pw


# numbers of 15+ digits are beyond what a double holds exactly
BIG = re.compile(r"\d{15,}")


def lit(n):
    return str(n) if n >= 0 else f"(minus {-n})"


class Generator:
    CMPS = ["is greater than", "is less than", "is at least", "is at most",
            "is equal to", "is not equal to"]

    def __init__(self, rng):
        self.rng = rng
        self.numvars = []           # numeric variables defined so far
        self.ok_defined = False

    def program(self):
        lines = [
            "define double with n\n    return (n multiplied by 2) plus 1\nend",
            "define bigger with a and b\n    if a is greater than b then\n        return a\n    end\n    return b\nend",
            "define fib with n\n    if n is at most 1 then\n        return n\n    end\n"
            "    return (fib with (n minus 1)) plus (fib with (n minus 2))\nend",
            "define positive with n\n    return n is greater than 0\nend",
        ]
        for v in ["a", "b", "c"]:
            lines.append(f"set {v} to {self.num(2)}")
            self.numvars.append(v)
        lines.append(f"set ok to {self.boolean(2)}")
        self.ok_defined = True
        for _ in range(self.rng.randint(5, 12)):
            lines.append(self.statement(0, False))
        return "\n".join(lines)

    # ── statements ──
    def statement(self, depth, in_loop):
        r = self.rng
        kinds = ["say", "say", "sayt", "set", "setbool"]
        if depth < 2:
            kinds += ["if", "count", "repeat", "while", "match"]
        if in_loop:
            kinds += ["stop", "skip"]
        k = r.choice(kinds)
        if k == "say":
            return f"say {self.num(0) if r.random() < 0.7 else self.boolean(0)}"
        if k == "sayt":
            return f'say "{r.choice(["v:", "total ", "x="])}" plus {self.num(0)}'
        if k == "set":
            return f"set {r.choice(self.numvars)} to {self.num(0)}"
        if k == "setbool":
            return f"set ok to {self.boolean(0)}"
        if k == "stop":
            return f"if {self.boolean(1)} then\nstop\nend"
        if k == "skip":
            return f"if {self.boolean(1)} then\nskip\nend"
        if k == "if":
            els = ("\notherwise\n" + self.block(depth + 1, in_loop)) if r.random() < 0.5 else ""
            return f"if {self.boolean(0)} then\n{self.block(depth + 1, in_loop)}{els}\nend"
        if k == "match":
            cases = "\n".join(f"when {r.randint(0, 5)} then\n{self.block(depth + 1, in_loop)}"
                              for _ in range(r.randint(1, 3)))
            els = ("\notherwise\n" + self.block(depth + 1, in_loop)) if r.random() < 0.6 else ""
            return f"match {self.num(0)}\n{cases}{els}\nend"
        if k == "count":
            v = r.choice(["i", "j"])
            return f"count {v} from {lit(r.randint(-2, 3))} to {lit(r.randint(-2, 5))}\n{self.block(depth + 1, True, v)}\nend"
        if k == "repeat":
            return f"repeat {r.randint(0, 4)} times\n{self.block(depth + 1, True)}\nend"
        # while, driven by its own counter so it always terminates
        w = f"w{depth}"
        return (f"set {w} to 0\nwhile {w} is less than {r.randint(0, 4)}\nset {w} to {w} plus 1\n"
                f"{self.block(depth + 1, True)}\nend")

    def block(self, depth, in_loop, loopvar=None):
        saved = list(self.numvars)
        if loopvar:
            self.numvars.append(loopvar)
        out = "\n".join(self.statement(depth, in_loop) for _ in range(self.rng.randint(1, 3)))
        self.numvars = saved
        return out

    # ── expressions ──
    def num(self, d):
        r = self.rng
        if d >= 3 or r.random() < 0.35:
            return r.choice(self.numvars) if self.numvars and r.random() < 0.5 else lit(r.randint(-4, 12))
        e = lambda: self.num(d + 1)
        c = r.choice(["op", "op", "op", "div", "rem", "round", "unary", "minmax",
                      "power", "call", "bigger", "fib", "abs", "sqrt", "neg"])
        if c == "op":     return f"({e()} {r.choice(['plus', 'minus', 'multiplied by'])} {e()})"
        if c == "div":    return f"({e()} divided by {e()})"
        if c == "rem":    return f"(remainder of {e()} and {e()})"
        if c == "round":  return f"(round of {e()})"
        if c == "unary":  return f"({r.choice(['floor', 'ceiling'])} of {e()})"
        if c == "minmax": return f"({r.choice(['min', 'max'])} of {e()} and {e()})"
        if c == "power":  return f"(power of (remainder of (absolute of {e()}) and 7) and {r.randint(0, 3)})"
        if c == "call":   return f"(double with {e()})"
        if c == "bigger": return f"(bigger with {e()} and {e()})"
        if c == "fib":    return f"(fib with (remainder of (absolute of {e()}) and 9))"
        if c == "abs":    return f"(absolute of {e()})"
        if c == "sqrt":   return f"(square root of (absolute of {e()}))"
        return f"(minus {e()})"

    def boolean(self, d):
        r = self.rng
        if d >= 3 or r.random() < 0.3:
            return f"({self.num(d + 1)} {r.choice(self.CMPS)} {self.num(d + 1)})"
        c = r.choice(["cmp", "and", "or", "not", "ok", "positive", "lit"])
        if c == "cmp":      return f"({self.num(d + 1)} {r.choice(self.CMPS)} {self.num(d + 1)})"
        if c == "and":      return f"({self.boolean(d + 1)} and {self.boolean(d + 1)})"
        if c == "or":       return f"({self.boolean(d + 1)} or {self.boolean(d + 1)})"
        if c == "not":      return f"(not {self.boolean(d + 1)})"
        if c == "ok":       return "ok" if self.ok_defined else "true"
        if c == "positive": return f"(positive with {self.num(d + 1)})"
        return r.choice(["true", "false"])


def interp(source):
    out = []
    pl.run_source(source, on_output=out.append)
    error = bool(out) and out[-1].startswith("\n  Oops")
    return (out[:-1] if error else out), error


def compare(programs):
    """Run programs through both engines. Returns the first (source, tree, wasm) mismatch."""
    modules = [pw.compile_wasm(p) for p in programs]
    results = pw.run_wasm_batch(modules)
    for src, res in zip(programs, results):
        tree_out, tree_err = interp(src)
        if any(BIG.search(line) for line in tree_out + res["out"]):
            continue        # past 2**53 the interpreter's exact integers and f64 legitimately differ
        if tree_out != res["out"] or tree_err != (res["error"] is not None):
            return src, (tree_out, tree_err), (res["out"], res["error"])
    return None


def fuzz(n, seed=0, batch=100):
    for start in range(0, n, batch):
        programs = [Generator(random.Random(seed * 1_000_003 + k)).program()
                    for k in range(start, min(n, start + batch))]
        bad = compare(programs)
        if bad:
            return bad
    return None


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    bad = fuzz(n, seed)
    if bad is None:
        print(f"✓ {n} random programs — interpreter and WebAssembly agreed on every one.")
        sys.exit(0)
    src, tree, wasm = bad
    print("✗ MISMATCH\n--- program ---\n" + src)
    print("\n--- interpreter ---", tree)
    print("\n--- webassembly ---", wasm)
    sys.exit(1)
