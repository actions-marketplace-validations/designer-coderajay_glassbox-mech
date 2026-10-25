from xh import *
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
F = "caveat-latin-600-normal.woff2"

# 1. find the circuit: a wall of heads, a flashlight, a few glow
c = Canvas(21, F)
gx, gy, cell = 760, 180, 38
glow = {(2, 4), (5, 8), (6, 2), (3, 9), (7, 6), (4, 1)}
for r in range(10):
    for q in range(10):
        on = (r, q) in glow
        c.rect(gx + q * cell, gy + r * cell, 30, 30, color=RED if on else BLACK, fill="#fbd9cf" if on else "#fff", sw=2.4 if not on else 3.4)
c.text(gx + 190, gy - 30, "every attention head", BLACK, 40, "middle")
c.xiaohei(430, 560, 1.0, look=.8, hands=[(560, 380), None])
# flashlight beam
c.line([(560, 380), (610, 360)], BLACK, 10)
c.line([(610, 345), (760, 250), (760, 480), (610, 395)], ORANGE, 3, "none", closed=False, dash="10 8")
c.text(190, 300, "3 passes,\nnot a search", BLUE, 40)
c.text(1020, 640, "keep the few\nthat carry the decision", RED, 42, "middle")
c.save("04-find-circuit.svg")

# 2. test by taking it out
c = Canvas(22, F)
c.rect(300, 330, 330, 190, fill="#fff")
for r in range(3):
    for q in range(6):
        gap = (r, q) in {(0, 2), (1, 4), (2, 1)}
        if not gap:
            c.rect(322 + q * 50, 350 + r * 54, 34, 36, sw=2.4)
        else:
            c.rect(322 + q * 50, 350 + r * 54, 34, 36, sw=2, fill="#fff", color=ORANGE)
c.text(465, 300, "the circuit, pulled out", BLACK, 40, "middle")
c.xiaohei(760, 560, 1.0, look=-.8, hands=[(660, 400), None])
c.rect(640, 392, 34, 36, color=RED, fill="#fbd9cf", sw=3.4, rot=8)
# a dial that drops
c.circle(1090, 400, 100, BLACK, "#fff", 3.6)
for t in range(11):
    a = -2.35 + t * 0.47
    c.line([(1090 + 82 * math.sin(a), 400 - 82 * math.cos(a)), (1090 + 96 * math.sin(a), 400 - 96 * math.cos(a))], BLACK, 2.4)
c.line([(1090, 400), (1090 + 70 * math.sin(-1.3), 400 - 70 * math.cos(-1.3))], RED, 5)
c.text(1090, 560, "ablate, don't assert", RED, 44, "middle")
c.text(1090, 250, "does the decision break?", BLUE, 38, "middle")
c.text(180, 640, "sufficiency: circuit alone\ncomprehensiveness: circuit removed", BLUE, 34)
c.save("05-test-by-ablation.svg")

# 3. why did the system change: three switches, one at a time
c = Canvas(23, F)
names = ["new index", "edited prompt", "new framework"]
for i, n in enumerate(names):
    x = 180 + i * 300
    c.rect(x, 330, 200, 90, fill="#fff")
    on = i == 0
    c.rect(x + (110 if on else 20), 345, 70, 60, color=RED if on else BLACK, fill="#fbd9cf" if on else "#fff", sw=3.4 if on else 2.6)
    c.text(x + 100, 460, n, BLACK, 38, "middle")
    c.circle(x + 100, 280, 18, RED if on else BLACK, "#f6b8a9" if on else "#fff", 3)
c.text(580, 195, "3 changes landed in the same week", BLACK, 42, "middle")
c.xiaohei(1160, 600, 1.0, look=-.8, hands=[(990, 392), None])
c.text(180, 590, "switch each one on alone,\nthen revert each alone", BLUE, 40)
c.text(580, 720, "where runs differ is not why", RED, 42, "middle")
c.save("06-why-it-changed.svg")
