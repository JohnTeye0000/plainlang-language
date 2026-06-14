"""
PlainVM — a bytecode compiler and stack-based virtual machine for PlainLang.

PlainLang has two independent execution backends:

    1. plainlang.py — a tree-walking interpreter (simple, the reference).
    2. plainvm.py   — this file: a *compiler* that lowers the syntax tree to
       bytecode, and a *virtual machine* that executes it on an operand stack,
       the way real languages (Python, Lua, the JVM) work.

Both are verified to produce identical output on the whole test suite
(see test_vm.py). Having two backends that agree is a strong correctness signal.

Usage:
    python plainvm.py program.plang            # compile, then run on the VM
    python plainvm.py --dis program.plang      # show the compiled bytecode
    python plainvm.py --compare program.plang  # run BOTH engines, check they agree
    python plainvm.py --bench                  # benchmark VM vs tree-walker
"""

import sys
import time

import plainlang as pl
from plainlang import PlainLangError


# ─── Value helpers (kept identical to the tree-walker) ────────────────────────

def to_str(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    if isinstance(v, list):
        return "[" + ", ".join(to_str(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{to_str(k)}: {to_str(val)}" for k, val in v.items()) + "}"
    if v is None:
        return "nothing"
    return str(v)


def truthy(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, (str, list, dict)):
        return len(v) > 0
    return v is not None


def type_name(v):
    if isinstance(v, bool):           return "true/false"
    if isinstance(v, (int, float)):   return "a number"
    if isinstance(v, str):            return "some text"
    if isinstance(v, list):           return "a list"
    if isinstance(v, dict):           return "a record"
    return "nothing"


# ─── Bytecode chunk ───────────────────────────────────────────────────────────
# A chunk is a flat list of instructions [op, arg, line] plus a pool of
# constants referenced by index.

class Chunk:
    def __init__(self, name):
        self.name = name
        self.code = []      # list of [op, arg, line]
        self.consts = []    # constant pool

    def add_const(self, value):
        self.consts.append(value)
        return len(self.consts) - 1


class Function:
    def __init__(self, name, params, chunk):
        self.name = name
        self.params = params
        self.chunk = chunk


class Program:
    def __init__(self, main, functions):
        self.main = main              # Chunk
        self.functions = functions    # {name: Function}


# ─── Compiler: AST → bytecode ─────────────────────────────────────────────────

class Compiler:
    def __init__(self, name="main"):
        self.chunk = Chunk(name)
        self.line = 0
        self._tmp = 0

    # — emit helpers —
    def emit(self, op, arg=None):
        self.chunk.code.append([op, arg, self.line])
        return len(self.chunk.code) - 1

    def patch(self, idx, target):
        self.chunk.code[idx][1] = target

    def here(self):
        return len(self.chunk.code)

    def const(self, value):
        self.emit("CONST", self.chunk.add_const(value))

    def newtmp(self, prefix):
        # '$' cannot appear in user identifiers, so these never collide
        self._tmp += 1
        return f"${prefix}{self._tmp}"

    # — blocks & statements —
    def block(self, node):
        for stmt in node[1]:
            self.statement(stmt)

    def statement(self, node):
        if node[0] == "@":
            self.line = node[1]
            node = node[2]
        op = node[0]
        method = getattr(self, "s_" + op, None)
        if method is None:
            raise PlainLangError(f"compiler: unknown statement {op!r}", self.line)
        method(node)

    def s_set(self, node):
        self.expr(node[2]); self.emit("STORE", node[1])

    def s_say(self, node):
        self.expr(node[1]); self.emit("PRINT")

    def s_ask(self, node):
        self.expr(node[1]); self.emit("INPUT", node[2])

    def s_return(self, node):
        self.expr(node[1]); self.emit("RETURN")

    def s_call(self, node):
        self.call(node); self.emit("POP")   # statement: discard the result

    def s_add(self, node):
        self.expr(node[1]); self.emit("LIST_ADD", node[2])

    def s_remove(self, node):
        self.expr(node[1]); self.emit("LIST_REMOVE", node[2])

    def s_setindex(self, node):
        _, target, key, value = node
        self.expr(target); self.expr(key); self.expr(value); self.emit("SET_INDEX")

    def s_define(self, node):
        pass   # functions are hoisted & compiled separately

    def s_if(self, node):
        _, branches, else_block = node
        end_jumps = []
        for cond, body in branches:
            self.expr(cond)
            j_next = self.emit("JUMP_IF_FALSE", None)
            self.block(body)
            end_jumps.append(self.emit("JUMP", None))
            self.patch(j_next, self.here())
        if else_block:
            self.block(else_block)
        for j in end_jumps:
            self.patch(j, self.here())

    def s_while(self, node):
        test = self.here()
        self.expr(node[1])
        j_exit = self.emit("JUMP_IF_FALSE", None)
        self.block(node[2])
        self.emit("JUMP", test)
        self.patch(j_exit, self.here())

    def s_repeat(self, node):
        cnt, i = self.newtmp("cnt"), self.newtmp("i")
        self.expr(node[1]); self.emit("STORE", cnt)
        self.const(0); self.emit("STORE", i)
        test = self.here()
        self.emit("LOAD", i); self.emit("LOAD", cnt); self.emit("LT")
        j_exit = self.emit("JUMP_IF_FALSE", None)
        self.block(node[2])
        self.emit("LOAD", i); self.const(1); self.emit("ADD"); self.emit("STORE", i)
        self.emit("JUMP", test)
        self.patch(j_exit, self.here())

    def s_count(self, node):
        # count VAR from START to STOP ... end   (works up OR down)
        # The "in range?" test is  (var - stop) * step <= 0  — a single test
        # that works in both directions. The next value is committed to VAR
        # only when it is still in range, so after the loop VAR holds the last
        # value actually used (matching the tree-walker, not the overshoot).
        _, var, start, stop, body = node
        stop_t, step_t, next_t = self.newtmp("stop"), self.newtmp("step"), self.newtmp("next")

        def in_range_test(value_name):
            self.emit("LOAD", value_name); self.emit("LOAD", stop_t); self.emit("SUB")
            self.emit("LOAD", step_t); self.emit("MUL")
            self.const(0); self.emit("LE")

        self.expr(start); self.emit("STORE", var)
        self.expr(stop);  self.emit("STORE", stop_t)
        # step = (stop >= start) ? 1 : -1     (var still equals start here)
        self.emit("LOAD", stop_t); self.emit("LOAD", var); self.emit("GE")
        j_neg = self.emit("JUMP_IF_FALSE", None)
        self.const(1); self.emit("STORE", step_t)
        j_after = self.emit("JUMP", None)
        self.patch(j_neg, self.here())
        self.const(-1); self.emit("STORE", step_t)
        self.patch(j_after, self.here())

        in_range_test(var)                          # is START itself in range?
        j_end = self.emit("JUMP_IF_FALSE", None)
        body_start = self.here()
        self.block(body)
        self.emit("LOAD", var); self.emit("LOAD", step_t); self.emit("ADD"); self.emit("STORE", next_t)
        in_range_test(next_t)                        # is the NEXT value in range?
        j_exit = self.emit("JUMP_IF_FALSE", None)
        self.emit("LOAD", next_t); self.emit("STORE", var)
        self.emit("JUMP", body_start)
        self.patch(j_exit, self.here())
        self.patch(j_end, self.here())

    def s_foreach(self, node):
        _, var, seq, body = node
        seq_t, idx_t = self.newtmp("seq"), self.newtmp("idx")
        self.expr(seq); self.emit("STORE", seq_t)
        self.const(0); self.emit("STORE", idx_t)
        test = self.here()
        self.emit("LOAD", idx_t); self.emit("LOAD", seq_t); self.emit("BUILTIN", ("length", 1)); self.emit("LT")
        j_exit = self.emit("JUMP_IF_FALSE", None)
        # var = item (idx + 1) of seq
        self.emit("LOAD", seq_t); self.emit("LOAD", idx_t); self.const(1); self.emit("ADD")
        self.emit("GET_ITEM"); self.emit("STORE", var)
        self.block(body)
        self.emit("LOAD", idx_t); self.const(1); self.emit("ADD"); self.emit("STORE", idx_t)
        self.emit("JUMP", test)
        self.patch(j_exit, self.here())

    # — expressions (each leaves exactly one value on the stack) —
    def expr(self, node):
        op = node[0]
        method = getattr(self, "e_" + op, None)
        if method is None:
            raise PlainLangError(f"compiler: unknown expression {op!r}", self.line)
        method(node)

    def e_num(self, node):  self.const(node[1])
    def e_str(self, node):  self.const(node[1])
    def e_bool(self, node): self.emit("TRUE" if node[1] else "FALSE")
    def e_var(self, node):  self.emit("LOAD", node[1])
    def e_neg(self, node):  self.expr(node[1]); self.emit("NEG")

    def e_list(self, node):
        for el in node[1]:
            self.expr(el)
        self.emit("BUILD_LIST", len(node[1]))

    def e_record(self, node):
        for k, v in node[1]:
            self.expr(k); self.expr(v)
        self.emit("BUILD_RECORD", len(node[1]))

    def e_index(self, node):
        self.expr(node[1]); self.expr(node[2]); self.emit("GET_ITEM")

    def e_binop(self, node):
        _, opc, l, r = node
        self.expr(l); self.expr(r)
        self.emit({"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV"}[opc])

    def e_cmp(self, node):
        _, opc, l, r = node
        self.expr(l); self.expr(r)
        self.emit({"==": "EQ", "!=": "NE", ">": "GT", "<": "LT", ">=": "GE", "<=": "LE"}[opc])

    def e_not(self, node):
        self.expr(node[1]); self.emit("NOT")

    def e_and(self, node):
        # short-circuit, boolean result
        self.expr(node[1])
        j_false = self.emit("JUMP_IF_FALSE", None)
        self.expr(node[2])
        j_false2 = self.emit("JUMP_IF_FALSE", None)
        self.emit("TRUE")
        j_end = self.emit("JUMP", None)
        self.patch(j_false, self.here()); self.patch(j_false2, self.here())
        self.emit("FALSE")
        self.patch(j_end, self.here())

    def e_or(self, node):
        self.expr(node[1])
        j_true = self.emit("JUMP_IF_TRUE", None)
        self.expr(node[2])
        j_true2 = self.emit("JUMP_IF_TRUE", None)
        self.emit("FALSE")
        j_end = self.emit("JUMP", None)
        self.patch(j_true, self.here()); self.patch(j_true2, self.here())
        self.emit("TRUE")
        self.patch(j_end, self.here())

    def e_builtin(self, node):
        _, name, args = node
        for a in args:
            self.expr(a)
        self.emit("BUILTIN", (name, len(args)))

    def e_call(self, node):
        self.call(node)

    def call(self, node):
        _, name, args = node
        for a in args:
            self.expr(a)
        self.emit("CALL", (name, len(args)))


def compile_program(source):
    tokens = pl.tokenize(source)
    tree = pl.Parser(tokens).parse()

    # hoist every function definition and compile each into its own chunk
    functions = {}
    def find_defines(block):
        for stmt in block[1]:
            n = stmt[2] if stmt[0] == "@" else stmt
            if n[0] == "define":
                _, fname, params, body = n
                c = Compiler(fname)
                c.block(body)
                c.const(None); c.emit("RETURN")        # implicit "return nothing"
                functions[fname] = Function(fname, params, c.chunk)
                find_defines(body)
            else:
                for key in ("if", "repeat", "while", "count", "foreach"):
                    pass
                # descend into compound statements to find nested defines
                if n[0] == "if":
                    for _, b in n[1]:
                        find_defines(b)
                    if n[2]:
                        find_defines(n[2])
                elif n[0] == "repeat":  find_defines(n[2])
                elif n[0] == "while":   find_defines(n[2])
                elif n[0] == "count":   find_defines(n[4])
                elif n[0] == "foreach": find_defines(n[3])
    find_defines(tree)

    main = Compiler("main")
    main.block(tree)
    main.emit("HALT")

    # Freeze every chunk's instructions to tuples (faster to unpack in the VM
    # loop than lists, and immutable once all jump targets are patched).
    program = Program(main.chunk, functions)
    for chunk in [program.main] + [fn.chunk for fn in functions.values()]:
        chunk.code = [tuple(instr) for instr in chunk.code]
    return program


# ─── Virtual machine ──────────────────────────────────────────────────────────

_MISS = object()   # sentinel for "variable not found" without exceptions


class VM:
    def __init__(self, program, on_output=None, on_input=None, rng=None):
        self.program = program
        self.globals = {}
        self.stack = []
        self.line = 0
        self.on_output = on_output or (lambda s: print(s))
        self.on_input = on_input or (lambda p: input(p))
        import random
        self.rng = rng or random.random
        self.steps = 0

    def run(self):
        # The dispatch loop is deliberately flat and hot-path-first: variable
        # access and arithmetic are inlined (no method calls) and the most
        # common opcodes are tested earliest. The instruction pointer `ip` and
        # the current chunk are kept in locals; calls/returns swap them and
        # save/restore the previous frame via the `frames` list.
        glb = self.globals
        stack = self.stack
        push = stack.append
        pop = stack.pop
        functions = self.program.functions
        MISS = _MISS
        frames = []                 # saved (code, consts, locals, ip) per call
        code = self.program.main.code
        consts = self.program.main.consts
        floc = glb                  # top-level locals ARE the globals
        ip = 0
        steps = 0
        LIMIT = 200_000_000

        while True:
            op, arg, line = code[ip]
            ip += 1
            steps += 1
            if steps > LIMIT:
                raise PlainLangError("Your program ran for too long and was stopped.", line)

            if op == "LOAD":
                v = floc.get(arg, MISS)
                if v is MISS:
                    v = glb.get(arg, MISS)
                    if v is MISS:
                        raise pl.unknown_variable_error(arg, list(floc) + list(glb), line)
                push(v)
            elif op == "CONST":
                push(consts[arg])
            elif op == "STORE":
                if arg in floc: floc[arg] = pop()
                elif arg in glb: glb[arg] = pop()
                else: floc[arg] = pop()
            elif op == "ADD":
                b = pop(); a = pop(); ta = type(a); tb = type(b)
                if (ta is int or ta is float) and (tb is int or tb is float): push(a + b)
                else: self.line = line; push(self.arith("ADD", a, b))
            elif op == "SUB":
                b = pop(); a = pop(); ta = type(a); tb = type(b)
                if (ta is int or ta is float) and (tb is int or tb is float): push(a - b)
                else: self.line = line; push(self.arith("SUB", a, b))
            elif op == "MUL":
                b = pop(); a = pop(); ta = type(a); tb = type(b)
                if (ta is int or ta is float) and (tb is int or tb is float): push(a * b)
                else: self.line = line; push(self.arith("MUL", a, b))
            elif op == "LT":
                b = pop(); a = pop()
                try: push(a < b)
                except TypeError: self.line = line; push(self.compare("LT", a, b))
            elif op == "JUMP_IF_FALSE":
                if not truthy(pop()): ip = arg
            elif op == "JUMP":
                ip = arg
            elif op == "CALL":
                name, argc = arg
                fn = functions.get(name)
                if fn is None:
                    raise pl.unknown_function_error(name, functions.keys(), line)
                if len(fn.params) != argc:
                    raise PlainLangError(f"'{name}' expects {len(fn.params)} value(s), but got {argc}.", line)
                if argc:
                    callargs = stack[-argc:]; del stack[-argc:]
                else:
                    callargs = ()
                frames.append((code, consts, floc, ip))
                code = fn.chunk.code; consts = fn.chunk.consts
                floc = dict(zip(fn.params, callargs)); ip = 0
            elif op == "RETURN":
                ret = pop()
                code, consts, floc, ip = frames.pop()
                push(ret)
            elif op == "EQ":
                b = pop(); a = pop(); push(a == b)
            elif op == "NE":
                b = pop(); a = pop(); push(a != b)
            elif op == "GT":
                b = pop(); a = pop()
                try: push(a > b)
                except TypeError: self.line = line; push(self.compare("GT", a, b))
            elif op == "GE":
                b = pop(); a = pop()
                try: push(a >= b)
                except TypeError: self.line = line; push(self.compare("GE", a, b))
            elif op == "LE":
                b = pop(); a = pop()
                try: push(a <= b)
                except TypeError: self.line = line; push(self.compare("LE", a, b))
            elif op == "DIV":
                b = pop(); a = pop(); self.line = line; push(self.arith("DIV", a, b))
            elif op == "JUMP_IF_TRUE":
                if truthy(pop()): ip = arg
            elif op == "PRINT":
                self.on_output(to_str(pop()))
            elif op == "POP":
                pop()
            elif op == "TRUE":
                push(True)
            elif op == "FALSE":
                push(False)
            elif op == "NEG":
                push(-pop())
            elif op == "NOT":
                push(not truthy(pop()))
            elif op == "BUILD_LIST":
                if arg:
                    items = stack[-arg:]; del stack[-arg:]; push(list(items))
                else:
                    push([])
            elif op == "BUILD_RECORD":
                cnt = arg * 2
                if cnt:
                    vals = stack[-cnt:]; del stack[-cnt:]
                else:
                    vals = ()
                d = {}
                for k in range(0, cnt, 2):
                    d[vals[k]] = vals[k + 1]
                push(d)
            elif op == "SET_INDEX":
                value = pop(); key = pop(); target = pop(); self.line = line
                if isinstance(target, dict):
                    target[key] = value
                elif isinstance(target, list):
                    idx = int(key)
                    if idx < 1 or idx > len(target):
                        raise PlainLangError(
                            f"There is no item {idx} (the list has {len(target)} item(s)).",
                            line, "Lists start counting at item 1.")
                    target[idx - 1] = value
                else:
                    raise PlainLangError("'set item ... of ...' needs a list or a record.", line)
            elif op == "GET_ITEM":
                i = pop(); seq = pop(); self.line = line; push(self.get_item(seq, i))
            elif op == "BUILTIN":
                name, argc = arg
                if argc:
                    bargs = stack[-argc:]; del stack[-argc:]
                else:
                    bargs = ()
                self.line = line; push(self.builtin(name, list(bargs)))
            elif op == "INPUT":
                v = self.coerce_input(self.on_input(to_str(pop()) + " "))
                if arg in floc: floc[arg] = v
                elif arg in glb: glb[arg] = v
                else: floc[arg] = v
            elif op == "LIST_ADD":
                value = pop()
                target = floc.get(arg, MISS)
                if target is MISS: target = glb.get(arg, MISS)
                if target is MISS:
                    raise PlainLangError(f"I haven't heard of a variable called '{arg}' yet.", line)
                if not isinstance(target, list):
                    raise PlainLangError(f"I can only add to a list, but '{arg}' is not a list.", line)
                target.append(value)
            elif op == "LIST_REMOVE":
                idx = int(pop())
                target = floc.get(arg, MISS)
                if target is MISS: target = glb.get(arg, MISS)
                if target is MISS:
                    raise PlainLangError(f"I haven't heard of a variable called '{arg}' yet.", line)
                if not isinstance(target, list):
                    raise PlainLangError(f"I can only remove from a list, but '{arg}' is not a list.", line)
                if idx < 1 or idx > len(target):
                    raise PlainLangError(f"There is no item {idx} in '{arg}' (it has {len(target)} item(s)).", line)
                target.pop(idx - 1)
            elif op == "HALT":
                break
            else:
                raise PlainLangError(f"vm: unknown opcode {op!r}", line)

    # — operations (identical semantics to the tree-walker) —
    def arith(self, op, a, b):
        if op == "ADD":
            if isinstance(a, str) or isinstance(b, str):
                return to_str(a) + to_str(b)
            if isinstance(a, list) and isinstance(b, list):
                return a + b
            self.need_numbers("plus", a, b); return a + b
        if op == "SUB": self.need_numbers("minus", a, b); return a - b
        if op == "MUL": self.need_numbers("multiplied by", a, b); return a * b
        if op == "DIV":
            self.need_numbers("divided by", a, b)
            if b == 0:
                raise PlainLangError("You can't divide by zero.", self.line, "Check the number you're dividing by.")
            r = a / b
            return int(r) if r == int(r) else r

    def need_numbers(self, name, a, b):
        for v in (a, b):
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise PlainLangError(f"'{name}' only works with numbers, but I got {type_name(v)}.", self.line)

    def compare(self, op, a, b):
        try:
            return {"EQ": a == b, "NE": a != b, "GT": a > b,
                    "LT": a < b, "GE": a >= b, "LE": a <= b}[op]
        except TypeError:
            raise PlainLangError(f"I can't compare {type_name(a)} with {type_name(b)}.", self.line)

    def get_item(self, seq, i):
        if isinstance(seq, dict):
            if i not in seq:
                raise PlainLangError(
                    f"There is no key '{to_str(i)}' in that record.", self.line,
                    pl._did_you_mean(to_str(i), [to_str(k) for k in seq])
                    or "Check the spelling of the key.")
            return seq[i]
        if not isinstance(seq, list):
            raise PlainLangError("'item ... of ...' needs a list or a record.", self.line)
        i = int(i)
        if i < 1 or i > len(seq):
            raise PlainLangError(f"There is no item {i} (the list has {len(seq)} item(s)).",
                                 self.line, "Lists start counting at item 1.")
        return seq[i - 1]

    def builtin(self, name, args):
        import math
        if name == "length":
            v = args[0]
            if isinstance(v, (list, str, dict)): return len(v)
            raise PlainLangError("'length of' works on text, a list, or a record.", self.line)
        if name == "keys":
            if isinstance(args[0], dict): return list(args[0].keys())
            raise PlainLangError("'keys of' works on a record.", self.line)
        if name == "uppercase": return to_str(args[0]).upper()
        if name == "lowercase": return to_str(args[0]).lower()
        if name == "round":     return round(args[0])
        if name == "absolute":  return abs(args[0])
        if name == "sqrt":
            if args[0] < 0:
                raise PlainLangError("I can't take the square root of a negative number.", self.line)
            r = math.sqrt(args[0]); return int(r) if r == int(r) else r
        if name == "random":
            lo, hi = int(args[0]), int(args[1])
            lo, hi = min(lo, hi), max(lo, hi)
            return lo + int(self.rng() * (hi - lo + 1))

    def coerce_input(self, raw):
        try:
            return int(raw)
        except ValueError:
            try:
                return float(raw)
            except ValueError:
                return raw


# ─── Disassembler ─────────────────────────────────────────────────────────────

def disassemble(program):
    out = []
    def dis_chunk(chunk, params=None):
        header = f"chunk <{chunk.name}>"
        if params is not None:
            header += f"  params: {', '.join(params) or '(none)'}"
        out.append(header)
        for i, (op, arg, line) in enumerate(chunk.code):
            shown = ""
            if op == "CONST":
                shown = repr(chunk.consts[arg])
            elif op in ("LOAD", "STORE", "LIST_ADD", "LIST_REMOVE", "INPUT"):
                shown = str(arg)
            elif op in ("JUMP", "JUMP_IF_FALSE", "JUMP_IF_TRUE"):
                shown = f"-> {arg}"
            elif op in ("CALL", "BUILTIN"):
                shown = f"{arg[0]} ({arg[1]} arg)"
            elif op == "BUILD_LIST":
                shown = f"{arg} items"
            out.append(f"  {i:>4}  {op:<16} {shown}")
        out.append("")
    dis_chunk(program.main)
    for fn in program.functions.values():
        dis_chunk(fn.chunk, fn.params)
    return "\n".join(out)


# ─── Public entry points ──────────────────────────────────────────────────────

def run_source(source, on_output=print, on_input=input, rng=None):
    """Compile and run on the VM. Returns (ok, error_message)."""
    try:
        program = compile_program(source)
        VM(program, on_output, on_input, rng).run()
        return True, None
    except PlainLangError as e:
        msg = pl.format_error(source, e)
        on_output(msg)
        return False, msg


def _bench():
    prog = (
        "define fib with n\n"
        "    if n is less than 2 then\n"
        "        return n\n"
        "    end\n"
        "    return (fib with (n minus 1)) plus (fib with (n minus 2))\n"
        "end\n"
        "say fib with 27\n"
    )
    sink = lambda s: None
    t0 = time.perf_counter(); pl.run_source(prog, on_output=sink); t1 = time.perf_counter()
    t2 = time.perf_counter(); run_source(prog, on_output=sink); t3 = time.perf_counter()
    tree_ms = (t1 - t0) * 1000
    vm_ms = (t3 - t2) * 1000
    print("Benchmark — fib(27)")
    print(f"  tree-walker : {tree_ms:8.1f} ms")
    print(f"  bytecode VM : {vm_ms:8.1f} ms")
    if vm_ms > 0:
        print(f"  speedup     : {tree_ms / vm_ms:8.2f}x")


def _compare(path):
    with open(path, encoding="utf-8") as f:
        source = f.read()
    a, b = [], []
    pl.run_source(source, on_output=a.append)
    run_source(source, on_output=b.append)
    same = a == b
    print("tree-walker output:"); print("\n".join(a))
    print("\nbytecode VM output:"); print("\n".join(b))
    print("\n" + ("✓ Both engines agree." if same else "✗ MISMATCH between engines!"))
    return same


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
    elif args[0] == "--bench":
        _bench()
    elif args[0] == "--dis":
        with open(args[1], encoding="utf-8") as f:
            print(disassemble(compile_program(f.read())))
    elif args[0] == "--compare":
        sys.exit(0 if _compare(args[1]) else 1)
    else:
        try:
            with open(args[0], encoding="utf-8") as f:
                run_source(f.read())
        except FileNotFoundError:
            print(f"I couldn't find a file called '{args[0]}'.")
