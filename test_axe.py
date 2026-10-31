"""
Tests for plainaxe.py (PlainLang -> native x86-64 for the AetherOS kernel) and
plainhint.py (the static scheduling-hint classifier).

The core check is differential, like test_wasm.py: every program is run through
the tree-walking interpreter AND compiled to machine code and executed inside
the real AetherOS kernel (booted in QEMU), and the outputs must match exactly,
including the point where a runtime error stops the program. That includes a
few hundred random programs from the WebAssembly fuzzer's generator.

Needs the AetherOS repo (sibling folder `aetheros-kernel`, or $AETHEROS_DIR)
with a built kernel image, and QEMU. Skips itself (exit 0) if either is missing.

Run with:   python test_axe.py
"""

import os
import random
import re
import sys

import fuzz_wasm
import plainaxe as px
import plainhint
import plainlang as pl

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL = os.environ.get("AETHEROS_DIR") or os.path.join(HERE, "..", "aetheros-kernel")
sys.path.insert(0, os.path.join(KERNEL, "experiments"))

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def interp(source):
    """Reference run (waits only affect timing, so they're dropped)."""
    src = "\n".join(l for l in source.split("\n") if not l.strip().startswith("wait "))
    return fuzz_wasm.interp(src)


# ─── pure-Python checks (no kernel needed) ──────────────────────────────────

print("Encoder")
a = px.Asm()
a.const(1.0)
check("loading 1.0 into xmm0 is mov rax, imm64 + movq xmm0, rax",
      bytes(a.code) == bytes.fromhex("48b8000000000000f03f66480f6ec0"), bytes(a.code).hex())
a = px.Asm()
a.jmp("x"); a.bind("x")
check("a forward jump to the next instruction has displacement 0",
      a.finish() == bytes.fromhex("e900000000"))
a = px.Asm()
a.bind("top"); a.jcc("ne", "top")
check("a backward jcc encodes a negative rel32", a.finish() == bytes.fromhex("0f85faffffff"))
check("AXE1 text has the magic, the hint line, and hex bytes",
      px.to_axe_text(b"\xcd\x80", "io").splitlines()[0] == "AXE1"
      and "hint=io" in px.to_axe_text(b"\xcd\x80", "io")
      and px.to_axe_text(b"\xcd\x80", "io").rstrip().endswith("cd 80"))

print("Unsupported features are refused, not miscompiled")
for name, src in [
    ("lists", "set xs to list of 1, 2, 3\nsay length of xs"),
    ("records", 'set p to record with "a" as 1\nsay p'),
    ("text variables", 'set s to "hi"\nsay s'),
    ("ask", 'ask "n?" into n\nsay n'),
    ("for each", "for each n in list of 1, 2\nsay n\nend"),
]:
    try:
        px.compile_axe(src)
        check(f"refuses {name}", False, "compiled without complaint")
    except px.AxeUnsupported as e:
        check(f"refuses {name}", "WebAssembly" not in str(e), str(e))
check("`wait` parses as a statement", px.parse("wait 1")[1][0][2][0] == "wait")
try:
    pl.Parser(pl.tokenize("wait 1")).parse()
    check("the standard parser still rejects `wait` at the command line", False)
except pl.PlainLangError:
    check("the standard parser still rejects `wait` at the command line", True)

print("Hint classifier")
CPU_PROG = "set s to 0\ncount i from 1 to 200000\nset s to s plus i\nend\nsay s"
IO_PROG = "repeat 30 times\nset s to 0\ncount i from 1 to 2000\nset s to s plus i\nend\nwait 0.004\nend"
INT_PROG = "repeat 30 times\nwait 0.015\nset s to 0\ncount i from 1 to 50\nset s to s plus i\nend\nend"
for name, src, want in [("a long counting loop", CPU_PROG, "cpu"),
                        ("bursts of work between waits", IO_PROG, "io"),
                        ("mostly waiting, tiny bursts", INT_PROG, "interactive"),
                        ("a three-line program", "say 1\nsay 2\nsay 3", "none")]:
    hint, why = plainhint.infer(px.parse(src))
    check(f"{name} -> {want}", hint == want, f"got {hint}: {why}")
