"""
Tests for plainlsp.py, the Language Server Protocol server.

Most of the suite drives LSPServer.handle() directly -- pure request-in,
messages-out, no stdio -- so it's fast and deterministic. One test spawns the
real stdio server as a subprocess and speaks actual LSP framing to it, proving
the transport an editor would actually use also works.

Run with:   python test_lsp.py
"""

import json
import subprocess
import sys

import plainlsp as lsp

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


# ── diagnostics_for: the core, pure conversion ─────────────────────────────
print("diagnostics_for")

check("clean program has no diagnostics", lsp.diagnostics_for('say "hi"') == [])

d = lsp.diagnostics_for("say mystery")
check("undefined variable is reported", len(d) == 1, d)
check("severity is Error (1)", d[0]["severity"] == 1, d)
check("position is 0-based and covers the name",
      d[0]["range"] == {"start": {"line": 0, "character": 4}, "end": {"line": 0, "character": 11}}, d)
check("hint is folded into the message", "Set it first" in d[0]["message"], d)

d = lsp.diagnostics_for('define f with n\nreturn n\nend\nsay f with 1 and 2')
check("wrong argument count is on the right line", d[0]["range"]["start"]["line"] == 3, d)

d = lsp.diagnostics_for('say boom (')  # a genuine syntax error
check("syntax errors are also reported", len(d) >= 1 and d[0]["severity"] == 1, d)

d = lsp.diagnostics_for('define f with n\nreturn 1\nsay "after return"\nend\nsay f with 1')
check("unreachable code is a Warning (2)", any(x["severity"] == 2 for x in d), d)


# ── LSPServer: the message protocol ────────────────────────────────────────
print("LSPServer message handling")

s = lsp.LSPServer()
resp = s.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
check("initialize returns capabilities", resp[0]["result"]["capabilities"]["textDocumentSync"] == 1, resp)
check("initialize echoes the request id", resp[0]["id"] == 1, resp)

resp = s.handle({"jsonrpc": "2.0", "method": "initialized", "params": {}})
check("initialized needs no response", resp == [], resp)

resp = s.handle({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
    "textDocument": {"uri": "file:///a.plang", "text": "say mystery"}}})
check("didOpen publishes diagnostics for the open file",
      resp[0]["method"] == "textDocument/publishDiagnostics" and
      resp[0]["params"]["uri"] == "file:///a.plang" and
      len(resp[0]["params"]["diagnostics"]) == 1, resp)

resp = s.handle({"jsonrpc": "2.0", "method": "textDocument/didChange", "params": {
    "textDocument": {"uri": "file:///a.plang"},
    "contentChanges": [{"text": 'say "fixed now"'}]}})
check("didChange re-analyzes the new text (fixed -> no diagnostics)",
      resp[0]["params"]["diagnostics"] == [], resp)
check("the server remembers the updated text",
      s.docs["file:///a.plang"] == 'say "fixed now"', s.docs)

resp = s.handle({"jsonrpc": "2.0", "method": "textDocument/didClose",
                  "params": {"textDocument": {"uri": "file:///a.plang"}}})
check("didClose clears diagnostics for the file", resp[0]["params"]["diagnostics"] == [], resp)
check("didClose forgets the document", "file:///a.plang" not in s.docs)

s.handle({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
    "textDocument": {"uri": "file:///b.plang", "text": "define f with n\nreturn n\nend"}}})
resp = s.handle({"jsonrpc": "2.0", "id": 5, "method": "textDocument/hover", "params": {
    "textDocument": {"uri": "file:///b.plang"}, "position": {"line": 0, "character": 2}}})
check("hover on a known keyword returns docs",
      "declares a function" in resp[0]["result"]["contents"]["value"], resp)

resp = s.handle({"jsonrpc": "2.0", "id": 6, "method": "textDocument/hover", "params": {
    "textDocument": {"uri": "file:///b.plang"}, "position": {"line": 1, "character": 0}}})
check("hover on an ordinary identifier returns nothing", resp[0]["result"] is None, resp)

resp = s.handle({"jsonrpc": "2.0", "id": 7, "method": "shutdown", "params": {}})
check("shutdown acknowledges with a null result", resp[0]["result"] is None, resp)
check("shutdown sets the flag", s.shutdown_requested is True)

resp = s.handle({"jsonrpc": "2.0", "method": "exit"})
check("exit signals the transport to stop", resp == ["__exit__"], resp)

resp = s.handle({"jsonrpc": "2.0", "id": 9, "method": "totally/unknown", "params": {}})
check("an unknown request still gets a reply (never hangs the client)",
      resp == [{"jsonrpc": "2.0", "id": 9, "result": None}], resp)



