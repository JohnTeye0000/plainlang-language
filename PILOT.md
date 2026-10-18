# Running a PlainLang pilot

A guide for a teacher, club leader or older student who wants to try PlainLang with a small
group of beginners. You don't need to know how to code. A session takes about 45 minutes.

## Before you start

- **Devices:** any computer with a modern browser. Learners install nothing. The playground works
  offline as long as `playground.html` sits in the same folder as `plainlang.js`, `lessons.js`
  and `pilot.js` — so if the internet is unreliable, copy that folder (or the built `site/`
  folder from `python plain.py docs`) onto a USB stick and open the page from there.
- **For you, afterwards:** Python 3 on one computer, to turn the exported files into a report.
- **Group size:** 3–8 learners is plenty. Pairs sharing a computer work well.
- **Permission:** if the learners are under 18, get the permission your school or club needs
  before the session. Pilot mode collects no names and no code (see below), but say plainly what
  you are doing and why.
- **Pick participant codes** ahead of time on paper: `P01`, `P02`, `P03`… Keep the sheet that
  says who is which code. **That sheet is the only link to a real person, and it never goes into
  the software.**

## What pilot mode records (and doesn't)

Open the playground with `?pilot=1` at the end of the address, e.g.
`playground.html?pilot=1`. A dark bar appears at the top.

| Recorded | Never recorded |
|---|---|
| Which lesson was opened | The program a learner typed |
| Whether each "Check my answer" passed | Their name (the code field accepts only letters, digits and `-`, max 12) |
| Whether each run worked or hit an error | What they typed into any prompt |
| The *kind* of error ("unknown variable", "missing word"…) and its line number | The error message's own wording (it can quote a learner's variable name) |
| Timestamps, and the length of the program | Anything about the device or person |

Everything stays in that one browser. Nothing is uploaded. Learners can see exactly what it says
in the bar: *"Records which lessons are tried and what kinds of errors happen — never the code or
a name."*

## Running the session

1. **Open** `playground.html?pilot=1` on each device. Type the learner's participant code into the bar.
2. **Two minutes of context, no more.** "This is a language that reads like English. There's a
   workbook of short lessons. Try them; if you're stuck, try something before asking me."
3. **Open the Workbook** (button at the top) and let them start at lesson 1.
4. **Mostly stay quiet.** The most useful data is where people get stuck *before* you help. When
   you do help, write it down on paper: lesson number, what confused them, what you said.
5. **Watch for:** words they guess that don't exist (e.g. `print`), confusion about `end`, and
   whether the red error messages help them or put them off.
6. **At the end** (5 minutes): ask each learner two things and write the answers down. *"What was
   the hardest part?"* and *"What would you tell a friend about it?"*

## After the session

1. On each device click **Export data**. A file like `plainlang-pilot-P01.json` downloads. Collect
   the files in one folder.
2. Make the report:

   ```bash
   python plain.py pilot exports/ -o findings.md --csv events.csv
   ```

   `findings.md` shows who got how far, which lessons took the most tries, how long things took,
   and which kinds of error came up. `events.csv` is the raw event list for a spreadsheet.
3. Click **Clear data** on each device so the next group starts fresh.
4. Put your handwritten notes next to the report. **The report says where people got stuck; your
   notes say why.** Both matter.

## Reading the results honestly

- With a handful of learners, the numbers are **stories, not statistics.** "3 of 5 passed lesson 4
  on the first try" is a true observation; "60% of learners can…" is not a claim the data supports.
  The report says so itself when there are fewer than five participants.
- A lesson that takes many tries might be a *hard idea*, a *confusing instruction*, or a *bad error
  message*. The error-kind table and your notes help tell them apart.
- Report what went badly as plainly as what went well. A pilot that finds three real problems is
  more valuable than one that finds none.

## What to do with what you learn

Every confusing lesson or error message is a concrete thing to fix. Fix it, run the tests
(`python run_tests.py`), and note it in `CHANGELOG.md`: "Lesson 6's instructions confused 3 of 5
learners; reworded". That trail of *observed problem → change* is the real evidence that the
project responds to the people it's for.
