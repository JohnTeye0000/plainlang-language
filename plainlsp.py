"""
plainlsp — a minimal Language Server Protocol server for PlainLang.

Gives editors live diagnostics (the same ones plaincheck.py reports on the
command line) as you type: undefined variables, wrong argument counts, type
errors, unreachable code, and syntax errors -- all with "did you mean?"
suggestions where available.

The transport (stdio, LSP framing) is a thin shell around LSPServer, which is
pure request-in/messages-out and has no I/O of its own -- that's what makes it
testable without spawning a subprocess or a real editor.

Run as a server (an editor extension would launch this):
    python plainlsp.py

Speaks LSP over stdio: Content-Length-framed JSON-RPC, same as any other
language server (pyright, gopls, ...). See test_lsp.py for a scripted client.
"""

import json
import sys

import plaincheck as pc
import plainlang as pl

SEVERITY_ERROR = 1
SEVERITY_WARNING = 2


def _position(source, d):
    """0-based (line, col, length) for a diagnostic, resolving 'near' the same
    way plaincheck's own text renderer does when an exact column isn't known."""
    if not d.line:
        return 0, 0, 1
    lines = source.split("\n")
    line0 = d.line - 1
    src = lines[line0] if 0 <= line0 < len(lines) else ""
    col, length = d.col, d.length
    if col is None and d.near and src:
        idx = src.find(d.near)
        if idx >= 0:
            col, length = idx + 1, len(d.near)
    col = col or 1
    return line0, col - 1, length or 1


def diagnostics_for(source):
    """PlainLang source -> a list of LSP Diagnostic objects."""
    diags, _ = pc.check_source(source)
    out = []
    for d in diags:
        line0, col0, length = _position(source, d)
        message = d.message + (f"  ({d.hint})" if getattr(d, "hint", None) else "")
        severity = SEVERITY_ERROR if getattr(d, "severity", "error") == "error" else SEVERITY_WARNING
        out.append({
            "range": {
                "start": {"line": line0, "character": col0},
                "end": {"line": line0, "character": col0 + length},
            },
            "severity": severity,
            "source": "plainlang",
            "message": message,
        })
    return out


SYMBOL_FUNCTION = 12
SYMBOL_VARIABLE = 13
COMPLETION_FUNCTION = 3
COMPLETION_VARIABLE = 6
COMPLETION_KEYWORD = 14


def index_document(source):
    """Token-based symbol index: {'functions': {name: {...}}, 'variables': {name: {...}}}.
    Token-based (not tree-based) so it still works while the file has syntax errors."""
    try:
        toks = pl.tokenize(source)
    except pl.PlainLangError:
        return {"functions": {}, "variables": {}}
    functions, variables = {}, {}

    def record(table, tok, **extra):
        name = tok[1]
        if name not in table:
            table[name] = {"line": tok[2] - 1, "col": tok[3] - 1, "length": tok[4], **extra}

    n = len(toks)
    for i, t in enumerate(toks):
        nxt = toks[i + 1] if i + 1 < n else None
        if t[0] != "KW" or nxt is None:
            continue
        kw = t[1]
        if kw == "define" and nxt[0] == "IDENT":
            params, j = [], i + 2
            if j < n and toks[j][0] == "KW" and toks[j][1] == "with":
                j += 1
                while j < n and toks[j][2] == t[2]:
                    if toks[j][0] == "IDENT":
                        params.append(toks[j][1])
                    j += 1
            record(functions, nxt, params=params)
        elif kw == "set" and nxt[0] == "IDENT":
            record(variables, nxt)
        elif kw == "count" and nxt[0] == "IDENT":
            record(variables, nxt)
        elif kw == "each" and nxt[0] == "IDENT":
            record(variables, nxt)
        elif kw == "into" and nxt[0] == "IDENT":
            record(variables, nxt)
    return {"functions": functions, "variables": variables}


def _range(sym):
    return {"start": {"line": sym["line"], "character": sym["col"]},
            "end": {"line": sym["line"], "character": sym["col"] + sym["length"]}}


