# PlainLang for VS Code

Syntax highlighting and live diagnostics for `.plang` files, backed by the same
static analyzer (`plaincheck.py`) as the command-line tools, via `plainlsp.py`.

## What you get

- Syntax highlighting for keywords, strings (with `{interpolation}`), numbers, and comments
- Live diagnostics as you type: undefined variables, wrong argument counts, type errors,
  unreachable code, and syntax errors — with "did you mean?" suggestions
- Hover documentation for keywords like `define`, `if`, `count`, `match`, `reduce`

## Requirements

- Python 3, with this repo's `plainlang.py` / `plaincheck.py` / `plainlsp.py` available
  (the extension runs `python plainlsp.py` as a subprocess)

## Installing (from source, not yet published to the marketplace)

```bash
cd vscode-extension
npm install
npx vsce package
code --install-extension plainlang-0.1.0.vsix
```

## Settings

| Setting | Default | Description |
|---|---|---|
| `plainlang.pythonPath` | `"python"` | Command used to run Python |
| `plainlang.serverPath` | *(bundled `plainlsp.py`)* | Override to point at a different copy of `plainlsp.py` |

## How it's wired

`src/extension.js` is a thin client: it starts `python plainlsp.py` as a subprocess and
speaks LSP to it over stdio using `vscode-languageclient`. All the actual language logic —
tokenizing, parsing, type inference, diagnostics — lives in the Python engine
(`plaincheck.py`), so the extension itself has no PlainLang-specific logic beyond syntax
highlighting (`syntaxes/plainlang.tmLanguage.json`).
