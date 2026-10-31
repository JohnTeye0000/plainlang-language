"""
plainaxe -- compile PlainLang to native x86-64 programs for the AetherOS kernel.

AetherOS (github.com/JohnTeye0000/aetheros, a separate from-scratch kernel)
runs user programs in ring 3 from "AXE1" files: plain text holding hex machine
code, plus an optional scheduling hint. This backend emits that machine code
directly -- no assembler, no linker. Every instruction below is hand-encoded
x86-64; numbers are IEEE doubles in SSE2 registers, exactly as in every other
PlainLang engine.

Supported subset: the same "systems core" as the WebAssembly backend (numbers,
true/false, arithmetic, comparisons, and/or/not, set, say, if, match, repeat,
while, count, stop, skip, define/return/call incl. recursion, and the numeric
builtins) -- this backend reuses plainwasm's front end (name resolution and type
inference), so the two refuse exactly the same programs, with the same reasons.

Plus one statement no other command-line engine runs:

    wait N        pause for N seconds (SPEC.md defines it; until now only the
                  browser playground executed it). On AetherOS it becomes the
                  kernel's sleep system call: the process blocks and uses no
                  CPU, which is precisely what makes it interesting to a
                  scheduler.

Known differences from the interpreter (stated, tested, and refused loudly
rather than silently wrong):
  * `power` with a fractional exponent stops with an error (integer exponents
    work, via exact repeated squaring).
  * `remainder` of operands beyond 2**53 stops with an error (the interpreter
    switches to exact big integers there; this backend has no bignums).
  * text output is ASCII; other characters print as '.' (the kernel's console
    is ASCII-only).

Usage:
    python plainaxe.py program.plang -o program.axe [--hint auto|cpu|io|interactive|none]
                                                    [--analysis counted|basic|safe]
    python plainaxe.py program.plang --explain      # show the inferred hint and why
"""

import struct
import sys

import plainlang as pl
import plainwasm as pw

ERROR_PREFIX = "!!PLAINLANG-ERROR: "    # how a compiled program reports a runtime error


class AxeUnsupported(Exception):
    """The program uses a feature this backend doesn't cover (yet)."""


# ─── the x86-64 encoder ─────────────────────────────────────────────────────

CC = {"e": 0x4, "ne": 0x5, "b": 0x2, "ae": 0x3, "be": 0x6, "a": 0x7,
      "l": 0xC, "le": 0xE, "g": 0xF, "s": 0x8, "ns": 0x9}

# syscall numbers (see aetheros-kernel/src/usermode.rs)
SYS_EXIT, SYS_WRITE, SYS_SLEEP, SYS_PRINTNUM = 0, 1, 4, 13


def f64_bits(x):
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


