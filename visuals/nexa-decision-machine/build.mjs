import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as k from "../../.agents/skills/anatomy/kit/iso-kit.mjs";
import { kitScript } from "../../.agents/skills/anatomy/scripts/inline-kit.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const theme = process.argv.includes("--light") ? "light" : "dark";
const STATES = ["4 pillars · awaiting decision", "Technical Analysis · verified", "On-chain Metrics · verified", "News Sentiment · verified", "Macro Calendar · protected"];
const WIDTH = 760;
const HEIGHT = 500;

const BASE = { x: -220, y: -112, w: 440, d: 224, r: 12 };
const BASE_Z = 0;
const ENGINE = { x: -58, y: -48, w: 116, d: 96, r: 10 };
const ENGINE_Z = 22;
const GUARD = { x: -76, y: 58, w: 152, d: 28, r: 7 };
const OUTPUTS = [
  { plan: { x: 108, y: -38, w: 74, d: 34, r: 6 }, label: "BUY", tone: "green" },
  { plan: { x: 108, y: 18, w: 74, d: 34, r: 6 }, label: "NO TRADE", tone: "amber" },
];
const PILLARS = [
  { id: "technical", title: "Technical", plan: { x: -190, y: -92, w: 86, d: 54, r: 6 }, accent: "cyan" },
  { id: "onchain", title: "On-chain", plan: { x: -190, y: 30, w: 86, d: 54, r: 6 }, accent: "blue" },
  { id: "news", title: "News", plan: { x: -80, y: -92, w: 86, d: 54, r: 6 }, accent: "green" },
  { id: "macro", title: "Macro", plan: { x: -80, y: 30, w: 86, d: 54, r: 6 }, accent: "amber" },
];

const extremes = [
  ...k.boxCorners(BASE, -8, 12),
  ...k.boxCorners(ENGINE, ENGINE_Z, ENGINE_Z + 44),
  ...k.boxCorners(GUARD, 12, 28),
  ...OUTPUTS.flatMap(({ plan }) => k.boxCorners(plan, 18, 34)),
];
const P = k.fitProjection(extremes, WIDTH, HEIGHT, { pad: 34, azimuth: 42, elevation: 30 });
const at = (p) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (points, style) => k.dotsSvg(points, style);
const toneFor = (accent) => accent === "green" ? "green" : accent === "amber" ? "red" : "blue";

function screws(plan, z) {
  const pts = k.corners(plan, 7);
  return D(pts.map(([x, y]) => at([x, y, z])), { size: 0.65, tone: "lo" }) +
    L(pts.map(([x, y]) => k.ring(x, y, 2.3, z, P, 16)).join(""), { tone: "lo" });
}

function base() {
  const out = [`<path class="iso-halo" d="${k.haloOf(BASE, -8, 12, P)}"/>`];
  out.push(S(k.slabOf(BASE, BASE_Z, 12, P, 10, 2), { tone: "mid" }));
  out.push(L(k.planOutline(k.insetPlan(BASE, 7), 12, P, 10), { tone: "lo" }));
  out.push(screws(BASE, 12));
  const rail = { x: -202, y: 101, w: 404, d: 7, r: 2 };
  out.push(S(k.slabOf(rail, 12, 2, P, 4, 0.5), { tone: "lo", crease: "none" }));
  const ticks = k.topTicks(rail.x + 8, rail.x + rail.w - 8, 12, 5, rail.y + 1, 14, [1.5, 3], P);
  out.push(L(ticks.minor, { tone: "lo" }), L(ticks.major, { tone: "mid" }));
  return out.join("");
}