def document_symbols(source):
    idx = index_document(source)
    out = []
    for name, s in idx["functions"].items():
        detail = "with " + " and ".join(s["params"]) if s["params"] else ""
        out.append({"name": name, "kind": SYMBOL_FUNCTION, "detail": detail,
                    "range": _range(s), "selectionRange": _range(s)})
    for name, s in idx["variables"].items():
        out.append({"name": name, "kind": SYMBOL_VARIABLE,
                    "range": _range(s), "selectionRange": _range(s)})
    out.sort(key=lambda o: (o["range"]["start"]["line"], o["range"]["start"]["character"]))
    return out


def completions_for(source):
    idx = index_document(source)
    items = []
    for name, s in idx["functions"].items():
        sig = "with " + " and ".join(s["params"]) if s["params"] else "no parameters"
        items.append({"label": name, "kind": COMPLETION_FUNCTION, "detail": f"function ({sig})"})
    for name in idx["variables"]:
        items.append({"label": name, "kind": COMPLETION_VARIABLE, "detail": "variable"})
    defined = {i["label"] for i in items}
    for kw in sorted(pl.KEYWORDS):
        if kw not in defined:
            items.append({"label": kw, "kind": COMPLETION_KEYWORD, "detail": "keyword"})
    return items


class LSPServer:
    """Pure message handling: feed it a request/notification dict, get back the
    list of response/notification dicts to send. No stdio, no sockets."""

    def __init__(self):
        self.docs = {}          # uri -> text
        self.shutdown_requested = False

    def handle(self, msg):
        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params") or {}

        if method == "initialize":
            return [self._response(msg_id, {
                "capabilities": {
                    "textDocumentSync": 1,   # 1 = full-document sync
                    "hoverProvider": True,
                    "definitionProvider": True,
                    "documentSymbolProvider": True,
                    "completionProvider": {"triggerCharacters": []},
                },
                "serverInfo": {"name": "plainlsp", "version": "0.1"},
            })]

        if method == "initialized":
            return []

        if method in ("textDocument/didOpen", "textDocument/didChange"):
            doc = params.get("textDocument", {})
            uri = doc.get("uri")
            if method == "textDocument/didOpen":
                text = doc.get("text", "")
            else:
                changes = params.get("contentChanges", [])
                text = changes[-1]["text"] if changes else self.docs.get(uri, "")
            self.docs[uri] = text
            return [self._publish_diagnostics(uri, text)]

        if method == "textDocument/didClose":
            uri = params.get("textDocument", {}).get("uri")
            self.docs.pop(uri, None)
            return [self._notification("textDocument/publishDiagnostics",
                                        {"uri": uri, "diagnostics": []})]

        if method == "textDocument/hover":
            uri = params.get("textDocument", {}).get("uri")
            pos = params.get("position", {})
            text = self.docs.get(uri, "")
            hover = self._hover_at(text, pos.get("line", 0), pos.get("character", 0))
            return [self._response(msg_id, hover)]

        if method == "textDocument/definition":
            uri = params.get("textDocument", {}).get("uri")
            pos = params.get("position", {})
            return [self._response(msg_id, self._definition_at(
                uri, self.docs.get(uri, ""), pos.get("line", 0), pos.get("character", 0)))]

        if method == "textDocument/documentSymbol":
            uri = params.get("textDocument", {}).get("uri")
            return [self._response(msg_id, document_symbols(self.docs.get(uri, "")))]

        if method == "textDocument/completion":
            uri = params.get("textDocument", {}).get("uri")
            return [self._response(msg_id, completions_for(self.docs.get(uri, "")))]

        if method == "shutdown":
            self.shutdown_requested = True
            return [self._response(msg_id, None)]

        if method == "exit":
            return ["__exit__"]

        if msg_id is not None:   # an unhandled request still needs a reply
            return [self._response(msg_id, None)]
        return []

    def _publish_diagnostics(self, uri, text):
        return self._notification("textDocument/publishDiagnostics",
                                   {"uri": uri, "diagnostics": diagnostics_for(text)})

    def _hover_at(self, text, line, char):
        lines = text.split("\n")
        if not (0 <= line < len(lines)):
            return None
        word = _word_at(lines[line], char)
        idx = index_document(text)
        if word in idx["functions"]:
            params = idx["functions"][word]["params"]
            sig = f"define {word}" + (" with " + " and ".join(params) if params else "")
            return {"contents": {"kind": "plaintext", "value": sig}}
        if word in idx["variables"]:
            return {"contents": {"kind": "plaintext", "value": f"variable {word}"}}
        doc = _HOVER_DOCS.get(word)
        if not doc:
            return None
        return {"contents": {"kind": "plaintext", "value": doc}}

    def _definition_at(self, uri, text, line, char):
        lines = text.split("\n")
        if not (0 <= line < len(lines)):
            return None
        word = _word_at(lines[line], char)
        idx = index_document(text)
        sym = idx["functions"].get(word) or idx["variables"].get(word)
        if not sym:
            return None
        return {"uri": uri, "range": _range(sym)}

    @staticmethod
    def _response(msg_id, result):
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _notification(method, params):
        return {"jsonrpc": "2.0", "method": method, "params": params}


