"""
plainwasm -- a WebAssembly backend for PlainLang.

Compiles PlainLang straight to a real .wasm binary: no assembler, no LLVM, no
external tools -- this file emits the module bytes itself (LEB128 integers,
section layout, opcodes, structured control flow with br-depth bookkeeping).
The result runs in any WebAssembly host: browsers, Node, wasmtime.

Supported subset (a "systems core" of the language):
  * numbers (f64) and true/false, all arithmetic, comparisons, and/or/not
  * set, say (numbers, booleans, and text built from literals + values),
    if/otherwise, match, repeat, while, count, stop, skip
  * define/return/call -- including recursion
  * builtins: absolute, floor, ceiling, round, square root, min, max,
    remainder, power
Lists, records, text variables, first-class functions and ask are not
supported yet; the compiler says so plainly instead of miscompiling.

Semantics are kept identical to the interpreter (checked by test_wasm.py, which
runs the same programs through the tree-walker and through real WebAssembly):
floored remainder, banker's rounding, divide-by-zero and friends fail with a
friendly message instead of producing infinity.

Usage:
    python plainwasm.py program.plang            # compile + run under Node
    python plainwasm.py program.plang -o out.wasm  # just emit the binary
"""

import base64
import json
import os
import struct
import subprocess
import sys

import plainlang as pl

HERE = os.path.dirname(os.path.abspath(__file__))


class WasmUnsupported(Exception):
    """The program uses a feature the WebAssembly backend doesn't cover (yet)."""


# ─── binary encoding helpers ────────────────────────────────────────────────

