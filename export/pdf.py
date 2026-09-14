"""Prancha técnica PDF (reportlab) — vetorial, layout A2 paisagem.

Estrutura inspirada na prancha de referência LED EXPERT 222-2023-11-FL01:
vistas com cotas, perspectiva, lista de materiais, notas, legenda e selo
"PROJETO SOMENTE PARA ORÇAMENTO — NÃO UTILIZAR PARA FABRICAÇÃO".
"""
from __future__ import annotations

import io
from datetime import date
from typing import Dict, List

from reportlab.lib.colors import HexColor, red
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from core.bom import build_bom
from drawing.projections import View2D

PAGE_W, PAGE_H = 594.0, 420.0  # A2 paisagem em mm
M = 10.0  # margem interna
NOTES_X = 452.0

INK = HexColor("#1f2937")
GREY = HexColor("#6b7280")
COTA = HexColor("#b45309")
ACCENT = HexColor("#0f766e")
LIGHT = HexColor("#e5e7eb")


def _line(c: rl_canvas.Canvas, x1, y1, x2, y2, w=0.25, color=INK, dash=None):
    c.setStrokeColor(color)
    c.setLineWidth(w)
    if dash:
        c.setDash(dash)
    c.line(x1, y1, x2, y2)
    if dash:
        c.setDash()


def _text(c: rl_canvas.Canvas, x, y, s, size=2.6, color=INK, bold=False, anchor="left"):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    if anchor == "center":
        c.drawCentredString(x, y, s)
    elif anchor == "right":
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)


def render_view_pdf(c: rl_canvas.Canvas, view: View2D, x: float, y: float, w: float, h: float,
                    title: str = "", pad_mm: float = 320.0) -> None:
    """Desenha a View2D dentro do retângulo (x = esq, y = base, w, h) em mm."""
    b = view.padded(pad_mm)
    if not b.valid:
        return
    wmm = max(b.max[0] - b.min[0], 1)
    hmm = max(b.max[1] - b.min[1], 1)
    scale = min(w / wmm, h / hmm)
    ox = x + (w - wmm * scale) / 2 - b.min[0] * scale
    oy = y + (h - hmm * scale) / 2 - b.min[1] * scale

    colors = {
        "perfil": INK, "perfil2": GREY, "poste": INK, "chapa": HexColor("#4b5563"),
        "painel": HexColor("#9ca3af"), "cota": COTA, "texto": INK,
        "label": ACCENT, "eixo": HexColor("#cbd5e1"),
    }

    for prim in view.prims:
        k = prim["k"]
        # A prancha é um esboço dimensional. Identificadores de barras e
        # materiais/perfis (METALON, TUBO etc.) são internos ao editor e não
        # fazem parte da entrega para a empresa de estrutura metálica.
        if k == "text" and prim.get("layer") != "cota":
            continue
        col = colors.get(prim.get("layer", "perfil"), INK)
        # Linhas de cota e chamadas precisam sobreviver à redução geométrica.
        lw = max(prim.get("w", 1.0) * scale, 0.35 if prim.get("layer") == "cota" else 0.18)
        if k == "line":
            (ax, ay), (bx, by) = prim["a"], prim["b"]
            dash = (1.2, 1.2) if prim.get("dash") else None
            _line(c, ox + ax * scale, oy + ay * scale, ox + bx * scale, oy + by * scale,
                  w=lw, color=col, dash=dash)
        elif k == "circle":
            (cx, cy), r = prim["c"], prim["r"]
            c.setStrokeColor(col)
            c.setLineWidth(lw)
            c.circle(ox + cx * scale, oy + cy * scale, r * scale, stroke=1, fill=0)
        elif k == "text":
            (tx, ty), s = prim["p"], prim["s"]
            # A geometria pode ter metros de altura e precisa caber na A2;
            # O canvas já está escalado em milímetros. O piso garante fonte
            # legível impressa: cotas nunca encolhem para caber.
            floor = 5.0 if prim.get("layer") == "cota" else 4.2
            size = max(s * scale, floor)
            anchor = {"middle": "center", "start": "left", "end": "right"}.get(
                prim.get("anchor", "middle"), "center")
            rot = prim.get("rot", 0)
            if rot:
                c.saveState()
                c.translate(ox + tx * scale, oy + ty * scale)
                c.rotate(rot)
                _text(c, 0, 0, prim["t"], size=size, color=col, anchor=anchor)
                c.restoreState()
            else:
                _text(c, ox + tx * scale, oy + ty * scale, prim["t"], size=size,
                      color=col, anchor=anchor)

    if title:
        _text(c, x + w / 2, y - 5.0, title, size=5.4, bold=True, anchor="center")


