"""Tiny Xiaohei-style illustration kit: wobbly black lines on white, a black bean creature with white dot eyes,
orange for the path, red for the key point, blue for secondary notes. Output: SVG with the font embedded."""
import base64, math, random

W, H = 1376, 768
BLACK, ORANGE, RED, BLUE = "#111111", "#e08a2c", "#c2392f", "#2f6ea5"

class Canvas:
    def __init__(self, seed, font_path):
        self.r = random.Random(seed)
        self.items = []
        self.font = base64.b64encode(open(font_path, "rb").read()).decode()

    # ---- wobbly primitives
    def _wob(self, pts, amp=1.3, step=9):
        out = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
            nx, ny = (y1 - y0), -(x1 - x0)
            ln = math.hypot(nx, ny) or 1
            for i in range(n):
                t = i / n
                j = self.r.uniform(-amp, amp)
                out.append((x0 + (x1 - x0) * t + nx / ln * j, y0 + (y1 - y0) * t + ny / ln * j))
        out.append(pts[-1])
        return out

    def _d(self, pts, closed=False):
        d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
        for i in range(1, len(pts) - 1):
            mx, my = (pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2
            d += f" Q{pts[i][0]:.1f} {pts[i][1]:.1f} {mx:.1f} {my:.1f}"
        d += f" L{pts[-1][0]:.1f} {pts[-1][1]:.1f}"
        return d + (" Z" if closed else "")

    def line(self, pts, color=BLACK, w=3.2, fill="none", closed=False, amp=1.3, dash=None):
        p = self._wob(pts + ([pts[0]] if closed else []), amp)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.items.append(f'<path d="{self._d(p, closed)}" fill="{fill}" stroke="{color}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"{da}/>')

    def rect(self, x, y, w, h, color=BLACK, fill="#fff", sw=3.2, rot=0):
        c = (x + w / 2, y + h / 2)
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        a = math.radians(rot)
        pts = [(c[0] + (px - c[0]) * math.cos(a) - (py - c[1]) * math.sin(a), c[1] + (px - c[0]) * math.sin(a) + (py - c[1]) * math.cos(a)) for px, py in pts]
        self.line(pts, color, sw, fill, closed=True)

    def circle(self, cx, cy, r, color=BLACK, fill="#fff", sw=3.2):
        pts = [(cx + r * math.cos(t), cy + r * math.sin(t)) for t in [i * math.pi / 14 for i in range(28)]]
        self.line(pts, color, sw, fill, closed=True, amp=1.0)

    def arrow(self, pts, color=ORANGE, w=4.2):
        self.line(pts, color, w)
        (x0, y0), (x1, y1) = pts[-2], pts[-1]
        a = math.atan2(y1 - y0, x1 - x0)
        for s in (-0.5, 0.5):
            self.line([(x1, y1), (x1 - 20 * math.cos(a + s), y1 - 20 * math.sin(a + s))], color, w)

    def text(self, x, y, s, color=BLACK, size=40, anchor="start"):
        lines = s.split("\n")
        for i, t in enumerate(lines):
            self.items.append(f'<text x="{x}" y="{y + i * size * 1.05:.1f}" font-family="Caveat" font-weight="600" font-size="{size}" fill="{color}" text-anchor="{anchor}">{t}</text>')

    # ---- the creature
    def xiaohei(self, cx, base, s=1.0, look=0, hands=None, squint=False):
        """cx,base = centre x and the y of its feet; s scale; look -1..1 eye shift; hands = [(x,y) or None, (x,y) or None]"""
        bw, bh = 120 * s, 150 * s
        top = base - 58 * s - bh
        body = [(cx - bw / 2, top + bh * 0.55), (cx - bw * 0.46, top + bh * 0.15), (cx - bw * 0.2, top), (cx + bw * 0.2, top),
                (cx + bw * 0.46, top + bh * 0.15), (cx + bw / 2, top + bh * 0.55), (cx + bw * 0.46, top + bh * 0.95), (cx, top + bh), (cx - bw * 0.46, top + bh * 0.95)]
        for lx in (-0.22, 0.22):
            self.line([(cx + lx * bw, top + bh * 0.98), (cx + lx * bw + 3 * s, base)], BLACK, 4.2 * s)
            self.line([(cx + lx * bw + 3 * s, base), (cx + lx * bw + 16 * s, base + 1)], BLACK, 4.2 * s)
        self.line(body, BLACK, 3, BLACK, closed=True, amp=1.2)
        ey = top + bh * 0.33
        for ex in (-0.17, 0.17):
            x = cx + ex * bw + look * 5 * s
            if squint:
                self.line([(x - 8 * s, ey), (x + 8 * s, ey)], "#fff", 3.6 * s)
            else:
                self.items.append(f'<circle cx="{x:.1f}" cy="{ey:.1f}" r="{7 * s:.1f}" fill="#fff"/>')
        for side, h in zip((-1, 1), hands or [None, None]):
            if h:
                sx, sy = cx + side * bw * 0.46, top + bh * 0.62
                mx, my = (sx + h[0]) / 2, max(sy, h[1]) + 14 * s
                self.line([(sx, sy), (mx, my), h], BLACK, 4.2 * s)
        return top

    def save(self, path):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
               f'<style>@font-face{{font-family:Caveat;font-weight:600;src:url(data:font/woff2;base64,{self.font}) format("woff2")}}</style>'
               f'<rect width="{W}" height="{H}" fill="#fff"/>{"".join(self.items)}</svg>')
        open(path, "w").write(svg)
