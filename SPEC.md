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

`absolute` `add` `and` `as` `ask` `at` `average` `between`  
`by` `call` `ceiling` `contains` `count` `define` `divided` `each`  
`empty` `end` `equal` `false` `filter` `first` `floor` `for`  
`from` `greater` `if` `import` `in` `into` `is` `item`  
`join` `keys` `largest` `last` `least` `length` `less` `list`  
`lowercase` `map` `match` `max` `min` `minus` `most` `multiplied`  
`not` `of` `or` `otherwise` `over` `plus` `position` `power`  
`random` `record` `reduce` `remainder` `remove` `repeat` `replace` `return`  
`reverse` `root` `round` `say` `set` `skip` `smallest` `sorted`  
`split` `square` `stop` `sum` `than` `then` `times` `to`  
`trim` `true` `uppercase` `when` `while` `with`

The browser's turtle vocabulary is reserved everywhere too, so a name means the same in every implementation: `back` `backward` `color` `down` `forward` `left` `move` `pen` `right` `turn` `up` `wait`.

**Text interpolation.** Inside a text literal, `{expression}` is replaced by the
value of the expression, converted to text as `say` would. The braces must contain
exactly one complete expression. `{{` and `}}` stand for literal braces.

## 3. Syntax

The syntax is given by this grammar, in the notation described at its top. It is exactly [`grammar.ebnf`](grammar.ebnf).

```ebnf
(* ═══════════════════════════════════════════════════════════════════════════
   PlainLang — syntactic grammar

   This file is the specification of PlainLang's syntax, and it is executable:
   plainspec.py reads it and recognizes programs directly, and test_spec.py
   differentially tests that recognizer against the real parsers on thousands
   of valid and deliberately-corrupted programs. Anything the grammar and a
   parser disagree about is a bug in one of them.

   Notation (PEG-flavoured EBNF)
     "word"      the keyword `word` (keywords are case-insensitive)
     "word"@     the keyword `word`, on the SAME LINE as the token before it
                 (the one context-sensitive rule: `otherwise if` chains only
                  when the `if` is on the `otherwise` line)
     IDENT       an identifier      NUMBER   a number      STRING   a text literal
     EOF         end of the program
     a b         sequence           a | b    ordered choice (first match wins)
     { a }       zero or more       [ a ]    optional      ( a )    grouping
   Newlines are otherwise insignificant: a program is a stream of tokens.
   ═══════════════════════════════════════════════════════════════════════════ *)

program        = block EOF ;

(* A block is a run of statements; it ends where no statement can start,
   which is exactly at `end`, `otherwise`, `when`, or the end of the program. *)
block          = { statement } ;

statement      = set_stmt | say_stmt | ask_stmt | if_stmt | match_stmt
               | repeat_stmt | while_stmt | count_stmt | foreach_stmt
               | define_stmt | import_stmt | return_stmt | add_stmt | remove_stmt
               | "stop" | "skip"
               | call_stmt ;

set_stmt       = "set" ( "item" expr "of" primary "to" expr
                       | IDENT "to" expr ) ;
say_stmt       = "say" expr ;
ask_stmt       = "ask" expr "into" IDENT ;

if_stmt        = "if" expr "then" block
                 { "otherwise" "if"@ expr "then" block }
                 [ "otherwise" block ]
                 "end" ;

match_stmt     = "match" expr
                 { "when" expr "then" block }
                 [ "otherwise" block ]
                 "end" ;

repeat_stmt    = "repeat" expr "times" block "end" ;
while_stmt     = "while" expr block "end" ;
count_stmt     = "count" IDENT "from" expr "to" expr block "end" ;
foreach_stmt   = "for" "each" IDENT "in" expr block "end" ;

define_stmt    = "define" IDENT [ "with" IDENT { "and" IDENT } ] block "end" ;
import_stmt    = "import" STRING ;
return_stmt    = "return" expr ;
add_stmt       = "add" expr "to" IDENT ;
remove_stmt    = "remove" "item" expr "from" IDENT ;

(* `call` is optional: a bare `greet with "Bob"` is a call statement too.
   Arguments are separated by `and`, so each argument is parsed *below* the
   and/or operators; a boolean argument needs parentheses:  f with (a and b) *)
call_stmt      = [ "call" ] IDENT [ "with" comparison { "and" comparison } ] ;

(* ── expressions, loosest to tightest ─────────────────────────────────── *)

expr           = or_expr ;
or_expr        = and_expr { "or" and_expr } ;
and_expr       = not_expr { "and" not_expr } ;
not_expr       = "not" not_expr | comparison ;

(* comparisons do not chain; a bare `is` means `is equal to` *)
comparison     = arith [ "is" cmp_op arith
                       | "contains" arith ] ;
cmp_op         = "not" [ "equal" [ "to" ] ]
               | "greater" "than"
               | "less" "than"
               | "at" ( "least" | "most" )
               | "equal" [ "to" ]
               | ;

arith          = term { ( "plus" | "minus" ) term } ;
term           = factor { ( "multiplied" | "divided" ) "by" factor } ;
factor         = "minus" factor | primary ;

primary        = NUMBER
               | STRING
               | "(" expr ")"
               | "true" | "false"
               | "empty" ( "record" | "list" )
               | "list" "of" expr { "," expr }
               | record_lit
               | ( "map" | "filter" ) comparison "over" comparison
               | "reduce" comparison "over" comparison "from" comparison
               | "item" expr "of" primary
               | ( "length" | "uppercase" | "lowercase" | "round" | "absolute"
                 | "keys" | "trim" | "sum" | "average" | "smallest" | "largest"
                 | "first" | "last" | "reverse" | "sorted" | "floor" | "ceiling" )
                 "of" primary
               | "square" "root" "of" primary
               | ( "remainder" | "power" | "min" | "max" ) "of" arith "and" arith
               | "split" comparison "by" comparison
               | "join" comparison "by" comparison
               | "replace" comparison "by" comparison "in" comparison
               | "position" "of" comparison "in" comparison
               | "random" "between" arith "and" arith
               | IDENT [ "with" comparison { "and" comparison } ] ;

record_lit     = "record" "with" comparison "as" comparison
                 { "," comparison "as" comparison } ;

(* ── the browser playground's turtle-graphics extension ───────────────────
   Only the JavaScript engine accepts these (the command-line engines say
   "turtle drawing only works in the web playground"). plainspec.py enables
   them with turtle=True. *)
turtle_stmt    = "move" [ "forward" | "backward" | "back" ] expr
               | "turn" [ "right" | "left" ] expr
               | "pen" ( "up" | "down" | "color" "to" expr )
               | "wait" expr ;
```

