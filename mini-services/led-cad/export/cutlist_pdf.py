"""PDF do plano de corte (reportlab) — folha de serralheria A4 paisagem.

Renderiza o cutlist do motor Python (core/cutlist.py, FFD) como documento
imprimível: cabeçalho com projeto/data/comprimento de barra, strip de
resumo (barras, peças, metros, sobra média) e UM CARD POR PERFIL com a
sequência de barras — cada barra desenhada como régua horizontal com os
cortes proporcionais (teal alternado) e a sobra em cinza.

Segue o mesmo idioma visual da prancha técnica (export/pdf.py) e do
comparativo (export/diff_pdf.py).

ATENÇÃO: o canvas é escalado para MM (c.scale(mm, mm)) — todos os
tamanhos de fonte são em MILÍMETROS (como na prancha A2), não em pt.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

PAGE_W, PAGE_H = 297.0, 210.0  # A4 paisagem em mm
M = 12.0

INK = HexColor("#1f2937")
GREY = HexColor("#6b7280")
FAINT = HexColor("#9ca3af")
ACCENT = HexColor("#0f766e")
ACCENT_DARK = HexColor("#0d5f59")
ACCENT_MID = HexColor("#14b8a6")
ACCENT_SOFT = HexColor("#99f6e4")
ACCENT_BG = HexColor("#f0fdfa")
AMBER = HexColor("#b45309")
AMBER_BG = HexColor("#fffbeb")
REST = HexColor("#e5e7eb")
LIGHT = HexColor("#f3f4f6")
LINE = HexColor("#d1d5db")

# alternância de cor dos cortes dentro da barra (distingue peças vizinhas)
SEG_COLORS = [HexColor("#0f766e"), HexColor("#14b8a6"),
              HexColor("#0d9488"), HexColor("#115e59")]

BAR_H = 4.6       # altura da régua de barra (mm)
BAR_GAP = 3.2     # espaço entre barras


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _num(v: float, dec: int = 1) -> str:
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


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


def _chip(c, x, y, label, bg, fg) -> float:
    """Chip arredondado; retorna a largura para encadear chips."""
    w = 3.4 + 1.2 * len(label)
    c.setFillColor(bg)
    c.setStrokeColor(bg)
    c.roundRect(x, y - 1.0, w, 3.2, 1.0, stroke=0, fill=1)
    _text(c, x + w / 2, y, label, size=2.2, color=fg, bold=True, anchor="center")
    return w


def _stat_box(c, x, y, w, h, label, value, sub="", accent=ACCENT) -> None:
    c.setFillColor(HexColor("#ffffff"))
    c.setStrokeColor(LINE)
    c.setLineWidth(0.3)
    c.roundRect(x, y, w, h, 2.0, stroke=1, fill=1)
    c.setFillColor(accent)
    c.rect(x, y, 1.4, h, stroke=0, fill=1)
    _text(c, x + 3.4, y + h - 3.2, label.upper(), size=2.1, color=GREY, bold=True)
    _text(c, x + 3.4, y + h - 7.6, value, size=4.6, color=INK, bold=True)
    if sub:
        _text(c, x + 3.4, y + 1.8, sub, size=2.0, color=FAINT)


def draw_bar_ruler(c, x, y, w, pieces: List[int], bar_len: int, kerf: float) -> None:
    """Régua horizontal de UMA barra: cortes proporcionais (teal alternado),
    separadores finos brancos (representam o corte da serra) e sobra cinza."""
    c.setFillColor(REST)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.25)
    c.roundRect(x, y, w, BAR_H, 0.9, stroke=1, fill=1)
    cx = x
    for i, plen in enumerate(pieces):
        seg_w = max(0.6, w * (plen / bar_len))
        c.setFillColor(SEG_COLORS[i % len(SEG_COLORS)])
        c.rect(cx, y, seg_w, BAR_H, stroke=0, fill=1)
        if i > 0:  # linha do corte de serra
            c.setFillColor(HexColor("#ffffff"))
            c.rect(cx - 0.18, y, 0.36, BAR_H, stroke=0, fill=1)
        cx += seg_w
    # contorno por cima dos segmentos
    c.setStrokeColor(LINE)
    c.setLineWidth(0.25)
    c.roundRect(x, y, w, BAR_H, 0.9, stroke=1, fill=0)


def build_cutlist_pdf(cl: Dict[str, Any], project_name: str = "",
                      preset_id: str = "") -> bytes:
    """Recebe o dict de build_cutlist() e devolve o PDF em bytes."""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W * mm, PAGE_H * mm))
    c.scale(mm, mm)
    c.setTitle("Plano de corte — LED STRUCTURE CAD")

    bar_len = int(cl.get("bar_len_mm", 6000))
    bar_m = bar_len // 1000
    kerf = float(cl.get("saw_kerf_mm", 3.0))
    groups: List[Dict[str, Any]] = cl.get("groups", [])

    total_bars = int(cl.get("total_bars", 0))
    total_pieces = sum(g.get("piece_count", 0) for g in groups)
    total_m = sum(g.get("total_m", 0.0) for g in groups)
    avg_waste = (sum(g.get("waste_pct", 0.0) for g in groups) / len(groups)) if groups else 0.0

    # ---------------------------------------------------------- cabeçalho
    y_top = PAGE_H - M
    _text(c, M, y_top - 4.4, "PLANO DE CORTE — SERRALHERIA", size=5.6, color=INK, bold=True)
    _text(c, M, y_top - 8.2, "LED STRUCTURE CAD · sequência de corte por First-Fit-Decreasing (motor Python)",
          size=2.5, color=GREY)
    sub2 = f"Projeto: {project_name or '—'}"
    if preset_id:
        sub2 += f"  ·  preset {preset_id}"
    _text(c, M, y_top - 11.2, sub2, size=2.4, color=GREY)
    x_chip = PAGE_W - M
    for label, bg, fg in ((f"BARRA COMERCIAL {bar_m} m", ACCENT, HexColor("#ffffff")),
                          (f"PERDA DE SERRA {_num(kerf, 0)} mm", AMBER_BG, AMBER)):
        wch = 3.4 + 1.2 * len(label)
        x_chip -= wch
        _chip(c, x_chip, y_top - 4.0, label, bg, fg)
        x_chip -= 2.2
    _line(c, M, y_top - 13.4, PAGE_W - M, y_top - 13.4, w=0.5, color=LINE)

    # ---------------------------------------------------------- resumo
    sy = y_top - 15.2
    bw = (PAGE_W - 2 * M - 3 * 3.0) / 4.0
    bh = 11.4
    _stat_box(c, M, sy - bh, bw, bh, "Barras a comprar",
              f"{total_bars} × {bar_m} m", f"{total_bars * bar_m} m de barra comercial")
    _stat_box(c, M + (bw + 3.0), sy - bh, bw, bh, "Peças a cortar",
              f"{total_pieces}", "todas com comprimento arredondado p/ cima")
    _stat_box(c, M + 2 * (bw + 3.0), sy - bh, bw, bh, "Perfil bruto",
              f"{_num(total_m)} m", "soma dos comprimentos das peças")
    _stat_box(c, M + 3 * (bw + 3.0), sy - bh, bw, bh, "Sobra média",
              f"{_num(avg_waste)} %", f"aproveitamento {_num(100 - avg_waste)} %")

    # ---------------------------------------------------------- cards por perfil
    y = sy - bh - 6.0
    viz_x = M + 30.0                       # início da régua
    viz_w = PAGE_W - M - 26.0 - viz_x      # largura da régua

    def _page_header():
        nonlocal y
        y = y_top - 4.4
        _text(c, M, y, "PLANO DE CORTE — continuação", size=4.0, color=INK, bold=True)
        _line(c, M, y - 2.2, PAGE_W - M, y - 2.2, w=0.4, color=LINE)
        y -= 5.6

    for gi, g in enumerate(groups):
        shown = g.get("bar_plan", [])[:8]
        extra = len(g.get("bar_plan", [])) - len(shown)
        note_h = 3.0 if extra > 0 else 0.0
        card_h = 8.6 + len(shown) * (BAR_H + BAR_GAP) + note_h + 3.0
        if y - card_h < M + 8.0:
            c.showPage()
            c.scale(mm, mm)
            _page_header()
        # moldura do card
        c.setFillColor(HexColor("#ffffff"))
        c.setStrokeColor(LINE)
        c.setLineWidth(0.3)
        c.roundRect(M, y - card_h, PAGE_W - 2 * M, card_h, 2.0, stroke=1, fill=1)
        c.setFillColor(ACCENT)
        c.rect(M, y - card_h, 1.4, card_h, stroke=0, fill=1)
        # cabeçalho do perfil + chips
        ty = y - 4.6
        _text(c, M + 4.0, ty, g.get("label", g.get("profile", "")), size=3.3, color=INK, bold=True)
        cx = M + 4.0
        # mede o rótulo p/ posicionar os chips depois dele
        c.setFont("Helvetica-Bold", 3.3)
        cx += c.stringWidth(g.get("label", ""), "Helvetica-Bold", 3.3) + 3.0
        g_bars = g.get("bars", 0)
        chips = [(f"{g.get('piece_count', 0)} pçs", LIGHT, INK),
                 (f"{_num(g.get('total_m', 0), 2)} m", LIGHT, INK),
                 (f"{g_bars} {'barra' if g_bars == 1 else 'barras'} {bar_m} m", ACCENT_BG, ACCENT_DARK),
                 (f"sobra {_num(g.get('waste_pct'), 1)} %",
                  AMBER_BG if g.get("waste_pct", 0) > 25 else ACCENT_BG,
                  AMBER if g.get("waste_pct", 0) > 25 else ACCENT_DARK)]
        for label, bg, fg in chips:
            cx += _chip(c, cx, ty, label, bg, fg) + 1.6
        # linha de peças
        pieces_txt = " · ".join(f"{p['len_mm']}×{p['qty']}" for p in g.get("pieces", []))
        _text(c, M + 4.0, ty - 3.4, f"Peças: {pieces_txt}", size=2.3, color=GREY)
        # barras (régua por barra)
        by = ty - 6.2
        for bi, bar in enumerate(shown):
            row_y = by - BAR_H
            _text(c, M + 4.0, row_y + BAR_H / 2 - 0.8, f"Barra {bi + 1}",
                  size=2.3, color=INK, bold=True)
            draw_bar_ruler(c, viz_x, row_y, viz_w, bar.get("pieces", []), bar_len, kerf)
            rest = int(bar.get("rest_mm", 0))
            rest_pct = int(round(100.0 * rest / bar_len))
            _text(c, viz_x + viz_w + 2.2, row_y + BAR_H / 2 - 0.8,
                  f"sobra {rest} mm ({rest_pct}%)", size=2.2,
                  color=AMBER if rest_pct > 25 else GREY)
            by = row_y - BAR_GAP
        if extra > 0:
            _text(c, viz_x, by + 0.7,
                  f"+ {extra} {'barra segue' if extra == 1 else 'barras seguem'} o mesmo empacotamento FFD (veja o CSV completo).",
                  size=2.2, color=FAINT)
        y -= card_h + 3.4

    # ---------------------------------------------------------- rodapé
    if y < M + 10.0:
        c.showPage()
        c.scale(mm, mm)
        y = y_top - 4.4
    _line(c, M, M + 7.4, PAGE_W - M, M + 7.4, w=0.4, color=LINE)
    _text(c, M, M + 4.6,
          f"Corte calculado por First-Fit-Decreasing no motor Python — barra comercial de {bar_len} mm "
          f"com perda de serra de {_num(kerf, 0)} mm por corte. Sobras em cinza; cada cor alterna para "
          "distinguir peças vizinhas (o número exato de cada corte está no CSV do plano).",
          size=2.2, color=GREY)
    _text(c, M, M + 1.6,
          "Confira as medidas antes de cortar — documento gerado automaticamente somente para orçamento/fabricação auxiliar.",
          size=2.2, color=AMBER, bold=True)
    _text(c, PAGE_W - M, M + 1.6, f"{date.today().strftime('%d/%m/%Y')} · LED STRUCTURE CAD",
          size=2.2, color=FAINT, anchor="right")

    c.save()
    return buf.getvalue()
