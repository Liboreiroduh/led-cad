"""Plano de corte (cut list): agrupa barras por perfil + comprimento e
calcula barras comerciais necessárias via First-Fit-Decreasing.

Saída pensada para a serralheria:
  - peças por perfil (quantidade × comprimento),
  - barras comerciais de 6.000 mm e sobra por barra,
  - metros totais por perfil (compra).

100% Python — parte do core.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List

from models.element import ProjectModel
from models.profile import get_profile

BAR_LEN_MM = 6000.0   # barra comercial padrão
STOCK_LENGTHS_MM = (4000.0, 6000.0, 8000.0, 12000.0)  # barras comerciais comuns
SAW_KERF_MM = 3.0     # perda de corte por seção (serra fita)


def normalize_bar_len(bar_len_mm: float | None) -> float:
    """Aceita apenas barras comerciais conhecidas (evita plano irreal)."""
    if bar_len_mm is None:
        return BAR_LEN_MM
    try:
        v = float(bar_len_mm)
    except (TypeError, ValueError):
        return BAR_LEN_MM
    for s in STOCK_LENGTHS_MM:
        if abs(v - s) < 1.0:
            return s
    return BAR_LEN_MM


def _pack_bars(lengths: List[float], bar_len: float = BAR_LEN_MM,
               kerf: float = SAW_KERF_MM) -> List[List[float]]:
    """First-Fit-Decreasing: retorna barras com as peças de cada uma."""
    bars: List[List[float]] = []
    for ln in sorted(lengths, reverse=True):
        for bar in bars:
            used = sum(bar) + kerf * len(bar)
            if used + kerf + ln <= bar_len + 1e-6:
                bar.append(ln)
                break
        else:
            bars.append([ln])
    return bars


def build_cutlist(model: ProjectModel, bar_len_mm: float | None = None) -> Dict[str, Any]:
    """Plano de corte p/ o comprimento de barra comercial escolhido
    (4 m / 6 m / 8 m / 12 m — default 6 m)."""
    bar_len = normalize_bar_len(bar_len_mm)
    groups: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "label": "", "pieces": defaultdict(int), "total_mm": 0.0, "count": 0})

    for el in model.elements:
        if el.type != "beam" or not el.profile:
            continue
        prof = get_profile(el.profile)
        g = groups[prof.name]
        g["label"] = prof.label
        g["count"] += 1
        ln = math.ceil(el.length())  # sempre arredonda p/ cima (corte real)
        g["pieces"][ln] += 1
        g["total_mm"] += ln

    out_groups: List[Dict[str, Any]] = []
    total_bars = 0
    for name in sorted(groups):
        g = groups[name]
        pieces = [{"len_mm": int(ln), "qty": q}
                  for ln, q in sorted(g["pieces"].items(), reverse=True)]
        lengths = []
        for ln, q in g["pieces"].items():
            lengths.extend([ln] * q)
        bars = _pack_bars(lengths, bar_len)
        total_bars += len(bars)
        used_mm = sum(sum(b) for b in bars) + SAW_KERF_MM * max(0, len(lengths) - len(bars))
        bar_mm_total = len(bars) * bar_len
        out_groups.append({
            "profile": name,
            "label": g["label"],
            "pieces": pieces,
            "piece_count": g["count"],
            "total_m": round(g["total_mm"] / 1000.0, 2),
            "bars": len(bars),
            "bars_used_mm": round(bar_mm_total, 0),
            "waste_pct": round(100.0 * (1 - used_mm / bar_mm_total), 1) if bar_mm_total else 0.0,
            "bar_plan": [
                {"pieces": [int(x) for x in bar],
                 "rest_mm": int(bar_len - sum(bar) - SAW_KERF_MM * (len(bar) - 1))}
                for bar in bars[:12]  # mostra até 12 barras por perfil
            ],
        })

    return {
        "groups": out_groups,
        "bar_len_mm": int(bar_len),
        "saw_kerf_mm": SAW_KERF_MM,
        "total_bars": total_bars,
    }