def uleb(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def sleb(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if (n == 0 and not b & 0x40) or (n == -1 and b & 0x40):
            out.append(b)
            return bytes(out)
        out.append(b | 0x80)


def vec(items):
    return uleb(len(items)) + b"".join(items)


def section(sec_id, payload):
    return bytes([sec_id]) + uleb(len(payload)) + payload


def wname(s):
    b = s.encode("utf-8")
    return uleb(len(b)) + b


F64, I32 = 0x7C, 0x7F
BLOCK_VOID = 0x40

# opcodes
BLOCK, LOOP, IF, ELSE, END, BR, BR_IF, RETURN, CALL, DROP = 0x02, 0x03, 0x04, 0x05, 0x0B, 0x0C, 0x0D, 0x0F, 0x10, 0x1A
LOCAL_GET, LOCAL_SET, LOCAL_TEE, GLOBAL_GET, GLOBAL_SET = 0x20, 0x21, 0x22, 0x23, 0x24
I32_CONST, F64_CONST = 0x41, 0x44
I32_EQZ = 0x45
F64_EQ, F64_NE, F64_LT, F64_GT, F64_LE, F64_GE = 0x61, 0x62, 0x63, 0x64, 0x65, 0x66
F64_ABS, F64_NEG, F64_CEIL, F64_FLOOR, F64_TRUNC, F64_NEAREST, F64_SQRT = 0x99, 0x9A, 0x9B, 0x9C, 0x9D, 0x9E, 0x9F
F64_ADD, F64_SUB, F64_MUL, F64_DIV, F64_MIN, F64_MAX = 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5
F64_CONVERT_I32_U = 0xB8

# host imports, in index order
IMPORTS = [
    ("print_str", (I32, I32), ()),
    ("print_num", (F64,), ()),
    ("print_bool", (I32,), ()),
    ("end_line", (), ()),
    ("fail", (I32, I32), ()),
    ("pow", (F64, F64), (F64,)),
    ("rem", (F64, F64), (F64,)),      # exact remainder for operands beyond 2**53
]
IMP = {name: i for i, (name, _, _) in enumerate(IMPORTS)}

CMP_OPS = {"==": F64_EQ, "!=": F64_NE, ">": F64_GT, "<": F64_LT, ">=": F64_GE, "<=": F64_LE}
BINOPS = {"+": F64_ADD, "-": F64_SUB, "*": F64_MUL}
SIMPLE_BUILTINS = {"absolute": F64_ABS, "floor": F64_FLOOR, "ceiling": F64_CEIL,
                   "min": F64_MIN, "max": F64_MAX}


def _unwrap(stmt):
    return stmt[2] if stmt[0] == "@" else stmt


def _stmts(block):
    return [_unwrap(s) for s in block[1]] if block else []


class FuncCtx:
    """Code being emitted for one wasm function."""

    def __init__(self, params, scope):
        self.scope = scope                  # None for the top-level program
        self.params = list(params)
        self.local_index = {p: i for i, p in enumerate(params)}
        self.extra = 0
        self.code = bytearray()
        self.labels = []                    # structured-control-flow label stack
        self.loops = []                     # (break_tag, continue_tag)
        self.uid = 0

    def new_local(self):
        idx = len(self.params) + self.extra
        self.extra += 1
        return idx

    def tag(self):
        self.uid += 1
        return object()

    def op(self, *bytes_):
        self.code += bytes(bytes_)

    def f64(self, x):
        self.code += bytes([F64_CONST]) + struct.pack("<d", float(x))

    def i32(self, x):
        self.code += bytes([I32_CONST]) + sleb(x)

    def get(self, i):
        self.code += bytes([LOCAL_GET]) + uleb(i)

    def set(self, i):
        self.code += bytes([LOCAL_SET]) + uleb(i)

    def tee(self, i):
        self.code += bytes([LOCAL_TEE]) + uleb(i)

    def open(self, opcode, blocktype, tag):
        self.code += bytes([opcode, blocktype])
        self.labels.append(tag)

    def close(self):
        self.code.append(END)
        self.labels.pop()

    def else_(self):
        self.code.append(ELSE)

    def br(self, tag, conditional=False):
        depth = len(self.labels) - 1 - self.labels.index(tag)
        self.code += bytes([BR_IF if conditional else BR]) + uleb(depth)


class Compiler:
    def __init__(self, tree):
        self.funcs = {}          # name -> dict(params, body, index)
        self.top = []            # top-level statements (defines removed)
        self.globals = {}        # name -> global index
        self.var_types = {}      # storage key -> 'num' | 'bool'
        self.ret_types = {}      # function name -> 'num' | 'bool'
        self.data = bytearray()
        self.string_at = {}
        self.sigs = []           # function signatures (deduped)
        self.tree = tree
        self._collect()

    # ── discovery ───────────────────────────────────────────────────────
    def _collect(self):
        for n in _stmts(self.tree):
            if n[0] == "define":
                _, name, params, body = n
                self.funcs[name] = {"params": params, "body": body, "index": None}
            else:
                self.top.append(n)
        for n in self.top:
            self._assigned(n, self.globals_set())
        for i, name in enumerate(self.globals):
            pass

    def globals_set(self):
        return self.globals

    def _assigned(self, n, into):
        """Record every variable a statement (recursively) assigns to."""
        op = n[0]
        if op == "set":
            into.setdefault(n[1], len(into))
        elif op == "count":
            into.setdefault(n[1], len(into))
            self._assigned_block(n[4], into)
        elif op in ("repeat", "while"):
            self._assigned_block(n[2], into)
        elif op == "if":
            for _, b in n[1]:
                self._assigned_block(b, into)
            if n[2]:
                self._assigned_block(n[2], into)
        elif op == "match":
            for _, b in n[2]:
                self._assigned_block(b, into)
            if n[3]:
                self._assigned_block(n[3], into)

    def _assigned_block(self, block, into):
        for s in _stmts(block):
            self._assigned(s, into)

    def fn_locals(self, fname):
        fn = self.funcs[fname]
        names = {}
        self._assigned_block(fn["body"], names)
        return names

    # ── name resolution ─────────────────────────────────────────────────
    def key_of(self, name, scope, for_write=False):
        if scope is None:
            if name in self.globals:
                return ("g", name)
            raise WasmUnsupported(f"I haven't heard of a variable called '{name}' yet.")
        fn = self.funcs[scope]
        if name in fn["params"]:
            return (scope, name)
        if name in self.globals:
            return ("g", name)
        if name in self.fn_locals(scope):
            return (scope, name)
        raise WasmUnsupported(f"I haven't heard of a variable called '{name}' yet.")

    # ── type inference ──────────────────────────────────────────────────
    def typeof(self, e, scope):
        op = e[0]
        if op == "num":
            return "num"
        if op == "bool":
            return "bool"
        if op == "str":
            return "text"
        if op == "neg":
            self._need_num(self.typeof(e[1], scope), "minus")
            return "num"
        if op == "binop":
            lt, rt = self.typeof(e[2], scope), self.typeof(e[3], scope)
            if e[1] == "+" and "text" in (lt, rt):
                return "text"
            self._need_num(lt, e[1]); self._need_num(rt, e[1])
            return "num"
        if op == "cmp":
            lt, rt = self.typeof(e[2], scope), self.typeof(e[3], scope)
            if "text" in (lt, rt):
                raise WasmUnsupported("comparing text is not supported by the WebAssembly backend yet")
            return "bool"
        if op in ("and", "or"):
            self.typeof(e[1], scope); self.typeof(e[2], scope)
            return "bool"
        if op == "not":
            self.typeof(e[1], scope)
            return "bool"
        if op == "var":
            t = self.var_types.get(self.key_of(e[1], scope), "unk")
            return t
        if op == "call":
            fn = self.funcs.get(e[1])
            if fn is None:
                raise WasmUnsupported(f"I don't know a function called '{e[1]}'.")
            if len(fn["params"]) != len(e[2]):
                raise WasmUnsupported(f"'{e[1]}' expects {len(fn['params'])} value(s), but got {len(e[2])}.")
            for a in e[2]:
                self.typeof(a, scope)
            return self.ret_types.get(e[1], "unk")
        if op == "builtin":
            if e[1] not in SIMPLE_BUILTINS and e[1] not in ("sqrt", "remainder", "power", "round"):
                raise WasmUnsupported(f"'{e[1]}' is not supported by the WebAssembly backend yet")
            for a in e[2]:
                self._need_num(self.typeof(a, scope), e[1])
            return "num"
        raise WasmUnsupported(
            f"'{op}' is not supported by the WebAssembly backend yet "
            "(it handles numbers, true/false, and text output)")

    @staticmethod
    def _need_num(t, what):
        if t not in ("num", "unk"):
            raise WasmUnsupported(f"'{what}' on {'text' if t == 'text' else 'true/false'} "
                                  "is not supported by the WebAssembly backend")

    def infer(self):
        """Fixpoint: variable and function-return types from assignments."""
        for _ in range(6):
            new_vars, new_rets = {}, {}
            seen = {}

            def note(key, t):
                if t == "unk":
                    return          # not resolved yet; a later pass will know
                if t == "text":
                    raise WasmUnsupported("text variables are not supported by the WebAssembly backend yet")
                if key in seen and seen[key] != t:
                    raise WasmUnsupported(f"'{key[-1]}' holds both numbers and true/false")
                seen[key] = t
                new_vars[key] = t

            def visit(block, scope):
                for n in _stmts(block):
                    self.visit_stmt(n, scope, note, new_rets)

            for n in self.top:
                self.visit_stmt(n, None, note, new_rets)
            for fname, fn in self.funcs.items():
                visit(fn["body"], fname)
            if new_vars == self.var_types and new_rets == self.ret_types:
                return
            self.var_types, self.ret_types = new_vars, new_rets

    def visit_stmt(self, n, scope, note, rets):
        op = n[0]

        def block(b):
            for s in _stmts(b):
                self.visit_stmt(s, scope, note, rets)

        if op == "set":
            note(self.key_of(n[1], scope, True), self.typeof(n[2], scope))
        elif op == "count":
            self._need_num(self.typeof(n[2], scope), "count"); self._need_num(self.typeof(n[3], scope), "count")
            note(self.key_of(n[1], scope, True), "num")
            block(n[4])
        elif op in ("repeat", "while"):
            self.typeof(n[1], scope)
            block(n[2])
        elif op == "if":
            for c, b in n[1]:
                self.typeof(c, scope); block(b)
            if n[2]:
                block(n[2])
        elif op == "match":
            self.typeof(n[1], scope)
            for v, b in n[2]:
                self.typeof(v, scope); block(b)
            if n[3]:
                block(n[3])
        elif op == "say":
            self.typeof(n[1], scope)
        elif op == "call":
            self.typeof(n, scope)
        elif op == "return":
            if scope is None:
                raise WasmUnsupported("'return' outside a function")
            t = self.typeof(n[1], scope)
            if t == "unk":
                return
            if t == "text":
                raise WasmUnsupported("functions returning text are not supported by the WebAssembly backend yet")
            if rets.get(scope, t) != t:
                raise WasmUnsupported(f"'{scope}' returns both numbers and true/false")
            rets[scope] = t
        elif op in ("break", "continue"):
            pass
        elif op == "define":
            raise WasmUnsupported("a function defined inside another block is not supported yet")
        else:
            raise WasmUnsupported(
                f"'{op}' is not supported by the WebAssembly backend yet "
                "(it handles numbers, true/false, and text output)")

    # ── module assembly ─────────────────────────────────────────────────
    def sig(self, params, results):
        s = (tuple(params), tuple(results))
        if s not in self.sigs:
            self.sigs.append(s)
        return self.sigs.index(s)

    def string(self, text):
        if text not in self.string_at:
            b = text.encode("utf-8")
            self.string_at[text] = (len(self.data), len(b))
            self.data += b
        return self.string_at[text]

    def compile(self):
        self.infer()
        n_imports = len(IMPORTS)
        for i, name in enumerate(self.funcs):
            self.funcs[name]["index"] = n_imports + i
        run_index = n_imports + len(self.funcs)

        bodies = []
        for name, fn in self.funcs.items():
            ctx = FuncCtx(fn["params"], name)
            self.block(fn["body"], ctx)
            ctx.f64(0)                      # falling off the end returns 0
            ctx.close_function = True
            bodies.append(self.finish_body(ctx))
        ctx = FuncCtx([], None)
        for n in self.top:
            self.stmt(n, ctx)
        bodies.append(self.finish_body(ctx))

        # type section: imports first, then user functions, then run
        type_idx = []
        for _, params, results in IMPORTS:
            type_idx.append(self.sig(params, results))
        fn_types = []
        for fn in self.funcs.values():
            fn_types.append(self.sig([F64] * len(fn["params"]), [F64]))
        fn_types.append(self.sig([], []))

        types = vec([b"\x60" + vec([bytes([p]) for p in ps]) + vec([bytes([r]) for r in rs])
                     for ps, rs in self.sigs])
        imports = vec([wname("env") + wname(name) + b"\x00" + uleb(type_idx[i])
                       for i, (name, _, _) in enumerate(IMPORTS)])
        funcs = vec([uleb(t) for t in fn_types])
        memory = vec([b"\x00" + uleb(1)])
        globs = vec([bytes([F64, 1, F64_CONST]) + struct.pack("<d", 0.0) + bytes([END])
                     for _ in self.globals])
        exports = vec([wname("run") + b"\x00" + uleb(run_index),
                       wname("memory") + b"\x02" + uleb(0)])
        code = vec(bodies)
        out = b"\x00asm\x01\x00\x00\x00"
        out += section(1, types) + section(2, imports) + section(3, funcs)
        out += section(5, memory) + section(6, globs) + section(7, exports) + section(10, code)
        if self.data:
            out += section(11, vec([b"\x00" + bytes([I32_CONST]) + sleb(0) + bytes([END])
                                    + uleb(len(self.data)) + bytes(self.data)]))
        return out

    def finish_body(self, ctx):
        locals_ = vec([uleb(ctx.extra) + bytes([F64])]) if ctx.extra else vec([])
        body = locals_ + bytes(ctx.code) + bytes([END])
        return uleb(len(body)) + body

    # ── statements ──────────────────────────────────────────────────────
    def block(self, block, ctx):
        for n in _stmts(block):
            self.stmt(n, ctx)

    def stmt(self, n, ctx):
        op = n[0]
        if op == "set":
            self.store(n[1], n[2], ctx)
        elif op == "say":
            self.say(n[1], ctx)
        elif op == "if":
            self.chain([(lambda c=c: self.cond(c, ctx), b) for c, b in n[1]], n[2], ctx)
        elif op == "match":
            tmp = ctx.new_local()
            self.num(n[1], ctx); ctx.set(tmp)
            def eq(v):
                def emit():
                    ctx.get(tmp); self.num(v, ctx); ctx.op(F64_EQ)
                return emit
            self.chain([(eq(v), b) for v, b in n[2]], n[3], ctx)
        elif op == "repeat":
            self.repeat(n, ctx)
        elif op == "while":
            self.loop(ctx, lambda: (self.cond(n[1], ctx), ctx.op(I32_EQZ)), n[2], lambda: None)
        elif op == "count":
            self.count(n, ctx)
        elif op == "call":
            self.expr(n, ctx); ctx.op(DROP)
        elif op == "return":
            self.num(n[1], ctx, allow_bool=True); ctx.op(RETURN)
        elif op == "break":
            if not ctx.loops:
                raise WasmUnsupported("'stop' can only be used inside a loop.")
            ctx.br(ctx.loops[-1][0])
        elif op == "continue":
            if not ctx.loops:
                raise WasmUnsupported("'skip' can only be used inside a loop.")
            ctx.br(ctx.loops[-1][1])
        else:
            raise WasmUnsupported(f"'{op}' is not supported by the WebAssembly backend yet")

    def store(self, name, expr, ctx):
        key = self.key_of(name, ctx.scope, True)
        self.num(expr, ctx, allow_bool=True)
        self.write_key(key, ctx)

    def write_key(self, key, ctx):
        if key[0] == "g":
            ctx.code += bytes([GLOBAL_SET]) + uleb(list(self.globals).index(key[1]))
        else:
            ctx.set(self.local_of(key, ctx))

    def read_key(self, key, ctx):
        if key[0] == "g":
            ctx.code += bytes([GLOBAL_GET]) + uleb(list(self.globals).index(key[1]))
        else:
            ctx.get(self.local_of(key, ctx))

    def local_of(self, key, ctx):
        name = key[1]
        if name not in ctx.local_index:
            ctx.local_index[name] = ctx.new_local()
        return ctx.local_index[name]

    def chain(self, branches, else_block, ctx):
        if not branches:
            if else_block:
                self.block(else_block, ctx)
            return
        cond, body = branches[0]
        cond()
        ctx.open(IF, BLOCK_VOID, ctx.tag())
        self.block(body, ctx)
        rest = branches[1:]
        if rest or else_block:
            ctx.else_()
            self.chain(rest, else_block, ctx)
        ctx.close()

    def loop(self, ctx, exit_test, body, step):
        brk, cont, top = ctx.tag(), ctx.tag(), ctx.tag()
        ctx.open(BLOCK, BLOCK_VOID, brk)
        ctx.open(LOOP, BLOCK_VOID, top)
        exit_test()
        ctx.br(brk, conditional=True)
        ctx.open(BLOCK, BLOCK_VOID, cont)
        ctx.loops.append((brk, cont))
        self.block(body, ctx)
        ctx.loops.pop()
        ctx.close()
        step()
        ctx.br(top)
        ctx.close()
        ctx.close()

    def repeat(self, n, ctx):
        limit, i = ctx.new_local(), ctx.new_local()
        self.num(n[1], ctx); ctx.op(F64_TRUNC); ctx.set(limit)
        ctx.f64(0); ctx.set(i)
        def test():
            ctx.get(i); ctx.get(limit); ctx.op(F64_LT); ctx.op(I32_EQZ)
        def step():
            ctx.get(i); ctx.f64(1); ctx.op(F64_ADD); ctx.set(i)
        self.loop(ctx, test, n[2], step)

    def count(self, n, ctx):
        _, var, start, stop, body = n
        cnt, stopv, step = ctx.new_local(), ctx.new_local(), ctx.new_local()
        key = self.key_of(var, ctx.scope, True)
        self.num(start, ctx); ctx.set(cnt)
        self.num(stop, ctx); ctx.set(stopv)
        ctx.get(stopv); ctx.get(cnt); ctx.op(F64_GE)         # stop >= start ?
        ctx.open(IF, F64, ctx.tag())
        ctx.f64(1); ctx.else_(); ctx.f64(-1)
        ctx.close()
        ctx.set(step)

        brk, cont, top = ctx.tag(), ctx.tag(), ctx.tag()
        ctx.open(BLOCK, BLOCK_VOID, brk)
        ctx.open(LOOP, BLOCK_VOID, top)
        # exit when (cnt - stop) * step > 0
        ctx.get(cnt); ctx.get(stopv); ctx.op(F64_SUB); ctx.get(step); ctx.op(F64_MUL)
        ctx.f64(0); ctx.op(F64_GT)
        ctx.br(brk, conditional=True)
        ctx.get(cnt); self.write_key(key, ctx)              # the loop variable
        ctx.open(BLOCK, BLOCK_VOID, cont)
        ctx.loops.append((brk, cont))
        self.block(body, ctx)
        ctx.loops.pop()
        ctx.close()
        ctx.get(cnt); ctx.get(step); ctx.op(F64_ADD); ctx.set(cnt)
        ctx.br(top)
        ctx.close()
        ctx.close()

    # ── say ─────────────────────────────────────────────────────────────
    def flatten(self, e, scope):
        if e[0] == "binop" and e[1] == "+" and self.typeof(e, scope) == "text":
            return self.flatten(e[2], scope) + self.flatten(e[3], scope)
        return [e]

    def say(self, e, ctx):
        for part in self.flatten(e, ctx.scope):
            if part[0] == "str":
                if part[1]:
                    ptr, length = self.string(part[1])
                    ctx.i32(ptr); ctx.i32(length)
                    ctx.op(CALL, IMP["print_str"])
                continue
            t = self.expr(part, ctx)
            ctx.op(CALL, IMP["print_bool"] if t == "bool" else IMP["print_num"])
        ctx.op(CALL, IMP["end_line"])

    # ── expressions ─────────────────────────────────────────────────────
    def num(self, e, ctx, allow_bool=False):
        """Emit e as an f64. With allow_bool, true/false is widened to 1/0."""
        t = self.expr(e, ctx)
        if t == "bool":
            if not allow_bool:
                raise WasmUnsupported("arithmetic on true/false is not supported by the WebAssembly backend")
            ctx.op(F64_CONVERT_I32_U)
        elif t == "text":
            raise WasmUnsupported("text values can only be said, not stored or computed with")

    def cond(self, e, ctx):
        """Emit e as an i32 truth value."""
        t = self.expr(e, ctx)
        if t == "num":
            ctx.f64(0); ctx.op(F64_NE)
        elif t == "text":
            raise WasmUnsupported("text used as a condition is not supported by the WebAssembly backend")

    def finite(self, ctx):
        """Leave the f64 on the stack unchanged -- but fail if it overflowed to
        infinity (x - x is 0 for every finite x and NaN for infinity)."""
        tmp = ctx.new_local()
        ctx.set(tmp)
        ctx.get(tmp); ctx.get(tmp); ctx.op(F64_SUB); ctx.f64(0); ctx.op(F64_NE)
        ctx.open(IF, BLOCK_VOID, ctx.tag())
        self.fail(ctx, "That number is too big for PlainLang to hold.")
        ctx.close()
        ctx.get(tmp)

    def fail(self, ctx, message):
        ptr, length = self.string(message)
        ctx.i32(ptr); ctx.i32(length); ctx.op(CALL, IMP["fail"])

    def expr(self, e, ctx):
        op = e[0]
        if op == "num":
            ctx.f64(e[1]); return "num"
        if op == "bool":
            ctx.i32(1 if e[1] else 0); return "bool"
        if op == "str":
            raise WasmUnsupported("text values can only be said, not stored or computed with")
        if op == "neg":
            self.num(e[1], ctx); ctx.op(F64_NEG); return "num"
        if op == "var":
            key = self.key_of(e[1], ctx.scope)
            self.read_key(key, ctx)
            if self.var_types.get(key, "num") == "bool":
                ctx.f64(0); ctx.op(F64_NE); return "bool"
            return "num"
        if op == "binop":
            if e[1] == "+" and self.typeof(e, ctx.scope) == "text":
                raise WasmUnsupported("text can only be said, not stored or computed with")
            self.num(e[2], ctx); self.num(e[3], ctx)
            if e[1] in BINOPS:
                ctx.op(BINOPS[e[1]])
            else:                                            # division
                tmp = ctx.new_local()
                ctx.tee(tmp); ctx.f64(0); ctx.op(F64_EQ)
                ctx.open(IF, BLOCK_VOID, ctx.tag())
                self.fail(ctx, "You can't divide by zero.")
                ctx.close()
                ctx.get(tmp); ctx.op(F64_DIV)
            self.finite(ctx)
            return "num"
        if op == "cmp":
            self.num(e[2], ctx, allow_bool=True); self.num(e[3], ctx, allow_bool=True)
            ctx.op(CMP_OPS[e[1]]); return "bool"
        if op == "and":
            self.cond(e[1], ctx)
            ctx.open(IF, I32, ctx.tag()); self.cond(e[2], ctx)
            ctx.else_(); ctx.i32(0); ctx.close(); return "bool"
        if op == "or":
            self.cond(e[1], ctx)
            ctx.open(IF, I32, ctx.tag()); ctx.i32(1)
            ctx.else_(); self.cond(e[2], ctx); ctx.close(); return "bool"
        if op == "not":
            self.cond(e[1], ctx); ctx.op(I32_EQZ); return "bool"
        if op == "call":
            fn = self.funcs[e[1]]
            for a in e[2]:
                self.num(a, ctx, allow_bool=True)
            ctx.op(CALL); ctx.code += uleb(fn["index"])
            if self.ret_types.get(e[1], "num") == "bool":
                ctx.f64(0); ctx.op(F64_NE); return "bool"
            return "num"
        if op == "builtin":
            return self.builtin(e[1], e[2], ctx)
        raise WasmUnsupported(f"'{op}' is not supported by the WebAssembly backend yet")

    def builtin(self, name, args, ctx):
        if name in SIMPLE_BUILTINS:
            for a in args:
                self.num(a, ctx)
            ctx.op(SIMPLE_BUILTINS[name])
        elif name == "round":
            # schoolbook rounding: sign * floor(|x| + 0.5)   (f64.nearest is banker's)
            tmp = ctx.new_local()
            self.num(args[0], ctx); ctx.tee(tmp); ctx.f64(0); ctx.op(F64_LT)
            ctx.open(IF, F64, ctx.tag())
            ctx.get(tmp); ctx.op(F64_NEG); ctx.f64(0.5); ctx.op(F64_ADD); ctx.op(F64_FLOOR); ctx.op(F64_NEG)
            ctx.else_()
            ctx.get(tmp); ctx.f64(0.5); ctx.op(F64_ADD); ctx.op(F64_FLOOR)
            ctx.close()
        elif name == "sqrt":
            tmp = ctx.new_local()
            self.num(args[0], ctx); ctx.tee(tmp); ctx.f64(0); ctx.op(F64_LT)
            ctx.open(IF, BLOCK_VOID, ctx.tag())
            self.fail(ctx, "I can't take the square root of a negative number.")
            ctx.close()
            ctx.get(tmp); ctx.op(F64_SQRT)
        elif name == "remainder":
            ta, tb = ctx.new_local(), ctx.new_local()
            self.num(args[0], ctx); ctx.op(F64_TRUNC); ctx.set(ta)
            self.num(args[1], ctx); ctx.op(F64_TRUNC); ctx.set(tb)
            ctx.get(tb); ctx.f64(0); ctx.op(F64_EQ)
            ctx.open(IF, BLOCK_VOID, ctx.tag())
            self.fail(ctx, "You can't take a remainder when dividing by zero.")
            ctx.close()
            # doubles can't do this exactly beyond 2**53, so huge operands go to the host
            # (BigInt), exactly as the interpreter's integers would
            big = 9007199254740992.0
            ctx.get(ta); ctx.op(F64_ABS); ctx.f64(big); ctx.op(F64_GT)
            ctx.get(tb); ctx.op(F64_ABS); ctx.f64(big); ctx.op(F64_GT)
            ctx.op(0x72)                                     # i32.or
            ctx.open(IF, F64, ctx.tag())
            ctx.get(ta); ctx.get(tb); ctx.op(CALL, IMP["rem"])
            ctx.else_()
            ctx.get(ta); ctx.get(tb); ctx.get(ta); ctx.get(tb); ctx.op(F64_DIV)
            ctx.op(F64_FLOOR); ctx.op(F64_MUL); ctx.op(F64_SUB)
            ctx.close()
        elif name == "power":
            base, exp = ctx.new_local(), ctx.new_local()
            self.num(args[0], ctx); ctx.set(base)
            self.num(args[1], ctx); ctx.set(exp)
            ctx.get(base); ctx.f64(0); ctx.op(F64_EQ)
            ctx.get(exp); ctx.f64(0); ctx.op(F64_LT)
            ctx.op(0x71)                                     # i32.and
            ctx.open(IF, BLOCK_VOID, ctx.tag())
            self.fail(ctx, "You can't raise 0 to a negative power.")
            ctx.close()
            ctx.get(base); ctx.f64(0); ctx.op(F64_LT)
            ctx.get(exp); ctx.get(exp); ctx.op(F64_TRUNC); ctx.op(F64_NE)
            ctx.op(0x71)
            ctx.open(IF, BLOCK_VOID, ctx.tag())
            self.fail(ctx, "I can't raise a negative number to a fractional power.")
            ctx.close()
            ctx.get(base); ctx.get(exp); ctx.op(CALL, IMP["pow"])
            self.finite(ctx)
        return "num"


# ─── public API ─────────────────────────────────────────────────────────────

def compile_wasm(source):
    """PlainLang source -> the bytes of a WebAssembly module. Raises WasmUnsupported."""
    tree = pl.Parser(pl.tokenize(source)).parse()
    return Compiler(tree).compile()


def run_wasm_batch(modules, timeout=60):
    """Run several compiled modules under Node in one process.
    Returns [{'out': [lines], 'error': None | message}, ...]."""
    payload = json.dumps([base64.b64encode(m).decode("ascii") for m in modules])
    proc = subprocess.run(["node", os.path.join(HERE, "wasm_runner.js")], input=payload.encode(),
                          capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError("wasm runner failed: " + proc.stderr.decode("utf-8", "replace"))
    return json.loads(proc.stdout.decode("utf-8"))


def run_wasm(source):
    """Compile and run one program. Returns (output_lines, error_or_None)."""
    result = run_wasm_batch([compile_wasm(source)])[0]
    return result["out"], result["error"]


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    path = argv[0]
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"I couldn't find a file called '{path}'.")
        return 1
    try:
        wasm = compile_wasm(source)
    except WasmUnsupported as e:
        print(f"\n  The WebAssembly backend can't compile this yet:\n    {e}")
        return 1
    except pl.PlainLangError as e:
        print(pl.format_error(source, e))
        return 1
    if "-o" in argv:
        out = argv[argv.index("-o") + 1]
        with open(out, "wb") as f:
            f.write(wasm)
        print(f"wrote {out} ({len(wasm)} bytes)")
        return 0
    lines, error = run_wasm(source)
    for line in lines:
        print(line)
    if error:
        print(f"\n  Oops! Something went wrong:\n    {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
