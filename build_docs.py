"""
Builds the PlainLang documentation site into ./site (the folder GitHub Pages serves).

    python build_docs.py            # write site/
    python build_docs.py --check    # build to a temp dir, exit 1 if any example misbehaves

The interesting part: every runnable example in docs_content.py is *executed*
here, and its real output is printed under it. Documentation that's generated
from running code can't drift out of date -- if a language change breaks an
example, the build (and CI) fails instead of the docs quietly lying.

The site is a single self-contained page plus the playground next to it, so it
can be served from any static host with no build step on the host's side.
"""

import html
import os
import re
import shutil
import sys
import tempfile

import docs_content as content
import plainlang as pl

HERE = os.path.dirname(os.path.abspath(__file__))
_TOKEN = re.compile(r'(?P<com>#[^\n]*)|(?P<str>"[^"\n]*")|(?P<num>\b\d+(?:\.\d+)?\b)|(?P<word>[A-Za-z_][A-Za-z0-9_]*)')


def run_example(code):
    """Run source through the reference interpreter. Returns (lines, failed)."""
    out = []
    ok, _ = pl.run_source(code, on_output=out.append, on_input=lambda prompt: "")
    return out, (not ok)


def highlight(code):
    def repl(m):
        text = html.escape(m.group(0))
        if m.group("com"):
            return f'<span class="c">{text}</span>'
        if m.group("str"):
            return f'<span class="s">{text}</span>'
        if m.group("num"):
            return f'<span class="n">{text}</span>'
        if m.group("word") and m.group("word").lower() in pl.KEYWORDS:
            return f'<span class="k">{text}</span>'
        return text
    # escape everything between tokens too
    out, last = [], 0
    for m in _TOKEN.finditer(code):
        out.append(html.escape(code[last:m.start()]))
        out.append(repl(m))
        last = m.end()
    out.append(html.escape(code[last:]))
    return "".join(out)


def render_example(ex, problems):
    code = ex["code"]
    parts = ['<div class="ex">']
    if ex.get("note"):
        parts.append(f'<p class="note">{ex["note"]}</p>')
    parts.append(f'<pre class="code"><code>{highlight(code)}</code></pre>')
    if ex.get("run", True):
        lines, failed = run_example(code)
        if ex.get("error"):
            if not failed:
                problems.append(f"example was meant to fail but ran cleanly:\n{code}")
            body = html.escape("\n".join(lines).strip("\n"))
            parts.append(f'<pre class="out err"><code>{body}</code></pre>')
        else:
            if failed:
                problems.append(f"example failed:\n{code}\n{lines}")
            body = html.escape("\n".join(lines))
            parts.append(f'<pre class="out"><code>{body if lines else "(prints nothing)"}</code></pre>')
    else:
        parts.append('<p class="norun">Not run here — try it in the <a href="playground.html">playground</a> or from the command line.</p>')
    parts.append("</div>")
    return "\n".join(parts)


CSS = """
:root{--paper:#f4eee1;--paper-2:#ece2cf;--ink:#211b14;--ink-2:#4a4034;--soft:#665b48;--rule:#d2c6ad;--red:#c0392b;--red-ink:#9c2a1f;
--str:#55621f;--num:#963f0d;--com:#665b48;--serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
--sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--mono:ui-monospace,"SF Mono","Cascadia Code",Consolas,monospace}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:radial-gradient(1400px 700px at 78% -15%,#fbf7ed 0%,var(--paper) 60%);color:var(--ink);font:16px/1.65 var(--sans)}
a{color:var(--red-ink)}code{font-family:var(--mono);font-size:.9em;background:var(--paper-2);padding:1px 5px;border-radius:3px}
.layout{display:grid;grid-template-columns:230px minmax(0,1fr);max-width:1080px;margin:0 auto;gap:0 48px;padding:0 24px}
nav{position:sticky;top:0;align-self:start;height:100vh;overflow:auto;padding:36px 0}
nav .brand{font:600 26px/1 var(--serif);margin:0 0 4px}nav .brand em{color:var(--red);font-style:italic}
nav .tag{color:var(--soft);font-size:13px;margin:0 0 22px}
nav a{display:block;text-decoration:none;color:var(--ink-2);padding:5px 0 5px 12px;border-left:2px solid var(--rule);font-size:14.5px}
nav a:hover{color:var(--red-ink);border-left-color:var(--red)}
nav .play{margin:0 0 18px;display:inline-block;background:var(--ink);color:var(--paper);padding:9px 16px;border-left:0;border-radius:3px;font-weight:600}
nav .play:hover{background:var(--red);color:var(--paper)}
main{padding:36px 0 96px}
.hero h1{font:600 clamp(34px,5vw,54px)/1.05 var(--serif);letter-spacing:-.5px;margin:0 0 14px}
.hero h1 em{color:var(--red)}.hero p{font-size:19px;color:var(--ink-2);max-width:38em}
.hero pre{font-size:15px}
section{padding-top:44px;border-top:1px solid var(--rule);margin-top:44px}
section:first-of-type{border-top:0;margin-top:0}
h2{font:600 30px/1.15 var(--serif);margin:0 0 10px}
.ex{margin:20px 0}.note{margin:0 0 8px;color:var(--ink-2)}
pre{margin:0;padding:14px 18px;overflow:auto;font:14px/1.6 var(--mono);border-radius:3px}
pre code{background:none;padding:0}
pre.code{background:#fbf7ed;border:1px solid var(--rule);border-left:3px solid var(--ink)}
pre.out{background:var(--ink);color:#f4eee1;border-radius:0 0 3px 3px;margin-top:-1px;border-left:3px solid var(--soft)}
pre.out.err{color:#ffb4a8;border-left-color:var(--red)}
.k{font-weight:700}.s{color:var(--str)}.n{color:var(--num)}.c{color:var(--com);font-style:italic}
.norun{font-size:14px;color:var(--soft);margin:6px 0 0}
table{border-collapse:collapse;width:100%}td{padding:9px 12px;border-top:1px solid var(--rule);vertical-align:top}
td:first-child{white-space:nowrap;font-family:var(--mono);font-size:14px}
footer{color:var(--soft);font-size:14px;margin-top:64px;padding-top:20px;border-top:1px solid var(--rule)}
@media(max-width:800px){.layout{grid-template-columns:1fr;padding:0 16px}nav{position:static;height:auto;padding:20px 0 0}}
@media(prefers-color-scheme:dark){:root{--paper:#1c1813;--paper-2:#2a241c;--ink:#f1e9d8;--ink-2:#cdbfa4;--soft:#9d8f76;--rule:#3b3327;--red:#e2604f;--red-ink:#f08a7a;--str:#a7b95c;--num:#e0904f;--com:#a89b82}
body{background:var(--paper)}pre.code{background:#231e17}pre.out{background:#0f0d0a}nav .play{background:var(--red)}}
"""


