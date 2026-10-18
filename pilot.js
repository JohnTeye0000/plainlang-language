/*
 * Pilot mode: privacy-respecting usage recording for classroom pilots.
 *
 * Off by default. When a facilitator opens the playground with ?pilot=1, this
 * records WHAT KIND of thing happened -- which lesson, did the check pass, and the
 * *category* of any error -- so a pilot produces real data (completion rates, where
 * learners get stuck, which error messages matter) without ever collecting what a
 * child typed or who they are.
 *
 * What is recorded:   timestamps, a facilitator-assigned participant code ("P01"),
 *                     lesson number, run ok/failed, error category, code LENGTH.
 * What is never kept: the program text, names, or anything typed into a prompt.
 *
 * Everything stays in this browser (localStorage). Nothing is sent anywhere; the
 * facilitator exports a JSON file and analyses it with pilot_report.py.
 *
 * Pure logic with an injected storage object, so test_pilot.js can run it in Node.
 */
(function (global) {
  "use strict";

  const FORMAT = "plainlang-pilot";
  const VERSION = 1;
  const MAX_EVENTS = 5000;   // a lesson-long session is a few hundred; each save re-serialises the log
  const STORAGE_KEY = "plainlang.pilot.v1";

  // The error message wording is stable (it is held identical across every engine and
  // pinned by tests), so a message can be bucketed into a category by its shape.
  const CATEGORIES = [
    ["unknown-variable", /haven't heard of a variable/i],
    ["unknown-function", /don't know a function/i],
    ["bad-statement-start", /don't know how to start a statement/i],
    ["syntax-expected", /I expected .* here/i],
    ["bad-symbol", /don't understand the symbol/i],
    ["unclosed-text", /missing its closing quote/i],
    ["wrong-arg-count", /expects \d+ value/i],
    ["no-return", /didn't 'return'/i],
    ["type-math", /only works with numbers|needs a (list of )?numbers?|needs a number/i],
    ["type-compare", /can't compare/i],
    ["type-other", /needs (a list|a function|text|a record)|works on|must be/i],
    ["divide-by-zero", /divide by zero|dividing by zero/i],
    ["list-index", /no item \d+|Lists start counting/i],
    ["record-key", /no key '/i],
    ["stop-outside-loop", /can only be used inside a loop/i],
    ["limit", /too big|too long/i],
    ["ran-too-long", /ran for too long|too many times/i],
    ["interpolation", /couldn't understand '\{|empty \{\}|no matching '\}'/i],
  ];

  function classifyError(message) {
    if (!message) return null;
    const text = String(message);
    for (const [name, re] of CATEGORIES) if (re.test(text)) return name;
    return "other";
  }

  function create(options) {
    const opts = options || {};
    const storage = opts.storage || null;
    const now = opts.now || (() => new Date().toISOString());
    let data = { format: FORMAT, version: VERSION, participant: "", events: [] };

    function load() {
      if (!storage) return;
      try {
        const raw = storage.getItem(STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : null;
        if (parsed && parsed.format === FORMAT && Array.isArray(parsed.events)) data = parsed;
      } catch (e) { /* unreadable storage: start fresh */ }
    }
    function save() {
      if (!storage) return;
      try { storage.setItem(STORAGE_KEY, JSON.stringify(data)); } catch (e) { /* quota/private mode */ }
    }
    function push(event) {
      data.events.push(Object.assign({ t: now(), participant: data.participant }, event));
      if (data.events.length > MAX_EVENTS) data.events.splice(0, data.events.length - MAX_EVENTS);
      save();
    }
    load();

    return {
      setParticipant(code) {
        // a short facilitator-assigned code only: letters, digits, dash -- never a free-text name
        const clean = String(code || "").replace(/[^A-Za-z0-9-]/g, "").slice(0, 12);
        data.participant = clean;
        save();
        return clean;
      },
      get participant() { return data.participant; },
      sessionStart() { push({ type: "session_start" }); },
      lessonStart(lesson) { push({ type: "lesson_start", lesson }); },
      // `result` is what PlainLang.run() returned; the program text is deliberately not taken.
      run(result, codeLength, lesson) {
        const ok = !!(result && result.ok);
        push({
          type: "run", lesson: lesson == null ? null : lesson, ok,
          errorKind: ok ? null : classifyError(result && result.error),
          errorLine: ok ? null : ((result && result.errorLine) || null),
          codeLength: codeLength | 0,
        });
      },
      check(lesson, passed) { push({ type: "check", lesson, passed: !!passed }); },
      export() { return JSON.parse(JSON.stringify(data)); },
      exportText() { return JSON.stringify(data, null, 2); },
      clear() { data = { format: FORMAT, version: VERSION, participant: data.participant, events: [] }; save(); },
      count() { return data.events.length; },
    };
  }

  const api = { create, classifyError, CATEGORIES: CATEGORIES.map((c) => c[0]), FORMAT, VERSION, STORAGE_KEY };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.PlainLangPilot = api;
})(typeof window !== "undefined" ? window : globalThis);