def _bom_table(c: rl_canvas.Canvas, model, x: float, y: float, w: float, h: float) -> None:
    bom = build_bom(model)
    _text(c, x, y + h - 5, "LISTA DE MATERIAIS", size=4.2, bold=True)
    _text(c, x + w, y + h - 5, f"PESO TOTAL GERAL: {bom['total_mass_kg']:.2f} KG",
          size=3.4, bold=True, anchor="right")
    p = bom.get("pricing", {})
    if p:
        _text(c, x + w, y + h - 9.5,
              f"CUSTO ESTIMADO (MATERIAL): R$ {bom.get('total_cost_brl', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
              size=3.4, bold=True, anchor="right", color=ACCENT)
        _text(c, x + w, y + h - 13.5,
              f"REF: R$ {p.get('steel_profile_brl_kg', 0):.2f}/kg PERFIL + R$ {p.get('steel_plate_brl_kg', 0):.2f}/kg CHAPA "
              f"+ R$ {p.get('paint_brl_kg', 0):.2f}/kg PINTURA + {int((p.get('waste_factor', 1) - 1) * 100)}% PERDA",
              size=2.3, anchor="right", color=GREY)

    widths = [14, 132, 44, 28, 36, 58, 64, 48]
    headers = ["POS", "DESCRIÇÃO", "COMPR.", "UNID.", "QUANT.", "PESO UNIT.", "PESO TOTAL", "CUSTO (R$)"]
    ty = y + h - 19
    row_h = 4.6

    # header
    c.setFillColor(LIGHT)
    c.rect(x, ty - row_h + 1.2, sum(widths), row_h, stroke=0, fill=1)
    cx = x
    for wd, hd in zip(widths, headers):
        _text(c, cx + 1.4, ty - 3.2, hd, size=2.7, bold=True)
        cx += wd
    ty -= row_h

    c.setStrokeColor(HexColor("#d1d5db"))
    for it in bom["items"][:15]:
        cells = [f"{it['pos']:02d}", it["descr"][:40], str(it["compr"]), it["unid"],
                 str(it["quant"]), str(it["peso_unit"]), f"{it['peso_total']:.2f}",
                 f"{it.get('custo_total', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")]
        cx = x
        for wd, txt in zip(widths, cells):
            _text(c, cx + 1.4, ty - 3.2, txt, size=2.5)
            cx += wd
        _line(c, x, ty - row_h + 1.2, x + sum(widths), ty - row_h + 1.2, w=0.1,
              color=HexColor("#e5e7eb"))
        ty -= row_h
    _line(c, x, ty + row_h - row_h + 0.8, x + sum(widths), ty + 0.8, w=0.35)