class Asm:
    """A byte buffer with labels and rel32 fixups."""

    def __init__(self):
        self.code = bytearray()
        self.labels = {}
        self.fixups = []        # (position of the 4-byte field, label)
        self.n = 0

    def new_label(self, hint="L"):
        self.n += 1
        return f"{hint}{self.n}"

    def bind(self, label):
        assert label not in self.labels, label
        self.labels[label] = len(self.code)

    def emit(self, *parts):
        for p in parts:
            if isinstance(p, int):
                self.code.append(p)
            else:
                self.code += p

    def imm32(self, v):
        self.code += struct.pack("<i", v)

    def rel32(self, label):
        self.fixups.append((len(self.code), label))
        self.code += b"\0\0\0\0"

    def patch32(self, pos, v):
        self.code[pos:pos + 4] = struct.pack("<i", v)

    def finish(self):
        for pos, label in self.fixups:
            if label not in self.labels:
                raise AssertionError(f"unbound label {label}")
            self.patch32(pos, self.labels[label] - (pos + 4))
        return bytes(self.code)

    # — control flow —
    def jmp(self, label):  self.emit(0xE9); self.rel32(label)
    def jcc(self, cc, label): self.emit(0x0F, 0x80 | CC[cc]); self.rel32(label)
    def call(self, label): self.emit(0xE8); self.rel32(label)
    def ret(self):         self.emit(0xC3)

    # — integer registers —
    def mov_eax(self, v):  self.emit(0xB8); self.imm32(v)
    def mov_edi(self, v):  self.emit(0xBF); self.imm32(v)
    def mov_esi(self, v):  self.emit(0xBE); self.imm32(v)
    def mov_rax_imm64(self, v): self.emit(0x48, 0xB8, struct.pack("<Q", v & 0xFFFFFFFFFFFFFFFF))
    def syscall80(self):   self.emit(0xCD, 0x80)
    def lea_rdi(self, label): self.emit(0x48, 0x8D, 0x3D); self.rel32(label)

    # — SSE2 —
    def const(self, x, xmm=0):
        """xmm{0,1} = the double x (via rax)."""
        self.mov_rax_imm64(f64_bits(x))
        self.emit(0x66, 0x48, 0x0F, 0x6E, 0xC0 | (xmm << 3))       # movq xmmN, rax

    def push_x0(self):     self.emit(0x48, 0x83, 0xEC, 0x08, 0xF2, 0x0F, 0x11, 0x04, 0x24)
    def pop_x0(self):      self.emit(0xF2, 0x0F, 0x10, 0x04, 0x24, 0x48, 0x83, 0xC4, 0x08)
    def x1_from_x0(self):  self.emit(0xF2, 0x0F, 0x10, 0xC8)       # movsd xmm1, xmm0
    def x0_from_x1(self):  self.emit(0xF2, 0x0F, 0x10, 0xC1)       # movsd xmm0, xmm1
    def sd(self, op):      self.emit(0xF2, 0x0F, op, 0xC1)         # <op>sd xmm0, xmm1
    def zero_x1(self):     self.emit(0x66, 0x0F, 0x57, 0xC9)       # xorpd xmm1, xmm1
    def ucomis(self):      self.emit(0x66, 0x0F, 0x2E, 0xC1)       # ucomisd xmm0, xmm1
    def x0_bit63(self, btx):
        """Flip/clear the sign bit of xmm0 (btx = 0xF8 btc, 0xF0 btr)."""
        self.emit(0x66, 0x48, 0x0F, 0x7E, 0xC0)                    # movq rax, xmm0
        self.emit(0x48, 0x0F, 0xBA, btx, 0x3F)                     # btc/btr rax, 63
        self.emit(0x66, 0x48, 0x0F, 0x6E, 0xC0)                    # movq xmm0, rax

    def setcc_to_x0(self, cc):
        self.emit(0x0F, 0x90 | CC[cc], 0xC0)                       # setcc al
        self.emit(0x0F, 0xB6, 0xC0)                                # movzx eax, al
        self.emit(0xF2, 0x48, 0x0F, 0x2A, 0xC0)                    # cvtsi2sd xmm0, rax

    def load_rbp(self, disp):  self.emit(0xF2, 0x0F, 0x10, 0x85); self.imm32(disp)
    def store_rbp(self, disp): self.emit(0xF2, 0x0F, 0x11, 0x85); self.imm32(disp)
    def load_r15(self, disp):  self.emit(0xF2, 0x41, 0x0F, 0x10, 0x87); self.imm32(disp)
    def store_r15(self, disp): self.emit(0xF2, 0x41, 0x0F, 0x11, 0x87); self.imm32(disp)


# ─── per-function state ─────────────────────────────────────────────────────

class Frame:
    def __init__(self, params, scope):
        self.scope = scope
        self.params = list(params)
        self.slots = {}         # local name -> slot index
        self.n_slots = 0
        self.loops = []         # (break_label, continue_label)

    def temp(self):
        self.n_slots += 1
        return self.n_slots - 1

    def slot_of(self, name):
        if name not in self.slots:
            self.slots[name] = self.temp()
        return self.slots[name]

    def disp_param(self, name):
        i = self.params.index(name)
        return 16 + 8 * (len(self.params) - 1 - i)   # pushed left to right

    @staticmethod
    def disp_slot(k):
        return -8 * (k + 1)


# ─── the compiler ───────────────────────────────────────────────────────────

SIMPLE = {"min": 0x5D, "max": 0x5F}


