import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as k from "../../.agents/skills/anatomy/kit/iso-kit.mjs";
import { kitScript } from "../../.agents/skills/anatomy/scripts/inline-kit.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const theme = process.argv.includes("--light") ? "light" : "dark";
const W = 760, H = 500;
const at = (p, P) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const accentTone = (name) => name === "green" ? "green" : name === "red" ? "red" : name === "amber" ? "red" : "blue";

const specs = [
  {
    id: "guardrail-gate", fig: "Fig 2", title: "Guardrail gate", readout: "6 checks · order blocked", hint: "Hover to inspect a control", accent: "red",
    caption: "Before execution, the order plan passes through spread, size, open-order, daily-limit, loss-limit and macro checks. One failed control blocks the route.",
    keys: [{ mark: "red", label: "Blocked control" }, { mark: "green", label: "Passed control" }, { mark: "blue", label: "Order plan" }],
    mode: "gate",
  },
  {
    id: "audit-ledger", fig: "Fig 3", title: "Audit ledger", readout: "3 decisions · traceable", hint: "Hover to inspect a record", accent: "blue",
    caption: "Every decision is written to the audit trail with its timestamp, pillar statuses and reason. The ledger turns an automated action into a reviewable record.",
    keys: [{ mark: "green", label: "BUY record" }, { mark: "red", label: "BLOCKED record" }, { mark: "blue", label: "Recorded reason" }],
    mode: "ledger",
  },
  {
    id: "macro-blackout", fig: "Fig 4", title: "Macro blackout shield", readout: "CPI · protected window", hint: "Hover to inspect the event window", accent: "amber",
    caption: "A high-impact economic event creates a protected blackout window. Even a positive signal cannot cross the shield while the event risk is active.",
    keys: [{ mark: "red", label: "Protected blackout" }, { mark: "amber", label: "Economic event" }, { mark: "green", label: "Signal path" }],
    mode: "macro",
  },
  {
    id: "data-fusion", fig: "Fig 5", title: "Signal fusion manifold", readout: "4 pillars · synchronized", hint: "Hover to inspect a signal", accent: "green",
    caption: "Technical, on-chain, news and macro inputs arrive through separate channels and are synchronized at the decision manifold before a result is considered.",
    keys: [{ mark: "blue", label: "Input channel" }, { mark: "lit", label: "Fusion manifold" }, { mark: "green", label: "Verified output" }],
    mode: "fusion",
  },
  {
    id: "position-sizer", fig: "Fig 6", title: "Position sizing rig", readout: "Risk budget · 1:2 plan", hint: "Hover to inspect the sizing model", accent: "green",
    caption: "The position sizing rig converts account balance, risk budget and stop distance into a bounded order plan with stop-loss and take-profit levels.",
    keys: [{ mark: "blue", label: "Account balance" }, { mark: "red", label: "Stop-loss boundary" }, { mark: "green", label: "Take-profit boundary" }],
    mode: "sizer",
  },
];

function sceneBase(P) {
  const base = { x: -220, y: -112, w: 440, d: 224, r: 12 };
  return [`<path class="iso-halo" d="${k.haloOf(base, -8, 12, P)}"/>`, S(k.slabOf(base, 0, 12, P, 10, 2), { tone: "mid" }), L(k.planOutline(k.insetPlan(base, 7), 12, P, 10), { tone: "lo" })].join("");
}
function box(P, plan, z, h, label, tone = "mid", lit = false) {
  const top = z + h;
  return S(k.slabOf(plan, z, h, P, 8, 1), { tone, crease: "lo", lit }) +
    L(k.planOutline(k.insetPlan(plan, 4), top, P, 8), { tone: tone === "mid" ? "faint" : tone }) +
    k.faceTextSvg(k.topMatrix([plan.x + plan.w / 2, plan.y + plan.d / 2], top + 1, P), label, { size: 3.2, tone: tone === "mid" ? "lo" : tone, anchor: "middle" });
}
function bolt(P, plan, z) {
  const pts = k.corners(plan, 6);
  return L(pts.map(([x, y]) => k.ring(x, y, 2, z, P, 14)).join(""), { tone: "lo" }) + Dots(pts.map(([x, y]) => at([x, y, z], P)), "lo");
}
function Dots(points, tone = "mid") { return k.dotsSvg(points, { size: 0.55, tone }); }
function wire(P, from, to, tone = "blue", size = 1.4) { return k.wireSvg(at(from, P), at(to, P), { tone, size, ends: "both" }); }

