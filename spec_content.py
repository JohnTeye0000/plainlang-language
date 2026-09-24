"""
The prose and executable examples of the PlainLang language specification (SPEC.md).

build_spec.py assembles SPEC.md from this file, grammar.ebnf and the tokenizer's
own keyword table. test_spec.py then runs every example below through the
tree-walking interpreter, the bytecode VM and the JavaScript engine, and requires
all three to produce exactly the `expect` output (or an error containing the
`error` text). A rule of the language is only written down here if it is checked.

Each rule is (statement, [examples]); an example is
    {"code": ..., "expect": [lines]}      or      {"code": ..., "error": "fragment"}
"""

INTRO = """\
# The PlainLang Language Specification

This document defines PlainLang precisely enough to write a new implementation
from it. It is **checked, not just written**:

* the grammar in §3 is [`grammar.ebnf`](grammar.ebnf) verbatim, and `plainspec.py`
  executes it — `test_spec.py` differentially tests it against both hand-written
  parsers (Python and JavaScript) on thousands of valid and deliberately corrupted
  programs;
* every rule in §4 comes with an example whose result is verified on the
  tree-walking interpreter, the bytecode VM and the JavaScript engine (and the
  numeric subset on the WebAssembly backend);
* `build_spec.py --check` fails if this file drifts from its sources.

Where the specification and an implementation ever disagreed while it was being
written, that was a bug, and it was fixed — the `otherwise`/`if` line rule, the
junk-inside-braces leniency, and the three number-formatting/rounding differences
between engines were all found this way.
"""

LEXICAL = """\
## 2. Lexical structure

A program is Unicode text. It is split into **tokens**; whitespace (spaces, tabs,
newlines) separates tokens and is otherwise meaningless — *with one exception*, the
`otherwise if` rule in §3.

| Token | Form |
|---|---|
| comment | `#` to the end of the line; ignored |
| number | digits, optionally `.` and more digits: `42`, `3.14`. There is no sign, no exponent: a negative number is written `minus 5` |
| text | `"` … `"`; no escape sequences, cannot contain `"`, may span lines |
| identifier | a letter or `_`, then letters, digits, `_`. Case-sensitive |
| keyword | one of the reserved words below, in any case (`Say` = `say`) |
| punctuation | `(` `)` `,` — anything else is an error |

**Reserved words.** A keyword can never be used as a variable or function name:

{keywords}

**Text interpolation.** Inside a text literal, `{{expression}}` is replaced by the
value of the expression, converted to text as `say` would. The braces must contain
exactly one complete expression. `{{{{` and `}}}}` stand for literal braces.
"""

