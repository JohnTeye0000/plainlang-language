"""
Tests for plainlocale.py: writing PlainLang in another language.

  * the shipped locale files are complete and collision-free, and stay in sync with the language
  * the validator catches each kind of mistake a translator could make
  * translation touches keywords and nothing else (strings, comments, names), including {code} in text
  * a property test: hundreds of generated programs survive English -> French -> English unchanged
  * the `plain` command-line wiring, end to end

Run with:   python test_locale.py
"""

import glob
import json
import os
import random
import subprocess
import sys
import tempfile

import fuzz
import fuzz_wasm
import plainlang as pl
import plainlocale as L

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


def run_output(src):
    out = []
    pl.run_source(src, on_output=out.append)
    return out


fr = L.load_locale("fr")

print("The shipped locales")
shipped = sorted(glob.glob(os.path.join(L.LOCALES_DIR, "*.json")))
check("there is at least the demonstration locale", any(p.endswith("demo-fr.json") for p in shipped))
for path in shipped:
    loc = L.load_locale(path)
    check(f"{os.path.basename(path)} is complete and has no collisions", L.problems(loc) == [], L.problems(loc))
check("the demo locale covers exactly the language's keywords (so a new keyword fails this until it is translated)",
      set(fr.words) == set(pl.KEYWORDS), set(fr.words) ^ set(pl.KEYWORDS))
check("the demo locale is honestly labelled as an unreviewed demonstration",
      "DEMONSTRATION" in fr.notes and "native speaker" in fr.notes)

print("The validator catches a translator's mistakes")


def with_words(**changes):
    words = dict(fr.words)
    for k, v in changes.items():
        words[k] = v
    return L.Locale("t", "test", words)


def has(loc, fragment):
    return any(fragment in p for p in L.problems(loc))


check("a missing keyword", has(L.Locale("t", "t", {k: v for k, v in fr.words.items() if k != "say"}), "missing 1 keyword(s): say"))
check("a blank value counts as missing", has(with_words(say=""), "missing 1 keyword(s): say"))
check("a key that isn't a PlainLang keyword", has(with_words(banana="banane"), "not PlainLang keywords: banana"))
check("a phrase instead of one word", has(with_words(say="dire fort"), "must be a single word"))
check("a word starting with a digit", has(with_words(say="1dire"), "must be a single word"))
check("two keywords given the same word", has(with_words(say="mettre"), "both use the word"))
check("duplicates are caught regardless of capital letters", has(with_words(say="METTRE"), "both use the word"))
check("a word that is a *different* English keyword (it would change meaning)", has(with_words(say="while"), "also the English keyword 'while'"))
check("mapping a keyword to itself is fine", not has(with_words(plus="plus"), "English keyword"))
check("the blank template fails validation, naming every keyword", len(L.problems(L.Locale("t", "t", L.template()["words"]))) >= 1
      and has(L.Locale("t", "t", L.template()["words"]), f"missing {len(pl.KEYWORDS)} keyword(s)"))
check("the template has every keyword with a blank value", L.template()["words"] == {k: "" for k in sorted(pl.KEYWORDS)})

print("Translation touches keywords and nothing else")
check("French keywords become English ones", L.to_english('dire "x"', fr) == 'say "x"')
check("keywords match whatever the capitalisation", L.to_english("SI vrai alors\nfin", fr) == "if true then\nend")
check("text in quotes is never translated", L.to_english('dire "si alors fin"', fr) == 'say "si alors fin"')
check("comments are never translated", L.to_english("dire 1 # dire si fin", fr) == "say 1 # dire si fin")
check("a # inside a string isn't a comment (so the words after it are still code)",
      L.to_english('dire "a # b" plus 1', fr) == 'say "a # b" plus 1')
check("variable and function names pass through", L.to_english("mettre prix à 5", fr) == "set prix to 5")
check("code inside {braces} in a text IS translated", L.to_english('dire "total: {a plus 1}"', fr) == 'say "total: {a plus 1}"')
check("...including French keywords in there", L.to_english('dire "{longueur de liste de 1, 2}"', fr) == 'say "{length of list of 1, 2}"')
check("{{ and }} stay literal braces, with nothing inside them translated",
      L.to_english('dire "{{si}} {si}"', fr) == 'say "{{si}} {if}"')
check("an unclosed brace is left alone for the engine to report", L.to_english('dire "a { si"', fr) == 'say "a { si"')
check("non-English text in strings is preserved exactly", L.to_english('dire "Héllo ɔ ŋ ɛ 你好"', fr) == 'say "Héllo ɔ ŋ ɛ 你好"')
check("line structure is preserved exactly, so error line numbers stay right",
      L.to_english("dire 1\n\n\ndire 2\n", fr).count("\n") == 4)
check("English keywords left in a local program still work (gentle transition)",
      L.to_english("dire 1 plus 2\nsay 3", fr) == "say 1 plus 2\nsay 3")
check("a program written in French runs and gives the right answer",
      run_output(L.to_english('définir double avec n\n    retourner n multiplié par 2\nfin\ndire double avec 21', fr)) == ["42"])

