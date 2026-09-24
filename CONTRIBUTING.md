# Contributing to PlainLang

Thanks for helping. PlainLang is a teaching language, so two things matter more than
cleverness: **clarity for a first‑time coder**, and **every engine agreeing on what a program means**.

## Getting set up

You need Python 3.9+ and Node 20+ (Node is used for the JavaScript engine's tests and for
running WebAssembly). There are no dependencies to install.

```bash
python plain.py help          # every command
python plain.py run demo.plang
python plain.py repl
```

Run **everything CI runs** with one command:

```bash
python run_tests.py
```

Add `--quick` to skip the slow randomized suites while you iterate.

## How the project fits together

```
                       ┌─────────────► plainlang.py    tree-walking interpreter   (the reference)
 source ─► tokenizer ──┤─────────────► plainvm.py      bytecode compiler + VM
          + parser     ├─────────────► plainlang.js    JavaScript engine + transpiler (browser)
                       └─────────────► plainwasm.py    WebAssembly compiler (numeric core)

 plaincheck.py  static analysis        plainfmt.py  formatter        plainlsp.py  language server
 grammar.ebnf ─► plainspec.py          the grammar, executable; SPEC.md is generated from it
```

The Python parser is shared by the interpreter, the VM, the checker and the WebAssembly
compiler. The JavaScript engine has its **own** tokenizer and parser (it runs in the browser),
so any syntax change is made twice — and `spec_fuzz.py` will tell you if you got them out of step.

## The one rule: engines must agree

A program's observable behaviour — what it prints, and whether and where it fails — must be
identical across every engine that supports it. That is enforced by:

| Suite | What it guards |
|---|---|
| `test_plainlang.py` | the reference behaviour and every error message |
| `test_vm.py` | interpreter and VM agree, program by program |
| `test_js.js` | the JavaScript engine, transpiler and diagnostics |
| `test_wasm.py`, `fuzz_wasm.py` | WebAssembly vs the interpreter, incl. fuzzing |
| `fuzz.py` / `test_fuzz.py` | interpreter vs VM on thousands of random programs |
| `fuzz_js.py` / `test_fuzz_js.py` | the Python interpreter vs the JavaScript engine (the browser's) |
| `test_spec.py`, `spec_fuzz.py` | the grammar vs both parsers; every example in `SPEC.md` on every engine |
| `test_docs.py`, `test_lessons.js` | every documentation example and lesson solution really works |
| `test_a11y.py` | WCAG contrast and structure of the playground and docs |

**When a fuzzer finds a disagreement, fix the bug, then add a regression test in the suites above.**
Nearly every subtle behaviour in PlainLang has a story of that kind.

## Adding a language feature — the checklist

A feature isn't done until every box is ticked. (Adding a keyword touches a lot of files on
purpose: it's the price of four engines that agree.)

- [ ] **Tokenizer/parser** — `plainlang.py` (`KEYWORDS`, the parser) **and** `plainlang.js`
- [ ] **Interpreter** — `plainlang.py`; **VM** — `plainvm.py` (compiler + `builtin()` if it's a built‑in); **JS** — `plainlang.js` (interpreter *and* the transpiler in `Compiler`)
- [ ] **WebAssembly** — support it in `plainwasm.py`, or make sure it raises `WasmUnsupported` with a clear message
- [ ] **Static analysis** — `plaincheck.py` (types of results, argument checks)
- [ ] **Grammar** — `grammar.ebnf`; then `python spec_fuzz.py 3000` must report 0 disagreements
- [ ] **Specification** — a rule + executable example in `spec_content.py`, then `python build_spec.py`
- [ ] **Documentation** — an example in `docs_content.py` (`test_docs.py` requires every keyword to be documented)
- [ ] **Editors** — the keyword lists in `vscode-extension/syntaxes/plainlang.tmLanguage.json` and `plainlsp.py`'s hover docs
- [ ] **Tests** — `test_plainlang.py`, `test_vm.py` (cross‑validation), `test_js.js`, and `test_wasm.py` if applicable
- [ ] **Fuzzers** — teach `fuzz.py` (and `fuzz_wasm.py`) to generate it
- [ ] **README / CHANGELOG** — a line each

## Design principles

- **Read aloud.** If a construct can't be spoken naturally, redesign it.
- **Errors are teaching.** Say what happened in plain words, point at the exact spot, and suggest a fix.
- **Precision over cleverness in the checker.** A warning that cries wolf teaches beginners to ignore warnings.
- **No silent behaviour.** Prefer a friendly error to a surprising result (see how numbers, text size and `replace ""` are handled).

## Commits and history

Write commit messages that say *why*. Commits land on the day the work really happens — the history
is part of the project's record. Keep changes focused; a bug fix and its regression test belong together.

## Reporting bugs

Use the bug‑report template. The most useful report is a **small program**, what you expected, what
you got, and *which engine* (`plain run`, `plain vm`, the playground, `plain wasm`) — if two engines
disagree, that alone is a valuable finding.
