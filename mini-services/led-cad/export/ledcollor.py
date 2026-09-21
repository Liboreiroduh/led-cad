"""Prancha final LED Collor — template visual + planejador dinâmico de folhas.

Fluxo:
ProjectModel → projeções/cotas (drawing.*) → planejador de folhas → template LED Collor → PDF
Não fixa geometria (V, duas faces, medidas). O número de folhas e seus
conteúdos acompanham o projeto real.
"""
from __future__ import annotations
import io
import math
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from reportlab.lib.colors import HexColor, red
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from core.bom import build_bom
from drawing.projections import View2D, project_view
from drawing.dimensions import add_dimensions, view_title
from models.element import ProjectModel

# ---------------------------------------------------------------------------
# Paleta / métrica visual (padrão LED Collor: branco, grafite, acento teal)
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = 594.0, 420.0  # A2 paisagem em mm
M = 12.0  # margem interna
INK = HexColor("#1f2937")  # grafite escuro
GREY = HexColor("#6b7280")  # cinza médio
ACCENT = HexColor("#0f766e")  # teal LED Collor
LIGHT = HexColor("#e5e7eb")  # linha fina
COTA = HexColor("#b45309")  # cor das cotas (herdada do exporter técnico)
SIDEBAR_X = PAGE_W - M - 72  # início da coluna lateral direita (mais larga)


def _line(c: rl_canvas.Canvas, x1: float, y1: float, x2: float, y2: float,
          w: float = 0.25, color: Any = INK, dash: Optional[Tuple[int, int]] = None) -> None:
    """Desenha uma linha com cores e estilo configuráveis."""
    c.setStrokeColor(color)
    c.setLineWidth(w)
    if dash:
        c.setDash(dash)
    c.line(x1, y1, x2, y2)
    if dash:
        c.setDash()


def _text(c: rl_canvas.Canvas, x: float, y: float, s: str, size: float = 3.0,
          color: Any = INK, bold: bool = False, anchor: str = "left") -> None:
    """Desenha texto com alinhamento e formatação configuráveis."""
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    if anchor == "center":
        c.drawCentredString(x, y, s)
    elif anchor == "right":
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)


# ---------------------------------------------------------------------------
# Planejador de folhas (dinâmico, baseado na geometria real)
# ---------------------------------------------------------------------------
class SheetSpec:
    """Especificação mínima de uma folha da prancha."""
    def __init__(self, title: str, subtitle: str, view_name: str,
                 subject: Optional[str] = None, dimensions: str = "auto"):
        self.title = title
        self.subtitle = subtitle
        self.view_name = view_name  # FRONTAL | LATERAL | SUPERIOR | ISOMETRICA | …
        self.subject = subject  # FACE-A, FACE-B, POSTES, BASE, …
        self.dimensions = dimensions  # "auto" usa add_dimensions padrão


