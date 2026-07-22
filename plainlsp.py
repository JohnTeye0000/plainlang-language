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
        doc = _HOVER_DOCS.get(word)
        if not doc:
            return None
        return {"contents": {"kind": "plaintext", "value": doc}}

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
