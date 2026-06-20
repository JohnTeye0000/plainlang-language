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
- [ ] More standard library: numbers/math helpers, list helpers, dates
- [ ] Modules / imports — multi-file programs
- [ ] Release **v0.2**

## Phase 2 — A real compiler  *(weeks)*

Deepen the back end into something a compilers course would recognize:

- [ ] An **optional/gradual type checker** with friendly type errors
- [ ] Optimizer passes: constant folding, peephole, dead-code elimination (show bytecode shrink)
- [ ] Parser **error recovery** → report many syntax errors at once
- [ ] **Source maps** linking bytecode back to lines
- [ ] A native backend: compile to **WebAssembly** (or C)
- [ ] Release **v0.3**

## Phase 3 — Real tooling  *(weeks)*

The artifacts that prove engineering maturity:

- [ ] A **Language Server (LSP)**: autocomplete, hover, go-to-definition, live diagnostics
- [ ] A **VS Code extension** wired to the language server
- [ ] A **code formatter** (`plainfmt`, like gofmt/prettier)
- [ ] **CI/CD** with GitHub Actions running every test suite on each push (green badge)
- [ ] A **fuzzer** / property-based tests for the parser and VM
- [ ] Release **v0.4**

## Phase 4 — Product & reach  *(weeks)*

Make it real for learners:

- [ ] Deploy the playground to a public URL (GitHub Pages)
- [ ] A documentation site (guide, reference, tutorials)
- [ ] Expand the Workbook into a full **interactive course** (dozens of lessons, multiple units)
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
