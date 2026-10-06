// Drive mario.html in headless Chromium frame by frame and save PNG frames per scene.
// usage: node drive.mjs scenes.mjs outdir [sceneName]   (build.sh runs this)
import { spawn } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import path from "node:path";

const [scenesFile, outDir, only] = process.argv.slice(2);
const { scenes } = await import(pathToFileURL(path.resolve(scenesFile)));
const GAME = pathToFileURL(path.resolve(path.dirname(new URL(import.meta.url).pathname), "../mario.html")).href;
const PORT = 9337;

const chrome = spawn("chromium", ["--headless=new", "--disable-gpu", `--remote-debugging-port=${PORT}`,
  "--user-data-dir=" + path.resolve(outDir, ".profile"), "--window-size=800,800", "about:blank"],
  { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let targets;
for (let i = 0; i < 50; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json(); break; } catch { await sleep(200); }
}
const page = targets.find(t => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener("open", r));
let id = 0; const waiting = new Map();
ws.addEventListener("message", ev => {
  const m = JSON.parse(ev.data);
  if (m.id && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); }
});
const send = (method, params = {}) => new Promise(r => { const i = ++id; waiting.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
async function ev(expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
  if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 600));
  return r.result.result.value;
}

await send("Page.enable");
await send("Runtime.enable");
// the game's own clock never runs: requestAnimationFrame is a no-op, we call update/render ourselves
await send("Page.addScriptToEvaluateOnNewDocument", { source: "window.requestAnimationFrame = () => 0;" });

// in-page helpers: step n frames with held keys, tapping some on the first frame
const HELPERS = `
window.__step = (n, hold, tap) => {
  for (const k of Object.keys(keys)) keys[k] = false;
  for (let i = 0; i < n; i++) {
    for (const k of Object.keys(hold)) keys[k] = !!hold[k];
    if (i === 0) for (const k of tap) { pressed[k] = true; keys[k] = true; }
    update();
  }
  // a scene can frame the shot further left than the game's own camera would
  if (window.__camShift) cam = Math.max(0, cam - window.__camShift);
  render();
  return c.toDataURL("image/png");
};
window.__reset = () => {
  startLevel(true);
  for (const s of overworld.enemies) s.spawned = true;   // scenes place their own cast
  ents.length = 0;
};
0`;

// method shorthand ("setup() {...}") serialises without the function keyword
const fnSrc = f => { const s = f.toString(); return /^(function|async|\(|[\w$]+\s*=>)/.test(s) ? s : "function " + s; };

for (const scene of scenes) {
  if (only && scene.name !== only) continue;
  await send("Page.navigate", { url: GAME });
  await sleep(700);
  await ev(HELPERS);
  await ev(`__reset(); (${fnSrc(scene.setup)})(); render(); 0`);
  const dir = path.join(outDir, scene.name); rmSync(dir, { recursive: true, force: true }); mkdirSync(dir, { recursive: true });
  let n = 0;
  const save = url => writeFileSync(path.join(dir, String(n++).padStart(4, "0") + ".png"), Buffer.from(url.split(",")[1], "base64"));
  for (const step of scene.steps) {
    if (step.js) { await ev(`(${fnSrc(step.js)})(); 0`); continue; }
    const hold = step.hold || {}, tap = step.tap || [];
    const frames = step.frames ?? 2;
    if (step.skip) { await ev(`__step(${frames}, ${JSON.stringify(hold)}, ${JSON.stringify(tap)}); 0`); continue; }
    // two game updates per saved frame -> 30 fps video
    for (let f = 0; f < frames; f += 2) {
      const t = f === 0 ? tap : [];
      save(await ev(`__step(2, ${JSON.stringify(hold)}, ${JSON.stringify(t)})`));
    }
  }
  console.log(scene.name, n, "frames");
}
ws.close(); chrome.kill();
