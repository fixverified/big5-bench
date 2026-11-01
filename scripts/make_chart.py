"""Build docs/results.html from the reported scores."""

TRAITS = ["Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism"]
MODELS = [
    ("gpt-6.1-sol", [3.16, 4.32, 2.69, 4.37, 1.43], "91%"),
    ("claude-opus-5", [4.10, 4.21, 3.25, 4.34, 1.83], "94%"),
    ("glm-5.3", [3.45, 4.06, 2.90, 4.00, 1.92], "36%"),
    ("grok-4.3", [3.27, 4.16, 3.08, 4.08, 1.39], "63%"),
]
HIGHLIGHT = "claude-opus-5"
STANDOUT_TRAIT = "Openness"

# Layout of the results grid, in CSS pixels.
W = 1496
HEAD_H, ROW_H, PASS_H = 78, 70, 78
H = HEAD_H + ROW_H * len(TRAITS) + PASS_H
PLOT_X, PLOT_W = 306, 500
COL_W = 166
COL_X = W - COL_W * len(MODELS)
DOT_R = 12


def scale_x(value):
    """Map a rating on the 1-5 scale to an x position in the plot."""
    return PLOT_X + PLOT_W * (value - 1) / 4


def col_center(index):
    return COL_X + COL_W * (index + 0.5)


def row_center(index):
    return HEAD_H + ROW_H * (index + 0.5)


def header():
    parts = []
    for tick in range(1, 6):
        cls = "tick mid-tick" if tick == 3 else "tick"
        parts.append(f'<text x="{scale_x(tick):.1f}" y="{HEAD_H - 16}" text-anchor="middle" class="{cls}">{tick}</text>')
    parts.append(f'<text x="{scale_x(3):.1f}" y="{HEAD_H - 48}" text-anchor="middle" class="mid-label">midpoint</text>')
    parts.append(f'<text x="0" y="{HEAD_H - 16}" class="axis-title">Self-rating, 1 to 5</text>')
    for m, (name, _, _) in enumerate(MODELS):
        cls = "model model-hi" if name == HIGHLIGHT else "model"
        parts.append(f'<text x="{col_center(m):.1f}" y="{HEAD_H - 16}" text-anchor="middle" class="{cls}">{name}</text>')
        dot_cls = "dot dot-hi" if name == HIGHLIGHT else "dot"
        parts.append(f'<circle cx="{col_center(m):.1f}" cy="{HEAD_H - 55}" r="{DOT_R - 2}" class="{dot_cls}"/>')
    return parts


