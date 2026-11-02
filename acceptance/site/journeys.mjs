// Browser journeys for the Dex Trove docs site: real Chrome (headless, real time), real clicks and keystrokes.
//
//   node acceptance/site/journeys.mjs <dist-dir> [--base /Dex-Trove/]
//
// Serves the built site at its base path, then walks what a visitor does: land on the home page, search and
// filter the catalog, open an item and copy its install command, read a docs page whose Mermaid diagram must
// render and respond to hover, switch theme, hit a 404, and check phone width for horizontal overflow. Every page
// is also watched for console errors and uncaught exceptions. Prints one line per journey and a JSON summary;
// exits 1 if any journey fails. Needs Node 22+ and Chrome (CHROME=… to override the path).
import { execFileSync, spawn } from "node:child_process";
import { createReadStream, existsSync, mkdtempSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { extname, join, normalize } from "node:path";

const args = process.argv.slice(2);
const dist = args[0];
const base = args.includes("--base") ? args[args.indexOf("--base") + 1] : "/Dex-Trove/";
if (!dist || !existsSync(join(dist, "index.html"))) {
  console.error(`usage: journeys.mjs <dist-dir> [--base /Dex-Trove/] (no index.html in ${dist})`);
  process.exit(2);
}
const CHROME =
  process.env.CHROME ||
  ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium"].find(existsSync);
if (!CHROME) {
  console.error("Chrome not found; set CHROME=/path/to/chrome");
  process.exit(2);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2" };

// ---------------------------------------------------------------------------------------------- static server
const server = createServer((req, res) => {
  const url = decodeURIComponent((req.url || "/").split("?")[0]);
  if (!url.startsWith(base)) return void res.writeHead(404).end("outside base");
  let file = normalize(join(dist, url.slice(base.length)));
  if (!file.startsWith(normalize(dist))) return void res.writeHead(403).end();
  if (existsSync(file) && statSync(file).isDirectory()) file = join(file, "index.html");
  if (!existsSync(file)) {
    res.writeHead(404, { "content-type": "text/html" });
    return void createReadStream(join(dist, "404.html")).pipe(res);
  }
  res.writeHead(200, { "content-type": TYPES[extname(file)] || "application/octet-stream" });
  createReadStream(file).pipe(res);
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const origin = `http://127.0.0.1:${server.address().port}`;

// ---------------------------------------------------------------------------------------------- CDP plumbing
const port = 9500 + Math.floor(Math.random() * 400);
// --use-mock-keychain / --password-store=basic: with an isolated HOME (as in the acceptance sandbox) macOS
// Chrome otherwise blocks on the login keychain and the whole run hangs.
const chrome = spawn(
  CHROME,
  ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "journeys-"))}`,
    "--no-first-run", "--no-default-browser-check", "--use-mock-keychain", "--password-store=basic", "--hide-scrollbars", "about:blank"],
  { stdio: "ignore" },
);
// Watchdog: a hang anywhere fails fast with a clear message instead of eating the caller's timeout.
const WATCHDOG_MS = Number(process.env.JOURNEYS_TIMEOUT_MS || 180000);
setTimeout(() => {
  console.log(`✗ journeys timed out after ${WATCHDOG_MS / 1000}s`);
  chrome.kill();
  process.exit(1);
}, WATCHDOG_MS).unref();
let target;
for (let i = 0; i < 100 && !target; i++) {
  await sleep(150);
  try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page"); } catch {}
}
if (!target) {
  console.log("✗ Chrome did not expose a DevTools target (is CHROME correct?)");
  process.exit(1);
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0;
const pending = new Map();
let problems = [];
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") problems.push("exception: " + (msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text).split("\n")[0]);
  if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") problems.push("console.error: " + msg.params.args.map((a) => a.value ?? a.description).join(" ").slice(0, 200));
  if (msg.method === "Log.entryAdded" && msg.params.entry.level === "error" && !/favicon|fonts\.g/.test(msg.params.entry.url || "")) problems.push("log: " + msg.params.entry.text.slice(0, 200));
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval failed: " + r.result.exceptionDetails.text);
  return r.result?.result?.value;
};
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const viewport = (width, height, mobile = false) => send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
const go = async (path, settle = 1500) => {
  problems = [];
  await send("Page.navigate", { url: origin + base + path.replace(/^\//, "") });
  await sleep(settle);
};
const waitFor = async (expr, ms = 8000) => {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (await evaluate(expr)) return true; await sleep(200); }
  return false;
};
const mouse = async (x, y) => send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
const type = async (text) => { for (const ch of text) await send("Input.insertText", { text: ch }); };

// ---------------------------------------------------------------------------------------------- journeys
const results = [];
async function journey(name, fn) {
  const started = Date.now();
  try {
    const detail = (await fn()) || "";
    const errs = problems.filter((p) => !/ResizeObserver loop/.test(p));
    if (errs.length) throw new Error(errs.slice(0, 3).join(" | "));
    results.push({ name, ok: true, ms: Date.now() - started, detail });
    console.log(`✓ ${name}${detail ? ` (${detail})` : ""}`);
  } catch (e) {
    results.push({ name, ok: false, ms: Date.now() - started, detail: String(e.message || e) });
    console.log(`✗ ${name}: ${e.message || e}`);
  }
}
const expect = (cond, message) => { if (!cond) throw new Error(message); };

await viewport(1366, 900);

await journey("home page introduces the trove", async () => {
  await go("");
  const t = await evaluate(`({ title: document.title, h1: document.querySelector("h1")?.innerText || "", sr: document.querySelector("h1 .mk-sr")?.textContent || "", stats: document.querySelectorAll(".stat, [data-countup]").length })`);
  expect(/Dex Trove/.test(t.title), `title is ${t.title}`);
  expect(/trove of dexterities/i.test(t.h1 + t.sr), `headline missing: ${t.h1}`);
  expect(t.stats >= 3, `only ${t.stats} stats`);
  return `${t.stats} stats`;
});

await journey("catalog search narrows results and kind filters apply", async () => {
  await go("catalog/");
  const total = await evaluate(`document.querySelectorAll("#results li:not([hidden])").length`);
  expect(total > 900, `catalog shows ${total} items`);
  await evaluate(`document.querySelector("#q").focus()`);
  await type("interactive web motion");
  await sleep(500);
  const hits = await evaluate(`Array.from(document.querySelectorAll("#results li:not([hidden])")).map(li => li.dataset.name)`);
  expect(hits.includes("interactive-web-motion"), `search did not find it: ${hits.slice(0, 5)}`);
  expect(hits.length < total, "search did not narrow the list");
  await evaluate(`document.querySelector("#q").value = ""; document.querySelector("#q").dispatchEvent(new Event("input"))`);
  await evaluate(`document.querySelector('button[data-kind="hook"]').click()`);
  await sleep(400);
  const kinds = await evaluate(`[...new Set(Array.from(document.querySelectorAll("#results li:not([hidden])")).map(li => li.dataset.kind))]`);
  expect(kinds.length === 1 && kinds[0] === "hook", `hook filter shows kinds ${kinds}`);
  return `${total} items → ${hits.length} for the query; hook filter OK`;
});

await journey("facet filters match the CLI, count disjunctively and work from the keyboard", async () => {
  // Parity: the site and `dex search` must agree on the same query (DEX_BIN is the build under test).
  const cli = JSON.parse(execFileSync(process.env.DEX_BIN || "dex", ["search", "--methodology", "tdd", "--phase", "testing", "--json", "-n", "1000"], { encoding: "utf8" }));
  await go("catalog/?methodology=tdd&phase=testing");
  const site = await evaluate(`Array.from(document.querySelectorAll("#results li:not([hidden])")).map(li => li.dataset.kind + ":" + li.querySelector(".meta").textContent.trim()).sort()`);
  const expected = cli.results.map((r) => `${r.kind}:${r.id}`).sort();
  expect(JSON.stringify(site) === JSON.stringify(expected), `site shows ${site.length}, CLI ${expected.length}: ${site.slice(0, 3)} vs ${expected.slice(0, 3)}`);
  const state = await evaluate(`({ pressed: document.querySelector('.facet-chip[data-facet="methodology"][data-value="tdd"]').getAttribute("aria-pressed"), open: document.querySelector('details.facet[data-facet="methodology"]').open, chips: document.querySelectorAll("#active-chips .chip").length })`);
  expect(state.pressed === "true" && state.open && state.chips === 2, `URL state not restored: ${JSON.stringify(state)}`);
  // Disjunctive: the tdd chip's count ignores the methodology selection, so it equals the CLI total for phase=testing + tdd.
  const tddCount = await evaluate(`Number(document.querySelector('.facet-chip[data-facet="methodology"][data-value="tdd"] .n').textContent)`);
  expect(tddCount === expected.length, `tdd chip says ${tddCount}, expected ${expected.length}`);
  // Keyboard: focus a chip in another facet and press Enter; results narrow and the URL records it.
  await evaluate(`document.querySelector('details.facet[data-facet="role"]').open = true; document.querySelector('.facet-chip[data-facet="role"][data-value="developer"]').focus()`);
  await send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, text: "\r" });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
  await sleep(400);
  const after = await evaluate(`({ n: document.querySelectorAll("#results li:not([hidden])").length, url: location.search, live: document.querySelector("#count").textContent })`);
  expect(after.url.includes("role=developer"), `URL is ${after.url}`);
  expect(after.n <= expected.length && after.n > 0, `role filter shows ${after.n}`);
  await evaluate(`document.querySelector("#reset").click()`);
  await sleep(300);
  const cleared = await evaluate(`location.search`);
  expect(!/methodology|role|phase/.test(cleared), `reset left ${cleared}`);
  return `${expected.length} items match CLI; keyboard → ${after.n}; "${after.live}"`;
});

await journey("item page shows where it fits, linked into the catalog", async () => {
  await go("skill/superpowers.test-driven-development/");
  const t = await evaluate(`({ text: document.querySelector(".where-it-fits")?.innerText || "", link: document.querySelector('.where-it-fits a[href*="methodology=tdd"]')?.getAttribute("href") || "" })`);
  expect(/Where it fits/i.test(t.text) && /Test-driven development/i.test(t.text), "facets section missing");
  expect(/reviewed by the Dex Trove maintainers/i.test(t.text), "review status missing");
  expect(t.link.includes("catalog/?methodology=tdd"), `chip link is ${t.link}`);
  return "facets, review status and catalog links present";
});

await journey("item page shows licence, provenance and install commands", async () => {
  await go("skill/neo-pragnya.living-diagrams/");
  const t = await evaluate(`document.body.innerText`);
  expect(/dex install (skill:)?neo-pragnya\/living-diagrams --target claude/.test(t), "install command missing");
  expect(/MIT/.test(t), "licence missing");
  expect(t.includes("ananke://skill/neo-pragnya/living-diagrams"), "Ananke reference missing");
  return "install, licence and Ananke ref present";
});

await journey("docs Mermaid diagram renders and lights up on hover", async () => {
  await go("docs/concepts/architecture/", 800);
  await evaluate(`document.querySelector("pre.mermaid-src, figure.mermaid-diagram")?.scrollIntoView({ block: "center" })`);
  expect(await waitFor(`!!document.querySelector("figure.mermaid-diagram svg")`, 15000), "diagram never rendered");
  expect(await evaluate(`document.querySelectorAll(".diagram-error").length === 0`), "a diagram failed to render");
  expect(await waitFor(`!!document.querySelector("figure.mermaid-diagram svg.dfx")`, 5000), "diagram-fx did not enhance the diagram");
  // Hover nodes (not clusters) until one with connections lights its edges.
  const centres = await evaluate(`Array.from(document.querySelectorAll("figure.mermaid-diagram svg g.node.dfx-node")).slice(0, 8).map(n => { n.scrollIntoView({ block: "center" }); const r = n.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })`);
  let lit = false;
  for (const [x, y] of centres) {
    await mouse(1, 1);
    await mouse(x, y);
    if (await waitFor(`!!document.querySelector("figure.mermaid-diagram svg.dfx-focus .dfx-edge.dfx-on")`, 1200)) { lit = true; break; }
  }
  expect(lit, "hovering diagram nodes never lit an edge");
  return "rendered, enhanced, hover lights edges";
});

await journey("code blocks keep syntax highlighting", async () => {
  await go("docs/guides/getting-started/");
  const n = await evaluate(`document.querySelectorAll("pre.astro-code span[style*='--shiki']").length`);
  expect(n > 5, `only ${n} highlighted tokens`);
  return `${n} highlighted tokens`;
});

await journey("theme toggle switches to dark and remembers it", async () => {
  await go("");
  await evaluate(`document.querySelector("#theme-toggle").click()`);
  expect(await evaluate(`document.documentElement.dataset.theme === "dark"`), "dark theme not applied");
  await go("catalog/");
  expect(await evaluate(`document.documentElement.dataset.theme === "dark"`), "theme not remembered across pages");
  await evaluate(`document.querySelector("#theme-toggle").click()`);
  return "dark on, persisted, off";
});

await journey("unknown page shows the 404", async () => {
  await go("no-such-page/");
  const t = await evaluate(`document.body.innerText`);
  expect(t.includes("That page isn't in the trove"), "404 page not shown");
  problems = problems.filter((p) => !/404|Failed to load resource/.test(p));
});

await viewport(390, 844, true);
await journey("phone width has no horizontal scroll", async () => {
  const bad = [];
  const pages = ["", "catalog/", "catalog/?methodology=tdd&phase=testing", "skill/neo-pragnya.living-diagrams/",
    "skill/superpowers.test-driven-development/", "docs/concepts/architecture/", "docs/concepts/which-artifact-when/",
    "docs/guides/finding-capabilities/"];
  for (const path of pages) {
    await go(path, 1200);
    const w = await evaluate(`[document.documentElement.scrollWidth, window.innerWidth]`);
    if (w[0] > w[1] + 1) bad.push(`${path || "/"} ${w[0]}>${w[1]}`);
  }
  expect(!bad.length, bad.join(", "));
  return `${pages.length} pages fit 390 px`;
});

ws.close();
chrome.kill();
server.close();
const failed = results.filter((r) => !r.ok);
console.log(JSON.stringify({ journeys: results.length, failed: failed.length, results }));
console.log(failed.length ? `${failed.length} journey(s) failed` : `all ${results.length} journeys passed`);
process.exit(failed.length ? 1 : 0);
