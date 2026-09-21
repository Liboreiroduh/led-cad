"""PDF do comparativo de versões (reportlab) — página A4 paisagem.

Renderiza o resultado do diff de BOM (services/project_service) como um
documento imprimível: cabeçalho A ↔ B com datas e totais, cards de Δ
peso/custo, tabela de itens (+/−/alterados com valores antigos → novos)
e rodapé explicativo. Segue o mesmo idioma visual da prancha técnica
(export/pdf.py): tinta cinza-escuro, acento teal, tabelas com zebra.

ATENÇÃO: o canvas é escalado para MM (c.scale(mm, mm)) — todos os
tamanhos de fonte são em MILÍMETROS (como na prancha A2), não em pt.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

PAGE_W, PAGE_H = 297.0, 210.0  # A4 paisagem em mm
M = 12.0

INK = HexColor("#1f2937")
GREY = HexColor("#6b7280")
FAINT = HexColor("#9ca3af")
ACCENT = HexColor("#0f766e")
ACCENT_BG = HexColor("#f0fdfa")
AMBER = HexColor("#b45309")
AMBER_BG = HexColor("#fffbeb")
RED = HexColor("#b91c1c")
GREEN = HexColor("#15803d")
LIGHT = HexColor("#f3f4f6")
LINE = HexColor("#e5e7eb")


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _kg(v: float) -> str:
    return f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _line(c, x1, y1, x2, y2, w=0.25, color=INK, dash=None):
    c.setStrokeColor(color)
    c.setLineWidth(w)
    if dash:
        c.setDash(dash)
    c.line(x1, y1, x2, y2)
    if dash:
        c.setDash()


def _text(c, x, y, s, size=2.6, color=INK, bold=False, anchor="left"):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    if anchor == "center":
        c.drawCentredString(x, y, s)
    elif anchor == "right":
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)


def _chip(c, x, y, label, bg, fg) -> None:
    """Chip arredondado pequeno (+/−/Δquant) com texto centrado."""
    w = 3.2 + 1.15 * len(label)
    c.setFillColor(bg)
    c.setStrokeColor(bg)
    c.roundRect(x, y - 0.9, w, 3.0, 0.9, stroke=0, fill=1)
    _text(c, x + w / 2, y, label, size=2.2, color=fg, bold=True, anchor="center")


def build_diff_pdf(diff: Dict[str, Any]) -> bytes:
    """Recebe o dict de diff (diff_snapshots) e devolve o PDF em bytes."""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W * mm, PAGE_H * mm))
    c.scale(mm, mm)
    c.setTitle("Comparativo de versões — LED STRUCTURE CAD")

    T = diff.get("totals", {})
    added = diff.get("added", [])
    removed = diff.get("removed", [])
    changed = diff.get("changed", [])
    n_items = len(added) + len(removed) + len(changed)

    # ---------------- moldura ----------------
    _line(c, M, M, PAGE_W - M, M, w=0.7)
    _line(c, M, M, M, PAGE_H - M, w=0.7)
    _line(c, PAGE_W - M, M, PAGE_W - M, PAGE_H - M, w=0.7)
    _line(c, M, PAGE_H - M, PAGE_W - M, PAGE_H - M, w=0.7)

    # ---------------- cabeçalho ----------------
    y = PAGE_H - M - 7
    _text(c, M + 4, y, "COMPARATIVO DE VERSÕES — LISTA DE MATERIAIS", size=5.4, bold=True)
    _text(c, PAGE_W - M - 4, y, date.today().strftime("%d/%m/%Y"), size=3.6,
          color=GREY, anchor="right")
    _text(c, PAGE_W - M - 4, y - 3.6, "LED STRUCTURE CAD · motor Python",
          size=2.4, color=FAINT, anchor="right")
    _line(c, M + 4, y - 6, PAGE_W - M - 4, y - 6, w=0.4)

    # ---------------- cards A ↔ B ----------------
    ix = M + 4                      # x inicial útil
    iw = PAGE_W - 2 * M - 8         # largura útil total
    gap = 8.0
    card_w = (iw - gap) / 2
    cy, ch = y - 24, 18.0

    sides = (
        ("A", ix, AMBER_BG, AMBER, diff.get("name", "A"),
         diff.get("saved_at", "—"), diff.get("saved_elements", 0),
         T.get("saved", {}).get("mass_kg", 0), T.get("saved", {}).get("cost_brl", 0)),
        ("B", ix + card_w + gap, ACCENT_BG, ACCENT, diff.get("other_name", "projeto atual"),
         diff.get("other_saved_at", "—"), diff.get("current_elements", 0),
         T.get("current", {}).get("mass_kg", 0), T.get("current", {}).get("cost_brl", 0)),
    )
    for side, cx0, bg, fg, tag, saved, elems, mass, cost in sides:
        c.setFillColor(bg)
        c.setStrokeColor(LINE)
        c.roundRect(cx0, cy, card_w, ch, 2, stroke=1, fill=1)
        _text(c, cx0 + 3, cy + ch - 3.6, f"LADO {side}", size=2.2, color=GREY, bold=True)
        _text(c, cx0 + 3, cy + ch - 8.6, str(tag)[:46], size=4.0, bold=True)
        _text(c, cx0 + card_w - 3, cy + ch - 8.6,
              f"{_kg(mass)} kg", size=4.0, bold=True, color=fg, anchor="right")
        _text(c, cx0 + 3, cy + 2.8, f"{saved}  ·  {elems} elementos", size=2.5, color=GREY)
        _text(c, cx0 + card_w - 3, cy + 2.8, _brl(cost), size=3.4, bold=True,
              color=fg, anchor="right")

    # seta entre os cards
    mid_x = ix + card_w + gap / 2
    _text(c, mid_x, cy + ch / 2 - 1, "→", size=6, color=FAINT, bold=True, anchor="center")

    # ---------------- deltas ----------------
    dy = cy - 6
    dm = float(T.get("delta_mass_kg", 0))
    dc = float(T.get("delta_cost_brl", 0))
    _text(c, ix, dy, "Δ PESO:", size=3.0, color=GREY, bold=True)
    _text(c, ix + 15, dy, f"{'+' if dm >= 0 else '−'}{_kg(abs(dm))} kg",
          size=3.4, bold=True, color=(GREEN if dm < 0 else RED) if abs(dm) > 0.05 else GREY)
    _text(c, ix + 48, dy, "Δ CUSTO:", size=3.0, color=GREY, bold=True)
    _text(c, ix + 66, dy, f"{'+' if dc >= 0 else '−'}{_brl(abs(dc))}",
          size=3.4, bold=True, color=(RED if dc > 0 else GREEN) if abs(dc) > 0.5 else GREY)
    _text(c, ix + iw, dy,
          f"{n_items} itens · {len(added)} novos · {len(removed)} removidos · {len(changed)} alterados",
          size=2.8, color=GREY, anchor="right")

    # ---------------- tabela ----------------
    ty = dy - 6
    widths = [10, 92, 44, 46, 50, 17]          # total = 259 = iw (259)
    headers = ["", "ITEM", "QUANTIDADE", "PESO (kg)", "CUSTO (R$)", "Δ CUSTO"]
    x0 = ix

    c.setFillColor(LIGHT)
    c.rect(x0, ty - 5.2, sum(widths), 5.6, stroke=0, fill=1)
    cx = x0
    for wd, hd in zip(widths, headers):
        _text(c, cx + 1.6, ty - 3.4, hd, size=2.5, bold=True, color=GREY)
        cx += wd
    ty -= 5.6

    rows = ([("alt", it) for it in changed]
            + [("add", it) for it in added]
            + [("rem", it) for it in removed])

    max_rows = 26
    row_h = 5.0
    for i, (kind, it) in enumerate(rows[:max_rows]):
        if i % 2 == 1:
            c.setFillColor(HexColor("#fafafa"))
            c.rect(x0, ty - row_h + 1.4, sum(widths), row_h, stroke=0, fill=1)
        cx = x0
        # chip
        if kind == "add":
            _chip(c, cx + 1.6, ty - 3.1, "+", HexColor("#d1fae5"), GREEN)
        elif kind == "rem":
            _chip(c, cx + 1.6, ty - 3.1, "−", HexColor("#fee2e2"), RED)
        else:
            dq = float(it.get("delta_quant", 0))
            label = f"{'+' if dq > 0 else ''}{dq:g}" if abs(dq) > 1e-9 else "alt"
            _chip(c, cx + 1.6, ty - 3.1, label, HexColor("#fef3c7"), AMBER)
        cx += widths[0]
        _text(c, cx + 1.6, ty - 3.2, str(it.get("descr", ""))[:60], size=2.6, bold=True)
        cx += widths[1]
        if kind == "add":
            q = f"— → {it.get('quant', 0)}"
        elif kind == "rem":
            q = f"{it.get('quant', 0)} → —"
        else:
            q = f"{it['old'].get('quant', 0)} → {it['new'].get('quant', 0)}"
        _text(c, cx + 1.6, ty - 3.2, q, size=2.6)
        cx += widths[2]
        if kind == "add":
            p = f"— → {_kg(it.get('peso_total', 0))}"
        elif kind == "rem":
            p = f"{_kg(it.get('peso_total', 0))} → —"
        else:
            p = f"{_kg(it['old'].get('peso_total', 0))} → {_kg(it['new'].get('peso_total', 0))}"
        _text(c, cx + 1.6, ty - 3.2, p, size=2.6)
        cx += widths[3]
        if kind == "add":
            v = f"— → {_brl(it.get('custo_total', 0))}"
        elif kind == "rem":
            v = f"{_brl(it.get('custo_total', 0))} → —"
        else:
            v = f"{_brl(it['old'].get('custo_total', 0))} → {_brl(it['new'].get('custo_total', 0))}"
        _text(c, cx + 1.6, ty - 3.2, v, size=2.6)
        cx += widths[4]
        if kind == "add":
            dv, dcol = f"+{_brl(it.get('custo_total', 0))}", RED
        elif kind == "rem":
            dv, dcol = f"−{_brl(it.get('custo_total', 0))}", GREEN
        else:
            dcv = float(it.get("delta_custo", 0))
            dv = f"{'+' if dcv >= 0 else '−'}{_brl(abs(dcv))}"
            dcol = RED if dcv > 0 else GREEN
        _text(c, cx + widths[5] - 1.6, ty - 3.2, dv, size=2.6, bold=True,
              color=dcol, anchor="right")

        _line(c, x0, ty - row_h + 1.4, x0 + sum(widths), ty - row_h + 1.4, w=0.1, color=LINE)
        ty -= row_h

    if not rows:
        _text(c, x0 + sum(widths) / 2, ty - 8,
              "✓ Nenhuma diferença de materiais entre os dois lados.", size=3.6,
              color=GREEN, anchor="center")
        ty -= 12
    elif len(rows) > max_rows:
        _text(c, x0, ty - 3.5, f"… e mais {len(rows) - max_rows} itens (comparativo interativo na aplicação).",
              size=2.4, color=FAINT)
        ty -= 5

    # ---------------- rodapé ----------------
    fy = M + 8
    _line(c, M + 4, fy + 4.5, PAGE_W - M - 4, fy + 4.5, w=0.35)
    _text(c, M + 4, fy, "Comparação calculada no motor Python a partir dos snapshots da lista de "
          "materiais gravados a cada salvamento — pesos em kg, valores estimados apenas de MATERIAL "
          "(não incluem fundação, transporte, montagem nem impostos).", size=2.3, color=GREY)
    _text(c, PAGE_W - M - 4, fy - 3.6,
          f"A: {diff.get('saved_at', '—')}   ·   B: {diff.get('other_saved_at', '—')}",
          size=2.3, color=FAINT, anchor="right")

    c.showPage()
    c.save()
    return buf.getvalue()
