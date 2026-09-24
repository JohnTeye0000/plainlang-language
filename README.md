# PlainLang

[![CI](https://github.com/JohnTeye0000/plainlang-language/actions/workflows/ci.yml/badge.svg)](https://github.com/JohnTeye0000/plainlang-language/actions/workflows/ci.yml)
&nbsp;·&nbsp; 824 checks + differential fuzzing &nbsp;·&nbsp; 4 execution back ends

**A programming language written to be read aloud — and a playground built to teach a first coder.**

```
set scores to list of 90, 75, 88, 95, 60
set total to 0

for each s in scores
    set total to total plus s
end

say "Average: " plus (total divided by length of scores)
```

Most first languages ask a beginner to absorb two hard things at once: how a computer
*thinks*, and a wall of unfamiliar punctuation (`{ } ; => != &&`). PlainLang removes the
second problem so the learner can focus on the first. The code reads like English, the
error messages read like a patient teacher, and the playground lets you *watch* a program
run one step at a time.

---

## What's in here

| File | What it is |
|------|-----------|
| **`playground.html`** | A self-contained web IDE — editor, live console, turtle-graphics canvas, a variable inspector, a **time-travel debugger**, a built-in **lessons workbook**, and a **"see it as JavaScript"** view. Open it in any browser. |
| **`plainlang.js`** | The language engine in JavaScript: tokenizer → parser → interpreter, **plus a compiler that translates PlainLang to readable JavaScript**. |
| **`plainlang.py`** | A second, independent implementation: a tree-walking command-line interpreter and REPL. |
| **`plainvm.py`** | A **third** backend: a bytecode *compiler* and a stack-based *virtual machine*, with a disassembler. ~1.9× faster than the tree-walker. |
| **`plaincheck.py`** | A static analyzer + **gradual type checker** — a semantic pass that finds bugs *before* the program runs and reports many at once (undefined/unused variables, unknown functions, wrong arity, unreachable code, and type errors like text-minus-a-number). |
| **`test_plainlang.py`** | The reference test suite: language behaviour and error messages, including a regression test for every bug the fuzzers and the spec have found. |
| **`test_vm.py`** | **Cross-validation**: every program is run through both the tree-walker and the VM and must produce identical output — including the wording of every error. |
| **`test_diagnostics.py`** | A 14-case suite for the diagnostics: caret underlines and "did you mean?" suggestions. |
| **`test_check.py`** | Tests for the static analyzer and type checker (including its precision — clean code must not be flagged). |
| **`test_js.js`** | A Node suite for the JavaScript engine, transpiler, and diagnostics. |
| **`fuzz.py`** | A **differential fuzzer** — a type-aware generator emits random programs across the whole language and checks the tree-walker and VM agree on every one. |
| **`test_fuzz.py`** | A seeded, reproducible fuzzing run (1,200 random programs) wired into CI. |
| **`plainfmt.py`** | A **code formatter** — re-indents a program from its block structure and normalizes whitespace, like gofmt/prettier. `--write` formats in place, `--check` fails CI on unformatted files. |
| **`test_fmt.py`** | Tests the formatter for the two properties that matter: it never changes what a program does, and formatting an already-formatted program is a no-op. |
| **`test_imports.py`** | Tests multi-file programs (`import`): transitive and diamond imports, circular-import and non-library-file rejection, cross-validated between the tree-walker and the VM. |
| **`plainlsp.py`** | A **Language Server** — live diagnostics (reusing `plaincheck.py`) and hover, spoken over real LSP stdio framing so any LSP-capable editor can connect. |
| **`test_lsp.py`** | Tests the LSP message protocol directly (no editor needed) plus one real subprocess test that speaks actual stdio framing to the server. |
| **`plainwasm.py`** | A **WebAssembly backend** — compiles PlainLang to a real `.wasm` binary (hand-written encoder: LEB128, sections, opcodes, structured control flow). Runs in any WASM host. |
| **`wasm_runner.js`** | The small host that supplies a compiled module's imports (print, fail, pow) and runs it under Node. |
| **`fuzz_wasm.py`** / **`test_wasm.py`** | A differential fuzzer and test suite that run every program through the interpreter *and* real WebAssembly and demand identical output. |
| **`vscode-extension/`** | A VS Code extension: syntax highlighting + `plainlsp.py` wired in as the language server. |
| **`lessons.js`** / **`test_lessons.js`** | The Workbook: a 29-lesson, 6-unit interactive course. Every lesson has a reference solution, and the tests prove each solution passes its own checker and each untouched starter does not. |
| **`build_docs.py`** / **`docs_content.py`** / **`test_docs.py`** | The documentation site. Every example is *run* when the site is built and its real output printed beneath it; tests check that each example works, that the Python and JS engines agree, and that every keyword is documented. `pages.yml` deploys it with the playground to GitHub Pages. |
| **`test_a11y.py`** | Accessibility regression tests: WCAG AA contrast for every palette colour (light and dark), plus the playground's landmarks, labels, tab/dialog semantics and keyboard support. The original fixes came from a real axe-core audit. |
| **`SPEC.md`** / **`grammar.ebnf`** | The **language specification**, generated from an executable grammar and from examples that are run on every engine. |
| **`fuzz_js.py`** / **`test_fuzz_js.py`** | A differential fuzzer for the JavaScript engine (the browser's, with its own parser): the same random programs run on it and on the Python interpreter and must agree. |
| **`plainspec.py`** / **`spec_fuzz.py`** / **`test_spec.py`** | The grammar as a recognizer, a differential tester that pits it against both hand-written parsers on thousands of corrupted programs, and the test suite that checks every rule of the spec. |
| **`plain.py`** | **One command for everything**: `plain run`, `repl`, `check`, `fmt`, `vm`, `wasm`, `spec`, `lsp`, `docs`. Each runs the tool of the same name, so it can't drift. |
| **`run_tests.py`** / **`test_meta.py`** | Runs every suite CI runs (`--quick` skips the slow randomized ones); the meta-test fails if a suite isn't wired into both CI and the runner. |
| **`CONTRIBUTING.md`** / **`CHANGELOG.md`** | How the four engines fit together and the checklist for adding a feature; the release history. |
| **`demo.plang`** | A guided tour program that exercises every feature. |
| **`examples/shapes/`** | A small multi-file program (`main.plang` imports `geometry.plang`) showing `import` in practice. |

---

## Three things that make it more than a toy

### 1. Error messages that teach
A beginner language lives or dies by what happens when you get it *wrong*. Errors point
to the exact source text with a caret, and an edit-distance check offers a way forward —
Rust/Elm-grade diagnostics, aimed at someone on their first day:

```
  Oops! Something went wrong on line 3:
    I haven't heard of a variable called 'scor' yet.

    3 | say scor plus total
            ^^^^
  Hint: Did you mean 'score'?
```

The same machinery catches mistyped functions and even mistyped keywords
(`saay "hi"` → *Did you mean 'say'?*). Both Python back ends and the JavaScript engine
build these through shared helpers, so the message is identical everywhere.

### 2. A time-travel debugger
Running a program records a snapshot before every step. You can then scrub a slider to
move forward *and backward* through execution — watching each variable change and the
turtle's drawing build up, with the current line highlighted. Abstract control flow
becomes something you can see.

### 3. It compiles to real JavaScript
PlainLang isn't just interpreted — the same syntax tree is walked by a compiler that emits
clean, idiomatic JavaScript. A learner flips to the **As JS** tab and sees their English
turn into the code a professional would write:

```
define factorial with n          function factorial(n) {
    if n is at most 1 then          if ((n <= 1)) {
        return 1            ─►          return 1;
    end                               }
    return n multiplied by            return (n * factorial((n - 1)));
        factorial with (n minus 1)  }
end
```

---

## The language in one screen

```
# Variables and text
set name to "Ada"
say "Hi, " plus name

# Math:  plus  minus  multiplied by  divided by
say (2 plus 3) multiplied by 4

# Decisions
if age is at least 18 then ... otherwise if ... then ... otherwise ... end

# Pattern matching
match grade
    when "A" then say "Excellent!"
    when "B" then say "Good job."
    otherwise   say "Let's review."
end

# Comparisons:  is equal to · is greater than · is at least · is not equal to
# Booleans:     and · or · not

# Loops  (use 'stop' to leave early, 'skip' to jump to the next pass)
repeat 3 times ... end
count i from 1 to 5 ... end
while x is greater than 0 ... end
for each item in things ... end

# Lists
set fruits to list of "apple", "banana"
add "cherry" to fruits
say item 2 of fruits
say length of fruits

# Records (dictionaries) — named fields
set player to record with "name" as "Ada", "score" as 0
set item "score" of player to 150
say item "name" of player
for each field in keys of player
    say field plus " = " plus item field of player
end

# Functions (with recursion)
define double with n
    return n multiplied by 2
end
say double with 21

# Functions are values — store them, pass them around
set op to double
say op with 21
define apply_twice with f and x
    return f with (f with x)
end
say apply_twice with double and 5

# Higher-order: map / filter / reduce
define combine with a and b
    return a plus b
end
say map double over (list of 1, 2, 3)              # [2, 4, 6]
say reduce combine over (list of 1, 2, 3, 4) from 0   # 10

# Built-ins:  length of · uppercase of · round of · square root of · random between 1 and 6
# More math:  floor of · ceiling of · power of X and Y · min of X and Y · max of X and Y

# Multi-file programs (running from the command line)
import "geometry.plang"                 # pulls in another file's functions
say area_of_circle with 4               # a library file may only define functions

# Numbers & lists toolbox
say sum of (list of 5, 2, 8)       # 15
say average of (list of 2, 4, 6)   # 4
say smallest of (list of 5, 2, 8)  # 2
say sorted of (list of 3, 1, 2)    # [1, 2, 3]
say remainder of 17 and 5          # 2

# Text toolbox
say split "a,b,c" by ","          # [a, b, c]
say join (list of "a", "b") by "-"  # a-b
say trim of "  hi  "              # hi
say replace "o" by "0" in "foo"   # f00
say position of "b" in "abc"      # 2
say "hello" contains "ell"        # true

# Turtle graphics
pen color to "#38bdf8"
repeat 4 times
    move forward 120
    turn right 90
end
```

---

## Running it

**The playground** (recommended):
```bash
# from this folder
python -m http.server 8753
# then open http://localhost:8753/playground.html
```
Or just open `playground.html` directly in a browser.

**The command line:**
```bash
python plain.py run demo.plang     # run a program
python plain.py repl               # interactive prompt
python plain.py check demo.plang   # find mistakes before running
python plain.py fmt --write demo.plang
python plain.py wasm demo.plang    # compile to WebAssembly
python plain.py help               # everything else
```
Each command is the tool of the same name (`plainlang.py`, `plaincheck.py`, …) run exactly as if you'd typed it, so `python plainlang.py demo.plang` still works too.

**The tests:**
```bash
python run_tests.py            # every suite CI runs
python run_tests.py --quick    # skip the slow randomized ones
```

---

## How it works

A classic front end feeding **three** independent back ends:

1. **Tokenizer** — turns source text into a stream of words, numbers, strings, and symbols, tracking line numbers for error reporting.
2. **Parser** — a recursive-descent parser with correct operator precedence builds a syntax tree. Keywords like `plus`, `is greater than`, and `multiplied by` stand in for symbols.
3. **Back ends** — the same syntax tree is consumed by:
   - a **tree-walking interpreter** (the simple reference);
   - a **bytecode compiler + stack VM** (`plainvm.py`) — lowers the tree to flat bytecode executed on an operand stack;
   - a **JavaScript transpiler** (`plainlang.js`) — emits readable JS;
   - and, in the browser, an **execution tracer** that powers the time-travel debugger.

### Three back ends, one truth

The tree-walker and the bytecode VM are completely separate implementations. They are
held to the same behaviour by `test_vm.py`, which runs a battery of programs through both
and asserts the output is identical — *including* the wording of every error message.
Two implementations that agree on everything is strong evidence both are correct.

On top of the hand-written cases, `fuzz.py` does **differential fuzzing** — a type-aware
generator emits random programs across the *whole* language (numbers, text, lists,
booleans, `if`/`count`/`match`, function calls, `map`/`filter`/`reduce`), and every one is
checked for identical output on both engines. This has found real bugs twice:

1. Nested `count` loops reusing the same variable name diverged — the VM used the loop
   variable itself as the iteration counter, so an inner loop corrupted the outer one. Fixed
   by driving iteration with a hidden counter.
2. An error occurring in the same expression as, but *after*, a function call was blamed on
   a line inside the function body instead of the real call site — the interpreters weren't
   restoring the "current line" when a call returned. Fixed in all three engines. The same
   sweep also caught `round`/`absolute`/`sqrt`/`random`/`remainder` calling straight into
   `int()`/`round()` without checking their argument was a number first, so bad input raised
   a raw crash instead of a friendly error — now they all validate first.
3. Adding `power`/`min`/`max` surfaced a real semantics bug in `is equal to`/`is not equal
   to`: the tree-walker built a dict of all six comparison results at once to pick the right
   one, so an *ordering* comparison between incompatible types (`5 > "five"`) threw before
   the requested `==` was ever read — meaning equality checks between mismatched types
   raised instead of just being `false`, and the JS engine additionally compared lists and
   records by reference instead of by value. Fixed everywhere: equality is now always
   well-defined across types (like Python's own `==`), only ordering requires matching
   operand shapes, and list/record equality is structural in all three engines.

4. A *fourth* engine turned up four more. `plainwasm.py` (below) compiles to real WebAssembly,
   so fuzzing it against the interpreter meant comparing more independent implementations
   than ever — and they immediately disagreed: an `if` on the line after `otherwise` was
   silently parsed as `otherwise if` (newlines were invisible to the parser, so a nested `if`
   swallowed an `end`); `round` gave `2` for `2.5` in Python but `3` in JavaScript; Python printed
   `6.64712e-05` where JavaScript printed `0.0000664712`; and `power of 0 and -1` crashed the
   interpreter with a raw exception. Each is fixed once, in every engine, with a regression test.

5. The spec and a stricter fuzzer found four more. The executable specification turned up a
   parser leniency (`"{1 2}"` silently dropped the `2`) and a VM/interpreter split (a function that
   never `return`s, used as a value, printed `nothing` on the VM but raised the right error
   everywhere else). And the fuzzer itself was audited: a bug in *my generator* meant 99% of its
   programs were syntactically invalid, so the engines "agreed" on the syntax error and the run
   proved little — `fuzz.py` now fails loudly unless at least 95% of its programs are valid. Once the
   programs were real, deeper bugs surfaced: an unbounded-integer crash at 4,300 digits (numbers are
   now 64-bit floats in every engine, with a friendly "too big" error), and text that could grow
   until the machine ran out of memory (text now has a ceiling too, and replacing empty text is an
   error — Python and JavaScript disagreed about what it even meant).

Every one of these is fixed once, in every engine, with a regression test. After the fixes, 30,000
valid random programs agree between the interpreter and the VM, and 10,000 between the interpreter
and real WebAssembly — with no magnitude exemptions.

### Seeing the bytecode

```
$ python plainvm.py --dis program.plang       # disassemble to bytecode
$ python plainvm.py --compare program.plang   # prove both back ends agree
$ python plainvm.py --bench                    # VM vs tree-walker timing
$ python plainvm.py --optimize program.plang  # how much the optimizer removes
$ python plainvm.py --trace program.plang     # watch the VM execute, step by step
$ python plainvm.py --emit program.plang      # compile to a portable bytecode file
$ python plainvm.py --run-bc program.plbc     # run compiled bytecode (no source, no parser)
```

Like `.pyc`/`.class`, PlainLang can compile a program **ahead of time** to a portable
bytecode file and run it later without the source or the parser — the round-trip is
verified to produce identical output to a direct run.

`--trace` prints every bytecode step with its **source line** and the **operand stack**, so
you can watch the stack machine run — and see the optimizer's work, since `set x to 2 plus 3`
already traces as `CONST 5`. The disassembler carries the same source-line column.

The compiler runs an **optimizer** before emitting bytecode — three passes:
*constant folding* (any expression whose operands are all literals is pre-computed, so
`say (2 plus 3) multiplied by 4` compiles straight to `CONST 20; PRINT`), *dead-code
elimination* (branches that can never run, and statements after a `return`/`stop`/`skip`,
are dropped), and a *peephole* pass (redundant jumps are threaded and removed). It only
optimizes transformations it can prove are valid — `5 divided by 0` and `"a" minus 1` are
left for the runtime to report — and the cross-validation suite proves the optimizer never
changes a program's output.

A `count` loop, for example, lowers to primitive jumps and a single direction-agnostic
loop test `(i - stop) * step <= 0`:

```
   4  CONST            3
   5  STORE            $stop1
   ...
  15  LOAD             i
  16  LOAD             $stop1
  17  SUB
  18  LOAD             $step2
  19  MUL
  20  CONST            0
  21  LE
  22  JUMP_IF_FALSE    -> 32
  ...
  31  JUMP             -> 15
```

The VM's dispatch loop inlines the hottest opcodes (variable access, arithmetic, calls)
and runs roughly **1.9× faster** than the tree-walker on recursive workloads.

### Catching bugs before you run

`plaincheck.py` is a separate **semantic-analysis phase**. It walks the tree, tracks a
chain of scopes, and reports problems *before* execution — and, unlike the runtime, it
reports them *all at once*, each with a caret:

```
$ python plaincheck.py program.plang

  error  ·  line 8
    'double' expects 1 value(s), but you gave 2.

    8 | say double with 3 and 4
            ^^^^^^

  warning  ·  line 11
    This line can never run — it comes after a 'return'.
  ...
  6 problem(s):  3 error(s), 3 warning(s).
```

It is tuned for **precision** — correct programs are never flagged — because a teaching
tool that cries wolf is worse than none.

When a program has several *syntax* errors, the checker uses **panic-mode error recovery**
to keep going past each one and report them all at once, instead of stopping at the first.

The same pass does **gradual type checking**: it infers a type for each variable (from
literals and consistent assignments) and reports operations that must fail, while leaving
anything it can't determine as *unknown* and never complaining about it. So
`set age to "twelve"` followed by `if age is at least 18` is caught before running —
*"I can't compare some text with a number"* — but a function parameter whose type isn't
known is never second-guessed.

### Keeping code consistent

`plainfmt.py` re-indents a program from its block structure and normalizes whitespace —
one canonical layout, so every file in a project looks the same no matter who wrote it:

```
$ python plainfmt.py program.plang            # print the formatted result
$ python plainfmt.py --write program.plang    # format the file in place
$ python plainfmt.py --check program.plang    # exit 1 if it isn't formatted (for CI)
```

It's held to the two properties that matter for a formatter: it never changes what a
program *does* (every program in `test_fmt.py` is run before and after formatting and
must produce identical output), and formatting an already-formatted file is a no-op
(idempotence). `demo.plang` was written by hand and happens to already match the
formatter's output byte-for-byte.

### Compiling to WebAssembly

`plainwasm.py` compiles PlainLang to a real **`.wasm` binary** — not text, not a wrapper: it
writes the module bytes itself (LEB128 integers, type/import/function/memory/global/export/code/
data sections, opcodes, and structured control flow with `br`-depth bookkeeping), so there's no
assembler, LLVM, or toolchain in the loop. The output runs in any WebAssembly host.

```
$ python plainwasm.py program.plang              # compile, then run under Node
$ python plainwasm.py program.plang -o out.wasm  # just emit the binary
```

It covers a "systems core" of the language — numbers (f64) and true/false, all arithmetic and
comparisons, `if`/`match`/`repeat`/`while`/`count`/`stop`/`skip`, functions with recursion, the
math built-ins, and `say` with text — and refuses anything else (lists, records, text
variables) with a plain explanation instead of miscompiling. `count` uses the same hidden-counter
design the VM adopted after the nested-loop bug; `round`, `remainder`, and `power` are emitted to
match the interpreter's exact semantics (WASM's own `f64.nearest` rounds ties to even, so `round`
is built from `floor`); divide-by-zero and friends call a host `fail` instead of producing `inf`.

It's held to the same standard as every other engine: `fuzz_wasm.py` generates random programs
and checks the interpreter and **real WebAssembly** agree on every one — output *and* the point
where a runtime error stops the program. Known, documented limit: the WASM backend uses doubles,
and numbers are 64-bit floats in *every* engine, so the same program prints the same digits everywhere.

### Editor tooling

`plainlsp.py` is a real **Language Server** — the same protocol pyright, gopls, and
rust-analyzer speak. Point any LSP-capable editor at `python plainlsp.py` and it gets
live diagnostics as you type (undefined variables, wrong argument counts, type errors,
unreachable code, syntax errors — the exact same checks as `plaincheck.py`, with the same
"did you mean?" suggestions) and hover documentation for keywords. The transport (stdio,
`Content-Length`-framed JSON-RPC) is a thin shell around a pure `LSPServer.handle()` — one
dict in, a list of response/notification dicts out — so the whole protocol is tested
without spawning an editor or even a subprocess, plus one real subprocess test proving the
actual stdio framing works.

`vscode-extension/` is a real VS Code extension wired to it — `syntaxes/plainlang.tmLanguage.json`
gives `.plang` files syntax highlighting (keywords, strings with `{interpolation}`, numbers,
comments), and `src/extension.js` is a thin client that starts `python plainlsp.py` and speaks
LSP to it over stdio via `vscode-languageclient`. The client has no PlainLang-specific logic of
its own — every diagnostic comes from the same `plaincheck.py` the CLI uses. See its own
[README](vscode-extension/README.md) for installing it from source.

---

## Design notes & trade-offs

- **Lists are 1-indexed** (`item 1 of list`) — beginners count from one, so the language does too.
- **`plus` concatenates** when either side is text, so `"score: " plus 42` just works.
- **Function arguments are separated by `and`**, which is also the boolean operator — so a boolean *inside* an argument needs parentheses: `f with (a and b)`. (This ambiguity was caught by the test suite.)
- **The compiler favours readability over byte-for-byte fidelity** — e.g. generated JavaScript shows full floating-point precision rather than PlainLang's rounded display. It's a teaching window into "what real code looks like," not a second runtime.
