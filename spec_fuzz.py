"""
Differential testing of the grammar against the real parsers.

Takes valid PlainLang programs, corrupts them at the token level (delete,
duplicate, swap, replace, insert, move to another line), and asks three
independent judges whether each result is still a program:

    * the Python parser (plainlang.py)
    * the JavaScript parser (plainlang.js, via Node)
    * the recognizer generated from grammar.ebnf (plainspec.py)

They must always agree. Where they don't, either the written specification or an
implementation is wrong -- this is how the spec stays honest.

Two known, deliberate differences are excluded from the comparison:
  * the "did you mean 'say'?" typo check: a bare name followed by a value is a
    *diagnostic* refusal, not a grammar rule (the grammar accepts it as two calls)
  * `import` and turtle statements, which only one engine supports
"""

import json
import os
import random
import shutil
import subprocess

import plainlang as pl
import plainspec

HERE = os.path.dirname(os.path.abspath(__file__))
VOCAB_KW = sorted(k for k in pl.KEYWORDS
                  if k not in ("move", "forward", "backward", "back", "turn", "left", "right",
                               "pen", "up", "down", "color", "wait", "import"))
FILLER = [("IDENT", "x"), ("IDENT", "foo"), ("NUMBER", 1), ("NUMBER", 2.5), ("STRING", "s"),
          ("STRING", "a {x} b"), ("STRING", "{x y}"), ("STRING", "{1 2}"), ("STRING", "{"),
          ("STRING", "}"), ("STRING", "{}"), ("STRING", "{x plus}"), ("STRING", "{{x}}"),
          ("LPAREN", "("), ("RPAREN", ")"), ("COMMA", ",")]


def to_source(tokens):
    """Rebuild source text from (kind, value, line) triples, keeping line breaks."""
    out, cur = [], 1
    for kind, val, line in tokens:
        while cur < line:
            out.append("\n")
            cur += 1
        if kind == "STRING":
            text = f'"{val}"'
        elif kind == "NUMBER":
            text = repr(val)
        else:
            text = str(val)
        out.append(text + " ")
    return "".join(out)


def tokens_of(source):
    toks = pl.tokenize(source)
    return [(t[0], t[1], t[2]) for t in toks if t[0] != "EOF"]


def mutate(tokens, rng):
    toks = list(tokens)
    if not toks:
        return toks
    kind = rng.choice(["delete", "duplicate", "swap", "replace", "insert", "newline", "join"])
    i = rng.randrange(len(toks))
    pick = lambda: (lambda k, v: (k, v, toks[min(i, len(toks) - 1)][2]))(
        *(rng.choice(FILLER) if rng.random() < 0.4 else ("KW", rng.choice(VOCAB_KW))))
    if kind == "delete":
        del toks[i]
    elif kind == "duplicate":
        toks.insert(i, toks[i])
    elif kind == "swap" and i + 1 < len(toks):
        (k1, v1, l1), (k2, v2, l2) = toks[i], toks[i + 1]
        toks[i], toks[i + 1] = (k2, v2, l1), (k1, v1, l2)
    elif kind == "replace":
        toks[i] = pick()
    elif kind == "insert":
        toks.insert(i, pick())
    elif kind == "newline":               # push this token and the rest onto a later line
        toks = toks[:i] + [(k, v, l + 1) for k, v, l in toks[i:]]
    elif kind == "join" and i > 0:        # pull this token up to the previous token's line
        k, v, _ = toks[i]
        toks[i] = (k, v, toks[i - 1][2])
    return toks


def python_verdict(source):
    """'ok', 'reject', or 'skip' (a diagnostics-only refusal we don't compare)."""
    try:
        pl.Parser(pl.tokenize(source)).parse()
        return "ok"
    except pl.PlainLangError as e:
        if (e.hint or "").startswith("Did you mean") and e.message.startswith("I don't know how to start a statement with"):
            return "skip"
        return "reject"


def js_verdicts(sources):
    """Verdicts from the JavaScript parser for many sources at once (None if no node)."""
    if shutil.which("node") is None:
        return None
    script = (
        'const PL=require("./plainlang.js");const src=JSON.parse(require("fs").readFileSync(0,"utf8"));'
        'process.stdout.write(JSON.stringify(src.map(s=>{try{new PL.Parser(PL.tokenize(s)).parse();return "ok";}'
        'catch(e){if(e&&e.hint&&/^Did you mean/.test(e.hint)&&/^I don.t know how to start a statement with/.test(e.plMessage||""))return "skip";return "reject";}})));'
    )
    proc = subprocess.run(["node", "-e", script], input=json.dumps(sources).encode(), capture_output=True, cwd=HERE)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace"))
    return json.loads(proc.stdout.decode("utf-8"))


def run(corpus, n_mutants, seed=0, batch=400):
    """Returns (compared, [disagreements]); each is (source, {judge: verdict})."""
    rng = random.Random(seed)
    recognizer = plainspec.Recognizer()
    base = [tokens_of(src) for src in corpus]
    compared, bad = 0, []
    for start in range(0, n_mutants, batch):
        sources = []
        for _ in range(min(batch, n_mutants - start)):
            toks = rng.choice(base)
            for _ in range(rng.choice([1, 1, 1, 2])):
                toks = mutate(toks, rng)
            try:
                sources.append(to_source(toks))
            except Exception:
                continue
        js = js_verdicts(sources)
        for k, src in enumerate(sources):
            py = python_verdict(src)
            if py == "skip":
                continue
            spec = "ok" if recognizer.accepts(src) else "reject"
            verdicts = {"python": py, "spec": spec}
            has_import = "import" in src.lower().split()
            if js is not None and not has_import:
                if js[k] == "skip":
                    continue
                verdicts["javascript"] = js[k]
            compared += 1
            if len(set(verdicts.values())) > 1:
                bad.append((src, verdicts))
    return compared, bad


if __name__ == "__main__":
    import sys
    import docs_content as dc
    import fuzz
    import fuzz_wasm
    corpus = [open(os.path.join(HERE, "demo.plang"), encoding="utf-8").read()]
    corpus += [e["code"] for s in dc.SECTIONS for e in s["examples"] if e.get("run", True)]
    corpus += [fuzz.Generator(random.Random(k)).program() for k in range(40)]
    corpus += [fuzz_wasm.Generator(random.Random(k)).program() for k in range(40)]
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    compared, bad = run(corpus, n, seed)
    print(f"{compared} mutants compared, {len(bad)} disagreements")
    for src, v in bad[:8]:
        print("---", v)
        print(src)