def plan_sheets(model: ProjectModel) -> List[SheetSpec]:
    """Decide quais vistas merecem folha a partir da geometria atual."""
    sheets: List[SheetSpec] = []

    # 1) Elevações principais (sempre que houver elementos nessa orientação)
    has_frontal = any(e.type == "beam" and e.start and e.end
                      for e in model.elements)
    if has_frontal:
        sheets.append(SheetSpec(
            title="ELEVAÇÃO PRINCIPAL",
            subtitle="VISTA FRONTAL",
            view_name="FRONTAL",
        ))

    # 2) Faces adicionais (FACE-B, FACE-C, …) — detectadas por grupo
    face_groups = sorted({
        e.group for e in model.elements
        if e.group and e.group.upper().startswith("FACE-")
    })
    for fg in face_groups:
        sheets.append(SheetSpec(
            title=f"ELEVAÇÃO {fg.replace('FACE-', 'FACE ')}",
            subtitle=f"VISTA DA ESTRUTURA {fg}",
            view_name="FRONTAL",  # reutiliza frontal; filtro por grupo fica pra v2
        ))

    # 3) Vista lateral (quando há profundidade relevante)
    has_depth = any(abs(e.end.y - e.start.y) > 50
                    for e in model.elements if e.type == "beam" and e.start and e.end)
    if has_depth:
        sheets.append(SheetSpec(
            title="VISTA LATERAL",
            subtitle="PROFUNDIDADE / SUPORTES",
            view_name="LATERAL",
        ))

    # 4) Planta superior (sempre útil para entender disposição em X/Y)
    sheets.append(SheetSpec(
        title="VISTA SUPERIOR / PLANTA",
        subtitle="GEOMETRIA DA ESTRUTURA",
        view_name="SUPERIOR",
    ))

    # 5) Detalhes relevantes (base, poste, passarela) — um por tipo quando existir
    has_posts = any(e.role == "post" for e in model.elements)
    if has_posts:
        sheets.append(SheetSpec(
            title="DETALHE DO POSTE",
            subtitle="ALTURAS E FIXAÇÃO",
            view_name="FRONTAL",  # recorta no zoom; por ora reusa frontal
        ))

    has_bases = any(e.type == "plate" and e.role == "base" for e in model.elements)
    if has_bases:
        sheets.append(SheetSpec(
            title="DETALHE DA BASE",
            subtitle="PLACA DE ANCORAGEM",
            view_name="SUPERIOR",
        ))

    # 6) Isométrica / perspectiva (sempre fecha o documento)
    sheets.append(SheetSpec(
        title="PERSPECTIVA ISOMÉTRICA",
        subtitle="VISTA EM PERSPECTIVA",
        view_name="ISOMETRICA",
    ))

    return sheets


# ---------------------------------------------------------------------------
# Template visual LED Collor (moldura, títulos, coluna lateral, aviso)
# ---------------------------------------------------------------------------
def _draw_frame(c: rl_canvas.Canvas, page_w: float, page_h: float) -> None:
    """Moldura técnica fina + separação da coluna lateral."""
    _line(c, M, M, page_w - M, M, w=0.8)
    _line(c, M, M, M, page_h - M, w=0.8)
    _line(c, page_w - M, M, page_w - M, page_h - M, w=0.8)
    _line(c, M, page_h - M, page_w - M, page_h - M, w=0.8)
    # divisor da coluna lateral
    _line(c, SIDEBAR_X, M, SIDEBAR_X, page_h - M, w=0.45)


def _draw_header(c: rl_canvas.Canvas, page_w: float, page_h: float,
                 title: str, subtitle: str) -> None:
    """Título grande + subtítulo no topo da área útil."""
    _text(c, M + 4, page_h - M - 10, title, size=7.5, bold=True, color=ACCENT)
    _text(c, M + 4, page_h - M - 18, subtitle, size=4.2, color=GREY)


def _draw_sidebar(c: rl_canvas.Canvas, page_w: float, page_h: float,
                  sheet_no: int, total_sheets: int,
                  meta: Dict[str, str]) -> None:
    """Coluna lateral direita: logo, unidades, folha, contato."""
    sx = SIDEBAR_X + 6
    top_y = page_h - M - 10

    # Logo placeholder (área reservada maior)
    _text(c, sx, top_y, "LED COLLOR", size=8.0, bold=True, color=ACCENT)
    _line(c, sx, top_y - 4, sx + 58, top_y - 4, w=0.4, color=ACCENT)

    # Site / Instagram
    _text(c, sx, top_y - 14, "ledcollor.com.br", size=3.0, color=GREY)
    _text(c, sx, top_y - 19, "@ledcollor", size=3.0, color=GREY)

    # Unidades
    _text(c, sx, top_y - 32, "UNIDADES", size=2.8, bold=True)
    _text(c, sx, top_y - 37, "mm", size=3.6, bold=True, color=INK)

    # Folha (destaque maior)
    _text(c, sx, top_y - 52, "FOLHA", size=2.8, bold=True)
    _text(c, sx, top_y - 59, f"{sheet_no:02d}/{total_sheets:02d}",
          size=5.0, bold=True, color=INK)

    # Data
    _text(c, sx, top_y - 74, date.today().strftime("%d/%m/%Y"),
          size=2.8, color=GREY)


