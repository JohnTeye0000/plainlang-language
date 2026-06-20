"""
PlainLang — a beginner-friendly programming language that reads like English.

The goal: a first language where the code says what it does, and the error
messages teach instead of confuse.

    set name to "Alice"
    say "Hello, " plus name

    set scores to list of 90, 75, 88
    set total to 0
    for each s in scores
        set total to total plus s
    end
    say "Average: " plus (total divided by length of scores)

    define double with n
        return n multiplied by 2
    end
    say double with 21

Run a file:   python plainlang.py myprogram.plang
Open a REPL:  python plainlang.py
See syntax:   python plainlang.py --help
"""

import sys
import re
import math
import random

# Make sure we can print Unicode (e.g. box-drawing chars) on Windows consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


# ─── Errors & diagnostics ────────────────────────────────────────────────────
# One error type, carrying a line and (when we can) a source span so the
# message can underline the exact offending text with a caret, plus a hint
# that may include a "did you mean?" suggestion.

class PlainLangError(Exception):
    def __init__(self, message, line=None, hint=None, col=None, length=None, near=None):
        self.message = message
        self.line = line
        self.hint = hint
        self.col = col          # 1-based column of the offending token
        self.length = length    # width of the caret underline
        self.near = near        # an identifier to locate in the line, when col is unknown
        super().__init__(message)

    def show(self):
        where = f"line {self.line}" if self.line else "your program"
        out = [f"\n  Oops! Something went wrong on {where}:", f"    {self.message}"]
        if self.hint:
            out.append(f"  Hint: {self.hint}")
        return "\n".join(out)


