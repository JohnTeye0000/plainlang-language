"""
Tests for the language specification (grammar.ebnf, plainspec.py, SPEC.md).

  1. the grammar is well-formed (every rule defined and used)
  2. the recognizer generated from it accepts what it should and rejects what it should,
     including the one context-sensitive rule and text interpolation
  3. it accepts every real program in the repository (demos, docs, lessons, fuzz corpora)
  4. differential testing: on thousands of corrupted programs, the grammar, the Python
     parser and the JavaScript parser all give the same verdict
  5. every executable example in the specification gives the stated result on the
     tree-walking interpreter, the bytecode VM and the JavaScript engine (and on
     WebAssembly where it can compile)
  6. SPEC.md is exactly what build_spec.py generates

Run with:   python test_spec.py
"""

import json
import os
import random
import shutil
import subprocess
import sys

import build_spec
import docs_content as dc
import fuzz
import fuzz_wasm
import plainlang as pl
import plainspec
import plainvm as vm
import plainwasm as pw
import spec_content as sc
import spec_fuzz

HERE = os.path.dirname(os.path.abspath(__file__))
PASS = FAIL = 0
HAVE_NODE = shutil.which("node") is not None


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


R = plainspec.Recognizer()

# ── 1 ─────────────────────────────────────────────────────────────────────────
print("The grammar itself")
rules = plainspec.load_rules()
check("it defines the expected top-level rules", {"program", "block", "statement", "expr", "primary"} <= set(rules))


def refs(node, out):
    if node[0] == "ref":
        out.add(node[1])
    elif node[0] in ("seq", "alt"):
        for n in node[1]:
            refs(n, out)
    elif node[0] in ("opt", "rep"):
        refs(node[1], out)
    return out


used = set()
for body in rules.values():
    refs(body, used)
check("every rule that is used is defined", used <= set(rules), used - set(rules))
check("every rule is used somewhere (besides the entry points)",
      set(rules) - used <= {"program", "turtle_stmt"}, set(rules) - used - {"program", "turtle_stmt"})
kw_in_grammar = set()


def kws(node):
    if node[0] == "kw":
        kw_in_grammar.add(node[1])
    elif node[0] in ("seq", "alt"):
        for n in node[1]:
            kws(n)
    elif node[0] in ("opt", "rep"):
        kws(node[1])


for body in rules.values():
    kws(body)
check("every word the grammar uses is a real keyword",
      {k for k in kw_in_grammar if k.isalpha()} <= pl.KEYWORDS, {k for k in kw_in_grammar if k.isalpha()} - pl.KEYWORDS)
check("every keyword of the language appears in the grammar (turtle words in its extension)",
      pl.KEYWORDS <= kw_in_grammar, pl.KEYWORDS - kw_in_grammar)

# ── 2 ─────────────────────────────────────────────────────────────────────────
print("What the grammar accepts and rejects")
ACCEPT = [
    ("an empty program", ""),
    ("only a comment", "# nothing here"),
    ("say a text", 'say "hi"'),
    ("set and say", "set x to 5\nsay x plus 1"),
    ("no call keyword needed", 'greet with "Bob"'),
    ("call keyword", 'call greet with "Bob"'),
    ("a bare call with no arguments", "reset"),
    ("otherwise if on one line", "if a then\nsay 1\notherwise if b then\nsay 2\nend"),
    ("an if inside otherwise", "if a then\nsay 1\notherwise\nif b then\nsay 2\nend\nend"),
    ("match with otherwise", "match x\nwhen 1 then\nsay 1\notherwise\nsay 2\nend"),
    ("match with no cases", "match x\nend"),
    ("comparison words", "say a is at least 3\nsay a is at most 3\nsay a is not equal to 3\nsay a is greater than 3\nsay a is less than 3"),
    ("a bare 'is'", "say a is 3"),
    ("'is not' alone", "say a is not 3"),
    ("contains", 'say "abc" contains "b"'),
    ("nested arithmetic", "say (1 plus 2) multiplied by minus 3 divided by 4"),
    ("unary minus chains", "say minus minus 3"),
    ("list and record literals", 'set p to record with "a" as 1, "b" as 2\nset xs to list of 1, 2, 3\nset e to empty list\nset r to empty record'),
    ("map, filter, reduce", "say map f over xs\nsay filter f over xs\nsay reduce f over xs from 0"),
    ("two-argument builtins", "say remainder of 7 and 2\nsay power of 2 and 3\nsay min of 1 and 2\nsay random between 1 and 6"),
    ("text builtins", 'say split "a b" by " "\nsay join xs by ","\nsay replace "a" by "b" in "aa"\nsay position of "a" in "abc"'),
    ("function with several parameters", "define f with a and b and c\nreturn a\nend"),
    ("function with none", "define f\nsay 1\nend"),
    ("arguments separated by and", "say f with 1 and 2 and 3"),
    ("a parenthesised boolean argument", "say f with (a and b) and c"),
    ("stop and skip", "repeat 2 times\nstop\nskip\nend"),
    ("for each", "for each x in xs\nsay x\nend"),
    ("count", "count i from 1 to 3\nsay i\nend"),
    ("add / remove / set item", "add 1 to xs\nremove item 1 from xs\nset item 1 of xs to 2"),
    ("import", 'import "a.plang"'),
    ("ask", 'ask "name?" into name'),
    ("interpolation", 'say "hi {name}, {1 plus 2}!"'),
    ("escaped braces", 'say "{{ not an expression }}"'),
    ("keywords in any case", "SAY 1\nSet X To 2"),
]
for name, src in ACCEPT:
    check(f"accepts {name}", R.accepts(src), src)