def _draw_footer(c: rl_canvas.Canvas, page_w: float) -> None:
    """Aviso técnico em vermelho no rodapé."""
    fy = M + 8
    _text(c, M, fy,
          "ESBOÇO DE REFERÊNCIA GEOMÉTRICO — SOMENTE PARA A EMPRESA RESPONSÁVEL PELA CRIAÇÃO",
          size=3.2, bold=True, color=red)
    _text(c, M, fy - 6,
          "Este é apenas um esboço de referência geométrico. Não utilizar para fabricação sem revisão.",
          size=2.6, color=HexColor("#b91c1c"))


# ---------------------------------------------------------------------------
# Renderização de vista com FIT-TO-PAGE real (transformação manual)
# ---------------------------------------------------------------------------
def _primitive_bounds(prims):
    """Bounds of what is actually rendered, in projection millimetres."""
    from reportlab.pdfbase.pdfmetrics import stringWidth, getAscentDescent
    points = []
    for p in prims:
        k = p["k"]
        if k == "line":
            points.extend((p["a"], p["b"]))
        elif k == "circle":
            x, y = p["c"]
            r = abs(p["r"])
            points.extend(((x-r, y-r), (x+r, y+r)))
        elif k in ("polygon", "polyline"):
            points.extend(p.get("points", []))
        elif k == "text":
            size = p["s"]
            width = stringWidth(p["t"], "Helvetica", size)
            asc, desc = getAscentDescent("Helvetica", size)
            anchor = p.get("anchor", "middle")
            left = 0 if anchor == "start" else (-width if anchor == "end" else -width/2)
            angle = math.radians(p.get("rot", 0))
            co, si = math.cos(angle), math.sin(angle)
            x, y = p["p"]
            points.extend((x+u*co-v*si, y+u*si+v*co)
                          for u in (left, left+width) for v in (desc, asc))
    if not points:
        return None
    return (min(x for x, y in points), min(y for x, y in points),
            max(x for x, y in points), max(y for x, y in points))


def _fit_primitives(view):
    """Keep remote datum dimensions as notes instead of fitting empty space.

    Only dimension primitives outside the actual drawing envelope are
    compacted; structural geometry is never removed or transformed separately.
    """
    geometry = [p for p in view.prims if p.get("layer") not in
                ("cota", "texto", "label", "eixo") and p["k"] != "text"]
    bounds = _primitive_bounds(geometry)
    if bounds is None:
        return view.prims
    x0, y0, x1, y1 = bounds
    span = max(x1-x0, y1-y0, 1)
    allowance = span * 0.3
    result, notes = [], []
    for prim in view.prims:
        b = _primitive_bounds([prim])
        remote = b and (b[0] < x0-allowance or b[2] > x1+allowance or
                        b[1] < y0-allowance or b[3] > y1+allowance)
        if prim.get("layer") == "cota" and remote:
            if prim["k"] == "text":
                notes.append(prim["t"])
            continue
        result.append(prim)
    if notes:
        kept = _primitive_bounds(result) or bounds
        result.append({"k": "text", "p": ((kept[0]+kept[2])/2, kept[1]-span*.08),
                       "s": max(30.0, span*.016), "anchor": "middle", "layer": "cota",
                       "t": "Cota externa ao enquadramento: " +
                            "; ".join(dict.fromkeys(notes)) + " mm"})
    return result if notes else view.prims


