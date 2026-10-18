"""
pilot_report -- turn exported pilot data into findings.

After a pilot session, each browser exports a JSON file (the "Export data" button in
pilot mode, see pilot.js). This reads one or more of those files and prints a Markdown
report: who took part, how far they got, which lessons were hard, how long things took,
and which kinds of error learners hit -- the numbers the findings template asks for.

    python pilot_report.py pilot-P01.json pilot-P02.json
    python pilot_report.py exports/                    # every .json in a folder
    python pilot_report.py exports/ -o findings.md --csv events.csv

Honest by construction: it reports counts, not conclusions, and says so when the sample
is too small to mean much. The data holds no code and no names (see pilot.js), so
nothing here can identify a learner; participants are the facilitator's own codes.

Also available as:  python plain.py pilot ...
"""

import csv
import io
import json
import os
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime

FORMAT = "plainlang-pilot"
IDLE_CAP_SECONDS = 300      # a gap longer than this is a break, not time spent working
SMALL_SAMPLE = 5


class ReportError(Exception):
    """The input isn't usable pilot data. The message is meant to be shown as-is."""


def _parse_time(text):
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        raise ReportError(f"I couldn't read the timestamp {text!r}; is this a PlainLang pilot export?")


def load_exports(paths):
    """Read export files (or folders of them). Returns {participant: [events sorted by time]}.
    Events from the same participant code across several files are merged."""
    files = []
    for path in paths:
        if os.path.isdir(path):
            files += sorted(os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith(".json"))
        else:
            files.append(path)
    if not files:
        raise ReportError("No export files found. Pass one or more pilot .json files, or a folder of them.")
    by_participant = defaultdict(list)
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise ReportError(f"I couldn't find '{path}'.")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ReportError(f"'{path}' isn't valid JSON, so it can't be a pilot export.")
        if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("events"), list):
            raise ReportError(f"'{path}' isn't a PlainLang pilot export (expected format '{FORMAT}').")
        fallback = "anonymous-" + os.path.splitext(os.path.basename(path))[0]
        for e in data["events"]:
            if not isinstance(e, dict) or "t" not in e or "type" not in e:
                raise ReportError(f"'{path}' has an event I can't read: {e!r}")
            who = e.get("participant") or data.get("participant") or fallback
            by_participant[who].append({**e, "participant": who, "_time": _parse_time(e["t"])})
    for events in by_participant.values():
        events.sort(key=lambda e: e["_time"])
    return dict(by_participant)


def active_seconds(events):
    """Time spent working: the gaps between consecutive events, each capped so a break
    (or a laptop left open overnight) doesn't count as effort."""
    total = 0.0
    for a, b in zip(events, events[1:]):
        total += min((b["_time"] - a["_time"]).total_seconds(), IDLE_CAP_SECONDS)
    return total


def _per_lesson_for_participant(events):
    """{lesson: {'started': t, 'checks': n, 'passed_at_check': k or None, 'seconds_to_pass': s or None}}"""
    lessons = {}
    for e in events:
        n = e.get("lesson")
        if n is None:
            continue
        rec = lessons.setdefault(n, {"started": None, "checks": 0, "passed_at_check": None, "seconds_to_pass": None})
        if e["type"] == "lesson_start" and rec["started"] is None:
            rec["started"] = e["_time"]
        elif e["type"] == "check":
            if rec["started"] is None:
                rec["started"] = e["_time"]
            rec["checks"] += 1
            if e.get("passed") and rec["passed_at_check"] is None:
                rec["passed_at_check"] = rec["checks"]
                rec["seconds_to_pass"] = (e["_time"] - rec["started"]).total_seconds()
    return lessons


def summarize(by_participant, lesson_titles=None):
    people = {}
    lesson_table = defaultdict(lambda: {"started": 0, "passed": 0, "attempts": [], "seconds": [], "gave_up": 0})
    error_counts = Counter()
    error_people = defaultdict(set)
    total_runs = failed_runs = 0
    for who, events in by_participant.items():
        runs = [e for e in events if e["type"] == "run"]
        failed = [e for e in runs if not e.get("ok")]
        total_runs += len(runs)
        failed_runs += len(failed)
        for e in failed:
            kind = e.get("errorKind") or "other"
            error_counts[kind] += 1
            error_people[kind].add(who)
        per = _per_lesson_for_participant(events)
        for n, rec in per.items():
            row = lesson_table[n]
            row["started"] += 1
            if rec["passed_at_check"] is not None:
                row["passed"] += 1
                row["attempts"].append(rec["passed_at_check"])
                row["seconds"].append(rec["seconds_to_pass"])
            elif rec["checks"] > 0:
                row["gave_up"] += 1
        people[who] = {
            "events": len(events),
            "runs": len(runs),
            "failed_runs": len(failed),
            "lessons_started": len(per),
            "lessons_passed": sum(1 for r in per.values() if r["passed_at_check"] is not None),
            "active_minutes": active_seconds(events) / 60,
            "first": events[0]["_time"] if events else None,
        }
    lessons = []
    for n in sorted(lesson_table):
        row = lesson_table[n]
        lessons.append({
            "lesson": n,
            "title": (lesson_titles or {}).get(n),
            "started": row["started"],
            "passed": row["passed"],
            "completion": row["passed"] / row["started"] if row["started"] else 0.0,
            "median_attempts": statistics.median(row["attempts"]) if row["attempts"] else None,
            "median_minutes": statistics.median(row["seconds"]) / 60 if row["seconds"] else None,
            "tried_without_passing": row["gave_up"],
        })
    errors = [{"kind": k, "count": c, "people": len(error_people[k]),
               "share": c / failed_runs if failed_runs else 0.0}
              for k, c in error_counts.most_common()]
    return {
        "participants": people,
        "lessons": lessons,
        "errors": errors,
        "total_runs": total_runs,
        "failed_runs": failed_runs,
    }


