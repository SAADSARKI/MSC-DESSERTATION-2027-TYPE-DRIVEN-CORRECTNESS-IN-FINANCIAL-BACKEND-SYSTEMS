"""Figures from the experiment results (standard library only; SVG output).

Reads results/results_<program>.csv and the source trees (through summarise.py)
and writes:

  results/figures/scenario_matrix.svg     detection stage of DS1-DS13 per configuration
  results/figures/operator_outcomes.svg   operator mutants by detection stage per configuration
  results/figures/enforcement_lines.svg   tagged enforcement lines per invariant and program

Every value in a figure is also in results/summary.md and the CSV files.
Each mark has an SVG <title>, shown as a tooltip when the file is opened in a browser.

Usage:  python3 plots.py
"""
from __future__ import annotations

import os
from collections import Counter, defaultdict
from html import escape

from mutate import PROGRAMS, SCENARIOS
from summarise import CONFIGS, INVARIANTS, RES, enforcement, load_rows, stage_of

OUT = os.path.join(RES, "figures")

# Palette: reference instance (light mode), categorical slots 1-3, which are
# validated for all pairs; chart chrome and ink from the same reference.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
NEUTRAL = "#e1e0d9"  # one step darker than the surface wash, so the swatch stays visible
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
CRITICAL = "#d03b3b"
# system-ui first; named fallbacks so Word and LibreOffice also pick a sans face.
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Liberation Sans", "DejaVu Sans", sans-serif'

# Detection stages: colour carries the stage, the cell text names it as well.
STAGE_STYLE = {
    "compile": (SERIES[0], "#ffffff", "Rejected by the compiler"),
    "mypy": (SERIES[1], "#ffffff", "Rejected by mypy --strict"),
    "test": (NEUTRAL, INK_2, "Revealed by testing"),
    "MISSED": (CRITICAL, "#ffffff", "Not caught"),
}
PROGRAM_LABEL = {"rust_typed": "Rust-Typed", "rust_plain": "Rust-Plain", "python": "Python"}
INVARIANT_LABEL = {"I1": "Balance limits", "I2": "Conservation", "I3": "Valid amount",
                   "I4": "Account identity", "I5": "Atomicity"}


# ----------------------------------------------------------------- SVG helpers
def text(x: float, y: float, s: str, size: int = 12, fill: str = INK, anchor: str = "start",
         weight: str = "normal") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{escape(s)}</text>')


def rect(x: float, y: float, w: float, h: float, fill: str, tip: str = "", rx: float = 0) -> str:
    t = f"<title>{escape(tip)}</title>" if tip else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}">{t}</rect>'


def column(x: float, base: float, w: float, h: float, fill: str, tip: str, r: float = 4) -> str:
    """Vertical bar: 4px rounded data-end at the top, square at the baseline."""
    r = min(r, h, w / 2)
    y = base - h
    d = (f"M{x:.1f},{base:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
         f"H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{base:.1f} Z")
    return f'<path d="{d}" fill="{fill}"><title>{escape(tip)}</title></path>'


def hbar_end(x: float, y: float, w: float, h: float, fill: str, tip: str, r: float = 4) -> str:
    """Horizontal segment with a 4px rounded data-end on the right."""
    r = min(r, w, h / 2)
    d = (f"M{x:.1f},{y:.1f} H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
         f"V{y + h - r:.1f} Q{x + w:.1f},{y + h:.1f} {x + w - r:.1f},{y + h:.1f} H{x:.1f} Z")
    return f'<path d="{d}" fill="{fill}"><title>{escape(tip)}</title></path>'


def swatch_legend(x: float, y: float, items: list[tuple[str, str]]) -> tuple[list[str], float]:
    """One row of colour swatch + text-ink label; returns elements and end x."""
    out = []
    for colour, label in items:
        out.append(rect(x, y - 9, 10, 10, colour, rx=2))
        out.append(text(x + 15, y, label, 12, INK_2))
        x += 15 + 7.0 * len(label) + 22
    return out, x


