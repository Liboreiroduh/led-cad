"""Renderizador SVG das vistas (etapa intermediária vetorial para o PDF)."""
from __future__ import annotations

import math
from typing import Tuple

from drawing.projections import LAYERS, View2D


def _esc(t: str) -> str:
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_svg(view: View2D, width_px: float = 640.0, height_px: float = 480.0,
               bg: str = "#ffffff", show_box: bool = False) -> str:
    """Renderiza a View2D em string SVG, ajustando a escala para caber."""
    b = view.padded(300)
    if not b.valid:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" height="{height_px}"></svg>'

    wmm = max(b.max[0] - b.min[0], 1)
    hmm = max(b.max[1] - b.min[1], 1)
    scale = min(width_px / wmm, height_px / hmm)

    def T(p: Tuple[float, float]) -> Tuple[float, float]:
        px = (p[0] - b.min[0]) * scale
        py = height_px - (p[1] - b.min[1]) * scale
        return (round(px, 2), round(py, 2))

    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px:.0f} {height_px:.0f}" '
        f'width="{width_px:.0f}" height="{height_px:.0f}" style="background:{bg}">')

    for prim in view.prims:
        k = prim["k"]
        color = prim.get("color") or LAYERS.get(prim.get("layer", "perfil"), "#374151")
        w_px = max(prim.get("w", 1.0) * scale, 0.4)
        dash = prim.get("dash")
        da = f' stroke-dasharray="{dash}"' if dash else ""
        if k == "line":
            (x1, y1), (x2, y2) = T(prim["a"]), T(prim["b"])
            out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                       f'stroke="{color}" stroke-width="{w_px:.2f}"{da} stroke-linecap="round"/>')
        elif k == "circle":
            (cx, cy), r = T(prim["c"]), prim["r"] * scale
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" '
                       f'stroke="{color}" stroke-width="{w_px:.2f}"{da}/>')
        elif k == "text":
            (tx, ty) = T(prim["p"])
            size_px = max(prim["s"] * scale, 5)
            anchor = prim.get("anchor", "middle")
            rot = prim.get("rot", 0)
            tr = f' transform="rotate({rot} {tx} {ty})"' if rot else ""
            out.append(f'<text x="{tx}" y="{ty}" font-size="{size_px:.1f}" fill="{color}" '
                       f'text-anchor="{anchor}" font-family="Arial, sans-serif"{tr}>{_esc(prim["t"])}</text>')

    out.append("</svg>")
    return "".join(out)
