# PlainLang — Roadmap

**Vision:** the most approachable *first* programming language — English-like syntax,
world-class error messages, and a visual learning environment — backed by a real
compiler, virtual machine, and developer tooling, and validated with real beginners.

**Guiding principle:** *depth over line count.* This project is measured by what it can
do and who it helps — not by how many lines it contains. Every line should earn its place.

This is a multi-month effort. Each phase below is a body of work spanning weeks, tracked
with GitHub milestones and semantic-versioned releases.

---

## Phase 0 — Foundations  ✅ *(complete)*

The working core, already built and tested:

- Tree-walking interpreter, REPL, and English-like syntax
- A second engine in JavaScript + a **PlainLang → JavaScript transpiler**
- A **bytecode compiler + stack VM** (~1.9× faster), cross-validated against the interpreter
- **Professional diagnostics**: caret underlines + "did you mean?" suggestions
- A **static analyzer** (undefined/unused vars, arity, unreachable code)
- A self-contained **web IDE**: turtle graphics, time-travel debugger, lessons, sharing
- **114 automated tests** across four suites

---

## Phase 1 — A real language  *(weeks)*

Grow PlainLang from "teaching toy" to genuinely expressive:

- [x] Dictionaries / records (key–value data) — *done across all engines, cross-validated*
- [x] `break` and `continue` for loops — *as `stop` / `skip`, across all engines*
- [x] First-class functions: functions stored in variables, passed as arguments — *done across all engines, cross-validated*
- [x] Higher-order built-ins: `map`, `filter`, `reduce` expressed in PlainLang's style — *done across all engines, cross-validated; transpiles to native JS array methods*
- [x] Pattern matching (`match ... when ...`) — *done across all engines, cross-validated; transpiles to a JS switch*
- [x] A **text/string library**: split, join, trim, replace, position, contains — *done across all engines, cross-validated*
- [x] Numbers & lists toolbox: sum, average, smallest, largest, first, last, reverse, sorted, remainder — *done across all engines, cross-validated*
- [x] More math: `floor`, `ceiling`, `power`, `min`, `max` — cross-validated across all three engines; also fixed a real equality-semantics bug the fuzzer found along the way (`is equal to` between mismatched types incorrectly raised, and JS compared lists/records by reference instead of value)
- [ ] More standard library: dates
- [x] Modules / imports — `import "utils.plang"` pulls another file's function definitions into the current program (CLI-focused — the browser has no filesystem); resolves transitive and diamond imports, rejects cycles and non-library files, cross-validated between the tree-walker and the VM
- [ ] Release **v0.2**

## Phase 2 — A real compiler  *(weeks)*

Deepen the back end into something a compilers course would recognize:

- [x] A **gradual type checker** — infers variable types, flags operations that must fail (text minus a number, comparing incomparable types, `length of` a number, …); gradual, so unknowns are never flagged. *(Also fixed a real bug: `ask`-assigned variables weren't being tracked.)*
- [x] Optimizer passes: **constant folding** + **dead-code elimination** + **peephole** (jump threading & redundant-jump removal) — `--optimize` reports the shrink; cross-validated to preserve output.
- [x] Parser **error recovery** (panic-mode) → the static checker reports many syntax errors at once instead of stopping at the first
- [x] **Source maps** — disassembler shows the source line per instruction, and `--trace` watches the VM execute step by step (source line + operand stack)
- [x] **Portable bytecode** — `--emit` compiles a program to a distributable bytecode file; `--run-bc` runs it without the source or parser (round-trip verified)
- [x] A native backend: compile to **WebAssembly** — `plainwasm.py` emits real `.wasm` binaries with no external tools (numbers, booleans, text output, all control flow, functions incl. recursion); runs under Node and is differentially fuzzed against the interpreter. Lists/records/text variables still to come.
- [ ] Release **v0.3**

## Phase 3 — Real tooling  *(weeks)*

The artifacts that prove engineering maturity:

- [x] A **Language Server (LSP)**: `plainlsp.py` — live diagnostics, hover, go-to-definition, document symbols, and autocomplete, spoken over real LSP stdio framing so any LSP-capable editor can talk to it
- [x] A **VS Code extension** (`vscode-extension/`) wired to `plainlsp.py` over stdio — TextMate syntax highlighting, live diagnostics, and hover, no PlainLang-specific logic in the client itself (not yet published to the marketplace, but installable from source)
- [x] A **code formatter** (`plainfmt`, like gofmt/prettier) — re-indents from block structure, normalizes whitespace, tested for both idempotence and that it never changes a program's output; wired into CI
- [ ] **CI/CD** with GitHub Actions running every test suite on each push (green badge)
- [x] A **differential fuzzer** — random programs run through both engines and asserted to agree; already found and fixed a real codegen bug (nested `count` loops reusing a variable). Wired into CI.
- [ ] Release **v0.4**

## Phase 4 — Product & reach  *(weeks)*

Make it real for learners:

- [ ] Deploy the playground to a public URL (GitHub Pages) — *`pages.yml` workflow is ready; needs one click: Settings → Pages → Source: GitHub Actions*
- [x] A documentation site — `build_docs.py` generates a guide + reference where every example is *executed at build time* and its real output embedded; `test_docs.py` checks each example runs, both engines agree on it, and every keyword in the language is documented
- [x] Expand the Workbook into a full **interactive course** — 29 lessons in 6 units (first steps, decisions, loops, collections, functions, drawing); every lesson ships a reference solution that `test_lessons.js` proves passes its own checker while the starter does not
- [ ] Save/share projects; a small gallery of learner creations
- [ ] Accessibility pass; optional "teach in your language" (localized keywords)
- [ ] Release **v1.0**

## Phase 5 — Impact & evidence  *(ongoing)*

The part that actually differentiates a college application:

- [ ] Teach real beginners (siblings, a club, a library workshop); observe and record
- [ ] Gather data: completion rates, common errors, what the diagnostics fixed
- [ ] Write up the findings — a short paper/blog on English-like syntax and the
      time-travel debugger as learning aids
- [ ] Open-source it well (README, CONTRIBUTING, issues) and invite contributors

## Phase 6 — Stretch / research

- [ ] **Self-hosting**: write part of PlainLang's tooling *in* PlainLang
- [ ] A breakpoint debugger with a real debug protocol
- [ ] A concurrency model
- [ ] Formal semantics / a small specification document

---

## How progress is tracked

- **Milestones & issues** on GitHub, one milestone per phase.
- **Semantic versioning** (`v0.2`, `v0.3`, …) with a `CHANGELOG.md`.
- **Tests gate everything** — no feature ships without coverage, and the two engines
  must always agree.
- **Honest history** — commits land on the real day the work happens.
