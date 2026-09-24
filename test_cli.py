"""
Tests for plain.py, the unified command-line tool: every subcommand runs the tool
of the same name, so these check the wiring end to end through real subprocesses.

Run with:   python test_cli.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

try:                                   # ✓ needs UTF-8 even on a legacy Windows console
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def plain(*args, stdin=None):
    p = subprocess.run([sys.executable, os.path.join(HERE, "plain.py"), *args],
                       capture_output=True, cwd=HERE, input=stdin)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


tmp = tempfile.mkdtemp(prefix="plain_cli_")
prog = os.path.join(tmp, "hello.plang")
with open(prog, "w", encoding="utf-8") as f:
    f.write('define double with n\n    return n multiplied by 2\nend\nsay "twice 21 is " plus double with 21\n')
messy = os.path.join(tmp, "messy.plang")
with open(messy, "w", encoding="utf-8") as f:
    f.write('set   x   to 1\nif x is equal to 1 then\nsay   "one"\nend\n')
broken = os.path.join(tmp, "broken.plang")
with open(broken, "w", encoding="utf-8") as f:
    f.write("say mystery\n")

print("Meta")
code, out, _ = plain("version")
check("version prints the release", code == 0 and re.fullmatch(r"PlainLang \d+\.\d+\.\d+\s*", out), out)
import plain as plain_module
with open(os.path.join(HERE, "CHANGELOG.md"), encoding="utf-8") as f:
    latest = re.search(r"^## \[(\d+\.\d+\.\d+)\]", f.read(), re.M).group(1)
check("the version matches the top of the CHANGELOG", plain_module.VERSION == latest, (plain_module.VERSION, latest))
code, out, _ = plain("help")
check("help lists every command", code == 0 and all(c in out for c in plain_module.COMMANDS), out[:200])
code, out, _ = plain("nonsense")
check("an unknown command is refused with a hint", code == 2 and "unknown command" in out, out)

print("Running programs")
code, out, _ = plain("run", prog)
check("run executes a program", code == 0 and out.strip() == "twice 21 is 42", out)
code, out, _ = plain("vm", prog)
check("vm runs the same program on the bytecode VM", code == 0 and out.strip() == "twice 21 is 42", out)
code, out, _ = plain("vm", "--dis", prog)
check("vm --dis disassembles", code == 0 and "CALL" in out, out[:200])
code, out, _ = plain("run", broken)
check("run reports friendly errors", "haven't heard of a variable" in out, out)
code, out, _ = plain("repl", stdin=b'say 1 plus 2\nquit\n')
check("repl evaluates input", "3" in out, out)

print("Analysis and tooling")
code, out, _ = plain("check", prog)
check("check passes a clean program", code == 0 and "No problems" in out, out)
code, out, _ = plain("check", broken)
check("check fails a broken program with a nonzero exit code", code != 0 and "mystery" in out, out)
code, out, _ = plain("fmt", messy)
check("fmt prints the formatted program", 'set x to 1' in out and '    say "one"' in out, out)
code, out, _ = plain("fmt", "--check", messy)
check("fmt --check fails on an unformatted file", code == 1, (code, out))
code, _, _ = plain("fmt", "--write", messy)
code2, out2, _ = plain("fmt", "--check", messy)
check("fmt --write fixes it, and --check then passes", code == 0 and code2 == 0, out2)
code, out, _ = plain("spec", prog)
check("spec validates a program against the grammar", code == 0 and "valid PlainLang" in out, out)
code, out, _ = plain("spec", os.path.join(HERE, "grammar.ebnf"))
check("spec rejects a file that isn't PlainLang", code == 1, out)

if shutil.which("node"):
    print("WebAssembly")
    wasm = os.path.join(tmp, "out.wasm")
    numeric = os.path.join(tmp, "num.plang")
    with open(numeric, "w", encoding="utf-8") as f:
        f.write('define sq with n\n    return n multiplied by n\nend\nsay "sq is " plus sq with 12\n')
    code, out, _ = plain("wasm", numeric)
    check("wasm compiles and runs a numeric program", code == 0 and out.strip() == "sq is 144", out)
    code, out, _ = plain("wasm", numeric, "-o", wasm)
    check("wasm -o writes a binary module", code == 0 and open(wasm, "rb").read(8) == b"\x00asm\x01\x00\x00\x00", out)
    code, out, _ = plain("wasm", prog)
    check("wasm explains what it can't compile yet", code == 0 or "can't compile" in out, out)

print("Language server")
import json
body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}).encode()
exit_body = json.dumps({"jsonrpc": "2.0", "method": "exit"}).encode()
frame = lambda b: f"Content-Length: {len(b)}\r\n\r\n".encode() + b
code, out, _ = plain("lsp", stdin=frame(body) + frame(exit_body))
check("lsp answers an initialize request over stdio", '"capabilities"' in out and "definitionProvider" in out, out[:200])

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