hint, why = plainhint.infer(px.parse(
    "define g with a\nreturn a\nend\nset n to g with 5\nrepeat n times\nwait 1\nend"))
check("a loop count computed by a function call is flagged in the rationale", "isn't a constant" in why, why)

print("Counted-loop analysis")
COUNTED = "set x to 0\nwhile x is less than 10000\nset x to x plus 1\nend\nwait 0.001"
_, why = plainhint.infer(px.parse(COUNTED))
check("a counted while loop gets its exact trip count", "10,000 iterations" in why, why)
_, why = plainhint.infer(px.parse(COUNTED), "basic")
check("the basic analysis still just guesses", "assumed 100" in why, why)
for name, body, reason in [
    ("a `skip` that can jump past the increment",
     "set x to 0\nwhile x is less than 50\nif x is equal to 3 then\nskip\nend\nset x to x plus 1\nend", "skip"),
    ("a counter that moves away from its bound",
     "set x to 0\nwhile x is less than 50\nset x to x minus 1\nend", "away"),
    ("a bound that changes inside the loop",
     "set n to 50\nset x to 0\nwhile x is less than n\nset n to n plus 1\nset x to x plus 1\nend", "bound changes"),
    ("a counter written twice",
     "set x to 0\nwhile x is less than 50\nset x to x plus 1\nset x to x plus 1\nend", "exactly once"),
    ("an unknown starting value",
     "define g with a\nreturn a\nend\nset x to g with 0\nwhile x is less than 50\nset x to x plus 1\nend", "starting value"),
]:
    _, why = plainhint.infer(px.parse(body))
    check(f"refuses to guess: {name}", "assumed 100" in why and reason in why, why)
_, why = plainhint.infer(px.parse("set x to 10\nwhile x is greater than 0\nset x to x minus 2\nend"))
check("a counting-down loop is recognised (5 iterations)", "5 iterations" in why, why)

print("Safety-biased analysis")
OPAQUE = ("define g with a\nreturn a\nend\nrepeat 30 times\nset n to g with 5000\nset x to 0\n"
          "while x is less than n\nset x to x plus 1\nend\nwait 0.004\nend")
check("counted guesses an opaque loop light", plainhint.infer(px.parse(OPAQUE))[0] == "interactive")
hint, why = plainhint.infer(px.parse(OPAQUE), "safe")
check("safe assumes 10,000 iterations and guesses heavier", hint == "io" and "assumed 10000" in why, f"{hint}: {why}")
GATED = ("count r from 1 to 40\nset s to 0\ncount i from 1 to 2000\nset s to s plus i\nend\n"
         "if remainder of r and 4 is 0 then\nwait 0.004\nend\nend")
check("counted counts a gated wait on every round", plainhint.infer(px.parse(GATED))[0] == "io")
hint, why = plainhint.infer(px.parse(GATED), "safe")
check("safe counts an `if` without `otherwise` as no wait", hint == "cpu" and "fewest waits" in why, f"{hint}: {why}")
hint, _ = plainhint.infer(px.parse(GATED.replace("wait 0.004\nend", "wait 0.004\notherwise\nwait 0.001\nend")), "safe")
check("safe keeps a wait taken on every branch", hint == "io", hint)
check("known loops are unaffected by safe", plainhint.infer(px.parse(IO_PROG), "safe")[0] == "io")

# ─── differential: interpreter vs. the real kernel ──────────────────────────

try:
    import aetherbench as ab
except ImportError:
    ab = None
if ab is None or not os.path.exists(ab.DEFAULT_BIN) or not os.path.exists(ab.DEFAULT_QEMU):
    print("\nAetherOS kernel image or QEMU not found -- skipping the on-kernel tests")
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)

WORK = os.path.join(HERE, ".axe_test")
os.makedirs(WORK, exist_ok=True)
BATCH_BYTES = 900_000      # AFS1 holds up to 1 MiB per disk image


