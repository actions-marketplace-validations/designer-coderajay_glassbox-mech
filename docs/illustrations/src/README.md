# Illustration sources

The three images one level up are drawn by `glassbox.py` with the small kit in `xh.py` (wobbly black lines, a black creature with white dot eyes, orange for the path, red for the key point, blue for side notes). They are hand-authored vector drawings, not AI-generated art.

```bash
python3 glassbox.py                                              # writes 04-find-circuit.svg, 05-test-by-ablation.svg, 06-why-it-changed.svg
node render.js 04-find-circuit 05-test-by-ablation 06-why-it-changed   # needs playwright with Chromium; writes the PNGs
```

The lettering font is Caveat (SIL Open Font License 1.1), embedded in each SVG from `caveat-latin-600-normal.woff2`.

The grids and dials are drawn for the picture and show no measured data.
