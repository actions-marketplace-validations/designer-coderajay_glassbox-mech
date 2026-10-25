// Builds the interactive Glassbox bench: node build.mjs [--light]
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as k from "./kit/iso-kit.mjs";
import { kitScript } from "./scripts/inline-kit.mjs";
import * as rig from "./rig.mjs";
import * as g from "./parts.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const theme = process.argv.includes("--light") ? "light" : "dark";
const WIDTH = 800;
const HEIGHT = 420;
const { W } = g;
const REST = 0.975;

const P = k.fitProjection(
  [...k.boxCorners(W.PLATE, -17, 0), [-100, 0, 40], [146, 50, 30], [150, -60, 8]],
  WIDTH,
  HEIGHT,
  { pad: 22, azimuth: 62 },
);

const CLEAN = [26, 30, 20];
const CORRUPT = [26, 10, 20];
const cardPos = (p, i) => [i === 0 ? 50 : 100, -61, p.prompts];

function dynamic(p) {
  const lit = new Set(rig.CIRCUIT.filter((_, i) => p.picked[i] > 0.5));
  const q = (v) => Math.round(v * 40) / 40;
  const pegs = g.pegs(P, (l, h) => q(rig.pegHeight(l, h, p)), lit);
  const mk = (i, bars, light) => {
    const [x, y, o] = cardPos(p, i);
    return g.card(P, x - 30 * (1 - o), y, bars, o * p.fade, light);
  };
  return { pegs, clean: mk(0, CLEAN, true), corrupt: mk(1, CORRUPT, false) };
}

function scene(u) {
  const p = rig.pose(u);
  const d = dynamic(p);
  const gs = W.GAUGES;
  const val = { suff: p.suff, comp: p.comp, f1: p.f1 };
  return [
    g.plate(P),
    g.board(P),
    `<g data-part="pegs">${d.pegs}</g>`,
    g.tray(P),
    `<g data-part="clean">${d.clean}</g>`,
    `<g data-part="corrupt">${d.corrupt}</g>`,
    `<g data-part="plaque">${g.plaque(P, p.grade)}</g>`,
    ...gs.flatMap((gg) => [g.gauge(P, gg), `<path data-part="needle-${gg.key}" class="iso-line" data-tone="lit" data-free="start" d="${g.needleD(P, gg, val[gg.key])}" style="stroke-width:1"/>`]),
  ];
}

const svg = k.figureSvg({
  width: WIDTH,
  height: HEIGHT,
  label:
    "A pegboard bench that works like a Glassbox audit. A board of 144 pegs, one per attention head in 12 layers of 12, rises to the height of each head's causal score. The top few pegs light up as the circuit. Keeping only the circuit reads sufficiency on one dial, removing only the circuit reads comprehensiveness on a second, and a third reads their F1, which sets the grade plate.",
  body: scene(REST),
});

const strip = (file) => readFileSync(join(HERE, file), "utf8").replace(/^export /gm, "").replace(/^import .*$/gm, "");
const kitNames = Object.keys(k).join(", ");

