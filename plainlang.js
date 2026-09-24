/*
 * PlainLang — JavaScript engine
 * ------------------------------------------------------------------
 * A faithful port of the Python interpreter, extended with:
 *   - turtle graphics (visual output on a canvas)
 *   - execution tracing (for the time-travel debugger)
 *
 * Public API:
 *   PlainLang.run(source, options) -> {
 *       ok, error, output (string[]),
 *       trace (Frame[]), turtle (Segment[])
 *   }
 *
 * A Frame is a snapshot taken just before each statement runs:
 *   { line, vars: {name: displayValue}, outputLen, turtleLen, turtle:{x,y,angle,penDown,color} }
 *
 * Works in the browser and in Node (module.exports at the bottom).
 */
(function (global) {
  "use strict";

  // ─── Errors & diagnostics ──────────────────────────────────────────────────
  class PlainLangError extends Error {
    constructor(message, line, hint, col, length, near) {
      super(message);
      this.plMessage = message;
      this.line = line || null;
      this.hint = hint || null;
      this.col = col != null ? col : null;       // 1-based column of the token
      this.length = length != null ? length : null;
      this.near = near || null;                  // identifier to locate when col is unknown
    }
    show() {
      const where = this.line ? `line ${this.line}` : "your program";
      let out = `Oops! Something went wrong on ${where}:\n    ${this.plMessage}`;
      if (this.hint) out += `\n  Hint: ${this.hint}`;
      return out;
    }
  }

  function levenshtein(a, b) {
    if (a === b) return 0;
    if (!a || !b) return a.length + b.length;
    let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i++) {
      const cur = [i];
      for (let j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0));
      }
      prev = cur;
    }
    return prev[b.length];
  }

  function suggest(name, candidates) {
    let best = null, bestD = 999;
    const low = name.toLowerCase();
    for (const c of [...new Set(candidates)].sort()) {   // sorted -> stable ties
      const d = levenshtein(low, c.toLowerCase());
      if (d < bestD) { best = c; bestD = d; }
    }
    if (best !== null && bestD <= Math.min(3, Math.max(1, Math.floor(name.length / 2) + 1))) return best;
    return null;
  }
  function didYouMean(name, candidates) {
    const s = suggest(name, candidates);
    return s ? `Did you mean '${s}'?` : null;
  }
  function unknownVariableError(name, candidates, line) {
    const visible = [...candidates].filter((c) => !c.startsWith("$"));
    const hint = didYouMean(name, visible) || `Create it first with:  set ${name} to ...`;
    return new PlainLangError(`I haven't heard of a variable called '${name}' yet.`, line, hint, null, null, name);
  }
  function unknownFunctionError(name, candidates, line) {
    const hint = didYouMean(name, [...candidates]) || `Teach me one with:  define ${name} ... end`;
    return new PlainLangError(`I don't know a function called '${name}'.`, line, hint, null, null, name);
  }

  function formatError(source, err) {
    if (!(err instanceof PlainLangError)) return "Error: " + (err && err.message);
    if (!err.line) return err.show();
    const lines = source.split("\n");
    if (err.line < 1 || err.line > lines.length) return err.show();
    const src = lines[err.line - 1];
    let col = err.col, length = err.length;
    if (col == null && err.near) {
      const idx = src.indexOf(err.near);
      if (idx >= 0) { col = idx + 1; length = err.near.length; }
    }
    const num = String(err.line);
    let out = `Oops! Something went wrong on line ${err.line}:\n    ${err.plMessage}\n\n    ${num} | ${src}`;
    if (col) out += `\n    ${" ".repeat(num.length + 3 + col - 1)}${"^".repeat(Math.max(1, length || 1))}`;
    if (err.hint) out += `\n  Hint: ${err.hint}`;
    return out;
  }

  // ─── Tokenizer ───────────────────────────────────────────────────────────
  const KEYWORDS = new Set([
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
    "sum", "average", "smallest", "largest", "first", "last", "reverse", "sorted", "remainder",
    "floor", "ceiling", "power", "min", "max",
    // turtle vocabulary
    "move", "forward", "backward", "back", "turn", "left", "right",
    "pen", "up", "down", "color", "wait",
  ]);

  function tokenize(source) {
    // Each token is [kind, value, line, col, length]; col is 1-based so errors
    // can underline the exact source text with a caret.
    const tokens = [];
    let line = 1;
    let lineStart = 0;
    let i = 0;
    const n = source.length;
    const isAlpha = (c) => /[A-Za-z_]/.test(c);
    const isAlnum = (c) => /[A-Za-z0-9_]/.test(c);
    const isDigit = (c) => c >= "0" && c <= "9";

    while (i < n) {
      const c = source[i];
      if (c === "\n") { line++; i++; lineStart = i; continue; }
      if (c === " " || c === "\t" || c === "\r") { i++; continue; }
      if (c === "#") { while (i < n && source[i] !== "\n") i++; continue; }
      const col = i - lineStart + 1;
      if (c === "(") { tokens.push(["LPAREN", "(", line, col, 1]); i++; continue; }
      if (c === ")") { tokens.push(["RPAREN", ")", line, col, 1]); i++; continue; }
      if (c === ",") { tokens.push(["COMMA", ",", line, col, 1]); i++; continue; }
      if (c === '"') {
        let j = i + 1, s = "";
        while (j < n && source[j] !== '"') { s += source[j]; j++; }
        if (j >= n) throw new PlainLangError("This text is missing its closing quote (\").", line, null, col, 1);
        tokens.push(["STRING", s, line, col, j + 1 - i]);
        i = j + 1;
        continue;
      }
      if (isDigit(c)) {
        let j = i, s = "";
        while (j < n && isDigit(source[j])) { s += source[j]; j++; }
        if (source[j] === "." && isDigit(source[j + 1])) {
          s += "."; j++;
          while (j < n && isDigit(source[j])) { s += source[j]; j++; }
        }
        const num = parseFloat(s);
        if (!Number.isFinite(num)) throw new PlainLangError("That number is too big for PlainLang to hold.", line, null, col, j - i);
        tokens.push(["NUMBER", num, line, col, j - i]);
        i = j;
        continue;
      }
      if (isAlpha(c)) {
        let j = i, s = "";
        while (j < n && isAlnum(source[j])) { s += source[j]; j++; }
        const low = s.toLowerCase();
        tokens.push(KEYWORDS.has(low) ? ["KW", low, line, col, j - i] : ["IDENT", s, line, col, j - i]);
        i = j;
        continue;
      }
      throw new PlainLangError(
        `I don't understand the symbol '${c}'.`, line,
        "PlainLang uses words like 'plus' and 'is greater than' instead of symbols.", col, 1);
    }
    tokens.push(["EOF", null, line, i - lineStart + 1, 1]);
    return tokens;
  }

  // ─── Parser ──────────────────────────────────────────────────────────────
  const BLOCK_ENDERS = new Set(["end", "otherwise", "when"]);
  const STATEMENT_KW = ["set", "say", "ask", "if", "repeat", "while", "count",
    "for", "define", "call", "return", "add", "remove", "move", "turn", "pen"];
  const VALUE_START_KW = new Set(["true", "false", "empty", "list", "item", "length",
    "uppercase", "lowercase", "round", "absolute", "square", "random", "minus",
    "floor", "ceiling", "power", "min", "max"]);

  class Parser {
    constructor(tokens) { this.t = tokens; this.p = 0; }
    peek() { return this.t[this.p]; }
    kind() { return this.t[this.p][0]; }
    line() { return this.t[this.p][2]; }
    isKw(...words) { const x = this.t[this.p]; return x[0] === "KW" && words.includes(x[1]); }
    advance() { return this.t[this.p++]; }

    describe(x) {
      if (x[0] === "EOF") return "the end of the program";
      if (x[0] === "STRING") return `the text "${x[1]}"`;
      if (x[0] === "NUMBER") return `the number ${x[1]}`;
      return `'${x[1]}'`;
    }
    span(x) { return [x[3] != null ? x[3] : null, x[4] != null ? x[4] : null]; }
    eatKw(word) {
      const x = this.peek();
      if (x[0] !== "KW" || x[1] !== word) {
        const [col, len] = this.span(x);
        throw new PlainLangError(`I expected the word '${word}' here, but found ${this.describe(x)}.`, x[2], null, col, len);
      }
      return this.advance();
    }
    eat(kind, label) {
      const x = this.peek();
      if (x[0] !== kind) {
        const [col, len] = this.span(x);
        throw new PlainLangError(`I expected ${label} here, but found ${this.describe(x)}.`, x[2], null, col, len);
      }
      return this.advance();
    }

    parse() {
      const stmts = [];
      while (this.kind() !== "EOF") stmts.push(this.statement());
      return ["block", stmts];
    }
    block() {
      const stmts = [];
      while (this.kind() !== "EOF" && !(this.peek()[0] === "KW" && BLOCK_ENDERS.has(this.peek()[1])))
        stmts.push(this.statement());
      return ["block", stmts];
    }

    statement() {
      const ln = this.line();
      return ["@", ln, this.inner()];
    }
    inner() {
      if (this.isKw("set")) return this.setStmt();
      if (this.isKw("say")) return this.sayStmt();
      if (this.isKw("ask")) return this.askStmt();
      if (this.isKw("if")) return this.ifStmt();
      if (this.isKw("match")) return this.matchStmt();
      if (this.isKw("repeat")) return this.repeatStmt();
      if (this.isKw("while")) return this.whileStmt();
      if (this.isKw("count")) return this.countStmt();
      if (this.isKw("for")) return this.foreachStmt();
      if (this.isKw("define")) return this.defineStmt();
      if (this.isKw("call")) return this.callStmt();
      if (this.isKw("return")) return this.returnStmt();
      if (this.isKw("add")) return this.addStmt();
      if (this.isKw("remove")) return this.removeStmt();
      if (this.isKw("stop")) { this.advance(); return ["break"]; }
      if (this.isKw("skip")) { this.advance(); return ["continue"]; }
      if (this.isKw("move")) return this.moveStmt();
      if (this.isKw("turn")) return this.turnStmt();
      if (this.isKw("pen")) return this.penStmt();
      if (this.isKw("wait")) return this.waitStmt();
      if (this.kind() === "IDENT") return this.callStmt();
      const x = this.peek();
      const [col, len] = this.span(x);
      let hint = "Statements begin with words like set, say, if, repeat, for, define, or move.";
      if (x[0] === "IDENT") {
        const s = suggest(x[1], STATEMENT_KW);
        if (s) hint = `Did you mean '${s}'?`;
      }
      throw new PlainLangError(
        `I don't know how to start a statement with ${this.describe(x)}.`, x[2], hint, col, len);
    }

    setStmt() {
      this.eatKw("set");
      if (this.isKw("item")) {   // set item KEY of TARGET to VALUE
        this.advance();
        const key = this.expression();
        this.eatKw("of");
        const target = this.primary();
        this.eatKw("to");
        return ["setindex", target, key, this.expression()];
      }
      const name = this.eat("IDENT", "a variable name")[1];
      this.eatKw("to");
      return ["set", name, this.expression()];
    }
    recordLiteral() {
      this.eatKw("record"); this.eatKw("with");
      const pairs = [];
      for (;;) {
        const key = this.comparison();
        this.eatKw("as");
        const value = this.comparison();
        pairs.push([key, value]);
        if (this.kind() === "COMMA") this.advance(); else break;
      }
      return ["record", pairs];
    }
    sayStmt() { this.eatKw("say"); return ["say", this.expression()]; }
    askStmt() { this.eatKw("ask"); const p = this.expression(); this.eatKw("into"); const name = this.eat("IDENT", "a variable name")[1]; return ["ask", p, name]; }

    matchStmt() {
      this.eatKw("match");
      const subject = this.expression();
      const cases = [];
      while (this.isKw("when")) {
        this.advance();
        const value = this.expression();
        this.eatKw("then");
        cases.push([value, this.block()]);
      }
      let elseBlock = null;
      if (this.isKw("otherwise")) { this.advance(); elseBlock = this.block(); }
      this.eatKw("end");
      return ["match", subject, cases, elseBlock];
    }
    ifStmt() {
      this.eatKw("if");
      const branches = [];
      let cond = this.expression(); this.eatKw("then");
      branches.push([cond, this.block()]);
      let elseBlock = null;
      while (this.isKw("otherwise")) {
        const otherLine = this.advance()[2];
        // 'otherwise if' chains only when 'if' is on the same line; an 'if' on the
        // next line is an ordinary statement inside the else-block
        if (this.isKw("if") && this.peek()[2] === otherLine) {
          this.advance();
          cond = this.expression(); this.eatKw("then");
          branches.push([cond, this.block()]);
        } else { elseBlock = this.block(); break; }
      }
      this.eatKw("end");
      return ["if", branches, elseBlock];
    }
    repeatStmt() { this.eatKw("repeat"); const c = this.expression(); this.eatKw("times"); const b = this.block(); this.eatKw("end"); return ["repeat", c, b]; }
    whileStmt() { this.eatKw("while"); const c = this.expression(); const b = this.block(); this.eatKw("end"); return ["while", c, b]; }
    countStmt() {
      this.eatKw("count");
      const v = this.eat("IDENT", "a counter variable name")[1];
      this.eatKw("from"); const s = this.expression();
      this.eatKw("to"); const e = this.expression();
      const b = this.block(); this.eatKw("end");
      return ["count", v, s, e, b];
    }
    foreachStmt() {
      this.eatKw("for"); this.eatKw("each");
      const v = this.eat("IDENT", "a loop variable name")[1];
      this.eatKw("in"); const seq = this.expression();
      const b = this.block(); this.eatKw("end");
      return ["foreach", v, seq, b];
    }
    defineStmt() {
      this.eatKw("define");
      const name = this.eat("IDENT", "a function name")[1];
      const params = [];
      if (this.isKw("with")) {
        this.advance();
        params.push(this.eat("IDENT", "a parameter name")[1]);
        while (this.isKw("and")) { this.advance(); params.push(this.eat("IDENT", "a parameter name")[1]); }
      }
      const b = this.block(); this.eatKw("end");
      return ["define", name, params, b];
    }
    callStmt() {
      if (this.isKw("call")) this.advance();
      const nameTok = this.eat("IDENT", "a function name");
      const name = nameTok[1];
      // A bare name followed by a value (not 'with') that looks like a mistyped
      // keyword is almost certainly a typo:  saay "hi"  ->  say
      if (!this.isKw("with")) {
        const nxt = this.peek();
        const looksLikeValue = ["STRING", "NUMBER", "IDENT", "LPAREN"].includes(nxt[0]) ||
          (nxt[0] === "KW" && VALUE_START_KW.has(nxt[1]));
        if (looksLikeValue) {
          const s = suggest(name, STATEMENT_KW);
          if (s) {
            const [col, len] = this.span(nameTok);
            throw new PlainLangError(`I don't know how to start a statement with '${name}'.`,
              nameTok[2], `Did you mean '${s}'?`, col, len);
          }
        }
      }
      return ["call", name, this.maybeArgs()];
    }
    maybeArgs() {
      // Arguments are separated by 'and' (also the boolean operator), so each
      // argument parses below 'and'/'or'. Use parens for a boolean argument.
      const args = [];
      if (this.isKw("with")) {
        this.advance();
        args.push(this.comparison());
        while (this.isKw("and")) { this.advance(); args.push(this.comparison()); }
      }
      return args;
    }
    returnStmt() { this.eatKw("return"); return ["return", this.expression()]; }
    addStmt() { this.eatKw("add"); const v = this.expression(); this.eatKw("to"); const name = this.eat("IDENT", "a list variable name")[1]; return ["add", v, name]; }
    removeStmt() { this.eatKw("remove"); this.eatKw("item"); const idx = this.expression(); this.eatKw("from"); const name = this.eat("IDENT", "a list variable name")[1]; return ["remove", idx, name]; }

    // turtle
    moveStmt() {
      this.eatKw("move");
      let dir = "forward";
      if (this.isKw("forward")) { this.advance(); dir = "forward"; }
      else if (this.isKw("backward", "back")) { this.advance(); dir = "back"; }
      return ["move", dir, this.expression()];
    }
    turnStmt() {
      this.eatKw("turn");
      let dir = "right";
      if (this.isKw("right")) { this.advance(); dir = "right"; }
      else if (this.isKw("left")) { this.advance(); dir = "left"; }
      return ["turn", dir, this.expression()];
    }
    penStmt() {
      this.eatKw("pen");
      if (this.isKw("up")) { this.advance(); return ["pen", "up"]; }
      if (this.isKw("down")) { this.advance(); return ["pen", "down"]; }
      if (this.isKw("color")) { this.advance(); this.eatKw("to"); return ["pencolor", this.expression()]; }
      const x = this.peek();
      throw new PlainLangError("After 'pen' I expected 'up', 'down', or 'color to ...'.", x[2]);
    }
    waitStmt() { this.eatKw("wait"); return ["wait", this.expression()]; }

    // expressions
    expression() { return this.orExpr(); }
    orExpr() { let l = this.andExpr(); while (this.isKw("or")) { this.advance(); l = ["or", l, this.andExpr()]; } return l; }
    andExpr() { let l = this.notExpr(); while (this.isKw("and")) { this.advance(); l = ["and", l, this.notExpr()]; } return l; }
    notExpr() { if (this.isKw("not")) { this.advance(); return ["not", this.notExpr()]; } return this.comparison(); }
    comparison() {
      const l = this.arith();
      if (this.isKw("is")) { this.advance(); const op = this.compOp(); return ["cmp", op, l, this.arith()]; }
      if (this.isKw("contains")) { this.advance(); return ["builtin", "contains", [l, this.arith()]]; }
      return l;
    }
    compOp() {
      if (this.isKw("not")) { this.advance(); if (this.isKw("equal")) { this.advance(); if (this.isKw("to")) this.advance(); } return "!="; }
      if (this.isKw("greater")) { this.advance(); this.eatKw("than"); return ">"; }
      if (this.isKw("less")) { this.advance(); this.eatKw("than"); return "<"; }
      if (this.isKw("at")) {
        this.advance();
        if (this.isKw("least")) { this.advance(); return ">="; }
        if (this.isKw("most")) { this.advance(); return "<="; }
        throw new PlainLangError("After 'is at' I expected 'least' or 'most'.", this.line());
      }
      if (this.isKw("equal")) { this.advance(); if (this.isKw("to")) this.advance(); return "=="; }
      return "==";
    }
    arith() {
      let l = this.term();
      while (this.isKw("plus", "minus")) { const op = this.advance()[1] === "plus" ? "+" : "-"; l = ["binop", op, l, this.term()]; }
      return l;
    }
    term() {
      let l = this.factor();
      while (this.isKw("multiplied", "divided")) { const w = this.advance()[1]; this.eatKw("by"); l = ["binop", w === "multiplied" ? "*" : "/", l, this.factor()]; }
      return l;
    }
    factor() { if (this.isKw("minus")) { this.advance(); return ["neg", this.factor()]; } return this.primary(); }
    interpolate(text, line) {
      // "Hi {name}!"  ->  "" + "Hi " + name + "!"   ({{ }} are literal braces)
      if (text.indexOf("{") < 0 && text.indexOf("}") < 0) return ["str", text];
      const parts = [];
      let buf = "", i = 0;
      while (i < text.length) {
        const c = text[i];
        if (c === "{" && text[i + 1] === "{") { buf += "{"; i += 2; continue; }
        if (c === "}" && text[i + 1] === "}") { buf += "}"; i += 2; continue; }
        if (c === "{") {
          if (buf) { parts.push(["str", buf]); buf = ""; }
          const j = text.indexOf("}", i + 1);
          if (j < 0) throw new PlainLangError("This text has a '{' with no matching '}'.", line, "Use {{ if you meant a real curly brace.");
          const exprSrc = text.slice(i + 1, j).trim();
          if (!exprSrc) throw new PlainLangError("There's an empty {} in this text.", line, "Put a variable or value between the braces.");
          let node;
          try {
            const inner = new Parser(tokenize(exprSrc));
            node = inner.expression();
            if (inner.kind() !== "EOF")            // {x y} used to silently drop the 'y'
              throw new PlainLangError(`I found ${inner.describe(inner.peek())} after the value`);
          }
          catch (e) { throw new PlainLangError(`I couldn't understand '{${exprSrc}}': ${e.plMessage || e.message}`, line); }
          parts.push(node);
          i = j + 1;
          continue;
        }
        buf += c; i += 1;
      }
      if (buf) parts.push(["str", buf]);
      let result = ["str", ""];
      for (const p of parts) result = ["binop", "+", result, p];
      return result;
    }
    primary() {
      const x = this.peek();
      if (x[0] === "NUMBER") { this.advance(); return ["num", x[1]]; }
      if (x[0] === "STRING") { const tok = this.advance(); return this.interpolate(tok[1], tok[2]); }
      if (x[0] === "LPAREN") { this.advance(); const e = this.expression(); this.eat("RPAREN", "a closing ')'"); return e; }
      if (this.isKw("true")) { this.advance(); return ["bool", true]; }
      if (this.isKw("false")) { this.advance(); return ["bool", false]; }
      if (this.isKw("empty")) {
        this.advance();
        if (this.isKw("record")) { this.advance(); return ["record", []]; }
        this.eatKw("list"); return ["list", []];
      }
      if (this.isKw("list")) {
        this.advance(); this.eatKw("of");
        const items = [this.expression()];
        while (this.kind() === "COMMA") { this.advance(); items.push(this.expression()); }
        return ["list", items];
      }
      if (this.isKw("record")) return this.recordLiteral();
      if (this.isKw("map", "filter")) { const kind = this.advance()[1]; const fn = this.comparison(); this.eatKw("over"); return [kind, fn, this.comparison()]; }
      if (this.isKw("reduce")) { this.advance(); const fn = this.comparison(); this.eatKw("over"); const seq = this.comparison(); this.eatKw("from"); return ["reduce", fn, seq, this.comparison()]; }
      if (this.isKw("item")) { this.advance(); const idx = this.expression(); this.eatKw("of"); const seq = this.primary(); return ["index", seq, idx]; }
      if (this.isKw("length", "uppercase", "lowercase", "round", "absolute", "keys", "trim",
                    "sum", "average", "smallest", "largest", "first", "last", "reverse", "sorted",
                    "floor", "ceiling")) {
        const name = this.advance()[1]; this.eatKw("of"); return ["builtin", name, [this.primary()]];
      }
      if (this.isKw("square")) { this.advance(); this.eatKw("root"); this.eatKw("of"); return ["builtin", "sqrt", [this.primary()]]; }
      if (this.isKw("remainder", "power", "min", "max")) {
        const name = this.advance()[1]; this.eatKw("of"); const a = this.arith(); this.eatKw("and"); return ["builtin", name, [a, this.arith()]];
      }
      if (this.isKw("random")) { this.advance(); this.eatKw("between"); const lo = this.arith(); this.eatKw("and"); const hi = this.arith(); return ["builtin", "random", [lo, hi]]; }
      if (this.isKw("split")) { this.advance(); const t = this.comparison(); this.eatKw("by"); return ["builtin", "split", [t, this.comparison()]]; }
      if (this.isKw("join")) { this.advance(); const s = this.comparison(); this.eatKw("by"); return ["builtin", "join", [s, this.comparison()]]; }
      if (this.isKw("replace")) { this.advance(); const o = this.comparison(); this.eatKw("by"); const n = this.comparison(); this.eatKw("in"); return ["builtin", "replace", [o, n, this.comparison()]]; }
      if (this.isKw("position")) { this.advance(); this.eatKw("of"); const p = this.comparison(); this.eatKw("in"); return ["builtin", "position", [p, this.comparison()]]; }
      if (x[0] === "IDENT") {
        this.advance();
        if (this.isKw("with")) {
          this.advance();
          const args = [this.comparison()];
          while (this.isKw("and")) { this.advance(); args.push(this.comparison()); }
          return ["call", x[1], args];
        }
        return ["var", x[1]];
      }
      const [col, len] = this.span(x);
      throw new PlainLangError(
        `I expected a value here, but found ${this.describe(x)}.`, x[2],
        'A value is a number, some "text", a variable, or a list.', col, len);
    }
  }

  // ─── Interpreter ─────────────────────────────────────────────────────────
  const RETURN = Symbol("return");
  const BREAK = Symbol("break");        // thrown by 'stop'
  const CONTINUE = Symbol("continue");  // thrown by 'skip'
  const breakSignal = () => { const e = new Error("stop"); e[BREAK] = true; return e; };
  const continueSignal = () => { const e = new Error("skip"); e[CONTINUE] = true; return e; };

  const UNSET = Symbol("unset");
  class Environment {
    constructor(parent) { this.vars = Object.create(null); this.parent = parent || null; }
    lookup(name) {
      let e = this;
      while (e) { if (name in e.vars) return e.vars[name]; e = e.parent; }
      return UNSET;
    }
    names() {
      const out = [];
      for (let e = this; e; e = e.parent) for (const k in e.vars) out.push(k);
      return out;
    }
    get(name, line) {
      const v = this.lookup(name);
      if (v === UNSET) throw unknownVariableError(name, this.names(), line);
      return v;
    }
    assign(name, value) {
      let e = this;
      while (e) { if (name in e.vars) { e.vars[name] = value; return; } e = e.parent; }
      this.vars[name] = value;
    }
    flatten() {
      // child overrides parent; returns {name: value}
      const out = {};
      const chain = [];
      let e = this; while (e) { chain.push(e); e = e.parent; }
      for (let k = chain.length - 1; k >= 0; k--) Object.assign(out, chain[k].vars);
      return out;
    }
  }

  class Interpreter {
    constructor(options) {
      options = options || {};
      this.globals = new Environment();
      this.functions = Object.create(null);
      this.currentLine = null;
      this.output = [];
      this.trace = [];
      this.maxSteps = options.maxSteps || 200000;
      this.steps = 0;
      this.inputs = options.inputs || [];     // queued answers for `ask`
      this.inputIndex = 0;
      this.rng = options.rng || Math.random;
      // turtle state
      this.turtle = { x: 0, y: 0, angle: 0, penDown: true, color: "#38bdf8" };
      this.segments = [];                      // {x1,y1,x2,y2,color}
    }

    snapshot(line) {
      if (this.trace.length < 60000) {
        const vars = this.globals.flatten();
        const display = {};
        for (const k in vars) display[k] = toStr(vars[k]);
        this.trace.push({
          line,
          vars: display,
          outputLen: this.output.length,
          turtleLen: this.segments.length,
          turtle: { x: this.turtle.x, y: this.turtle.y, angle: this.turtle.angle, penDown: this.turtle.penDown, color: this.turtle.color },
        });
      }
    }

    tick() {
      if (++this.steps > this.maxSteps)
        throw new PlainLangError("Your program ran for too long and was stopped.", this.currentLine, "Check for a loop that never ends.");
    }

    run(tree) { this.execBlock(tree, this.globals); }
    execBlock(node, env) { for (const s of node[1]) this.execStmt(s, env); }

    execStmt(node, env) {
      if (node[0] === "@") { this.currentLine = node[1]; this.snapshot(node[1]); node = node[2]; }
      this.tick();
      const op = node[0];

      if (op === "set") { env.assign(node[1], this.eval(node[2], env)); return; }
      if (op === "say") { this.output.push(toStr(this.eval(node[1], env))); return; }
      if (op === "ask") {
        const ans = this.inputIndex < this.inputs.length ? this.inputs[this.inputIndex++] : "";
        env.assign(node[2], coerceInput(ans)); return;
      }
      if (op === "if") {
        for (const [cond, body] of node[1]) if (truthy(this.eval(cond, env))) { this.execBlock(body, env); return; }
        if (node[2]) this.execBlock(node[2], env);
        return;
      }
      if (op === "match") {
        const val = this.eval(node[1], env);
        for (const [valueExpr, body] of node[2]) {
          if (val === this.eval(valueExpr, env)) { this.execBlock(body, env); return; }
        }
        if (node[3]) this.execBlock(node[3], env);
        return;
      }
      if (op === "repeat") {
        const c = this.eval(node[1], env);
        if (typeof c !== "number") throw new PlainLangError("'repeat' needs a number of times to repeat.", this.currentLine);
        for (let k = 0; k < Math.floor(c); k++) { this.tick(); if (this.loopBody(node[2], env)) break; }
        return;
      }
      if (op === "while") {
        while (truthy(this.eval(node[1], env))) { this.tick(); if (this.loopBody(node[2], env)) break; }
        return;
      }
      if (op === "count") {
        const start = Math.floor(this.eval(node[2], env));
        const stop = Math.floor(this.eval(node[3], env));
        const step = stop >= start ? 1 : -1;
        for (let i = start; step > 0 ? i <= stop : i >= stop; i += step) { this.tick(); env.assign(node[1], i); if (this.loopBody(node[4], env)) break; }
        return;
      }
      if (op === "foreach") {
        const seq = this.eval(node[2], env);
        if (!Array.isArray(seq)) throw new PlainLangError("'for each' needs a list to walk through.", this.currentLine, "Make one with:  set things to list of 1, 2, 3");
        for (const item of seq) { this.tick(); env.assign(node[1], item); if (this.loopBody(node[3], env)) break; }
        return;
      }
      if (op === "break") { throw breakSignal(); }
      if (op === "continue") { throw continueSignal(); }
      if (op === "define") { this.functions[node[1]] = { __plfn: true, name: node[1], params: node[2], body: node[3] }; return; }
      if (op === "call") { this.callFunction(node[1], node[2], env); return; }
      if (op === "return") { const v = this.eval(node[1], env); const e = new Error("return"); e[RETURN] = true; e.value = v; throw e; }
      if (op === "add") {
        const v = this.eval(node[1], env); const t = env.get(node[2], this.currentLine);
        if (!Array.isArray(t)) throw new PlainLangError(`I can only add to a list, but '${node[2]}' is not a list.`, this.currentLine);
        t.push(v); return;
      }
      if (op === "remove") {
        const idx = Math.floor(this.eval(node[1], env)); const t = env.get(node[2], this.currentLine);
        if (!Array.isArray(t)) throw new PlainLangError(`I can only remove from a list, but '${node[2]}' is not a list.`, this.currentLine);
        if (idx < 1 || idx > t.length) throw new PlainLangError(`There is no item ${idx} in '${node[2]}' (it has ${t.length} item(s)).`, this.currentLine);
        t.splice(idx - 1, 1); return;
      }
      if (op === "setindex") {
        const target = this.eval(node[1], env);
        const key = this.eval(node[2], env);
        const value = this.eval(node[3], env);
        if (isDict(target)) { target[key] = value; return; }
        if (Array.isArray(target)) {
          const i = Math.floor(key);
          if (i < 1 || i > target.length) throw new PlainLangError(`There is no item ${i} (the list has ${target.length} item(s)).`, this.currentLine, "Lists start counting at item 1.");
          target[i - 1] = value; return;
        }
        throw new PlainLangError("'set item ... of ...' needs a list or a record.", this.currentLine);
      }
      // turtle
      if (op === "move") {
        const dist = this.eval(node[2], env);
        if (typeof dist !== "number") throw new PlainLangError("'move' needs a number of steps.", this.currentLine);
        const sign = node[1] === "forward" ? 1 : -1;
        const rad = (this.turtle.angle - 90) * Math.PI / 180; // 0 = up
        const nx = this.turtle.x + Math.cos(rad) * dist * sign;
        const ny = this.turtle.y + Math.sin(rad) * dist * sign;
        if (this.turtle.penDown) this.segments.push({ x1: this.turtle.x, y1: this.turtle.y, x2: nx, y2: ny, color: this.turtle.color });
        this.turtle.x = nx; this.turtle.y = ny; return;
      }
      if (op === "turn") {
        const deg = this.eval(node[2], env);
        if (typeof deg !== "number") throw new PlainLangError("'turn' needs a number of degrees.", this.currentLine);
        this.turtle.angle += node[1] === "right" ? deg : -deg; return;
      }
      if (op === "pen") { this.turtle.penDown = node[1] === "down"; return; }
      if (op === "pencolor") { this.turtle.color = String(this.eval(node[1], env)); return; }
      if (op === "wait") { return; /* no-op in trace model; UI controls timing */ }
    }

    loopBody(body, env) {
      // Run one pass of a loop body; return true if 'stop' was requested.
      try { this.execBlock(body, env); }
      catch (e) { if (e[CONTINUE]) return false; if (e[BREAK]) return true; throw e; }
      return false;
    }

    callFunction(name, argExprs, env) {
      // 'name with args' calls a defined function or a variable holding one.
      let fn = this.functions[name];
      if (!fn) {
        const v = env.lookup(name);
        if (v && v.__plfn) fn = v;
        else if (v !== UNSET) throw new PlainLangError(`'${name}' is not a function, so it can't be called with values.`, this.currentLine);
        else throw unknownFunctionError(name, Object.keys(this.functions), this.currentLine);
      }
      if (fn.params.length !== argExprs.length)
        throw new PlainLangError(`'${fn.name}' expects ${fn.params.length} value(s), but got ${argExprs.length}.`, this.currentLine);
      const local = new Environment(this.globals);
      for (let k = 0; k < fn.params.length; k++) local.vars[fn.params[k]] = this.eval(argExprs[k], env);
      const callerLine = this.currentLine;
      try { this.execBlock(fn.body, local); }
      catch (e) { if (e[RETURN]) return e.value; throw e; }
      finally { this.currentLine = callerLine; }
      return null;
    }

    invoke(fn, args) {
      // call a function value with already-evaluated arguments (for map/filter/reduce)
      if (fn.params.length !== args.length)
        throw new PlainLangError(`'${fn.name}' expects ${fn.params.length} value(s), but got ${args.length}.`, this.currentLine);
      const local = new Environment(this.globals);
      for (let k = 0; k < fn.params.length; k++) local.vars[fn.params[k]] = args[k];
      const callerLine = this.currentLine;
      try { this.execBlock(fn.body, local); }
      catch (e) { if (e[RETURN]) return e.value; throw e; }
      finally { this.currentLine = callerLine; }
      return null;
    }
    needListFn(fn, seq, name) {
      if (!isPlFn(fn)) throw new PlainLangError(`'${name}' needs a function.`, this.currentLine);
      if (!Array.isArray(seq)) throw new PlainLangError(`'${name} ... over ...' needs a list.`, this.currentLine);
    }

    eval(node, env) {
      const op = node[0];
      if (op === "num") return node[1];
      if (op === "str") return node[1];
      if (op === "bool") return node[1];
      if (op === "var") {
        const v = env.lookup(node[1]);
        if (v !== UNSET) return v;
        if (node[1] in this.functions) return this.functions[node[1]];   // function as a value
        throw unknownVariableError(node[1], env.names(), this.currentLine);
      }
      if (op === "neg") return -this.eval(node[1], env);
      if (op === "list") return node[1].map((e) => this.eval(e, env));
      if (op === "record") {
        const d = {};
        for (const [k, v] of node[1]) d[this.eval(k, env)] = this.eval(v, env);
        return d;
      }
      if (op === "map" || op === "filter") {
        const fn = this.eval(node[1], env), seq = this.eval(node[2], env);
        this.needListFn(fn, seq, op);
        if (op === "map") return seq.map((x) => this.invoke(fn, [x]));
        return seq.filter((x) => truthy(this.invoke(fn, [x])));
      }
      if (op === "reduce") {
        const fn = this.eval(node[1], env), seq = this.eval(node[2], env);
        let acc = this.eval(node[3], env);
        this.needListFn(fn, seq, "reduce");
        for (const x of seq) acc = this.invoke(fn, [acc, x]);
        return acc;
      }
      if (op === "index") {
        const seq = this.eval(node[1], env);
        const rawKey = this.eval(node[2], env);
        if (isDict(seq)) {
          if (!(rawKey in seq)) throw new PlainLangError(`There is no key '${toStr(rawKey)}' in that record.`, this.currentLine,
            didYouMean(toStr(rawKey), Object.keys(seq)) || "Check the spelling of the key.");
          return seq[rawKey];
        }
        if (!Array.isArray(seq)) throw new PlainLangError("'item ... of ...' needs a list or a record.", this.currentLine);
        const i = Math.floor(rawKey);
        if (i < 1 || i > seq.length) throw new PlainLangError(`There is no item ${i} (the list has ${seq.length} item(s)).`, this.currentLine, "Lists start counting at item 1.");
        return seq[i - 1];
      }
      if (op === "binop") return this.binop(node[1], this.eval(node[2], env), this.eval(node[3], env));
      if (op === "cmp") return this.compare(node[1], this.eval(node[2], env), this.eval(node[3], env));
      if (op === "and") return truthy(this.eval(node[1], env)) && truthy(this.eval(node[2], env));
      if (op === "or") return truthy(this.eval(node[1], env)) || truthy(this.eval(node[2], env));
      if (op === "not") return !truthy(this.eval(node[1], env));
      if (op === "builtin") return this.builtin(node[1], node[2].map((a) => this.eval(a, env)));
      if (op === "call") {
        const r = this.callFunction(node[1], node[2], env);
        if (r === null) throw new PlainLangError(`The function '${node[1]}' was used as a value, but it didn't 'return' anything.`, this.currentLine);
        return r;
      }
      throw new PlainLangError("I couldn't make sense of part of your program.", this.currentLine);
    }

    binop(op, a, b) {
      if (op === "+") {
        if (typeof a === "string" || typeof b === "string") {
          const t = toStr(a) + toStr(b);
          if (t.length > MAX_TEXT) throw tooLong(this.currentLine);
          return t;
        }
        if (Array.isArray(a) && Array.isArray(b)) {
          if (a.length + b.length > MAX_LIST) throw tooLongList(this.currentLine);
          return a.concat(b);
        }
        this.needNumbers("plus", a, b); return this.finite(a + b);
      }
      if (op === "-") { this.needNumbers("minus", a, b); return this.finite(a - b); }
      if (op === "*") { this.needNumbers("multiplied by", a, b); return this.finite(a * b); }
      if (op === "/") {
        this.needNumbers("divided by", a, b);
        if (b === 0) throw new PlainLangError("You can't divide by zero.", this.currentLine, "Check the number you're dividing by.");
        return this.finite(a / b);
      }
    }
    finite(x) {
      if (!Number.isFinite(x)) throw tooBig(this.currentLine);
      return x;
    }
    needNumbers(name, a, b) {
      for (const v of [a, b]) this.needNumber(name, v);
    }
    needNumber(name, v) {
      if (typeof v !== "number")
        throw new PlainLangError(`'${name}' only works with numbers, but I got ${typeName(v)}.`, this.currentLine);
    }
    compare(op, a, b) {
      // equality is always well-defined, even across types (it's simply 'no') —
      // only ordering needs same-shaped operands, so only it can raise
      if (op === "==") return deepEqual(a, b);
      if (op === "!=") return !deepEqual(a, b);
      const ca = compareCategory(a), cb = compareCategory(b);
      const orderable = ca === cb && ca !== "record" && ca !== "function" && ca !== "none";
      if (!orderable) throw new PlainLangError(`I can't compare ${typeName(a)} with ${typeName(b)}.`, this.currentLine);
      switch (op) {
        case ">": return a > b;
        case "<": return a < b;
        case ">=": return a >= b;
        case "<=": return a <= b;
      }
    }
    builtin(name, args) {
      if (name === "length") {
        const v = args[0];
        if (Array.isArray(v) || typeof v === "string") return v.length;
        if (isDict(v)) return Object.keys(v).length;
        throw new PlainLangError("'length of' works on text, a list, or a record.", this.currentLine);
      }
      if (name === "keys") {
        if (isDict(args[0])) return Object.keys(args[0]);
        throw new PlainLangError("'keys of' works on a record.", this.currentLine);
      }
      if (name === "uppercase") return toStr(args[0]).toUpperCase();
      if (name === "lowercase") return toStr(args[0]).toLowerCase();
      if (name === "trim") return toStr(args[0]).trim();
      if (name === "split") {
        const text = toStr(args[0]), sep = toStr(args[1]);
        return sep === "" ? text.split("") : text.split(sep);
      }
      if (name === "join") {
        if (!Array.isArray(args[0])) throw new PlainLangError("'join' works on a list.", this.currentLine);
        const parts = args[0].map(toStr), sep = toStr(args[1]);
        let size = sep.length * Math.max(parts.length - 1, 0);      // sized BEFORE building it
        for (const p of parts) size += p.length;
        if (size > MAX_TEXT) throw tooLong(this.currentLine);
        return parts.join(sep);
      }
      if (name === "replace") {
        if (toStr(args[0]) === "") throw new PlainLangError("The text to replace can't be empty.", this.currentLine);
        const text = toStr(args[2]), old = toStr(args[0]), rep = toStr(args[1]);
        const pieces = text.split(old);                                  // pieces.length - 1 hits
        if (text.length + (pieces.length - 1) * (rep.length - old.length) > MAX_TEXT) throw tooLong(this.currentLine);
        return pieces.join(rep);
      }
      if (name === "position") return toStr(args[1]).indexOf(toStr(args[0])) + 1;
      if (name === "contains") {
        if (Array.isArray(args[0])) return args[0].includes(args[1]);
        return toStr(args[0]).includes(toStr(args[1]));
      }
      if (name === "round") { this.needNumber(name, args[0]); return roundHalfAway(args[0]); }
      if (name === "absolute") { this.needNumber(name, args[0]); return Math.abs(args[0]); }
      if (name === "floor") { this.needNumber(name, args[0]); return Math.floor(args[0]); }
      if (name === "ceiling") { this.needNumber(name, args[0]); return Math.ceil(args[0]); }
      if (name === "power") {
        this.needNumber(name, args[0]); this.needNumber(name, args[1]);
        if (args[0] === 0 && args[1] < 0) throw new PlainLangError("You can't raise 0 to a negative power.", this.currentLine);
        if (args[0] < 0 && !Number.isInteger(args[1])) throw new PlainLangError("I can't raise a negative number to a fractional power.", this.currentLine);
        return this.finite(Math.pow(args[0], args[1]));
      }
      if (name === "min") { this.needNumber(name, args[0]); this.needNumber(name, args[1]); return Math.min(args[0], args[1]); }
      if (name === "max") { this.needNumber(name, args[0]); this.needNumber(name, args[1]); return Math.max(args[0], args[1]); }
      if (name === "sqrt") {
        this.needNumber(name, args[0]);
        if (args[0] < 0) throw new PlainLangError("I can't take the square root of a negative number.", this.currentLine);
        return Math.sqrt(args[0]);
      }
      if (name === "random") {
        this.needNumber(name, args[0]); this.needNumber(name, args[1]);
        const lo = Math.floor(args[0]), hi = Math.floor(args[1]);
        const a = Math.min(lo, hi), b = Math.max(lo, hi);
        return a + Math.floor(this.rng() * (b - a + 1));
      }
      // — numbers & lists toolbox —
      if (["sum", "average", "smallest", "largest", "first", "last", "reverse", "sorted"].includes(name)) {
        const v = args[0];
        if (name === "reverse") {
          if (typeof v === "string") return v.split("").reverse().join("");
          this.needList(v, name); return [...v].reverse();
        }
        this.needList(v, name);
        if (name === "sum" || name === "average") {
          for (const x of v) if (typeof x !== "number") throw new PlainLangError(`'${name} of' needs a list of numbers.`, this.currentLine);
          const total = this.finite(v.reduce((a, b) => a + b, 0));
          if (name === "sum") return total;
          if (v.length === 0) throw new PlainLangError("I can't take the average of an empty list.", this.currentLine);
          return total / v.length;
        }
        if (v.length === 0) throw new PlainLangError(`I can't take the ${name} of an empty list.`, this.currentLine);
        if (name === "smallest") return v.reduce((a, b) => (b < a ? b : a));
        if (name === "largest") return v.reduce((a, b) => (b > a ? b : a));
        if (name === "first") return v[0];
        if (name === "last") return v[v.length - 1];
        if (name === "sorted") {
          const allNum = v.every((x) => typeof x === "number");
          const allStr = v.every((x) => typeof x === "string");
          if (!allNum && !allStr) throw new PlainLangError("I can only sort a list of all numbers or all text.", this.currentLine);
          return allNum ? [...v].sort((a, b) => a - b) : [...v].sort();
        }
      }
      if (name === "remainder") {
        this.needNumber(name, args[0]); this.needNumber(name, args[1]);
        const a = Math.trunc(args[0]), b = Math.trunc(args[1]);
        if (b === 0) throw new PlainLangError("You can't take a remainder when dividing by zero.", this.currentLine);
        if (Math.abs(a) <= 9007199254740992 && Math.abs(b) <= 9007199254740992) {
          return a - b * Math.floor(a / b);   // floored remainder, matches Python's %
        }
        const A = BigInt(a), B = BigInt(b);   // beyond 2**53 doubles can't do it exactly; BigInt can
        let m = A % B;
        if (m !== 0n && ((m < 0n) !== (B < 0n))) m += B;
        return Number(m);
      }
    }
    needList(v, name) {
      if (!Array.isArray(v)) throw new PlainLangError(`'${name} of' needs a list.`, this.currentLine);
    }
  }

  // ─── Shared helpers ──────────────────────────────────────────────────────
  function isPlFn(v) { return v != null && typeof v === "object" && v.__plfn === true; }
  function isDict(v) { return v != null && typeof v === "object" && !Array.isArray(v) && !isPlFn(v); }
  function truthy(v) {
    if (typeof v === "boolean") return v;
    if (typeof v === "number") return v !== 0;
    if (typeof v === "string" || Array.isArray(v)) return v.length > 0;
    if (isDict(v)) return Object.keys(v).length > 0;
    return v != null;
  }
  function coerceInput(raw) {
    if (typeof raw !== "string") return raw;
    if (raw.trim() !== "" && !isNaN(Number(raw))) return Number(raw);
    return raw;
  }
  function roundHalfAway(x) {
    // schoolbook rounding (2.5 -> 3, -2.5 -> -3); Math.round rounds ties toward +infinity
    return Math.sign(x) * Math.floor(Math.abs(x) + 0.5);
  }
  const MAX_TEXT = 10000000;
  const MAX_LIST = 10000000;
  function tooLongList(line) { return new PlainLangError("That list is too long for PlainLang to hold.", line); }
  function tooLong(line) { return new PlainLangError("That text is too long for PlainLang to hold.", line); }
  function tooBig(line) { return new PlainLangError("That number is too big for PlainLang to hold.", line); }
  function formatNumber(v) {
    // whole numbers plainly, everything else rounded to 10 places, and never in
    // scientific notation (JS and Python disagree about when to switch to it)
    if (Number.isInteger(v)) return Math.abs(v) <= 9007199254740992 ? String(v) : BigInt(v).toString();
    const r = roundHalfAway(v * 1e10) / 1e10;
    if (Number.isInteger(r)) return String(r);
    const text = String(r);
    return /e/i.test(text) ? r.toFixed(10).replace(/0+$/, "").replace(/\.$/, "") : text;
  }
  function toStr(v) {
    if (typeof v === "boolean") return v ? "true" : "false";
    if (typeof v === "number") return formatNumber(v);
    if (isPlFn(v)) return `function ${v.name}`;
    if (Array.isArray(v)) return "[" + v.map(toStr).join(", ") + "]";
    if (isDict(v)) return "{" + Object.keys(v).map((k) => `${k}: ${toStr(v[k])}`).join(", ") + "}";
    if (v == null) return "nothing";
    return String(v);
  }
  function typeName(v) {
    if (typeof v === "boolean") return "true/false";
    if (typeof v === "number") return "a number";
    if (typeof v === "string") return "some text";
    if (isPlFn(v)) return "a function";
    if (Array.isArray(v)) return "a list";
    if (isDict(v)) return "a record";
    return "nothing";
  }
  function compareCategory(v) {
    // mirrors what Python considers orderable together: numbers (bool included,
    // since Python's bool is an int subtype), text, and lists compare within
    // their own category; records and functions never order (Python raises
    // TypeError on dict > dict / function > function, same as mismatched types).
    if (typeof v === "number" || typeof v === "boolean") return "number";
    if (typeof v === "string") return "text";
    if (Array.isArray(v)) return "list";
    if (isDict(v)) return "record";
    if (isPlFn(v)) return "function";
    return "none";
  }
  function deepEqual(a, b) {
    if (Array.isArray(a) && Array.isArray(b)) {
      return a.length === b.length && a.every((x, i) => deepEqual(x, b[i]));
    }
    if (isDict(a) && isDict(b)) {
      const ka = Object.keys(a), kb = Object.keys(b);
      return ka.length === kb.length && ka.every((k) => k in b && deepEqual(a[k], b[k]));
    }
    return a === b;
  }

  // ─── Compiler: PlainLang → JavaScript ──────────────────────────────────────
  // Walks the same AST the interpreter uses and emits readable, idiomatic
  // JavaScript. The point is pedagogical: a beginner sees their English program
  // become the real code a professional would write.
  class Compiler {
    constructor() { this.lines = []; this.indent = 0; }
    pad() { return "  ".repeat(this.indent); }
    emit(s) { this.lines.push(this.pad() + s); }
    unwrap(n) { return n[0] === "@" ? n[2] : n; }

    compile(tree) {
      // declare top-level variables, then the statements
      this.declareScope(tree);
      this.stmtList(tree);
      const body = this.lines.join("\n");
      return this.prelude(body) + body + "\n";
    }

    prelude(body) {
      const parts = [
        "// Generated from PlainLang — the real JavaScript your program becomes.",
        "const say = (x) => console.log(format(x));",
        "function format(v) {",
        '  if (typeof v === "boolean") return v ? "true" : "false";',
        '  if (typeof v === "number") return Number.isInteger(v) ? String(v) : String(Math.round(v * 1e10) / 1e10);',
        '  if (Array.isArray(v)) return "[" + v.map(format).join(", ") + "]";',
        '  if (v && typeof v === "object") return "{" + Object.keys(v).map((k) => k + ": " + format(v[k])).join(", ") + "}";',
        "  return String(v);",
        "}",
      ];
      if (/\brandomBetween\(/.test(body)) parts.push(
        "function randomBetween(a, b) {",
        "  a = Math.floor(a); b = Math.floor(b);",
        "  const lo = Math.min(a, b), hi = Math.max(a, b);",
        "  return lo + Math.floor(Math.random() * (hi - lo + 1));",
        "}");
      if (/\bask\(/.test(body)) parts.push("const ask = (q) => prompt(q);");
      // 'item ... of ...' and 'length of' work on both lists and records, so a
      // small runtime helper picks the right behaviour (lists are 1-indexed).
      if (/\bitemOf\(/.test(body)) parts.push(
        "const itemOf = (c, k) => Array.isArray(c) ? c[k - 1] : c[k];");
      if (/\bsetItemOf\(/.test(body)) parts.push(
        "function setItemOf(c, k, v) { if (Array.isArray(c)) c[k - 1] = v; else c[k] = v; }");
      if (/\bsizeOf\(/.test(body)) parts.push(
        "const sizeOf = (x) => Array.isArray(x) || typeof x === \"string\" ? x.length : Object.keys(x).length;");
      if (/\bcontainsOf\(/.test(body)) parts.push(
        "const containsOf = (c, p) => Array.isArray(c) ? c.includes(p) : String(c).includes(String(p));");
      if (/\bturtle\./.test(body)) parts.push(
        "// 'turtle' would be your drawing library (move the pen across a canvas).");
      return parts.join("\n") + "\n\n";
    }

    declareScope(block) {
      const names = new Set();
      const walk = (stmts) => {
        for (let s of stmts) {
          s = this.unwrap(s);
          const op = s[0];
          if (op === "set" || op === "ask") names.add(s[1]);
          else if (op === "if") { for (const [, b] of s[1]) walk(b[1]); if (s[2]) walk(s[2][1]); }
          else if (op === "match") { for (const [, b] of s[2]) walk(b[1]); if (s[3]) walk(s[3][1]); }
          else if (op === "repeat") walk(s[2][1]);
          else if (op === "while") walk(s[2][1]);
          else if (op === "count") walk(s[4][1]);
          else if (op === "foreach") walk(s[3][1]);
          // 'define' bodies get their own scope — don't descend
        }
      };
      walk(block[1]);
      if (names.size) this.emit("let " + [...names].join(", ") + ";");
    }

    stmtList(block) { for (const s of block[1]) this.stmt(s); }

    openBlock(header, body) {
      this.emit(header + " {");
      this.indent++; this.stmtList(body); this.indent--;
      this.emit("}");
    }

    stmt(node) {
      node = this.unwrap(node);
      const op = node[0];
      switch (op) {
        case "set":  this.emit(`${node[1]} = ${this.expr(node[2])};`); break;
        case "say":  this.emit(`say(${this.expr(node[1])});`); break;
        case "ask":  this.emit(`${node[2]} = ask(${this.expr(node[1])});`); break;
        case "return": this.emit(`return ${this.expr(node[1])};`); break;
        case "repeat": this.openBlock(`for (let i = 0; i < ${this.expr(node[1])}; i++)`, node[2]); break;
        case "while":  this.openBlock(`while (${this.expr(node[1])})`, node[2]); break;
        case "count":  this.openBlock(
          `for (let ${node[1]} = ${this.expr(node[2])}; ${node[1]} <= ${this.expr(node[3])}; ${node[1]}++)`, node[4]); break;
        case "foreach": this.openBlock(`for (const ${node[1]} of ${this.expr(node[2])})`, node[3]); break;
        case "define": {
          this.emit(`function ${node[1]}(${node[2].join(", ")}) {`);
          this.indent++; this.declareScope(node[3]); this.stmtList(node[3]); this.indent--;
          this.emit("}");
          break;
        }
        case "call": this.emit(`${node[1]}(${node[2].map((a) => this.expr(a)).join(", ")});`); break;
        case "add":  this.emit(`${node[2]}.push(${this.expr(node[1])});`); break;
        case "remove": this.emit(`${node[2]}.splice(${this.expr(node[1])} - 1, 1);`); break;
        case "setindex": this.emit(`setItemOf(${this.expr(node[1])}, ${this.expr(node[2])}, ${this.expr(node[3])});`); break;
        case "move": this.emit(`turtle.${node[1] === "forward" ? "forward" : "back"}(${this.expr(node[2])});`); break;
        case "turn": this.emit(`turtle.${node[1]}(${this.expr(node[2])});`); break;
        case "pen":  this.emit(`turtle.${node[1] === "down" ? "penDown" : "penUp"}();`); break;
        case "pencolor": this.emit(`turtle.color(${this.expr(node[1])});`); break;
        case "wait": this.emit(`// wait`); break;
        case "break": this.emit(`break;`); break;
        case "continue": this.emit(`continue;`); break;
        case "if": {
          const [branches, elseBlock] = [node[1], node[2]];
          branches.forEach(([cond, body], idx) => {
            const kw = idx === 0 ? "if" : "} else if";
            if (idx === 0) this.emit(`if (${this.expr(cond)}) {`);
            else this.emit(`} else if (${this.expr(cond)}) {`);
            this.indent++; this.stmtList(body); this.indent--;
          });
          if (elseBlock) { this.emit("} else {"); this.indent++; this.stmtList(elseBlock); this.indent--; }
          this.emit("}");
          break;
        }
        case "match": {
          const [subject, cases, elseBlock] = [node[1], node[2], node[3]];
          this.emit(`switch (${this.expr(subject)}) {`);
          this.indent++;
          for (const [value, body] of cases) {
            this.emit(`case ${this.expr(value)}: {`);
            this.indent++; this.stmtList(body); this.emit("break;"); this.indent--;
            this.emit("}");
          }
          if (elseBlock) { this.emit("default: {"); this.indent++; this.stmtList(elseBlock); this.indent--; this.emit("}"); }
          this.indent--;
          this.emit("}");
          break;
        }
      }
    }

    expr(node) {
      const op = node[0];
      if (op === "num") return String(node[1]);
      if (op === "str") return JSON.stringify(node[1]);
      if (op === "bool") return String(node[1]);
      if (op === "var") return node[1];
      if (op === "neg") return `(-${this.expr(node[1])})`;
      if (op === "list") return "[" + node[1].map((e) => this.expr(e)).join(", ") + "]";
      if (op === "record") return "{ " + node[1].map(([k, v]) => `[${this.expr(k)}]: ${this.expr(v)}`).join(", ") + " }";
      if (op === "map") return `${this.expr(node[2])}.map(${this.expr(node[1])})`;
      if (op === "filter") return `${this.expr(node[2])}.filter(${this.expr(node[1])})`;
      if (op === "reduce") return `${this.expr(node[2])}.reduce(${this.expr(node[1])}, ${this.expr(node[3])})`;
      if (op === "index") return `itemOf(${this.expr(node[1])}, ${this.expr(node[2])})`;
      if (op === "binop") return `(${this.expr(node[2])} ${node[1]} ${this.expr(node[3])})`;
      if (op === "cmp") {
        const js = { "==": "===", "!=": "!==", ">": ">", "<": "<", ">=": ">=", "<=": "<=" }[node[1]];
        return `(${this.expr(node[2])} ${js} ${this.expr(node[3])})`;
      }
      if (op === "and") return `(${this.expr(node[1])} && ${this.expr(node[2])})`;
      if (op === "or")  return `(${this.expr(node[1])} || ${this.expr(node[2])})`;
      if (op === "not") return `(!${this.expr(node[1])})`;
      if (op === "call") return `${node[1]}(${node[2].map((a) => this.expr(a)).join(", ")})`;
      if (op === "builtin") {
        const a = node[2].map((x) => this.expr(x));
        switch (node[1]) {
          case "length":    return `sizeOf(${a[0]})`;
          case "keys":      return `Object.keys(${a[0]})`;
          case "uppercase": return `String(${a[0]}).toUpperCase()`;
          case "lowercase": return `String(${a[0]}).toLowerCase()`;
          case "trim":      return `String(${a[0]}).trim()`;
          case "split":     return `String(${a[0]}).split(${a[1]})`;
          case "join":      return `${a[0]}.map(format).join(${a[1]})`;
          case "replace":   return `String(${a[2]}).split(${a[0]}).join(${a[1]})`;
          case "position":  return `(String(${a[1]}).indexOf(${a[0]}) + 1)`;
          case "contains":  return `containsOf(${a[0]}, ${a[1]})`;
          case "round":     return `Math.round(${a[0]})`;
          case "absolute":  return `Math.abs(${a[0]})`;
          case "sqrt":      return `Math.sqrt(${a[0]})`;
          case "random":    return `randomBetween(${a[0]}, ${a[1]})`;
          case "sum":       return `${a[0]}.reduce((x, y) => x + y, 0)`;
          case "average":   return `(${a[0]}.reduce((x, y) => x + y, 0) / ${a[0]}.length)`;
          case "smallest":  return `${a[0]}.reduce((x, y) => (y < x ? y : x))`;
          case "largest":   return `${a[0]}.reduce((x, y) => (y > x ? y : x))`;
          case "first":     return `${a[0]}[0]`;
          case "last":      return `${a[0]}[${a[0]}.length - 1]`;
          case "reverse":   return `[...${a[0]}].reverse()`;
          case "sorted":    return `[...${a[0]}].sort((x, y) => x - y)`;
          case "remainder": return `(${a[0]} % ${a[1]})`;
          case "floor":     return `Math.floor(${a[0]})`;
          case "ceiling":   return `Math.ceil(${a[0]})`;
          case "power":     return `Math.pow(${a[0]}, ${a[1]})`;
          case "min":       return `Math.min(${a[0]}, ${a[1]})`;
          case "max":       return `Math.max(${a[0]}, ${a[1]})`;
        }
      }
      return "/* ? */";
    }
  }

  function compile(source) {
    const tokens = tokenize(source);
    const tree = new Parser(tokens).parse();
    return new Compiler().compile(tree);
  }

  // ─── Public entry point ──────────────────────────────────────────────────
  function run(source, options) {
    const interp = new Interpreter(options);
    try {
      const tokens = tokenize(source);
      const tree = new Parser(tokens).parse();
      interp.run(tree);
      interp.snapshot(null); // final frame: end-state variables, full output & drawing
      return { ok: true, error: null, output: interp.output, trace: interp.trace, turtle: interp.segments };
    } catch (e) {
      if (e instanceof PlainLangError) {
        return { ok: false, error: formatError(source, e), errorLine: e.line, output: interp.output, trace: interp.trace, turtle: interp.segments };
      }
      if (e && e[RETURN]) {
        return { ok: true, error: null, output: interp.output, trace: interp.trace, turtle: interp.segments };
      }
      if (e && (e[BREAK] || e[CONTINUE])) {
        const word = e[BREAK] ? "stop" : "skip";
        const err = new PlainLangError(`'${word}' can only be used inside a loop.`);
        return { ok: false, error: formatError(source, err), output: interp.output, trace: interp.trace, turtle: interp.segments };
      }
      return { ok: false, error: "Unexpected problem: " + (e && e.message), output: interp.output, trace: interp.trace, turtle: interp.segments };
    }
  }

  const PlainLang = { run, compile, tokenize, Parser, Interpreter, toStr, PlainLangError,
                      suggest, formatError };
  if (typeof module !== "undefined" && module.exports) module.exports = PlainLang;
  global.PlainLang = PlainLang;
})(typeof window !== "undefined" ? window : globalThis);