def svg(width: int, height: int, title: str, subtitle: str, body: list[str]) -> str:
    head = [text(24, 30, title, 15, INK, weight="600"), text(24, 50, subtitle, 12, INK_2)]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" font-family=\'{FONT}\'>\n'
            f'<title>{escape(title)}</title>\n'
            + rect(0, 0, width, height, SURFACE) + "\n" + "\n".join(head + body) + "\n</svg>\n")


def save(name: str, content: str) -> None:
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
    print("wrote", os.path.relpath(os.path.join(OUT, name), os.path.dirname(RES)))


# --------------------------------------------------------------------- figures
def scenario_matrix(rows: list[dict[str, str]]) -> str:
    grp: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        if r["kind"] == "scenario":
            grp[(r["operator"], r["configuration"])].append(r)
    label_w, cell_w, cell_h, gap = 300, 112, 26, 2
    x0, y0 = 24 + label_w, 112
    width = int(x0 + len(CONFIGS) * cell_w + 24)
    height = int(y0 + len(SCENARIOS) * cell_h + 40)
    body, _ = swatch_legend(24, 76, [(STAGE_STYLE[k][0], STAGE_STYLE[k][2]) for k in ("compile", "mypy", "test")])
    for j, c in enumerate(CONFIGS):
        body.append(text(x0 + j * cell_w + (cell_w - gap) / 2, y0 - 10, c, 12, INK_2, "middle", "600"))
    present: set[str] = set()
    for i, (ds, (title, inv, origin, _)) in enumerate(SCENARIOS.items()):
        y = y0 + i * cell_h
        mark = " *" if origin == "industrial" else ""
        body.append(text(24, y + cell_h / 2 + 4, f"{ds}  {title}{mark}", 12, INK))
        body.append(text(x0 - 10, y + cell_h / 2 + 4, inv.replace(",", ", "), 11, MUTED, "end"))
        for j, c in enumerate(CONFIGS):
            st = stage_of(grp[(ds, c)]) if grp.get((ds, c)) else "n/a"
            present.add(st)
            fill, ink, desc = STAGE_STYLE.get(st, (NEUTRAL, INK_2, st))
            cx = x0 + j * cell_w
            body.append(rect(cx, y, cell_w - gap, cell_h - gap, fill, f"{ds} {title} | {c}: {desc}"))
            body.append(text(cx + (cell_w - gap) / 2, y + cell_h / 2 + 3, st, 11, ink, "middle"))
    note = "* derived from the industrial reference system.  Rust: debug and release builds gave the same result."
    if "MISSED" in present:
        note = "Red: not caught by any test.  " + note
    body.append(text(24, height - 16, note, 11, MUTED))
    return svg(width, height, "Defect scenarios: detection stage",
               "Where each defect was first stopped, per configuration (invariant at right of each name)", body)