## 4. Meaning

### 4.1 Values and output

There are six kinds of value: **number**, **text**, **true/false**, **list**, **record** (an ordered map from text or number keys to values) and **function**. `say` prints a value on its own line.

```
say 42
say "hi"
say true
say list of 1, 2
say record with "a" as 1
```
prints:
```
42
hi
true
[1, 2]
{a: 1}
```

A whole number prints with no decimal point; any other number is rounded to ten decimal places and **never printed in scientific notation**. Rounding of ties is *half away from zero*.

```
say 4 multiplied by 0.5 plus 8
say 10 divided by 3
say 1 divided by 1000000
say 1 divided by 1000000000000
```
prints:
```
10
3.3333333333
0.000001
0
```

### 4.2 Numbers

Numbers are **64-bit floating point** (IEEE 754 doubles) in every implementation. A whole number beyond 2^53 prints as the exact digits of the nearest double, and a result too large for a double is an error, never `Infinity`.

```
say power of 2 and 100
say 9007199254740993
```
prints:
```
1267650600228229401496703205376
9007199254740992
```

```
say power of 10 and 400
```
is an error, and the message contains *“too big”*.

`plus`, `minus`, `multiplied by`, `divided by` take numbers; `plus` also joins text (§4.4). Dividing by zero is an error. Unary `minus` negates.

```
say 7 divided by 2
say minus 5 plus 8
```
prints:
```
3.5
3
```

```
say 1 divided by 0
```
is an error, and the message contains *“divide by zero”*.

`round of` rounds half **away from zero** (2.5 → 3, −2.5 → −3). `floor of` and `ceiling of` round toward −∞ and +∞. `remainder of A and B` is the **floored** remainder of the whole-number parts (its sign follows B); `B` may not be 0.

```
say round of 2.5
say round of (minus 2.5)
say floor of (minus 3.2)
say ceiling of (minus 3.7)
```
prints:
```
3
-3
-4
-3
```

```
say remainder of 17 and 5
say remainder of (minus 7) and 3
say remainder of 7 and (minus 3)
```
prints:
```
2
2
-2
```

`power of X and Y` is X^Y; `min of` / `max of` compare two numbers; `square root of X` needs X ≥ 0; `absolute of X` is |X|. Zero to a negative power, and a negative number to a fractional power, are errors.