def _build_pdf_compact_legacy(model, views: Dict[str, View2D], meta: Dict[str, str] | None = None) -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W * mm, PAGE_H * mm))
    c.scale(mm, mm)  # unidades em mm
    meta = meta or {}

    # ---------------- moldura ----------------
    _line(c, M, M, PAGE_W - M, M, w=0.8)
    _line(c, M, M, M, PAGE_H - M, w=0.8)
    _line(c, PAGE_W - M, M, PAGE_W - M, PAGE_H - M, w=0.8)
    _line(c, M, PAGE_H - M, PAGE_W - M, PAGE_H - M, w=0.8)
    _line(c, NOTES_X, M, NOTES_X, PAGE_H - M, w=0.5)

    # ---------------- vistas (2 bandas à esquerda) ----------------
    bandA_y, bandA_h = 212.0, 162.0   # base e altura
    bandB_y, bandB_h = 120.0, 86.0

    if "FRONTAL" in views:
        render_view_pdf(c, views["FRONTAL"], M + 2, bandA_y, 248, bandA_h,
                        title="VISTA FRONTAL")
    if "LATERAL" in views:
        render_view_pdf(c, views["LATERAL"], 264, bandA_y, 90, bandA_h,
                        title="VISTA LATERAL", pad_mm=380)
    if "ISOMETRICA" in views:
        render_view_pdf(c, views["ISOMETRICA"], 358, bandA_y, 88, bandA_h,
                        title="PERSPECTIVA", pad_mm=430)
    if "SUPERIOR" in views:
        render_view_pdf(c, views["SUPERIOR"], M + 2, bandB_y, 248, bandB_h,
                        title="VISTA SUPERIOR (MONTAR PISO)", pad_mm=180)
    if "INFERIOR" in views:
        render_view_pdf(c, views["INFERIOR"], 264, bandB_y, 182, bandB_h,
                        title="VISTA INFERIOR (CHAPA EXPANDIDA)", pad_mm=180)

    # Prancha visual: vistas, cotas e geometria; sem quantitativos ou custos.

    # ---------------- notas / revisões / selo (coluna direita) ----------------
    nx = NOTES_X + 3
    nw = PAGE_W - M - nx
    ny = PAGE_H - M - 7
    _text(c, nx, ny, "NOTAS:", size=3.6, bold=True)
    _text(c, nx, ny - 5.5, "MEDIDAS EM MILÍMETRO;", size=2.9)
    _text(c, nx, ny - 10, "SEGUIR TODAS AS COTAS DO PROJETO.", size=2.9)
    _text(c, nx, ny - 17, "ESTRUTURA PARA INSTALAÇÃO DE PAINEL", size=2.9)
    inst_lines = {
        "post": "DE LED — USO EM OUTDOOR (DOOH).",
        "wall": "DE LED — FIXADO EM PAREDE/FACHADA.",
        "suspended": "DE LED — SUSPENSO A TETO/GALPÃO.",
        "rental": "DE LED — TEMPORÁRIA (PALCO/EVENTO).",
    }
    _text(c, nx, ny - 21.5, inst_lines.get(model.installation.type,
                                            "DE LED."), size=2.9)

    rv_y = ny - 34
    _line(c, nx, rv_y, nx + nw - 3, rv_y, w=0.4)
    cx = nx
    for wd, hd in zip((14, 46, 26, 26), ("Nº", "DESCRIÇÃO", "RESP.", "DATA")):
        _text(c, cx + 1, rv_y - 4, hd, size=2.5, bold=True)
        cx += wd
    revs = meta.get("revisions") or [("00", "INICIAL", "P.C.A",
                                      date.today().strftime("%d/%m/%Y"))]
    ry = rv_y - 9.5
    for rev in revs[:4]:
        cx = nx
        for wd, val in zip((14, 46, 26, 26), rev):
            _text(c, cx + 1, ry, str(val), size=2.5)
            cx += wd
        ry -= 6

    # logo
    ly = ry - 10
    c.setStrokeColor(ACCENT)
    c.setLineWidth(0.9)
    c.roundRect(nx, ly - 13, 66, 14, 2, stroke=1, fill=0)
    _text(c, nx + 33, ly - 8.5, meta.get("brand", "LED COLLOR"), size=5.6, bold=True,
          color=ACCENT, anchor="center")

    # selo vermelho
    _text(c, nx, ly - 28, "ESBOÇO VISUAL PARA VALIDAÇÃO", size=4.4, bold=True, color=red)
    _text(c, nx, ly - 35.5, "REVISAR COM ENGENHEIRO RESPONSÁVEL", size=3.7, bold=True, color=red)

    # ---------------- legenda (title block) ----------------
    tb_h = 60.0
    _line(c, NOTES_X, M + tb_h, PAGE_W - M, M + tb_h, w=0.6)
    ry = M + tb_h - 7
    _text(c, nx, ry, "OBRA:", size=2.7, bold=True)
    _text(c, nx, ry - 4.6, str(meta.get("obra", model.project.name))[:58], size=2.9)
    ry -= 13
    _text(c, nx, ry, "CONTÉM:", size=2.7, bold=True)
    _text(c, nx, ry - 4.6, str(meta.get("contem", "PROJETO DE ESTRUTURA METÁLICA — PAINEL LED"))[:58], size=2.9)
    _line(c, NOTES_X, ry - 8.5, PAGE_W - M, ry - 8.5, w=0.3)

    today = date.today().strftime("%d-%m-%Y")
    cx = nx
    colw = (PAGE_W - M - nx) / 4
    for lab, val in (("OBRA", meta.get("obra_short", "PAINEL LED OUTDOOR")),
                     ("Data:", today),
                     ("Desenhista:", meta.get("desenhista", "LED COLLOR")),
                     ("Nº PRANCHA:", meta.get("sheet", "LC-FL01"))):
        _text(c, cx, ry - 12.5, lab, size=2.2, bold=True, color=GREY)
        _text(c, cx, ry - 17.5, str(val)[:24], size=2.7)
        cx += colw
    _line(c, NOTES_X, ry - 21, PAGE_W - M, ry - 21, w=0.3)
    cx = nx
    for lab, val in (("ESCALA:", meta.get("escala", "IND.")),
                     ("FORMATO:", "A2"),
                     ("Nº LED COLLOR:", meta.get("number", "LC-001")),
                     ("REVISÃO:", meta.get("revision", "00"))):
        _text(c, cx, ry - 25, lab, size=2.2, bold=True, color=GREY)
        _text(c, cx, ry - 30, str(val)[:24], size=2.7, bold=True)
        cx += colw

    c.showPage()
    c.save()
    return buf.getvalue()