def _levenshtein(a, b):
    if a == b:
        return 0
    if not a or not b:
        return len(a) + len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def suggest(name, candidates):
    """Closest candidate to `name`, if one is near enough. Deterministic."""
    best, best_d = None, 999
    low = name.lower()
    for c in sorted(set(candidates)):     # sorted -> stable tie-breaking
        d = _levenshtein(low, c.lower())
        if d < best_d:
            best, best_d = c, d
    if best is not None and best_d <= min(3, max(1, len(name) // 2 + 1)):
        return best
    return None


def _did_you_mean(name, candidates):
    s = suggest(name, candidates)
    return f"Did you mean '{s}'?" if s else None


def unknown_variable_error(name, candidates, line):
    """Built in one place so both back ends produce identical messages."""
    visible = [c for c in candidates if not c.startswith("$")]
    hint = _did_you_mean(name, visible) or f"Create it first with:  set {name} to ..."
    return PlainLangError(f"I haven't heard of a variable called '{name}' yet.",
                          line, hint, near=name)


def unknown_function_error(name, candidates, line):
    hint = _did_you_mean(name, list(candidates)) or f"Teach me one with:  define {name} ... end"
    return PlainLangError(f"I don't know a function called '{name}'.",
                          line, hint, near=name)


def format_error(source, err):
    """Render an error with a source-line excerpt and a caret underline."""
    if not isinstance(err, PlainLangError):
        return f"\n  Error: {err}"
    if not err.line:
        return err.show()
    lines = source.split("\n")
    if not (1 <= err.line <= len(lines)):
        return err.show()
    src = lines[err.line - 1]
    col, length = err.col, err.length
    if col is None and err.near:                 # locate the name to underline it
        idx = src.find(err.near)
        if idx >= 0:
            col, length = idx + 1, len(err.near)
    num = str(err.line)
    out = [f"\n  Oops! Something went wrong on line {err.line}:",
           f"    {err.message}", "",
           f"    {num} | {src}"]
    if col:
        out.append(f"    {' ' * (len(num) + 3 + col - 1)}{'^' * max(1, length or 1)}")
    if err.hint:
        out.append(f"  Hint: {err.hint}")
    return "\n".join(out)


# ─── Tokenizer ──────────────────────────────────────────────────────────────

TOKEN_SPEC = [
    ("NUMBER",  r"\d+(?:\.\d+)?"),
    ("STRING",  r'"[^"]*"'),
    ("NEWLINE", r"\n"),
    ("SKIP",    r"[ \t\r]+|#[^\n]*"),
    ("LPAREN",  r"\("),
    ("RPAREN",  r"\)"),
    ("COMMA",   r","),
    ("WORD",    r"[A-Za-z_][A-Za-z0-9_]*"),
    ("UNKNOWN", r"."),
]
MASTER = re.compile("|".join(f"(?P<{n}>{p})" for n, p in TOKEN_SPEC))

# Words that are part of the language's grammar (so they can't be variable names).
KEYWORDS = {
    "set", "to", "say", "ask", "into",
    "if", "then", "otherwise", "end",
    "repeat", "times", "while", "count", "from", "for", "each", "in",
    "define", "with", "call", "return",
    "list", "of", "empty", "add", "remove", "item",
    "plus", "minus", "multiplied", "divided", "by",
    "is", "not", "greater", "less", "than", "equal", "at", "least", "most",
    "and", "or", "true", "false",
    "length", "uppercase", "lowercase", "round", "absolute",
    "square", "root", "random", "between",
    "record", "as", "keys",
    "stop", "skip",
    "map", "filter", "reduce", "over",
    "split", "join", "trim", "replace", "position", "contains",
    "match", "when",
}


def tokenize(source):
    # Each token is (kind, value, line, col, length). col is 1-based; length is
    # the width of the source text, so errors can underline it with a caret.
    tokens = []
    line = 1
    line_start = 0
    for m in MASTER.finditer(source):
        kind, val = m.lastgroup, m.group()
        col = m.start() - line_start + 1
        length = m.end() - m.start()
        if kind == "NEWLINE":
            line += 1
            line_start = m.end()
        elif kind == "SKIP":
            continue
        elif kind == "NUMBER":
            tokens.append(("NUMBER", float(val) if "." in val else int(val), line, col, length))
        elif kind == "STRING":
            tokens.append(("STRING", val[1:-1], line, col, length))
        elif kind == "WORD":
            low = val.lower()
            tokens.append((("KW", low) if low in KEYWORDS else ("IDENT", val)) + (line, col, length))
        elif kind in ("LPAREN", "RPAREN", "COMMA"):
            tokens.append((kind, val, line, col, length))
        elif kind == "UNKNOWN":
            raise PlainLangError(
                f"I don't understand the symbol '{val}'.", line,
                "PlainLang uses words like 'plus' and 'is greater than' instead of symbols.",
                col=col, length=length)
    tokens.append(("EOF", None, line, len(source) - line_start + 1, 1))
    return tokens


# ─── Parser ─────────────────────────────────────────────────────────────────
# Turns the flat list of tokens into a tree of statements and expressions.
# Statements are wrapped as ("@", line, node) so runtime errors know where
# they happened.

BLOCK_ENDERS = {"end", "otherwise", "when"}


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # — cursor helpers —
    def peek(self):
        return self.tokens[self.pos]

    def kind(self):
        return self.tokens[self.pos][0]

    def is_kw(self, *words):
        t = self.tokens[self.pos]
        return t[0] == "KW" and t[1] in words

    def advance(self):
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def line(self):
        return self.tokens[self.pos][2]

    @staticmethod
    def _span(t):
        return (t[3] if len(t) > 3 else None, t[4] if len(t) > 4 else None)

    def eat_kw(self, word):
        t = self.peek()
        if t[0] != "KW" or t[1] != word:
            col, length = self._span(t)
            raise PlainLangError(
                f"I expected the word '{word}' here, but found {self._describe(t)}.",
                t[2], col=col, length=length)
        return self.advance()

    def eat(self, kind, label):
        t = self.peek()
        if t[0] != kind:
            col, length = self._span(t)
            raise PlainLangError(
                f"I expected {label} here, but found {self._describe(t)}.",
                t[2], col=col, length=length)
        return self.advance()

    @staticmethod
    def _describe(t):
        if t[0] == "EOF":
            return "the end of the program"
        if t[0] == "STRING":
            return f'the text "{t[1]}"'
        if t[0] == "NUMBER":
            return f"the number {t[1]}"
        return f"'{t[1]}'"

    # — top level —
    def parse(self):
        stmts = []
        while self.kind() != "EOF":
            stmts.append(self.statement())
        return ("block", stmts)

    def block(self):
        """A run of statements ending at 'end' or 'otherwise' (not consumed)."""
        stmts = []
        while self.kind() != "EOF" and not self.is_kw(*BLOCK_ENDERS):
            stmts.append(self.statement())
        return ("block", stmts)

    # — statements —
    def statement(self):
        ln = self.line()
        node = self._statement_inner()
        return ("@", ln, node)

    def _statement_inner(self):
        if self.is_kw("set"):     return self.set_stmt()
        if self.is_kw("say"):     return self.say_stmt()
        if self.is_kw("ask"):     return self.ask_stmt()
        if self.is_kw("if"):      return self.if_stmt()
        if self.is_kw("match"):   return self.match_stmt()
        if self.is_kw("repeat"):  return self.repeat_stmt()
        if self.is_kw("while"):   return self.while_stmt()
        if self.is_kw("count"):   return self.count_stmt()
        if self.is_kw("for"):     return self.foreach_stmt()
        if self.is_kw("define"):  return self.define_stmt()
        if self.is_kw("call"):    return self.call_stmt()
        if self.is_kw("return"):  return self.return_stmt()
        if self.is_kw("add"):     return self.add_stmt()
        if self.is_kw("remove"):  return self.remove_stmt()
        if self.is_kw("stop"):    self.advance(); return ("break",)
        if self.is_kw("skip"):    self.advance(); return ("continue",)
        if self.kind() == "IDENT":
            return self.call_stmt()  # bare function call, e.g. greet with "Bob"
        t = self.peek()
        col, length = self._span(t)
        hint = "Statements begin with words like set, say, if, repeat, for, or define."
        if t[0] == "IDENT":
            s = suggest(t[1], ["set", "say", "ask", "if", "repeat", "while",
                               "count", "for", "define", "call", "return", "add", "remove"])
            if s:
                hint = f"Did you mean '{s}'?"
        raise PlainLangError(
            f"I don't know how to start a statement with {self._describe(t)}.",
            t[2], hint, col=col, length=length)

    def set_stmt(self):
        self.eat_kw("set")
        # set item KEY of TARGET to VALUE  — update a list element or record field
        if self.is_kw("item"):
            self.advance()
            key = self.expression()
            self.eat_kw("of")
            target = self.primary()
            self.eat_kw("to")
            return ("setindex", target, key, self.expression())
        name = self.eat("IDENT", "a variable name")[1]
        self.eat_kw("to")
        return ("set", name, self.expression())

    def record_literal(self):
        # record with KEY as VALUE, KEY as VALUE, ...
        self.eat_kw("record")
        self.eat_kw("with")
        pairs = []
        while True:
            key = self.comparison()
            self.eat_kw("as")
            value = self.comparison()
            pairs.append((key, value))
            if self.kind() == "COMMA":
                self.advance()
            else:
                break
        return ("record", pairs)

    def say_stmt(self):
        self.eat_kw("say")
        return ("say", self.expression())

    def ask_stmt(self):
        self.eat_kw("ask")
        prompt = self.expression()
        self.eat_kw("into")
        name = self.eat("IDENT", "a variable name")[1]
        return ("ask", prompt, name)

    def if_stmt(self):
        self.eat_kw("if")
        branches = []
        cond = self.expression()
        self.eat_kw("then")
        branches.append((cond, self.block()))
        else_block = None
        while self.is_kw("otherwise"):
            self.advance()
            if self.is_kw("if"):
                self.advance()
                cond = self.expression()
                self.eat_kw("then")
                branches.append((cond, self.block()))
            else:
                else_block = self.block()
                break
        self.eat_kw("end")
        return ("if", branches, else_block)

    def repeat_stmt(self):
        self.eat_kw("repeat")
        count = self.expression()
        self.eat_kw("times")
        body = self.block()
        self.eat_kw("end")
        return ("repeat", count, body)

    def match_stmt(self):
        # match X  when V then ...  when V then ...  otherwise ...  end
        self.eat_kw("match")
        subject = self.expression()
        cases = []
        while self.is_kw("when"):
            self.advance()
            value = self.expression()
            self.eat_kw("then")
            cases.append((value, self.block()))
        else_block = None
        if self.is_kw("otherwise"):
            self.advance()
            else_block = self.block()
        self.eat_kw("end")
        return ("match", subject, cases, else_block)

    def while_stmt(self):
        self.eat_kw("while")
        cond = self.expression()
        body = self.block()
        self.eat_kw("end")
        return ("while", cond, body)

    def count_stmt(self):
        # count i from 1 to 10 ... end
        self.eat_kw("count")
        var = self.eat("IDENT", "a counter variable name")[1]
        self.eat_kw("from")
        start = self.expression()
        self.eat_kw("to")
        stop = self.expression()
        body = self.block()
        self.eat_kw("end")
        return ("count", var, start, stop, body)

    def foreach_stmt(self):
        # for each item in things ... end
        self.eat_kw("for")
        self.eat_kw("each")
        var = self.eat("IDENT", "a loop variable name")[1]
        self.eat_kw("in")
        seq = self.expression()
        body = self.block()
        self.eat_kw("end")
        return ("foreach", var, seq, body)

    def define_stmt(self):
        self.eat_kw("define")
        name = self.eat("IDENT", "a function name")[1]
        params = []
        if self.is_kw("with"):
            self.advance()
            params.append(self.eat("IDENT", "a parameter name")[1])
            while self.is_kw("and"):
                self.advance()
                params.append(self.eat("IDENT", "a parameter name")[1])
        body = self.block()
        self.eat_kw("end")
        return ("define", name, params, body)

    # tokens that can begin a value (so we can tell a real call from a typo)
    _VALUE_START_KW = {"true", "false", "empty", "list", "item", "length",
                       "uppercase", "lowercase", "round", "absolute", "square",
                       "random", "minus"}
    _STATEMENT_KW = ["set", "say", "ask", "if", "repeat", "while", "count",
                     "for", "define", "call", "return", "add", "remove"]

    def call_stmt(self):
        if self.is_kw("call"):
            self.advance()
        name_tok = self.eat("IDENT", "a function name")
        name = name_tok[1]
        # A bare name followed by a value (not 'with') that looks like a
        # mistyped keyword is almost certainly a typo:  saay "hi"  ->  say
        if not self.is_kw("with"):
            nxt = self.peek()
            looks_like_value = nxt[0] in ("STRING", "NUMBER", "IDENT", "LPAREN") or \
                               (nxt[0] == "KW" and nxt[1] in self._VALUE_START_KW)
            if looks_like_value:
                s = suggest(name, self._STATEMENT_KW)
                if s:
                    col, length = self._span(name_tok)
                    raise PlainLangError(
                        f"I don't know how to start a statement with '{name}'.",
                        name_tok[2], f"Did you mean '{s}'?", col=col, length=length)
        args = self._maybe_args()
        return ("call", name, args)

    def _maybe_args(self):
        # Arguments are separated by 'and', which is also the boolean operator.
        # So each argument parses below 'and'/'or' (use parentheses for a
        # boolean argument, e.g.  f with (a and b)).
        args = []
        if self.is_kw("with"):
            self.advance()
            args.append(self.comparison())
            while self.is_kw("and"):
                self.advance()
                args.append(self.comparison())
        return args

    def return_stmt(self):
        self.eat_kw("return")
        return ("return", self.expression())

    def add_stmt(self):
        # add X to mylist
        self.eat_kw("add")
        value = self.expression()
        self.eat_kw("to")
        name = self.eat("IDENT", "a list variable name")[1]
        return ("add", value, name)

    def remove_stmt(self):
        # remove item N from mylist
        self.eat_kw("remove")
        self.eat_kw("item")
        index = self.expression()
        self.eat_kw("from")
        name = self.eat("IDENT", "a list variable name")[1]
        return ("remove", index, name)

    # — expressions, lowest to highest precedence —
    def expression(self):
        return self.or_expr()

    def or_expr(self):
        left = self.and_expr()
        while self.is_kw("or"):
            self.advance()
            left = ("or", left, self.and_expr())
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.is_kw("and"):
            self.advance()
            left = ("and", left, self.not_expr())
        return left

    def not_expr(self):
        if self.is_kw("not"):
            self.advance()
            return ("not", self.not_expr())
        return self.comparison()

    def comparison(self):
        left = self.arith()
        if self.is_kw("is"):
            self.advance()
            op = self._comparison_op()
            right = self.arith()
            return ("cmp", op, left, right)
        if self.is_kw("contains"):           # "TEXT contains PART" / "LIST contains ITEM"
            self.advance()
            return ("builtin", "contains", [left, self.arith()])
        return left

    def _comparison_op(self):
        if self.is_kw("not"):
            self.advance()
            if self.is_kw("equal"):
                self.advance()
                if self.is_kw("to"):
                    self.advance()
            return "!="
        if self.is_kw("greater"):
            self.advance(); self.eat_kw("than"); return ">"
        if self.is_kw("less"):
            self.advance(); self.eat_kw("than"); return "<"
        if self.is_kw("at"):
            self.advance()
            if self.is_kw("least"):
                self.advance(); return ">="
            if self.is_kw("most"):
                self.advance(); return "<="
            t = self.peek()
            raise PlainLangError(
                "After 'is at' I expected 'least' or 'most'.", t[2])
        if self.is_kw("equal"):
            self.advance()
            if self.is_kw("to"):
                self.advance()
            return "=="
        return "=="  # bare "is"

    def arith(self):
        left = self.term()
        while self.is_kw("plus", "minus"):
            op = "+" if self.advance()[1] == "plus" else "-"
            left = ("binop", op, left, self.term())
        return left

    def term(self):
        left = self.factor()
        while self.is_kw("multiplied", "divided"):
            word = self.advance()[1]
            self.eat_kw("by")
            op = "*" if word == "multiplied" else "/"
            left = ("binop", op, left, self.factor())
        return left

    def factor(self):
        if self.is_kw("minus"):  # unary negation: minus 5
            self.advance()
            return ("neg", self.factor())
        return self.primary()

    def primary(self):
        t = self.peek()

        if t[0] == "NUMBER":
            self.advance(); return ("num", t[1])
        if t[0] == "STRING":
            self.advance(); return ("str", t[1])
        if t[0] == "LPAREN":
            self.advance()
            inner = self.expression()
            self.eat("RPAREN", "a closing ')'")
            return inner
        if self.is_kw("true"):
            self.advance(); return ("bool", True)
        if self.is_kw("false"):
            self.advance(); return ("bool", False)

        # lists & records
        if self.is_kw("empty"):
            self.advance()
            if self.is_kw("record"):
                self.advance(); return ("record", [])
            self.eat_kw("list"); return ("list", [])
        if self.is_kw("list"):
            self.advance(); self.eat_kw("of")
            items = [self.expression()]
            while self.kind() == "COMMA":
                self.advance()
                items.append(self.expression())
            return ("list", items)
        if self.is_kw("record"):
            return self.record_literal()
        if self.is_kw("map", "filter"):
            kind = self.advance()[1]
            fn = self.comparison()
            self.eat_kw("over")
            return (kind, fn, self.comparison())
        if self.is_kw("reduce"):
            self.advance()
            fn = self.comparison()
            self.eat_kw("over")
            seq = self.comparison()
            self.eat_kw("from")
            return ("reduce", fn, seq, self.comparison())
        if self.is_kw("item"):
            self.advance()
            index = self.expression()
            self.eat_kw("of")
            seq = self.primary()
            return ("index", seq, index)

        # built-in functions
        if self.is_kw("length", "uppercase", "lowercase", "round", "absolute", "keys", "trim"):
            name = self.advance()[1]
            self.eat_kw("of")
            return ("builtin", name, [self.primary()])
        if self.is_kw("square"):
            self.advance(); self.eat_kw("root"); self.eat_kw("of")
            return ("builtin", "sqrt", [self.primary()])
        # text helpers
        if self.is_kw("split"):              # split TEXT by SEP
            self.advance(); text = self.comparison(); self.eat_kw("by")
            return ("builtin", "split", [text, self.comparison()])
        if self.is_kw("join"):               # join LIST by SEP
            self.advance(); seq = self.comparison(); self.eat_kw("by")
            return ("builtin", "join", [seq, self.comparison()])
        if self.is_kw("replace"):            # replace OLD by NEW in TEXT
            self.advance(); old = self.comparison(); self.eat_kw("by")
            new = self.comparison(); self.eat_kw("in")
            return ("builtin", "replace", [old, new, self.comparison()])
        if self.is_kw("position"):           # position of PART in TEXT
            self.advance(); self.eat_kw("of"); part = self.comparison(); self.eat_kw("in")
            return ("builtin", "position", [part, self.comparison()])
        if self.is_kw("random"):
            self.advance(); self.eat_kw("between")
            low = self.arith()
            self.eat_kw("and")
            high = self.arith()
            return ("builtin", "random", [low, high])

        # variable or function-call-as-value
        if t[0] == "IDENT":
            self.advance()
            if self.is_kw("with"):
                self.advance()
                args = [self.comparison()]
                while self.is_kw("and"):
                    self.advance()
                    args.append(self.comparison())
                return ("call", t[1], args)
            return ("var", t[1])

        col, length = self._span(t)
        raise PlainLangError(
            f"I expected a value here, but found {self._describe(t)}.", t[2],
            "A value is a number, some \"text\", a variable, or a list.",
            col=col, length=length)


# ─── Interpreter ────────────────────────────────────────────────────────────

class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    """Raised by 'stop' to leave the nearest loop."""


class ContinueSignal(Exception):
    """Raised by 'skip' to jump to the next pass of the nearest loop."""


_UNSET = object()   # "no such variable" sentinel (distinct from any real value)


class PlainFunction:
    """A function as a first-class value — it can be stored and passed around."""
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body


class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def lookup(self, name):
        """Return the value, or _UNSET if the name isn't defined (never raises)."""
        env = self
        while env:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        return _UNSET

    def visible_names(self):
        names = set()
        env = self
        while env:
            names.update(env.vars.keys())
            env = env.parent
        return names

    def get(self, name, line=None):
        val = self.lookup(name)
        if val is _UNSET:
            raise unknown_variable_error(name, self.visible_names(), line)
        return val

    def assign(self, name, value):
        env = self
        while env:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        self.vars[name] = value  # new variable, lives in current scope


class Interpreter:
    def __init__(self, on_output=None, on_input=None):
        self.globals = Environment()
        self.functions = {}
        self.current_line = None
        self.on_output = on_output or (lambda s: print(s))
        self.on_input = on_input or (lambda p: input(p))

    def run(self, tree):
        self.exec_block(tree, self.globals)

    def exec_block(self, node, env):
        for stmt in node[1]:
            self.exec_stmt(stmt, env)

    def exec_stmt(self, node, env):
        if node[0] == "@":
            self.current_line = node[1]
            node = node[2]
        op = node[0]

        if op == "set":
            env.assign(node[1], self.eval(node[2], env))

        elif op == "say":
            self.on_output(self.to_str(self.eval(node[1], env)))

        elif op == "ask":
            prompt = self.to_str(self.eval(node[1], env))
            raw = self.on_input(prompt + " ")
            env.assign(node[2], self._coerce_input(raw))

        elif op == "if":
            branches, else_block = node[1], node[2]
            for cond, body in branches:
                if self.truthy(self.eval(cond, env)):
                    self.exec_block(body, env)
                    return
            if else_block:
                self.exec_block(else_block, env)

        elif op == "match":
            _, subject, cases, else_block = node
            val = self.eval(subject, env)
            for value_expr, body in cases:
                if val == self.eval(value_expr, env):
                    self.exec_block(body, env)
                    return
            if else_block:
                self.exec_block(else_block, env)

        elif op == "repeat":
            count = self.eval(node[1], env)
            if not isinstance(count, (int, float)):
                raise PlainLangError(
                    "'repeat' needs a number of times to repeat.", self.current_line)
            for _ in range(int(count)):
                if self._loop_body(node[2], env):
                    break

        elif op == "while":
            guard = 0
            while self.truthy(self.eval(node[1], env)):
                if self._loop_body(node[2], env):
                    break
                guard += 1
                if guard > 1_000_000:
                    raise PlainLangError(
                        "This 'while' loop ran a million times and may never stop.",
                        self.current_line,
                        "Make sure something inside the loop changes the condition.")

        elif op == "count":
            _, var, start_e, stop_e, body = node
            start = int(self.eval(start_e, env))
            stop = int(self.eval(stop_e, env))
            step = 1 if stop >= start else -1
            for i in range(start, stop + step, step):
                env.assign(var, i)
                if self._loop_body(body, env):
                    break

        elif op == "foreach":
            _, var, seq_e, body = node
            seq = self.eval(seq_e, env)
            if not isinstance(seq, list):
                raise PlainLangError(
                    "'for each' needs a list to walk through.", self.current_line,
                    "Make one with:  set things to list of 1, 2, 3")
            for item in seq:
                env.assign(var, item)
                if self._loop_body(body, env):
                    break

        elif op == "break":
            raise BreakSignal()

        elif op == "continue":
            raise ContinueSignal()

        elif op == "define":
            _, name, params, body = node
            self.functions[name] = PlainFunction(name, params, body)

        elif op == "call":
            self.call_function(node[1], node[2], env)

        elif op == "return":
            raise ReturnSignal(self.eval(node[1], env))

        elif op == "add":
            value = self.eval(node[1], env)
            target = env.get(node[2], self.current_line)
            if not isinstance(target, list):
                raise PlainLangError(
                    f"I can only add to a list, but '{node[2]}' is not a list.",
                    self.current_line)
            target.append(value)

        elif op == "remove":
            index = int(self.eval(node[1], env))
            target = env.get(node[2], self.current_line)
            if not isinstance(target, list):
                raise PlainLangError(
                    f"I can only remove from a list, but '{node[2]}' is not a list.",
                    self.current_line)
            if index < 1 or index > len(target):
                raise PlainLangError(
                    f"There is no item {index} in '{node[2]}' "
                    f"(it has {len(target)} item(s)).", self.current_line)
            target.pop(index - 1)

        elif op == "setindex":
            target = self.eval(node[1], env)
            key = self.eval(node[2], env)
            value = self.eval(node[3], env)
            if isinstance(target, dict):
                target[key] = value
            elif isinstance(target, list):
                i = int(key)
                if i < 1 or i > len(target):
                    raise PlainLangError(
                        f"There is no item {i} (the list has {len(target)} item(s)).",
                        self.current_line, "Lists start counting at item 1.")
                target[i - 1] = value
            else:
                raise PlainLangError(
                    "'set item ... of ...' needs a list or a record.", self.current_line)

    def _loop_body(self, body, env):
        """Run one pass of a loop body. Returns True if 'stop' was requested."""
        try:
            self.exec_block(body, env)
        except ContinueSignal:
            pass
        except BreakSignal:
            return True
        return False

    def call_function(self, name, arg_exprs, env):
        # 'name with args' calls either a defined function or a variable that
        # holds a function value (first-class functions).
        fn = self.functions.get(name)
        if fn is None:
            val = env.lookup(name)
            if isinstance(val, PlainFunction):
                fn = val
            elif val is not _UNSET:
                raise PlainLangError(
                    f"'{name}' is not a function, so it can't be called with values.",
                    self.current_line)
            else:
                raise unknown_function_error(name, self.functions.keys(), self.current_line)
        if len(fn.params) != len(arg_exprs):
            raise PlainLangError(
                f"'{fn.name}' expects {len(fn.params)} value(s), "
                f"but got {len(arg_exprs)}.", self.current_line)
        local = Environment(self.globals)
        for p, a in zip(fn.params, arg_exprs):
            local.vars[p] = self.eval(a, env)
        try:
            self.exec_block(fn.body, local)
        except ReturnSignal as r:
            return r.value
        return None

    def _need_list_fn(self, fn, seq, name):
        if not isinstance(fn, PlainFunction):
            raise PlainLangError(f"'{name}' needs a function.", self.current_line)
        if not isinstance(seq, list):
            raise PlainLangError(f"'{name} ... over ...' needs a list.", self.current_line)

    def call_value(self, fn, args):
        """Invoke a PlainFunction with already-evaluated argument values."""
        if len(fn.params) != len(args):
            raise PlainLangError(
                f"'{fn.name}' expects {len(fn.params)} value(s), but got {len(args)}.",
                self.current_line)
        local = Environment(self.globals)
        for p, a in zip(fn.params, args):
            local.vars[p] = a
        try:
            self.exec_block(fn.body, local)
        except ReturnSignal as r:
            return r.value
        return None

    # — expression evaluation —
    def eval(self, node, env):
        op = node[0]
        if op == "num":  return node[1]
        if op == "str":  return node[1]
        if op == "bool": return node[1]
        if op == "var":
            name = node[1]
            val = env.lookup(name)
            if val is not _UNSET:
                return val
            if name in self.functions:        # a function used as a value
                return self.functions[name]
            raise unknown_variable_error(name, env.visible_names(), self.current_line)
        if op == "neg":  return -self.eval(node[1], env)

        if op == "list":
            return [self.eval(e, env) for e in node[1]]

        if op == "record":
            d = {}
            for k, v in node[1]:
                d[self.eval(k, env)] = self.eval(v, env)
            return d

        if op in ("map", "filter"):
            fn = self.eval(node[1], env)
            seq = self.eval(node[2], env)
            self._need_list_fn(fn, seq, op)
            if op == "map":
                return [self.call_value(fn, [x]) for x in seq]
            return [x for x in seq if self.truthy(self.call_value(fn, [x]))]

        if op == "reduce":
            fn = self.eval(node[1], env)
            seq = self.eval(node[2], env)
            acc = self.eval(node[3], env)
            self._need_list_fn(fn, seq, "reduce")
            for x in seq:
                acc = self.call_value(fn, [acc, x])
            return acc

        if op == "index":
            seq = self.eval(node[1], env)
            idx = self.eval(node[2], env)
            if isinstance(seq, dict):
                if idx not in seq:
                    raise PlainLangError(
                        f"There is no key '{self.to_str(idx)}' in that record.",
                        self.current_line,
                        _did_you_mean(self.to_str(idx), [self.to_str(k) for k in seq])
                        or "Check the spelling of the key.")
                return seq[idx]
            if not isinstance(seq, list):
                raise PlainLangError(
                    "'item ... of ...' needs a list or a record.", self.current_line)
            i = int(idx)
            if i < 1 or i > len(seq):
                raise PlainLangError(
                    f"There is no item {i} (the list has {len(seq)} item(s)).",
                    self.current_line,
                    "Lists start counting at item 1.")
            return seq[i - 1]

        if op == "binop":
            return self._binop(node[1], self.eval(node[2], env),
                               self.eval(node[3], env))

        if op == "cmp":
            return self._compare(node[1], self.eval(node[2], env),
                                self.eval(node[3], env))

        if op == "and":
            return self.truthy(self.eval(node[1], env)) and \
                   self.truthy(self.eval(node[2], env))
        if op == "or":
            return self.truthy(self.eval(node[1], env)) or \
                   self.truthy(self.eval(node[2], env))
        if op == "not":
            return not self.truthy(self.eval(node[1], env))

        if op == "builtin":
            return self._builtin(node[1], [self.eval(a, env) for a in node[2]])

        if op == "call":
            result = self.call_function(node[1], node[2], env)
            if result is None:
                raise PlainLangError(
                    f"The function '{node[1]}' was used as a value, "
                    f"but it didn't 'return' anything.", self.current_line)
            return result

        raise PlainLangError("I couldn't make sense of part of your program.",
                             self.current_line)

    def _binop(self, op, a, b):
        if op == "+":
            if isinstance(a, str) or isinstance(b, str):
                return self.to_str(a) + self.to_str(b)
            if isinstance(a, list) and isinstance(b, list):
                return a + b
            self._need_numbers("plus", a, b)
            return a + b
        if op == "-":
            self._need_numbers("minus", a, b); return a - b
        if op == "*":
            self._need_numbers("multiplied by", a, b); return a * b
        if op == "/":
            self._need_numbers("divided by", a, b)
            if b == 0:
                raise PlainLangError(
                    "You can't divide by zero.", self.current_line,
                    "Check the number you're dividing by.")
            result = a / b
            return int(result) if result == int(result) else result

    def _need_numbers(self, opname, a, b):
        for v in (a, b):
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise PlainLangError(
                    f"'{opname}' only works with numbers, "
                    f"but I got {self._type_name(v)}.", self.current_line)

    def _compare(self, op, a, b):
        try:
            return {"==": a == b, "!=": a != b,
                    ">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]
        except TypeError:
            raise PlainLangError(
                f"I can't compare {self._type_name(a)} with {self._type_name(b)}.",
                self.current_line)

    def _builtin(self, name, args):
        if name == "length":
            v = args[0]
            if isinstance(v, (list, str, dict)):
                return len(v)
            raise PlainLangError(
                "'length of' works on text, a list, or a record.", self.current_line)
        if name == "keys":
            v = args[0]
            if isinstance(v, dict):
                return list(v.keys())
            raise PlainLangError("'keys of' works on a record.", self.current_line)
        if name == "uppercase":
            return self.to_str(args[0]).upper()
        if name == "lowercase":
            return self.to_str(args[0]).lower()
        if name == "trim":
            return self.to_str(args[0]).strip()
        if name == "split":
            text, sep = self.to_str(args[0]), self.to_str(args[1])
            return list(text) if sep == "" else text.split(sep)
        if name == "join":
            seq = args[0]
            if not isinstance(seq, list):
                raise PlainLangError("'join' works on a list.", self.current_line)
            return self.to_str(args[1]).join(self.to_str(x) for x in seq)
        if name == "replace":
            old, new, text = self.to_str(args[0]), self.to_str(args[1]), self.to_str(args[2])
            return text.replace(old, new)
        if name == "position":
            part, text = self.to_str(args[0]), self.to_str(args[1])
            return text.find(part) + 1
        if name == "contains":
            container, part = args[0], args[1]
            if isinstance(container, list):
                return part in container
            return self.to_str(part) in self.to_str(container)
        if name == "round":
            return round(args[0])
        if name == "absolute":
            return abs(args[0])
        if name == "sqrt":
            if args[0] < 0:
                raise PlainLangError(
                    "I can't take the square root of a negative number.",
                    self.current_line)
            r = math.sqrt(args[0])
            return int(r) if r == int(r) else r
        if name == "random":
            low, high = int(args[0]), int(args[1])
            return random.randint(min(low, high), max(low, high))

    # — helpers —
    def truthy(self, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v != 0
        if isinstance(v, (str, list, dict)):
            return len(v) > 0
        return v is not None

    def _coerce_input(self, raw):
        try:
            return int(raw)
        except ValueError:
            try:
                return float(raw)
            except ValueError:
                return raw

    def to_str(self, v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, float) and v == int(v):
            return str(int(v))
        if isinstance(v, list):
            return "[" + ", ".join(self.to_str(x) for x in v) + "]"
        if isinstance(v, dict):
            return "{" + ", ".join(f"{self.to_str(k)}: {self.to_str(val)}"
                                   for k, val in v.items()) + "}"
        if isinstance(v, PlainFunction):
            return f"function {v.name}"
        return str(v)

    @staticmethod
    def _type_name(v):
        if isinstance(v, bool):           return "true/false"
        if isinstance(v, (int, float)):   return "a number"
        if isinstance(v, str):            return "some text"
        if isinstance(v, list):           return "a list"
        if isinstance(v, dict):           return "a record"
        if isinstance(v, PlainFunction):  return "a function"
        return "nothing"


# ─── Help text & CLI ─────────────────────────────────────────────────────────

HELP = """
PlainLang — code that reads like English
══════════════════════════════════════════

VARIABLES
  set name to "Alice"
  set age to 25

SHOW & ASK
  say "Hello, " plus name
  ask "What is your name?" into name

MATH        plus   minus   multiplied by   divided by
  set total to (3 plus 4) multiplied by 2

COMPARISONS (used in if / while)
  is equal to      is not equal to
  is greater than  is less than
  is at least      is at most
  combine with:  and   or   not

DECISIONS
  if age is at least 18 then
      say "adult"
  otherwise if age is at least 13 then
      say "teenager"
  otherwise
      say "child"
  end

LOOPS
  repeat 3 times ... end
  count i from 1 to 5 ... end
  while x is greater than 0 ... end
  for each item in things ... end

LISTS
  set fruits to list of "apple", "banana"
  set empties to empty list
  add "cherry" to fruits
  remove item 1 from fruits
  say item 2 of fruits
  say length of fruits

FUNCTIONS
  define double with n
      return n multiplied by 2
  end
  say double with 21          # used as a value
  call greet with "Bob"       # called as an action

BUILT-IN HELPERS
  length of X        uppercase of X     lowercase of X
  round of X         absolute of X      square root of X
  random between 1 and 6
"""


def _format_friendly(err):
    return err.show()


def run_source(source, on_output=print, on_input=input):
    """Run PlainLang source. Returns (ok, error_message)."""
    try:
        tokens = tokenize(source)
        tree = Parser(tokens).parse()
        Interpreter(on_output, on_input).run(tree)
        return True, None
    except PlainLangError as e:
        msg = format_error(source, e)
        on_output(msg)
        return False, msg
    except (BreakSignal, ContinueSignal):
        word = "stop" if isinstance(sys.exc_info()[1], BreakSignal) else "skip"
        msg = format_error(source, PlainLangError(
            f"'{word}' can only be used inside a loop.", None))
        on_output(msg)
        return False, msg
    except RecursionError:
        msg = "\n  Oops! A function called itself too many times (no stopping point)."
        on_output(msg)
        return False, msg


def run_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"I couldn't find a file called '{path}'.")
        return
    run_source(source)


def repl():
    print("PlainLang  ·  type 'help' for syntax, 'quit' to leave")
    interp = Interpreter()
    buffer, depth = [], 0
    openers = ("if", "repeat", "while", "count", "for", "define")
    while True:
        try:
            line = input("... " if buffer else ">>> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not buffer:
            cmd = line.strip().lower()
            if cmd == "quit":
                break
            if cmd == "help":
                print(HELP); continue
            if cmd == "":
                continue
        buffer.append(line)
        words = line.strip().split()
        if words:
            if words[0] in openers:
                depth += 1
            if words[0] == "end":
                depth -= 1
        if depth <= 0:
            source = "\n".join(buffer)
            buffer, depth = [], 0
            try:
                tokens = tokenize(source)
                tree = Parser(tokens).parse()
                interp.run(tree)
            except PlainLangError as e:
                print(format_error(source, e))
            except ReturnSignal:
                pass


if __name__ == "__main__":
    if len(sys.argv) == 1:
        repl()
    elif sys.argv[1] in ("-h", "--help", "help"):
        print(HELP)
    else:
        run_file(sys.argv[1])