# ── §4: semantics ─────────────────────────────────────────────────────────────
SEMANTICS = [
    {
        "title": "4.1 Values and output",
        "rules": [
            ("There are six kinds of value: **number**, **text**, **true/false**, **list**, **record** (an ordered "
             "map from text or number keys to values) and **function**. `say` prints a value on its own line.",
             [{"code": 'say 42\nsay "hi"\nsay true\nsay list of 1, 2\nsay record with "a" as 1', "expect": ["42", "hi", "true", "[1, 2]", "{a: 1}"]}]),
            ("A whole number prints with no decimal point; any other number is rounded to ten decimal places and "
             "**never printed in scientific notation**. Rounding of ties is *half away from zero*.",
             [{"code": 'say 4 multiplied by 0.5 plus 8\nsay 10 divided by 3\nsay 1 divided by 1000000\nsay 1 divided by 1000000000000',
               "expect": ["10", "3.3333333333", "0.000001", "0"]}]),
        ],
    },
    {
        "title": "4.2 Numbers",
        "rules": [
            ("Numbers are **64-bit floating point** (IEEE 754 doubles) in every implementation. A whole number "
             "beyond 2^53 prints as the exact digits of the nearest double, and a result too large for a double is "
             "an error, never `Infinity`.",
             [{"code": 'say power of 2 and 100\nsay 9007199254740993', "expect": ["1267650600228229401496703205376", "9007199254740992"]},
              {"code": 'say power of 10 and 400', "error": "too big"}]),
            ("`plus`, `minus`, `multiplied by`, `divided by` take numbers; `plus` also joins text (§4.4). "
             "Dividing by zero is an error. Unary `minus` negates.",
             [{"code": 'say 7 divided by 2\nsay minus 5 plus 8', "expect": ["3.5", "3"]},
              {"code": 'say 1 divided by 0', "error": "divide by zero"}]),
            ("`round of` rounds half **away from zero** (2.5 → 3, −2.5 → −3). `floor of` and `ceiling of` round "
             "toward −∞ and +∞. `remainder of A and B` is the **floored** remainder of the whole-number parts "
             "(its sign follows B); `B` may not be 0.",
             [{"code": 'say round of 2.5\nsay round of (minus 2.5)\nsay floor of (minus 3.2)\nsay ceiling of (minus 3.7)',
               "expect": ["3", "-3", "-4", "-3"]},
              {"code": 'say remainder of 17 and 5\nsay remainder of (minus 7) and 3\nsay remainder of 7 and (minus 3)',
               "expect": ["2", "2", "-2"]}]),
            ("`power of X and Y` is X^Y; `min of` / `max of` compare two numbers; `square root of X` needs X ≥ 0; "
             "`absolute of X` is |X|. Zero to a negative power, and a negative number to a fractional power, are errors.",
             [{"code": 'say power of 2 and 10\nsay min of 4 and 9\nsay max of 4 and 9\nsay square root of 144\nsay absolute of (minus 8)',
               "expect": ["1024", "4", "9", "12", "8"]},
              {"code": 'say power of 0 and (minus 1)', "error": "negative power"}]),
        ],
    },
    {
        "title": "4.3 Truth, comparison and logic",
        "rules": [
            ("`is equal to` and `is not equal to` are defined for **every** pair of values and never fail: values of "
             "different kinds are simply not equal; lists and records are equal when their contents are.",
             [{"code": 'say 16 is equal to "hi"\nsay 16 is not equal to "hi"\nset a to list of 1, 2\nset b to list of 1, 2\nsay a is equal to b',
               "expect": ["false", "true", "true"]}]),
            ("`is greater than`, `is less than`, `is at least`, `is at most` need two numbers or two texts "
             "(texts compare in dictionary order); anything else is an error. A bare `is` means `is equal to`.",
             [{"code": 'say 5 is greater than 3\nsay "apple" is less than "banana"\nsay 4 is 4', "expect": ["true", "true", "true"]},
              {"code": 'say 5 is greater than "five"', "error": "can't compare"}]),
            ("A condition may be any value: a number is true unless 0, text/list/record is true unless empty. "
             "`and` / `or` **short-circuit** — the right side is not evaluated when the left decides — and `not` negates.",
             [{"code": 'if 3 then\nsay "nonzero"\nend\nif "" then\nsay "no"\notherwise\nsay "empty text is false"\nend\nsay false and (1 divided by 0)\nsay true or (1 divided by 0)',
               "expect": ["nonzero", "empty text is false", "false", "true"]}]),
        ],
    },
    {
        "title": "4.4 Text",
        "rules": [
            ("`plus` with text on either side joins them, converting the other side as `say` would. "
             "`uppercase of`, `lowercase of`, `trim of`, `length of` work on text; `split TEXT by SEP` gives a list of "
             "pieces (`\"\"` splits into characters); `join LIST by SEP` reverses it; `replace OLD by NEW in TEXT` "
             "replaces every occurrence; `position of PART in TEXT` is 1-based, 0 when absent; `TEXT contains PART` tests.",
             [{"code": 'say "n = " plus 3 plus "!"\nsay uppercase of "hi"\nsay split "a,b,c" by ","\nsay join (list of "a", "b") by "-"\nsay replace "o" by "0" in "foo"\nsay position of "b" in "abc"\nsay "hello" contains "ell"',
               "expect": ["n = 3!", "HI", "[a, b, c]", "a-b", "f00", "2", "true"]}]),
            ("Text has a ceiling of ten million characters — growing past it is an error, not an out-of-memory crash. "
             "`replace` needs something to look for: an empty `OLD` is an error.",
             [{"code": 'set t to "abcdefghij"\nrepeat 30 times\n    set t to t plus t\nend\nsay length of t', "error": "too long"},
              {"code": 'say replace "" by "x" in "abc"', "error": "can't be empty"}]),
            ("Interpolation `{expr}` inside text splices in a value; the braces must hold exactly one expression.",
             [{"code": 'set n to 3\nsay "double is {n multiplied by 2}, braces are {{like this}}"', "expect": ["double is 6, braces are {like this}"]},
              {"code": 'say "{1 2}"', "error": "after the value"}]),
        ],
    },
    {
        "title": "4.5 Lists and records",
        "rules": [
            ("Lists are ordered and **1-indexed**. `item N of L` reads, `set item N of L to V` replaces, `add V to L` "
             "appends, `remove item N from L` deletes; an index outside the list is an error. `first`, `last`, "
             "`length`, `sum`, `average`, `smallest`, `largest`, `sorted` (numbers or texts, ascending) and "
             "`reverse` (lists or text) are built in.",
             [{"code": 'set xs to list of 10, 20, 30\nadd 40 to xs\nremove item 1 from xs\nset item 1 of xs to 99\nsay xs\nsay item 2 of xs\nsay length of xs\nsay sum of xs\nsay average of xs\nsay sorted of xs\nsay reverse of xs',
               "expect": ["[99, 30, 40]", "30", "3", "169", "56.3333333333", "[30, 40, 99]", "[40, 30, 99]"]},
              {"code": 'set xs to list of 1\nsay item 5 of xs', "error": "no item 5"}]),
            ("Records map keys to values. `item KEY of R` reads a field (an unknown key is an error), "
             "`set item KEY of R to V` adds or replaces one, `keys of R` lists the keys in insertion order.",
             [{"code": 'set p to record with "name" as "Ada", "score" as 10\nset item "score" of p to 15\nset item "city" of p to "London"\nsay item "name" of p\nsay keys of p\nsay p',
               "expect": ["Ada", "[name, score, city]", "{name: Ada, score: 15, city: London}"]}]),
            ("Lists and records are passed to functions **by reference**: a function that adds to its parameter "
             "changes the caller's list.",
             [{"code": 'set a to list of 1\ndefine grow with xs\n    add 2 to xs\nend\ncall grow with a\nsay a', "expect": ["[1, 2]"]}]),
        ],
    },
    {
        "title": "4.6 Statements and scope",
        "rules": [
            ("`set NAME to V` assigns. If NAME already exists in an enclosing scope it is updated; otherwise a new "
             "variable is created in the current scope. Reading a name that does not exist is an error.",
             [{"code": 'set total to 0\ndefine bump with n\n    set total to total plus n\nend\ncall bump with 5\ncall bump with 7\nsay total', "expect": ["12"]},
              {"code": 'say mystery', "error": "haven't heard of a variable"}]),
            ("A function's parameters are local: they shadow, and never change, a variable of the same name outside.",
             [{"code": 'set n to 100\ndefine f with n\n    return n plus 1\nend\nsay f with 1\nsay n', "expect": ["2", "100"]}]),
            ("`if` runs the first branch whose condition is true (else the `otherwise` block). `otherwise if` chains "
             "only when the `if` is on the **same line** as `otherwise`; an `if` on the next line is an ordinary "
             "statement inside the else-block.",
             [{"code": 'set n to 15\nif n is at least 18 then\n    say "adult"\notherwise if n is at least 13 then\n    say "teen"\notherwise\n    say "child"\nend',
               "expect": ["teen"]},
              {"code": 'set ok to true\nif false then\n    say "a"\notherwise\n    if ok then\n        say "inner"\n    end\n    say "after"\nend',
               "expect": ["inner", "after"]}]),
            ("`match V` compares V with each `when` value using equality (§4.3, so it never fails) and runs the first "
             "match, else the `otherwise` block.",
             [{"code": 'match "hi"\n    when 1 then\n        say "num"\n    when "hi" then\n        say "text"\n    otherwise\n        say "other"\nend', "expect": ["text"]}]),
        ],
    },
    {
        "title": "4.7 Loops",
        "rules": [
            ("`repeat N times` runs its body N times (N is truncated to a whole number; zero or negative runs it "
             "never). `while C` repeats while C is true. `for each X in L` visits each item of a list in order.",
             [{"code": 'repeat 2 times\n    say "hi"\nend\nset n to 1\nwhile n is less than 10\n    set n to n multiplied by 3\nend\nsay n\nfor each c in list of "a", "b"\n    say c\nend',
               "expect": ["hi", "hi", "27", "a", "b"]}]),
            ("`count I from A to B` sets I to A, A±1, … up to and including B, counting **down** when B < A. The loop "
             "variable keeps its last value afterwards, and nested loops may reuse a name without disturbing each other.",
             [{"code": 'count i from 3 to 1\n    say i\nend\nsay i\ncount i from 1 to 2\n    count i from 1 to 2\n    end\n    say i\nend',
               "expect": ["3", "2", "1", "1", "2", "2"]}]),
            ("`stop` leaves the innermost loop; `skip` jumps to its next pass.",
             [{"code": 'count i from 1 to 10\n    if i is equal to 5 then\n        stop\n    end\n    if remainder of i and 2 is equal to 0 then\n        skip\n    end\n    say i\nend',
               "expect": ["1", "3"]}]),
        ],
    },
    {
        "title": "4.8 Functions",
        "rules": [
            ("`define NAME with P and Q … end` declares a function; `NAME with X and Y` calls it as a value, and "
             "`call NAME with X and Y` (or just `NAME with X`) calls it as a statement, discarding the result. "
             "`return V` ends the call with a value. Functions may call themselves. Arguments are separated by `and`, "
             "so a true/false argument needs parentheses.",
             [{"code": 'define fact with n\n    if n is at most 1 then\n        return 1\n    end\n    return n multiplied by (fact with (n minus 1))\nend\nsay fact with 10',
               "expect": ["3628800"]},
              {"code": 'define both with a and b\n    return a and b\nend\nsay both with (true and false) and true', "expect": ["false"]}]),
            ("Calling with the wrong number of arguments is an error; so is using a function that never `return`s "
             "as a value.",
             [{"code": 'define f with a\n    return a\nend\nsay f with 1 and 2', "error": "expects 1"},
              {"code": 'define quiet with n\n    set x to n\nend\nsay quiet with 1', "error": "didn't 'return'"}]),
            ("Functions are values: a function can be stored in a variable, passed to another function, and "
             "used by `map FN over L` (transform each item), `filter FN over L` (keep items for which it returns "
             "true) and `reduce FN over L from START` (fold left).",
             [{"code": 'define double with n\n    return n multiplied by 2\nend\ndefine is_even with n\n    return remainder of n and 2 is equal to 0\nend\ndefine combine with a and b\n    return a plus b\nend\nset nums to list of 1, 2, 3, 4\nset f to double\nsay f with 21\nsay map double over nums\nsay filter is_even over nums\nsay reduce combine over nums from 0',
               "expect": ["42", "[2, 4, 6, 8]", "[2, 4]", "10"]}]),
        ],
    },
    {
        "title": "4.9 Errors",
        "rules": [
            ("A runtime error stops the program at once; everything printed before it stays printed. Errors are "
             "reported in plain language with the line, the offending source, and — for a mistyped name — a "
             "*did you mean* suggestion.",
             [{"code": 'say "before"\nsay 1 divided by 0\nsay "never printed"', "error": "divide by zero"},
              {"code": 'set score to 1\nsay scor', "error": "Did you mean 'score'"}]),
        ],
    },
]

