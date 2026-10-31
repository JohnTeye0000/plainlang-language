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

Three analyses (`infer(tree, analysis=...)`, CLI `--analysis`):

  basic    every `while` loop is assumed to run UNKNOWN_TRIPS times. This is the
           classifier the first scheduling experiments used, kept so their
           compiled programs stay reproducible.
  counted  (default) also tracks constants and recognises COUNTED while loops:
               set x to 0
               while x is less than 10000
                   set x to x plus 1
               end
           gets an exact trip count (10000) instead of a guess. The recognition
           is conservative: it gives up (and says so in the rationale) when the
           loop could escape its counter, i.e. the counter is written more than
           once or inside an `if`, the body can `skip` past the increment, the
           bound is not a known constant, or the step moves away from the
           bound. `stop` is fine (it can only shorten the loop; every estimate
           here is an upper bound). Calls are never evaluated, so a bound
           computed by a function stays "unknown" -- that is the classifier's
           deliberate blind spot, and `p_opaque.plang` in the AetherOS repo
           exercises it.
  safe     counted, but biased to guess HEAVY when unsure: a loop of unknown
           length is assumed to run UNKNOWN_TRIPS_SAFE times, and an `if`
           counts the fewest waits of its branches (an `if` without
           `otherwise` counts none). On 150 generated programs every miss of
           `counted` was too light, which is the harmful direction for a
           scheduler that turns hints into priority (AetherOS RESEARCH.md,
           F17-F18); `safe` trades some accuracy to avoid it.

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
UNKNOWN_TRIPS_SAFE = 10_000  # the same, for the heavy-biased `safe` analysis
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


def const_eval(e, env, tainted=frozenset()):
    """Value of an expression if it is a compile-time constant, else None.
    `env` maps variable -> known constant; `tainted` are variables some function
    may overwrite behind our back (never treated as constant). Calls are never
    evaluated."""
    if not isinstance(e, tuple):
        return None
    op = e[0]
    if op == "num":
        return e[1]
    if op == "neg":
        v = const_eval(e[1], env, tainted)
        return None if v is None else -v
    if op == "var":
        return None if e[1] in tainted else env.get(e[1])
    if op == "binop":
        a, b = const_eval(e[2], env, tainted), const_eval(e[3], env, tainted)
        if a is None or b is None:
            return None
        if e[1] == "+":
            return a + b
        if e[1] == "-":
            return a - b
        if e[1] == "*":
            return a * b
        if e[1] == "/":
            return None if b == 0 else a / b
        return None
    if op == "builtin" and e[1] in ("absolute", "min", "max"):
        vals = [const_eval(a, env, tainted) for a in e[2]]
        if any(v is None for v in vals):
            return None
        return abs(vals[0]) if e[1] == "absolute" else (min(vals) if e[1] == "min" else max(vals))
    return None


def assigned_in(block):
    """Every variable a block (recursively) writes: set targets and count variables."""
    out = set()

    def walk(b):
        for st in _stmts(b):
            op = st[0]
            if op == "set":
                out.add(st[1])
            elif op == "count":
                out.add(st[1])
                walk(st[4])
            elif op in ("repeat", "while"):
                walk(st[2])
            elif op == "if":
                for _, body in st[1]:
                    walk(body)
                if st[2]:
                    walk(st[2])
            elif op == "match":
                for _, body in st[2]:
                    walk(body)
                if st[3]:
                    walk(st[3])
    walk(block)
    return out


def contains_continue(block):
    """Does the block contain a `skip` (outside any nested loop, where it would
    belong to that loop instead)?"""
    for st in _stmts(block):
        op = st[0]
        if op == "continue":
            return True
        if op == "if":
            if any(contains_continue(b) for _, b in st[1]) or (st[2] and contains_continue(st[2])):
                return True
        if op == "match":
            if any(contains_continue(b) for _, b in st[2]) or (st[3] and contains_continue(st[3])):
                return True
    return False