# ── navigation: symbols, definition, completion, richer hover ──────────────
print("navigation")

NAV = 'define double with n
    return n multiplied by 2
end
set total to 0
count i from 1 to 3
    set total to total plus double with i
end
'
syms = lsp.document_symbols(NAV)
check("document symbols list functions and variables",
      [(s["name"], s["kind"]) for s in syms] == [("double", 12), ("total", 13), ("i", 13)], syms)
check("function symbol carries its signature", syms[0]["detail"] == "with n", syms[0])

idx = lsp.index_document("define f with a and b
return a
end")
check("index captures parameters", idx["functions"]["f"]["params"] == ["a", "b"], idx)
check("index survives a syntax error elsewhere",
      "f" in lsp.index_document("define f with a
return a
end
say (")["functions"])

s = lsp.LSPServer()
s.handle({"jsonrpc": "2.0", "method": "textDocument/didOpen",
          "params": {"textDocument": {"uri": "u", "text": NAV}}})
r = s.handle({"jsonrpc": "2.0", "id": 1, "method": "textDocument/definition", "params": {
    "textDocument": {"uri": "u"}, "position": {"line": 5, "character": 30}}})
check("go-to-definition on a function call jumps to its define",
      r[0]["result"]["range"]["start"] == {"line": 0, "character": 7}, r)
r = s.handle({"jsonrpc": "2.0", "id": 2, "method": "textDocument/definition", "params": {
    "textDocument": {"uri": "u"}, "position": {"line": 5, "character": 12}}})
check("go-to-definition on a variable jumps to its first assignment",
      r[0]["result"]["range"]["start"]["line"] == 3, r)
r = s.handle({"jsonrpc": "2.0", "id": 3, "method": "textDocument/definition", "params": {
    "textDocument": {"uri": "u"}, "position": {"line": 1, "character": 5}}})
check("go-to-definition on a keyword returns nothing", r[0]["result"] is None, r)
r = s.handle({"jsonrpc": "2.0", "id": 4, "method": "textDocument/hover", "params": {
    "textDocument": {"uri": "u"}, "position": {"line": 5, "character": 30}}})
check("hover on a user function shows its signature",
      r[0]["result"]["contents"]["value"] == "define double with n", r)
r = s.handle({"jsonrpc": "2.0", "id": 5, "method": "textDocument/completion",
              "params": {"textDocument": {"uri": "u"}, "position": {"line": 0, "character": 0}}})
labels = {i["label"] for i in r[0]["result"]}
check("completion offers user symbols and keywords",
      {"double", "total", "define", "reduce", "floor"} <= labels, sorted(labels)[:5])
r = s.handle({"jsonrpc": "2.0", "id": 6, "method": "textDocument/documentSymbol",
              "params": {"textDocument": {"uri": "u"}}})
check("documentSymbol request works over the protocol", len(r[0]["result"]) == 3, r)
caps = lsp.LSPServer().handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})[0]["result"]["capabilities"]
check("capabilities advertise the new features",
      caps["definitionProvider"] and caps["documentSymbolProvider"] and "completionProvider" in caps, caps)

# ── real stdio transport, spoken by a real subprocess ──────────────────────
print("stdio transport (subprocess)")


def _frame(msg):
    body = json.dumps(msg).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8") + body


def _read(stream):
    length = None
    while True:
        line = stream.readline()
        if not line:
            return None
        line = line.rstrip(b"\r\n")
        if line == b"":
            break
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip())
    return json.loads(stream.read(length).decode("utf-8"))


proc = subprocess.Popen([sys.executable, "plainlsp.py"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
try:
    proc.stdin.write(_frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
    proc.stdin.flush()
    init = _read(proc.stdout)
    check("subprocess responds to initialize", init is not None and init["id"] == 1, init)

    proc.stdin.write(_frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
        "textDocument": {"uri": "file:///t.plang", "text": "say mystery"}}}))
    proc.stdin.flush()
    diag = _read(proc.stdout)
    check("subprocess publishes real diagnostics over stdio",
          len(diag["params"]["diagnostics"]) == 1, diag)

    proc.stdin.write(_frame({"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}}))
    proc.stdin.flush()
    _read(proc.stdout)
    proc.stdin.write(_frame({"jsonrpc": "2.0", "method": "exit"}))
    proc.stdin.flush()
    proc.wait(timeout=5)
    check("subprocess exits cleanly after 'exit'", proc.returncode == 0, proc.returncode)
finally:
    if proc.poll() is None:
        proc.kill()


print(f"\n{PASS} passed, {FAIL} failed")
if FAIL:
    raise SystemExit(1)
