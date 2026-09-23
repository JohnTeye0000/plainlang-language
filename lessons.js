/*
 * The Workbook: PlainLang's guided, auto-checked course.
 *
 * Kept in its own file so the playground (browser) and the test suite (Node)
 * share exactly one copy. Every lesson has:
 *   unit     which unit it belongs to
 *   title    short name
 *   brief    HTML instructions shown to the learner
 *   starter  the code the editor starts with
 *   solution a reference answer -- test_lessons.js proves it passes its own
 *            check() and that the untouched starter does not
 *   check    (result, source) => "" when correct, otherwise a helpful hint
 *
 * `result` is what PlainLang.run() returns: { ok, output: string[], turtle, ... }
 */
(function (global) {
  "use strict";

  const errHint = "There's an error in your program — read the message and fix it.";
  const lines = (r) => r.output.map((l) => l.trim());
  const has = (src, re) => re.test(src);

  const LESSONS = [
    // ── Unit 1 · First steps ──────────────────────────────────────────────
    { unit: "First steps", title: "Say something",
      brief: 'Use <code>say</code> to print a greeting. Make the program print exactly: <code>Hello, world!</code>',
      starter: '# Lesson 1 — print a line of text.\n# Use:  say "your words here"\n\n',
      solution: 'say "Hello, world!"',
      check(r) { if (!r.ok) return errHint;
        return lines(r).includes("Hello, world!") ? "" : "Not yet — it should print exactly: Hello, world!"; } },

    { unit: "First steps", title: "Remember a value",
      brief: 'Create a variable called <code>age</code>, set it to a number, then print a sentence like <code>I am 12 years old</code> that uses the variable.',
      starter: '# Lesson 2 — variables.\n# set age to ...   then   say ... plus age plus ...\n\n',
      solution: 'set age to 12\nsay "I am " plus age plus " years old"',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /set\s+age\s+to/i)) return "Make a variable named age:  set age to ...";
        return lines(r).some((l) => /^I am \d+ years old$/.test(l)) ? "" : "Print a line exactly like: I am 12 years old"; } },

    { unit: "First steps", title: "Do some math",
      brief: 'Print the answer to 23 × 19 — but let PlainLang multiply it with <code>multiplied by</code> (don’t just type 437).',
      starter: '# Lesson 3 — arithmetic.\n# Use:  multiplied by\n\n',
      solution: 'say 23 multiplied by 19',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /multiplied by/i)) return "Use 'multiplied by' to do the calculation.";
        return r.output.some((l) => l.includes("437")) ? "" : "That doesn't equal 437 yet."; } },

    { unit: "First steps", title: "Mix text and numbers",
      brief: 'A variable <code>price</code> is set to <code>20</code> and <code>quantity</code> to <code>3</code>. Print <code>Total: 60</code>, computing the 60 from the variables.',
      starter: 'set price to 20\nset quantity to 3\n\n# Lesson 4 — say "Total: " plus (something)\n\n',
      solution: 'set price to 20\nset quantity to 3\nsay "Total: " plus (price multiplied by quantity)',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /price\s+multiplied by\s+quantity|quantity\s+multiplied by\s+price/i)) return "Multiply the two variables together instead of typing 60.";
        return lines(r).includes("Total: 60") ? "" : 'It should print exactly: Total: 60'; } },

    { unit: "First steps", title: "Divide and round",
      brief: 'Print <code>10 divided by 3</code> rounded to the nearest whole number (that’s <code>3</code>) using <code>round of</code>.',
      starter: '# Lesson 5 — round of (…)\n\n',
      solution: 'say round of (10 divided by 3)',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /round of/i)) return "Use 'round of' around the division.";
        return lines(r).includes("3") ? "" : "10 divided by 3 rounds to 3."; } },

    // ── Unit 2 · Making decisions ─────────────────────────────────────────
    { unit: "Making decisions", title: "Make a decision",
      brief: 'A variable <code>score</code> is provided. Print <code>PASS</code> when it is at least 50, otherwise <code>FAIL</code>. Use <code>if … otherwise … end</code>.',
      starter: 'set score to 72\n\n# Lesson 6 — if / otherwise.\n# Print PASS if score is at least 50, otherwise FAIL.\n\n',
      solution: 'set score to 72\nif score is at least 50 then\n    say "PASS"\notherwise\n    say "FAIL"\nend',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /\bif\b/i) || !has(src, /otherwise/i)) return "Use an if … otherwise … end.";
        return lines(r).includes("PASS") ? "" : "With score 72 it should print PASS. (Try other scores too!)"; } },

    { unit: "Making decisions", title: "Letter grades",
      brief: 'With <code>score</code> set to <code>85</code>, print <code>A</code> for 90 or more, <code>B</code> for 80 or more, and <code>C</code> otherwise — using <code>otherwise if</code>.',
      starter: 'set score to 85\n\n# Lesson 7 — a chain of decisions.\n# if … then … otherwise if … then … otherwise … end\n\n',
      solution: 'set score to 85\nif score is at least 90 then\n    say "A"\notherwise if score is at least 80 then\n    say "B"\notherwise\n    say "C"\nend',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /otherwise\s+if/i)) return "Chain the checks with 'otherwise if'.";
        return lines(r).join(",") === "B" ? "" : "85 should print B — and only B."; } },

    { unit: "Making decisions", title: "Combine conditions",
      brief: 'Set <code>age</code> to <code>15</code> and <code>has_ticket</code> to <code>true</code>. Print <code>Enter</code> only if the person is at least 13 <b>and</b> has a ticket.',
      starter: 'set age to 15\nset has_ticket to true\n\n# Lesson 8 — use  and  to require both.\n\n',
      solution: 'set age to 15\nset has_ticket to true\nif age is at least 13 and has_ticket then\n    say "Enter"\nend',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /\band\b/i)) return "Use 'and' so both conditions must hold.";
        return lines(r).includes("Enter") ? "" : "They're 15 with a ticket, so it should print Enter."; } },

    { unit: "Making decisions", title: "Pick from many",
      brief: 'Set <code>day</code> to <code>3</code>. Use <code>match</code> to print <code>Monday</code> for 1, <code>Tuesday</code> for 2, <code>Wednesday</code> for 3, and <code>Some other day</code> otherwise.',
      starter: 'set day to 3\n\n# Lesson 9 — match … when … then … otherwise … end\n\n',
      solution: 'set day to 3\nmatch day\n    when 1 then\n        say "Monday"\n    when 2 then\n        say "Tuesday"\n    when 3 then\n        say "Wednesday"\n    otherwise\n        say "Some other day"\nend',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /\bmatch\b/i)) return "Use match … when … then.";
        return lines(r).join(",") === "Wednesday" ? "" : "Day 3 should print Wednesday."; } },

    // ── Unit 3 · Repeating things ─────────────────────────────────────────
    { unit: "Repeating things", title: "Count to five",
      brief: 'Print the numbers <code>1</code> through <code>5</code>, each on its own line, using a loop.',
      starter: '# Lesson 10 — loops.\n# Use:  count i from 1 to 5  ...  end\n\n',
      solution: 'count i from 1 to 5\n    say i\nend',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /(count|repeat|while)/i)) return "Use a loop (count / repeat), not five separate say lines.";
        return lines(r).join(",") === "1,2,3,4,5" ? "" : "It should print 1, 2, 3, 4, 5 — one per line."; } },

    { unit: "Repeating things", title: "Count down",
      brief: 'Count <b>down</b> from <code>5</code> to <code>1</code>, then print <code>Liftoff!</code>.',
      starter: '# Lesson 11 — count works in either direction.\n# count i from 5 to 1 ... end\n\n',
      solution: 'count i from 5 to 1\n    say i\nend\nsay "Liftoff!"',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /(count|repeat|while)/i)) return "Use a loop.";
        return lines(r).join(",") === "5,4,3,2,1,Liftoff!" ? "" : "Expected 5, 4, 3, 2, 1 and then Liftoff!"; } },

    { unit: "Repeating things", title: "Keep going while…",
      brief: 'Start <code>n</code> at <code>1</code> and keep doubling it <code>while</code> it is less than 100. When the loop ends, print <code>n</code> (it should be <code>128</code>).',
      starter: 'set n to 1\n\n# Lesson 12 — while CONDITION … end\n\n',
      solution: 'set n to 1\nwhile n is less than 100\n    set n to n multiplied by 2\nend\nsay n',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /\bwhile\b/i)) return "Use a while loop.";
        return lines(r).includes("128") ? "" : "After the loop n should be 128."; } },

    { unit: "Repeating things", title: "Loops inside loops",
      brief: 'Use two <code>count</code> loops, one inside the other, to print every product <code>i multiplied by j</code> for i and j from 1 to 3 (nine lines — the last is <code>9</code>).',
      starter: '# Lesson 13 — a loop inside a loop.\n\n',
      solution: 'count i from 1 to 3\n    count j from 1 to 3\n        say i multiplied by j\n    end\nend',
      check(r, src) { if (!r.ok) return errHint;
        const n = (src.match(/\bcount\b/gi) || []).length;
        if (n < 2) return "Put one count loop inside another.";
        return lines(r).join(",") === "1,2,3,2,4,6,3,6,9" ? "" : "Expected nine lines: 1,2,3,2,4,6,3,6,9."; } },

    { unit: "Repeating things", title: "Skip and stop",
      brief: 'Count from <code>1</code> to <code>10</code>. <code>skip</code> multiples of 3 and <code>stop</code> the loop when you reach 9. It should print <code>1 2 4 5 7 8</code> (one per line).',
      starter: '# Lesson 14 — skip jumps to the next pass, stop leaves the loop.\n# remainder of i and 3  is 0 for multiples of 3\n\n',
      solution: 'count i from 1 to 10\n    if i is equal to 9 then\n        stop\n    end\n    if remainder of i and 3 is equal to 0 then\n        skip\n    end\n    say i\nend',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /\bskip\b/i) || !has(src, /\bstop\b/i)) return "Use both skip and stop.";
        return lines(r).join(",") === "1,2,4,5,7,8" ? "" : "Expected 1, 2, 4, 5, 7, 8."; } },

    // ── Unit 4 · Collections ──────────────────────────────────────────────
    { unit: "Collections", title: "Add up a list",
      brief: 'Make a list of <code>4, 8, 15</code>, then use <code>for each</code> to add them and print the total (<code>27</code>).',
      starter: '# Lesson 15 — lists.\n# set nums to list of 4, 8, 15\n# for each n in nums ... end\n\n',
      solution: 'set nums to list of 4, 8, 15\nset total to 0\nfor each n in nums\n    set total to total plus n\nend\nsay total',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /list of/i)) return "Make a list:  set nums to list of 4, 8, 15";
        if (!has(src, /for each/i)) return "Walk the list:  for each n in nums ... end";
        return r.output.some((l) => l.includes("27")) ? "" : "The total should be 27."; } },

    { unit: "Collections", title: "Build a list",
      brief: 'Start with an <code>empty list</code> called <code>squares</code>. Use a loop and <code>add … to squares</code> to put the squares of 1 to 5 in it, then <code>say squares</code>.',
      starter: 'set squares to empty list\n\n# Lesson 16 — add X to squares\n\n',
      solution: 'set squares to empty list\ncount i from 1 to 5\n    add i multiplied by i to squares\nend\nsay squares',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /\badd\b/i)) return "Use  add … to squares  inside a loop.";
        return lines(r).join("") === "[1, 4, 9, 16, 25]" ? "" : "It should print [1, 4, 9, 16, 25]."; } },

    { unit: "Collections", title: "Reach into a list",
      brief: 'Given <code>names</code>, print the <b>second</b> name and how many names there are, on two lines. (Lists count from 1.)',
      starter: 'set names to list of "Ada", "Grace", "Alan", "Edsger"\n\n# Lesson 17 — item 2 of names, length of names\n\n',
      solution: 'set names to list of "Ada", "Grace", "Alan", "Edsger"\nsay item 2 of names\nsay length of names',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /item\s+2\s+of/i)) return "Use  item 2 of names.";
        return lines(r).join(",") === "Grace,4" ? "" : "Expected Grace and then 4."; } },

    { unit: "Collections", title: "Statistics in one word",
      brief: 'For <code>scores</code>, print the <code>sum of</code> them, then their <code>average of</code>, then the <code>largest of</code> them — one per line.',
      starter: 'set scores to list of 90, 75, 88, 95, 60\n\n# Lesson 18 — sum of, average of, largest of\n\n',
      solution: 'set scores to list of 90, 75, 88, 95, 60\nsay sum of scores\nsay average of scores\nsay largest of scores',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /sum of/i) || !has(src, /average of/i) || !has(src, /largest of/i)) return "Use sum of, average of, and largest of.";
        return lines(r).join(",") === "408,81.6,95" ? "" : "Expected 408, 81.6 and 95."; } },

    { unit: "Collections", title: "Sort and reverse",
      brief: 'Print the list <code>5, 3, 9, 1</code> <code>sorted of</code> (smallest first), then the same list <code>reverse of</code> the sorted list.',
      starter: 'set nums to list of 5, 3, 9, 1\n\n# Lesson 19 — sorted of, reverse of\n\n',
      solution: 'set nums to list of 5, 3, 9, 1\nsay sorted of nums\nsay reverse of (sorted of nums)',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /sorted of/i) || !has(src, /reverse of/i)) return "Use sorted of and reverse of.";
        return lines(r).join("|") === "[1, 3, 5, 9]|[9, 5, 3, 1]" ? "" : "Expected [1, 3, 5, 9] and then [9, 5, 3, 1]."; } },

    { unit: "Collections", title: "Work with words",
      brief: 'Split <code>"the quick brown fox"</code> by a space to get its words, then print how many words there are (<code>4</code>) and the sentence <code>uppercase of</code>.',
      starter: 'set sentence to "the quick brown fox"\n\n# Lesson 20 — split TEXT by SEP,  length of,  uppercase of\n\n',
      solution: 'set sentence to "the quick brown fox"\nset words to split sentence by " "\nsay length of words\nsay uppercase of sentence',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /\bsplit\b/i)) return "Use  split sentence by \" \".";
        return lines(r).join("|") === "4|THE QUICK BROWN FOX" ? "" : "Expected 4 and then THE QUICK BROWN FOX."; } },

    { unit: "Collections", title: "Records",
      brief: 'Make a <code>record</code> called <code>player</code> with a <code>"name"</code> of <code>"Ada"</code> and a <code>"score"</code> of <code>10</code>. Add 5 to the score with <code>set item</code>, then print <code>Ada has 15</code>.',
      starter: '# Lesson 21 — records hold named fields.\n# set player to record with "name" as "Ada", "score" as 10\n# set item "score" of player to ...\n\n',
      solution: 'set player to record with "name" as "Ada", "score" as 10\nset item "score" of player to (item "score" of player) plus 5\nsay item "name" of player plus " has " plus item "score" of player',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /record with/i)) return "Make the record with:  record with \"name\" as …";
        return lines(r).includes("Ada has 15") ? "" : "It should print: Ada has 15"; } },

    // ── Unit 5 · Functions ────────────────────────────────────────────────
    { unit: "Functions", title: "Write a function",
      brief: 'Define a function <code>double</code> that returns its input times two, then print <code>double with 50</code> (it should be <code>100</code>).',
      starter: '# Lesson 22 — functions.\n# define double with n ... return ... end\n\n',
      solution: 'define double with n\n    return n multiplied by 2\nend\nsay double with 50',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /define\s+double\s+with/i)) return "Start with:  define double with n";
        if (!has(src, /return/i)) return "A function hands back a value with 'return'.";
        return r.output.some((l) => l.includes("100")) ? "" : "double with 50 should be 100."; } },

    { unit: "Functions", title: "More than one input",
      brief: 'Define <code>bigger with a and b</code> that returns whichever number is larger, and print <code>bigger with 7 and 12</code> (<code>12</code>).',
      starter: '# Lesson 23 — several parameters are separated by  and\n\n',
      solution: 'define bigger with a and b\n    if a is greater than b then\n        return a\n    end\n    return b\nend\nsay bigger with 7 and 12',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /define\s+bigger\s+with\s+\w+\s+and\s+\w+/i)) return "Start with:  define bigger with a and b";
        return lines(r).includes("12") ? "" : "bigger with 7 and 12 should print 12."; } },

    { unit: "Functions", title: "A function that calls itself",
      brief: 'Write a recursive <code>factorial with n</code> (n × (n−1) × … × 1; the factorial of 1 is 1) and print <code>factorial with 6</code> (<code>720</code>).',
      starter: '# Lesson 24 — recursion: a function that uses itself.\n# Remember a stopping case!\n\n',
      solution: 'define factorial with n\n    if n is at most 1 then\n        return 1\n    end\n    return n multiplied by (factorial with (n minus 1))\nend\nsay factorial with 6',
      check(r, src) { if (!r.ok) return errHint;
        const body = src.split(/define\s+factorial/i)[1] || "";
        if (!/factorial\s+with/i.test(body)) return "Your factorial should call itself.";
        return lines(r).includes("720") ? "" : "factorial with 6 should be 720."; } },

    { unit: "Functions", title: "Map, filter, reduce",
      brief: 'With the helper functions provided, print <code>map double over nums</code>, then <code>filter is_even over nums</code>, then <code>reduce combine over nums from 0</code> — three lines.',
      starter: 'define double with n\n    return n multiplied by 2\nend\ndefine is_even with n\n    return remainder of n and 2 is equal to 0\nend\ndefine combine with a and b\n    return a plus b\nend\nset nums to list of 1, 2, 3, 4, 5, 6\n\n# Lesson 25 — map FN over LIST,  filter FN over LIST,  reduce FN over LIST from START\n\n',
      solution: 'define double with n\n    return n multiplied by 2\nend\ndefine is_even with n\n    return remainder of n and 2 is equal to 0\nend\ndefine combine with a and b\n    return a plus b\nend\nset nums to list of 1, 2, 3, 4, 5, 6\nsay map double over nums\nsay filter is_even over nums\nsay reduce combine over nums from 0',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /\bmap\b/i) || !has(src, /\bfilter\b/i) || !has(src, /\breduce\b/i)) return "Use map, filter and reduce.";
        return lines(r).join("|") === "[2, 4, 6, 8, 10, 12]|[2, 4, 6]|21" ? "" : "Expected [2, 4, 6, 8, 10, 12], then [2, 4, 6], then 21."; } },

    { unit: "Functions", title: "FizzBuzz",
      brief: 'The classic! For 1 to 15 print <code>Fizz</code> for multiples of 3, <code>Buzz</code> for multiples of 5, <code>FizzBuzz</code> for both, otherwise the number.',
      starter: '# Lesson 26 — put it all together.\n# Hint: remainder of n and 3 is equal to 0\n\n',
      solution: 'count n from 1 to 15\n    if remainder of n and 15 is equal to 0 then\n        say "FizzBuzz"\n    otherwise if remainder of n and 3 is equal to 0 then\n        say "Fizz"\n    otherwise if remainder of n and 5 is equal to 0 then\n        say "Buzz"\n    otherwise\n        say n\n    end\nend',
      check(r) { if (!r.ok) return errHint;
        const want = "1,2,Fizz,4,Buzz,Fizz,7,8,Fizz,Buzz,11,Fizz,13,14,FizzBuzz";
        return lines(r).join(",") === want ? "" : "Not quite — compare with the FizzBuzz rules. Check 15 first!"; } },

    // ── Unit 6 · Drawing ──────────────────────────────────────────────────
    { unit: "Drawing", title: "Draw a square",
      brief: 'Open the <code>Drawn</code> tab. Use <code>move forward</code> and <code>turn right</code> inside a loop to draw a square.',
      starter: '# Lesson 27 — turtle drawing!\n# repeat 4 times\n#     move forward 120\n#     turn right 90\n# end\n\n',
      solution: 'repeat 4 times\n    move forward 120\n    turn right 90\nend',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /move/i)) return "Move the turtle:  move forward 120";
        return (r.turtle && r.turtle.length >= 4) ? "" : "Draw at least four sides to make a square."; } },

    { unit: "Drawing", title: "Draw a triangle",
      brief: 'A triangle has three equal sides, and the turtle turns <code>120</code> degrees at each corner. Draw one.',
      starter: '# Lesson 28 — exterior angles add up to 360.\n\n',
      solution: 'repeat 3 times\n    move forward 150\n    turn right 120\nend',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /turn\s+(right|left)\s+120/i)) return "Turn 120 degrees at each corner.";
        return (r.turtle && r.turtle.length >= 3) ? "" : "Draw three sides."; } },

    { unit: "Drawing", title: "A spiral",
      brief: 'Draw a spiral: count <code>i</code> from 1 to 40, and each time <code>move forward</code> by <code>i multiplied by 4</code> then <code>turn right 91</code>.',
      starter: '# Lesson 29 — a loop variable can change the drawing.\n\n',
      solution: 'count i from 1 to 40\n    move forward i multiplied by 4\n    turn right 91\nend',
      check(r, src) { if (!r.ok) return errHint;
        if (!has(src, /count/i)) return "Use a count loop.";
        return (r.turtle && r.turtle.length >= 40) ? "" : "It should draw 40 segments."; } },
  ];

  const api = { LESSONS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.PLAINLANG_LESSONS = LESSONS;
})(typeof window !== "undefined" ? window : globalThis);
