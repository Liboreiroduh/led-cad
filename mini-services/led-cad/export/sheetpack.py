"""P2 — Prancha técnica de fabricação (7 folhas) para serralheria.

Gera SVG e PDF vetoriais a partir de um snapshot do ProjectModel.
Template inspirado na referência LED EXPERT / LedCollor:
- folha A4 retrato (210×297 mm)
- faixa lateral de marca configurável
- carimbo inferior com unidade mm, revisão, folha N/07 e aviso de esboço
- cotas associativas derivadas do modelo (nunca texto inventado)

Folhas:
  01 - ELEVAÇÃO FACE LED (malha de gabinetes + cotas totais e por módulo)
  02 - ESTRUTURA TRASEIRA (gaiola + passarela + guarda-corpo)
  03 - VISTA LATERAL DIREITA
  04 - VISTA SUPERIOR
  05 - VISTA ISOMÉTRICA
  06 - DETALHES DE MONTAGEM (postes/gaiola/passarela)
  07 - LISTA DE MATERIAIS / NOTAS
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from drawing.projections import View2D, project_view
from models.element import ProjectModel


PAGE_W_MM = 210.0   # A4 retrato
PAGE_H_MM = 297.0
MARGIN = 8.0        # margem interna da moldura
BRAND_W = 20.0      # largura da faixa lateral de marca
STAMP_H = 26.0      # altura do carimbo inferior

INK = HexColor("#111827")
GREY = HexColor("#6b7280")
ACCENT = HexColor("#26313d")
COTA = HexColor("#b45309")
LIGHT = HexColor("#e5e7eb")
BRAND_BG = HexColor("#1b2530")
BRAND_FG = HexColor("#f9fafb")

SHEETS = [
    ("01", "ELEVAÇÃO FACE LED"),
    ("02", "ESTRUTURA TRASEIRA"),
    ("03", "VISTA LATERAL DIREITA"),
    ("04", "VISTA SUPERIOR"),
    ("05", "VISTA ISOMÉTRICA"),
    ("06", "DETALHES DE MONTAGEM"),
    ("07", "LISTA DE MATERIAIS / NOTAS"),
]


@dataclass
class SheetMeta:
    obra: str = ""
    cliente: str = ""
    marca: str = "LED STRUCTURE CAD"
    numero: str = "LC-2026-001"
    revisao: str = "A"
    unidade: str = "mm"
    data: str = ""
    aviso: str = ("ESBOÇO GEOMÉTRICO — REVISAR COM ENGENHEIRO RESPONSÁVEL "
                  "PELA CRIAÇÃO/VALIDAÇÃO ESTRUTURAL")

    def __post_init__(self) -> None:
        if not self.data:
            self.data = date.today().strftime("%d/%m/%Y")


def _line(c: rl_canvas.Canvas, x1: float, y1: float, x2: float, y2: float,
          w: float = 0.25, color=INK, dash: Optional[str] = None) -> None:
    c.setStrokeColor(color)
    c.setLineWidth(w)
    if dash:
        c.setDash([float(v) for v in dash.split(",")])
    c.line(x1, y1, x2, y2)
    if dash:
        c.setDash()


def _text(c: rl_canvas.Canvas, x: float, y: float, s: str, size: float = 2.6,
          color=INK, bold: bool = False, anchor: str = "left",
          rotate: float = 0.0) -> None:
    font = "Helvetica-Bold" if bold else "Helvetica"
    c.setFont(font, size)
    c.setFillColor(color)
    tw = c.stringWidth(s, font, size)
    if anchor == "center":
        x -= tw / 2.0
    elif anchor == "right":
        x -= tw
    if rotate:
        c.saveState()
        c.translate(x, y)
        c.rotate(rotate)
        c.drawString(0, 0, s)
        c.restoreState()
    else:
        c.drawString(x, y, s)


def _draw_frame(c: rl_canvas.Canvas, meta: SheetMeta, sheet_no: str,
                title: str) -> None:
    """Moldura + faixa lateral de marca + carimbo inferior."""
    pw, ph = PAGE_W_MM, PAGE_H_MM
    # moldura externa
    _line(c, MARGIN, MARGIN, pw - MARGIN, MARGIN, w=0.7)
    _line(c, MARGIN, MARGIN, MARGIN, ph - MARGIN, w=0.7)
    _line(c, pw - MARGIN, MARGIN, pw - MARGIN, ph - MARGIN, w=0.7)
    _line(c, MARGIN, ph - MARGIN, pw - MARGIN, ph - MARGIN, w=0.7)

    # faixa lateral esquerda (marca)
    bx = MARGIN
    by = MARGIN
    bw = BRAND_W
    bh = ph - 2 * MARGIN - STAMP_H
    c.setFillColor(BRAND_BG)
    c.rect(bx, by, bw, bh, fill=1, stroke=0)
    # texto vertical da marca
    c.saveState()
    c.translate(bx + bw / 2.0, by + bh / 2.0)
    c.rotate(90)
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(BRAND_FG)
    c.drawCentredString(0, 0, meta.marca.upper())
    c.restoreState()

    # carimbo inferior
    sx = MARGIN + BRAND_W
    sy = MARGIN
    sw = pw - 2 * MARGIN - BRAND_W
    sh = STAMP_H
    _line(c, sx, sy + sh, sx + sw, sy + sh, w=0.5)
    _line(c, sx, sy, sx, sy + sh, w=0.5)
    _line(c, sx + sw, sy, sx + sw, sy + sh, w=0.5)
    # divisões horizontais do carimbo
    for dy in (sh * 0.33, sh * 0.66):
        _line(c, sx, sy + dy, sx + sw, sy + dy, w=0.35)
    # divisão vertical no meio
    mid_x = sx + sw * 0.55
    _line(c, mid_x, sy, mid_x, sy + sh, w=0.35)

    # conteúdo do carimbo
    pad = 3.0
    left_x = sx + pad
    right_x = mid_x + pad
    top_y = sy + sh - pad

    _text(c, left_x, top_y - 4, meta.obra or "PAINEL LED", size=4.0, bold=True)
    _text(c, left_x, top_y - 10, f"Cliente: {meta.cliente}" if meta.cliente else "",
          size=2.8, color=GREY)
    _text(c, left_x, top_y - 16, f"Nº {meta.numero}", size=2.8)
    _text(c, left_x, top_y - 22, meta.aviso[:80], size=2.2, color=GREY)

    _text(c, right_x, top_y - 4, title, size=4.5, bold=True, color=ACCENT)
    _text(c, right_x, top_y - 11, f"Unidade: {meta.unidade}", size=2.8)
    _text(c, right_x, top_y - 17, f"Revisão: {meta.revisao}", size=2.8)
    _text(c, right_x, top_y - 23, f"Folha {sheet_no}/07 · {meta.data}",
          size=2.8, bold=True)


def _dim_h(c: rl_canvas.Canvas, x1: float, x2: float, y: float,
           label: str, offset: float = 8.0, size: float = 2.8) -> None:
    """Cota horizontal com linhas de chamada e setas."""
    yo = y + offset
    _line(c, x1, y, x1, yo + 3, w=0.18, color=COTA)
    _line(c, x2, y, x2, yo + 3, w=0.18, color=COTA)
    _line(c, x1, yo, x2, yo, w=0.25, color=COTA)
    # setas
    aw = 1.5
    _line(c, x1, yo, x1 + aw, yo + 0.6, w=0.2, color=COTA)
    _line(c, x1, yo, x1 + aw, yo - 0.6, w=0.2, color=COTA)
    _line(c, x2, yo, x2 - aw, yo + 0.6, w=0.2, color=COTA)
    _line(c, x2, yo, x2 - aw, yo - 0.6, w=0.2, color=COTA)
    _text(c, (x1 + x2) / 2.0, yo + 1.5, label, size=size,
          color=COTA, anchor="center")


def _dim_v(c: rl_canvas.Canvas, x: float, y1: float, y2: float,
           label: str, offset: float = 8.0, size: float = 2.8) -> None:
    """Cota vertical."""
    xo = x - offset
    _line(c, x, y1, xo - 3, y1, w=0.18, color=COTA)
    _line(c, x, y2, xo - 3, y2, w=0.18, color=COTA)
    _line(c, xo, y1, xo, y2, w=0.25, color=COTA)
    aw = 1.5
    _line(c, xo, y1, xo + 0.6, y1 + aw, w=0.2, color=COTA)
    _line(c, xo, y1, xo - 0.6, y1 + aw, w=0.2, color=COTA)
    _line(c, xo, y2, xo + 0.6, y2 - aw, w=0.2, color=COTA)
    _line(c, xo, y2, xo - 0.6, y2 - aw, w=0.2, color=COTA)
    _text(c, xo - 2, (y1 + y2) / 2.0, label, size=size,
          color=COTA, anchor="right", rotate=90)


def _render_view_into(c: rl_canvas.Canvas, view: View2D,
                      x: float, y: float, w: float, h: float,
                      pad_mm: float = 200.0) -> None:
    """Desenha uma View2D dentro do retângulo (x,y,w,h) em mm."""
    bounds = view.padded(pad_mm)
    dw = max(bounds.max[0] - bounds.min[0], 1.0)
    dh = max(bounds.max[1] - bounds.min[1], 1.0)
    scale = min(w / dw, h / dh)
    ox = x + (w - dw * scale) / 2.0 - bounds.min[0] * scale
    oy = y + (h - dh * scale) / 2.0 - bounds.min[1] * scale

    for p in view.prims:
        if p["k"] == "line":
            ax, ay = p["a"]
            bx, by = p["b"]
            lx1 = ox + ax * scale
            ly1 = oy + ay * scale
            lx2 = ox + bx * scale
            ly2 = oy + by * scale
            color = COTA if p.get("layer") == "cota" else INK
            _line(c, lx1, ly1, lx2, ly2, w=p.get("w", 0.25) * 0.3,
                  color=color, dash=p.get("dash"))
        elif p["k"] == "circle":
            cx, cy = p["c"]
            r = p["r"] * scale
            px = ox + cx * scale
            py = oy + cy * scale
            c.setStrokeColor(INK)
            c.setLineWidth(p.get("w", 0.25) * 0.3)
            c.circle(px, py, r, fill=0)
        elif p["k"] == "text":
            px, py = p["p"]
            tx = ox + px * scale
            ty = oy + py * scale
            fs = max(p.get("s", 2.5) * scale * 0.35, 1.2)
            color = INK
            if p.get("layer") == "cota":
                color = COTA
            _text(c, tx, ty, p["t"], size=fs, color=color,
                  anchor=p.get("anchor", "middle"),
                  rotate=p.get("rot", 0.0))


def _build_sheet_01(model: ProjectModel, meta: SheetMeta) -> bytes:
    """Folha 01: ELEVAÇÃO FACE LED com malha de gabinetes e cotas."""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W_MM * mm, PAGE_H_MM * mm))
    c.scale(mm, mm)
    _draw_frame(c, meta, "01", SHEETS[0][1])

    view = project_view(model, "FRONTAL", labels=True)

    area_x = MARGIN + BRAND_W + 5
    area_y = MARGIN + STAMP_H + 5
    area_w = PAGE_W_MM - 2 * MARGIN - BRAND_W - 10
    area_h = PAGE_H_MM - 2 * MARGIN - STAMP_H - 30

    _render_view_into(c, view, area_x, area_y, area_w, area_h, pad_mm=350.0)

    # cotas totais do painel (derivadas do modelo)
    pw = model.panel.width
    ph = model.panel.height
    gc = model.installation.ground_clearance
    base_y = area_y + 15
    _dim_h(c, area_x + 10, area_x + 10 + pw * 0.25, base_y,
           f"{pw:.0f}", offset=6, size=3.2)
    _dim_v(c, area_x + 5, base_y + 10, base_y + 10 + ph * 0.25,
           f"{ph:.0f}", offset=6, size=3.2)

    # cotas por gabinete (se houver cabinet no panel)
    cabinet = getattr(model.panel, "cabinet", None)
    if cabinet is None and hasattr(model, "panel"):
        # tenta extrair de elementos
        cols = rows = cw = ch = 0
    else:
        cols = getattr(cabinet, "cols", 0) or 0
        rows = getattr(cabinet, "rows", 0) or 0
        cw = getattr(cabinet, "w", 0) or 0
        ch = getattr(cabinet, "h", 0) or 0

    if cols > 0 and cw > 0:
        step_x = pw / cols
        for i in range(cols):
            x1 = area_x + 10 + i * step_x * 0.25
            x2 = x1 + step_x * 0.25
            _dim_h(c, x1, x2, base_y - 12, f"{cw:.0f}", offset=4, size=2.4)

    if rows > 0 and ch > 0:
        step_z = ph / rows
        for j in range(rows):
            y1 = base_y + 10 + j * step_z * 0.25
            y2 = y1 + step_z * 0.25
            _dim_v(c, area_x - 2, y1, y2, f"{ch:.0f}", offset=4, size=2.4)

    # cota ao solo
    if gc > 0:
        _dim_v(c, area_x + area_w - 15, base_y, base_y + gc * 0.25,
               f"±{gc:.0f}", offset=6, size=2.8)

    # título da vista
    _text(c, area_x + area_w / 2.0, area_y + area_h + 8,
          "ELEVAÇÃO FACE LED", size=5.0, bold=True, anchor="center",
          color=ACCENT)

    c.showPage()
    c.save()
    return buf.getvalue()


def _build_generic_sheet(model: ProjectModel, meta: SheetMeta,
                         sheet_no: str, title: str,
                         view_name: Optional[str]) -> bytes:
    """Folhas genéricas (02-05): renderizam uma vista ou placeholder."""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W_MM * mm, PAGE_H_MM * mm))
    c.scale(mm, mm)
    _draw_frame(c, meta, sheet_no, title)

    area_x = MARGIN + BRAND_W + 5
    area_y = MARGIN + STAMP_H + 5
    area_w = PAGE_W_MM - 2 * MARGIN - BRAND_W - 10
    area_h = PAGE_H_MM - 2 * MARGIN - STAMP_H - 30

    if view_name:
        try:
            view = project_view(model, view_name, labels=True)
            _render_view_into(c, view, area_x, area_y, area_w, area_h,
                              pad_mm=300.0)
        except Exception:
            _text(c, area_x + area_w / 2.0, area_y + area_h / 2.0,
                  "Vista indisponível para este projeto",
                  size=4.0, anchor="center", color=GREY)
    else:
        _text(c, area_x + area_w / 2.0, area_y + area_h / 2.0,
              "Detalhes específicos não aplicáveis\nnesta configuração",
              size=4.0, anchor="center", color=GREY)

    _text(c, area_x + area_w / 2.0, area_y + area_h + 8,
          title, size=5.0, bold=True, anchor="center", color=ACCENT)

    c.showPage()
    c.save()
    return buf.getvalue()


def _build_sheet_07(model: ProjectModel, meta: SheetMeta) -> bytes:
    """Folha 07: Lista de materiais resumida + notas."""
    from core.bom import build_bom

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W_MM * mm, PAGE_H_MM * mm))
    c.scale(mm, mm)
    _draw_frame(c, meta, "07", SHEETS[6][1])

    area_x = MARGIN + BRAND_W + 10
    area_y = MARGIN + STAMP_H + 10
    area_w = PAGE_W_MM - 2 * MARGIN - BRAND_W - 20

    _text(c, area_x, area_y + PAGE_H_MM - STAMP_H - 50,
          "LISTA DE MATERIAIS", size=5.0, bold=True, color=ACCENT)

    try:
        bom = build_bom(model)
        items = bom.get("items", [])
    except Exception:
        items = []

    row_y = area_y + PAGE_H_MM - STAMP_H - 65
    _text(c, area_x, row_y, "QTD", size=2.8, bold=True)
    _text(c, area_x + 20, row_y, "DESCRIÇÃO", size=2.8, bold=True)
    _text(c, area_x + area_w - 40, row_y, "COMPRIMENTO (mm)", size=2.8,
          bold=True, anchor="right")
    row_y -= 5
    _line(c, area_x, row_y, area_x + area_w, row_y, w=0.4)

    for item in items[:35]:
        row_y -= 5.5
        if row_y < area_y + 40:
            break
        qty = item.get("qty", 0)
        desc = str(item.get("description", item.get("profile", "")))[:60]
        length = item.get("length_mm", 0)
        _text(c, area_x, row_y, str(qty), size=2.6)
        _text(c, area_x + 20, row_y, desc, size=2.6)
        if length:
            _text(c, area_x + area_w - 40, row_y, f"{length:.0f}",
                  size=2.6, anchor="right")

    # notas
    notes_y = area_y + 25
    _text(c, area_x, notes_y, "NOTAS:", size=3.0, bold=True)
    notes = [
        "1. Todas as cotas estão em milímetros (mm).",
        "2. Este documento é um ESBOÇO GEOMÉTRICO para orçamento/fabricação.",
        "3. A validação estrutural (vento, fundação, ancoragem) é de",
        "   responsabilidade do engenheiro calculista.",
        f"4. Revisão {meta.revisao} — gerado em {meta.data}.",
    ]
    for note in notes:
        notes_y -= 5
        _text(c, area_x + 3, notes_y, note, size=2.4, color=GREY)

    c.showPage()
    c.save()
    return buf.getvalue()


def _collect_details(model: ProjectModel) -> List[Dict[str, Any]]:
    """Janelas de detalhe derivadas do modelo: canto inferior-esquerdo da
    gaiola, interface poste→quadro, guarda-corpo e quadro superior."""
    from models.element import Element
    gc = model.installation.ground_clearance
    top = gc + model.panel.height
    pw = model.panel.width
    depth = model.panel.depth or 650.0
    det_list: List[Dict[str, Any]] = []

    beams = [el for el in model.elements if el.type == "beam"]
    posts = [el for el in model.elements if el.type == "post"]

    cage_front = [el for el in beams if el.group and "FRENTE" in el.group]
    if cage_front:
        det_list.append({
            "title": "DET. 01 — QUADRO FRENTE (canto inf.)",
            "aabb": ((-pw / 2 - 150, gc - 150), (pw / 2 + 150, top + 150)),
            "elements": cage_front, "label_w": round(pw / 4),
        })
    if posts:
        px = [p.a.x for p in posts if p.a]
        pmin = min(px) if px else 0.0
        det_list.append({
            "title": "DET. 02 — POSTE / GAIOLA (interface)",
            "aabb": ((pmin - 400, -depth - 300), (pmin + 400, 300)),
            "elements": posts + [el for el in beams if el.group and
                                 "INTERFACE" in el.group],
            "label_w": round(gc) if gc else None,
        })
    rail = [el for el in beams if el.group and "GUARDA" in el.group]
    if rail:
        det_list.append({
            "title": "DET. 03 — GUARDA-CORPO",
            "aabb": ((-pw / 2 - 200, -depth - 800), (pw / 2 + 200, -depth)),
            "elements": rail, "label_w": 1100,
        })
    walk = [el for el in model.elements
            if el.type == "grid" and el.group and "PASSARELA" in el.group]
    if walk:
        det_list.append({
            "title": "DET. 04 — PASSARELA / PISO",
            "aabb": ((-pw / 2 - 200, -depth - 700), (pw / 2 + 200, -depth)),
            "elements": walk, "label_w": round(pw / 4),
        })
    return det_list


def _draw_detail_pdf(c: rl_canvas.Canvas, det: Dict[str, Any],
                     x: float, y: float, w: float, h: float) -> None:
    """Desenha uma janela de detalhe: moldura + elementos + título + cota."""
    _line(c, x, y, x + w, y, w=0.4, color=GREY)
    _line(c, x, y + h, x + w, y + h, w=0.4, color=GREY)
    _line(c, x, y, x, y + h, w=0.4, color=GREY)
    _line(c, x + w, y, x + w, y + h, w=0.4, color=GREY)

    (x0, z0), (x1, z1) = det["aabb"]
    dw = max(x1 - x0, 1.0)
    dh = max(z1 - z0, 1.0)
    scale = min((w - 10) / dw, (h - 14) / dh)
    ox = x + 5 + ((w - 10) - dw * scale) / 2 - x0 * scale
    oy = y + 7 + ((h - 14) - dh * scale) / 2 - z0 * scale

    for el in det["elements"]:
        pts = []
        if el.start and el.end:
            pts = [(el.start.x, el.start.z), (el.end.x, el.end.z)]
        if len(pts) == 2:
            (a, b) = pts
            _line(c, ox + a[0] * scale, oy + a[1] * scale,
                  ox + b[0] * scale, oy + b[1] * scale, w=0.3, color=INK)
        elif el.a and el.b:
            _line(c, ox + el.a.x * scale, oy + el.a.z * scale,
                  ox + el.b.x * scale, oy + el.b.z * scale, w=0.3, color=INK)

    _text(c, x + 2, y + h - 5, det["title"], size=2.8, bold=True, color=ACCENT)
    lw = det.get("label_w")
    if lw:
        _dim_h(c, x + 5, x + 5 + lw * scale, y + 3, f"{lw}", offset=3, size=2.2)


def build_sheetpack_pdf(model: ProjectModel,
                        meta: Optional[Dict[str, str]] = None) -> bytes:
    """Gera PDF completo com 7 folhas."""
    m = SheetMeta(
        obra=(meta or {}).get("obra", model.project.name or ""),
        cliente=(meta or {}).get("cliente", ""),
        marca=(meta or {}).get("marca", "LED STRUCTURE CAD"),
        numero=(meta or {}).get("numero", "LC-2026-001"),
        revisao=str((meta or {}).get("revisao", "A")),
    )

    views_map = {
        "02": ("TRASEIRA", SHEETS[1][1]),
        "03": ("LATERAL", SHEETS[2][1]),
        "04": ("SUPERIOR", SHEETS[3][1]),
        "05": ("ISOMETRICA", SHEETS[4][1]),
    }

    buf2 = io.BytesIO()
    out = rl_canvas.Canvas(buf2, pagesize=(PAGE_W_MM * mm, PAGE_H_MM * mm))

    # Folha 01
    out.scale(mm, mm)
    _draw_frame(out, m, "01", SHEETS[0][1])
    view_front = project_view(model, "FRONTAL", labels=True)
    ax = MARGIN + BRAND_W + 5
    ay = MARGIN + STAMP_H + 5
    aw = PAGE_W_MM - 2 * MARGIN - BRAND_W - 10
    ah = PAGE_H_MM - 2 * MARGIN - STAMP_H - 30
    _render_view_into(out, view_front, ax, ay, aw, ah, pad_mm=350.0)
    pw = model.panel.width
    ph = model.panel.height
    gc = model.installation.ground_clearance
    _dim_h(out, ax + 10, ax + 10 + pw * 0.25, ay + 15,
           f"{pw:.0f}", offset=6, size=3.2)
    _dim_v(out, ax + 5, ay + 25, ay + 25 + ph * 0.25,
           f"{ph:.0f}", offset=6, size=3.2)
    if gc > 0:
        _dim_v(out, ax + aw - 15, ay + 15, ay + 15 + gc * 0.25,
               f"±{gc:.0f}", offset=6, size=2.8)
    _text(out, ax + aw / 2.0, ay + ah + 8,
          "ELEVAÇÃO FACE LED", size=5.0, bold=True, anchor="center",
          color=ACCENT)
    out.showPage()

    # Folhas 02-05
    for no, (vname, title) in views_map.items():
        out.scale(mm, mm)
        _draw_frame(out, m, no, title)
        try:
            v = project_view(model, vname, labels=True)
            _render_view_into(out, v, ax, ay, aw, ah, pad_mm=300.0)
        except Exception:
            _text(out, ax + aw / 2.0, ay + ah / 2.0,
                  "Vista indisponível", size=4.0, anchor="center", color=GREY)
        _text(out, ax + aw / 2.0, ay + ah + 8,
              title, size=5.0, bold=True, anchor="center", color=ACCENT)
        out.showPage()

    # Folha 06 — DETALHES (janelas de geometria REAL do modelo, ampliadas)
    out.scale(mm, mm)
    _draw_frame(out, m, "06", SHEETS[5][1])
    details = _collect_details(model)
    if details:
        dax = ax + 5
        day = ay + ah - 5
        dw = aw / 2 - 8
        dh = min(120.0, ah / 3 - 10)
        for i, det in enumerate(details[:4]):
            col = i % 2
            row = i // 2
            dx = dax + col * (dw + 6)
            dy = day - 14 - dh - row * (dh + 14)
            _draw_detail_pdf(out, det, dx, dy, dw, dh)
    else:
        _text(out, ax + aw / 2.0, ay + ah / 2.0,
              "Sem detalhes aplicáveis — projeto sem gaiola/postes/passarela.",
              size=4.0, anchor="center", color=GREY)
    _text(out, ax + aw / 2.0, ay + ah + 8,
          SHEETS[5][1], size=5.0, bold=True, anchor="center", color=ACCENT)
    out.showPage()

    # Folha 07
    out.scale(mm, mm)
    _draw_frame(out, m, "07", SHEETS[6][1])
    _text(out, ax, ay + ah - 10, "LISTA DE MATERIAIS", size=5.0,
          bold=True, color=ACCENT)
    try:
        from core.bom import build_bom
        bom = build_bom(model)
        items = bom.get("items", [])
    except Exception:
        items = []
    ry = ay + ah - 25
    _text(out, ax, ry, "QTD", size=2.8, bold=True)
    _text(out, ax + 20, ry, "DESCRIÇÃO", size=2.8, bold=True)
    _text(out, ax + aw - 40, ry, "COMP. (mm)", size=2.8, bold=True,
          anchor="right")
    ry -= 5
    _line(out, ax, ry, ax + aw, ry, w=0.4)
    for item in items[:35]:
        ry -= 5.5
        if ry < ay + 40:
            break
        _text(out, ax, ry, str(item.get("qty", 0)), size=2.6)
        _text(out, ax + 20, ry,
              str(item.get("description", item.get("profile", "")))[:60],
              size=2.6)
        ln = item.get("length_mm", 0)
        if ln:
            _text(out, ax + aw - 40, ry, f"{ln:.0f}", size=2.6,
                  anchor="right")
    ny = ay + 25
    _text(out, ax, ny, "NOTAS:", size=3.0, bold=True)
    for note in [
        "1. Cotas em milímetros (mm).",
        "2. ESBOÇO GEOMÉTRICO — validar com engenheiro responsável.",
        f"3. Revisão {m.revisao} — {m.data}.",
    ]:
        ny -= 5
        _text(out, ax + 3, ny, note, size=2.4, color=GREY)
    out.showPage()

    out.save()
    return buf2.getvalue()


def build_sheet_svg(model: ProjectModel, sheet_index: int = 0,
                    meta: Optional[Dict[str, str]] = None) -> str:
    """Gera SVG de uma folha individual (0-indexed)."""
    idx = max(0, min(sheet_index, len(SHEETS) - 1))
    sheet_no, title = SHEETS[idx]
    m = SheetMeta(
        obra=(meta or {}).get("obra", model.project.name or ""),
        cliente=(meta or {}).get("cliente", ""),
        marca=(meta or {}).get("marca", "LED STRUCTURE CAD"),
        numero=(meta or {}).get("numero", "LC-2026-001"),
        revisao=str((meta or {}).get("revisao", "A")),
    )

    pw_px = PAGE_W_MM * 2  # escala 2px/mm para boa resolução
    ph_px = PAGE_H_MM * 2
    sc = pw_px / PAGE_W_MM

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="{pw_px}" height="{ph_px}" '
                 f'viewBox="0 0 {PAGE_W_MM} {PAGE_H_MM}">')
    lines.append(f'<rect width="{PAGE_W_MM}" height="{PAGE_H_MM}" '
                 f'fill="white"/>')

    # moldura
    mx, my = MARGIN, MARGIN
    mw = PAGE_W_MM - 2 * MARGIN
    mh = PAGE_H_MM - 2 * MARGIN
    lines.append(f'<rect x="{mx}" y="{my}" width="{mw}" height="{mh}" '
                 f'fill="none" stroke="#111827" stroke-width="0.7"/>')

    # faixa lateral
    bh = PAGE_H_MM - 2 * MARGIN - STAMP_H
    lines.append(f'<rect x="{mx}" y="{my}" width="{BRAND_W}" height="{bh}" '
                 f'fill="#1b2530"/>')
    lines.append(f'<text x="{mx + BRAND_W / 2}" y="{my + bh / 2}" '
                 f'text-anchor="middle" dominant-baseline="central" '
                 f'font-size="7" font-weight="bold" fill="#f9fafb" '
                 f'transform="rotate(-90,{mx + BRAND_W / 2},{my + bh / 2})">'
                 f'{m.marca.upper()}</text>')

    # carimbo
    sx = mx + BRAND_W
    sy = my
    sw = PAGE_W_MM - 2 * MARGIN - BRAND_W
    sh = STAMP_H
    lines.append(f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" '
                 f'fill="none" stroke="#111827" stroke-width="0.5"/>')
    lines.append(f'<text x="{sx + 3}" y="{sy + sh - 5}" font-size="4" '
                 f'font-weight="bold">{m.obra or "PAINEL LED"}</text>')
    lines.append(f'<text x="{sx + sw * 0.55 + 3}" y="{sy + sh - 5}" '
                 f'font-size="4.5" font-weight="bold" fill="#26313d">'
                 f'{title}</text>')
    lines.append(f'<text x="{sx + sw * 0.55 + 3}" y="{sy + sh - 17}" '
                 f'font-size="2.8">Folha {sheet_no}/07 · Rev {m.revisao}'
                 f'</text>')
    lines.append(f'<text x="{sx + 3}" y="{sy + sh - 17}" font-size="2.2" '
                 f'fill="#6b7280">{m.aviso[:70]}</text>')

    # vista
    view_map = {
        0: "FRONTAL", 1: "TRASEIRA", 2: "LATERAL",
        3: "SUPERIOR", 4: "ISOMETRICA",
    }
    vname = view_map.get(idx)
    if idx == 5:
        # Folha 06 — detalhes (mesma janela que o PDF)
        details = _collect_details(model)
        area_x = mx + BRAND_W + 5
        area_y = my + STAMP_H + 5
        area_w = PAGE_W_MM - 2 * MARGIN - BRAND_W - 10
        area_h = PAGE_H_MM - 2 * MARGIN - STAMP_H - 30
        if details:
            dw = area_w / 2 - 8
            dh = min(120.0, area_h / 3 - 10)
            for i, det in enumerate(details[:4]):
                col, row = i % 2, i // 2
                dx = area_x + 5 + col * (dw + 6)
                dy = area_y + area_h - 5 - 14 - dh - row * (dh + 14)
                (x0, z0), (x1, z1) = det["aabb"]
                gw = max(x1 - x0, 1.0)
                gh = max(z1 - z0, 1.0)
                sc2 = min((dw - 10) / gw, (dh - 14) / gh)
                ox2 = dx + 5 + ((dw - 10) - gw * sc2) / 2 - x0 * sc2
                oy2 = dy + 7 + ((dh - 14) - gh * sc2) / 2 - z0 * sc2
                lines.append(f'<rect x="{dx:.1f}" y="{dy:.1f}" '
                             f'width="{dw:.1f}" height="{dh:.1f}" fill="none" '
                             f'stroke="#6b7280" stroke-width="0.4"/>')
                for el in det["elements"]:
                    pts = None
                    if el.start and el.end:
                        pts = ((el.start.x, el.start.z), (el.end.x, el.end.z))
                    elif getattr(el, "a", None) and getattr(el, "b", None):
                        pts = ((el.a.x, el.a.z), (el.b.x, el.b.z))
                    if pts:
                        (a, b) = pts
                        lines.append(
                            f'<line x1="{ox2 + a[0] * sc2:.1f}" '
                            f'y1="{oy2 + a[1] * sc2:.1f}" '
                            f'x2="{ox2 + b[0] * sc2:.1f}" '
                            f'y2="{oy2 + b[1] * sc2:.1f}" '
                            f'stroke="#111827" stroke-width="0.3"/>')
                lines.append(f'<text x="{dx + 2:.1f}" y="{dy + dh - 5:.1f}" '
                             f'font-size="2.8" font-weight="bold" '
                             f'fill="#26313d">{det["title"]}</text>')
        else:
            lines.append(f'<text x="{area_x + area_w / 2:.1f}" '
                         f'y="{area_y + area_h / 2:.1f}" font-size="4" '
                         f'text-anchor="middle" fill="#6b7280">'
                         f'Sem detalhes aplicáveis</text>')
    elif vname:
        try:
            view = project_view(model, vname, labels=True)
            bounds = view.padded(300.0)
            dw = max(bounds.max[0] - bounds.min[0], 1.0)
            dh = max(bounds.max[1] - bounds.min[1], 1.0)
            area_x = mx + BRAND_W + 5
            area_y = my + STAMP_H + 5
            area_w = PAGE_W_MM - 2 * MARGIN - BRAND_W - 10
            area_h = PAGE_H_MM - 2 * MARGIN - STAMP_H - 30
            vscale = min(area_w / dw, area_h / dh)
            vox = area_x + (area_w - dw * vscale) / 2.0 - bounds.min[0] * vscale
            voy = area_y + (area_h - dh * vscale) / 2.0 - bounds.min[1] * vscale

            for prim in view.prims:
                if prim["k"] == "line":
                    ax, ay = prim["a"]
                    bx, by = prim["b"]
                    lx1 = vox + ax * vscale
                    ly1 = voy + ay * vscale
                    lx2 = vox + bx * vscale
                    ly2 = voy + by * vscale
                    # SVG y é invertido
                    ly1 = PAGE_H_MM - ly1
                    ly2 = PAGE_H_MM - ly2
                    color = "#b45309" if prim.get("layer") == "cota" else "#111827"
                    dash = prim.get("dash")
                    da = f' stroke-dasharray="{dash}"' if dash else ""
                    lines.append(f'<line x1="{lx1:.1f}" y1="{ly1:.1f}" '
                                 f'x2="{lx2:.1f}" y2="{ly2:.1f}" '
                                 f'stroke="{color}" '
                                 f'stroke-width="{prim.get("w", 0.25) * 0.3:.2f}"'
                                 f'{da}/>')
                elif prim["k"] == "circle":
                    cx, cy = prim["c"]
                    px = vox + cx * vscale
                    py = PAGE_H_MM - (voy + cy * vscale)
                    r = prim["r"] * vscale
                    lines.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" '
                                 f'r="{r:.1f}" fill="none" stroke="#111827" '
                                 f'stroke-width="{prim.get("w", 0.25) * 0.3:.2f}"/>')
                elif prim["k"] == "text":
                    px, py = prim["p"]
                    tx = vox + px * vscale
                    ty = PAGE_H_MM - (voy + py * vscale)
                    fs = max(prim.get("s", 2.5) * vscale * 0.35, 1.8)
                    anc = prim.get("anchor", "middle")
                    svg_anchor = {"start": "start", "end": "end"}.get(anc, "middle")
                    color = prim.get("color", "#111827") or "#111827"
                    rot = prim.get("rot", 0.0)
                    transform = f' transform="rotate({-rot},{tx:.1f},{ty:.1f})"' if rot else ""
                    lines.append(f'<text x="{tx:.1f}" y="{ty:.1f}" '
                                 f'font-size="{fs:.1f}" text-anchor="{svg_anchor}" '
                                 f'fill="{color}"{transform}>{prim["t"]}</text>')
        except Exception:
            pass

    # Cotas associativas (folha 01) — derivadas do modelo, nunca texto fixo
    if idx == 0:
        from drawing.dimensions import add_dimensions
        area_x = mx + BRAND_W + 5
        area_y = my + STAMP_H + 5
        area_w = PAGE_W_MM - 2 * MARGIN - BRAND_W - 10
        area_h = PAGE_H_MM - 2 * MARGIN - STAMP_H - 30
        pw = model.panel.width
        ph = model.panel.height
        gc = model.installation.ground_clearance
        # malha de gabinetes derivada da geometria dos elementos (grupos)
        xs = sorted({round(el.start.x) for el in model.elements
                     if el.type == "beam" and el.group and
                     "FRENTE" in el.group and abs(el.start.z - gc) < 1 and
                     abs(el.end.z - gc) < 1
                     for el in [el] if True} or set())
        cols = max(0, len(xs) - 1) if xs else 0
        cw = round(pw / cols) if cols else 0
        rows = max(0, len(sorted({round(el.start.z) for el in model.elements
                                  if el.type == "beam" and el.group and
                                  "FRENTE" in el.group and
                                  abs(el.start.x + pw / 2) < 1})) - 1) if model.elements else 0
        ch = round(ph / rows) if rows else 0
        cw = cw or round(pw)
        ch = ch or round(ph)

        def _svg_dim_h(x1, x2, y, label, off=6.0):
            yo = y + off
            lines.append(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x1:.1f}" '
                         f'y2="{yo + 3:.1f}" stroke="#b45309" '
                         f'stroke-width="0.18"/>')
            lines.append(f'<line x1="{x2:.1f}" y1="{y:.1f}" x2="{x2:.1f}" '
                         f'y2="{yo + 3:.1f}" stroke="#b45309" '
                         f'stroke-width="0.18"/>')
            lines.append(f'<line x1="{x1:.1f}" y1="{yo:.1f}" x2="{x2:.1f}" '
                         f'y2="{yo:.1f}" stroke="#b45309" stroke-width="0.25"/>')
            lines.append(f'<text x="{(x1 + x2) / 2:.1f}" y="{yo - 1:.1f}" '
                         f'font-size="3.2" text-anchor="middle" '
                         f'fill="#b45309">{label}</text>')

        def _svg_dim_v(x, y1, y2, label, off=6.0):
            xo = x - off
            lines.append(f'<line x1="{x:.1f}" y1="{y1:.1f}" x2="{xo - 3:.1f}" '
                         f'y2="{y1:.1f}" stroke="#b45309" '
                         f'stroke-width="0.18"/>')
            lines.append(f'<line x1="{x:.1f}" y1="{y2:.1f}" x2="{xo - 3:.1f}" '
                         f'y2="{y2:.1f}" stroke="#b45309" '
                         f'stroke-width="0.18"/>')
            lines.append(f'<line x1="{xo:.1f}" y1="{y1:.1f}" x2="{xo:.1f}" '
                         f'y2="{y2:.1f}" stroke="#b45309" '
                         f'stroke-width="0.25"/>')
            lines.append(f'<text x="{xo - 2:.1f}" y="{(y1 + y2) / 2:.1f}" '
                         f'font-size="3.2" text-anchor="end" '
                         f'fill="#b45309" transform="rotate(-90 '
                         f'{xo - 2:.1f},{(y1 + y2) / 2:.1f})">'
                         f'{label}</text>')

        # base do desenho: borda inferior da área de vista
        b0 = area_y + 20
        # cota total (largura)
        _svg_dim_h(area_x + 10, area_x + area_w - 10, b0,
                   f"{round(pw)}", off=8)
        # cotas por módulo (horizontais)
        if cols >= 1:
            step = (area_w - 20) / cols
            for i in range(cols):
                _svg_dim_h(area_x + 10 + i * step,
                           area_x + 10 + (i + 1) * step, b0 + 14,
                           f"{cw}", off=5)
        # cota total (altura) à esquerda
        t0 = b0 + 30
        _svg_dim_v(area_x + 12, t0, t0 + area_h - 60, f"{round(ph)}", off=10)
        # cotas por módulo (verticais)
        if rows >= 1:
            vstep = (area_h - 60) / rows
            for j in range(rows):
                _svg_dim_v(area_x + 26, t0 + j * vstep, t0 + (j + 1) * vstep,
                           f"{ch}", off=6)
        # cota ao solo (à direita)
        if gc > 0:
            sol = t0 + area_h - 60 - 30
            _svg_dim_v(area_x + area_w - 18, sol, sol + 28,
                       f"{round(gc)}", off=6)
            # nível do solo
            gy = PAGE_H_MM - MARGIN - STAMP_H - 12
            lines.append(f'<line x1="{area_x:.1f}" y1="{gy:.1f}" '
                         f'x2="{area_x + area_w:.1f}" y2="{gy:.1f}" '
                         f'stroke="#111827" stroke-width="0.5"/>')
            lines.append(f'<text x="{area_x + area_w - 4:.1f}" '
                         f'y="{gy - 3:.1f}" font-size="2.6" '
                         f'text-anchor="end" fill="#6b7280">'
                         f'NÍVEL DO SOLO</text>')

    lines.append('</svg>')
    return "\n".join(lines)