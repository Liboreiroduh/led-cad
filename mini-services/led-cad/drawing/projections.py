"""Projeções ortográficas: geram vistas 2D a partir da MESMA geometria 3D.

Nenhuma vista é desenhada à mão: todas são projeções reais do modelo.
Sistema de primitivas compartilhado entre SVG (navegador) e PDF (prancha).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from core.geometry import AABB
from models.element import Element, ProjectModel
from models.profile import get_profile

# primitivas (todas em mm, coordenadas da vista; v cresce para CIMA)
# line:   {k:"line", a:(u,v), b:(u,v), w:espessura, layer, dash}
# circle: {k:"circle", c:(u,v), r, w, layer, fill}
# text:   {k:"text", p:(u,v), s:altura_mm, t:texto, layer, anchor, rot, color}
Prim = dict

LAYERS = {
    "perfil": "#374151",       # estrutura
    "perfil2": "#6b7280",      # secundária
    "poste": "#1f2937",
    "chapa": "#4b5563",
    "hachura": "#a1a1aa",      # hachura 45° das chapas (vistas de plano)
    "painel": "#9ca3af",
    "cota": "#b45309",
    "texto": "#111827",
    "label": "#0f766e",
    "eixo": "#d4d4d8",
}


@dataclass
class View2D:
    name: str
    prims: List[Prim] = field(default_factory=list)
    box: AABB = field(default_factory=AABB)

    def add_line(self, a: Tuple[float, float], b: Tuple[float, float], w: float = 1.0,
                 layer: str = "perfil", dash: Optional[str] = None) -> None:
        self.prims.append({"k": "line", "a": a, "b": b, "w": w, "layer": layer, "dash": dash})
        self.box.add_points([a, b])

    def add_circle(self, c: Tuple[float, float], r: float, w: float = 1.0,
                   layer: str = "perfil") -> None:
        self.prims.append({"k": "circle", "c": c, "r": r, "w": w, "layer": layer})
        self.box.add_points([(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)])

    def add_text(self, p: Tuple[float, float], s: float, t: str, layer: str = "texto",
                 anchor: str = "middle", rot: float = 0.0, color: str = "") -> None:
        self.prims.append({"k": "text", "p": p, "s": s, "t": t, "layer": layer,
                           "anchor": anchor, "rot": rot, "color": color})
        # A caixa de escala da vista precisa incluir os TEXTOS (cotas, rótulos
        # e títulos), senão eles são cortados na borda da folha.
        w = max(len(t) * 0.62 * s, s)
        if abs(rot % 180.0) == 90.0:          # texto na vertical
            dx, dy = 1.2 * s, w
        else:
            dx, dy = w, 1.2 * s
        if anchor == "start":
            x0, x1 = p[0], p[0] + dx
        elif anchor == "end":
            x0, x1 = p[0] - dx, p[0]
        else:
            x0, x1 = p[0] - dx / 2.0, p[0] + dx / 2.0
        y0, y1 = p[1] - dy / 2.0, p[1] + dy / 2.0
        self.box.add_points([(x0, y0), (x1, y1)])

    def padded(self, pad: float = 250.0) -> AABB:
        if not self.box.valid:
            return AABB()
        b = AABB()
        b.add_points([
            (self.box.min[0] - pad, self.box.min[1] - pad),
            (self.box.max[0] + pad, self.box.max[1] + pad),
        ])
        return b


# ------------------------------------------------------------ projeções

def _proj(view: str, p: Tuple[float, float, float]) -> Tuple[float, float]:
    """Projeta ponto 3D (mm) para (u, v) da vista. v cresce para cima."""
    x, y, z = p
    if view == "FRONTAL":     # observador em +Y
        return (x, z)
    if view == "TRASEIRA":    # observador em -Y
        return (-x, z)
    if view == "LATERAL":     # observador em +X (vista lateral direita)
        return (y, z)
    if view == "SUPERIOR":    # observador em +Z
        return (x, y)
    if view == "INFERIOR":    # observador em -Z
        return (x, -y)
    if view == "ISOMETRICA":
        c30, s30 = math.cos(math.radians(30)), math.sin(math.radians(30))
        return ((x - y) * c30, z - (x + y) * s30 * 0.5 + (x + y) * 0.25)
    raise ValueError(f"Vista desconhecida: {view}")


def _thickness_mm(el: Element, view: str) -> float:
    """Espessura aparente da barra na vista (largura da seção)."""
    if el.profile:
        prof = get_profile(el.profile)
        return prof.w
    return 40.0


def add_beam_outline(v: View2D, a: Tuple[float, float], b: Tuple[float, float],
                     w: float, layer: str = "perfil") -> None:
    """Desenha a barra como CONTORNO (retângulo orientado), estilo CAD."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln * w / 2, dx / ln * w / 2
    p1 = (a[0] + nx, a[1] + ny)
    p2 = (b[0] + nx, b[1] + ny)
    p3 = (b[0] - nx, b[1] - ny)
    p4 = (a[0] - nx, a[1] - ny)
    for p, q in ((p1, p2), (p2, p3), (p3, p4), (p4, p1)):
        v.add_line(p, q, w=0.6, layer=layer)
    # linha de centro (eixo) da barra
    v.add_line(a, b, w=0.3, layer="eixo", dash="8,4")