function gate(P) {
  const checks = [
    { x: -172, label: "SPREAD", ok: true }, { x: -112, label: "SIZE", ok: true }, { x: -52, label: "OPEN", ok: true },
    { x: 8, label: "DAILY", ok: true }, { x: 68, label: "LOSS", ok: false }, { x: 128, label: "MACRO", ok: true },
  ];
  let out = sceneBase(P);
  checks.forEach((c) => { const plan = { x: c.x, y: -20, w: 44, d: 62, r: 5 }; out += box(P, plan, 14, 14, c.label, c.ok ? "mid" : "red", c.ok); out += bolt(P, plan, 28); });
  out += box(P, { x: -52, y: 48, w: 104, d: 36, r: 7 }, 14, 20, "ORDER PLAN", "hi", true);
  out += box(P, { x: 76, y: 48, w: 96, d: 36, r: 7 }, 14, 20, "BLOCKED", "red", false);
  checks.forEach((c) => { out += wire(P, [-52, 48, 32], [c.x + 22, 11, 28], c.ok ? "green" : "red"); });
  out += wire(P, [52, 66, 32], [76, 66, 32], "red", 1.8);
  return out;
}
function ledger(P) {
  let out = sceneBase(P);
  out += box(P, { x: -176, y: -70, w: 116, d: 140, r: 8 }, 14, 28, "AUDIT LOG", "hi", true);
  const rows = [
    { y: -52, label: "BUY", tone: "green" }, { y: -6, label: "NO TRADE", tone: "mid" }, { y: 40, label: "BLOCKED", tone: "red" },
  ];
  rows.forEach((r, i) => {
    const plan = { x: -40, y: r.y, w: 188, d: 32, r: 4 };
    out += box(P, plan, 14, 10, r.label, r.tone === "mid" ? "mid" : r.tone, r.tone === "green");
    out += L(k.lineOnTop([plan.x + 10, plan.y + 9], [plan.x + 82, plan.y + 9], 25, P), { tone: "lo", free: true });
    out += L(k.lineOnTop([plan.x + 92, plan.y + 9], [plan.x + 166, plan.y + 9], 25, P), { tone: "lo", free: true });
    out += wire(P, [-60, r.y + 16, 26], [plan.x, r.y + 16, 25], r.tone === "green" ? "green" : r.tone === "red" ? "red" : "blue");
  });
  out += box(P, { x: -40, y: 84, w: 188, d: 20, r: 4 }, 14, 8, "TIMESTAMP + REASON", "mid");
  return out;
}
function macro(P) {
  let out = sceneBase(P);
  out += box(P, { x: -174, y: -52, w: 90, d: 100, r: 8 }, 14, 26, "SIGNAL", "green", true);
  out += box(P, { x: -34, y: -52, w: 90, d: 100, r: 8 }, 14, 26, "CPI", "red", false);
  out += box(P, { x: 108, y: -52, w: 90, d: 100, r: 26 }, 14, 12, "SHIELD", "red", false);
  out += k.faceTextSvg(k.topMatrix([11, -2], 28, P), "T−30m  /  T+30m", { size: 3, tone: "red", anchor: "middle" });
  out += wire(P, [-84, -2, 40], [-34, -2, 40], "green", 1.8);
  out += wire(P, [56, -2, 40], [108, -2, 28], "red", 1.8);
  out += L(k.lineOnTop([72, -42], [72, 42], 28, P), { tone: "red", dashed: true, free: true });
  out += Dots([at([72, -42, 28], P), at([72, 42, 28], P)], "red");
  return out;
}
function fusion(P) {
  let out = sceneBase(P);
  const inputs = [
    { plan: { x: -176, y: -68, w: 78, d: 42, r: 5 }, label: "TECH", tone: "blue" },
    { plan: { x: -176, y: 22, w: 78, d: 42, r: 5 }, label: "CHAIN", tone: "blue" },
    { plan: { x: -78, y: -68, w: 78, d: 42, r: 5 }, label: "NEWS", tone: "green" },
    { plan: { x: -78, y: 22, w: 78, d: 42, r: 5 }, label: "MACRO", tone: "amber" },
  ];
  inputs.forEach((i) => { out += box(P, i.plan, 14, 16, i.label, accentTone(i.tone), i.tone === "green"); });
  out += box(P, { x: 24, y: -48, w: 90, d: 92, r: 18 }, 18, 34, "FUSION", "hi", true);
  out += box(P, { x: 148, y: -34, w: 50, d: 64, r: 6 }, 18, 20, "PASS", "green", true);
  inputs.forEach((i) => out += wire(P, [i.plan.x + i.plan.w, i.plan.y + i.plan.d / 2, 30], [24, 0, 52], i.tone === "amber" ? "red" : i.tone));
  out += wire(P, [114, 0, 52], [148, -2, 40], "green", 1.8);
  return out;
}
function sizer(P) {
  let out = sceneBase(P);
  out += box(P, { x: -176, y: -62, w: 94, d: 124, r: 8 }, 14, 24, "BALANCE", "blue", false);
  out += box(P, { x: -28, y: -62, w: 94, d: 124, r: 8 }, 14, 24, "RISK", "red", false);
  out += box(P, { x: 120, y: -62, w: 78, d: 56, r: 7 }, 14, 22, "SL", "red", false);
  out += box(P, { x: 120, y: 20, w: 78, d: 56, r: 7 }, 14, 22, "TP", "green", true);
  out += k.faceTextSvg(k.topMatrix([-129, 4], 40, P), "ACCOUNT → SIZE", { size: 3, tone: "blue", anchor: "middle" });
  out += k.faceTextSvg(k.topMatrix([19, 4], 40, P), "1% → 2R", { size: 3, tone: "red", anchor: "middle" });
  out += wire(P, [-82, 0, 40], [-28, 0, 40], "blue", 1.8);
  out += wire(P, [66, 0, 40], [120, -34, 38], "red");
  out += wire(P, [66, 0, 40], [120, 48, 38], "green");
  return out;
}

