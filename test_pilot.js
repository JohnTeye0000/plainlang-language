/*
 * Tests for pilot.js (privacy-respecting pilot recording).
 *   node test_pilot.js
 */
const assert = require("assert");
const PL = require("./plainlang.js");
const Pilot = require("./pilot.js");

let pass = 0, fail = 0;
function test(name, fn) {
  try { fn(); pass++; console.log(`  ✓ ${name}`); }
  catch (e) { fail++; console.log(`  ✗ ${name}\n      ${e.message}`); }
}
function memoryStorage() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), _m: m };
}
let tick = 0;
const clock = () => `2026-10-18T10:00:${String(tick++).padStart(2, "0")}Z`;

console.log("Error classification (against the real engine's messages)");
const CASES = {
  "unknown-variable": "say scor",
  "unknown-function": "call nope with 1",
  "bad-statement-start": "5",
  "syntax-expected": "if 5 is greater 3 then\nsay 1\nend",
  "bad-symbol": "say 1 + 2",
  "unclosed-text": 'say "hello',
  "wrong-arg-count": "define f with a\nreturn a\nend\nsay f with 1 and 2",
  "no-return": "define q with n\nset x to n\nend\nsay q with 1",
  "type-math": 'say "a" minus 1',
  "type-compare": 'say 5 is greater than "five"',
  "divide-by-zero": "say 1 divided by 0",
  "list-index": "set xs to list of 1\nsay item 5 of xs",
  "record-key": 'set p to record with "a" as 1\nsay item "b" of p',
  "stop-outside-loop": "stop",
  "limit": "say power of 10 and 400",
  "interpolation": 'say "{}"',
};
for (const [kind, src] of Object.entries(CASES)) {
  test(`'${src.split("\n")[0].slice(0, 36)}' is ${kind}`, () => {
    const r = PL.run(src, { rng: () => 0.5 });
    assert.ok(!r.ok, "expected the program to fail");
    assert.strictEqual(Pilot.classifyError(r.error), kind, r.error);
  });
}
test("an unrecognised message falls into 'other', and no message into null", () => {
  assert.strictEqual(Pilot.classifyError("something entirely new"), "other");
  assert.strictEqual(Pilot.classifyError(null), null);
});
test("every category the classifier can return is declared", () => {
  for (const kind of Object.keys(CASES)) assert.ok(Pilot.CATEGORIES.includes(kind), kind);
});

console.log("Recording");
test("a session is recorded as ordered, timestamped events carrying the participant code", () => {
  const p = Pilot.create({ storage: memoryStorage(), now: clock });
  p.setParticipant("P01");
  p.sessionStart();
  p.lessonStart(3);
  p.run({ ok: false, error: "I haven't heard of a variable called 'x' yet.", errorLine: 2 }, 18, 3);
  p.run({ ok: true }, 22, 3);
  p.check(3, true);
  const d = p.export();
  assert.deepStrictEqual(d.events.map((e) => e.type), ["session_start", "lesson_start", "run", "run", "check"]);
  assert.ok(d.events.every((e) => e.participant === "P01" && /^\d{4}-/.test(e.t)));
  assert.strictEqual(d.events[2].errorKind, "unknown-variable");
  assert.strictEqual(d.events[2].errorLine, 2);
  assert.strictEqual(d.events[3].ok, true);
  assert.strictEqual(d.events[4].passed, true);
});
test("the participant code is sanitised: short, letters/digits/dash only (never a free-text name)", () => {
  const p = Pilot.create({ storage: memoryStorage(), now: clock });
  assert.strictEqual(p.setParticipant("Ama Mensah <script>"), "AmaMensahscr");
  assert.strictEqual(p.setParticipant("P-07"), "P-07");
  assert.strictEqual(p.setParticipant("x".repeat(40)).length, 12);
});
test("the program text is never recorded -- only its length", () => {
  const p = Pilot.create({ storage: memoryStorage(), now: clock });
  const secret = 'say "my name is Kwame and I live at 12 Ring Road"';
  p.run({ ok: true }, secret.length, null);
  const text = p.exportText();
  assert.ok(!/Kwame|Ring Road|my name/.test(text), "program text leaked into the export");
  assert.ok(text.includes(String(secret.length)));
});
test("an error message's own wording (which can quote a learner's variable name) is never kept", () => {
  const p = Pilot.create({ storage: memoryStorage(), now: clock });
  p.run({ ok: false, error: "I haven't heard of a variable called 'kwame_secret' yet." }, 5, null);
  assert.ok(!/kwame_secret/.test(p.exportText()));
});
test("events persist across a reload through storage", () => {
  const storage = memoryStorage();
  const a = Pilot.create({ storage, now: clock });
  a.setParticipant("P02"); a.sessionStart(); a.check(1, false);
  const b = Pilot.create({ storage, now: clock });
  assert.strictEqual(b.participant, "P02");
  assert.strictEqual(b.count(), 2);
});
test("clear() empties the log but keeps the participant code", () => {
  const p = Pilot.create({ storage: memoryStorage(), now: clock });
  p.setParticipant("P03"); p.sessionStart(); p.clear();
  assert.strictEqual(p.count(), 0);
  assert.strictEqual(p.participant, "P03");
});
test("the log is capped so a long session can't fill storage", () => {
  const p = Pilot.create({ now: clock });          // no storage: keeps this test fast
  for (let i = 0; i < 5050; i++) p.sessionStart();
  assert.strictEqual(p.count(), 5000);
});
test("corrupt or foreign storage is ignored rather than crashing", () => {
  const s = memoryStorage();
  s.setItem(Pilot.STORAGE_KEY, "{not json");
  assert.strictEqual(Pilot.create({ storage: s, now: clock }).count(), 0);
  s.setItem(Pilot.STORAGE_KEY, JSON.stringify({ format: "something-else", events: [1] }));
  assert.strictEqual(Pilot.create({ storage: s, now: clock }).count(), 0);
});
test("works with no storage at all (private browsing / blocked storage)", () => {
  const p = Pilot.create({ now: clock });
  p.sessionStart();
  assert.strictEqual(p.count(), 1);
});
test("a storage that throws on write doesn't break recording", () => {
  const bad = { getItem: () => null, setItem: () => { throw new Error("quota"); } };
  const p = Pilot.create({ storage: bad, now: clock });
  p.sessionStart();
  assert.strictEqual(p.count(), 1);
});
test("the export declares its format and version", () => {
  const d = Pilot.create({ storage: memoryStorage(), now: clock }).export();
  assert.strictEqual(d.format, "plainlang-pilot");
  assert.strictEqual(d.version, 1);
});

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