def _plate_corners(el: Element) -> List[Tuple[float, float, float]]:
    assert el.center is not None
    cx, cy, cz = el.center.as_tuple()
    hx, hy, hz = el.size_x / 2, el.size_y / 2, el.size_z / 2
    out = []
    for dx in (-hx, hx):
        for dy in (-hy, hy):
            for dz in (-hz, hz):
                out.append((cx + dx, cy + dy, cz + dz))
    return out


def _panel_corners(model: ProjectModel) -> List[Tuple[float, float, float]]:
    p = model.panel
    c = model.installation.ground_clearance
    d = p.depth
    return [
        (-p.width / 2, d / 2, c + p.height), (p.width / 2, d / 2, c + p.height),
        (p.width / 2, d / 2, c), (-p.width / 2, d / 2, c),
    ]


def _draw_plate(v: View2D, el: Element, view: str) -> None:
    """Chapa como retângulo fechado + cruz de centro + hachura 45° em
    vistas de plano (SUPERIOR/INFERIOR) — padrão de prancha metálica."""
    corners = [_proj(view, p) for p in _plate_corners(el)]
    us, vs = [c[0] for c in corners], [c[1] for c in corners]
    u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
    rect = [((u0, v0), (u1, v0)), ((u1, v0), (u1, v1)),
            ((u1, v1), (u0, v1)), ((u0, v1), (u0, v0))]
    for p, q in rect:
        v.add_line(p, q, w=1.2, layer="chapa")
    w_rect, h_rect = u1 - u0, v1 - v0
    if min(w_rect, h_rect) > 30:  # cruz de centro (eixos)
        v.add_line(((u0 + u1) / 2, v0), ((u0 + u1) / 2, v1), w=0.3,
                   layer="eixo", dash="6,3")
        v.add_line((u0, (v0 + v1) / 2), (u1, (v0 + v1) / 2), w=0.3,
                   layer="eixo", dash="6,3")
    if view in ("SUPERIOR", "INFERIOR") and w_rect > 1 and h_rect > 1:
        spacing = max(30.0, min(w_rect, h_rect) / 8.0)
        span = w_rect + h_rect
        s = spacing
        while s < span:  # hachura 45° (família u+v = c), recortada no retângulo
            if s <= h_rect:
                enter = (u0, v0 + s)
            else:
                enter = (u0 + s - h_rect, v1)
            if s <= w_rect:
                exit_ = (u0 + s, v0)
            else:
                exit_ = (u1, v0 + s - w_rect)
            v.add_line(enter, exit_, w=0.25, layer="hachura")
            s += spacing


