"""
Runs every PlainLang test suite -- the same ones CI runs -- and prints a summary.

    python run_tests.py            # everything
    python run_tests.py --quick    # skip the slow randomized suites while you iterate
    python run_tests.py spec vm    # only suites whose name contains 'spec' or 'vm'

Exit code is nonzero if anything fails.
"""

import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# (label, command, slow?)
SUITES = [
    ("test_plainlang", ["python", "test_plainlang.py"], False),
    ("test_vm", ["python", "test_vm.py"], False),
    ("test_diagnostics", ["python", "test_diagnostics.py"], False),
    ("test_check", ["python", "test_check.py"], False),
    ("test_fuzz", ["python", "test_fuzz.py"], True),
    ("test_fuzz_js", ["python", "test_fuzz_js.py"], True),
    ("test_fuzz_transpiler", ["python", "test_fuzz_transpiler.py"], True),
    ("test_fmt", ["python", "test_fmt.py"], False),
    ("test_imports", ["python", "test_imports.py"], False),
    ("test_lsp", ["python", "test_lsp.py"], False),
    ("test_wasm", ["python", "test_wasm.py"], True),
    ("test_axe", ["python", "test_axe.py"], True),
    ("test_docs", ["python", "test_docs.py"], False),
    ("test_a11y", ["python", "test_a11y.py"], False),
    ("test_spec", ["python", "test_spec.py"], True),
    ("test_cli", ["python", "test_cli.py"], False),
    ("test_meta", ["python", "test_meta.py"], False),
    ("build_spec --check", ["python", "build_spec.py", "--check"], False),
    ("test_js", ["node", "test_js.js"], False),
    ("test_lessons", ["node", "test_lessons.js"], False),
    ("test_pilot", ["node", "test_pilot.js"], False),
    ("test_pilot_report", ["python", "test_pilot_report.py"], False),
]


def main(argv):
    quick = "--quick" in argv
    filters = [a for a in argv if not a.startswith("--")]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    python = sys.executable
    results, total = [], 0
    started = time.time()
    for label, cmd, slow in SUITES:
        if quick and slow:
            print(f"  –  {label:22} skipped (--quick)")
            continue
        if filters and not any(f in label for f in filters):
            continue
        cmd = [python if c == "python" else c for c in cmd]
        t0 = time.time()
        p = subprocess.run(cmd, cwd=HERE, capture_output=True, env=env)
        out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
        counts = re.findall(r"(\d+) passed, (\d+) failed", out)
        passed = sum(int(a) for a, _ in counts)
        total += passed
        ok = p.returncode == 0
        results.append((label, ok, out))
        tail = f"{passed} passed" if counts else out.strip().splitlines()[-1][:60] if out.strip() else ""
        print(f"  {'✓' if ok else '✗'}  {label:22} {tail:24} {time.time() - t0:5.1f}s")
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} suites passed · {total} checks · {time.time() - started:.0f}s")
    for label, _, out in failed:
        print(f"\n── {label} " + "─" * 50)
        print("\n".join(l for l in out.splitlines() if "✗" in l or "Traceback" in l or "Error" in l)[:2000] or out[-1500:])
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main(sys.argv[1:]))