function pillar(pillar) {
  const { plan, title, accent } = pillar;
  const z = 14;
  const out = [];
  out.push(S(k.slabOf(plan, z, 16, P, 7, 1), { tone: "hi", crease: "lo" }));
  out.push(L(k.planOutline(k.insetPlan(plan, 4), z + 16, P, 7), { tone: "faint" }));
  out.push(screws(plan, z + 16));
  const bar = { x: plan.x + 8, y: plan.y + 8, w: plan.w - 16, d: 5, r: 2 };
  out.push(S(k.slabOf(bar, z + 16, 3, P, 4), { tone: toneFor(accent), crease: "none", lit: accent === "green" }));
  out.push(k.faceTextSvg(k.topMatrix([plan.x + plan.w / 2, plan.y + plan.d / 2], z + 19, P), title, { size: 3.2, tone: "lo", anchor: "middle" }));
  return out.join("");
}

function engine() {
  const out = [];
  out.push(`<path class="iso-halo" d="${k.haloOf(ENGINE, ENGINE_Z, 44, P)}" style="filter:blur(5px)"/>`);
  out.push(S(k.slabOf(ENGINE, ENGINE_Z, 44, P, 10, 2), { tone: "hi", crease: "lo", lit: true }));
  out.push(L(k.planOutline(k.insetPlan(ENGINE, 8), ENGINE_Z + 44, P, 10), { tone: "mid" }));
  out.push(screws(ENGINE, ENGINE_Z + 44));
  const rotor = [
    [0, 0, ENGINE_Z + 45],
    [-24, 0, ENGINE_Z + 45], [24, 0, ENGINE_Z + 45],
    [0, -24, ENGINE_Z + 45], [0, 24, ENGINE_Z + 45],
  ];
  out.push(S(k.cylinder(0, 0, 18, ENGINE_Z + 44, 5, P, 48), { tone: "mid" }));
  out.push(L([[-26, 0], [26, 0], [0, -26], [0, 26]].map(([x, y]) => k.lineOnTop([0, 0], [x, y], ENGINE_Z + 49, P)).join(""), { tone: "lit", free: true }));
  out.push(D(rotor.map(at), { size: 1.15, tone: "lit", pulse: true }));
  out.push(k.faceTextSvg(k.topMatrix([0, -4], ENGINE_Z + 50, P), "DECISION", { size: 3.7, tone: "lit", anchor: "middle" }));
  return out.join("");
}

function guardrail() {
  const out = [];
  out.push(S(k.slabOf(GUARD, 12, 14, P, 8, 1), { tone: "mid", crease: "lo" }));
  out.push(L(k.planOutline(k.insetPlan(GUARD, 4), 26, P, 8), { tone: "red" }));
  const gate = { x: -8, y: GUARD.y + 2, w: 16, d: GUARD.d - 4, r: 3 };
  out.push(S(k.slabOf(gate, 26, 18, P, 5, 1), { tone: "red", crease: "none" }));
  out.push(k.faceTextSvg(k.topMatrix([0, GUARD.y + GUARD.d / 2], 45, P), "RISK", { size: 3.5, tone: "lit", anchor: "middle" }));
  return out.join("");
}

function outputs() {
  return OUTPUTS.map(({ plan, label, tone }) => {
    const z = 18;
    const out = [];
    out.push(S(k.slabOf(plan, z, 16, P, 7, 1), { tone: tone === "green" ? "hi" : "mid", crease: tone === "green" ? "green" : "red", lit: tone === "green" }));
    out.push(L(k.planOutline(k.insetPlan(plan, 4), z + 16, P, 7), { tone: tone === "green" ? "green" : "red" }));
    out.push(k.faceTextSvg(k.topMatrix([plan.x + plan.w / 2, plan.y + plan.d / 2], z + 17, P), label, { size: 3.2, tone: tone === "green" ? "green" : "red", anchor: "middle" }));
    return out.join("");
  }).join("");
}

