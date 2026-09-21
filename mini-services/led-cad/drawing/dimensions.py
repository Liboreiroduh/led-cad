"""Cotas automáticas: política paramétrica por vista (esboço estrutural).

TODAS as cotas são derivadas do ProjectModel e das coordenadas reais
(preset, edições manuais ou IA): se a geometria muda, a cota muda.
A prancha é um esboço GEOMÉTRICO para a empresa de estrutura — aqui não
existe perfil, material, peso, custo ou quantidade de peças; apenas a
posição e as dimensões (mm) de barras, postes, chapas, bases e gaiola.

Política:
- Cada vista ortográfica recebe a sua matriz mínima: cadeia local
  (vãos/afastamentos) no nível mais próximo, totais nos níveis externos.
- Vista isométrica fica limpa: as cotas completas pertencem às ortográficas.
- Níveis de cota são calculados a partir das constantes de texto/seta
  (nada de números mágicos) e afastados automaticamente quando uma nova
  linha ameaça colidir com outra já lançada no mesmo lado.
- Valor repetido não é cotado de novo na mesma folha/orientação: se o
  envelope coincide com a gaiola, a cota duplicada é descartada.
- Cadeia com muitos pontos vira apenas o total (sem nuvem ilegível).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from models.element import Element, ProjectModel
from drawing.projections import View2D

COTA_LAYER = "cota"
ARROW = 26.0   # comprimento da seta (mm)
TXT_H = 30.0   # altura do texto de cota (mm)

# ---- níveis derivados das constantes de texto (sem números mágicos) ----
_FIRST_LEVEL = 3.0 * TXT_H    # 1ª linha de cota a partir do contorno
_LEVEL_STEP = 2.4 * TXT_H     # afastamento entre níveis de cota
_MIN_SEP = 1.3 * TXT_H        # separação mínima entre linhas no mesmo lado
_MAX_CHAIN = 8                # acima disso a cadeia vira só o total

# sinal de projeção por vista (espelha u/v exatamente como _proj):
# TRASEIRA observa em -X (u = -x); INFERIOR observa em -Z (v = -y).
_SIGNS: Dict[str, Tuple[float, float]] = {
    "FRONTAL": (1.0, 1.0),
    "TRASEIRA": (-1.0, 1.0),
    "LATERAL": (1.0, 1.0),
    "SUPERIOR": (1.0, 1.0),
    "INFERIOR": (1.0, -1.0),
}

# eixos (u, v) de cada vista — espelha exatamente projections._proj
_VIEW_AXES: Dict[str, Tuple[int, int]] = {
    "FRONTAL": (0, 2),    # u = ±x, v = ±z
    "TRASEIRA": (0, 2),
    "LATERAL": (1, 2),    # u = ±y, v = ±z
    "SUPERIOR": (0, 1),   # u = ±x, v = ±y
    "INFERIOR": (0, 1),
}


def _vproj(view: str, p3: Tuple[float, float, float]) -> Tuple[float, float]:
    """Projeta um ponto 3D nos (u, v) da vista — MESMA matemática de
    drawing.projections._proj (mantida em sincronia via _SIGNS/_VIEW_AXES)."""
    u_ax, v_ax = _VIEW_AXES[view]
    su, sv = _SIGNS[view]
    return (su * p3[u_ax], sv * p3[v_ax])


def _tick(v: View2D, p: Tuple[float, float], direction: int = 1) -> None:
    """Seta de cota (duas linhas em 'V')."""
    a = 0.55 * ARROW
    v.add_line((p[0] - a, p[1] - a * direction * 0.55), (p[0], p[1]), w=0.45, layer=COTA_LAYER)
    v.add_line((p[0] - a, p[1] + a * direction * 0.55), (p[0], p[1]), w=0.45, layer=COTA_LAYER)


def _fmt(mm: float) -> str:
    return f"{mm:.0f}"


def hdim(v: View2D, base_v: float, line_v: float, u0: float, u1: float,
         ext_from: Optional[float] = None, text: Optional[str] = None,
         inside: bool = True) -> None:
    """Cota horizontal entre u0..u1 na altura line_v (v da vista)."""
    ef = base_v if ext_from is None else ext_from
    for u in (u0, u1):
        if abs(ef - line_v) > 1:
            v.add_line((u, ef), (u, line_v + (6 if ef > line_v else -6)), w=0.35, layer=COTA_LAYER)
    if inside:
        v.add_line((u0, line_v), (u1, line_v), w=0.45, layer=COTA_LAYER)
        _tick(v, (u0, line_v), +1)
        _tick(v, (u1, line_v), -1)
        mid = ((u0 + u1) / 2, line_v + TXT_H * 0.7)
    else:
        gap = 30.0
        v.add_line((u0, line_v), (u0 - gap, line_v), w=0.45, layer=COTA_LAYER)
        v.add_line((u1, line_v), (u1 + gap, line_v), w=0.45, layer=COTA_LAYER)
        _tick(v, (u0, line_v), +1)
        _tick(v, (u1, line_v), -1)
        mid = ((u0 + u1) / 2, line_v + TXT_H * 0.7)
    v.add_text(mid, TXT_H, text or _fmt(abs(u1 - u0)), layer=COTA_LAYER, color="#b45309")


def vdim(v: View2D, base_u: float, line_u: float, v0: float, v1: float,
         ext_from: Optional[float] = None, text: Optional[str] = None) -> None:
    """Cota vertical entre v0..v1 na posição line_u."""
    ef = base_u if ext_from is None else ext_from
    for w in (v0, v1):
        if abs(ef - line_u) > 1:
            v.add_line((ef, w), (line_u + (6 if ef > line_u else -6), w), w=0.35, layer=COTA_LAYER)
    v.add_line((line_u, v0), (line_u, v1), w=0.45, layer=COTA_LAYER)
    _tick(v, (line_u, v0), +1)
    _tick(v, (line_u, v1), -1)
    mid = (line_u - TXT_H * 0.55, (v0 + v1) / 2)
    t = text or _fmt(abs(v1 - v0))
    v.add_text(mid, TXT_H, t, layer=COTA_LAYER, rot=90, color="#b45309")


def _vertical_zs(model: ProjectModel) -> Tuple[float, float]:
    """Z inferior e superior do quadro (dos verticais do QUADRO).
    Desenho LIVRE (IA) não tem grupo QUADRO: cai para o envelope de TODAS
    as barras — as cotas continuam funcionando em qualquer esboço."""
    zs = [z for e in model.elements
          if e.type == "beam" and e.group == "QUADRO" and e.role == "vertical"
          and e.start and e.end for z in (e.start.z, e.end.z)]
    if not zs:
        zs = [z for e in model.elements if e.type == "beam"
              and e.start and e.end for z in (e.start.z, e.end.z)]
    return (min(zs), max(zs)) if zs else (0.0, 0.0)


def _frame_xs(model: ProjectModel) -> List[float]:
    """X dos verticais do QUADRO (desenho livre: todas as barras)."""
    xs = [e.start.x for e in model.elements
          if e.type == "beam" and e.group == "QUADRO" and e.role == "vertical"]
    if not xs:
        xs = [x for e in model.elements if e.type == "beam"
              and e.start and e.end for x in (e.start.x, e.end.x)]
    return xs


def _beams(model: ProjectModel) -> List[Element]:
    return [e for e in model.elements if e.type == "beam" and e.start and e.end]


def _posts(model: ProjectModel) -> List[Element]:
    return [e for e in _beams(model) if e.role == "post"]


def _base_plates(model: ProjectModel) -> List[Element]:
    return [e for e in model.elements
            if e.type == "plate" and e.center is not None and e.role == "base"]


def e_size(el: Element, axis: int) -> float:
    return (el.size_x, el.size_y, el.size_z)[axis]


def _plate_span(el: Element, axis: int) -> Tuple[float, float]:
    c = el.center.as_tuple()[axis]
    half = e_size(el, axis) / 2.0
    return (c - half, c + half)


def _axis_env(model: ProjectModel, axis: int, only_beams: bool = False) \
        -> Optional[Tuple[float, float]]:
    """min/max do eixo (0=X, 1=Y, 2=Z) sobre barras (+ chapas). Pinos
    (chumbadores) ficam fora: descem abaixo do solo e não são estrutura."""
    lo: Optional[float] = None
    hi: Optional[float] = None
    for e in model.elements:
        if e.type == "beam" and e.start and e.end:
            vals = (getattr(e.start, "xyz"[axis]), getattr(e.end, "xyz"[axis]))
        elif e.type == "plate" and e.center is not None and not only_beams:
            c = e.center.as_tuple()[axis]
            vals = (c - e_size(e, axis) / 2.0, c + e_size(e, axis) / 2.0)
        else:
            continue
        lo = min(vals) if lo is None else min(lo, min(vals))
        hi = max(vals) if hi is None else max(hi, max(vals))
    return (lo, hi) if lo is not None else None


def _unique_sorted(vals: Sequence[float], tol: float = 1.0) -> List[float]:
    out: List[float] = []
    for v in sorted(vals):
        if not out or abs(v - out[-1]) > tol:
            out.append(v)
    return out


def _distinct_base_spans(model: ProjectModel, axis: int) -> List[Tuple[float, float]]:
    """Span (lo, hi) das chapas de base no eixo — um por tamanho distinto."""
    out: List[Tuple[float, float]] = []
    sizes: set = set()
    for pl in _base_plates(model):
        key = int(round(e_size(pl, axis)))
        if key in sizes:
            continue
        sizes.add(key)
        out.append(_plate_span(pl, axis))
    return out


class _V:
    """Estado de cotagem de uma vista: dedupe de valores + níveis sem colisão.

    A caixa do DESENHO é capturada na criação (antes das cotas) para que os
    níveis sejam medidos sempre a partir do contorno, não de outra cota.
    """

    def __init__(self, v: View2D):
        self.view = v
        b = v.box
        self.v_lo, self.v_hi = b.min[1], b.max[1]
        self.u_lo, self.u_hi = b.min[0], b.max[0]
        self.vals: Dict[str, set] = {"h": set(), "v": set()}
        self.h_lines: List[float] = []   # linhas de cota horizontais lançadas
        self.v_lines: List[float] = []   # linhas de cota verticais lançadas
        self.h_spans: List[Tuple[float, float]] = []  # extensões cotadas (u)
        self.v_spans: List[Tuple[float, float]] = []  # extensões cotadas (v)

    @staticmethod
    def _alloc(used: List[float], want: float, direction: float) -> float:
        """Posição livre: afasta para o nível externo até não colidir."""
        pos = want
        for _ in range(24):
            if all(abs(pos - q) >= _MIN_SEP for q in used):
                break
            pos += direction * _MIN_SEP
        used.append(pos)
        return pos

    def h(self, u0: float, u1: float, side: str = "bottom", level: int = 0,
          value: Optional[float] = None, force: bool = False) -> None:
        val = int(round(value if value is not None else abs(u1 - u0)))
        if val <= 0 or (not force and val in self.vals["h"]):
            return
        self.vals["h"].add(val)
        base = self.v_lo if side == "bottom" else self.v_hi
        d = -1.0 if side == "bottom" else 1.0
        line_v = self._alloc(self.h_lines,
                             base + d * (_FIRST_LEVEL + level * _LEVEL_STEP), d)
        hdim(self.view, base, line_v, u0, u1)
        self.h_spans.append((min(u0, u1), max(u0, u1)))

    def vd(self, w0: float, w1: float, side: str = "left", level: int = 0,
          value: Optional[float] = None, force: bool = False) -> None:
        val = int(round(value if value is not None else abs(w1 - w0)))
        if val <= 0 or (not force and val in self.vals["v"]):
            return
        self.vals["v"].add(val)
        base = self.u_lo if side == "left" else self.u_hi
        d = -1.0 if side == "left" else 1.0
        line_u = self._alloc(self.v_lines,
                             base + d * (_FIRST_LEVEL + level * _LEVEL_STEP), d)
        vdim(self.view, base, line_u, w0, w1)
        self.v_spans.append((min(w0, w1), max(w0, w1)))


def _chain_and_totals_h(D: _V, coords: List[float], su: float,
                        model: ProjectModel, axis: int) -> None:
    """Cadeia inferior de afastamentos + totais (gaiola e envelope)."""
    if len(coords) < 2:
        return
    us = sorted(su * c for c in coords)
    if len(us) <= _MAX_CHAIN:
        for a, bb in zip(us, us[1:]):
            D.h(a, bb, "bottom", force=True)       # cadeia dos vãos
    D.h(us[0], us[-1], "bottom", level=1)          # vão total do quadro
    env = _axis_env(model, axis, only_beams=True)
    if env:
        bu = sorted(su * c for c in env)
        D.h(bu[0], bu[1], "bottom", level=2)       # gaiola (todas as barras)
    env = _axis_env(model, axis)
    if env:
        eu = sorted(su * c for c in env)
        D.h(eu[0], eu[1], "bottom", level=3)       # envelope com chapas


def _elevation_heights(D: _V, model: ProjectModel, sv: float) -> None:
    """Alturas de elevação: gaiola -> vão livre -> total (esquerda);
    alturas de poste (degraus viram níveis externos) à direita."""
    z0, z1 = _vertical_zs(model)
    D.vd(sv * z0, sv * z1, "left", level=0)             # altura da gaiola
    clearance = model.installation.ground_clearance
    if clearance > 1:
        D.vd(sv * 0.0, sv * z0, "left", level=1)        # vão livre ao apoio
    ez = _axis_env(model, 2)
    if ez:
        D.vd(sv * ez[0], sv * ez[1], "left", level=2)   # altura total
    heights: Dict[int, Tuple[float, float]] = {}
    for p in _posts(model):
        key = int(round(p.end.z - p.start.z))
        heights.setdefault(key, (p.start.z, p.end.z))
    for k, (h_mm, (za, zb)) in enumerate(sorted(heights.items())):
        D.vd(sv * za, sv * zb, "right", level=k, value=float(h_mm))


def _covered(spans: List[Tuple[float, float]], a: float, b: float,
             tol: float = 1.0) -> bool:
    """A extensão [a, b] já está explicitada por alguma cota lançada?"""
    lo, hi = min(a, b), max(a, b)
    return any(abs(lo - s0) <= tol and abs(hi - s1) <= tol for s0, s1 in spans)


def _canonical_view(el: Element) -> str:
    """Vista ortográfica em que o comprimento da barra é legível SEM
    ambiguidade. Cada barra recebe UMA vista canônica (nunca a mesma medida
    repetida em três folhas): vertical/X/XZ → FRONTAL; travessa Y e diagonal
    YZ → LATERAL; diagonal de planta (XY) → SUPERIOR."""
    dx = abs(el.end.x - el.start.x)
    dy = abs(el.end.y - el.start.y)
    dz = abs(el.end.z - el.start.z)
    if dz >= dx and dz >= dy:                 # tem altura dominante
        return "FRONTAL" if dx >= dy else "LATERAL"
    if dz < 1.0 and dy > 1.0 and dx > 1.0:    # diagonal no plano XY (planta)
        return "SUPERIOR"
    if dy > dx:                               # dominante em profundidade
        return "SUPERIOR" if dx > 1.0 else "LATERAL"
    return "FRONTAL"                          # horizontal em X


def _bar_dimensions(D: "_V", model: ProjectModel, view: str) -> None:
    """Cota de COMPRIMENTO de cada barra/linha estrutural visível na vista.

    - Valor sempre derivado dos pontos reais start/end (nunca inventado);
      para diagonais 3D o valor é o comprimento REAL (a projeção serve de
      linha de chamada).
    - Barras com a mesma projeção (colineares sobrepostas nesta vista) são
      agrupadas em UMA cota; o que a cadeia/total já explicita não é
      repetido; vertical com altura já cotada não é repetido.
    - Linha de cota alinhada à barra, afastada do contorno; o lado e o
      nível são escolhidos para não colidir com textos já lançados.
    """
    v = D.view
    cx, cy = (D.u_lo + D.u_hi) / 2.0, (D.v_lo + D.v_hi) / 2.0
    seen: set = set()                         # barras já representadas nesta vista
    txt_pts: List[Tuple[float, float]] = []   # textos de barra já lançados

    for el in _beams(model):
        if _canonical_view(el) != view:
            continue
        p0 = _vproj(view, el.start.as_tuple())
        p1 = _vproj(view, el.end.as_tuple())
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        ln = math.hypot(dx, dy)
        if ln < 2.0 * ARROW:                  # perpendicular/residual: cotada
            continue                          # na vista em que aparece
        a, b = (p0, p1) if (p0, p1) <= (p1, p0) else (p1, p0)
        key = (round(a[0] / 5.0), round(a[1] / 5.0),
               round(b[0] / 5.0), round(b[1] / 5.0))
        if key in seen:
            continue                          # mesma barra projetada de novo
        # já explicitada pelas cotas gerais? (cadeia, total, gaiola, alturas)
        if abs(dy) < 1.0:                     # horizontal na vista
            if _covered(D.h_spans, p0[0], p1[0]):
                continue
        elif abs(dx) < 1.0:                   # vertical na vista
            h_val = int(round(el.length()))
            if h_val in D.vals["v"] or _covered(D.v_spans, p0[1], p1[1]):
                continue
        seen.add(key)

        val = _fmt(el.length())               # comprimento REAL 3D (mm)
        nx, ny = -dy / ln, dx / ln
        mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
        if nx * (mx - cx) + ny * (my - cy) < 0:   # normal p/ fora do desenho
            nx, ny = -nx, -ny

        # escolhe (nível, lado) sem colidir com os textos de barra já lançados
        off = _FIRST_LEVEL
        for k in range(4):
            base_off = _FIRST_LEVEL + k * _LEVEL_STEP
            for s in (1.0, -1.0):
                cand = (mx + nx * s * (base_off + TXT_H * 0.7),
                        my + ny * s * (base_off + TXT_H * 0.7))
                if all(abs(cand[0] - t[0]) + abs(cand[1] - t[1]) >= 2.4 * TXT_H
                       for t in txt_pts):
                    off = s * base_off
                    break
                off = s * base_off
            else:
                continue
            break

        q0 = (p0[0] + nx * off, p0[1] + ny * off)
        q1 = (p1[0] + nx * off, p1[1] + ny * off)
        v.add_line(p0, q0, w=0.35, layer=COTA_LAYER)
        v.add_line(p1, q1, w=0.35, layer=COTA_LAYER)
        v.add_line(q0, q1, w=0.45, layer=COTA_LAYER)
        _tick(v, q0, +1)
        _tick(v, q1, -1)
        ang = math.degrees(math.atan2(dy * (1 if off > 0 else -1), dx))
        if ang > 90.0:
            ang -= 180.0
        elif ang < -90.0:
            ang += 180.0
        t_pt = (mx + nx * (off + (TXT_H * 0.7 if off > 0 else -TXT_H * 0.1)),
                my + ny * (off + (TXT_H * 0.7 if off > 0 else -TXT_H * 0.1)))
        v.add_text(t_pt, TXT_H, val, layer=COTA_LAYER, rot=ang, color="#b45309")
        txt_pts.append(t_pt)


def add_dimensions(model: ProjectModel, v: View2D, view: str) -> None:
    """Anexa as cotas da matriz mínima à vista (sempre da geometria real)."""
    if view == "ISOMETRICA" or view not in _SIGNS:
        return  # isométrica limpa: cotas completas pertencem às ortográficas
    if not v.box.valid:
        return
    su, sv = _SIGNS[view]
    D = _V(v)

    if view in ("FRONTAL", "TRASEIRA", "LATERAL"):
        axis = 1 if view == "LATERAL" else 0
        if axis == 1:
            coords = _unique_sorted([w for e in _beams(model)
                                     for w in (e.start.y, e.end.y)])
        else:
            coords = _unique_sorted(_frame_xs(model))
        _chain_and_totals_h(D, coords, su, model, axis)
        _elevation_heights(D, model, sv)
        # profundidade em planta das bases (na lateral, Y é horizontal)
        if view == "LATERAL":
            for a, bb in _distinct_base_spans(model, 1):
                D.h(a, bb, "top", value=bb - a)

    elif view in ("SUPERIOR", "INFERIOR"):
        # horizontal da vista = X (postes); vertical = ±Y (travessas)
        xs = _unique_sorted([p.start.x for p in _posts(model)]) \
            or _unique_sorted(_frame_xs(model))
        _chain_and_totals_h(D, xs, su, model, 0)
        ys = _unique_sorted([w for e in _beams(model)
                             for w in (e.start.y, e.end.y)])
        if len(ys) >= 2:
            ws = sorted(sv * c for c in ys)
            if len(ws) <= _MAX_CHAIN:
                for a, bb in zip(ws, ws[1:]):
                    D.vd(a, bb, "right", force=True)    # afastamentos em Y
            D.vd(ws[0], ws[-1], "right", level=1)       # profundidade do quadro
        env = _axis_env(model, 1, only_beams=True)
        if env:
            wu = sorted(sv * c for c in env)
            D.vd(wu[0], wu[1], "right", level=2)        # profundidade da gaiola
        env = _axis_env(model, 1)
        if env:
            wu = sorted(sv * c for c in env)
            D.vd(wu[0], wu[1], "right", level=3)        # profundidade do envelope
        # bases em planta: largura (topo) × profundidade (esquerda)
        for a, bb in _distinct_base_spans(model, 0):
            D.h(a, bb, "top", value=bb - a)
        for a0, bb0 in _distinct_base_spans(model, 1):
            a, bb = sorted((sv * a0, sv * bb0))
            D.vd(a, bb, "left", value=bb - a)

    # comprimento de cada barra/segmento (uma vista canônica por barra;
    # roda DEPOIS das cotas gerais para não repetir o que já está explícito)
    _bar_dimensions(D, model, view)


def view_title(v: View2D, y_offset: Optional[float] = None) -> None:
    """Título sublinhado abaixo da vista (padrão prancha)."""
    b = v.box
    if not b.valid:
        return
    if y_offset is None:
        # abaixo do último nível de cota (cadeia + totais + texto), sem colidir
        y_offset = -(2.0 * _FIRST_LEVEL + 2.0 * _LEVEL_STEP + 2.2 * TXT_H)
    cx = (b.min[0] + b.max[0]) / 2
    y = b.min[1] + y_offset
    v.add_text((cx, y), 44, v.name, layer="texto")
    half = len(v.name) * 12
    v.add_line((cx - half, y - 36), (cx + half, y - 36), w=0.5, layer="texto")
