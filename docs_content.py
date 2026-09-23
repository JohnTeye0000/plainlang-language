"""
The PlainLang guide and reference, as data.

Every example with "run": True is executed when the site is built (build_docs.py)
and its real output is printed beneath it -- so the documentation can't claim
something the language doesn't do. test_docs.py holds it to that: every runnable
example must run, the Python and JavaScript engines must agree on its output,
and every keyword in the language must appear somewhere in these pages.

Fields:
  code   the example source
  run    False for things that can't run in a browser-less build (imports, turtle)
  error  True when the example is *meant* to fail, to show the error message
"""

SECTIONS = [
    {
        "id": "start", "title": "Getting started",
        "intro": "<p>PlainLang is written to be read aloud. There are no braces, no semicolons, no symbols to memorize — "
                 "just words. Every program is a list of <em>statements</em>, one per line, run from top to bottom.</p>",
        "examples": [
            {"code": 'say "Hello, world!"', "note": "<code>say</code> prints a line."},
            {"code": 'set name to "Ada"\nset year to 1843\nsay name plus " wrote the first program in " plus year',
             "note": "<code>set</code> remembers a value under a name. <code>plus</code> joins text and numbers."},
            {"code": '# lines starting with a hash are comments — notes for humans\nsay 2 plus 3 multiplied by 4   # multiplication happens first',
             "note": "Comments start with <code>#</code>. The usual order of operations applies; use parentheses to change it."},
        ],
    },
    {
        "id": "values", "title": "Numbers, text and true/false",
        "intro": "<p>There are three basic kinds of value. <strong>Numbers</strong> use <code>plus</code>, <code>minus</code>, "
                 "<code>multiplied by</code> and <code>divided by</code>. <strong>Text</strong> goes in double quotes. "
                 "<strong>True/false</strong> values come from comparisons.</p>",
        "examples": [
            {"code": 'say 7 divided by 2\nsay 10 minus 3\nsay minus 4 plus 10',
             "note": "Division gives fractions. A negative number is written with <code>minus</code> in front."},
            {"code": 'set who to "Sam"\nset n to 3\nsay "Hi {who}, you have {n plus 1} messages"',
             "note": "Anything inside <code>{ }</code> in a piece of text is worked out and dropped in. Write <code>{{</code> for a literal brace."},
            {"code": 'say 5 is greater than 3\nsay 5 is equal to 6\nsay true and false\nsay not false',
             "note": "Comparisons and <code>and</code> / <code>or</code> / <code>not</code> make true/false values."},
        ],
    },
    {
        "id": "decisions", "title": "Making decisions",
        "intro": "<p>Use <code>if … then … otherwise … end</code> to choose what to do. Comparisons read like English: "
                 "<code>is equal to</code>, <code>is not equal to</code>, <code>is greater than</code>, <code>is less than</code>, "
                 "<code>is at least</code>, <code>is at most</code>.</p>",
        "examples": [
            {"code": 'set age to 15\nif age is at least 18 then\n    say "adult"\notherwise if age is at least 13 then\n    say "teenager"\notherwise\n    say "child"\nend',
             "note": "Chain checks with <code>otherwise if</code> — but keep the <code>if</code> on the same line as <code>otherwise</code>."},
            {"code": 'set has_ticket to true\nset is_member to false\nif has_ticket and is_member then\n    say "VIP"\notherwise if has_ticket or is_member then\n    say "welcome"\notherwise\n    say "sorry"\nend'},
            {"code": 'set day to 2\nmatch day\n    when 1 then\n        say "Monday"\n    when 2 then\n        say "Tuesday"\n    otherwise\n        say "another day"\nend',
             "note": "<code>match</code> compares one value against several <code>when</code> cases. Comparing values of different kinds is never an error — they are simply not equal."},
        ],
    },
    {
        "id": "loops", "title": "Repeating things",
        "intro": "<p>Four kinds of loop, all closed with <code>end</code>. Inside any loop, <code>stop</code> leaves it early and "
                 "<code>skip</code> jumps to the next pass.</p>",
        "examples": [
            {"code": 'repeat 3 times\n    say "hello"\nend', "note": "<code>repeat N times</code> runs its body a fixed number of times."},
            {"code": 'count i from 1 to 5\n    say i\nend\ncount i from 3 to 1\n    say i\nend',
             "note": "<code>count</code> goes up or down automatically, and the counting variable is yours to use."},
            {"code": 'set n to 1\nwhile n is less than 100\n    set n to n multiplied by 2\nend\nsay n', "note": "<code>while</code> keeps going as long as its condition is true."},
            {"code": 'for each colour in list of "red", "green", "blue"\n    say colour\nend', "note": "<code>for each … in</code> walks through a list."},
            {"code": 'count i from 1 to 10\n    if i is equal to 9 then\n        stop\n    end\n    if remainder of i and 3 is equal to 0 then\n        skip\n    end\n    say i\nend',
             "note": "Skip the multiples of 3, and stop when we reach 9."},
        ],
    },
    {
        "id": "lists", "title": "Lists",
        "intro": "<p>A list holds several values in order. Lists count from <strong>1</strong> — the way people do.</p>",
        "examples": [
            {"code": 'set fruits to list of "apple", "banana"\nadd "cherry" to fruits\nsay fruits\nsay item 2 of fruits\nsay length of fruits',
             "note": "<code>list of</code> makes a list, <code>add … to</code> appends, <code>item N of</code> reads, <code>length of</code> counts."},
            {"code": 'set xs to list of 10, 20, 30, 40\nremove item 2 from xs\nset item 1 of xs to 99\nsay xs',
             "note": "<code>remove item</code> deletes; <code>set item … of … to</code> replaces."},
            {"code": 'set stuff to empty list\nadd 1 to stuff\nsay stuff\nsay length of stuff', "note": "<code>empty list</code> starts you with nothing."},
        ],
    },
    {
        "id": "records", "title": "Records",
        "intro": "<p>A record is a bundle of named fields — like a card with labelled boxes.</p>",
        "examples": [
            {"code": 'set player to record with "name" as "Ada", "score" as 0\nset item "score" of player to 150\nsay item "name" of player\nsay player',
             "note": "Read a field with <code>item \"name\" of</code>; change one with <code>set item</code>."},
            {"code": 'set p to record with "x" as 1, "y" as 2\nfor each field in keys of p\n    say field plus " = " plus item field of p\nend',
             "note": "<code>keys of</code> lists the field names."},
        ],
    },
    {
        "id": "functions", "title": "Functions",
        "intro": "<p>Teach PlainLang a new word with <code>define</code>. A function takes inputs after <code>with</code> "
                 "(separated by <code>and</code>) and hands a value back with <code>return</code>. Functions may call themselves.</p>",
        "examples": [
            {"code": 'define double with n\n    return n multiplied by 2\nend\nsay double with 21'},
            {"code": 'define bigger with a and b\n    if a is greater than b then\n        return a\n    end\n    return b\nend\nsay bigger with 7 and 12',
             "note": "Several inputs are separated by <code>and</code>. If an input is itself a true/false expression, wrap it in parentheses."},
            {"code": 'define factorial with n\n    if n is at most 1 then\n        return 1\n    end\n    return n multiplied by (factorial with (n minus 1))\nend\nsay factorial with 10',
             "note": "Recursion: a function that uses itself. Always give it a stopping case."},
            {"code": 'define greet with who\n    say "Hello, " plus who\nend\ncall greet with "Bob"', "note": "<code>call</code> runs a function as an action and ignores what it returns."},
            {"code": 'define double with n\n    return n multiplied by 2\nend\ndefine apply_twice with f and x\n    return f with (f with x)\nend\nset op to double\nsay op with 21\nsay apply_twice with double and 5',
             "note": "Functions are values: store them in variables and pass them to other functions."},
        ],
    },
    {
        "id": "higher", "title": "Map, filter and reduce",
        "intro": "<p>Three ways to work on a whole list at once, without writing the loop yourself.</p>",
        "examples": [
            {"code": 'define double with n\n    return n multiplied by 2\nend\ndefine is_even with n\n    return remainder of n and 2 is equal to 0\nend\ndefine combine with a and b\n    return a plus b\nend\nset nums to list of 1, 2, 3, 4, 5, 6\nsay map double over nums\nsay filter is_even over nums\nsay reduce combine over nums from 0',
             "note": "<code>map</code> transforms every item, <code>filter</code> keeps the items a function approves of, <code>reduce</code> folds a list down to one value."},
        ],
    },
    {
        "id": "text", "title": "Working with text",
        "intro": "<p>A small toolbox for words.</p>",
        "examples": [
            {"code": 'say uppercase of "hello"\nsay lowercase of "HELLO"\nsay trim of "   padded   "\nsay length of "hello"'},
            {"code": 'say split "a,b,c" by ","\nsay join (list of "a", "b", "c") by "-"\nsay replace "o" by "0" in "foo"',
             "note": "<code>split</code> breaks text into a list; <code>join</code> glues a list into text; <code>replace</code> swaps pieces."},
            {"code": 'say position of "b" in "abc"\nsay "hello" contains "ell"\nsay (list of 1, 2, 3) contains 2',
             "note": "<code>position of</code> is 1-based (0 means not found); <code>contains</code> works on text and lists."},
        ],
    },
    {
        "id": "numbers", "title": "Numbers and math",
        "intro": "<p>Built-in helpers for numbers and for lists of numbers.</p>",
        "examples": [
            {"code": 'say round of 2.5\nsay floor of 3.7\nsay ceiling of 3.2\nsay absolute of (minus 8)\nsay square root of 144',
             "note": "<code>round</code> rounds halves <em>away</em> from zero (2.5 → 3, −2.5 → −3), the way it's taught in school."},
            {"code": 'say power of 2 and 10\nsay min of 4 and 9\nsay max of 4 and 9\nsay remainder of 17 and 5',
             "note": "Two-input helpers use <code>and</code>. <code>remainder</code> is what's left after dividing."},
            {"code": 'set scores to list of 90, 75, 88, 95, 60\nsay sum of scores\nsay average of scores\nsay smallest of scores\nsay largest of scores\nsay first of scores\nsay last of scores',
             "note": "Numbers never print in scientific notation, and fractions show up to ten decimal places."},
            {"code": 'say sorted of (list of 3, 1, 2)\nsay reverse of (list of 1, 2, 3)\nsay reverse of "abc"'},
            {"code": 'set roll to random between 1 and 6\nsay roll is at least 1', "note": "<code>random between</code> gives a whole number in the range, inclusive."},
        ],
    },
    {
        "id": "input", "title": "Asking questions",
        "intro": "<p><code>ask</code> pauses and waits for the person running the program. It can't run in this documentation "
                 "(there's nobody to answer), but try it in the playground.</p>",
        "examples": [
            {"code": 'ask "What is your name? " into name\nsay "Nice to meet you, " plus name', "run": False,
             "note": "Whatever is typed is stored in the variable after <code>into</code>; numbers arrive as numbers."},
        ],
    },
    {
        "id": "errors", "title": "When something goes wrong",
        "intro": "<p>Errors in PlainLang are written for beginners: they point at the exact spot, say what happened in plain words, "
                 "and often suggest a fix.</p>",
        "examples": [
            {"code": 'set score to 10\nsay scor plus 1', "error": True,
             "note": "A mistyped name gets a <em>did you mean</em> suggestion."},
            {"code": 'say 10 divided by 0', "error": True},
            {"code": 'say "apples" minus 3', "error": True, "note": "Some mistakes are caught before the program even runs — see <code>plaincheck.py</code> in the tools section."},
        ],
    },
    {
        "id": "modules", "title": "Programs in several files",
        "intro": "<p>From the command line, one file can <code>import</code> another's functions. An imported file is a library: "
                 "it may only contain function definitions. (The browser playground has no filesystem, so imports work only from the command line.)</p>",
        "examples": [
            {"code": 'import "geometry.plang"\n\nsay area_of_circle with 4', "run": False,
             "note": "Imports resolve transitively; circular imports and missing files give friendly errors."},
        ],
    },
    {
        "id": "turtle", "title": "Drawing with the turtle",
        "intro": "<p>In the playground, a turtle draws as it moves. Open the <em>Drawn</em> tab. (Drawing only works in the browser.)</p>",
        "examples": [
            {"code": 'pen color to "#c0392b"\nrepeat 4 times\n    move forward 120\n    turn right 90\nend', "run": False,
             "note": "<code>move forward</code>, <code>move backward</code>, <code>turn left</code>, <code>turn right</code>, <code>pen up</code>, <code>pen down</code>, <code>pen color to</code>, <code>wait</code>."},
            {"code": 'count i from 1 to 40\n    move forward i multiplied by 4\n    turn right 91\nend', "run": False, "note": "Loop variables can shape the drawing."},
        ],
    },
]

# Prose-only pages that describe the tools around the language.
TOOLS = [
    ("plainlang.py", "The reference interpreter and REPL: <code>python plainlang.py program.plang</code>, or with no argument for an interactive prompt."),
    ("plainvm.py", "A bytecode compiler and stack VM (<code>--dis</code> to disassemble, <code>--trace</code> to watch it run, <code>--optimize</code>, <code>--emit</code> / <code>--run-bc</code> for portable bytecode)."),
    ("plainwasm.py", "Compiles a numeric-core subset to a real WebAssembly binary: <code>python plainwasm.py program.plang -o out.wasm</code>."),
    ("plaincheck.py", "A static analyzer and gradual type checker that finds mistakes before a program runs."),
    ("plainfmt.py", "The code formatter: <code>--write</code> to format in place, <code>--check</code> for CI."),
    ("plainlsp.py", "A Language Server for editors: diagnostics, hover, go-to-definition, symbols and completion."),
]
