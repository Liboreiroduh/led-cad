"""Snap determinístico (seção 17) — a lógica vive no CORE Python.

O frontend envia um ponto 3D bruto (interseção do raio com o plano de
trabalho); este módulo aplica as prioridades:
  1. extremidades de barras existentes (raio ENDPOINT_MM);
  2. centros/miolo de barras existentes (raio CENTER_MM);
  3. aresta — ponto projetado sobre o eixo da barra (raio EDGE_MM),
     útil para ligar uma barra nova no MEIO de outra em qualquer posição;
  4. grade (GRID_MM).
Sempre retorna o ponto ajustado + qual regra venceu.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from models.element import ProjectModel

GRID_MM = 50.0
ENDPOINT_MM = 250.0      # raio de captura de extremidades
CENTER_MM = 180.0        # raio de captura de centros (ponto médio)
EDGE_MM = 120.0          # raio de captura do ponto projetado na aresta


def _project_on_segment(p: Tuple[float, float, float],
                        s: Tuple[float, float, float],
                        e: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Ponto mais próximo de p no segmento s→e (projeção com clamp)."""
    vx, vy, vz = e[0] - s[0], e[1] - s[1], e[2] - s[2]
    wx, wy, wz = p[0] - s[0], p[1] - s[1], p[2] - s[2]
    vv = vx * vx + vy * vy + vz * vz
    if vv < 1e-9:
        return s
    t = max(0.0, min(1.0, (wx * vx + wy * vy + wz * vz) / vv))
    return (s[0] + t * vx, s[1] + t * vy, s[2] + t * vz)


def snap_point(model: ProjectModel, point: Dict[str, float],
               want_grid: bool = True, want_endpoints: bool = True,
               want_centers: bool = True, want_edges: bool = True) -> Dict[str, Any]:
    px = float(point.get("x", 0))
    py = float(point.get("y", 0))
    pz = float(point.get("z", 0))

    best_rule = "free"
    best_el = ""
    best_d2 = float("inf")
    best = (px, py, pz)

    if want_endpoints or want_centers or want_edges:
        for el in model.elements:
            if el.type != "beam" or el.start is None or el.end is None:
                continue
            s = el.start.as_tuple()
            e = el.end.as_tuple()
            if want_endpoints:
                for q in (s, e):
                    d2 = (px - q[0]) ** 2 + (py - q[1]) ** 2 + (pz - q[2]) ** 2
                    if d2 <= ENDPOINT_MM ** 2 and d2 < best_d2:
                        best_d2, best, best_rule, best_el = d2, q, "endpoint", el.id
            if want_centers:
                c = ((s[0] + e[0]) / 2, (s[1] + e[1]) / 2, (s[2] + e[2]) / 2)
                d2 = (px - c[0]) ** 2 + (py - c[1]) ** 2 + (pz - c[2]) ** 2
                if d2 <= CENTER_MM ** 2 and d2 < best_d2:
                    best_d2, best, best_rule, best_el = d2, c, "center", el.id
            if want_edges:
                q = _project_on_segment((px, py, pz), s, e)
                d2 = (px - q[0]) ** 2 + (py - q[1]) ** 2 + (pz - q[2]) ** 2
                # só vale se NÃO estiver pertíssimo de extremidade/centro
                # (evita competir com as regras de maior prioridade)
                if d2 <= EDGE_MM ** 2 and d2 < best_d2 and best_rule not in ("endpoint", "center"):
                    best_d2, best, best_rule, best_el = d2, q, "edge", el.id

    if best_rule == "free" and want_grid:
        g = GRID_MM
        best = (round(px / g) * g, round(py / g) * g, round(pz / g) * g)
        best_rule = "grid"

    return {
        "point": {"x": best[0], "y": best[1], "z": best[2]},
        "rule": best_rule,
        "element_id": best_el or None,
    }
