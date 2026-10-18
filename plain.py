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
    plain pilot exports/           turn exported pilot data into a findings report
    plain run --lang fr program.plang      write programs in another language (run/check/vm/wasm/spec)
    plain translate --lang fr program.plang   translate a program to/from English (--to CODE)
    plain locale check|template ...        validate a locale file / start a new one
    plain version

Each subcommand is the tool of the same name, run exactly as if you had typed
`python plainlang.py ...` (or plainvm.py, plaincheck.py, ...), so nothing here can
drift from what those tools do.
"""

import os
import runpy
import sys
import tempfile

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
    "pilot": "pilot_report",
    "locale": "plainlocale",
    "translate": "plainlocale",
}

# commands that can read a program written in another language (via --lang)
LANG_COMMANDS = ("run", "check", "vm", "wasm", "spec")


def _extract_lang(rest):
    """Remove --lang CODE from the arguments. Returns (code or None, remaining arguments)."""
    if "--lang" not in rest:
        return None, rest
    i = rest.index("--lang")
    if i + 1 >= len(rest):
        raise SystemExit("plain: --lang needs a language code, e.g. --lang fr")
    return rest[i + 1], rest[:i] + rest[i + 2:]


def _run_translated(tool, rest, lang):
    """Translate the program file to English, run `tool` on it, then clean up. The temporary file
    sits next to the original so relative imports still resolve."""
    import plainlocale
    files = [a for a in rest if not a.startswith("-") and os.path.isfile(a)]
    if not files:
        raise SystemExit("plain: --lang needs a program file to translate.")
    original = files[0]
    locale = plainlocale.load_locale(lang)
    with open(original, encoding="utf-8") as f:
        english = plainlocale.to_english(f.read(), locale)
    directory = os.path.dirname(os.path.abspath(original))
    fd, temp = tempfile.mkstemp(suffix=".plang", prefix=".translated-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(english)
        args = [temp if a == original else a for a in rest]
        print(f"(running {os.path.basename(original)} translated from {locale.name or lang}; errors are shown in English)",
              file=sys.stderr)
        sys.argv = [f"{tool}.py"] + args
        try:
            runpy.run_module(tool, run_name="__main__", alter_sys=True)
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        return 0
    finally:
        try:
            os.remove(temp)
        except OSError:
            pass



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
    if cmd == "translate":
        rest = ["translate"] + rest
    if cmd in LANG_COMMANDS:
        lang, rest = _extract_lang(rest)
        if lang:
            try:
                return _run_translated(tool, rest, lang)
            except Exception as e:      # LocaleError and friends: show a friendly line, not a traceback
                if type(e).__name__ == "LocaleError":
                    print(f"\n  Oops! {e}")
                    return 2
                raise
    sys.argv = [f"{tool}.py"] + rest
    try:
        runpy.run_module(tool, run_name="__main__", alter_sys=True)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
