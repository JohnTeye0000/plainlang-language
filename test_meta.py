"""
Tests about the test-suite itself: a new suite that isn't wired into CI or the runner
silently stops protecting anything. This fails if that ever happens.

Run with:   python test_meta.py
"""

import glob
import os
import re
import sys

import run_tests

try:
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


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


suites = sorted(os.path.basename(p) for p in glob.glob(os.path.join(HERE, "test_*.py")) + glob.glob(os.path.join(HERE, "test_*.js")))
ci = read(".github/workflows/ci.yml")
runner_files = {" ".join(cmd[1:]) for _, cmd, _ in run_tests.SUITES}

print("Every test suite is wired in")
check(f"found {len(suites)} test suites", len(suites) >= 12, suites)
for s in suites:
    check(f"{s} runs in CI", s in ci, "add it to .github/workflows/ci.yml")
    check(f"{s} runs in run_tests.py", any(s in r for r in runner_files), "add it to SUITES")

print("Automation that must not go stale")
check("CI checks that SPEC.md is up to date", "build_spec.py --check" in ci)
check("CI builds the docs (test_docs.py) and deploys Pages on main", "test_docs.py" in ci and os.path.exists(os.path.join(HERE, ".github/workflows/pages.yml")))
check("run_tests.py also checks SPEC.md", any("build_spec.py --check" in r for r in runner_files))

print("Versioning")
import plain
changelog = read("CHANGELOG.md")
top = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.M).group(1)
check(f"plain.py's version ({plain.VERSION}) matches the newest CHANGELOG entry ({top})", plain.VERSION == top)
roadmap = read("ROADMAP.md")
check("ROADMAP.md links the CHANGELOG", "CHANGELOG.md" in roadmap)

print("Project hygiene")
for doc in ("README.md", "ROADMAP.md", "CHANGELOG.md", "CONTRIBUTING.md", "SPEC.md"):
    check(f"{doc} exists and isn't empty", len(read(doc)) > 500)
check("every file the README's table names actually exists",
      all(os.path.exists(os.path.join(HERE, f)) for f in
          re.findall(r"^\| \*\*`([A-Za-z0-9_./-]+\.(?:py|js|html|ebnf|md|plang))`", read("README.md"), re.M)),
      [f for f in re.findall(r"^\| \*\*`([A-Za-z0-9_./-]+\.(?:py|js|html|ebnf|md|plang))`", read("README.md"), re.M)
       if not os.path.exists(os.path.join(HERE, f))])

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
