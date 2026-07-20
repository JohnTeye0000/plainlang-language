"""
Tests for multi-file programs: 'import "other.plang"' pulls another file's
function definitions into the current program. CLI-only (the browser has no
filesystem) -- cross-validated between the tree-walking interpreter and the
bytecode VM, since both resolve imports through the same load_program().

Run with:   python test_imports.py
"""

import os
import shutil
import tempfile

import plainlang as pl
import plainvm as vm

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


class Project:
    """A throwaway directory of .plang files for one test."""
    def __init__(self, files):
        self.dir = tempfile.mkdtemp(prefix="plainlang_import_test_")
        for name, content in files.items():
            with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
                f.write(content)

    def path(self, name):
        return os.path.join(self.dir, name)

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def run_both(entry):
    tree_out, vm_out = [], []
    tree_tree = pl.load_program(entry)
    pl.Interpreter(tree_out.append).run(tree_tree)
    vm.run_file(entry, on_output=vm_out.append, rng=lambda: 0.5)
    return tree_out, vm_out


print("Resolving imports")
proj = Project({
    "utils.plang": 'define sq with n\nreturn n multiplied by n\nend\n'
                   'define cube with n\nreturn n multiplied by (sq with n)\nend',
    "main.plang": 'import "utils.plang"\nsay sq with 5\nsay cube with 3',
})
tree_out, vm_out = run_both(proj.path("main.plang"))
check("imported functions are callable", tree_out == ["25", "27"], tree_out)
check("tree-walker and VM agree", tree_out == vm_out, (tree_out, vm_out))
proj.cleanup()

print("Transitive imports")
proj = Project({
    "a.plang": 'define f with n\nreturn n plus 1\nend',
    "b.plang": 'import "a.plang"\ndefine g with n\nreturn f with (n multiplied by 2)\nend',
    "main.plang": 'import "b.plang"\nsay g with 10',
})
tree_out, vm_out = run_both(proj.path("main.plang"))
check("a function from a transitively-imported file works", tree_out == ["21"], tree_out)
check("tree-walker and VM agree (transitive)", tree_out == vm_out, (tree_out, vm_out))
proj.cleanup()

print("Diamond import (same module imported twice)")
proj = Project({
    "shared.plang": 'define h with n\nreturn n\nend',
    "left.plang": 'import "shared.plang"\ndefine l with n\nreturn h with n\nend',
    "right.plang": 'import "shared.plang"\ndefine r with n\nreturn h with n\nend',
    "main.plang": 'import "left.plang"\nimport "right.plang"\nsay l with 1\nsay r with 2',
})
tree_out, vm_out = run_both(proj.path("main.plang"))
check("diamond import doesn't error", tree_out == ["1", "2"], tree_out)
check("tree-walker and VM agree (diamond)", tree_out == vm_out, (tree_out, vm_out))
proj.cleanup()

print("Error cases")
proj = Project({
    "bad.plang": 'define f with n\nreturn n\nend\nsay "top-level code in a library"',
    "main.plang": 'import "bad.plang"\nsay "hi"',
})
try:
    pl.load_program(proj.path("main.plang"))
    check("rejects a library with top-level code", False, "did not raise")
except pl.PlainLangError as e:
    check("rejects a library with top-level code", "only contain function definitions" in e.message, e.message)
proj.cleanup()

proj = Project({
    "a.plang": 'import "b.plang"\ndefine a with n\nreturn n\nend',
    "b.plang": 'import "a.plang"\ndefine b with n\nreturn n\nend',
})
try:
    pl.load_program(proj.path("a.plang"))
    check("rejects a circular import", False, "did not raise")
except pl.PlainLangError as e:
    check("rejects a circular import", "Circular import" in e.message, e.message)
proj.cleanup()

proj = Project({"main.plang": 'import "nope.plang"\nsay 1'})
try:
    pl.load_program(proj.path("main.plang"))
    check("reports a missing import file", False, "did not raise")
except pl.PlainLangError as e:
    check("reports a missing import file", "couldn't find" in e.message, e.message)
proj.cleanup()

print(f"\n{PASS} passed, {FAIL} failed")
if FAIL:
    raise SystemExit(1)
