// The model behind the figure. Pure functions: the geometry, the motion and the readout all read from here.
// Real, from the README: the IOI benchmark readout on GPT-2 small (sufficiency 1.00, comprehensiveness 0.543,
// F1 0.704, Grade B), attribution patching in 3 forward passes, a 12 x 12 head grid, the default sufficiency
// target 0.85. Illustrative: every per-head score and which heads end up in the circuit.

export const LAYERS = 12;
export const HEADS = 12;
export const SUFF = 1.0;
export const COMP = 0.543;
export const F1 = 0.704;
export const GRADE = "B";
export const K = 6; // heads kept in the drawn circuit
export const CYCLE = 26;

export const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
export const seg = (u, a, b) => clamp((u - a) / (b - a));
export const ease = (t) => t * t * (3 - 2 * t);

// deterministic sample scores in 0..1; a handful of clear peaks, a low noisy floor
const peaks = { "9,9": 1, "9,6": 0.86, "10,0": 0.74, "10,7": 0.6, "7,3": 0.52, "8,6": 0.46 };
const hash = (l, h) => { let x = (l * 73856093) ^ (h * 19349663); x = (x ^ (x >>> 13)) * 1274126177; return ((x ^ (x >>> 16)) >>> 0) / 4294967295; };
export const SCORE = Array.from({ length: LAYERS }, (_, l) => Array.from({ length: HEADS }, (_, h) => peaks[l + "," + h] ?? 0.04 + 0.2 * hash(l, h) ** 2));
export const ORDER = SCORE.flatMap((row, l) => row.map((s, h) => ({ l, h, s }))).sort((a, b) => b.s - a.s || a.l - b.l || a.h - b.h);
export const CIRCUIT = ORDER.slice(0, K).map(({ l, h }) => l * HEADS + h);
export const inCircuit = (l, h) => CIRCUIT.includes(l * HEADS + h);

export const T = {
  prompts: [0.02, 0.1],
  rise: [0.12, 0.34],
  pick: [0.36, 0.52],
  keep: [0.54, 0.68], // only the circuit stays: sufficiency
  cut: [0.7, 0.84], // the circuit is removed: comprehensiveness
  grade: [0.86, 0.95],
  fade: [0.985, 1.0],
};

export function pose(u) {
  const fade = 1 - seg(u, T.fade[0], T.fade[1]);
  const rise = ease(seg(u, ...T.rise));
  const pickT = seg(u, ...T.pick);
  const picked = CIRCUIT.map((_, i) => ease(clamp(pickT * K - i, 0, 1)));
  // 0 = all pegs up, 1 = circuit alone (others sunk), then back, then circuit sunk
  const keepIn = ease(seg(u, T.keep[0], T.keep[0] + 0.04));
  const keepOut = ease(seg(u, T.keep[1] - 0.04, T.keep[1]));
  const cutIn = ease(seg(u, T.cut[0], T.cut[0] + 0.04));
  const cutOut = ease(seg(u, T.cut[1] - 0.04, T.cut[1]));
  const sinkOthers = keepIn * (1 - keepOut);
  const sinkCircuit = cutIn * (1 - cutOut);
  return {
    u,
    fade,
    prompts: ease(seg(u, ...T.prompts)),
    rise,
    picked,
    sinkOthers,
    sinkCircuit,
    suff: SUFF * ease(seg(u, T.keep[0] + 0.03, T.keep[1] - 0.03)),
    comp: COMP * ease(seg(u, T.cut[0] + 0.03, T.cut[1] - 0.03)),
    f1: F1 * ease(seg(u, T.grade[0], T.grade[1])),
    grade: seg(u, T.grade[0] + 0.05, T.grade[1]),
  };
}

export function pegHeight(l, h, p) {
  const circ = inCircuit(l, h);
  let v = SCORE[l][h] * p.rise;
  if (circ) v *= 1 - p.sinkCircuit;
  else v *= 1 - p.sinkOthers;
  return v;
}

export function describe(u) {
  const p = pose(u);
  if (u < T.rise[0]) return "a prompt, the answer it should give, and the wrong one";
  if (u < T.pick[0]) return "attribution patching: score all 144 heads in 3 passes";
  if (u < T.keep[0]) return `keep the top ${K} heads: the smallest circuit that carries the decision`;
  if (u < T.cut[0]) return `circuit alone: sufficiency ${p.suff.toFixed(2)}`;
  if (u < T.grade[0]) return `circuit removed: comprehensiveness ${p.comp.toFixed(3)}`;
  if (u < T.fade[0]) return `F1 ${p.f1.toFixed(3)}  ·  Grade ${p.grade > 0.5 ? GRADE : "..."}`;
  return "ready for the next decision";
}
