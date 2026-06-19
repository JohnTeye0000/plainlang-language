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