class Compiler(pw.Compiler):
    """Front end from plainwasm (discovery, name resolution, type inference);
    back end emits x86-64."""

    def visit_stmt(self, n, scope, note, rets):
        if n[0] == "wait":
            self._need_num(self.typeof(n[1], scope), "wait")
            return
        return super().visit_stmt(n, scope, note, rets)

    # — module —
    def compile(self):
        try:
            self.infer()
        except pw.WasmUnsupported as e:
            raise AxeUnsupported(str(e).replace("WebAssembly backend", "AetherOS backend")) from None
        self.a = Asm()
        self.strings = {}
        a = self.a
        n_globals = len(self.globals)

        # entry: globals live in a block at the top of the stack (r15 points at
        # it; the kernel hands every process zeroed stack pages, so they start
        # as 0.0), then the top-level code runs in its own frame.
        a.emit(0x48, 0x81, 0xEC); a.imm32(8 * n_globals)           # sub rsp, 8*G
        a.emit(0x49, 0x89, 0xE7)                                   # mov r15, rsp
        top = Frame([], None)
        patch = self.prologue()
        try:
            for n in self.top:
                self.stmt(n, top)
            for name, fn in self.funcs.items():
                fn["label"] = "fn_" + name
        except pw.WasmUnsupported as e:
            raise AxeUnsupported(str(e).replace("WebAssembly backend", "AetherOS backend")) from None
        self.patch_prologue(patch, top)
        a.mov_edi(0); a.mov_eax(SYS_EXIT); a.syscall80()           # exit(0)

        for name, fn in self.funcs.items():
            a.bind("fn_" + name)
            f = Frame(fn["params"], name)
            patch = self.prologue()
            try:
                self.block(fn["body"], f)
            except pw.WasmUnsupported as e:
                raise AxeUnsupported(str(e).replace("WebAssembly backend", "AetherOS backend")) from None
            self.patch_prologue(patch, f)
            a.emit(0x66, 0x0F, 0x57, 0xC0)                         # falling off the end returns 0
            a.emit(0xC9); a.ret()                                  # leave; ret

        self.runtime()
        for text, label in self.strings.items():
            a.bind(label)
            a.emit(text.encode("ascii", "replace"))
        return a.finish()

    def prologue(self):
        a = self.a
        a.emit(0x55, 0x48, 0x89, 0xE5)                             # push rbp; mov rbp, rsp
        a.emit(0x48, 0x81, 0xEC); p1 = len(a.code); a.imm32(0)     # sub rsp, 8*slots
        a.emit(0x48, 0x89, 0xE7)                                   # mov rdi, rsp
        a.emit(0xB9); p2 = len(a.code); a.imm32(0)                 # mov ecx, slots
        a.emit(0x31, 0xC0, 0xF3, 0x48, 0xAB)                       # xor eax,eax; rep stosq
        return p1, p2

    def patch_prologue(self, patch, frame):
        self.a.patch32(patch[0], 8 * frame.n_slots)
        self.a.patch32(patch[1], frame.n_slots)

    def string(self, text):
        if text not in self.strings:
            self.strings[text] = self.a.new_label("str")
        return self.strings[text]

    def write_text(self, text):
        a = self.a
        a.lea_rdi(self.string(text)); a.mov_esi(len(text.encode("ascii", "replace")))
        a.mov_eax(SYS_WRITE); a.syscall80()

    def fail(self, message):
        a = self.a
        text = ERROR_PREFIX + message + "\n"
        a.lea_rdi(self.string(text)); a.mov_esi(len(text.encode("ascii", "replace")))
        a.call("rt_fail")

    # — runtime support routines (emitted once) —
    def runtime(self):
        a = self.a
        # rt_fail(rdi = message, esi = length): print it, exit(1)
        a.bind("rt_fail")
        a.mov_eax(SYS_WRITE); a.syscall80()
        a.mov_edi(1); a.mov_eax(SYS_EXIT); a.syscall80()

        # rt_printnum(xmm0): the kernel formats numbers exactly like the
        # interpreter's format_number (whole numbers without ".0", others
        # rounded to 10 places, never scientific notation)
        a.bind("rt_printnum")
        a.emit(0x66, 0x48, 0x0F, 0x7E, 0xC7)                       # movq rdi, xmm0
        a.mov_eax(SYS_PRINTNUM); a.syscall80(); a.ret()

        # rt_printbool(xmm0)
        a.bind("rt_printbool")
        f = a.new_label("pbf")
        a.zero_x1(); a.ucomis(); a.jcc("e", f)
        self.write_text("true"); a.ret()
        a.bind(f)
        self.write_text("false"); a.ret()

        # rt_finite(xmm0): stop with "too big" if xmm0 is +-infinity
        a.bind("rt_finite")
        ok = a.new_label("fin")
        a.emit(0x66, 0x48, 0x0F, 0x7E, 0xC0)                       # movq rax, xmm0
        a.emit(0x48, 0x89, 0xC1)                                   # mov rcx, rax
        a.emit(0x48, 0xC1, 0xE9, 0x34)                             # shr rcx, 52
        a.emit(0x81, 0xE1); a.imm32(0x7FF)                         # and ecx, 0x7ff
        a.emit(0x81, 0xF9); a.imm32(0x7FF)                         # cmp ecx, 0x7ff
        a.jcc("ne", ok)
        self.fail("That number is too big for PlainLang to hold.")
        a.bind(ok); a.ret()

        # rt_trunc(xmm0) -> xmm0 truncated toward zero (clobbers rax, rcx)
        a.bind("rt_trunc")
        done = a.new_label("tr")
        a.emit(0x66, 0x48, 0x0F, 0x7E, 0xC0)                       # movq rax, xmm0
        a.emit(0x48, 0x89, 0xC1)                                   # mov rcx, rax
        a.emit(0x48, 0xC1, 0xE9, 0x34)                             # shr rcx, 52
        a.emit(0x81, 0xE1); a.imm32(0x7FF)                         # and ecx, 0x7ff
        a.emit(0x81, 0xF9); a.imm32(1023 + 52)                     # |x| >= 2^52: already whole
        a.jcc("ae", done)
        a.emit(0xF2, 0x48, 0x0F, 0x2C, 0xC0)                       # cvttsd2si rax, xmm0
        a.emit(0xF2, 0x48, 0x0F, 0x2A, 0xC0)                       # cvtsi2sd xmm0, rax
        a.bind(done); a.ret()

        # rt_floor / rt_ceil (xmm0 -> xmm0; clobbers xmm1, xmm3, rax, rcx)
        for name, cc, op in (("rt_floor", "be", 0x5C), ("rt_ceil", "ae", 0x58)):
            a.bind(name)
            done = a.new_label("fl")
            a.emit(0xF2, 0x0F, 0x10, 0xD8)                         # movsd xmm3, xmm0
            a.call("rt_trunc")
            a.emit(0x66, 0x0F, 0x2E, 0xC3)                         # ucomisd xmm0, xmm3
            a.jcc(cc, done)                                        # floor: trunc <= x is right
            a.const(1.0, 1)
            a.sd(op)                                               # -/+ 1
            a.bind(done); a.ret()

        # rt_power(xmm0 = base, xmm1 = integer exponent) -> xmm0
        a.bind("rt_power")
        lp, skip, fin, pos, out, frac = (a.new_label(x) for x in ("pl", "ps", "pf", "pp", "po", "pq"))
        a.emit(0xF2, 0x0F, 0x10, 0xD8)                             # movsd xmm3, xmm0   (base)
        a.emit(0xF2, 0x0F, 0x10, 0xD1)                             # movsd xmm2, xmm1   (exponent)
        a.x0_from_x1(); a.call("rt_trunc")
        a.emit(0x66, 0x0F, 0x2E, 0xC2)                             # ucomisd xmm0, xmm2
        a.jcc("ne", frac)
        a.emit(0xF2, 0x48, 0x0F, 0x2C, 0xDA)                       # cvttsd2si rbx, xmm2
        a.emit(0x48, 0x89, 0xDA)                                   # mov rdx, rbx (sign)
        a.emit(0x48, 0x85, 0xDB); a.jcc("ns", pos)                 # test rbx,rbx
        a.emit(0x48, 0xF7, 0xDB)                                   # neg rbx
        a.bind(pos)
        a.const(1.0, 0)
        a.bind(lp)
        a.emit(0x48, 0x85, 0xDB); a.jcc("e", fin)                  # while rbx != 0
        a.emit(0xF6, 0xC3, 0x01); a.jcc("e", skip)                 # test bl, 1
        a.emit(0xF2, 0x0F, 0x59, 0xC3)                             # mulsd xmm0, xmm3
        a.bind(skip)
        a.emit(0xF2, 0x0F, 0x59, 0xDB)                             # mulsd xmm3, xmm3
        a.emit(0x48, 0xD1, 0xEB)                                   # shr rbx, 1
        a.jmp(lp)
        a.bind(fin)
        a.emit(0x48, 0x85, 0xD2); a.jcc("ns", out)                 # negative exponent: 1/result
        a.const(1.0, 1)
        a.emit(0xF2, 0x0F, 0x5E, 0xC8)                             # divsd xmm1, xmm0
        a.x0_from_x1()
        a.bind(out); a.ret()
        a.bind(frac)
        self.fail("Fractional powers aren't supported by the AetherOS backend yet.")

    # — statements —
    def block(self, block, f):
        for n in pw._stmts(block):
            self.stmt(n, f)

    def stmt(self, n, f):
        a = self.a
        op = n[0]
        if op == "set":
            key = self.key_of(n[1], f.scope, True)
            self.num(n[2], f, allow_bool=True)
            self.write_key(key, f)
        elif op == "say":
            # Evaluate EVERY part before printing ANY of it: the interpreter
            # builds the whole line first, so an error in a later part must
            # stop the program with nothing printed (the differential fuzzer
            # caught an early version printing "total " and then failing).
            vals = []
            for part in self.flatten(n[1], f.scope):
                if part[0] == "str":
                    vals.append(("str", part[1]))
                else:
                    t = self.expr(part, f)
                    slot = f.temp()
                    a.store_rbp(Frame.disp_slot(slot))
                    vals.append((t, slot))
            for kind, v in vals:
                if kind == "str":
                    if v:
                        self.write_text(v)
                else:
                    a.load_rbp(Frame.disp_slot(v))
                    a.call("rt_printbool" if kind == "bool" else "rt_printnum")
            self.write_text("\n")
        elif op == "wait":
            self.wait(n[1], f)
        elif op == "if":
            end = a.new_label("ifend")
            for c, body in n[1]:
                nxt = a.new_label("ifnext")
                self.cond(c, f); self.branch_if_false(nxt)
                self.block(body, f)
                a.jmp(end)
                a.bind(nxt)
            if n[2]:
                self.block(n[2], f)
            a.bind(end)
        elif op == "match":
            tmp = f.temp()
            self.num(n[1], f); a.store_rbp(Frame.disp_slot(tmp))
            end = a.new_label("mend")
            for v, body in n[2]:
                nxt = a.new_label("mnext")
                self.num(v, f); a.x1_from_x0(); a.load_rbp(Frame.disp_slot(tmp))
                a.ucomis(); a.jcc("ne", nxt)
                self.block(body, f)
                a.jmp(end)
                a.bind(nxt)
            if n[3]:
                self.block(n[3], f)
            a.bind(end)
        elif op == "repeat":
            limit, i = f.temp(), f.temp()
            self.num(n[1], f); a.call("rt_trunc"); a.store_rbp(Frame.disp_slot(limit))
            a.emit(0x66, 0x0F, 0x57, 0xC0); a.store_rbp(Frame.disp_slot(i))   # i = 0
            top, cont, brk = a.new_label("rt"), a.new_label("rc"), a.new_label("rb")
            a.bind(top)
            a.load_rbp(Frame.disp_slot(limit)); a.x1_from_x0()
            a.load_rbp(Frame.disp_slot(i)); a.ucomis(); a.jcc("ae", brk)       # i >= limit
            f.loops.append((brk, cont))
            self.block(n[2], f)
            f.loops.pop()
            a.bind(cont)
            a.load_rbp(Frame.disp_slot(i)); a.const(1.0, 1); a.sd(0x58)
            a.store_rbp(Frame.disp_slot(i))
            a.jmp(top)
            a.bind(brk)
        elif op == "while":
            top, brk = a.new_label("wt"), a.new_label("wb")
            a.bind(top)
            self.cond(n[1], f); self.branch_if_false(brk)
            f.loops.append((brk, top))
            self.block(n[2], f)
            f.loops.pop()
            a.jmp(top)
            a.bind(brk)
        elif op == "count":
            self.count(n, f)
        elif op == "call":
            self.expr(n, f)
        elif op == "return":
            if f.scope is None:
                raise AxeUnsupported("'return' outside a function")
            self.num(n[1], f, allow_bool=True)
            a.emit(0xC9); a.ret()
        elif op == "break":
            if not f.loops:
                raise AxeUnsupported("'stop' can only be used inside a loop.")
            a.jmp(f.loops[-1][0])
        elif op == "continue":
            if not f.loops:
                raise AxeUnsupported("'skip' can only be used inside a loop.")
            a.jmp(f.loops[-1][1])
        else:
            raise AxeUnsupported(f"'{op}' is not supported by the AetherOS backend yet")

    def count(self, n, f):
        a = self.a
        _, var, start, stop, body = n
        cnt, stopv, step = f.temp(), f.temp(), f.temp()
        key = self.key_of(var, f.scope, True)
        self.num(start, f); a.store_rbp(Frame.disp_slot(cnt))
        self.num(stop, f); a.store_rbp(Frame.disp_slot(stopv))
        down, have = a.new_label("cd"), a.new_label("ch")
        a.x1_from_x0(); a.load_rbp(Frame.disp_slot(cnt))           # x0 = start, x1 = stop
        a.ucomis(); a.jcc("a", down)                               # start > stop: count down
        a.const(1.0, 0); a.jmp(have)
        a.bind(down); a.const(-1.0, 0)
        a.bind(have); a.store_rbp(Frame.disp_slot(step))
        top, cont, brk = a.new_label("ct"), a.new_label("cc"), a.new_label("cb")
        a.bind(top)
        # exit when (cnt - stop) * step > 0
        a.load_rbp(Frame.disp_slot(stopv)); a.x1_from_x0()
        a.load_rbp(Frame.disp_slot(cnt)); a.sd(0x5C)
        a.emit(0xF2, 0x0F, 0x59, 0x85); a.imm32(Frame.disp_slot(step))   # mulsd xmm0, [rbp+step]
        a.zero_x1(); a.ucomis(); a.jcc("a", brk)
        a.load_rbp(Frame.disp_slot(cnt)); self.write_key(key, f)
        f.loops.append((brk, cont))
        self.block(body, f)
        f.loops.pop()
        a.bind(cont)
        a.load_rbp(Frame.disp_slot(cnt))
        a.emit(0xF2, 0x0F, 0x58, 0x85); a.imm32(Frame.disp_slot(step))   # addsd xmm0, [rbp+step]
        a.store_rbp(Frame.disp_slot(cnt))
        a.jmp(top)
        a.bind(brk)

    def wait(self, e, f):
        """wait N seconds -> sleep(ms) system calls (the kernel caps one call at
        10 s, so long waits loop)."""
        a = self.a
        self.num(e, f)
        a.const(1000.0, 1); a.sd(0x59)                             # seconds -> ms
        a.emit(0xF2, 0x48, 0x0F, 0x2C, 0xD8)                       # cvttsd2si rbx, xmm0
        lp, last, done = a.new_label("wl"), a.new_label("wz"), a.new_label("wd")
        a.bind(lp)
        a.emit(0x48, 0x81, 0xFB); a.imm32(10000)                   # cmp rbx, 10000
        a.jcc("le", last)
        a.mov_edi(10000); a.mov_eax(SYS_SLEEP); a.syscall80()
        a.emit(0x48, 0x81, 0xEB); a.imm32(10000)                   # sub rbx, 10000
        a.jmp(lp)
        a.bind(last)
        a.emit(0x48, 0x85, 0xDB); a.jcc("le", done)                # nothing (left) to wait
        a.emit(0x48, 0x89, 0xDF)                                   # mov rdi, rbx
        a.mov_eax(SYS_SLEEP); a.syscall80()
        a.bind(done)

    # — variables —
    def write_key(self, key, f):
        if key[0] == "g":
            self.a.store_r15(8 * list(self.globals).index(key[1]))
        elif key[1] in f.params:
            self.a.emit(0xF2, 0x0F, 0x11, 0x85); self.a.imm32(f.disp_param(key[1]))
        else:
            self.a.store_rbp(Frame.disp_slot(f.slot_of(key[1])))

    def read_key(self, key, f):
        if key[0] == "g":
            self.a.load_r15(8 * list(self.globals).index(key[1]))
        elif key[1] in f.params:
            self.a.load_rbp(f.disp_param(key[1]))
        else:
            self.a.load_rbp(Frame.disp_slot(f.slot_of(key[1])))

    # — expressions: result always in xmm0 as a double (true/false = 1.0/0.0) —
    def num(self, e, f, allow_bool=False):
        t = self.expr(e, f)
        if t == "bool" and not allow_bool:
            raise AxeUnsupported("arithmetic on true/false is not supported by the AetherOS backend")
        if t == "text":
            raise AxeUnsupported("text values can only be said, not stored or computed with")

    def cond(self, e, f):
        t = self.expr(e, f)
        if t == "text":
            raise AxeUnsupported("text used as a condition is not supported by the AetherOS backend")

    def branch_if_false(self, label):
        self.a.zero_x1(); self.a.ucomis(); self.a.jcc("e", label)

    def binary(self, l, r, f, allow_bool=False):
        """xmm0 = l, xmm1 = r."""
        self.num(l, f, allow_bool); self.a.push_x0()
        self.num(r, f, allow_bool); self.a.x1_from_x0(); self.a.pop_x0()

    def expr(self, e, f):
        a = self.a
        op = e[0]
        if op == "num":
            a.const(e[1]); return "num"
        if op == "bool":
            a.const(1.0 if e[1] else 0.0); return "bool"
        if op == "str":
            raise AxeUnsupported("text values can only be said, not stored or computed with")
        if op == "neg":
            self.num(e[1], f); a.x0_bit63(0xF8); return "num"
        if op == "var":
            key = self.key_of(e[1], f.scope)
            self.read_key(key, f)
            return "bool" if self.var_types.get(key, "num") == "bool" else "num"
        if op == "binop":
            if e[1] == "+" and self.typeof(e, f.scope) == "text":
                raise AxeUnsupported("text can only be said, not stored or computed with")
            self.binary(e[2], e[3], f)
            if e[1] == "+":
                a.sd(0x58)
            elif e[1] == "-":
                a.sd(0x5C)
            elif e[1] == "*":
                a.sd(0x59)
            else:
                ok = a.new_label("dv")
                a.emit(0x66, 0x0F, 0x57, 0xD2)                     # xorpd xmm2, xmm2
                a.emit(0x66, 0x0F, 0x2E, 0xCA)                     # ucomisd xmm1, xmm2
                a.jcc("ne", ok)
                self.fail("You can't divide by zero.")
                a.bind(ok)
                a.sd(0x5E)
            a.call("rt_finite")
            return "num"
        if op == "cmp":
            self.binary(e[2], e[3], f, allow_bool=True)
            a.ucomis()
            a.setcc_to_x0({"==": "e", "!=": "ne", "<": "b", ">": "a", "<=": "be", ">=": "ae"}[e[1]])
            return "bool"
        if op in ("and", "or"):
            short, end = a.new_label("sc"), a.new_label("se")
            self.cond(e[1], f)
            a.zero_x1(); a.ucomis()
            a.jcc("e" if op == "and" else "ne", short)
            self.cond(e[2], f)
            a.zero_x1(); a.ucomis(); a.setcc_to_x0("ne")
            a.jmp(end)
            a.bind(short); a.const(0.0 if op == "and" else 1.0)
            a.bind(end)
            return "bool"
        if op == "not":
            self.cond(e[1], f)
            a.zero_x1(); a.ucomis(); a.setcc_to_x0("e")
            return "bool"
        if op == "call":
            fn = self.funcs[e[1]]
            for arg in e[2]:
                self.num(arg, f, allow_bool=True); a.push_x0()
            a.call("fn_" + e[1])
            if e[2]:
                a.emit(0x48, 0x81, 0xC4); a.imm32(8 * len(e[2]))   # add rsp, 8*args
            return "bool" if self.ret_types.get(e[1], "num") == "bool" else "num"
        if op == "builtin":
            return self.builtin(e[1], e[2], f)
        raise AxeUnsupported(f"'{op}' is not supported by the AetherOS backend yet")

    def builtin(self, name, args, f):
        a = self.a
        if name == "absolute":
            self.num(args[0], f); a.x0_bit63(0xF0)
        elif name in ("floor", "ceiling"):
            self.num(args[0], f); a.call("rt_floor" if name == "floor" else "rt_ceil")
        elif name in SIMPLE:
            self.binary(args[0], args[1], f); a.sd(SIMPLE[name])
        elif name == "round":
            # schoolbook rounding: sign * floor(|x| + 0.5)
            done = a.new_label("rd")
            self.num(args[0], f)
            a.emit(0xF2, 0x0F, 0x10, 0xD0)                         # movsd xmm2, xmm0
            a.x0_bit63(0xF0); a.const(0.5, 1); a.sd(0x58)
            a.call("rt_floor")
            a.emit(0x66, 0x48, 0x0F, 0x7E, 0xD0)                   # movq rax, xmm2
            a.emit(0x48, 0x85, 0xC0); a.jcc("ns", done)
            a.x0_bit63(0xF8)
            a.bind(done)
        elif name == "sqrt":
            ok = a.new_label("sq")
            self.num(args[0], f)
            a.zero_x1(); a.ucomis(); a.jcc("ae", ok)
            self.fail("I can't take the square root of a negative number.")
            a.bind(ok)
            a.emit(0xF2, 0x0F, 0x51, 0xC0)                         # sqrtsd xmm0, xmm0
        elif name == "remainder":
            ok, small = a.new_label("rz"), a.new_label("rs")
            self.num(args[0], f); a.call("rt_trunc"); a.push_x0()
            self.num(args[1], f); a.call("rt_trunc"); a.push_x0()
            a.emit(0xF2, 0x0F, 0x10, 0x0C, 0x24)                   # movsd xmm1, [rsp]   (b)
            a.emit(0x66, 0x0F, 0x57, 0xD2, 0x66, 0x0F, 0x2E, 0xCA)  # b == 0 ?
            a.jcc("ne", ok)
            self.fail("You can't take a remainder when dividing by zero.")
            a.bind(ok)
            # operands beyond 2**53: the interpreter uses exact big integers
            for disp in (0, 8):
                a.emit(0x48, 0x8B, 0x44, 0x24, disp)               # mov rax, [rsp+disp]
                a.emit(0x48, 0x0F, 0xBA, 0xF0, 0x3F)               # btr rax, 63
                a.emit(0x48, 0xB9); a.emit(struct.pack("<Q", f64_bits(2.0 ** 53)))  # mov rcx, 2^53
                a.emit(0x48, 0x39, 0xC8)                           # cmp rax, rcx
                a.jcc("a", small + "big")
            a.jmp(small)
            a.bind(small + "big")
            self.fail("Remainders of numbers beyond 2^53 aren't supported by the AetherOS backend yet.")
            a.bind(small)
            a.emit(0xF2, 0x0F, 0x10, 0x44, 0x24, 0x08)             # movsd xmm0, [rsp+8] (a)
            a.emit(0xF2, 0x0F, 0x10, 0x0C, 0x24)                   # movsd xmm1, [rsp]
            a.sd(0x5E); a.call("rt_floor")                         # floor(a / b)
            a.emit(0xF2, 0x0F, 0x10, 0x0C, 0x24); a.sd(0x59)       # * b
            a.x1_from_x0()
            a.emit(0xF2, 0x0F, 0x10, 0x44, 0x24, 0x08)             # a
            a.sd(0x5C)                                             # a - b*floor(a/b)
            a.emit(0x48, 0x83, 0xC4, 0x10)                         # add rsp, 16
        elif name == "power":
            ok = a.new_label("pw")
            self.binary(args[0], args[1], f)
            # 0 to a negative power
            a.emit(0x66, 0x0F, 0x57, 0xD2)                         # xorpd xmm2, xmm2
            a.emit(0x66, 0x0F, 0x2E, 0xC2); a.jcc("ne", ok)        # base != 0
            a.emit(0x66, 0x0F, 0x2E, 0xCA); a.jcc("ae", ok)        # exponent >= 0
            self.fail("You can't raise 0 to a negative power.")
            a.bind(ok)
            a.call("rt_power")
            a.call("rt_finite")
        else:
            raise AxeUnsupported(f"'{name}' is not supported by the AetherOS backend yet")
        return "num"


