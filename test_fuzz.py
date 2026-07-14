"""
Differential-fuzzing test: a fixed, seeded batch of random programs must produce
identical output from the tree-walker and the bytecode VM. Deterministic (seeded)
so it's reproducible in CI. Run with:  python test_fuzz.py
"""

import sys
import fuzz

BATCHES = [(400, 1), (400, 2), (400, 3)]   # (count, seed)

failed = 0
total = 0
for count, seed in BATCHES:
    checked, failure = fuzz.fuzz(count, seed=seed)
    total += checked
    if failure is None:
        print(f"  ✓ seed {seed}: {checked} random programs — both engines agreed")
    else:
        failed += 1
        source, tree, vmout = failure
        print(f"  ✗ seed {seed}: engines disagreed after {checked} programs")
        print("      program:", repr(source))
        print("      tree-walker:", tree)
        print("      bytecode VM:", vmout)

print(f"\n{total} random programs checked, {failed} mismatching batch(es)")
sys.exit(1 if failed else 0)
