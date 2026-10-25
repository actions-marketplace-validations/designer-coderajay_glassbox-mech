// Geometry for the Glassbox bench. Every function takes the projection P and returns SVG text.
// The same file is used by build.mjs (first frame) and inlined into the page (live frames).
import * as k from "./kit/iso-kit.mjs";

export const W = {
  PLATE: { x: -176, y: -84, w: 360, d: 168, r: 9 },
  PLATE_H: 12,
  FOOT_H: 5,
  BOARD: { x: -162, y: -74, w: 150, d: 148, r: 3 },
  BOARD_H: 5,
  CELL: 12,
  PEG_R: 3.5,
  PEG_MAX: 30,
  TRAY: { x: 16, y: -76, w: 150, d: 30, r: 3 },
  CARD: { w: 34, d: 20 },
  PLAQUE: { x: 22, y: -40, w: 144, d: 24, r: 3 },
  GAUGES: [
    { key: "suff", cx: 42, cy: 50, R: 17, z: 17, h: 7, label: "S" },
    { key: "comp", cx: 94, cy: 50, R: 17, z: 17, h: 7, label: "C" },
    { key: "f1", cx: 146, cy: 50, R: 17, z: 17, h: 7, label: "F1" },
  ],
  A0: -0.75 * Math.PI,
  SPAN: 1.5 * Math.PI,
};
export const pegXY = (l, h) => [W.BOARD.x + 4 + W.CELL * h + W.CELL / 2, W.BOARD.y + 4 + W.CELL * l + W.CELL / 2];

const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (points, style) => k.dotsSvg(points, style);
const at = (P, p) => k.iso(p, P);
const opaque = (svg, op) => (op >= 0.999 ? svg : `<g opacity="${Math.max(0, op).toFixed(3)}">${svg}</g>`);

export function plate(P) {
  const { PLATE, PLATE_H, FOOT_H } = W;
  const out = [`<path class="iso-halo" d="${k.haloOf(PLATE, -PLATE_H - FOOT_H, PLATE_H, P)}"/>`];
  const feet = [...k.corners(PLATE, 22), [0, PLATE.y + 22], [0, PLATE.y + PLATE.d - 22]];
  for (const [x, y] of [...feet].sort((a, b) => k.depthOf([a[0], a[1], 0], P) - k.depthOf([b[0], b[1], 0], P))) {
    out.push(S(k.cylinder(x, y, 7, -PLATE_H - FOOT_H, 1.6, P, 28), { tone: "lo" }));
    out.push(S(k.cylinder(x, y, 5.4, -PLATE_H - FOOT_H + 1.6, FOOT_H - 1.6, P, 28), { tone: "mid" }));
  }
  out.push(S(k.slabOf(PLATE, -PLATE_H, PLATE_H, P, 8, 1.6), { tone: "mid" }));
  out.push(L(k.planOutline(k.insetPlan(PLATE, 5), 0, P), { tone: "lo" }));
  const corner = k.corners(PLATE, 10);
  out.push(L(corner.map(([x, y]) => k.ring(x, y, 2.2, 0, P, 16)).join(""), { tone: "lo" }));
  out.push(D(corner.map(([x, y]) => at(P, [x, y, 0])), { size: 0.5 }));
  const strip = { x: -162, y: PLATE.y + PLATE.d - 15, w: 326, d: 7, r: 1 };
  out.push(S(k.slabOf(strip, 0, 0.6, P, 3), { tone: "lo", crease: "none" }));
  const t = k.topTicks(strip.x + 4, strip.x + strip.w - 4, 5, 5, strip.y + 0.8, 0.6, [2, 3.6], P);
  out.push(L(t.minor, { tone: "lo" }), L(t.major, { tone: "mid" }));
  out.push(D([at(P, [strip.x + 2, strip.y + 3.5, 0.6]), at(P, [strip.x + strip.w - 2, strip.y + 3.5, 0.6])], { size: 0.45 }));
  return out.join("");
}

// the pegboard: one hole per attention head, rows are layers, columns are heads
export function board(P) {
  const { BOARD, BOARD_H, CELL } = W;
  const out = [`<path class="iso-halo" d="${k.haloOf(BOARD, 0, BOARD_H, P)}" style="filter:blur(4px)"/>`];
  out.push(S(k.slabOf(BOARD, 0, BOARD_H, P, 5, 0.7), { tone: "mid" }));
  out.push(L(k.planOutline(k.insetPlan(BOARD, 2.6), BOARD_H, P, 4), { tone: "faint" }));
  const holes = [];
  for (let l = 0; l < 12; l++) for (let h = 0; h < 12; h++) holes.push(at(P, [...pegXY(l, h), BOARD_H]));
  out.push(D(holes, { size: 0.5, tone: "lo" }));
  out.push(D(k.corners(BOARD, 2).map(([x, y]) => at(P, [x, y, BOARD_H])), { size: 0.45 }));
  return out.join("");
}