REJECT = [
    ("a statement missing its end", "if a then\nsay 1"),
    ("a dangling end", "say 1\nend"),
    ("otherwise outside an if", "otherwise\nsay 1"),
    ("a number starting a statement", "5"),
    ("an operator with no right side", "say 1 plus"),
    ("set without to", "set x 5"),
    ("count without from", "count i to 5\nend"),
    ("chained comparisons", "say 1 is less than 2 is less than 3"),
    ("'is at' with nothing after", "say a is at 3"),
    ("a keyword as a variable name", "set say to 1"),
    ("an unclosed parenthesis", "say (1 plus 2"),
    ("an unmatched brace in text", 'say "a { b"'),
    ("empty braces in text", 'say "{}"'),
    ("two expressions in braces", 'say "{1 2}"'),
    ("an incomplete expression in braces", 'say "{1 plus}"'),
    ("a symbol PlainLang doesn't have", "say 1 + 2"),
    ("a negative literal", "say -5"),
    ("a for without each", "for x in xs\nend"),
    ("remove without item", "remove 1 from xs"),
    ("a list with a trailing comma", "say list of 1, 2,"),
    ("ask without into", 'ask "q?" name'),
]
for name, src in REJECT:
    check(f"rejects {name}", not R.accepts(src), src)
check("'otherwise' + 'if' on DIFFERENT lines is not a chain (grammar has no way to end the if early)",
      not R.accepts("if a then\nsay 1\notherwise\nif b then\nsay 2\nend"))
check("turtle statements are not core syntax", not R.accepts("move forward 10"))
T = plainspec.Recognizer(turtle=True)
check("turtle statements are accepted with the extension on",
      all(T.accepts(s) for s in ("move forward 10", "move 5", "turn left 90", "turn 45", "pen up", "pen down", 'pen color to "red"', "wait 1")))

# ── 3 ─────────────────────────────────────────────────────────────────────────
print("Every real program in the repository")
corpus = {"demo.plang": open(os.path.join(HERE, "demo.plang"), encoding="utf-8").read()}
for name in ("examples/shapes/main.plang", "examples/shapes/geometry.plang"):
    corpus[name] = open(os.path.join(HERE, name), encoding="utf-8").read()
for s in dc.SECTIONS:
    for i, e in enumerate(s["examples"]):
        if e.get("run", True) or "move" not in e["code"]:
            corpus[f"docs:{s['id']}#{i}"] = e["code"]
lessons = None
if HAVE_NODE:
    proc = subprocess.run(["node", "-e", 'const L=require("./lessons.js").LESSONS;process.stdout.write(JSON.stringify(L.map(l=>[l.title,l.solution,l.starter])))'],
                          capture_output=True, cwd=HERE)
    lessons = json.loads(proc.stdout.decode("utf-8"))
    for title, solution, starter in lessons:
        corpus[f"lesson solution: {title}"] = solution
        corpus[f"lesson starter: {title}"] = starter
