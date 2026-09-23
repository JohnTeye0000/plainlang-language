/*
 * Host for PlainLang's WebAssembly backend (plainwasm.py).
 *
 * A compiled PlainLang module imports a handful of host functions (print text,
 * print a number, end a line, fail with a message, pow) -- this file supplies
 * them and runs the module. Two modes:
 *
 *   node wasm_runner.js program.wasm        run one module, print its output
 *   echo '["<base64>", ...]' | node wasm_runner.js
 *                                            run a batch, print JSON results
 */
const fs = require("fs");

function roundHalfAway(x) {
  return Math.sign(x) * Math.floor(Math.abs(x) + 0.5);
}

function toStr(v) {
  // the same number formatting every PlainLang engine uses
  if (Number.isInteger(v)) return Math.abs(v) < 1e21 ? String(v) : BigInt(v).toString();
  const r = roundHalfAway(v * 1e10) / 1e10;
  if (Number.isInteger(r)) return String(r);
  const text = String(r);
  return /e/i.test(text) ? r.toFixed(10).replace(/0+$/, "").replace(/\.$/, "") : text;
}

function runModule(bytes) {
  const out = [];
  let line = "";
  let memory;
  const decoder = new TextDecoder();
  const text = (ptr, len) => decoder.decode(new Uint8Array(memory.buffer, ptr, len));
  const imports = {
    env: {
      print_str: (ptr, len) => { line += text(ptr, len); },
      print_num: (v) => { line += toStr(v); },
      print_bool: (v) => { line += v ? "true" : "false"; },
      end_line: () => { out.push(line); line = ""; },
      fail: (ptr, len) => { throw new Error(text(ptr, len)); },
      pow: Math.pow,
    },
  };
  let instance;
  try {
    instance = new WebAssembly.Instance(new WebAssembly.Module(bytes), imports);
  } catch (e) {
    return { out, error: "invalid module: " + e.message };
  }
  memory = instance.exports.memory;
  try {
    instance.exports.run();
    return { out, error: null };
  } catch (e) {
    return { out, error: e.message };
  }
}

if (require.main === module) {
  const arg = process.argv[2];
  if (arg) {
    const result = runModule(fs.readFileSync(arg));
    for (const l of result.out) console.log(l);
    if (result.error) { console.log("\n  Oops! Something went wrong:\n    " + result.error); process.exit(1); }
  } else {
    const modules = JSON.parse(fs.readFileSync(0, "utf8"));
    const results = modules.map((b64) => runModule(Buffer.from(b64, "base64")));
    process.stdout.write(JSON.stringify(results));
  }
}

module.exports = { runModule, toStr };
