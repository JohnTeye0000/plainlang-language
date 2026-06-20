# PlainLang

[![CI](https://github.com/JohnTeye0000/plainlang-language/actions/workflows/ci.yml/badge.svg)](https://github.com/JohnTeye0000/plainlang-language/actions/workflows/ci.yml)
&nbsp;·&nbsp; 218 passing tests &nbsp;·&nbsp; 3 execution back ends

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
| **`plaincheck.py`** | A static analyzer — a semantic pass that finds bugs *before* the program runs and reports many at once (undefined/unused variables, unknown functions, wrong arity, unreachable code). |
| **`test_plainlang.py`** | A 48-case test suite covering the language and its error messages. |
| **`test_vm.py`** | A 34-case **cross-validation** suite: every program is run through both the tree-walker and the VM and asserted to produce identical output. |
| **`test_diagnostics.py`** | A 14-case suite for the diagnostics: caret underlines and "did you mean?" suggestions. |
| **`test_check.py`** | An 18-case suite for the static analyzer (and its precision — clean code must not be flagged). |
| **`test_js.js`** | A 19-case Node suite for the JavaScript engine, transpiler, and diagnostics. |
| **`demo.plang`** | A guided tour program that exercises every feature. |

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
python plainlang.py demo.plang     # run a program
python plainlang.py                # interactive REPL
python plainlang.py --help         # full syntax reference
```

**The tests:**
```bash
python test_plainlang.py
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

### Seeing the bytecode

```
$ python plainvm.py --dis program.plang     # disassemble to bytecode
$ python plainvm.py --compare program.plang  # prove both back ends agree
$ python plainvm.py --bench                  # VM vs tree-walker timing
```

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

---

## Design notes & trade-offs

- **Lists are 1-indexed** (`item 1 of list`) — beginners count from one, so the language does too.
- **`plus` concatenates** when either side is text, so `"score: " plus 42` just works.
- **Function arguments are separated by `and`**, which is also the boolean operator — so a boolean *inside* an argument needs parentheses: `f with (a and b)`. (This ambiguity was caught by the test suite.)
- **The compiler favours readability over byte-for-byte fidelity** — e.g. generated JavaScript shows full floating-point precision rather than PlainLang's rounded display. It's a teaching window into "what real code looks like," not a second runtime.