def run_on_aetheros(programs):
    """{name: source} -> {name: (output_lines, errored, exit_status)}, running
    every program in as few kernel boots as fit."""
    compiled = {n: px.to_axe_text(px.compile_axe(src), "none", n) for n, src in programs.items()}
    results, batch, size = {}, [], 0
    names = list(compiled)

    def flush(batch, k):
        files = {n: compiled[n] for n in batch}
        files["autorun"] = "".join(f"exec {n}\n" for n in batch) + "poweroff\n"
        img, log = os.path.join(WORK, f"b{k}.img"), os.path.join(WORK, f"b{k}.log")
        ab.build_data_image(img, files)
        if os.path.exists(log):
            os.remove(log)
        ab.run_qemu(ab.DEFAULT_QEMU, ab.DEFAULT_BIN, img, log, False, 600, stall=60)
        text = open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else ""
        for n in batch:
            m = re.search(re.escape(f"PROG,{n},begin") + r"\r?\n(.*?)\r?\nPROG," + re.escape(n) + r",end,(\S+)",
                          text, re.S)
            if not m:
                results[n] = (None, None, "no output (kernel crashed or timed out?)")
                continue
            lines = [l for l in m.group(1).replace("\r", "").split("\n") if not l.startswith("[harden]")]
            if lines and lines[-1] == "":
                lines.pop()
            err = None
            for i, l in enumerate(lines):
                if l.startswith(px.ERROR_PREFIX):
                    err = i
                    break
            results[n] = ((lines[:err] if err is not None else lines), err is not None, m.group(2))

    k = 0
    for n in names:
        if batch and size + len(compiled[n]) > BATCH_BYTES:
            flush(batch, k); k += 1; batch, size = [], 0
        batch.append(n); size += len(compiled[n])
    if batch:
        flush(batch, k)
    return results