def counted_while_trips(cond, body, env, tainted):
    """Exact trip count of `while v <op> bound` whose body steps `v` by a constant
    exactly once, unconditionally. Returns (trips, None) or (None, why_not)."""
    if cond[0] != "cmp" or cond[1] not in ("<", "<=", ">", ">=") or cond[2][0] != "var":
        return None, "the loop condition isn't a simple `counter <op> bound` comparison"
    v, op = cond[2][1], cond[1]
    if v in tainted or v not in env:
        return None, f"the counter '{v}' has no known starting value"
    bound = const_eval(cond[3], env, tainted)
    if bound is None:
        return None, "the loop bound isn't a known constant"
    if contains_continue(body):
        return None, "the body contains `skip`, which could jump past the counter update"
    writes = [st for st in _stmts(body) if st[0] == "set" and st[1] == v]
    if len(writes) != 1:
        return None, f"the counter '{v}' isn't updated exactly once per pass"
    # the single write must be a TOP-LEVEL statement, and the only write anywhere
    nested = assigned_in(
        ("block", [("@", 0, st) for st in _stmts(body) if st[0] != "set"])
    )
    if v in nested:
        return None, f"the counter '{v}' is also written inside a nested block"
    if bound_vars_written(cond[3], body):
        return None, "the loop bound changes inside the loop"
    w = writes[0][2]
    if not (w[0] == "binop" and w[1] in ("+", "-") and w[2] == ("var", v)):
        return None, f"the counter '{v}' isn't stepped as `{v} plus/minus a constant`"
    c = const_eval(w[3], env, tainted)
    if c is None or c == 0:
        return None, "the step isn't a known non-zero constant"
    step = c if w[1] == "+" else -c
    a = env[v]
    import math
    if op in ("<", "<="):
        if step <= 0:
            return None, "the counter moves away from the bound (the loop would not end)"
        n = math.ceil((bound - a) / step) if op == "<" else math.floor((bound - a) / step) + 1
    else:
        if step >= 0:
            return None, "the counter moves away from the bound (the loop would not end)"
        n = math.ceil((a - bound) / -step) if op == ">" else math.floor((a - bound) / -step) + 1
    return max(0, min(int(n), 10 ** 9)), None


def bound_vars_written(expr, body):
    """Is any variable the bound expression reads written by the body?"""
    written = assigned_in(body)

    def reads(e):
        if not isinstance(e, tuple):
            return set()
        if e[0] == "var":
            return {e[1]}
        out = set()
        for part in e[1:]:
            if isinstance(part, tuple):
                out |= reads(part)
            elif isinstance(part, list):
                for q in part:
                    out |= reads(q)
        return out
    return bool(reads(expr) & written)


