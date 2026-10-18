"""
Tests for pilot_report.py: exported pilot data -> a Markdown findings report.

Uses a small scenario whose every number is worked out by hand below, the error paths
(bad files must produce a clear message, never a traceback), and a real round trip:
the JavaScript recorder writes an export and this reads it.

Run with:   python test_pilot_report.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

import pilot_report as pr

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def ev(sec, type_, participant="P01", **kw):
    return {"t": f"2026-10-18T10:{sec // 60:02d}:{sec % 60:02d}Z", "participant": participant, "type": type_, **kw}


def export(events, participant=""):
    return {"format": "plainlang-pilot", "version": 1, "participant": participant, "events": events}


# ── the scenario ──────────────────────────────────────────────────────────────
# P01: lesson 1 started at :10, passes on their 3rd check at :150 (140 s after starting);
#      lesson 2 started at :160, checks once, never passes.
# P02: lesson 1 passes first try 30 s after starting; lesson 2 passes on the 2nd check.
P01 = [
    ev(0, "session_start"),
    ev(10, "lesson_start", lesson=1),
    ev(20, "run", lesson=1, ok=True),
    ev(60, "check", lesson=1, passed=False),
    ev(90, "run", lesson=1, ok=False, errorKind="unknown-variable", errorLine=1),
    ev(120, "check", lesson=1, passed=False),
    ev(150, "check", lesson=1, passed=True),
    ev(160, "lesson_start", lesson=2),
    ev(400, "check", lesson=2, passed=False),
]
P02 = [
    ev(0, "session_start", "P02"),
    ev(5, "lesson_start", "P02", lesson=1),
    ev(35, "check", "P02", lesson=1, passed=True),
    ev(40, "lesson_start", "P02", lesson=2),
    ev(50, "run", "P02", lesson=2, ok=False, errorKind="syntax-expected", errorLine=2),
    ev(60, "check", "P02", lesson=2, passed=False),
    ev(80, "check", "P02", lesson=2, passed=True),
]

tmp = tempfile.mkdtemp(prefix="pilot_test_")


def write(name, obj):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj))
    return path


p1 = write("pilot-P01.json", export(P01, "P01"))
p2 = write("pilot-P02.json", export(P02, "P02"))

print("The scenario's numbers, worked out by hand")
people = pr.load_exports([p1, p2])
s = pr.summarize(people)
check("two participants", sorted(s["participants"]) == ["P01", "P02"])
lesson = {l["lesson"]: l for l in s["lessons"]}
check("lesson 1: both started, both passed, 100% completion",
      (lesson[1]["started"], lesson[1]["passed"], lesson[1]["completion"]) == (2, 2, 1.0), lesson[1])
check("lesson 1: median checks to pass is median(3, 1) = 2", lesson[1]["median_attempts"] == 2, lesson[1])
check("lesson 1: median time to pass is median(140 s, 30 s) = 85 s",
      abs(lesson[1]["median_minutes"] * 60 - 85) < 1e-6, lesson[1])
check("lesson 2: 2 started, 1 passed, 50% completion",
      (lesson[2]["started"], lesson[2]["passed"], lesson[2]["completion"]) == (2, 1, 0.5), lesson[2])
check("lesson 2: P01 tried and never passed, so 'tried without passing' is 1", lesson[2]["tried_without_passing"] == 1)
check("lesson 2: the median is over those who passed (P02 needed 2 checks)", lesson[2]["median_attempts"] == 2)
check("3 runs in total (P01: one ok and one failing; P02: one failing), 2 of them failures",
      s["total_runs"] == 3 and s["failed_runs"] == 2, (s["total_runs"], s["failed_runs"]))
kinds = {e["kind"]: e for e in s["errors"]}
check("error kinds are counted, with how many learners hit each",
      kinds["unknown-variable"]["count"] == 1 and kinds["syntax-expected"]["people"] == 1, kinds)
check("shares of failures add up to 100%", abs(sum(e["share"] for e in s["errors"]) - 1.0) < 1e-9)
check("P01 passed 1 of 2 started lessons", (s["participants"]["P01"]["lessons_passed"],
                                           s["participants"]["P01"]["lessons_started"]) == (1, 2))

print("Active time ignores breaks")
sample = [{"_time": pr._parse_time(t)} for t in ("2026-10-18T10:00:00Z", "2026-10-18T10:01:40Z", "2026-10-18T10:16:40Z")]
check("100 s of work, then a 15-minute break counted as at most 5 minutes (= 400 s)",
      pr.active_seconds(sample) == 400, pr.active_seconds(sample))
check("one event (or none) is zero time", pr.active_seconds(sample[:1]) == 0 and pr.active_seconds([]) == 0)

print("The Markdown report")
md = pr.render_markdown(pr.summarize(people, {1: "Say something", 2: "Remember a value"}))
check("it names both participants and the lesson titles", "P01" in md and "P02" in md and "Say something" in md)
check("it warns that a tiny sample means observations, not rates", "only 2 participants" in md and "observations" in md)
check("it lists the lesson someone tried but didn't pass", "Someone tried but didn't pass" in md and "lesson 2 (1)" in md)
check("it ranks what took the most tries", "Took the most tries" in md)
check("it shows the error table", "unknown-variable" in md and "1 of 2" in md)
check("it explains how to read active time and the automatic starter run", "Active time" in md and "starter code" in md)
many = {f"P{i:02d}": [ev(0, "session_start", f"P{i:02d}"), ev(5, "lesson_start", f"P{i:02d}", lesson=1)] for i in range(6)}
check("with 5+ participants the small-sample warning disappears",
      "treat everything below" not in pr.render_markdown(pr.summarize(
          {k: [{**e, "_time": pr._parse_time(e["t"])} for e in v] for k, v in many.items()})))
quiet = pr.render_markdown(pr.summarize({"P09": [{**ev(0, "session_start", "P09"), "_time": pr._parse_time("2026-10-18T10:00:00Z")}]}))
check("a session with no lessons or errors still produces a sensible report",
      "No lesson activity" in quiet and "No failed runs" in quiet)

print("CSV export")
rows = pr.events_csv(people).strip().split("\n")
check("one header row plus one row per event", len(rows) == 1 + len(P01) + len(P02), len(rows))
check("the columns are the documented ones", rows[0] == "participant,t,type,lesson,ok,passed,errorKind,errorLine,codeLength")
check("events are grouped by participant and ordered in time", rows[1].startswith("P01,") and rows[1 + len(P01)].startswith("P02,"))

print("Loading")
folder = os.path.join(tmp, "folder")
os.makedirs(folder)
shutil.copy(p1, folder); shutil.copy(p2, folder)
write("folder/notes.txt", "not json, and ignored because it isn't .json")
check("a folder loads every .json file in it", sorted(pr.load_exports([folder])) == ["P01", "P02"])
a = write("deviceA.json", export([ev(0, "session_start", "P05"), ev(10, "lesson_start", "P05", lesson=1)]))
b = write("deviceB.json", export([ev(20, "check", "P05", lesson=1, passed=True)]))
merged = pr.load_exports([a, b])
check("the same participant on two devices is merged, in time order",
      list(merged) == ["P05"] and [e["type"] for e in merged["P05"]] == ["session_start", "lesson_start", "check"])
anon = write("kids-laptop-3.json", export([{"t": "2026-10-18T10:00:00Z", "type": "session_start"}]))
check("events with no participant code are labelled by their file, never dropped",
      list(pr.load_exports([anon])) == ["anonymous-kids-laptop-3"])

print("Bad input gets a clear message, never a traceback")


def refuses(path_or_paths, fragment):
    try:
        pr.load_exports(path_or_paths if isinstance(path_or_paths, list) else [path_or_paths])
        return False
    except pr.ReportError as e:
        return fragment in str(e)


check("a missing file", refuses(os.path.join(tmp, "nope.json"), "couldn't find"))
check("a file that isn't JSON", refuses(write("bad.json", "this is {not json"), "isn't valid JSON"))
check("JSON that isn't a pilot export", refuses(write("other.json", {"hello": "world"}), "isn't a PlainLang pilot export"))
check("an export with a malformed event", refuses(write("badev.json", export([{"type": "run"}])), "event I can't read"))
check("an unreadable timestamp", refuses(write("badt.json", export([{"t": "yesterday", "type": "run"}])), "timestamp"))
check("an empty folder", refuses(os.path.join(tmp, "empty") if os.makedirs(os.path.join(tmp, "empty")) is None else "", "No export files"))
check("no paths at all", refuses([], "No export files"))

print("The command line")


def cli(*args):
    proc = subprocess.run([sys.executable, os.path.join(HERE, "pilot_report.py"), *args],
                          capture_output=True, cwd=HERE)
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


code, out = cli(p1, p2)
check("it prints the report and exits 0", code == 0 and "# Pilot findings" in out, out[:200])
report_file, csv_file = os.path.join(tmp, "findings.md"), os.path.join(tmp, "events.csv")
code, out = cli(folder, "-o", report_file, "--csv", csv_file)
check("-o and --csv write files", code == 0 and os.path.exists(report_file) and os.path.exists(csv_file))
check("the written report matches what was printed", "# Pilot findings" in open(report_file, encoding="utf-8").read())
code, out = cli(os.path.join(tmp, "bad.json"))
check("a bad file exits 2 with a friendly message", code == 2 and "Oops!" in out and "Traceback" not in out, out)
code, out = cli("--help")
check("--help explains usage", code == 0 and "pilot_report.py" in out)

print("Round trip with the real JavaScript recorder")
if shutil.which("node") is None:
    print("  (node not found -- skipping)")
else:
    script = r'''
const PL = require("./plainlang.js"), Pilot = require("./pilot.js");
const p = Pilot.create({});
p.setParticipant("P42"); p.sessionStart(); p.lessonStart(1);
p.run(PL.run("say scor", {}), 8, 1);
p.check(1, false);
p.run(PL.run('say "Hello, world!"', {}), 22, 1);
p.check(1, true);
require("fs").writeFileSync(process.argv[1], p.exportText());
'''
    target = os.path.join(tmp, "from-js.json")
    proc = subprocess.run(["node", "-e", script, target], capture_output=True, cwd=HERE)
    check("the JS recorder wrote an export", proc.returncode == 0 and os.path.exists(target), proc.stderr.decode()[:300])
    real = pr.summarize(pr.load_exports([target]))
    check("the Python report reads it: lesson 1 passed on the 2nd check",
          real["lessons"][0]["passed"] == 1 and real["lessons"][0]["median_attempts"] == 2, real["lessons"])
    check("and the real engine's error was bucketed as an unknown variable",
          real["errors"][0]["kind"] == "unknown-variable", real["errors"])
    titles = pr.lesson_titles_from_js(HERE)
    check("lesson titles can be read from lessons.js", titles.get(1) == "Say something", titles)

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
