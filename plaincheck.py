"""
PlainCheck — a static analyzer for PlainLang.

A separate semantic-analysis phase that runs over the syntax tree *before* the
program executes and reports problems — several at once, each with the same
caret diagnostics the runtime uses. It catches:

    - undefined variables               (used but never set)
    - a function used without calling it (forgot 'with')
    - unknown functions                 (called but never defined)
    - wrong number of arguments         (call vs definition)
    - unused variables                  (set but never read)        [warning]
    - unreachable code                  (after a 'return')          [warning]

Usage:
    python plaincheck.py program.plang
"""

import sys

import plainlang as pl
from plainlang import PlainLangError, suggest


def _unwrap(stmt):
    return stmt[2] if stmt[0] == "@" else stmt


class Scope:
    def __init__(self, assigned, parent=None):
        self.assigned = assigned     # names known in this scope (flow-insensitive)
        self.parent = parent

    def defines(self, name):
        s = self
        while s:
            if name in s.assigned:
                return True
            s = s.parent
        return False

    def names(self):
        out = set()
        s = self
        while s:
            out |= s.assigned
            s = s.parent
        return {n for n in out if not n.startswith("$")}


class Analyzer:
    def __init__(self, source):
        self.source = source
        self.diags = []
        self.functions = {}      # name -> params
        self.bodies = {}         # name -> body block
        self.reads = set()       # every name read anywhere (for the unused check)
        self.defs = []           # (name, line) for set/ask, for the unused check
        self.loop_depth = 0      # >0 means we're inside a loop (for stop/skip)

    # — diagnostic helpers —
    def add(self, severity, message, line, hint=None, near=None):
        d = PlainLangError(message, line, hint, near=near)
        d.severity = severity
        self.diags.append(d)

    def error(self, *a, **k): self.add("error", *a, **k)
    def warn(self, *a, **k):  self.add("warning", *a, **k)

    # — collection passes —
    def collect_functions(self, block):
        for stmt in block[1]:
            n = _unwrap(stmt)
            op = n[0]
            if op == "define":
                _, name, params, body = n
                self.functions[name] = params
                self.bodies[name] = body
                self.collect_functions(body)
            elif op == "if":
                for _, b in n[1]:
                    self.collect_functions(b)
                if n[2]:
                    self.collect_functions(n[2])
            elif op in ("repeat", "while"):
                self.collect_functions(n[2])
            elif op == "count":
                self.collect_functions(n[4])
            elif op == "foreach":
                self.collect_functions(n[3])

    def collect_assigned(self, block):
        names = set()
        for stmt in block[1]:
            n = _unwrap(stmt)
            op = n[0]
            if op in ("set", "ask"):
                names.add(n[1])
            elif op == "count":
                names.add(n[1]); names |= self.collect_assigned(n[4])
            elif op == "foreach":
                names.add(n[1]); names |= self.collect_assigned(n[3])
            elif op == "if":
                for _, b in n[1]:
                    names |= self.collect_assigned(b)
                if n[2]:
                    names |= self.collect_assigned(n[2])
            elif op in ("repeat", "while"):
                names |= self.collect_assigned(n[2])
        return names

    # — main entry —
    def analyze(self, tree):
        self.collect_functions(tree)
        global_scope = Scope(self.collect_assigned(tree))
        self.walk_block(tree, global_scope)
        for name, params in self.functions.items():
            body = self.bodies[name]
            fscope = Scope(set(params) | self.collect_assigned(body), global_scope)
            self.walk_block(body, fscope)
        # unused: a set/ask name read nowhere in the whole program
        for name, line in self.defs:
            if name not in self.reads:
                self.warn(f"You define '{name}' but never use it.", line, near=name,
                          hint="Remove it, or use it somewhere.")
        self.diags.sort(key=lambda d: (d.line or 0, d.col or 0))
        return self.diags

    # — walking —
    def walk_loop(self, block, scope):
        self.loop_depth += 1
        self.walk_block(block, scope)
        self.loop_depth -= 1

    def walk_block(self, block, scope):
        TERMINATORS = {"return": "return", "break": "stop", "continue": "skip"}
        ended_by = None
        for stmt in block[1]:
            line = stmt[1] if stmt[0] == "@" else None
            n = _unwrap(stmt)
            if ended_by:
                self.warn(f"This line can never run — it comes after '{ended_by}'.", line)
                break
            self.walk_stmt(n, scope, line)
            ended_by = TERMINATORS.get(n[0])

    def walk_stmt(self, n, scope, line):
        op = n[0]
        if op == "set":
            self.walk_expr(n[2], scope, line); self.defs.append((n[1], line))
        elif op == "ask":
            self.walk_expr(n[1], scope, line); self.defs.append((n[2], line))
        elif op == "say":
            self.walk_expr(n[1], scope, line)
        elif op == "return":
            self.walk_expr(n[1], scope, line)
        elif op == "if":
            for cond, body in n[1]:
                self.walk_expr(cond, scope, line); self.walk_block(body, scope)
            if n[2]:
                self.walk_block(n[2], scope)
        elif op == "while":
            self.walk_expr(n[1], scope, line); self.walk_loop(n[2], scope)
        elif op == "repeat":
            self.walk_expr(n[1], scope, line); self.walk_loop(n[2], scope)
        elif op == "count":
            self.walk_expr(n[2], scope, line); self.walk_expr(n[3], scope, line)
            self.walk_loop(n[4], scope)
        elif op == "foreach":
            self.walk_expr(n[2], scope, line); self.walk_loop(n[3], scope)
        elif op == "break":
            if self.loop_depth == 0:
                self.error("'stop' can only be used inside a loop.", line)
        elif op == "continue":
            if self.loop_depth == 0:
                self.error("'skip' can only be used inside a loop.", line)
        elif op == "call":
            self.walk_expr(n, scope, line)
        elif op == "add":
            self.walk_expr(n[1], scope, line); self.use_var(n[2], scope, line)
        elif op == "remove":
            self.walk_expr(n[1], scope, line); self.use_var(n[2], scope, line)
        elif op == "setindex":
            self.walk_expr(n[1], scope, line)   # target (read+mutated)
            self.walk_expr(n[2], scope, line)   # key
            self.walk_expr(n[3], scope, line)   # value
        # 'define' is analyzed in its own scope, not inline

    def walk_expr(self, node, scope, line):
        op = node[0]
        if op == "var":
            self.use_var(node[1], scope, line)
        elif op == "call":
            self.check_call(node, scope, line)
            for a in node[2]:
                self.walk_expr(a, scope, line)
        elif op == "builtin":
            for a in node[2]:
                self.walk_expr(a, scope, line)
        elif op == "index":
            self.walk_expr(node[1], scope, line); self.walk_expr(node[2], scope, line)
        elif op in ("binop", "cmp"):
            self.walk_expr(node[2], scope, line); self.walk_expr(node[3], scope, line)
        elif op in ("and", "or"):
            self.walk_expr(node[1], scope, line); self.walk_expr(node[2], scope, line)
        elif op in ("neg", "not"):
            self.walk_expr(node[1], scope, line)
        elif op == "list":
            for el in node[1]:
                self.walk_expr(el, scope, line)
        elif op == "record":
            for k, v in node[1]:
                self.walk_expr(k, scope, line); self.walk_expr(v, scope, line)
        elif op in ("map", "filter"):
            self.walk_expr(node[1], scope, line); self.walk_expr(node[2], scope, line)
        elif op == "reduce":
            self.walk_expr(node[1], scope, line); self.walk_expr(node[2], scope, line)
            self.walk_expr(node[3], scope, line)
        # num / str / bool: nothing to check

    def use_var(self, name, scope, line):
        self.reads.add(name)
        if scope.defines(name):
            return
        if name in self.functions:
            return   # a function used as a first-class value — legal
        else:
            self.error(f"I haven't heard of a variable called '{name}' yet.", line,
                       hint=pl._did_you_mean(name, scope.names()) or f"Set it first:  set {name} to ...",
                       near=name)

    def check_call(self, node, scope, line):
        name, args = node[1], node[2]
        if name in self.functions:
            need = len(self.functions[name])
            if need != len(args):
                self.error(f"'{name}' expects {need} value(s), but you gave {len(args)}.",
                           line, near=name)
        elif scope.defines(name):
            self.reads.add(name)   # a variable holding a function — arity is dynamic
        else:
            self.error(f"I don't know a function called '{name}'.", line,
                       hint=pl._did_you_mean(name, self.functions.keys())
                            or f"Define it first:  define {name} ... end",
                       near=name)