class Estimator:
    def __init__(self, tree, analysis="counted"):
        if analysis not in ("basic", "counted", "safe"):
            raise ValueError("analysis must be 'basic', 'counted' or 'safe'")
        self.counted = analysis in ("counted", "safe")
        self.safe = analysis == "safe"
        self.unknown = UNKNOWN_TRIPS_SAFE if self.safe else UNKNOWN_TRIPS
        self.funcs = {}
        self.top = []
        for n in _stmts(tree):
            if n[0] == "define":
                self.funcs[n[1]] = n[3]
            else:
                self.top.append(n)
        self.notes = []
        self._fn_cache = {}
        self.env = {}                      # variable -> known constant (counted analysis)
        # variables any function might overwrite: never trusted as constants
        self.tainted = set()
        for body in self.funcs.values():
            self.tainted |= assigned_in(body)

    def cv(self, e):
        """Constant value of e right now, or None."""
        return const_eval(e, self.env, self.tainted) if self.counted else _const(e)

    def _scoped(self, blocks, fn):
        """Run `fn` with the constant environment weakened for blocks that may
        run any number of times / not at all: anything they write is unknown
        inside them and afterwards."""
        if not self.counted:
            return fn()
        killed = set()
        for b in blocks:
            if b:
                killed |= assigned_in(b)
        saved = dict(self.env)
        self.env = {k: v for k, v in saved.items() if k not in killed}
        try:
            return fn()
        finally:
            self.env = {k: v for k, v in saved.items() if k not in killed}

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
            saved, self.env = self.env, {}     # parameters are unknown inside a function
            try:
                self._fn_cache[key] = self.block(self.funcs[name], depth)
            finally:
                self.env = saved
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
            c = self.cv(n[1])
            trips = int(c) if c is not None else self.unknown
            if c is None:
                self.note(f"a 'repeat' count isn't a constant; assumed {self.unknown} times")
            w, z = self._scoped([n[2]], lambda: self.block(n[2], depth))
            return 1 + trips * (w + 2), trips * z
        if op == "count":
            a, b = self.cv(n[2]), self.cv(n[3])
            if a is not None and b is not None:
                trips = int(abs(b - a)) + 1
            else:
                trips = self.unknown
                self.note(f"a 'count' range isn't constant; assumed {self.unknown} steps")
            if self.counted:
                self.env.pop(n[1], None)
            w, z = self._scoped([n[4]], lambda: self.block(n[4], depth))
            if self.counted:
                self.env.pop(n[1], None)
            return 3 + trips * (w + 3), trips * z
        if op == "while":
            cw, _ = self.expr(n[1], depth)
            trips = None
            if self.counted:
                trips, why = counted_while_trips(n[1], n[2], self.env, self.tainted)
                if trips is not None:
                    self.note(f"a 'while' loop was recognised as counted: {trips:,} iterations")
                else:
                    self.note(f"a 'while' loop's length can't be known statically ({why}); "
                              f"assumed {self.unknown} iterations")
            else:
                self.note(f"a 'while' loop's length can't be known statically; assumed {self.unknown} iterations")
            if trips is None:
                trips = self.unknown
            w, z = self._scoped([n[2]], lambda: self.block(n[2], depth))
            return trips * (w + cw), trips * z
        if op == "if":
            # take the most expensive branch (an upper bound); `safe` counts the
            # FEWEST waits instead, so a gated wait can't make work look light
            best_w = best_z = 0
            work = 0
            bodies = [b for _, b in n[1]] + ([n[2]] if n[2] else [])
            fewest = None if n[2] else 0
            for c, b in n[1]:
                cw, _ = self.expr(c, depth)
                work += cw
            for b in bodies:
                w, z = self._scoped(bodies, lambda b=b: self.block(b, depth))
                best_w, best_z = max(best_w, w), max(best_z, z)
                fewest = z if fewest is None else min(fewest, z)
            if self.safe:
                if fewest < best_z:
                    self.note("an 'if' may skip its wait; counted the fewest waits of its branches")
                return work + best_w, fewest
            return work + best_w, best_z
        if op == "match":
            vw, _ = self.expr(n[1], depth)
            best_w = best_z = 0
            bodies = [b for _, b in n[2]] + ([n[3]] if n[3] else [])
            for b in bodies:
                w, z = self._scoped(bodies, lambda b=b: self.block(b, depth))
                best_w, best_z = max(best_w, w), max(best_z, z)
            return vw + best_w, best_z
        # set, say, call, return, ...: just the expressions inside
        work, waits = 1, 0
        for part in n[1:]:
            if isinstance(part, tuple):
                w, z = self.expr(part, depth)
                work += w; waits += z
        if op == "set" and self.counted:
            v = self.cv(n[2])
            if v is None:
                self.env.pop(n[1], None)
            else:
                self.env[n[1]] = v
        return work, waits


def infer(tree, analysis="counted"):
    """-> (hint, rationale) for a parsed program."""
    est = Estimator(tree, analysis)
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


def infer_source(source, analysis="counted"):
    import plainaxe
    return infer(plainaxe.parse(source), analysis)


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            hint, why = infer_source(f.read())
        print(f"{path}: {hint}\n  " + why.replace("\n", "\n  "))
