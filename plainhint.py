"""
plainhint -- guess how a PlainLang program will behave, before it runs.

Used by the AetherOS backend (plainaxe.py) to attach a scheduling hint to the
compiled program: `cpu`, `io`, `interactive`, or `none`. The kernel's
hint-aware schedulers use it to decide priority (see the AetherOS repo,
experiments/RESEARCH.md).

The analysis is deliberately simple and explainable -- every hint comes with a
written rationale, so a wrong guess can be traced to the rule that made it:

1. Estimate the WORK a program does: count expression/statement operations,
   multiplying by loop trip counts. Trip counts come from the source when they
   are constant (`repeat 50 times`, `count i from 1 to 1000`); otherwise a
   default guess (UNKNOWN_TRIPS) is used and the rationale says so.
2. Estimate how many times it WAITs (`wait N` blocks without using the CPU).
3. Classify by the work done per wait:
     no waits at all, lots of work            -> cpu
     no waits, little work                    -> none (finishes too fast to matter)
     work per wait <= INTERACTIVE_MAX         -> interactive  (wakes, does a little, sleeps)
     work per wait <= IO_MAX                  -> io           (bursts of work between waits)
     otherwise                                -> cpu          (waits are rare)

The thresholds are in "operations", not time. Measured on AetherOS (QEMU,
-icount shift=3, i.e. 8 ns per instruction): loop-heavy compiled PlainLang runs
about 40 ns per estimated operation (p_io: ~2.1 M estimated ops, 84 ms of CPU),
so INTERACTIVE_MAX = 2k ops is ~0.1 ms of work per wait and IO_MAX = 100k ops is
~4 ms -- comparable to the kernel's 10 ms scheduling quantum. Programs that do
little work around their waits cost more per op (syscall overhead dominates).
The thresholds are knobs of the study, not facts about programs; the
experiments measure what happens when the classifier is wrong.
"""

import plainlang as pl

UNKNOWN_TRIPS = 100        # assumed iterations for loops whose count isn't a constant
CPU_MIN = 50_000           # less total work than this: not worth a hint
INTERACTIVE_MAX = 2_000    # ops per wait
IO_MAX = 100_000           # ops per wait
MAX_CALL_DEPTH = 8         # how far to follow function calls (recursion is cut off)


def _stmts(block):
    return [s[2] if s[0] == "@" else s for s in block[1]] if block else []


def _const(e):
    if e[0] == "num":
        return e[1]
    if e[0] == "neg" and e[1][0] == "num":
        return -e[1][1]
    return None


