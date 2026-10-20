// cdp_check.mjs — drive real (not virtual-time) headless Chrome: real frames, real mouse moves, screenshots.
// Headless --screenshot / --dump-dom with --virtual-time-budget barely runs requestAnimationFrame, so canvas and
// hover effects look frozen there. This driver waits in real time instead. Needs Node 22+ (global WebSocket).
// usage: node cdp_check.mjs <url> <out.png> [width] [height] [steps-json]
// steps: [{"wait":ms} | {"move":[x,y]} | {"moveTo":"css selector", "dx":0.5, "dy":0.5} | {"shot":"file.png"} | {"eval":"js"} | {"scroll":y}]
import { spawn } from "node:child_process";
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const [url, out, w = "1400", h = "900", stepsJson = "[]"] = process.argv.slice(2);
const CH = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; // set CHROME on Linux/Windows
const port = 9300 + Math.floor(Math.random() * 500);
const prof = mkdtempSync(join(tmpdir(), "cdp-"));
const chrome = spawn(CH, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, `--window-size=${w},${h}`, "--hide-scrollbars", "--force-device-scale-factor=1", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) {
  await sleep(150);
  try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page"); } catch {}
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pending = new Map(); const logs = [];
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.consoleAPICalled") logs.push(msg.params.args.map((a) => a.value ?? a.description).join(" "));
  if (msg.method === "Runtime.exceptionThrown") logs.push("EXC " + (msg.params.exceptionDetails.exception?.description ?? msg.params.exceptionDetails.text));
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Runtime.enable"); await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: +w, height: +h, deviceScaleFactor: 1, mobile: +w < 500 });
await send("Page.navigate", { url });
await sleep(2500);
const shot = async (file) => { const r = await send("Page.captureScreenshot", { format: "png" }); writeFileSync(file, Buffer.from(r.result.data, "base64")); };
const evaluate = async (expr) => (await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result?.result?.value;
let mx = 0, my = 0;
const moveTo = async (x, y, n = 12) => { for (let i = 1; i <= n; i++) { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: mx + ((x - mx) * i) / n, y: my + ((y - my) * i) / n }); await sleep(16); } mx = x; my = y; };
for (const s of JSON.parse(stepsJson)) {
  if (s.wait) await sleep(s.wait);
  if (s.move) await moveTo(...s.move);
  if (s.moveTo) { const r = await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(s.moveTo)});if(!e)return null;const b=e.getBoundingClientRect();return [b.left+b.width*${s.dx ?? 0.5}, b.top+b.height*${s.dy ?? 0.5}]})()`); if (r) await moveTo(r[0], r[1]); else logs.push("no element " + s.moveTo); }
  if (s.scroll !== undefined) await evaluate(`window.scrollTo(0, ${s.scroll})`);
  if (s.eval) logs.push("eval: " + JSON.stringify(await evaluate(s.eval)));
  if (s.shot) await shot(s.shot);
}
await shot(out);
console.log(logs.join("\n"));
ws.close(); chrome.kill();