# ─── parsing (with `wait`) ──────────────────────────────────────────────────

class Parser(pl.Parser):
    """The standard parser, plus `wait N` (the spec's turtle-extension
    statement, which this backend can actually execute)."""

    def _statement_inner(self):
        if self.is_kw("wait"):
            self.advance()
            return ("wait", self.expression())
        return super()._statement_inner()


def parse(source):
    return Parser(pl.tokenize(source)).parse()


def compile_axe(source):
    """PlainLang source -> x86-64 machine code (bytes). Raises AxeUnsupported."""
    return Compiler(parse(source)).compile()


def to_axe_text(code, hint="none", name="program", rationale=""):
    lines = ["AXE1", f"# {name} - compiled from PlainLang by plainaxe"]
    if rationale:
        lines += ["# " + l for l in rationale.splitlines()]
    if hint != "none":
        lines.append(f"hint={hint}")
    for i in range(0, len(code), 16):
        lines.append(" ".join(f"{b:02x}" for b in code[i:i + 16]))
    return "\n".join(lines) + "\n"


def main(argv):
    import plainhint
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
        tree = parse(source)
        code = Compiler(tree).compile()
    except AxeUnsupported as e:
        print(f"\n  The AetherOS backend can't compile this yet:\n    {e}")
        return 1
    except pl.PlainLangError as e:
        print(pl.format_error(source, e))
        return 1
    hint_arg = argv[argv.index("--hint") + 1] if "--hint" in argv else "auto"
    analysis = argv[argv.index("--analysis") + 1] if "--analysis" in argv else "counted"
    if hint_arg == "auto":
        hint, why = plainhint.infer(tree, analysis)
        why = f"analysis: {analysis}\n" + why
    else:
        hint, why = hint_arg, "hint given on the command line"
    if "--explain" in argv:
        print(f"hint: {hint}\n{why}")
    import os
    out = argv[argv.index("-o") + 1] if "-o" in argv else os.path.splitext(path)[0] + ".axe"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(to_axe_text(code, hint, os.path.basename(path), why))
    print(f"wrote {out} ({len(code)} bytes of x86-64, hint={hint})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