TURTLE = """\
### 4.10 Drawing (browser only)

The playground adds turtle statements to the grammar (`turtle_stmt`, enabled with
`turtle=True` in `plainspec.py`). The command-line engines reject them with a
message explaining that drawing needs the playground.

| Statement | Effect |
|---|---|
| `move forward N` / `move backward N` | move the turtle, drawing if the pen is down |
| `turn right N` / `turn left N` | rotate by N degrees |
| `pen up` / `pen down` | stop / start drawing |
| `pen color to "#rrggbb"` | choose the pen colour |
| `wait N` | pause N seconds |
"""

MODULES = """\
### 4.11 Modules (command line only)

`import "file.plang"` (grammar rule `import_stmt`) is resolved **before** a program
runs: the named file — relative to the importing file — is read and its function
definitions are spliced in. An imported file may contain only function definitions;
imports may be nested; the same file imported twice is fine; a cycle is an error.
The browser has no filesystem, so the JavaScript engine does not implement `import`.
"""

CONFORMANCE = """\
## 5. Conformance

PlainLang has four independent implementations. All are held to this document and
to each other:

| Implementation | Role |
|---|---|
| `plainlang.py` | reference tree-walking interpreter |
| `plainvm.py` | bytecode compiler and stack VM |
| `plainlang.js` | JavaScript engine (browser) with a PlainLang→JavaScript transpiler |
| `plainwasm.py` | WebAssembly compiler for the numeric core (numbers, true/false, text output, control flow, functions) |

A program's observable behaviour — what it prints, and whether and where it fails —
must be identical across all of them. This is enforced by `test_vm.py`,
`test_js.js`, `test_wasm.py` and three differential fuzzers (`fuzz.py`, `fuzz_wasm.py`,
`spec_fuzz.py`).
"""