```
say power of 2 and 10
say min of 4 and 9
say max of 4 and 9
say square root of 144
say absolute of (minus 8)
```
prints:
```
1024
4
9
12
8
```

```
say power of 0 and (minus 1)
```
is an error, and the message contains *“negative power”*.

### 4.3 Truth, comparison and logic

`is equal to` and `is not equal to` are defined for **every** pair of values and never fail: values of different kinds are simply not equal; lists and records are equal when their contents are.

```
say 16 is equal to "hi"
say 16 is not equal to "hi"
set a to list of 1, 2
set b to list of 1, 2
say a is equal to b
```
prints:
```
false
true
true
```

`is greater than`, `is less than`, `is at least`, `is at most` need two numbers or two texts (texts compare in dictionary order); anything else is an error. A bare `is` means `is equal to`.

```
say 5 is greater than 3
say "apple" is less than "banana"
say 4 is 4
```
prints:
```
true
true
true
```

```
say 5 is greater than "five"
```
is an error, and the message contains *“can't compare”*.

A condition may be any value: a number is true unless 0, text/list/record is true unless empty. `and` / `or` **short-circuit** — the right side is not evaluated when the left decides — and `not` negates.

```
if 3 then
say "nonzero"
end
if "" then
say "no"
otherwise
say "empty text is false"
end
say false and (1 divided by 0)
say true or (1 divided by 0)
```
prints:
```
nonzero
empty text is false
false
true
```

### 4.4 Text

`plus` with text on either side joins them, converting the other side as `say` would. `uppercase of`, `lowercase of`, `trim of`, `length of` work on text; `split TEXT by SEP` gives a list of pieces (`""` splits into characters); `join LIST by SEP` reverses it; `replace OLD by NEW in TEXT` replaces every occurrence; `position of PART in TEXT` is 1-based, 0 when absent; `TEXT contains PART` tests.

```
say "n = " plus 3 plus "!"
say uppercase of "hi"
say split "a,b,c" by ","
say join (list of "a", "b") by "-"
say replace "o" by "0" in "foo"
say position of "b" in "abc"
say "hello" contains "ell"
```
prints:
```
n = 3!
HI
[a, b, c]
a-b
f00
2
true
```

Text has a ceiling of ten million characters — growing past it is an error, not an out-of-memory crash. `replace` needs something to look for: an empty `OLD` is an error.

```
set t to "abcdefghij"
repeat 30 times
    set t to t plus t
end
say length of t
```
is an error, and the message contains *“too long”*.

```
say replace "" by "x" in "abc"
```
is an error, and the message contains *“can't be empty”*.

Interpolation `{expr}` inside text splices in a value; the braces must hold exactly one expression.

```
set n to 3
say "double is {n multiplied by 2}, braces are {{like this}}"
```
prints:
```
double is 6, braces are {like this}
```

```
say "{1 2}"
```
is an error, and the message contains *“after the value”*.

### 4.5 Lists and records

Lists are ordered and **1-indexed**. `item N of L` reads, `set item N of L to V` replaces, `add V to L` appends, `remove item N from L` deletes; an index outside the list is an error. `first`, `last`, `length`, `sum`, `average`, `smallest`, `largest`, `sorted` (numbers or texts, ascending) and `reverse` (lists or text) are built in.

```
set xs to list of 10, 20, 30
add 40 to xs
remove item 1 from xs
set item 1 of xs to 99
say xs
say item 2 of xs
say length of xs
say sum of xs
say average of xs
say sorted of xs
say reverse of xs
```
prints:
```
[99, 30, 40]
30
3
169
56.3333333333
[30, 40, 99]
[40, 30, 99]
```

```
set xs to list of 1
say item 5 of xs
```
is an error, and the message contains *“no item 5”*.

Records map keys to values. `item KEY of R` reads a field (an unknown key is an error), `set item KEY of R to V` adds or replaces one, `keys of R` lists the keys in insertion order.

```
set p to record with "name" as "Ada", "score" as 10
set item "score" of p to 15
set item "city" of p to "London"
say item "name" of p
say keys of p
say p
```
prints:
```
Ada
[name, score, city]
{name: Ada, score: 15, city: London}
```

Lists and records are passed to functions **by reference**: a function that adds to its parameter changes the caller's list.

```
set a to list of 1
define grow with xs
    add 2 to xs
end
call grow with a
say a
```
prints:
```
[1, 2]
```

### 4.6 Statements and scope

`set NAME to V` assigns. If NAME already exists in an enclosing scope it is updated; otherwise a new variable is created in the current scope. Reading a name that does not exist is an error.

