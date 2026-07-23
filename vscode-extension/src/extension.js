// The VS Code side of the PlainLang language server: spawns `python plainlsp.py`
// as a subprocess and speaks LSP to it over stdio (see plainlsp.py in the repo
// root -- this file just wires an editor to it, it has no language logic itself).

const path = require("path");
const vscode = require("vscode");
const { LanguageClient, TransportKind } = require("vscode-languageclient/node");

let client;

function resolveServerPath(context) {
  const config = vscode.workspace.getConfiguration("plainlang");
  const configured = config.get("serverPath");
  if (configured) return configured;
  // fall back to the plainlsp.py that ships next to this extension in the repo
  return path.join(context.extensionPath, "..", "plainlsp.py");
}

function activate(context) {
  const config = vscode.workspace.getConfiguration("plainlang");
  const pythonPath = config.get("pythonPath") || "python";
  const serverPath = resolveServerPath(context);

  const serverOptions = {
    command: pythonPath,
    args: [serverPath],
    transport: TransportKind.stdio,
  };

  const clientOptions = {
    documentSelector: [{ scheme: "file", language: "plainlang" }],
  };

  client = new LanguageClient(
    "plainlang",
    "PlainLang Language Server",
    serverOptions,
    clientOptions
  );

  context.subscriptions.push(client.start());
}

function deactivate() {
  if (!client) return undefined;
  return client.stop();
}

module.exports = { activate, deactivate };
