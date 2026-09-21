"""Sparkline de evolução do projeto (SVG 100% gerado em Python).

Desenha um mini-gráfico de linha com DUAS séries — peso total (kg) e
custo estimado (R$) — ao longo das versões arquivadas de um projeto.
É servido como imagem (`/api/projects/{pid}/versions/spark.svg`) e
exibido dentro do painel de versões do frontend.

Design: eixo duplo normalizado (cada série usa sua própria escala),
área com gradiente sob a série de custo, pontos marcados, rótulos da
primeira/última versão e legenda compacta. Sem dependências externas —
apenas construção manual de strings SVG (mesma abordagem de drawing/svg).
"""
from __future__ import annotations

from typing import Any, Dict, List

W, H = 300.0, 86.0          # tamanho do SVG em px (CSS do painel controla o resto)
PAD_L, PAD_R, PAD_T, PAD_B = 34.0, 10.0, 14.0, 16.0

INK = "#92400e"             # âmbar escuro (tema do painel de versões)
COST = "#b45309"            # laranja — custo
MASS = "#0f766e"            # teal — peso
GRID = "#fde68a"            # grade sutil (âmbar claro)
MUTED = "#a16207"


def _fmt_brl(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _fmt_kg(v: float) -> str:
    return f"{v:,.1f} kg".replace(",", "X").replace(".", ",").replace("X", ".")


def _poly_points(values: List[float], vmin: float, vmax: float) -> List[tuple[float, float]]:
    n = len(values)
    span = (vmax - vmin) or 1.0
    x0, x1 = PAD_L, W - PAD_R
    y0, y1 = H - PAD_B, PAD_T
    pts = []
    for i, v in enumerate(values):
        x = x0 if n == 1 else x0 + (x1 - x0) * i / (n - 1)
        y = y0 - (y0 - y1) * ((v - vmin) / span)
        pts.append((round(x, 1), round(y, 1)))
    return pts


def _series_path(pts: List[tuple[float, float]]) -> str:
    return " ".join(f"{x},{y}" for x, y in pts)


def versions_spark_svg(versions: List[Dict[str, Any]]) -> str:
    """SVG do gráfico de evolução a partir dos metadados das versões
    (cada item precisa de v, mass_kg, cost_brl — saída de read_versions)."""
    pts_data = [(v.get("v", i + 1),
                 float(v.get("mass_kg") or 0.0),
                 float(v.get("cost_brl") or 0.0))
                for i, v in enumerate(versions)]
    if not pts_data:
        return ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 86' width='300' height='86'>"
                "<text x='150' y='46' text-anchor='middle' font-size='9' fill='#a16207' "
                "font-family='system-ui'>salve versões para ver a evolução</text></svg>")

    masses = [p[1] for p in pts_data]
    costs = [p[2] for p in pts_data]

    def _bounds(vals: List[float]) -> tuple[float, float]:
        lo, hi = min(vals), max(vals)
        if abs(hi - lo) < 1e-9:
            lo, hi = lo * 0.95 - 1.0, hi * 1.05 + 1.0  # série "reta" ganha faixa
        pad = (hi - lo) * 0.12
        return lo - pad, hi + pad

    m_lo, m_hi = _bounds(masses)
    c_lo, c_hi = _bounds(costs)
    pts_m = _poly_points(masses, m_lo, m_hi)
    pts_c = _poly_points(costs, c_lo, c_hi)

    parts: List[str] = []
    parts.append(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W:.0f} {H:.0f}' "
                 f"width='{W:.0f}' height='{H:.0f}' role='img' "
                 f"aria-label='Evolução de peso e custo por versão'>")
    parts.append("<defs><linearGradient id='sg' x1='0' y1='0' x2='0' y2='1'>"
                 "<stop offset='0' stop-color='#f59e0b' stop-opacity='.28'/>"
                 "<stop offset='1' stop-color='#f59e0b' stop-opacity='.02'/>"
                 "</linearGradient></defs>")

    # grade horizontal (3 linhas)
    for frac in (0.0, 0.5, 1.0):
        y = (H - PAD_B) - (H - PAD_B - PAD_T) * frac
        parts.append(f"<line x1='{PAD_L}' y1='{y:.1f}' x2='{W - PAD_R}' y2='{y:.1f}' "
                     f"stroke='{GRID}' stroke-width='1' stroke-dasharray='2 3'/>")

    # área sob a série de custo (destaque do orçamento)
    first, last = pts_c[0], pts_c[-1]
    parts.append(f"<polygon points='{PAD_L},{H - PAD_B:.1f} {_series_path(pts_c)} "
                 f"{last[0]},{H - PAD_B:.1f}' fill='url(#sg)' stroke='none'/>")

    # séries
    parts.append(f"<polyline points='{_series_path(pts_m)}' fill='none' stroke='{MASS}' "
                 f"stroke-width='1.8' stroke-linejoin='round' stroke-linecap='round'/>")
    parts.append(f"<polyline points='{_series_path(pts_c)}' fill='none' stroke='{COST}' "
                 f"stroke-width='1.8' stroke-linejoin='round' stroke-linecap='round'/>")

    # pontos + tooltip nativo (title)
    for (vx, _, _), (x, y), m, c in zip(pts_data, pts_m, masses, costs):
        parts.append(f"<circle cx='{x}' cy='{y}' r='2.4' fill='#fff' stroke='{MASS}' stroke-width='1.4'>"
                     f"<title>v{vx} — {_fmt_kg(m)}</title></circle>")
    for (vx, _, _), (x, y), m, c in zip(pts_data, pts_c, masses, costs):
        parts.append(f"<circle cx='{x}' cy='{y}' r='2.4' fill='#fff' stroke='{COST}' stroke-width='1.4'>"
                     f"<title>v{vx} — {_fmt_brl(c)}</title></circle>")

    # destaque no último ponto (estado mais recente)
    lx, ly = pts_c[-1]
    parts.append(f"<circle cx='{lx}' cy='{ly}' r='3.6' fill='{COST}' fill-opacity='.25' stroke='none'/>")

    # rótulos de versão (primeira e última)
    v_first, v_last = pts_data[0][0], pts_data[-1][0]
    parts.append(f"<text x='{PAD_L}' y='{H - 4}' font-size='7.5' fill='{MUTED}' font-family='ui-monospace,monospace'>v{v_first}</text>")
    parts.append(f"<text x='{W - PAD_R}' y='{H - 4}' font-size='7.5' fill='{MUTED}' text-anchor='end' "
                 f"font-family='ui-monospace,monospace'>v{v_last}</text>")

    # legenda compacta
    parts.append(f"<g font-size='7.5' font-family='system-ui' fill='{INK}'>"
                 f"<rect x='{PAD_L}' y='2' width='7' height='2.6' rx='1.3' fill='{MASS}'/>"
                 f"<text x='{PAD_L + 10}' y='6.4'>peso</text>"
                 f"<rect x='{PAD_L + 42}' y='2' width='7' height='2.6' rx='1.3' fill='{COST}'/>"
                 f"<text x='{PAD_L + 52}' y='6.4'>custo</text>"
                 f"<text x='{W - PAD_R}' y='6.4' text-anchor='end' font-weight='700'>{_fmt_brl(costs[-1])}</text>"
                 f"</g>")

    # mini-eixo esquerdo: valor máximo de PESO (topo) dá a escala da série teal
    parts.append(f"<text x='{PAD_L - 3}' y='{PAD_T + 3:.1f}' font-size='6.4' fill='{MASS}' "
                 f"text-anchor='end' font-family='ui-monospace,monospace'>{round(max(masses))} kg</text>")
    parts.append("</svg>")
    return "".join(parts)
