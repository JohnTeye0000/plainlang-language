/*
 * Tests for the Workbook (lessons.js): the course can't ship a lesson whose own
 * reference solution fails its checker, or whose untouched starter already
 * "passes". Every lesson's solution is run through the real engine and must
 * satisfy its check(); every starter must not.
 *
 *   node test_lessons.js
 */
const assert = require("assert");
const PL = require("./plainlang.js");
const { LESSONS } = require("./lessons.js");

let pass = 0, fail = 0;
function test(name, fn) {
  try { fn(); pass++; console.log(`  ✓ ${name}`); }
  catch (e) { fail++; console.log(`  ✗ ${name}\n      ${e.message}`); }
}

console.log("Course structure");
test("there are at least 25 lessons", () => assert.ok(LESSONS.length >= 25, LESSONS.length));
test("every lesson has all its parts", () => {
  for (const l of LESSONS) {
    for (const k of ["unit", "title", "brief", "starter", "solution"]) assert.ok(typeof l[k] === "string" && l[k].length, `${l.title}: missing ${k}`);
    assert.strictEqual(typeof l.check, "function", `${l.title}: missing check`);
  }
});
test("lesson titles are unique", () => {
  const t = LESSONS.map((l) => l.title);
  assert.strictEqual(new Set(t).size, t.length);
});
test("units are contiguous and there are several", () => {
  const seen = [];
  for (const l of LESSONS) if (seen[seen.length - 1] !== l.unit) seen.push(l.unit);
  assert.strictEqual(new Set(seen).size, seen.length, "a unit is split into pieces: " + seen.join(" / "));
  assert.ok(seen.length >= 5, seen.length);
});

console.log("Every lesson, end to end");
LESSONS.forEach((l, i) => {
  test(`lesson ${i + 1} · ${l.title}: the reference solution passes its own check`, () => {
    const r = PL.run(l.solution, { rng: () => 0.5 });
    assert.ok(r.ok, "solution failed to run:\n" + r.error);
    assert.strictEqual(l.check(r, l.solution), "", "check said: " + l.check(r, l.solution));
  });
  test(`lesson ${i + 1} · ${l.title}: the untouched starter does not pass`, () => {
    const r = PL.run(l.starter, { rng: () => 0.5 });
    assert.notStrictEqual(l.check(r, l.starter), "", "the starter already satisfies the lesson");
  });
});

console.log("Solutions are well-formed PlainLang");
test("every solution is clean under the formatter's conventions (4-space blocks)", () => {
  for (const l of LESSONS) assert.ok(!/\t/.test(l.solution), l.title + " uses tabs");
});

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