def render(source, d):
    lines = source.split("\n")
    src = lines[d.line - 1] if d.line and 1 <= d.line <= len(lines) else ""
    col, length = d.col, d.length
    if col is None and d.near and src:
        idx = src.find(d.near)
        if idx >= 0:
            col, length = idx + 1, len(d.near)
    label = getattr(d, "severity", "error")
    num = str(d.line) if d.line else "?"
    out = [f"  {label}  ·  line {d.line}", f"    {d.message}", "", f"    {num} | {src}"]
    if col:
        out.append("    " + " " * (len(num) + 3 + col - 1) + "^" * max(1, length or 1))
    if d.hint:
        out.append(f"    {d.hint}")
    return "\n".join(out)


def check_source(source):
    """Return (diagnostics, rendered_text)."""
    try:
        tokens = pl.tokenize(source)
        tree = pl.Parser(tokens).parse()
    except PlainLangError as e:
        e.severity = "error"
        return [e], render(source, e)
    diags = Analyzer(source).analyze(tree)
    text = "\n\n".join(render(source, d) for d in diags)
    return diags, text


def main(path):
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"I couldn't find a file called '{path}'.")
        return 1
    diags, text = check_source(source)
    errors = sum(1 for d in diags if getattr(d, "severity", "error") == "error")
    warnings = len(diags) - errors
    if not diags:
        print(f"  ✓ No problems found in {path}.")
        return 0
    print(text)
    print(f"\n  {len(diags)} problem(s):  {errors} error(s), {warnings} warning(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python plaincheck.py program.plang")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