CASES = {
    "integer arithmetic": "say 2 plus 3 multiplied by 4\nsay (2 plus 3) multiplied by 4",
    "division gives fractions": "say 7 divided by 2\nsay 12 divided by 3\nsay 1 divided by 3",
    "negative numbers": "say minus 5 plus 8\nsay absolute of (minus 8)",
    "floor ceiling round": "say floor of 3.7\nsay ceiling of 3.2\nsay round of 2.5\nsay round of 3.5\n"
                           "say round of (minus 2.5)\nsay floor of (minus 3.5)\nsay ceiling of (minus 3.5)",
    "floored remainder": "say remainder of 17 and 5\nsay remainder of (minus 7) and 3\nsay remainder of 7 and (minus 3)",
    "min max power sqrt": "say min of 4 and 9\nsay max of 4 and 9\nsay power of 2 and 10\nsay square root of 144\n"
                          "say power of 2 and (minus 2)\nsay power of (minus 3) and 3",
    "tiny fractions": "say 1 divided by 1000000\nsay 5 divided by 100000000000\nsay 0.1 plus 0.2",
    "big numbers": "say power of 2 and 100\nsay power of 2 and 60\nsay 123456789 multiplied by 987654321",
    "booleans": "say 5 is greater than 3\nsay 5 is less than 3\nsay not false\nsay (1 is 1) and (2 is 3)",
    "text and values": 'set n to 3\nsay "n is " plus n plus "!"\nsay "half: " plus (n divided by 2)',
    "interpolation": 'set who to 4\nsay "value {who} and {who plus 1}"',
    "if chain": "set a to 15\nif a is at least 18 then\nsay 1\notherwise if a is at least 13 then\nsay 2\n"
                "otherwise\nsay 3\nend",
    "match": "match 3\nwhen 1 then\nsay 10\nwhen 3 then\nsay 30\notherwise\nsay 99\nend",
    "repeat while count": "set n to 0\nrepeat 4 times\nset n to n plus 2\nend\nsay n\nset x to 0\n"
                          "while x is less than 4\nset x to x plus 1\nsay x\nend\ncount i from 5 to 1\nsay i\nend",
    "count leaves its value": "count i from 1 to 4\nend\nsay i",
    "stop and skip": "count i from 1 to 9\nif i is equal to 3 then\nskip\nend\nif i is greater than 5 then\nstop\n"
                     "end\nsay i\nend",
    "nested loops": "count a from 1 to 2\ncount b from 1 to 9\nif b is greater than 2 then\nstop\nend\n"
                    "say a plus b\nend\nend",
    "recursion": "define fact with n\nif n is at most 1 then\nreturn 1\nend\nreturn n multiplied by fact with "
                 "(n minus 1)\nend\nsay fact with 20\ndefine fib with n\nif n is less than 2 then\nreturn n\n"
                 "end\nreturn (fib with (n minus 1)) plus (fib with (n minus 2))\nend\nsay fib with 20",
    "two-argument functions": "define hyp with a and b\nreturn square root of (a multiplied by a plus b "
                              "multiplied by b)\nend\nsay hyp with 3 and 4",
    "functions returning booleans": "define big with n\nreturn n is greater than 3\nend\nsay big with 5\n"
                                    "say big with 1",
    "globals from functions": "set total to 0\ndefine bump with n\nset total to total plus n\nend\n"
                              "call bump with 5\ncall bump with 7\nsay total",
    "parameters shadow globals": "set n to 100\ndefine f with n\nreturn n plus 1\nend\nsay f with 1\nsay n",
    "divide by zero": "say 1\nsay 1 divided by 0\nsay 2",
    "remainder by zero": "say 5\nsay remainder of 5 and 0",
    "negative square root": "say 1\nsay square root of (minus 4)",
    "zero to a negative power": "say power of 0 and (minus 1)",
    "too big": "say power of 10 and 400",
    "too big by multiplication": "set x to 10\nrepeat 400 times\nset x to x multiplied by 10\nend\nsay x",
    "error inside a loop": "count i from 1 to 5\nsay 10 divided by (i minus 3)\nend",
    "wait is a pause, not a change": "say 1\nwait 0.01\nsay 2\nrepeat 3 times\nwait 0.002\nend\nsay 3",
}
# Documented differences: the backend must stop with an error instead of
# printing a (possibly wrong) answer.
DIVERGE = {
    "fractional power": "say power of 2 and 0.5",
    "huge remainder": "say remainder of (power of 2 and 100) and 7",
}

rng = random.Random(7)
FUZZ = {}
while len(FUZZ) < 200:
    src = fuzz_wasm.Generator(rng).program()
    try:
        px.compile_axe(src)
    except px.AxeUnsupported:
        continue
    FUZZ[f"f{len(FUZZ):03d}.axe"] = src

programs = {f"c{i:02d}.axe": src for i, src in enumerate(CASES.values())}
programs.update({f"d{i}.axe": src for i, src in enumerate(DIVERGE.values())})
programs.update(FUZZ)
print(f"\nRunning {len(programs)} programs inside AetherOS (QEMU)...")
got = run_on_aetheros(programs)

print("Hand-written programs: interpreter vs AetherOS")
for i, (name, src) in enumerate(CASES.items()):
    out, err, status = got[f"c{i:02d}.axe"]
    want_out, want_err = interp(src)
    check(name, (out, err) == (want_out, want_err),
          f"\n      interpreter: {(want_out, want_err)}\n      aetheros:    {(out, err, status)}")
    if out is not None:
        check(f"{name}: exit status says how it ended", status == ("1" if err else "0"), status)

print("Documented differences stop cleanly with an error")
for i, (name, src) in enumerate(DIVERGE.items()):
    out, err, status = got[f"d{i}.axe"]
    check(name, err is True and status == "1", (out, err, status))

print("Differential fuzzing (200 random programs)")
bad = []
for name, src in FUZZ.items():
    out, err, status = got[name]
    if (out, err) != interp(src):
        bad.append((name, src, (out, err, status), interp(src)))
check("200 random programs agree with the interpreter", not bad,
      bad and f"\n{bad[0][1]}\n      aetheros:    {bad[0][2]}\n      interpreter: {bad[0][3]}")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
