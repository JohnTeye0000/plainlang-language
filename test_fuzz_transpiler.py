"""
Seeded, reproducible differential fuzzing of the PlainLang -> JavaScript transpiler
against the JS engine's own interpreter (see fuzz_transpiler.py). Nothing else in
the suite exercised the transpiler beyond a handful of hand-written cases in
test_js.js -- this is what actually found the bugs listed in CHANGELOG.md.

Skips itself (exit 0) if Node isn't installed.

Run with:   python test_fuzz_transpiler.py
"""

import shutil
import sys

import fuzz_transpiler

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

if shutil.which("node") is None:
    print("node not found -- skipping")
    sys.exit(0)

BATCHES = [(300, 1), (300, 2), (300, 3)]
failures = 0
for count, seed in BATCHES:
    bad = fuzz_transpiler.fuzz_transpiler(count, seed)
    if bad is None:
        print(f"  ✓ seed {seed}: {count} random programs — transpiled JS matched the JS engine")
    else:
        failures += 1
        src, interp, transpiled = bad
        print(f"  ✗ seed {seed}: MISMATCH\n{src}\n  interpreter: {interp}\n  transpiled:  {transpiled}")

print(f"\n{sum(c for c, _ in BATCHES)} random programs checked, {failures} mismatching batch(es)")
sys.exit(1 if failures else 0)
