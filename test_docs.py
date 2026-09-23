"""
Holds the documentation to account.

  * every runnable example in docs_content.py runs (or fails, if marked `error`)
  * the Python and JavaScript engines print the same thing for every example
  * every keyword in the language is mentioned somewhere in the docs
  * the built site contains what it should

Run with:   python test_docs.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import build_docs
import docs_content as content
import plainlang as pl

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


examples = [(s["id"], e) for s in content.SECTIONS for e in s["examples"]]
runnable = [(sid, e) for sid, e in examples if e.get("run", True)]

print("Examples")
with tempfile.TemporaryDirectory() as d:
    problems = build_docs.build(d)
    site = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    served = sorted(os.listdir(d))
check("every runnable example runs (or fails on purpose)", not problems, "\n".join(problems))
check(f"the guide has plenty of examples ({len(examples)})", len(examples) >= 35, len(examples))
check("some examples demonstrate errors", any(e.get("error") for _, e in examples))
check("no example is both an error and unrunnable", not any(e.get("error") and not e.get("run", True) for _, e in examples))

print("Two engines, one answer")
if shutil.which("node") is None:
    print("  (node not found — skipping the JavaScript comparison)")
else:
    payload = [e["code"] for _, e in runnable]
    script = (
        'const PL=require("./plainlang.js");const src=JSON.parse(require("fs").readFileSync(0,"utf8"));'
        'process.stdout.write(JSON.stringify(src.map(c=>{const r=PL.run(c,{rng:()=>0.5});'
        'return {ok:r.ok,out:r.output,err:r.error};})));'
    )
    proc = subprocess.run(["node", "-e", script], input=json.dumps(payload).encode(),
                          capture_output=True, cwd=HERE)
    js = json.loads(proc.stdout.decode("utf-8"))
    for (sid, e), j in zip(runnable, js):
        py_out, py_failed = build_docs.run_example(e["code"])
        if e.get("error"):
            same = py_failed and not j["ok"]
        else:
            same = (not py_failed) and j["ok"] and py_out == j["out"]
        check(f"[{sid}] {e['code'].splitlines()[0][:48]!r} agrees", same,
              f"\n      python: {py_out}\n      js:     {j['out'] or j['err']}")

print("Coverage")
prose = " ".join([s["intro"] + " ".join(e["code"] + " " + e.get("note", "") for e in s["examples"])
                  for s in content.SECTIONS])
text = re.sub(r"<[^>]+>", " ", prose).lower()
words = set(re.findall(r"[a-z_]+", text))
undocumented = sorted(k for k in pl.KEYWORDS if k not in words)
check("every keyword in the language appears in the docs", not undocumented, ", ".join(undocumented))

print("The built site")
check("it produced the docs page, the playground, the engine and the lessons",
      {"index.html", "playground.html", "plainlang.js", "lessons.js"} <= set(served), served)
check("it opts out of Jekyll processing so GitHub Pages serves files as-is", ".nojekyll" in served, served)
check("the page links to the playground", 'href="playground.html"' in site)
check("real program output is embedded", "Average: 81.6" in site)
check("code is escaped (no raw quotes from source text leak into markup)", '<code>say "Hello' not in site)
check("sections have working anchor links",
      all(f'id="{s["id"]}"' in site and f'href="#{s["id"]}"' in site for s in content.SECTIONS))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