def _pct(x):
    return f"{round(x * 100)}%"


def render_markdown(summary):
    people, lessons, errors = summary["participants"], summary["lessons"], summary["errors"]
    n = len(people)
    out = ["# Pilot findings", ""]
    out.append(f"**{n} participant{'s' if n != 1 else ''}**, {summary['total_runs']} program runs "
               f"({summary['failed_runs']} ended in an error"
               + (f", {_pct(summary['failed_runs'] / summary['total_runs'])}" if summary["total_runs"] else "") + ").")
    if n < SMALL_SAMPLE:
        out += ["", f"> ⚠ With only {n} participant{'s' if n != 1 else ''}, treat everything below as "
                    "*observations*, not rates. These are stories about a few learners, not statistics."]
    out += ["", "## Participants", "",
            "| Participant | Lessons passed / started | Active time | Runs | Runs with an error |",
            "|---|---|---|---|---|"]
    for who in sorted(people):
        p = people[who]
        out.append(f"| {who} | {p['lessons_passed']} / {p['lessons_started']} | {p['active_minutes']:.0f} min "
                   f"| {p['runs']} | {p['failed_runs']} |")
    out += ["", "## Lessons", ""]
    if not lessons:
        out.append("_No lesson activity was recorded._")
    else:
        out += ["| Lesson | Started | Passed | Completion | Median checks to pass | Median time to pass | Tried, never passed |",
                "|---|---|---|---|---|---|---|"]
        for l in lessons:
            label = f"{l['lesson']}" + (f" · {l['title']}" if l["title"] else "")
            attempts = f"{l['median_attempts']:g}" if l["median_attempts"] is not None else "—"
            minutes = f"{l['median_minutes']:.1f} min" if l["median_minutes"] is not None else "—"
            out.append(f"| {label} | {l['started']} | {l['passed']} | {_pct(l['completion'])} | {attempts} | {minutes} "
                       f"| {l['tried_without_passing']} |")
        hard = [l for l in lessons if l["median_attempts"] is not None and l["median_attempts"] > 1]
        hard.sort(key=lambda l: (-l["median_attempts"], l["lesson"]))
        stuck = [l for l in lessons if l["tried_without_passing"] > 0]
        out += [""]
        if hard:
            out.append("**Took the most tries:** " + ", ".join(
                f"lesson {l['lesson']} ({l['median_attempts']:g} checks)" for l in hard[:3]) + ".")
        if stuck:
            out.append("**Someone tried but didn't pass:** " + ", ".join(
                f"lesson {l['lesson']} ({l['tried_without_passing']})" for l in stuck) + ".")
        if not hard and not stuck:
            out.append("Every lesson that was attempted was passed on the first check.")
    out += ["", "## What went wrong when programs failed", ""]
    if not errors:
        out.append("_No failed runs were recorded._")
    else:
        out += ["| Kind of error | Times | Learners affected | Share of failures |", "|---|---|---|---|"]
        for e in errors:
            out.append(f"| {e['kind']} | {e['count']} | {e['people']} of {n} | {_pct(e['share'])} |")
        out += ["", "_Each kind maps to one of PlainLang's teaching error messages; the most common are the "
                    "ones worth improving first._"]
    out += ["", "## Notes on reading this", "",
            f"- **Active time** counts the gaps between actions, each capped at {IDLE_CAP_SECONDS // 60} minutes, so a "
            "break isn't counted as effort.",
            "- Opening a lesson runs its starter code once, so a lesson's first run is automatic, not an attempt; "
            "'checks' are the real attempts.",
            "- No program text or names are recorded, so this report can say *where* learners got stuck, "
            "not exactly *what they typed*. Pair it with your own observation notes."]
    return "\n".join(out) + "\n"


def events_csv(by_participant):
    buf = io.StringIO()
    cols = ["participant", "t", "type", "lesson", "ok", "passed", "errorKind", "errorLine", "codeLength"]
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    rows = [e for events in by_participant.values() for e in events]
    rows.sort(key=lambda e: (e["participant"], e["_time"]))
    for e in rows:
        w.writerow(["" if e.get(c) is None else e.get(c) for c in cols])
    return buf.getvalue()


def lesson_titles_from_js(here=None):
    """Lesson titles from lessons.js, if node is available (a nicety; the report works without)."""
    here = here or os.path.dirname(os.path.abspath(__file__))
    try:
        proc = subprocess.run(
            ["node", "-e", 'const L=require("./lessons.js").LESSONS;process.stdout.write(JSON.stringify(L.map(l=>l.title)))'],
            capture_output=True, cwd=here, timeout=15)
        if proc.returncode == 0:
            return {i + 1: t for i, t in enumerate(json.loads(proc.stdout.decode("utf-8")))}
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return {}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    paths, out_path, csv_path = [], None, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "-o" and i + 1 < len(argv):
            out_path = argv[i + 1]; i += 2
        elif a == "--csv" and i + 1 < len(argv):
            csv_path = argv[i + 1]; i += 2
        else:
            paths.append(a); i += 1
    try:
        by_participant = load_exports(paths)
        report = render_markdown(summarize(by_participant, lesson_titles_from_js()))
    except ReportError as e:
        print(f"\n  Oops! {e}")
        return 2
    if csv_path:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            f.write(events_csv(by_participant))
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(report)
        print(f"wrote {out_path}")
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