const live = `
const P = ${JSON.stringify(P)};
const REST = ${REST};
const CLEAN = ${JSON.stringify(CLEAN)}, CORRUPT = ${JSON.stringify(CORRUPT)};
const stage = document.querySelector(".iso-stage");
const svg = stage.querySelector("svg");
const part = (name) => svg.querySelector('[data-part="' + name + '"]');
const E = { pegs: part("pegs"), clean: part("clean"), corrupt: part("corrupt"), plaque: part("plaque"), needles: Object.fromEntries(W.GAUGES.map((gg) => [gg.key, part("needle-" + gg.key)])) };
const readout = document.querySelector("[data-readout]");
const still = matchMedia("(prefers-reduced-motion: reduce)");
const cache = {};
const put = (key, node, html) => { if (cache[key] !== html) { cache[key] = html; node.innerHTML = html; } };
let u = still.matches ? REST : 0, target = u, touring = !still.matches, frame = 0, last = 0, visible = false, idleTimer = 0;

function render() {
  const p = pose(u);
  const lit = new Set(CIRCUIT.filter((_, i) => p.picked[i] > 0.5));
  const q = (v) => Math.round(v * 40) / 40;
  put("pegs", E.pegs, pegs(P, (l, h) => q(pegHeight(l, h, p)), lit));
  const mk = (i, bars, light) => { const o = Math.round(p.prompts * 20) / 20; return card(P, (i === 0 ? 50 : 100) - 30 * (1 - o), -61, bars, o * p.fade, light); };
  put("clean", E.clean, mk(0, CLEAN, true));
  put("corrupt", E.corrupt, mk(1, CORRUPT, false));
  put("plaque", E.plaque, plaque(P, Math.round(p.grade * 20) / 20));
  const val = { suff: p.suff, comp: p.comp, f1: p.f1 };
  for (const gg of W.GAUGES) E.needles[gg.key].setAttribute("d", needleD(P, gg, val[gg.key]));
  const text = describe(u);
  if (readout.textContent !== text) readout.textContent = text;
  stage.setAttribute("aria-valuenow", String(Math.round(u * 100)));
  stage.setAttribute("aria-valuetext", text);
}

function tick(now) {
  const dt = last ? Math.min((now - last) / 1000, 1 / 30) : 1 / 60;
  last = now;
  if (touring) { u += dt / CYCLE; if (u >= 1) u -= 1; target = u; }
  else { u = still.matches ? target : u + (target - u) * (1 - Math.exp(-dt / 0.12)); if (Math.abs(target - u) < 0.0004) u = target; }
  render();
  frame = visible && (touring || u !== target) ? requestAnimationFrame(tick) : 0;
}
const run = () => { if (!frame && visible) { last = 0; frame = requestAnimationFrame(tick); } };
const hold = () => { touring = false; clearTimeout(idleTimer); idleTimer = setTimeout(() => { touring = !still.matches; run(); }, 3600); run(); };
new IntersectionObserver((entries) => { visible = entries[entries.length - 1].isIntersecting; if (visible) run(); }, { rootMargin: "120px 0px" }).observe(stage);
stage.addEventListener("pointermove", (event) => { const box = svg.getBoundingClientRect(); target = clamp(((event.clientX - box.left) / box.width - 0.06) / 0.88, 0, 0.995); hold(); });
stage.addEventListener("pointerleave", () => { clearTimeout(idleTimer); idleTimer = setTimeout(() => { touring = !still.matches; run(); }, 1200); });
stage.addEventListener("click", () => { u = target = 0; touring = !still.matches; if (still.matches) u = target = REST; clearTimeout(idleTimer); render(); run(); });
stage.addEventListener("keydown", (event) => {
  const key = event.key;
  if (key === "ArrowRight" || key === "ArrowUp") target = clamp(target + 0.03, 0, 0.995);
  else if (key === "ArrowLeft" || key === "ArrowDown") target = clamp(target - 0.03, 0, 0.995);
  else if (key === "Home") target = 0;
  else if (key === "End") target = REST;
  else if (key === " " || key === "Enter") { event.preventDefault(); u = target = 0; touring = !still.matches; render(); run(); return; }
  else return;
  event.preventDefault();
  hold();
});
window.__set = (uu) => { u = target = uu; touring = false; render(); };
render();
`;

const phone = `<style>@media (max-width:560px){.iso-plate-corner[data-corner="hint"]{display:none}.iso-plate-corner[data-corner="readout"]{left:0;right:0;white-space:normal;text-align:right;font-size:9.5px;line-height:1.35}}</style>`;
const body = phone + k.plateHtml({
  fig: "Fig 1",
  title: "Glassbox bench",
  hint: "Hover to scrub · click to replay",
  readout: rig.describe(REST),
  keys: [
    { mark: "lit", label: "Heads in the circuit and the gauge needles" },
    { mark: "raised", label: "One peg per attention head: 12 layers by 12 heads" },
  ],
  caption:
    "A pegboard with one peg per attention head. Attribution patching scores every head in 3 forward passes and the pegs rise to match. The top few light up as the circuit. Keeping only the circuit measures sufficiency (dial S); removing only the circuit measures comprehensiveness (dial C); F1 combines them and sets the grade. The three readings are the IOI benchmark on GPT-2 small from the README (1.00, 0.543, 0.704, Grade B); the per-head scores and which heads are lit are illustrative.",
  body: `<div class="iso-stage" tabindex="0" role="slider" aria-label="Glassbox bench: hover to scrub, click to replay, arrow keys step" aria-valuemin="0" aria-valuemax="100" aria-valuenow="97">${svg}</div>`,
});

const script = kitScript() + `\nconst k = { ${kitNames} };\n` + strip("rig.mjs") + "\n" + strip("parts.mjs") + "\n" + live;
const file = theme === "light" ? "glassbox-bench-light.html" : "glassbox-bench.html";
writeFileSync(join(HERE, file), k.pageHtml({ title: "Glassbox bench", theme, body, script, width: 860 }));
console.log("wrote", file);