def operator_outcomes(rows: list[dict[str, str]]) -> str:
    cnt: Counter[tuple[str, str]] = Counter()
    for r in rows:
        if r["kind"] == "operator" and r["profile"] != "release":
            cnt[(r["configuration"], {"compile_time": "compile", "static_check": "mypy",
                                      "testing": "test", "not_caught": "MISSED"}[r["result"]])] += 1
    stages = ["compile", "mypy", "test", "MISSED"]
    totals = {c: sum(cnt[(c, s)] for s in stages) for c in CONFIGS}
    label_w, bar_h, row_h, plot_w = 130, 22, 46, 400
    x0, y0 = 24 + label_w, 108
    scale = plot_w / max(totals.values())
    width, height = int(x0 + plot_w + 230), int(y0 + len(CONFIGS) * row_h + 44)
    body, _ = swatch_legend(24, 76, [(STAGE_STYLE[k][0], STAGE_STYLE[k][2]) for k in ("compile", "mypy", "test")])
    for t in range(0, max(totals.values()) + 1, 10):                       # hairline grid + ticks
        gx = x0 + t * scale
        body.append(f'<line x1="{gx:.1f}" y1="{y0 - 8}" x2="{gx:.1f}" y2="{y0 + len(CONFIGS) * row_h - 16}" '
                    f'stroke="{GRID if t else AXIS}" stroke-width="1"/>')
        body.append(text(gx, y0 + len(CONFIGS) * row_h, str(t), 11, MUTED, "middle"))
    for i, c in enumerate(CONFIGS):
        y = y0 + i * row_h
        body.append(text(x0 - 12, y + bar_h / 2 + 4, c, 12, INK, "end"))
        x = x0
        segs = [(s, cnt[(c, s)]) for s in stages if cnt[(c, s)]]
        for k, (s, n) in enumerate(segs):
            w = n * scale - (2 if k < len(segs) - 1 else 0)                # 2px surface gap
            tip = f"{c}: {n} of {totals[c]} operator mutants {STAGE_STYLE[s][2].lower()}"
            if k == len(segs) - 1:
                body.append(hbar_end(x, y, w, bar_h, STAGE_STYLE[s][0], tip))
            else:
                body.append(rect(x, y, w, bar_h, STAGE_STYLE[s][0], tip))
            x += n * scale
        summary = "  ·  ".join(f"{n} {s}" for s, n in segs)
        body.append(text(x0 + totals[c] * scale + 10, y + bar_h / 2 + 4, f"{summary}   (of {totals[c]})", 12, INK_2))
    body.append(text(24, height - 14, "Number of operator mutants. Rust: debug build shown (release identical).",
                     11, MUTED))
    return svg(width, height, "Operator mutants: detection stage",
               "Seven mutation operators applied at every applicable site", body)


def enforcement_lines() -> str:
    data = {p: enforcement(p)[0] for p in PROGRAMS}
    progs = list(PROGRAMS)
    bar_w, gap, group_gap, plot_h = 24, 2, 40, 180
    group_w = len(progs) * bar_w + (len(progs) - 1) * gap
    x0, base = 64, 110 + plot_h
    top = max(v for d in data.values() for v in d.values())
    ymax = top + 1
    scale = plot_h / ymax
    width = int(x0 + len(INVARIANTS) * (group_w + group_gap) + 24)
    height = base + 70
    body, _ = swatch_legend(24, 76, [(SERIES[k], PROGRAM_LABEL[p]) for k, p in enumerate(progs)])
    for t in range(0, ymax + 1):                                           # hairline grid
        gy = base - t * scale
        body.append(f'<line x1="{x0 - 8}" y1="{gy:.1f}" x2="{width - 24}" y2="{gy:.1f}" '
                    f'stroke="{AXIS if t == 0 else GRID}" stroke-width="1"/>')
        body.append(text(x0 - 14, gy + 4, str(t), 11, MUTED, "end"))
    for g, inv in enumerate(INVARIANTS):
        gx = x0 + group_gap / 2 + g * (group_w + group_gap)
        for k, p in enumerate(progs):
            v = data[p].get(inv, 0)
            bx = gx + k * (bar_w + gap)
            tip = f"{PROGRAM_LABEL[p]}, {inv} {INVARIANT_LABEL[inv]}: {v} tagged line(s)"
            if v:
                body.append(column(bx, base, bar_w, v * scale, SERIES[k], tip))
            body.append(text(bx + bar_w / 2, base - v * scale - 5, str(v), 11, INK_2, "middle"))
        body.append(text(gx + group_w / 2, base + 18, inv, 12, INK, "middle", "600"))
        body.append(text(gx + group_w / 2, base + 33, INVARIANT_LABEL[inv], 11, INK_2, "middle"))
    body.append(text(24, height - 12, "Lines carrying an [ENF:Ix] tag (SPEC Section 5); a line tagged with two "
                     "invariants counts for both.", 11, MUTED))
    return svg(width, height, "Enforcement code per invariant",
               "Tagged enforcement lines in each implementation", body)


def main() -> None:
    rows = load_rows()
    save("scenario_matrix.svg", scenario_matrix(rows))
    save("operator_outcomes.svg", operator_outcomes(rows))
    save("enforcement_lines.svg", enforcement_lines())


if __name__ == "__main__":
    main()