function scene(spec) {
  const points = [k.boxCorners({ x: -220, y: -112, w: 440, d: 224, r: 12 }, -8, 12), k.boxCorners({ x: -180, y: -70, w: 380, d: 140, r: 8 }, 14, 60)].flat();
  const P = k.fitProjection(points, W, H, { pad: 34, azimuth: 42, elevation: 30 });
  const body = spec.mode === "gate" ? gate(P) : spec.mode === "ledger" ? ledger(P) : spec.mode === "macro" ? macro(P) : spec.mode === "fusion" ? fusion(P) : sizer(P);
  const svg = k.figureSvg({ width: W, height: H, label: `${spec.title}. ${spec.caption}`, body });
  const live = `<script data-live>const stage=document.querySelector('.iso-stage');const svg=stage.querySelector('svg');const readout=document.querySelector('[data-readout]');const states=${JSON.stringify([spec.readout, "Input inspected · verified", "Risk rule inspected · protected", "Decision path inspected · traceable"])};let i=0;function setState(n){i=(n+states.length)%states.length;readout.textContent=states[i];stage.setAttribute('aria-valuenow',String(i));stage.setAttribute('aria-valuetext',states[i]);svg.dataset.active=String(i)}stage.addEventListener('pointermove',e=>setState(Math.floor(((e.clientX-svg.getBoundingClientRect().left)/svg.getBoundingClientRect().width)*4)));stage.addEventListener('pointerleave',()=>setState(0));stage.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key==='ArrowDown'){e.preventDefault();setState(i+1)}if(e.key==='ArrowLeft'||e.key==='ArrowUp'){e.preventDefault();setState(i-1)}});setState(0);</script>`;
  const bodyHtml = k.plateHtml({ fig: spec.fig, title: spec.title, hint: spec.hint, readout: spec.readout, keys: spec.keys, caption: spec.caption, body: `<div class="iso-stage" tabindex="0" role="slider" aria-label="${spec.title}: inspect the mechanism" aria-valuemin="0" aria-valuemax="3" aria-valuenow="0">${svg}</div>` });
  // pageHtml creates the module script; add the live script body before closing page tag.
  const page = k.pageHtml({ title: `Nexa-Trader · ${spec.title}`, theme, body: bodyHtml, script: kitScript() + live.replace(/^<script data-live>|<\/script>$/g, "") });
  writeFileSync(join(HERE, theme === "light" ? `${spec.id}-light.html` : `${spec.id}.html`), page);
}

mkdirSync(HERE, { recursive: true });
for (const spec of specs) scene(spec);
console.log(`wrote ${specs.length} figures (${theme})`);
