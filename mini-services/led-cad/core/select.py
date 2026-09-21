"""Seleção por retângulo (marquee) — a MATEMÁTICA fica no core Python.

O frontend captura o retângulo na tela e envia:
  - modo PLANAR: origem + base (right/up) + cantos u/v — p/ câmera orto;
  - modo FRUSTUM (padrão): origem (posição da câmera) + as 4 direções
    dos raios dos cantos do retângulo. Aqui montamos as 4 faces do
    tronco de pirâmide (cross entre raios vizinhos) e testamos o AABB
    de cada elemento contra as 4 semi-condições — interseção entra.

O Three.js só desenha — decisão de seleção é Python-first.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from models.element import Element, ProjectModel

Pt3 = Tuple[float, float, float]
CORNER_PAD_MM = 25.0  # meia-espessura típica p/ não exigir centro exato


def _cross(a: Pt3, b: Pt3) -> Pt3:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a: Pt3, b: Pt3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a: Pt3) -> Pt3:
    n = _dot(a, a) ** 0.5 or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def _element_corners(el: Element) -> List[Pt3]:
    """Cantos do AABB do elemento (barra, chapa ou pino)."""
    if el.type in ("beam", "bolt") and el.start and el.end:
        s, e = el.start.as_tuple(), el.end.as_tuple()
        p = CORNER_PAD_MM
        return [
            (min(s[0], e[0]) - p, min(s[1], e[1]) - p, min(s[2], e[2]) - p),
            (max(s[0], e[0]) + p, max(s[1], e[1]) + p, max(s[2], e[2]) + p),
        ]
    if el.type == "plate" and el.center:
        c = el.center.as_tuple()
        hx, hy, hz = el.size_x / 2, el.size_y / 2, el.size_z / 2
        return [(c[0] - hx, c[1] - hy, c[2] - hz),
                (c[0] + hx, c[1] + hy, c[2] + hz)]
    return []


def marquee_frustum(model: ProjectModel, origin: Pt3,
                    dirs: Sequence[Pt3]) -> Dict[str, Any]:
    """Retângulo → tronco de pirâmide (4 faces) → AABB overlap.

    dirs: 4 direções de raio (espaço do modelo) dos cantos do retângulo,
    em ordem: topo-esq, topo-dir, baixo-dir, baixo-esq.
    Um elemento entra se seu AABB intersecta TODAS as 4 semi-faces.
    """
    if len(dirs) != 4:
        return {"ids": [], "count": 0, "error": "dirs deve ter 4 direções"}
    d = [_norm(tuple(float(x) for x in v)) for v in dirs]
    center = _norm((d[0][0] + d[1][0] + d[2][0] + d[3][0],
                    d[0][1] + d[1][1] + d[2][1] + d[3][1],
                    d[0][2] + d[1][2] + d[2][2] + d[3][2]))
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    planes: List[Pt3] = []
    for a, b in edges:
        n = _norm(_cross(d[a], d[b]))
        if _dot(n, center) < 0:  # normal aponta PARA DENTRO do trapézio
            n = (-n[0], -n[1], -n[2])
        planes.append(n)

    ids: List[str] = []
    for el in model.elements:
        corners = _element_corners(el)
        if not corners:
            continue
        ok = True
        for n in planes:
            inside = max(_dot((c[0] - origin[0], c[1] - origin[1], c[2] - origin[2]), n)
                         for c in corners)
            if inside < 0:
                ok = False
                break
        # também exige estar à frente da câmera
        if ok and max(_dot((c[0] - origin[0], c[1] - origin[1], c[2] - origin[2]), center)
                      for c in corners) <= 0:
            ok = False
        if ok:
            ids.append(el.id)
    return {"ids": ids, "count": len(ids)}


def marquee_select(model: ProjectModel, origin: Pt3, right: Pt3, up: Pt3,
                   u0: float, v0: float, u1: float, v1: float) -> Dict[str, Any]:
    """Modo planar (câmera orto): projeta AABB na base (right, up)."""
    umin, umax = sorted((u0, u1))
    vmin, vmax = sorted((v0, v1))
    ids: List[str] = []
    for el in model.elements:
        corners = _element_corners(el)
        if not corners:
            continue
        us: List[float] = []
        vs: List[float] = []
        for c in corners:
            d = (c[0] - origin[0], c[1] - origin[1], c[2] - origin[2])
            us.append(_dot(d, right))
            vs.append(_dot(d, up))
        if max(us) >= umin and min(us) <= umax and max(vs) >= vmin and min(vs) <= vmax:
            ids.append(el.id)
    return {"ids": ids, "count": len(ids),
            "rect": {"u0": umin, "v0": vmin, "u1": umax, "v1": vmax}}