class Estimator:
    def __init__(self, tree):
        self.funcs = {}
        self.top = []
        for n in _stmts(tree):
            if n[0] == "define":
                self.funcs[n[1]] = n[3]
            else:
                self.top.append(n)
        self.notes = []
        self._fn_cache = {}

    def note(self, msg):
        if msg not in self.notes:
            self.notes.append(msg)

    # (work, waits) of an expression
    def expr(self, e, depth):
        if not isinstance(e, tuple):
            return 0, 0
        op = e[0]
        work, waits = 1, 0
        if op == "call" and len(e) > 2:
            for a in e[2]:
                w, z = self.expr(a, depth)
                work += w; waits += z
            if e[1] in self.funcs:
                w, z = self.function(e[1], depth + 1)
                work += w; waits += z
            return work, waits
        for part in e[1:]:
            if isinstance(part, tuple):
                w, z = self.expr(part, depth)
                work += w; waits += z
            elif isinstance(part, list):
                for p in part:
                    w, z = self.expr(p, depth)
                    work += w; waits += z
        return work, waits

    def function(self, name, depth):
        if depth > MAX_CALL_DEPTH:
            self.note(f"calls nested deeper than {MAX_CALL_DEPTH} (recursion?) were not followed")
            return 0, 0
        key = (name, depth)
        if key not in self._fn_cache:
            self._fn_cache[key] = (0, 0)       # guard against recursion
            self._fn_cache[key] = self.block(self.funcs[name], depth)
        return self._fn_cache[key]

    def block(self, block, depth):
        work = waits = 0
        for s in _stmts(block):
            w, z = self.stmt(s, depth)
            work += w; waits += z
        return work, waits

    def stmt(self, n, depth):
        op = n[0]
        if op == "wait":
            w, _ = self.expr(n[1], depth)
            return w, 1
        if op == "repeat":
            c = _const(n[1])
            trips = int(c) if c is not None else UNKNOWN_TRIPS
            if c is None:
                self.note(f"a 'repeat' count isn't a constant; assumed {UNKNOWN_TRIPS} times")
            w, z = self.block(n[2], depth)
            return 1 + trips * (w + 2), trips * z
        if op == "count":
            a, b = _const(n[2]), _const(n[3])
            if a is not None and b is not None:
                trips = int(abs(b - a)) + 1
            else:
                trips = UNKNOWN_TRIPS
                self.note(f"a 'count' range isn't constant; assumed {UNKNOWN_TRIPS} steps")
            w, z = self.block(n[4], depth)
            return 3 + trips * (w + 3), trips * z
        if op == "while":
            self.note(f"a 'while' loop's length can't be known statically; assumed {UNKNOWN_TRIPS} iterations")
            cw, _ = self.expr(n[1], depth)
            w, z = self.block(n[2], depth)
            return UNKNOWN_TRIPS * (w + cw), UNKNOWN_TRIPS * z
        if op == "if":
            # take the most expensive branch (an upper bound)
            best_w = best_z = 0
            work = 0
            for c, b in n[1]:
                cw, _ = self.expr(c, depth)
                work += cw
                w, z = self.block(b, depth)
                best_w, best_z = max(best_w, w), max(best_z, z)
            if n[2]:
                w, z = self.block(n[2], depth)
                best_w, best_z = max(best_w, w), max(best_z, z)
            return work + best_w, best_z
        if op == "match":
            vw, _ = self.expr(n[1], depth)
            best_w = best_z = 0
            for v, b in n[2]:
                w, z = self.block(b, depth)
                best_w, best_z = max(best_w, w), max(best_z, z)
            if n[3]:
                w, z = self.block(n[3], depth)
                best_w, best_z = max(best_w, w), max(best_z, z)
            return vw + best_w, best_z
        # set, say, call, return, ...: just the expressions inside
        work, waits = 1, 0
        for part in n[1:]:
            if isinstance(part, tuple):
                w, z = self.expr(part, depth)
                work += w; waits += z
        return work, waits


def infer(tree):
    """-> (hint, rationale) for a parsed program."""
    est = Estimator(tree)
    work = waits = 0
    for n in est.top:
        w, z = est.stmt(n, 0)
        work += w; waits += z

    lines = [f"estimated work: ~{work:,} operations; estimated waits: {waits:,}"]
    if waits == 0:
        if work >= CPU_MIN:
            hint = "cpu"
            lines.append(f"never waits and does >= {CPU_MIN:,} operations -> cpu-bound")
        else:
            hint = "none"
            lines.append(f"never waits but does < {CPU_MIN:,} operations -> too short to matter")
    else:
        per = work / waits
        lines.append(f"~{per:,.0f} operations of work per wait")
        if per <= INTERACTIVE_MAX:
            hint = "interactive"
            lines.append(f"<= {INTERACTIVE_MAX:,} per wait: mostly waiting, brief bursts -> interactive")
        elif per <= IO_MAX:
            hint = "io"
            lines.append(f"<= {IO_MAX:,} per wait: bursts of work between waits -> io")
        else:
            hint = "cpu"
            lines.append(f"> {IO_MAX:,} per wait: waits are rare compared to work -> cpu")
    for n in est.notes:
        lines.append("note: " + n)
    return hint, "\n".join(lines)


def infer_source(source):
    import plainaxe
    return infer(plainaxe.parse(source))


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            hint, why = infer_source(f.read())
        print(f"{path}: {hint}\n  " + why.replace("\n", "\n  "))
