# Glassbox bench: the interactive figure

An isometric, interactive drawing of one Glassbox audit (`GlassboxV2.analyze`), built with the [Anatomy](https://github.com/wheresryan22/anatomy) Agent Skill by Ryan (MIT). A pegboard has one peg per attention head (12 layers by 12 heads). The pegs rise to each head's causal score, the top few light up as the circuit, and three dials read sufficiency, comprehensiveness and F1, which set the grade.

| File | What it is |
|---|---|
| `glassbox-bench-light.html` | The figure, light theme. Standalone: open it in a browser. |
| `glassbox-bench.html` | The same figure, dark theme. |
| `glassbox-bench.gif` | A recording of one full cycle, used in the main README. |
| `glassbox-bench.png` | A still of the finished state. |
| `rig.mjs` | The model: the README's IOI readings and the timeline. |
| `parts.mjs` | The geometry of every part, shared by the build and the live page. |
| `build.mjs` | Writes the HTML pages. |
| `kit/`, `scripts/` | The Anatomy drawing kit and its capture and line-check scripts, copied unchanged. `LICENSE-anatomy` is its licence. |

## Use it

Hover to scrub through the cycle, click or press Space or Enter to replay, arrow keys to step, Home and End to jump. The figure tours by itself when left alone and shows one still frame under reduced motion.

```bash
node build.mjs --light   # writes glassbox-bench-light.html  (Node 20.10 or later, nothing to install)
node build.mjs           # writes glassbox-bench.html
node scripts/lines.mjs glassbox-bench-light.html --reduced   # every drawn line must end on something (needs Chrome; set CHROME_PATH)
```

## What is real and what is drawn

Real, from the README: sufficiency 1.00, comprehensiveness 0.543, F1 0.704 and Grade B on the IOI benchmark with GPT-2 small, the 12 by 12 head grid, attribution patching in 3 forward passes.

Drawn for the picture: the score of every head and which heads end up lit. They show the idea, not the output of a run. The figure makes no measurement claim.