def _word_at(line, char):
    if not (0 <= char <= len(line)):
        return ""
    start = char
    while start > 0 and (line[start - 1].isalnum() or line[start - 1] == "_"):
        start -= 1
    end = char
    while end < len(line) and (line[end].isalnum() or line[end] == "_"):
        end += 1
    return line[start:end]


_HOVER_DOCS = {
    "floor": "floor of X -- rounds down to a whole number.",
    "ceiling": "ceiling of X -- rounds up to a whole number.",
    "power": "power of X and Y -- X raised to the power Y.",
    "min": "min of X and Y -- the smaller of two numbers.",
    "max": "max of X and Y -- the larger of two numbers.",
    "remainder": "remainder of X and Y -- what's left after dividing X by Y.",
    "sum": "sum of LIST -- adds up a list of numbers.",
    "average": "average of LIST -- the mean of a list of numbers.",
    "sorted": "sorted of LIST -- a new list in ascending order.",
    "split": "split TEXT by SEP -- breaks text into a list of pieces.",
    "join": "join LIST by SEP -- glues a list into one piece of text.",
    "length": "length of X -- how many characters, items, or fields.",
    "define": "define NAME with PARAM and PARAM ... end -- declares a function.",
    "if": "if CONDITION then ... otherwise ... end -- a decision.",
    "count": "count VAR from START to STOP ... end -- a counting loop.",
    "while": "while CONDITION ... end -- repeats as long as the condition holds.",
    "repeat": "repeat N times ... end -- runs the body N times.",
    "match": "match SUBJECT \\n when VALUE then ... otherwise ... end -- pattern matching.",
    "import": 'import "file.plang" -- pulls in another file\'s function definitions.',
    "reduce": "reduce FN over LIST from START -- folds a list down to one value.",
    "map": "map FN over LIST -- applies FN to every item, returning a new list.",
    "filter": "filter FN over LIST -- keeps only items where FN returns true.",
}


# ─── stdio transport ───────────────────────────────────────────────────────

def _read_message(stream):
    length = None
    while True:
        line = stream.readline()
        if not line:
            return None                 # EOF
        line = line.rstrip(b"\r\n")
        if line == b"":
            break
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip())
    if length is None:
        return None
    body = stream.read(length)
    return json.loads(body.decode("utf-8"))


def _write_message(stream, msg):
    body = json.dumps(msg).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8"))
    stream.write(body)
    stream.flush()


def serve(stdin=None, stdout=None):
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    server = LSPServer()
    while True:
        msg = _read_message(stdin)
        if msg is None:
            return
        for out in server.handle(msg):
            if out == "__exit__":
                return
            _write_message(stdout, out)


if __name__ == "__main__":
    serve()
