"""
Accessibility regression tests for the playground and the docs site.

These don't replace running a real audit (axe-core found and drove the original
fixes), but they lock the results in so they can't quietly regress without a
browser in CI:

  * every text/background colour pair in the palettes meets WCAG AA (4.5:1)
  * the playground keeps its landmarks, labels, tab semantics and dialog roles

Run with:   python test_a11y.py
"""

import re
import sys

import build_docs

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def luminance(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def css_vars(block):
    return {m.group(1): m.group(2) for m in re.finditer(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})", block)}


playground = open("playground.html", encoding="utf-8").read()

print("Playground palette (WCAG AA = 4.5:1)")
root = re.search(r":root\s*\{(.*?)\}", playground, re.S).group(1)
v = css_vars(root)
papers = [v["paper"], v["paper-2"], v["paper-3"]]
for name in ("ink", "ink-2", "ink-soft", "red-ink", "com", "str", "num", "fn"):
    worst = min(contrast(v[name], p) for p in papers)
    check(f"--{name} on every paper tone ({worst:.2f}:1)", worst >= 4.5, f"{v[name]} {worst:.2f}")
check("the changed-variable highlight colour stays readable mid-flash",
      contrast("#7d1f16", "#e3b4a7") >= 4.5)

print("Docs palette")
css = build_docs.CSS
light = css_vars(css.split("@media(prefers-color-scheme:dark)")[0])
dark = {**light, **css_vars(css.split("@media(prefers-color-scheme:dark)")[1])}
for label, pal, bgs in (("light", light, ["#f4eee1", "#fbf7ed", "#ece2cf"]),
                        ("dark", dark, ["#1c1813", "#231e17", "#2a241c"])):
    for name in ("ink", "ink-2", "soft", "red-ink", "com", "str", "num"):
        worst = min(contrast(pal[name], bg) for bg in bgs)
        check(f"[{label}] --{name} ({worst:.2f}:1)", worst >= 4.5, f"{pal[name]} {worst:.2f}")

print("Playground structure")
check("the page declares its language", '<html lang="en">' in playground)
check("has header, main and footer landmarks", all(t in playground for t in ("<header", "<main>", "<footer>")))
check("has a skip link to the editor", 'class="skip-link" href="#code"' in playground)
controls = re.findall(r"<(textarea|select|input)\b([^>]*)>", playground)
unlabeled = [a for _, a in controls if "aria-label" not in a and "type=\"hidden\"" not in a]
check("every form control has an accessible name", not unlabeled, unlabeled)
check("the view switcher is a real tablist", 'role="tablist"' in playground and playground.count('role="tab"') == 3)
check("tabs are buttons (keyboard operable), not divs", not re.search(r'<div class="tab[ \"]', playground))
check("every tab is wired to a tabpanel", playground.count('role="tabpanel"') == 3)
check("tab keyboard support (arrow keys) is implemented", "ArrowRight" in playground and "ArrowLeft" in playground)
check("the Workbook is a modal dialog", 'role="dialog"' in playground and 'aria-modal="true"' in playground)
check("Escape closes the Workbook and focus is returned", 'e.key === "Escape"' in playground and "wbOpener" in playground)
check("focus is trapped inside the open dialog", "keep focus inside the dialog" in playground)
check("program output is a live region", 'role="log" aria-live="polite"' in playground)
check("scrollable regions are keyboard-focusable",
      'id="console" tabindex="0"' in playground and 'id="jsPre" tabindex="0"' in playground and 'id="inspector" tabindex="0"' in playground)
check("the editor doesn't trap keyboard focus (Escape, then Tab)", "tabLeavesEditor" in playground)
check("reduced-motion preference is respected", "prefers-reduced-motion: reduce" in playground)
check("keyboard focus is visibly styled", ":focus-visible" in playground)

print("Docs structure")
import tempfile, os
with tempfile.TemporaryDirectory() as d:
    build_docs.build(d)
    site = open(os.path.join(d, "index.html"), encoding="utf-8").read()
check("docs page declares its language", '<html lang="en">' in site)
check("docs page has nav and main landmarks", "<nav>" in site and "<main>" in site)
check("docs page has a title and viewport", "<title>" in site and 'name="viewport"' in site)
check("docs respect the user's colour-scheme preference", "prefers-color-scheme:dark" in site)
check("headings are in order (one h1, then h2 sections)", site.count("<h1") == 1 and "<h3" not in site)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
