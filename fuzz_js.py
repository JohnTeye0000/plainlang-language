"""
Differential fuzzer: the Python interpreter vs the JavaScript engine.

The JS engine (the one the browser playground runs) has its own tokenizer, parser and
interpreter, so it is the engine most likely to drift. This generates the same random
whole-language programs as fuzz.py, runs each on both, and demands identical output --
and the same first line of error message when a program fails.

    python fuzz_js.py            # 1000 programs
    python fuzz_js.py 5000 3     # 5000 programs from seed 3
"""

import json
import os
import random
import shutil
import subprocess
import sys

import fuzz
import plainlang as pl

HERE = os.path.dirname(os.path.abspath(__file__))
_RUNNER = (
    'const PL=require("./plainlang.js");const s=JSON.parse(require("fs").readFileSync(0,"utf8"));'
    'process.stdout.write(JSON.stringify(s.map(c=>{const r=PL.run(c,{rng:()=>0.5});'
    'return {ok:r.ok,out:r.output,err:r.ok?null:r.error};})));'
)


def py_run(src):
    out = []
    ok, _ = pl.run_source(src, on_output=out.append)
    if ok:
        return True, out, None
    return False, out[:-1], out[-1]


def first_message_line(text):
    """The 'what went wrong' line of an error, which both engines word identically."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    return lines[1] if len(lines) > 1 else (lines[0] if lines else "")


def js_run_batch(sources):
    proc = subprocess.run(["node", "-e", _RUNNER], input=json.dumps(sources).encode(),
                          capture_output=True, cwd=HERE, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[:500])
    return json.loads(proc.stdout.decode("utf-8"))


def fuzz_js(n, seed=0, batch=200):
    """Returns None if every program agreed, else (source, python_result, js_result)."""
    for start in range(0, n, batch):
        sources = [fuzz.Generator(random.Random(seed * 1_000_003 + k)).program()
                   for k in range(start, min(n, start + batch))]
        js = js_run_batch(sources)
        for src, j in zip(sources, js):
            ok, out, err = py_run(src)
            same = ok == j["ok"] and out == j["out"]
            if same and not ok:
                same = first_message_line(err) == first_message_line(j["err"])
            if not same:
                return src, (ok, out, err and first_message_line(err)), (j["ok"], j["out"], j["err"] and first_message_line(j["err"]))
    return None


if __name__ == "__main__":
    if shutil.which("node") is None:
        print("node not found"); sys.exit(0)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    bad = fuzz_js(n, seed)
    if bad is None:
        print(f"✓ {n} random programs — the Python interpreter and the JavaScript engine agreed on every one.")
        sys.exit(0)
    src, py, js = bad
    print("✗ MISMATCH\n--- program ---\n" + src)
    print("\n--- python ---", py)
    print("\n--- javascript ---", js)
    sys.exit(1)