// all 144 pegs, back to front. heights: (l, h) -> 0..1 ; lit: Set of l*12+h
export function pegs(P, height, lit) {
  const { BOARD_H, PEG_R, PEG_MAX } = W;
  const list = [];
  for (let l = 0; l < 12; l++) for (let h = 0; h < 12; h++) list.push([l, h, ...pegXY(l, h)]);
  list.sort((a, b) => k.depthOf([a[2], a[3], 0], P) - k.depthOf([b[2], b[3], 0], P));
  const out = [];
  for (const [l, h, x, y] of list) {
    const v = height(l, h);
    const hh = 1.2 + PEG_MAX * v;
    const on = lit.has(l * 12 + h);
    out.push(S(k.cylinder(x, y, PEG_R, BOARD_H, hh, P, 10), { tone: on ? "hi" : "mid", lit: on, crease: "none" }));
  }
  return out.join("");
}

export function tray(P) {
  const { TRAY } = W;
  const out = [`<path class="iso-halo" d="${k.haloOf(TRAY, 0, 3, P)}" style="filter:blur(4px)"/>`];
  out.push(S(k.slabOf(TRAY, 0, 3, P, 5, 0.5), { tone: "mid" }));
  out.push(L(k.planOutline(k.insetPlan(TRAY, 2.4), 3, P, 4), { tone: "faint" }));
  out.push(D(k.corners(TRAY, 2.6).map(([x, y]) => at(P, [x, y, 3])), { size: 0.4 }));
  return out.join("");
}

// a prompt card; `bars` are printed line lengths; `swap` marks the corrupted copy with a short red-less tick set
export function card(P, x, y, bars, op = 1, lit = true) {
  if (op <= 0.003) return "";
  const { w, d } = W.CARD;
  const z = 3;
  const plan = { x: x - w / 2, y: y - d / 2, w, d, r: 1.2 };
  const out = [S(k.slabOf(plan, z, 1.2, P, 4, 0.3), { tone: "hi", lit, crease: "lo" })];
  bars.forEach((len, i) => out.push(L(k.lineOnTop([x - w / 2 + 3, y - d / 2 + 4.4 + i * 4.6], [x - w / 2 + 3 + len, y - d / 2 + 4.4 + i * 4.6], z + 1.2, P), { tone: "lo", free: true })));
  return opaque(out.join(""), op);
}

export function plaque(P, grade) {
  const { PLAQUE } = W;
  const top = 2;
  const out = [S(k.slabOf(PLAQUE, 0, top, P, 5, 0.5), { tone: "mid" })];
  out.push(L(k.planOutline(k.insetPlan(PLAQUE, 2.2), top, P, 4), { tone: "faint" }));
  out.push(k.faceTextSvg(k.topMatrix([PLAQUE.x + 8, PLAQUE.y + 16.6], top, P, "x"), "GRADE", { size: 7, tone: "lo" }));
  if (grade > 0.02) out.push(`<g opacity="${grade.toFixed(3)}">${k.faceTextSvg(k.topMatrix([PLAQUE.x + 104, PLAQUE.y + 19], top, P, "x"), "B", { size: 16, tone: "hi" })}</g>`);
  out.push(D(k.corners(PLAQUE, 2.6).map(([x, y]) => at(P, [x, y, top])), { size: 0.4 }));
  return out.join("");
}

export function gauge(P, g) {
  const { cx: x, cy: y, R, z: Z, h: H } = g;
  const { A0, SPAN } = W;
  const top = Z + H;
  const out = [];
  const foot = { x: x - 14, y: y - 14, w: 28, d: 28, r: 3 };
  out.push(`<path class="iso-halo" d="${k.haloOf(foot, 0, 4, P)}" style="filter:blur(4px)"/>`);
  out.push(S(k.slabOf(foot, 0, 4, P, 5, 0.6), { tone: "mid" }));
  out.push(D(k.corners(foot, 3).map(([a, b]) => at(P, [a, b, 4])), { size: 0.4 }));
  out.push(S(k.cylinder(x, y, 3.8, 4, Z - 4, P, 24), { tone: "mid", crease: "none" }));
  out.push(L(k.sideArc(x, y, 3.8, 10, P, 14), { tone: "faint" }));
  out.push(S(k.cylinder(x, y, R, Z, H, P, 48, 0.7), { tone: "hi", crease: "lo" }));
  out.push(L(k.knurl(x, y, R, top - 3, top, 64, P, 0.3), { tone: "lo" }));
  out.push(L(k.ring(x, y, R - 2, top, P, 48), { tone: "lo" }));
  const ticks = k.radialTicks(x, y, R - 2.6, 50, 5, top, [1.2, 2.5], P, A0, SPAN);
  out.push(L(ticks.minor, { tone: "lo" }), L(ticks.major, { tone: "mid" }));
  out.push(L(k.ring(x, y, 1.5, top, P, 16), { tone: "mid" }));
  out.push(k.faceTextSvg(k.topMatrix([x, y + 8.6], top, P, "x"), g.label, { size: 3.4, tone: "hi", anchor: "middle" }));
  return out.join("");
}
export function needleD(P, g, v) {
  const { cx: x, cy: y, R, z: Z, h: H } = g;
  const a = W.A0 + W.SPAN * v;
  return k.lineOnTop([x - Math.sin(a) * 3, y + Math.cos(a) * 3], [x + Math.sin(a) * (R - 4), y - Math.cos(a) * (R - 4)], Z + H + 0.2, P);
}