def project_view(model: ProjectModel, view: str, labels: bool = True) -> View2D:
    v = View2D(name=f"VISTA {view}" if view != "ISOMETRICA" else "PERSPECTIVA ISOMÉTRICA")
    panel_done = False

    for el in model.elements:
        if el.type == "panel":
            corners = [_proj(view, p) for p in _panel_corners(model)]
            us, vs = [c[0] for c in corners], [c[1] for c in corners]
            v.add_line((min(us), min(vs)), (max(us), max(vs)), w=0.5, layer="painel", dash="6,4")
            panel_done = True
            continue

        if el.type == "plate":
            _draw_plate(v, el, view)
            continue

        if el.type == "bolt":
            a, b = _proj(view, el.start.as_tuple()), _proj(view, el.end.as_tuple())
            if a == b:
                # pino perpendicular à vista (plano): marca a posição
                v.add_circle(a, 18.0, w=0.5, layer="chapa")
                v.add_line((a[0] - 26, a[1]), (a[0] + 26, a[1]), w=0.25,
                           layer="eixo")
                v.add_line((a[0], a[1] - 26), (a[0], a[1] + 26), w=0.25,
                           layer="eixo")
            else:
                v.add_line(a, b, w=0.5, layer="chapa", dash="4,3")
            continue

        if el.type == "beam" and el.start and el.end:
            a, b = _proj(view, el.start.as_tuple()), _proj(view, el.end.as_tuple())
            if a == b:
                # barra perpendicular à vista: mostra a seção
                prof = get_profile(el.profile) if el.profile else None
                r = (prof.w / 2) if prof else 25.0
                if prof and prof.kind == "round":
                    v.add_circle(a, r, w=0.9, layer="poste")
                    v.add_circle(a, r * 0.85, w=0.4, layer="poste")
                else:
                    v.add_line((a[0] - r, a[1] - r), (a[0] + r, a[1] + r), w=0.9, layer="perfil")
                continue
            w = _thickness_mm(el, view)
            layer = "poste" if el.role == "post" else ("perfil2" if el.role in ("trave", "diagonal") else "perfil")
            add_beam_outline(v, a, b, w, layer)

    if labels:
        _add_profile_labels(model, v, view)
        _add_element_labels(model, v, view)
    return v


def _add_profile_labels(model: ProjectModel, v: View2D, view: str) -> None:
    """Rótulos de perfil com linha de chamada (como na prancha de referência)."""
    if view not in ("FRONTAL", "LATERAL"):
        return
    top = v.box.max[1] if v.box.valid else 0

    def label_over(text: str, target: Tuple[float, float], dx: float, ly: float,
                   color: str = "label"):
        lx = target[0] + dx
        v.add_line((lx, ly - 14), target, w=0.4, layer="label")
        v.add_circle(target, 14, w=0.4, layer="label")
        v.add_text((lx, ly + 4), 26, text, layer="label", color=color)

    def mid_of(el: Element) -> Tuple[float, float]:
        return _proj(view, ((el.start.x + el.end.x) / 2, (el.start.y + el.end.y) / 2,
                            (el.start.z + el.end.z) / 2))

    def find(eid: str):
        return next((e for e in model.elements if e.id == eid), None)

    if view == "FRONTAL":
        el = find("V02")
        if el and el.start:
            prof = get_profile(el.profile)
            label_over(prof.label, mid_of(el), -300, top + 210)
        el = find("HS01")
        if el and el.start:
            prof = get_profile(el.profile)
            label_over(prof.label, (el.start.x / 2, el.start.z), 380, top + 330)
        el = find("HM01")
        if el and el.start:
            prof = get_profile(el.profile)
            label_over(prof.label, (el.end.x - 300, el.start.z), 320, top + 90)
    else:
        post = next((e for e in model.elements if e.role == "post"), None)
        if post and post.start and post.end:
            prof = get_profile(post.profile)
            label_over(prof.label, mid_of(post), -420, top + 260)
        el = find("TS01")
        if el and el.start:
            prof = get_profile(el.profile)
            label_over(prof.label, mid_of(el), 260, top + 90)


def _add_element_labels(model: ProjectModel, v: View2D, view: str) -> None:
    """Rótulos de ID dos elementos principais."""
    for el in model.elements:
        if el.type != "beam" or not el.start or not el.end:
            continue
        if view == "FRONTAL" and el.id in ("V01", "V03", "HS01", "HI01"):
            mid = _proj(view, ((el.start.x + el.end.x) / 2, el.start.y,
                               (el.start.z + el.end.z) / 2))
            v.add_text((mid[0] + 55, mid[1]), 24, el.id, layer="texto", anchor="start", color="#6b7280")
        if view == "LATERAL" and el.id == "POSTE-01":
            mid = _proj(view, (el.start.x, (el.start.y + el.end.y) / 2,
                               (el.start.z + el.end.z) / 2))
            v.add_text((mid[0] + 60, mid[1] - 60), 26, el.id, layer="texto", anchor="start")
        if view == "SUPERIOR" and el.id in ("TS01", "DS01"):
            mid = _proj(view, ((el.start.x + el.end.x) / 2, (el.start.y + el.end.y) / 2, el.start.z))
            v.add_text((mid[0], mid[1] + 45), 22, el.id, layer="texto", color="#6b7280")
