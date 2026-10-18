# Changelog

All notable changes to PlainLang. Versions follow [semantic versioning](https://semver.org);
each maps to a phase of [ROADMAP.md](ROADMAP.md).

> **A note on the tags.** Git tags `v0.2.0`, `v0.3.0` and `v0.4.0` were created
> *retroactively* (on 2026‑09‑24) and point at the commits that actually completed each
> phase — the commit dates below are the real ones. Nothing was back‑dated.

## [Unreleased]

- **Write PlainLang in your own language** (`plainlocale.py`). A locale file maps each of the 98 keywords
  to a word in another language; programs are translated *before* tokenizing, so every engine, the checker
  and the formatter work in any language unchanged. `plain run --lang fr`, `plain translate`, and
  `plain locale check|template`. Comments, quoted text and names are never touched; `{code}` in a text is.
  English -> French -> English is the identity on hundreds of generated programs. Ships a demonstration
  French locale and a contributor guide, and deliberately no guessed Twi/Ga/Ewe: those need native speakers.
- **Pilot mode** for classroom trials: open the playground with `?pilot=1` and it records which lessons
  are tried, whether each check passed, and the *category* of each error, never the program text, names,
  or error wording (which can quote a learner's variable names). `plain pilot` turns exported files into a
  findings report (completion and attempts per lesson, time to pass, top error kinds), with an honest
  small-sample warning. `PILOT.md` is a step-by-step facilitator guide. The accessibility test caught the
  new participant field missing a label before it shipped.
- **Native x86-64 backend for the AetherOS kernel** (`plainaxe.py`): hand-encoded machine code (SSE2
  doubles, rel32 fixups, a small runtime for floor/trunc/power/error reporting), emitted as AXE1 programs
  that run in ring 3. Reuses the WebAssembly backend's front end. First command-line engine to execute
  `wait N`, compiled to the kernel's blocking `sleep` system call.
- **Static scheduling-hint classifier** (`plainhint.py`): estimates work per wait from loop structure and
  labels a program `cpu`, `io`, `interactive` or `none`, with a written rationale stored in the output.
- **`test_axe.py`**: boots the real kernel in QEMU and checks 30 programs + 200 fuzzer programs against the
  interpreter; also unit-tests the encoder and the classifier (those run in CI; the on-kernel part skips
  without QEMU). Caught an evaluation-order bug in `say` before it shipped.

## [0.5.0] — 2026‑09‑24  ·  Product, reach, and a specification

- **The JavaScript engine joined the fuzzing** (`fuzz_js.py`): 8,000 random programs agree with the Python
  interpreter. It found that `join`, `replace` and list concatenation built their result before checking
  its size, so a runaway program could exhaust memory; all three are now sized first, and lists have a
  ten-million-item ceiling like text.

- **Language specification** (`SPEC.md`), generated from an *executable* grammar
  (`grammar.ebnf`, run by `plainspec.py`) and from 40+ examples verified on every engine.
  `spec_fuzz.py` differentially tests the grammar against both hand‑written parsers on
  thousands of corrupted programs.
- **Documentation site** (`build_docs.py`) whose code examples are *executed at build time*;
  `pages.yml` deploys it with the playground to GitHub Pages.
- **Workbook** grew from 8 to 29 lessons in 6 units; every lesson ships a reference solution
  that its own checker must accept (`test_lessons.js`).
- **Accessibility pass**: an axe‑core audit drove WCAG AA contrast, labels, landmarks, real
  tab semantics, a modal dialog with focus management, live regions, and keyboard support.
  Zero violations across 8 UI states; locked in by `test_a11y.py`.
- **Language server**: go‑to‑definition, document symbols, autocomplete, richer hover.
- **Numbers are 64‑bit floats in every engine**; results too big for a float, and text past
  ten million characters, are friendly errors instead of crashes.
- **Fixed** (all found by fuzzing or the spec, each with a regression test): an `if` on the line
  after `otherwise` was parsed as `otherwise if`; `round` and number formatting differed between
  engines; `power of 0 and -1` crashed; `"{1 2}"` silently dropped the `2`; a function without
  `return` used as a value printed `nothing` on the VM; `replace ""` disagreed between engines
  and could exhaust memory; the differential fuzzer's own generator emitted invalid programs
  99% of the time (it now refuses to run in that state).

## [0.4.0] — 2026‑09‑23  ·  Real tooling  (`1b8a740`)

- **Language Server** (`plainlsp.py`): live diagnostics and hover over real LSP stdio framing.
- **VS Code extension** (`vscode-extension/`): syntax highlighting + the language server.
- **Code formatter** (`plainfmt.py`): idempotent, output‑preserving.
- **Differential fuzzers** and CI running every suite on each push.

## [0.3.0] — 2026‑09‑23  ·  A real compiler  (`931e976`)

- **WebAssembly backend** (`plainwasm.py`): a hand‑written `.wasm` encoder — no external
  tools — for the numeric core, run under Node and differentially fuzzed against the interpreter.
- Earlier in this phase (2026‑06‑25 → 2026‑07‑13): optimizer passes (constant folding,
  dead‑code elimination, peephole), gradual type checker, source maps and a VM tracer,
  portable bytecode, and parser error recovery.

## [0.2.0] — 2026‑07‑20  ·  A real language  (`922b5b1`)

- Records, `stop`/`skip`, first‑class functions, `map`/`filter`/`reduce`, pattern matching
  (`match`), a text library, a numbers‑and‑lists toolbox, more math, and multi‑file programs
  (`import`) — each cross‑validated across the engines.
- Fixed a nested‑`count` codegen bug found by the first differential fuzzer (2026‑07‑14).

## [0.1.0] — 2026‑06‑14  ·  Foundations

- Tree‑walking interpreter and REPL, the JavaScript engine and PlainLang→JavaScript
  transpiler, the bytecode VM, caret diagnostics with "did you mean?", a static analyzer,
  and the web playground with turtle graphics and a time‑travel debugger.
