# PlainLang — User-Testing Plan

The goal: put PlainLang in front of real beginners, watch what happens, and come away
with **evidence** — the single most valuable thing this project can have for an
application. You don't need many people. **5–10 sessions is enough for a real story.**

---

## 0. Before you start

- **Recruit 5–10 absolute beginners** — people who have never really coded. Good sources:
  a younger sibling and their friends, a school/library coding club, students you tutor,
  neighbours' kids, a scout troop.
- **Permission:** if anyone is under 18, get a parent's or teacher's verbal OK first, and
  don't record names or faces in anything you publish — use "Student 1", "Student 2".
- **Setup:** the playground open in a browser (`playground.html`). Nothing to install.
- **Your job during a session:** *watch and take notes. Do NOT help* unless they're stuck
  for more than ~90 seconds or visibly frustrated. The struggles are the data.

Keep each session to **15–20 minutes**.

---

## 1. The session script (read/paraphrase to them)

> "This is a programming language I built called PlainLang. It's meant to read like
> English. I'm testing the *language*, not you — if anything is confusing, that's useful
> for me to know. Think out loud as you go. I'll mostly just watch."

Then give them the three tasks below, one at a time. Let them type. Stay quiet.

---

## 2. The tasks (progressive)

**Task 1 — Say something (warm-up).**
> "Make the program print:  `Hello, world!`"
*Watching for:* do they find `say`? Do they understand the quotes?

**Task 2 — A number that changes.**
> "Make a variable for your age, then print a sentence using it, like `I am 12 years old`."
*Watching for:* `set`, using the variable, `plus` to join text and a number.

**Task 3 — Repeat something.**
> "Print the numbers 1 to 5, each on its own line."
*Watching for:* do they reach for a loop (`count`/`repeat`), or copy-paste five `say`s?

**Bonus (if they're flying) — Draw.**
> "Switch to the Drawing tab. Make the turtle draw a square."

---

## 3. Observation sheet (one per student)

Copy this for each session and fill it in *as they work*:

```
Student #: ____   Age: ____   Coded before? (none / a little)

TASK 1 (say hello)        completed? Y/N    time: ___    needed help? Y/N
TASK 2 (variable)         completed? Y/N    time: ___    needed help? Y/N
TASK 3 (loop)             completed? Y/N    time: ___    needed help? Y/N
BONUS (turtle square)     completed? Y/N

Errors they hit (copy the message):
  -
  -
When an error appeared, did they FIX IT THEMSELVES using the message?   Y/N/partly
  (this is the key question — it tests whether the diagnostics actually teach)

Exact words they said when confused:
  -
  -

What made them smile / light up:
  -
```

---

## 4. Post-session survey (ask out loud, jot answers)

1. On 1–5, how easy was it to read the code? (1 = total gibberish, 5 = like English)
2. On 1–5, when you made a mistake, how helpful was the red error message?
3. What was the most confusing part?
4. Would you want to keep playing with this? Why / why not?

---

## 5. What to measure (your headline numbers)

After all sessions, total these up — *these are the sentences that go in your essay/portfolio*:

- **Task completion:** "__ of __ students completed all three tasks."
- **Self-recovery from errors:** "__ of __ error situations were fixed by the student
  *using only the message*, with no help from me." ← your strongest stat.
- **Readability score:** average of survey Q1.
- **Error-helpfulness score:** average of survey Q2.
- **The most common confusion** (you'll likely see a pattern — that becomes your next
  improvement, which is itself a great story: *"testing showed X, so I changed Y."*)

---

## 6. After testing — close the loop

Pick the **single most common stumbling block** you observed and **fix it** in the language
(a clearer error message, a better default, a new lesson). Then you can write the most
compelling sentence of all:

> *"I watched real beginners use it, found that [X] confused most of them, and changed
> [Y] — completion went from __ to __."*

That sentence — observation → change → measured improvement — is what turns a project into
something that reads like real engineering and real empathy. Save the raw notes; they're
your evidence.
