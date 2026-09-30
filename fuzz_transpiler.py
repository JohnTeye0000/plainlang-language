"""
Differential fuzzer for the PlainLang -> JavaScript transpiler.

`Compiler.compile()` in plainlang.js emits standalone JavaScript from a PlainLang
program -- the "As JS" tab in the playground, and the whole point of the
"it compiles to real JavaScript" feature. Nothing had ever fuzzed the transpiler
itself: every other fuzzer in this repo checks an *engine's own* output against
another engine, but the transpiled JS is generated code with no engine of its own
to compare against except "run it and see".

This generates the same random whole-language programs as fuzz.py, compiles each
with PL.compile(), executes the result in a sandboxed VM context, and requires the
captured console.log output to match the JS interpreter's own PL.run() output for
that same program (the two must agree since they're both "the JavaScript engine's
answer" -- one by walking the tree, one by first lowering it to JS).

Found real bugs the first time it ran: a descending 'count' produced zero
iterations; a body reassigning the count variable corrupted the JS for-loop's own
control variable (exactly the bug the VM's compiler had, years before this
transpiler existed); 'repeat' hardcoded its hidden counter as literal 'i', which
collided with a real PlainLang variable also named i; native '+' bypassed the
shared number-formatting/size-ceiling logic; native '%' does truncated (not
floored) remainder; several text builtins used String() instead of format();
'sorted' used a numeric-only comparator; 'stop' inside a match-case nested in a
loop hit JS's switch-intercepts-bare-break behaviour; and format()'s own copy of
the number-to-text logic didn't have the "never scientific notation" and "BigInt
past 2**53" guards the rest of the codebase already had. All fixed; see CHANGELOG.

    python fuzz_transpiler.py            # 500 programs
    python fuzz_transpiler.py 3000 7     # 3000 programs, seed 7
"""

import json
import os
import random
import shutil
import subprocess
import sys

import fuzz
import fuzz_wasm

HERE = os.path.dirname(os.path.abspath(__file__))
_RUNNER = '''
const PL = require("./plainlang.js");
const vm = require("vm");
const srcs = JSON.parse(require("fs").readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(srcs.map(src => {
  const interp = PL.run(src, {rng: () => 0.5});
  let compiled = null, err = null;
  try {
    const js = PL.compile(src);
    const captured = [];
    vm.runInNewContext(js, {console: {log: (...a) => captured.push(a.join(" "))}, Math}, {timeout: 2000});
    compiled = captured;
  } catch (e) { err = String(e && e.message || e); }
  return {ok: interp.ok, out: interp.output, compiled, err};
})));
'''


def _batch(sources, timeout=180):
    proc = subprocess.run(["node", "-e", _RUNNER], input=json.dumps(sources).encode(),
                          capture_output=True, cwd=HERE, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[:2000])
    return json.loads(proc.stdout.decode("utf-8"))


def fuzz_transpiler(n, seed=0, batch=300):
    """Returns None if every program agreed, else (source, interp_output, transpiled_result)."""
    checked = 0
    for start in range(0, n, batch):
        k0 = seed * 1_000_003 + start
        sources = []
        for i in range(min(batch, n - start)):
            gen = fuzz.Generator if (start + i) % 2 == 0 else fuzz_wasm.Generator
            sources.append(gen(random.Random(k0 + i)).program())
        results = _batch(sources)
        for src, r in zip(sources, results):
            if not r["ok"]:
                continue          # only compare programs the JS interpreter itself ran cleanly
            checked += 1
            if r["err"] is not None or r["compiled"] != r["out"]:
                return src, r["out"], (r["compiled"], r["err"])
    return None


if __name__ == "__main__":
    if shutil.which("node") is None:
        print("node not found"); sys.exit(0)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    bad = fuzz_transpiler(n, seed)
    if bad is None:
        print(f"✓ {n} random programs — the transpiled JavaScript matched the JS engine's own output on every one.")
        sys.exit(0)
    src, interp, (compiled, err) = bad
    print("✗ MISMATCH\n--- program ---\n" + src)
    print("\n--- JS interpreter ---", interp)
    print("\n--- transpiled JS ---", compiled, err)
    sys.exit(1)