def _sheet_header(c: rl_canvas.Canvas, title: str, model, meta: Dict[str, str], number: int,
                  page_w: float, page_h: float) -> None:
    """Moldura de uma prancha de detalhe. A área útil é dedicada a uma vista."""
    _line(c, M, M, page_w - M, M, w=0.8)
    _line(c, M, M, M, page_h - M, w=0.8)
    _line(c, page_w - M, M, page_w - M, page_h - M, w=0.8)
    _line(c, M, page_h - M, page_w - M, page_h - M, w=0.8)
    _line(c, M, page_h - M - 20, page_w - M, page_h - M - 20, w=0.45)
    _line(c, M, 31, page_w - M, 31, w=0.45)
    _text(c, M + 5, page_h - M - 8, "ESBOÇO ESTRUTURAL DIMENSIONAL", size=6.2,
          bold=True, color=ACCENT)
    _text(c, page_w - M - 5, page_h - M - 8, title, size=6.2,
          bold=True, anchor="right")
    project = str(meta.get("obra", model.project.name or "PAINEL LED"))
    _text(c, M + 5, page_h - M - 15, project[:105], size=3.6, color=GREY)
    panel = f"PAINEL: {model.panel.width:.0f} × {model.panel.height:.0f} × {model.panel.depth:.0f} mm"
    _text(c, M + 5, 19, panel, size=3.6, bold=True)
    _text(c, M + 5, 13, "COTAS EM MILÍMETROS · ESBOÇO VISUAL — REVISAR COM ENGENHEIRO RESPONSÁVEL",
          size=3.2, color=GREY)
    _text(c, page_w - M - 5, 19, f"FOLHA {number:02d}", size=3.6, bold=True, anchor="right")
    _text(c, page_w - M - 5, 13, date.today().strftime("%d/%m/%Y"), size=3.2,
          color=GREY, anchor="right")


def build_pdf(model, views: Dict[str, View2D], meta: Dict[str, str] | None = None) -> bytes:
    """Exporta uma vista técnica por folha A2 para priorizar leitura das cotas."""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W * mm, PAGE_H * mm))
    # A escala em mm é (re)aplicada dentro do loop, folha a folha, porque o
    # showPage() reseta a CTM do reportlab (ver chamada abaixo).
    meta = meta or {}
    titles = {
        "FRONTAL": "VISTA FRONTAL",
        "TRASEIRA": "VISTA TRASEIRA",
        "LATERAL": "VISTA LATERAL",
        "SUPERIOR": "VISTA SUPERIOR",
        "INFERIOR": "VISTA INFERIOR",
        "ISOMETRICA": "VISTA ISOMÉTRICA",
    }
    # Cada página usa praticamente toda a A2; é propositalmente diferente do
    # layout compacto antigo, em que seis vistas comprimiam as cotas.
    order = ("FRONTAL", "TRASEIRA", "LATERAL", "SUPERIOR", "INFERIOR", "ISOMETRICA")
    page_no = 0
    for name in order:
        view = views.get(name)
        if view is None:
            continue
        page_no += 1
        # O showPage() do reportlab reseta o estado gráfico da CTM. O scale(mm)
        # precisa ser REAPLICADO no início de cada folha: aplicado uma única
        # vez antes do loop, as folhas seguintes eram desenhadas em pontos
        # (≈35% do tamanho), amontoadas no canto inferior esquerdo.
        c.scale(mm, mm)
        padding = 450.0 if name == "ISOMETRICA" else 300.0
        bounds = view.padded(padding)
        drawing_w = max(bounds.max[0] - bounds.min[0], 1)
        drawing_h = max(bounds.max[1] - bounds.min[1], 1)
        # Vista alta (poste/totem) ganha folha A2 retrato; as demais preservam
        # A2 paisagem. Isso ocupa a página de verdade sem comprimir o desenho.
        page_w, page_h = (PAGE_H, PAGE_W) if drawing_h / drawing_w > 1.15 else (PAGE_W, PAGE_H)
        c.setPageSize((page_w * mm, page_h * mm))
        _sheet_header(c, titles[name], model, meta, page_no, page_w, page_h)
        render_view_pdf(c, view, M + 8, 39, page_w - 2 * M - 16, page_h - 2 * M - 65,
                        pad_mm=padding)
        c.showPage()
    if page_no == 0:
        c.scale(mm, mm)   # página única fora do loop: aplica a escala em mm
        _sheet_header(c, "SEM VISTAS", model, meta, 1, PAGE_W, PAGE_H)
        _text(c, PAGE_W / 2, PAGE_H / 2, "Nenhuma geometria disponível para esta prancha.",
              size=6, anchor="center", color=GREY)
        c.showPage()
    c.save()
    return buf.getvalue()