def render_view_on_sheet(c: rl_canvas.Canvas, view: View2D,
                         x: float, y: float, w: float, h: float,
                         pad_mm: float = 0.0) -> None:
    """Viewport in sheet mm; primitives in model mm. One uniform transform.

    pad_mm remains accepted for compatibility; fitting uses a paper-space
    margin rather than a fixed model-space pad that penalizes small views.
    Caller establishes the mm-to-point conversion once per page.
    """
    prims = _fit_primitives(view)
    bounds = _primitive_bounds(prims)
    if bounds is None or w <= 0 or h <= 0:
        return
    x0, y0, x1, y1 = bounds
    margin = min(w, h) * 0.025
    scale = min((w-2*margin)/max(x1-x0, 1e-6),
                (h-2*margin)/max(y1-y0, 1e-6))
    ox = x+w/2-(x0+x1)/2*scale
    oy = y+h/2-(y0+y1)/2*scale
    colors = {"perfil": INK, "perfil2": GREY, "poste": INK,
              "chapa": HexColor("#4b5563"), "painel": HexColor("#9ca3af"),
              "cota": COTA, "texto": INK, "label": ACCENT,
              "eixo": HexColor("#cbd5e1")}
    c.saveState()
    clip = c.beginPath()
    clip.rect(x, y, w, h)
    c.clipPath(clip, stroke=0)
    c.translate(ox, oy)
    c.scale(scale, scale)
    for p in prims:
        k = p["k"]
        col = colors.get(p.get("layer", "perfil"), INK)
        # Paper-space minimum stroke, without changing geometry or text size.
        lw = max(p.get("w", 1.0), 0.18/scale)
        c.setStrokeColor(col)
        c.setLineWidth(lw)
        c.setDash([1.2/scale, 1.2/scale] if p.get("dash") else [])
        if k == "line":
            c.line(*p["a"], *p["b"])
        elif k == "circle":
            c.circle(*p["c"], p["r"], stroke=1, fill=0)
        elif k in ("polygon", "polyline") and p.get("points"):
            path = c.beginPath()
            path.moveTo(*p["points"][0])
            for point in p["points"][1:]:
                path.lineTo(*point)
            if k == "polygon":
                path.close()
            c.drawPath(path, stroke=1, fill=0)
        elif k == "text":
            c.saveState()
            c.translate(*p["p"])
            c.rotate(p.get("rot", 0))
            anchor = {"middle": "center", "start": "left", "end": "right"}.get(
                p.get("anchor", "middle"), "center")
            _text(c, 0, 0, p["t"], size=p["s"], color=col, anchor=anchor)
            c.restoreState()
    c.restoreState()


# ---------------------------------------------------------------------------
# Montagem da prancha completa
# ---------------------------------------------------------------------------
def build_presentation_pdf(model: ProjectModel,
                           meta: Optional[Dict[str, Any]] = None) -> bytes:
    """Gera o PDF de apresentação no padrão visual LED Collor."""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W * mm, PAGE_H * mm))

    meta = meta or {}
    sheets = plan_sheets(model)
    total = len(sheets) or 1

    for idx, spec in enumerate(sheets, start=1):
        c.scale(mm, mm)  # showPage resets CTM; sheet helpers expect mm.
        # --- moldura / header / sidebar ---
        _draw_frame(c, PAGE_W, PAGE_H)
        _draw_header(c, PAGE_W, PAGE_H, spec.title, spec.subtitle)
        _draw_sidebar(c, PAGE_W, PAGE_H, idx, total, meta)

        # --- gera a vista vetorial + cotas ---
        view = project_view(model, spec.view_name, labels=True)
        if spec.dimensions == "auto":
            add_dimensions(model, view, spec.view_name)

        # área útil (exclui coluna lateral e espaço para título/rodapé)
        useful_w = SIDEBAR_X - M - 12
        useful_h = PAGE_H - 2 * M - 48

        render_view_on_sheet(c, view, M + 6, M + 18, useful_w, useful_h)

        # --- rodapé ---
        _draw_footer(c, PAGE_W)
        c.showPage()

    c.save()
    return buf.getvalue()