def grid():
    parts = []
    bottom = HEAD_H + ROW_H * len(TRAITS)
    for tick in (1, 2, 4, 5):
        x = scale_x(tick)
        parts.append(f'<line x1="{x:.1f}" y1="{HEAD_H}" x2="{x:.1f}" y2="{bottom}" class="grid"/>')
    for r in range(len(TRAITS) + 1):
        y = HEAD_H + ROW_H * r
        cls = "rule-strong" if r in (0, len(TRAITS)) else "rule"
        parts.append(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" class="{cls}"/>')
    x = scale_x(3)
    parts.append(f'<line x1="{x:.1f}" y1="{HEAD_H}" x2="{x:.1f}" y2="{bottom}" class="midline"/>')
    return parts


def trait_row(r, trait):
    y = row_center(r)
    parts = [f'<text x="0" y="{y + 11}" class="trait">{trait}</text>']
    ordered = sorted(MODELS, key=lambda model: model[0] == HIGHLIGHT)  # highlighted model draws last
    for name, values, _ in ordered:
        cls = "dot dot-hi" if name == HIGHLIGHT else "dot"
        parts.append(f'<circle cx="{scale_x(values[r]):.2f}" cy="{y}" r="{DOT_R}" class="{cls}"/>')
    for m, (name, values, _) in enumerate(MODELS):
        x = col_center(m)
        standout = name == HIGHLIGHT and trait == STANDOUT_TRAIT
        if standout:
            parts.append(f'<rect x="{x - 62:.1f}" y="{y - 27}" width="124" height="54" rx="10" class="pill"/>')
            parts.append(
                f'<text x="{scale_x(values[r]) + DOT_R + 8:.1f}" y="{y + 8}" class="callout">Claude</text>'
            )
        cls = "val val-hi" if standout else "val"
        parts.append(f'<text x="{x:.1f}" y="{y + 13}" text-anchor="middle" class="{cls}">{values[r]:.2f}</text>')
    return parts


def pass_row():
    y = HEAD_H + ROW_H * len(TRAITS) + PASS_H / 2 + 6
    parts = [f'<text x="0" y="{y + 5}" class="trait">Same answer on all 3 passes</text>']
    for m, (_, _, same) in enumerate(MODELS):
        parts.append(f'<text x="{col_center(m):.1f}" y="{y + 7}" text-anchor="middle" class="val">{same}</text>')
    return parts


def results_svg():
    parts = header() + grid()
    for r, trait in enumerate(TRAITS):
        parts += trait_row(r, trait)
    parts += pass_row()
    label = "Self-ratings on a 1 to 5 scale for four models across five traits, with exact scores in a table."
    return f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">{"".join(parts)}</svg>'


STYLE = """
:root{--bg:#0C0F14;--line:#262D38;--line-strong:#4A5361;--ink:#F6F8FA;--muted:#B4BCC8;--accent:#46E0B5;--peer:#8B95A5}
*{box-sizing:border-box;margin:0}
html,body{overflow:hidden}
body{width:1600px;height:900px;background:var(--bg);color:var(--ink);font-family:-apple-system,"SF Pro Display","Helvetica Neue",Arial,sans-serif;padding:36px 52px 28px;display:flex;flex-direction:column;justify-content:space-between}
.eyebrow{color:var(--accent);font-size:24px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
h1{font-size:70px;line-height:1.04;font-weight:750;letter-spacing:-.026em;margin-top:8px}
.sub{font-size:31px;color:var(--muted);margin-top:12px;white-space:nowrap}
svg{display:block}
text{font-variant-numeric:tabular-nums}
.grid{stroke:var(--line);stroke-width:1}
.rule{stroke:var(--line);stroke-width:1}
.rule-strong{stroke:var(--line-strong);stroke-width:1.5}
.midline{stroke:var(--ink);stroke-width:2;stroke-dasharray:6 6}
.tick{fill:var(--muted);font-size:24px;font-weight:600}
.mid-tick{fill:var(--ink);font-weight:800}
.mid-label{fill:var(--ink);font-size:21px;font-weight:600}
.axis-title{fill:var(--muted);font-size:23px;font-weight:500}
.model{fill:var(--muted);font-size:24px;font-weight:700;letter-spacing:-.01em}
.model-hi{fill:var(--accent)}
.trait{fill:var(--ink);font-size:30px;font-weight:650;letter-spacing:-.012em}
.dot{fill:var(--peer);stroke:var(--bg);stroke-width:2.5}
.dot-hi{fill:var(--accent)}
.val{fill:var(--ink);font-size:36px;font-weight:700;letter-spacing:-.01em}
.val-hi{fill:#06231B;font-weight:800}
.pill{fill:var(--accent)}
.callout{fill:var(--accent);font-size:24px;font-weight:750}
footer{display:flex;justify-content:space-between;gap:40px;align-items:flex-end;font-size:22px;color:var(--muted);line-height:1.3}
.repo{color:var(--ink);font-weight:700;white-space:nowrap;font-size:28px;letter-spacing:-.01em}
"""

html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Big Five Bench</title><style>{STYLE}</style></head><body>
<header>
<div class="eyebrow">Big Five Bench</div>
<h1>Four AI models rated their<br>personalities almost the same</h1>
<div class="sub">High conscientiousness and agreeableness, low neuroticism. Only Claude stood out, on openness.</div>
</header>
{results_svg()}
<footer><div>Self-ratings from 1 to 5. 300 public-domain IPIP items, both scale directions,<br>3 passes, no persona. 7,200 answers.</div><div class="repo">github.com/fixverified/big5-bench</div></footer>
</body></html>"""
open("docs/results.html", "w").write(html)