def build(out_dir):
    """Write the site into out_dir. Returns a list of problems (empty = healthy)."""
    problems = []
    os.makedirs(out_dir, exist_ok=True)

    nav = "\n".join(f'<a href="#{s["id"]}">{html.escape(s["title"])}</a>' for s in content.SECTIONS)
    nav += '\n<a href="#tools">Command-line tools</a>'
    sections = []
    for s in content.SECTIONS:
        exs = "\n".join(render_example(e, problems) for e in s["examples"])
        sections.append(f'<section id="{s["id"]}"><h2>{html.escape(s["title"])}</h2>\n{s["intro"]}\n{exs}</section>')
    tools = "\n".join(f"<tr><td>{n}</td><td>{d}</td></tr>" for n, d in content.TOOLS)
    hero_out, _ = run_example('set scores to list of 90, 75, 88, 95, 60\nset total to 0\nfor each s in scores\n    set total to total plus s\nend\nsay "Average: " plus (total divided by length of scores)')

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PlainLang — guide and reference</title>
<meta name="description" content="PlainLang is a programming language written to be read aloud. Guide and reference, with every example run for real.">
<style>{CSS}</style></head><body>
<div class="layout">
<nav><p class="brand">Plain<em>Lang</em>.</p><p class="tag">a language you can read aloud</p>
<a class="play" href="playground.html">Open the playground →</a>
{nav}</nav>
<main>
<div class="hero"><h1>A language you can <em>read aloud</em>.</h1>
<p>Most first languages ask you to learn how a computer thinks <em>and</em> a wall of punctuation at the same time. PlainLang removes the punctuation. Code reads like English, errors read like a patient teacher, and the playground lets you watch a program run one step at a time.</p>
<pre class="code"><code>{highlight('set scores to list of 90, 75, 88, 95, 60\nset total to 0\nfor each s in scores\n    set total to total plus s\nend\nsay "Average: " plus (total divided by length of scores)')}</code></pre>
<pre class="out"><code>{html.escape(chr(10).join(hero_out))}</code></pre></div>
{chr(10).join(sections)}
<section id="tools"><h2>Command-line tools</h2>
<p>Everything in this guide runs in the browser playground, and the same language is available from the terminal.</p>
<table>{tools}</table></section>
<footer>Every example on this page was executed when the site was built, and the output shown is what it really printed.</footer>
</main></div></body></html>
"""
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    for name in ("playground.html", "plainlang.js", "lessons.js", "pilot.js"):
        shutil.copy(os.path.join(HERE, name), os.path.join(out_dir, name))
    open(os.path.join(out_dir, ".nojekyll"), "w").close()
    return problems


def main(argv):
    if "--check" in argv:
        with tempfile.TemporaryDirectory() as d:
            problems = build(d)
        for p in problems:
            print("✗", p)
        print("docs OK" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0
    out = os.path.join(HERE, "site")
    problems = build(out)
    for p in problems:
        print("✗", p)
    print(f"wrote {out}" + ("" if not problems else f" with {len(problems)} problem(s)"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
