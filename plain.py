"""
plain -- one command for everything PlainLang can do.

    plain run program.plang        run a program (tree-walking interpreter; supports import)
    plain repl                     an interactive prompt
    plain check program.plang      find mistakes before running (static analysis + types)
    plain fmt [--write|--check] program.plang
    plain vm program.plang         run on the bytecode VM   (--dis, --trace, --optimize, --emit, --run-bc)
    plain wasm program.plang       compile to WebAssembly   (-o out.wasm to keep the binary)
    plain spec program.plang       does the grammar accept this file?
    plain lsp                      start the language server on stdio (for editors)
    plain docs                     build the documentation site into ./site
    plain version

Each subcommand is the tool of the same name, run exactly as if you had typed
`python plainlang.py ...` (or plainvm.py, plaincheck.py, ...), so nothing here can
drift from what those tools do.
"""

import os
import runpy
import sys

VERSION = "0.5.0"
HERE = os.path.dirname(os.path.abspath(__file__))

COMMANDS = {
    "run": "plainlang",
    "repl": "plainlang",
    "check": "plaincheck",
    "fmt": "plainfmt",
    "vm": "plainvm",
    "wasm": "plainwasm",
    "spec": "plainspec",
    "lsp": "plainlsp",
    "docs": "build_docs",
}


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd in ("version", "--version", "-V"):
        print(f"PlainLang {VERSION}")
        return 0
    if cmd not in COMMANDS:
        print(f"plain: unknown command '{cmd}'.\n")
        close = [c for c in COMMANDS if c.startswith(cmd[:1])]
        if close:
            print(f"  Did you mean: {', '.join(close)}?")
        print("  Run 'plain help' to see every command.")
        return 2
    if cmd == "repl":
        rest = []
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    tool = COMMANDS[cmd]
    sys.argv = [f"{tool}.py"] + rest
    try:
        runpy.run_module(tool, run_name="__main__", alter_sys=True)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