function wires() {
  const out = [];
  for (const pillar of PILLARS) {
    const p = pillar.plan;
    out.push(k.wireSvg(at([p.x + p.w / 2, p.y + p.d / 2, 30]), at([ENGINE.x + ENGINE.w / 2, ENGINE.y + ENGINE.d / 2, ENGINE_Z + 44]), { tone: pillar.accent === "green" ? "green" : "blue", size: 1.4, ends: "both" }));
  }
  out.push(k.wireSvg(at([ENGINE.x + ENGINE.w / 2, ENGINE.y + ENGINE.d, ENGINE_Z + 25]), at([0, GUARD.y + GUARD.d / 2, 28]), { tone: "red", size: 1.6, ends: "both" }));
  out.push(k.wireSvg(at([GUARD.x + GUARD.w, GUARD.y + GUARD.d / 2, 28]), at([OUTPUTS[0].plan.x, OUTPUTS[0].plan.y + OUTPUTS[0].plan.d / 2, 26]), { tone: "green", size: 1.4, ends: "both" }));
  out.push(k.wireSvg(at([GUARD.x + GUARD.w, GUARD.y + GUARD.d / 2, 23]), at([OUTPUTS[1].plan.x, OUTPUTS[1].plan.y + OUTPUTS[1].plan.d / 2, 26]), { tone: "red", size: 1.4, ends: "both" }));
  return out.join("");
}

const svg = k.figureSvg({
  width: WIDTH,
  height: HEIGHT,
  label: "An isometric Nexa-Trader decision machine. Four market-data pillars feed a central decision engine, pass through a risk guardrail, and produce either BUY or NO TRADE.",
  body: [base(), ...PILLARS.map(pillar), wires(), engine(), guardrail(), outputs()].join(""),
});

const live = `
const stage = document.querySelector('.iso-stage');
const svg = stage.querySelector('svg');
const readout = document.querySelector('[data-readout]');
const panels = [...svg.querySelectorAll('.iso-line[data-tone]')];
const states = ${JSON.stringify(STATES)};
let active = 0;
function update(next) {
  active = (next + states.length) % states.length;
  const text = states[active];
  readout.textContent = text;
  stage.setAttribute('aria-valuenow', String(active));
  stage.setAttribute('aria-valuetext', text);
  svg.dataset.active = String(active);
}
stage.addEventListener('pointermove', (event) => {
  const box = svg.getBoundingClientRect();
  const x = (event.clientX - box.left) / box.width;
  update(Math.min(4, Math.max(0, Math.floor(x * 5))));
});
stage.addEventListener('pointerleave', () => update(0));
stage.addEventListener('keydown', (event) => {
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') { event.preventDefault(); update(active + 1); }
  if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') { event.preventDefault(); update(active - 1); }
  if (event.key === 'Home') { event.preventDefault(); update(0); }
  if (event.key === 'End') { event.preventDefault(); update(4); }
});
update(0);
`;

const body = k.plateHtml({
  fig: "Fig 1",
  title: "Nexa decision machine",
  hint: "Hover or use arrow keys to inspect each pillar",
  readout: STATES[0],
  keys: [
    { mark: "blue", label: "Four independent market-data pillars" },
    { mark: "lit", label: "Central decision engine" },
    { mark: "red", label: "Risk guardrail can block execution" },
    { mark: "green", label: "BUY only after approval" },
  ],
  caption: "Technical, on-chain, news and macro signals converge in one decision engine. A risk guardrail stands between analysis and execution; when approval is incomplete, the safe outcome is NO TRADE.",
  body: `<div class="iso-stage" tabindex="0" role="slider" aria-label="Nexa-Trader decision machine: inspect the four signal pillars" aria-valuemin="0" aria-valuemax="4" aria-valuenow="0">${svg}</div>`,
});

mkdirSync(HERE, { recursive: true });
writeFileSync(join(HERE, theme === "light" ? "nexa-decision-machine-light.html" : "nexa-decision-machine.html"), k.pageHtml({ title: "Nexa-Trader Decision Machine", theme, body, script: kitScript() + live }));
console.log("wrote", theme === "light" ? "nexa-decision-machine-light.html" : "nexa-decision-machine.html");
