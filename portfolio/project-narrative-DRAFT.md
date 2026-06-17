# PlainLang — Project Narrative (DRAFT / scaffold)

> **READ THIS FIRST.**
> This is a *scaffold*, not a finished essay. The technical facts here are true and yours to
> use. But everywhere you see `[brackets]`, only **you** can supply the truth — your reasons,
> your moments, your voice. **Do not submit this as-is.** Most colleges require your essays to
> be your own words; an AI-drafted essay passed off as yours is an integrity violation and it
> reads as generic. Use this to *remember the structure and the facts*, then rewrite it from
> scratch in your own voice. The strongest version sounds like you talking, not like this.

---

## Version A — short "activity description" (~150 words, for an application activities list)

> I designed and built **PlainLang**, a programming language whose code reads like English,
> to help complete beginners learn to code. It has three execution engines (a tree-walking
> interpreter, a bytecode compiler + virtual machine, and a JavaScript transpiler), a static
> analyzer, and a browser IDE with turtle graphics and a "time-travel" debugger that lets you
> scrub backward and forward through a program's execution. I focused especially on
> *teaching-grade error messages* that underline the mistake and suggest a fix. The project is
> ~[N] lines across [N] files, covered by [169]+ automated tests run on every commit via CI.
> [1–2 sentences: WHO you tested it with and the result — fill from your user testing.]

*(Trim to the word limit the application gives you. Replace the bracketed bits with real numbers.)*

---

## Version B — the longer story (for an essay, supplement, or portfolio write-up)

### The hook — start with a concrete moment, not a thesis
`[Open with a real, specific scene. Examples to jog your memory — pick the TRUE one:]`
- `[the moment you watched someone bounce off a wall of { } ; and give up, and thought "the punctuation is the problem, not them"]`
- `[your own first experience learning to code and what confused you]`
- `[someone you wanted to teach — a sibling, a friend — and couldn't]`

Whatever it is, make it a 2–3 sentence picture, not an abstract claim.

### The problem you decided to attack
Beginners have to learn two hard things at once: how a computer *thinks*, and a wall of
unfamiliar symbols. `[In your words: why you found that worth fixing.]` I wanted a first
language where the code says what it does, the errors teach instead of scold, and you can
*see* a program run.

### What you built
PlainLang reads like English — `set score to 90`, `if score is at least 50 then ... end`,
`for each item in things`. Under that simple surface I built a real toolchain:
- a tokenizer and a recursive-descent **parser** with proper operator precedence;
- **three independent backends** off that one parser — a tree-walking interpreter, a
  **bytecode compiler and stack virtual machine**, and a transpiler that turns the English
  into readable JavaScript so a learner can see "real code";
- a **static analyzer** that catches mistakes before the program runs and reports them all
  at once;
- **error messages built for beginners** — they underline the exact mistake with a caret and
  suggest the fix (`'scor' — did you mean 'score'?`);
- a self-contained **web IDE** with syntax highlighting, turtle graphics, an auto-checked
  lesson workbook, and a **time-travel debugger** that records every step so you can scrub
  through a program and watch each variable change.

### The hardest part `[pick what was genuinely hardest FOR YOU as you learned it]`
`[Tell one real problem in detail. Strong candidates, with the facts:]`
- *Two engines that must agree.* I built the VM as a second, independent way to run the same
  language, then wrote tests that run every program through *both* and demand identical output.
  It paid off: the test caught a bug where my loops left the counter one step too high
  (`i` ended at 5 instead of 4). `[how it felt to find / fix it]`
- *Compiling loops.* `stop` and `skip` (break/continue) had to jump to places in the bytecode
  that don't exist yet when you compile them, so I had to learn **backpatching** — record the
  jumps and fix their targets once the loop is fully compiled. `[what clicked for you here]`

### What you learned `[the reflection — this is what admissions actually reads for]`
`[Be specific and honest. Not "I learned to code." More like: what you now understand about
how languages work / about designing for someone who isn't you / about testing as a safety net
/ about what you did when you were stuck. One genuine realization beats five clichés.]`

### Evidence it works `[fill ONLY from real user testing — do not invent]`
`[e.g., "I ran it with __ beginners. __ of them wrote a working program in one session, and
__ fixed their own errors using just the messages. The most common confusion was __, so I
changed __."]`

### What's next
`[Honest: where you'd take it — type checking, an editor plugin, deploying it for a class,
getting it in front of more learners. Whatever you actually intend.]`

---

## A few honesty checks before you use any of this
- Every sentence should be something **you could defend in an interview.** If you can't yet,
  go do the `mastery-guide.md` first.
- Numbers (`169 tests`, line counts, user results) must be **real**. Pull current ones; don't
  round up.
- If asked about AI assistance, say so plainly and show that you understand the work. That's
  a fine, normal answer in 2026. Hiding it is the only wrong move.
