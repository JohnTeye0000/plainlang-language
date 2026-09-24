"""
plainspec -- PlainLang's grammar, executable.

Reads grammar.ebnf and recognizes programs against it directly. It's an
independent third opinion on what is and isn't a valid program: the reference
parsers are hand-written recursive descent, while this is generated from the
written specification. test_spec.py runs all of them on the same inputs, and any
disagreement is a bug -- either the parser or the spec is wrong.

    python plainspec.py program.plang     # does the grammar accept this file?

The recognizer is deliberately simple (a PEG-style matcher: ordered choice,
greedy repetition, no memoization) so it can be read and trusted at a glance.
"""

import os
import re
import sys

import plainlang as pl

HERE = os.path.dirname(os.path.abspath(__file__))
GRAMMAR_PATH = os.path.join(HERE, "grammar.ebnf")

_META_TOKEN = re.compile(r'\s+|\(\*.*?\*\)|(?P<str>"[^"]*")(?P<at>@?)|(?P<name>[A-Za-z_][A-Za-z0-9_]*)|(?P<sym>[=|;()\[\]{}])', re.S)


# ─── reading the EBNF ───────────────────────────────────────────────────────

def _meta_tokens(text):
    pos, out = 0, []
    while pos < len(text):
        m = _META_TOKEN.match(text, pos)
        if not m:
            raise ValueError(f"grammar.ebnf: can't read {text[pos:pos + 20]!r}")
        pos = m.end()
        if m.group("str") is not None:
            out.append(("kw", m.group("str")[1:-1], m.group("at") == "@"))
        elif m.group("name"):
            out.append(("name", m.group("name")))
        elif m.group("sym"):
            out.append(("sym", m.group("sym")))
    return out


class _MetaParser:
    def __init__(self, tokens):
        self.t, self.i = tokens, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else ("eof",)

    def sym(self, s):
        tok = self.peek()
        return tok[0] == "sym" and tok[1] == s

    def rules(self):
        rules = {}
        while self.peek()[0] != "eof":
            name = self.peek()
            assert name[0] == "name", f"rule name expected, got {name}"
            self.i += 1
            assert self.sym("="), f"'=' expected after {name[1]}"
            self.i += 1
            rules[name[1]] = self.alternatives()
            assert self.sym(";"), f"';' expected at end of {name[1]}"
            self.i += 1
        return rules

    def alternatives(self):
        alts = [self.sequence()]
        while self.sym("|"):
            self.i += 1
            alts.append(self.sequence())
        return alts[0] if len(alts) == 1 else ("alt", alts)

    def sequence(self):
        items = []
        while True:
            tok = self.peek()
            if tok[0] == "eof" or (tok[0] == "sym" and tok[1] in "|;)]}"):
                break
            items.append(self.atom())
        return ("seq", items)            # an empty sequence matches nothing (epsilon)

    def atom(self):
        tok = self.peek()
        self.i += 1
        if tok[0] == "kw":
            return ("kw", tok[1], tok[2])
        if tok[0] == "name":
            return ("tok", tok[1]) if tok[1] in ("IDENT", "NUMBER", "STRING", "EOF") else ("ref", tok[1])
        s = tok[1]
        if s == "(":
            inner = self.alternatives(); self._close(")"); return inner
        if s == "[":
            inner = self.alternatives(); self._close("]"); return ("opt", inner)
        if s == "{":
            inner = self.alternatives(); self._close("}"); return ("rep", inner)
        raise ValueError(f"grammar.ebnf: unexpected {s!r}")

    def _close(self, s):
        assert self.sym(s), f"'{s}' expected"
        self.i += 1


def load_rules(path=GRAMMAR_PATH):
    with open(path, encoding="utf-8") as f:
        return _MetaParser(_meta_tokens(f.read())).rules()


# ─── recognizing ────────────────────────────────────────────────────────────

_PUNCT = {"(": "LPAREN", ")": "RPAREN", ",": "COMMA"}


class Recognizer:
    def __init__(self, rules=None, turtle=False):
        self.rules = dict(rules or load_rules())
        if turtle:
            self.rules["statement"] = ("alt", [("ref", "turtle_stmt"), self.rules["statement"]])

    def accepts(self, source):
        """True if source is a program according to the grammar."""
        try:
            tokens = pl.tokenize(source)
        except pl.PlainLangError:
            return False
        return self._match(("ref", "program"), tokens, 0) is not None

    # returns the position after a match, or None
    def _match(self, node, toks, pos):
        kind = node[0]
        if kind == "seq":
            for item in node[1]:
                pos = self._match(item, toks, pos)
                if pos is None:
                    return None
            return pos
        if kind == "alt":
            for alt in node[1]:
                got = self._match(alt, toks, pos)
                if got is not None:
                    return got
            return None
        if kind == "opt":
            got = self._match(node[1], toks, pos)
            return pos if got is None else got
        if kind == "rep":
            while True:
                got = self._match(node[1], toks, pos)
                if got is None or got == pos:
                    return pos
                pos = got
        if kind == "ref":
            return self._match(self.rules[node[1]], toks, pos)
        if kind == "kw":
            t = toks[pos]
            word = node[1]
            if word in _PUNCT:
                ok = t[0] == _PUNCT[word]
            else:
                ok = t[0] == "KW" and t[1] == word
            if ok and node[2] and (pos == 0 or toks[pos - 1][2] != t[2]):
                ok = False                    # "word"@ must share a line with the previous token
            return pos + 1 if ok else None
        if kind == "tok":
            t = toks[pos]
            if node[1] == "EOF":
                return pos if t[0] == "EOF" else None
            if t[0] != node[1]:
                return None
            if node[1] == "STRING" and not self.string_ok(t[1]):
                return None
            return pos + 1
        raise ValueError(node)

    # A text literal may embed {expressions}; each must itself be a complete expression.
    def string_ok(self, text):
        i, n = 0, len(text)
        while i < n:
            c = text[i]
            if c in "{}" and i + 1 < n and text[i + 1] == c:
                i += 2
                continue
            if c == "}":
                i += 1
                continue                       # a lone } is literal text
            if c == "{":
                j = text.find("}", i + 1)
                if j == -1:
                    return False
                inner = text[i + 1:j].strip()
                if not inner:
                    return False
                try:
                    toks = pl.tokenize(inner)
                except pl.PlainLangError:
                    return False
                end = self._match(("ref", "expr"), toks, 0)
                if end is None or toks[end][0] != "EOF":
                    return False
                i = j + 1
                continue
            i += 1
        return True


def main(argv):
    if not argv:
        print(__doc__)
        return 0
    with open(argv[0], encoding="utf-8") as f:
        source = f.read()
    ok = Recognizer().accepts(source)
    print(f"{argv[0]}: {'valid PlainLang' if ok else 'NOT valid according to grammar.ebnf'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
