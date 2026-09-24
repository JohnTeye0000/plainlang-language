"""
Seeded, reproducible differential fuzzing of the JavaScript engine against the Python
interpreter (see fuzz_js.py). The JS engine is what the browser playground runs and has
its own tokenizer, parser and interpreter, so this is the guard against it drifting.

Skips itself (exit 0) if Node isn't installed.

Run with:   python test_fuzz_js.py
"""

import shutil
import sys

import fuzz_js

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

if shutil.which("node") is None:
    print("node not found -- skipping")
    sys.exit(0)

BATCHES = [(400, 1), (400, 2), (400, 3)]
failures = 0
for count, seed in BATCHES:
    bad = fuzz_js.fuzz_js(count, seed)
    if bad is None:
        print(f"  ✓ seed {seed}: {count} random programs — Python and JavaScript agreed")
    else:
        failures += 1
        src, py, js = bad
        print(f"  ✗ seed {seed}: MISMATCH\n{src}\n  python:     {py}\n  javascript: {js}")

print(f"\n{sum(c for c, _ in BATCHES)} random programs checked, {failures} mismatching batch(es)")
sys.exit(1 if failures else 0)