```
set total to 0
define bump with n
    set total to total plus n
end
call bump with 5
call bump with 7
say total
```
prints:
```
12
```

```
say mystery
```
is an error, and the message contains *“haven't heard of a variable”*.

A function's parameters are local: they shadow, and never change, a variable of the same name outside.

```
set n to 100
define f with n
    return n plus 1
end
say f with 1
say n
```
prints:
```
2
100
```

`if` runs the first branch whose condition is true (else the `otherwise` block). `otherwise if` chains only when the `if` is on the **same line** as `otherwise`; an `if` on the next line is an ordinary statement inside the else-block.

```
set n to 15
if n is at least 18 then
    say "adult"
otherwise if n is at least 13 then
    say "teen"
otherwise
    say "child"
end
```
prints:
```
teen
```

```
set ok to true
if false then
    say "a"
otherwise
    if ok then
        say "inner"
    end
    say "after"
end
```
prints:
```
inner
after
```

`match V` compares V with each `when` value using equality (§4.3, so it never fails) and runs the first match, else the `otherwise` block.

```
match "hi"
    when 1 then
        say "num"
    when "hi" then
        say "text"
    otherwise
        say "other"
end
```
prints:
```
text
```

### 4.7 Loops

`repeat N times` runs its body N times (N is truncated to a whole number; zero or negative runs it never). `while C` repeats while C is true. `for each X in L` visits each item of a list in order.

```
repeat 2 times
    say "hi"
end
set n to 1
while n is less than 10
    set n to n multiplied by 3
end
say n
for each c in list of "a", "b"
    say c
end
```
prints:
```
hi
hi
27
a
b
```

`count I from A to B` sets I to A, A±1, … up to and including B, counting **down** when B < A. The loop variable keeps its last value afterwards, and nested loops may reuse a name without disturbing each other.

```
count i from 3 to 1
    say i
end
say i
count i from 1 to 2
    count i from 1 to 2
    end
    say i
end
```
prints:
```
3
2
1
1
2
2
```

`stop` leaves the innermost loop; `skip` jumps to its next pass.

```
count i from 1 to 10
    if i is equal to 5 then
        stop
    end
    if remainder of i and 2 is equal to 0 then
        skip
    end
    say i
end
```
prints:
```
1
3
```

### 4.8 Functions

`define NAME with P and Q … end` declares a function; `NAME with X and Y` calls it as a value, and `call NAME with X and Y` (or just `NAME with X`) calls it as a statement, discarding the result. `return V` ends the call with a value. Functions may call themselves. Arguments are separated by `and`, so a true/false argument needs parentheses.

```
define fact with n
    if n is at most 1 then
        return 1
    end
    return n multiplied by (fact with (n minus 1))
end
say fact with 10
```
prints:
```
3628800
```

```
define both with a and b
    return a and b
end
say both with (true and false) and true
```
prints:
```
false
```

Calling with the wrong number of arguments is an error; so is using a function that never `return`s as a value.

```
define f with a
    return a
end
say f with 1 and 2
```
is an error, and the message contains *“expects 1”*.

```
define quiet with n
    set x to n
end
say quiet with 1
```
is an error, and the message contains *“didn't 'return'”*.

Functions are values: a function can be stored in a variable, passed to another function, and used by `map FN over L` (transform each item), `filter FN over L` (keep items for which it returns true) and `reduce FN over L from START` (fold left).

```
define double with n
    return n multiplied by 2
end
define is_even with n
    return remainder of n and 2 is equal to 0
end
define combine with a and b
    return a plus b
end
set nums to list of 1, 2, 3, 4
set f to double
say f with 21
say map double over nums
say filter is_even over nums
say reduce combine over nums from 0
```
prints:
```
42
[2, 4, 6, 8]
[2, 4]
10
```

### 4.9 Errors

A runtime error stops the program at once; everything printed before it stays printed. Errors are reported in plain language with the line, the offending source, and — for a mistyped name — a *did you mean* suggestion.

```
say "before"
say 1 divided by 0
say "never printed"
```
is an error, and the message contains *“divide by zero”*.

```
set score to 1
say scor
```
is an error, and the message contains *“Did you mean 'score'”*.

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

### 4.11 Modules (command line only)

`import "file.plang"` (grammar rule `import_stmt`) is resolved **before** a program
runs: the named file — relative to the importing file — is read and its function
definitions are spliced in. An imported file may contain only function definitions;
imports may be nested; the same file imported twice is fine; a cycle is an error.
The browser has no filesystem, so the JavaScript engine does not implement `import`.

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
