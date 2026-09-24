/*
 * Test suite for the JavaScript engine (plainlang.js): the interpreter, the
 * PlainLang -> JavaScript transpiler, and the diagnostics. Runs in Node with no
 * dependencies. Exits non-zero on failure so it can gate CI.
 *
 *   node test_js.js
 */
const assert = require("assert");
const vm = require("vm");
const PL = require("./plainlang.js");

let pass = 0, fail = 0;
function test(name, fn) {
  try { fn(); pass++; console.log(`  ✓ ${name}`); }
  catch (e) { fail++; console.log(`  ✗ ${name}\n      ${e.message}`); }
}

function out(src, opts) {
  const r = PL.run(src, Object.assign({ rng: () => 0.5 }, opts || {}));
  return r;
}

// ── interpreter ──────────────────────────────────────────────────────────────
console.log("Interpreter");
test("variables & math", () => {
  assert.deepStrictEqual(out('set a to 7\nset b to 6\nsay a plus " x " plus b plus " = " plus (a multiplied by b)').output, ["7 x 6 = 42"]);
});
test("operator precedence", () => {
  assert.deepStrictEqual(out("say 2 plus 3 multiplied by 4\nsay (2 plus 3) multiplied by 4").output, ["14", "20"]);
});
test("if / otherwise chain", () => {
  assert.deepStrictEqual(out('set a to 15\nif a is at least 18 then\nsay "adult"\notherwise if a is at least 13 then\nsay "teen"\notherwise\nsay "kid"\nend').output, ["teen"]);
});
test("count up and down", () => {
  assert.deepStrictEqual(out("count i from 1 to 3\nsay i\nend").output, ["1", "2", "3"]);
  assert.deepStrictEqual(out("count i from 3 to 1\nsay i\nend").output, ["3", "2", "1"]);
});
test("count leaves last value (not overshoot)", () => {
  assert.deepStrictEqual(out("count i from 1 to 4\nend\nsay i").output, ["4"]);
});
test("while loop", () => {
  assert.deepStrictEqual(out("set x to 0\nwhile x is less than 3\nset x to x plus 1\nsay x\nend").output, ["1", "2", "3"]);
});
test("stop and skip", () => {
  assert.deepStrictEqual(out("count i from 1 to 9\nif i is equal to 3 then\nskip\nend\nif i is greater than 6 then\nstop\nend\nsay i\nend").output, ["1", "2", "4", "5", "6"]);
});
test("stop only exits inner loop", () => {
  assert.deepStrictEqual(out('count a from 1 to 2\ncount b from 1 to 9\nif b is greater than 1 then\nstop\nend\nsay a plus "-" plus b\nend\nend').output, ["1-1", "2-1"]);
});
test("stop outside a loop errors", () => {
  assert.ok(/only be used inside a loop/.test(out("say 1\nstop").error));
});
test("lists & for-each", () => {
  assert.deepStrictEqual(out("set xs to list of 4, 8, 15\nset t to 0\nfor each n in xs\nset t to t plus n\nend\nsay t").output, ["27"]);
});
test("list mutation", () => {
  assert.deepStrictEqual(out("set xs to empty list\nadd 1 to xs\nadd 2 to xs\nremove item 1 from xs\nsay xs\nsay item 1 of xs").output, ["[2]", "2"]);
});
test("functions & recursion", () => {
  assert.deepStrictEqual(out("define f with n\nif n is at most 1 then\nreturn 1\nend\nreturn n multiplied by f with (n minus 1)\nend\nsay f with 6").output, ["720"]);
});
test("multiple arguments", () => {
  assert.deepStrictEqual(out("define add2 with a and b\nreturn a plus b\nend\nsay add2 with 3 and 4").output, ["7"]);
});
test("built-ins", () => {
  assert.deepStrictEqual(out('say uppercase of "hi"\nsay round of 3.7\nsay square root of 144').output, ["HI", "4", "12"]);
});
test("records: create, read, update, keys", () => {
  const r = out('set p to record with "name" as "Al", "age" as 9\nset item "age" of p to 10\nset item "city" of p to "NYC"\nsay item "name" of p\nsay item "age" of p\nsay keys of p\nsay length of p\nsay p');
  assert.deepStrictEqual(r.output, ["Al", "10", "[name, age, city]", "3", "{name: Al, age: 10, city: NYC}"]);
});
test("records: missing key gives a suggestion", () => {
  const r = out('set p to record with "name" as "Al"\nsay item "naem" of p');
  assert.ok(/Did you mean 'name'\?/.test(r.error), r.error);
});
test("string interpolation", () => {
  assert.deepStrictEqual(out('set name to "Al"\nsay "Hi {name}!"').output, ["Hi Al!"]);
  assert.deepStrictEqual(out('set n to 10\nsay "double is {n multiplied by 2}"').output, ["double is 20"]);
  assert.deepStrictEqual(out('set xs to list of 7, 8, 9\nsay "second: {item 2 of xs}"').output, ["second: 8"]);
  assert.deepStrictEqual(out('say "a {{ and a }}"').output, ["a { and a }"]);
  assert.ok(/haven't heard of a variable/.test(out('say "hi {missing}"').error));
});
test("float formatting matches the Python engine", () => {
  // both engines round to 10 decimals — these strings are asserted identically
  // in test_plainlang.py, proving cross-engine consistency
  assert.deepStrictEqual(out("say 10 divided by 3").output, ["3.3333333333"]);
  assert.deepStrictEqual(out("say average of (list of 2, 4, 5)").output, ["3.6666666667"]);
  assert.deepStrictEqual(out("say 7 divided by 2").output, ["3.5"]);
});
test("numbers & lists toolbox", () => {
  assert.deepStrictEqual(out('say sum of (list of 5, 2, 8, 1)').output, ["16"]);
  assert.deepStrictEqual(out('say average of (list of 2, 4, 6)').output, ["4"]);
  assert.deepStrictEqual(out('say smallest of (list of 5, 2, 8)\nsay largest of (list of 5, 2, 8)').output, ["2", "8"]);
  assert.deepStrictEqual(out('say sorted of (list of 10, 2, 33, 4)').output, ["[2, 4, 10, 33]"]);
  assert.deepStrictEqual(out('say sorted of (list of "pear", "apple", "fig")').output, ["[apple, fig, pear]"]);
  assert.deepStrictEqual(out('say reverse of (list of 1, 2, 3)\nsay reverse of "hi"').output, ["[3, 2, 1]", "ih"]);
  assert.deepStrictEqual(out('say remainder of 17 and 5\nsay remainder of 10 and 5').output, ["2", "0"]);
});
test("equality never errors across types, ordering still does", () => {
  // regression: compare() previously never checked types at all (no error for
  // 'is greater than' on mismatched types) AND used reference equality for
  // lists/records (structurally-identical lists compared unequal)
  assert.deepStrictEqual(out('say 16 is equal to "hi"\nsay 16 is not equal to "hi"').output, ["false", "true"]);
  assert.deepStrictEqual(
    out('set a to list of 1, 2\nset b to list of 1, 2\nsay a is equal to b\n' +
        'set p to record with "x" as 1\nset q to record with "x" as 1\nsay p is equal to q').output,
    ["true", "true"]);
  assert.ok(/can't compare/.test(out('say 5 is greater than "five"').error));
});
test("an if on the line after 'otherwise' is a nested statement, not an else-if chain", () => {
  assert.deepStrictEqual(
    out('set ok to true\nif false then\nsay "a"\notherwise\nif ok then\nsay "inner"\nend\nsay "after"\nend').output,
    ["inner", "after"]);
  assert.deepStrictEqual(
    out('if false then\nsay 1\notherwise if true then\nsay "chain"\notherwise\nsay 3\nend').output, ["chain"]);
});
test("rounding is half away from zero (matches the Python engines)", () => {
  assert.deepStrictEqual(out('say round of 2.5\nsay round of 3.5\nsay round of (minus 2.5)\nsay round of 2.4').output,
    ["3", "4", "-3", "2"]);
});
test("numbers never print in scientific notation", () => {
  assert.deepStrictEqual(
    out('say 1 divided by 1000000\nsay 1 divided by 1000000000000\nsay 5 divided by 100000000000').output,
    ["0.000001", "0", "0.0000000001"]);
});
test("numbers are doubles: big values print exact digits, overflow is a friendly error", () => {
  assert.deepStrictEqual(out("say power of 2 and 100\nsay power of 2 and 60").output,
    ["1267650600228229401496703205376", "1152921504606846976"]);
  assert.deepStrictEqual(out("say 9007199254740993").output, ["9007199254740992"]);
  assert.deepStrictEqual(out("say remainder of (power of 2 and 100) and 7").output, ["2"]);
  assert.ok(/too big/.test(out("say power of 10 and 400").error));
  assert.ok(/too big/.test(out("set x to 10\nrepeat 400 times\nset x to x multiplied by 10\nend\nsay x").error));
});
test("replace is sized before it is built", () => {
  assert.ok(/too long/.test(out('set t to "aaaaaaaaaa"\nrepeat 20 times\nset t to t plus t\nend\nset u to "xxxxxxxxxx"\nrepeat 5 times\nset u to u plus u\nend\nsay length of (replace "a" by u in t)').error));
});
test("lists have a ceiling and join is sized before it is built", () => {
  assert.ok(/list is too long/.test(out('set xs to list of 1\nrepeat 30 times\nset xs to xs plus xs\nend\nsay length of xs').error));
  assert.ok(/text is too long/.test(out('set s to "abcdefghij"\nrepeat 20 times\nset s to s plus s\nend\nsay length of (join (list of 1, 2, 3, 4, 5, 6, 7, 8, 9, 10) by s)').error));
  assert.deepStrictEqual(out('say join (list of 1, 2, 3) by "-"').output, ["1-2-3"]);
});
test("replacing empty text is an error; text has a ceiling", () => {
  assert.ok(/can't be empty/.test(out('say replace "" by "x" in "abc"').error));
  assert.ok(/too long/.test(out('set t to "abcdefghij"\nrepeat 30 times\nset t to t plus t\nend\nsay length of t').error));
});
test("junk after the value inside braces is rejected", () => {
  assert.ok(/after the value/.test(out('say "{1 2}"').error));
  assert.deepStrictEqual(out('say "sum {1 plus 2}!"').output, ["sum 3!"]);
});
test("power rejects zero-to-negative and negative-to-fractional", () => {
  assert.ok(/negative power/.test(out('say power of 0 and (minus 1)').error));
  assert.ok(/fractional power/.test(out('say power of (minus 8) and 0.5').error));
});
test("more math: floor, ceiling, power, min, max", () => {
  const r = out('say floor of 3.7\nsay ceiling of 3.2\nsay floor of (minus 3.2)\nsay ceiling of (minus 3.7)\nsay power of 2 and 10\nsay min of 4 and 9\nsay max of 4 and 9');
  assert.deepStrictEqual(r.output, ["3", "4", "-4", "-3", "1024", "4", "9"]);
});
test("more math transpiles to native JS", () => {
  const js = PL.compile('say power of 2 and 10\nsay min of 4 and 9\nsay floor of 3.7');
  assert.ok(js.includes("Math.pow(2, 10)"));
  assert.ok(js.includes("Math.min(4, 9)"));
  assert.ok(js.includes("Math.floor(3.7)"));
});
test("round/absolute/remainder reject non-numbers with a friendly error", () => {
  // regression: these used to call Math.round/Math.abs/Math.trunc directly on
  // the argument, so bad input fell through as NaN/silent instead of erroring
  assert.ok(/only works with numbers/.test(out('say round of "hi"').error));
  assert.ok(/only works with numbers/.test(out('say absolute of "hi"').error));
  assert.ok(/only works with numbers/.test(out('say remainder of "hi" and 2').error));
});
test("error line survives a function call", () => {
  // regression: an error later in the same expression as a function call used
  // to be blamed on a line inside the function body, not the real call site
  const r = out('define double with n\nreturn n multiplied by 2\nend\nsay (double with 5) plus (remainder of 1 and 0)');
  assert.ok(/line 4/.test(r.error), r.error);
});
test("pattern matching", () => {
  const m = 'match n\nwhen 1 then\nsay "one"\nwhen 2 then\nsay "two"\notherwise\nsay "many"\nend';
  assert.deepStrictEqual(out('set n to 1\n' + m).output, ["one"]);
  assert.deepStrictEqual(out('set n to 2\n' + m).output, ["two"]);
  assert.deepStrictEqual(out('set n to 7\n' + m).output, ["many"]);
  assert.deepStrictEqual(out('set light to "green"\nmatch light\nwhen "red" then\nsay "stop"\nwhen "green" then\nsay "go"\nend').output, ["go"]);
});
test("text library: split, join, trim, replace, position, contains", () => {
  assert.deepStrictEqual(out('say split "a,b,c" by ","').output, ["[a, b, c]"]);
  assert.deepStrictEqual(out('say join (list of "a", "b") by "-"').output, ["a-b"]);
  assert.deepStrictEqual(out('say trim of "  hi  "').output, ["hi"]);
  assert.deepStrictEqual(out('say replace "o" by "0" in "foo"').output, ["f00"]);
  assert.deepStrictEqual(out('say position of "b" in "abc"\nsay position of "z" in "abc"').output, ["2", "0"]);
  assert.deepStrictEqual(out('say "hello" contains "ell"\nsay (list of 1, 2, 3) contains 2').output, ["true", "true"]);
});
test("map / filter / reduce", () => {
  const prelude = 'define double with n\nreturn n multiplied by 2\nend\ndefine big with n\nreturn n is greater than 3\nend\ndefine combine with a and b\nreturn a plus b\nend\n';
  assert.deepStrictEqual(out(prelude + 'say map double over (list of 1, 2, 3)').output, ["[2, 4, 6]"]);
  assert.deepStrictEqual(out(prelude + 'say filter big over (list of 1, 5, 2, 9)').output, ["[5, 9]"]);
  assert.deepStrictEqual(out(prelude + 'say reduce combine over (list of 1, 2, 3, 4) from 0').output, ["10"]);
});
test("first-class functions: store, pass, display", () => {
  const r = out('define double with n\nreturn n multiplied by 2\nend\ndefine apply_twice with f and x\nreturn f with (f with x)\nend\nset op to double\nsay op with 10\nsay apply_twice with double and 5\nsay double');
  assert.deepStrictEqual(r.output, ["20", "20", "function double"]);
});
test("turtle produces drawing segments", () => {
  const r = out("repeat 4 times\nmove forward 100\nturn right 90\nend");
  assert.strictEqual(r.turtle.length, 4);
});
test("execution trace is recorded", () => {
  const r = out("set x to 1\nset y to 2\nsay x plus y");
  assert.ok(r.trace.length > 0);
});

// ── transpiler: generated JS must run and match the interpreter ──────────────
console.log("Transpiler");
function runJS(js) {
  const captured = [];
  vm.runInNewContext(js, { console: { log: (...a) => captured.push(a.join(" ")) }, Math });
  return captured;
}
for (const [name, src] of Object.entries({
  "vars": 'set a to 7\nsay a multiplied by 6',
  "loops": "count i from 1 to 5\nsay i\nend",
  "recursion": "define f with n\nif n is at most 1 then\nreturn 1\nend\nreturn n multiplied by f with (n minus 1)\nend\nsay f with 5",
  "records": 'set p to record with "a" as 1, "b" as 2\nset item "c" of p to 3\nsay item "b" of p\nsay length of p\nsay keys of p\nsay p',
  "stop/skip": "count i from 1 to 9\nif i is equal to 3 then\nskip\nend\nif i is greater than 6 then\nstop\nend\nsay i\nend",
})) {
  test(`transpiled JS matches interpreter: ${name}`, () => {
    const interp = out(src).output;
    const compiled = runJS(PL.compile(src));
    assert.deepStrictEqual(compiled, interp);
  });
}

// ── diagnostics ──────────────────────────────────────────────────────────────
console.log("Diagnostics");
test("undefined variable gets a caret + suggestion", () => {
  const r = out("set score to 1\nsay scor");
  assert.ok(/\^\^\^\^/.test(r.error), "expected a caret underline");
  assert.ok(/Did you mean 'score'\?/.test(r.error), "expected a suggestion");
});
test("mistyped keyword is caught", () => {
  const r = out('saay "hello"');
  assert.ok(/Did you mean 'say'\?/.test(r.error));
});
test("suggest() is deterministic", () => {
  assert.strictEqual(PL.suggest("aa", ["ab", "ac"]), PL.suggest("aa", ["ac", "ab"]));
});

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