for k in range(150):
    corpus[f"fuzz#{k}"] = fuzz.Generator(random.Random(k)).program()
    corpus[f"fuzz_wasm#{k}"] = fuzz_wasm.Generator(random.Random(k)).program()
rejected = []
for name, src in corpus.items():
    turtle = "move " in src or "turn " in src or "pen " in src
    if not (T if turtle else R).accepts(src):
        rejected.append(name)
check(f"the grammar accepts all {len(corpus)} of them", not rejected, rejected[:5])

# ── 4 ─────────────────────────────────────────────────────────────────────────
print("Differential testing: grammar vs the Python parser vs the JavaScript parser")
mutation_corpus = [corpus["demo.plang"]] + [e["code"] for s in dc.SECTIONS for e in s["examples"] if e.get("run", True)]
mutation_corpus += [fuzz.Generator(random.Random(k)).program() for k in range(30)]
mutation_corpus += [fuzz_wasm.Generator(random.Random(k)).program() for k in range(30)]
for seed in (1, 2, 3):
    compared, bad = spec_fuzz.run(mutation_corpus, 2000, seed)
    check(f"seed {seed}: {compared} corrupted programs — all three judges agree on every one", not bad,
          "\n" + "\n".join(f"      {v}: {src[:100]!r}" for src, v in bad[:3]))

# ── 5 ─────────────────────────────────────────────────────────────────────────
print("Every executable example in SPEC.md, on every engine")
examples = [(sec["title"], ex) for sec in sc.SEMANTICS for _, exs in sec["rules"] for ex in exs]
check(f"the specification carries {len(examples)} executable examples", len(examples) >= 35, len(examples))


def run_python(code):
    out = []
    ok, _ = pl.run_source(code, on_output=out.append)
    return ok, out


def run_vm(code):
    out = []
    ok, _ = vm.run_source(code, on_output=out.append, rng=lambda: 0.5)
    return ok, out


js_results = None
if HAVE_NODE:
    script = ('const PL=require("./plainlang.js");const s=JSON.parse(require("fs").readFileSync(0,"utf8"));'
              'process.stdout.write(JSON.stringify(s.map(c=>{const r=PL.run(c,{rng:()=>0.5});return {ok:r.ok,out:r.ok?r.output:[r.error]};})));')
    proc = subprocess.run(["node", "-e", script], input=json.dumps([ex["code"] for _, ex in examples]).encode(),
                          capture_output=True, cwd=HERE)
    js_results = json.loads(proc.stdout.decode("utf-8"))


def satisfies(ok, out, ex):
    if "expect" in ex:
        return ok and out == ex["expect"]
    return (not ok) and ex["error"].lower() in "\n".join(out).lower()


for i, (title, ex) in enumerate(examples):
    label = f"[{title.split()[0]}] {ex['code'].splitlines()[0][:44]!r}"
    results = {"interpreter": run_python(ex["code"]), "vm": run_vm(ex["code"])}
    if js_results:
        results["javascript"] = (js_results[i]["ok"], js_results[i]["out"])
    if "expect" in ex and HAVE_NODE:
        try:
            wasm_out, wasm_err = pw.run_wasm(ex["code"])
            results["webassembly"] = (wasm_err is None, wasm_out)
        except (pw.WasmUnsupported, pl.PlainLangError):
            pass                               # outside the numeric core: not compared
    failing = {k: v for k, v in results.items() if not satisfies(v[0], v[1], ex)}
    check(f"{label} on {len(results)} engines", not failing,
          "".join(f"\n      {k}: ok={v[0]} out={v[1]}" for k, v in failing.items()) + f"\n      wanted: {ex.get('expect', ex.get('error'))}")

# ── 6 ─────────────────────────────────────────────────────────────────────────
print("SPEC.md")
current = open(os.path.join(HERE, "SPEC.md"), encoding="utf-8").read().replace("\r\n", "\n") if os.path.exists("SPEC.md") else ""
check("SPEC.md is exactly what build_spec.py generates", current == build_spec.generate(), "run: python build_spec.py")
check("SPEC.md embeds grammar.ebnf verbatim",
      open(os.path.join(HERE, "grammar.ebnf"), encoding="utf-8").read().rstrip("\n") in current)
check("SPEC.md lists every reserved word", all(f"`{k}`" in current for k in pl.KEYWORDS))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