print("English -> locale")
check("English becomes French", L.to_locale('say "x"', fr) == 'dire "x"')
check("round trip on a program with strings, comments and interpolation",
      L.to_english(L.to_locale('set n to 3 # note: say\nsay "n={n plus 1} {{}}"', fr), fr) == 'set n to 3 # note: say\nsay "n={n plus 1} {{}}"')
try:
    L.to_locale("set dire to 1", fr)
    check("a program name that is a French keyword is refused rather than silently changed", False)
except L.LocaleError as e:
    check("a program name that is a French keyword is refused rather than silently changed", "dire" in str(e), str(e))
check("a name that merely contains a keyword isn't a clash", L.to_locale("set prefix to 1", fr) == "mettre prefix à 1")

print("Property test: English -> French -> English changes nothing")
checked = bad = 0
mismatch_run = []
for gen in (fuzz.Generator, fuzz_wasm.Generator):
    for k in range(250):
        src = gen(random.Random(k)).program()
        checked += 1
        french = L.to_locale(src, fr)
        if L.to_english(french, fr) != src:
            bad += 1
        elif k % 25 == 0 and run_output(L.to_english(french, fr)) != run_output(src):
            mismatch_run.append(k)
check(f"{checked} generated programs round-trip exactly through French", bad == 0, f"{bad} differed")
check("and the ones I ran behave identically", not mismatch_run, mismatch_run)
check("the French versions really are different text (the test isn't vacuous)",
      L.to_locale("define f with n\nreturn n\nend", fr) != "define f with n\nreturn n\nend")

print("Loading")
check("a bare code finds the demonstration locale", L.load_locale("fr").code == "fr")
check("an explicit path works", L.load_locale(os.path.join(L.LOCALES_DIR, "demo-fr.json")).name.startswith("Français"))
for label, thing, fragment in [("an unknown locale", "zz", "couldn't find a locale"),
                               ("a dict that isn't a locale", {"hello": 1}, "isn't a PlainLang locale file")]:
    try:
        L.load_locale(thing)
        check(f"{label} gives a clear message", False)
    except L.LocaleError as e:
        check(f"{label} gives a clear message", fragment in str(e), str(e))
tmp = tempfile.mkdtemp(prefix="loc_")
badfile = os.path.join(tmp, "bad.json")
with open(badfile, "w", encoding="utf-8") as f:
    f.write("{not json")
try:
    L.load_locale(badfile)
    check("a file that isn't JSON gives a clear message", False)
except L.LocaleError as e:
    check("a file that isn't JSON gives a clear message", "isn't valid JSON" in str(e))

print("The command line")


def plain(*args):
    p = subprocess.run([sys.executable, os.path.join(HERE, "plain.py"), *args], capture_output=True, cwd=HERE,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    out = p.stdout.decode("utf-8", "replace").replace("\r\n", "\n")     # Windows stdout writes \r\n
    return p.returncode, out, p.stderr.decode("utf-8", "replace")


french_prog = os.path.join(tmp, "salut.plang")
with open(french_prog, "w", encoding="utf-8") as f:
    f.write('mettre x à 6\ndire "x vaut {x}, double: {x multiplié par 2}"\n')
code, out, err = plain("run", "--lang", "fr", french_prog)
check("plain run --lang fr runs a French program", code == 0 and out.strip() == "x vaut 6, double: 12", (code, out, err))
check("it says it translated (errors are in English)", "translated" in err and "English" in err, err)
check("it leaves no temporary file behind", sorted(os.listdir(tmp)) == sorted(["bad.json", "salut.plang"]), os.listdir(tmp))
code, out, _ = plain("vm", "--lang", "fr", french_prog)
check("the bytecode VM reads French too", code == 0 and "x vaut 6" in out, out)
code, out, _ = plain("check", "--lang", "fr", french_prog)
check("the static checker reads French too", code == 0 and "No problems" in out, out)
code, out, _ = plain("translate", "--lang", "fr", french_prog)
check("plain translate prints the English", code == 0 and out.startswith("set x to 6"), out)
english_prog = os.path.join(tmp, "hello.plang")
with open(english_prog, "w", encoding="utf-8") as f:
    f.write('set x to 6\nsay "x is {x}"\n')
code, out, _ = plain("translate", "--lang", "fr", "--to", "fr", english_prog)
check("plain translate --to fr prints French", code == 0 and out.startswith("mettre x à 6\ndire"), out)
code, out, _ = plain("locale", "check", "demo-fr")
check("plain locale check passes the demo locale", code == 0 and "sound" in out, out)
tpl = os.path.join(tmp, "mine.json")
code, out, _ = plain("locale", "template")
with open(tpl, "w", encoding="utf-8") as f:
    f.write(out)
check("plain locale template prints valid JSON with every keyword", json.loads(out)["words"].keys() == set(pl.KEYWORDS))
code, out, _ = plain("locale", "check", tpl)
check("...and the blank template is reported as incomplete (exit 1)", code == 1 and "missing 98" in out, out)
code, out, _ = plain("run", "--lang", "zz", french_prog)
check("an unknown language gives a friendly message, exit 2", code == 2 and "Oops!" in out and "Traceback" not in out, out)
code, out, err = plain("run", "--lang", "fr")
check("--lang without a file is explained", code != 0 and "needs a program file" in (out + err), out + err)

for name in os.listdir(tmp):
    os.remove(os.path.join(tmp, name))
os.rmdir(tmp)
print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
