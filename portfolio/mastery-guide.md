# PlainLang — Mastery Guide

The point of this doc: make the project **genuinely, defensibly yours.** If you can answer
everything here out loud and do the exercises without help, then in an interview or a
maker-portfolio review you can stand behind every line — which is exactly when this project
becomes a real asset instead of a risk.

Work through it in order. For each question, **say the answer out loud** (or write it) before
checking the note. The answer notes are deliberately short — they're prompts, not scripts.

---

## The 60-second architecture (be able to draw this)

```
source text
   │  tokenizer        (plainlang.py / plainlang.js: tokenize)
   ▼
tokens  [kind, value, line, col, length]
   │  parser           (recursive descent, operator precedence)
   ▼
syntax tree (AST)      nested tuples/arrays like ("if", branches, else)
   │
   ├──► tree-walking interpreter   (plainlang.py — the reference)
   ├──► bytecode compiler → stack VM   (plainvm.py)
   ├──► JavaScript transpiler      (plainlang.js compile())
   └──► static analyzer            (plaincheck.py — runs before execution)
```

Three things to be able to say in one sentence each:
- **Why three backends?** One simple reference (tree-walker), one that shows real
  execution (the VM), one that proves it's "real code" (transpiler) — all from one parser.
- **Why do they agree?** `test_vm.py` runs programs through the tree-walker *and* the VM and
  asserts identical output. Two independent implementations agreeing = strong correctness.
- **What's the teaching angle?** Beginner-grade error messages + a time-travel debugger.

---

## Tier 1 — Foundations (you must nail these)

1. **What is a token? What does the tokenizer add besides the word itself?**
   *Note: smallest meaningful piece (word/number/string/symbol). It also records line, column,
   and length — so errors can underline the exact text with a caret.*

2. **What is the AST and why not just run the text directly?**
   *Note: a tree representing structure. Running text directly can't handle nesting/precedence;
   the tree makes `(2 plus 3) multiplied by 4` unambiguous.*

3. **How does the parser know `multiplied by` binds tighter than `plus`?**
   *Note: precedence is encoded by the call chain — `arith()` calls `term()` calls `factor()`;
   lower-precedence operators sit higher in the tree.*

4. **Walk through what happens to `set x to 2 plus 3` end to end.**
   *Note: tokens → parse to ("set","x",("binop","+",2,3)) → interpreter evals binop=5 → stores x.*

## Tier 2 — The interpreter & scoping

5. **How are variables stored? What happens on an undefined variable?**
   *Note: an `Environment` with a `vars` dict and a parent link. `get` walks the chain; if not
   found it raises an error and offers a "did you mean?" from the names in scope.*

6. **How do functions see variables? Why can a function read a global but its locals don't leak out?**
   *Note: a called function gets a new Environment whose parent is the *globals* (not the caller).
   So it can read globals but its own locals die when it returns.*

7. **How is `return` implemented in a tree-walker, and why an exception?**
   *Note: `ReturnSignal` exception unwinds out of nested blocks/loops back to the function call.
   `stop`/`skip` use the same trick (`BreakSignal`/`ContinueSignal`), caught by loops.*

## Tier 3 — The bytecode VM (the impressive part — know it cold)

8. **What's on the stack? Trace `say 2 plus 3` as bytecode.**
   *Note: `CONST 2; CONST 3; ADD; PRINT`. ADD pops two, pushes the sum; PRINT pops and outputs.*

9. **How does a function call work in the VM (frames)?**
   *Note: CALL pops args, pushes a new frame (its own locals + saved return address/ip); RETURN
   pops the frame and pushes the return value back for the caller.*

10. **Explain the `count` loop lowering and *why* the test is `(i - stop) * step <= 0`.**
    *Note: one comparison that works both directions — ascending step=+1 gives `i<=stop`;
    descending step=−1 flips the sign to `i>=stop`. Avoids branching on direction.*

11. **How do `stop`/`skip` compile, and how do nested loops get the right target?**
    *Note: they emit JUMPs whose targets aren't known yet → **backpatching**. The compiler keeps a
    stack of loops; `stop` jumps are patched to the loop end, `skip` jumps to the advance step,
    after the body is compiled.*

12. **Why is the VM faster than the tree-walker, and why only ~1.9×?**
    *Note: linear bytecode + a flat dispatch loop beats re-walking the tree and Python method calls
    per node. Only ~2× because both run in Python; a native VM would be far faster.*

## Tier 4 — Diagnostics & analysis

13. **How does "did you mean?" work? Why sort the candidates?**
    *Note: Levenshtein edit distance to each known name, pick the closest under a threshold.
    Sorting makes ties deterministic so both engines produce identical messages.*

14. **What does the static analyzer catch that the runtime can't, and why report many at once?**
    *Note: undefined/unused vars, wrong arity, unreachable code, function-used-as-value — before
    running, all in one pass, so a beginner fixes everything at once instead of one-at-a-time.*

15. **Why must clean programs never be flagged?**
    *Note: a linter that cries wolf gets ignored; precision matters more than recall for teaching.*

---

## Prove it — modify the language yourself (no help)

Do these solo. Each should end with all tests green (`python test_*.py`, `node test_js.js`).

- **Easy:** add a built-in `minimum of LIST` (and `maximum of`). Mirror how `length of` is wired
  through the tokenizer keyword set, the parser's builtin branch, and each engine's `builtin`.
  Add a test to every suite.
- **Medium:** add a comparison phrase `is between A and B`. Touches the parser's comparison
  operator and both interpreters/VM.
- **Hard:** add a `times` loop variant or a new turtle command, end to end, and update the
  cross-validation test so the VM and tree-walker still agree.

If you can do the Easy one start-to-finish without me, you understand the spine of the whole
project. If you can do the Hard one, you can honestly say you built and extended a language.

---

## Interview "gotchas" to rehearse

- "Show me a bug you hit and how you found it." → the `count` overshoot (`i` ended at 5 not 4),
  caught by the cross-validation test; or the `and` ambiguity in function arguments.
- "What would you do differently?" → have a real answer (e.g., spans on every AST node, not just
  statements; a single shared engine instead of mirrored ones).
- "What part are you proudest of / found hardest?" → answer honestly and specifically.
- "How much did you use AI?" → **be honest.** "I used an AI assistant to move fast, and I made
  sure I understood every piece — ask me about any of it." Then back it up. That answer is fine;
  pretending you didn't is not.
