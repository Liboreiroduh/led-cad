"""Exportação DXF (ezdxf) — mesma geometria, escala 1:1 em mm."""
from __future__ import annotations

import io
from typing import List

import ezdxf
from ezdxf.enums import TextEntityAlignment

from drawing.projections import View2D

_LAYER_DEFS = [  # (nome, cor ACI)
    ("PERFIS", 7), ("PERFIS2", 8), ("POSTE", 5), ("CHAPAS", 4),
    ("PAINEL", 9), ("COTAS", 2), ("TEXTOS", 3), ("HACHURA", 8),
]

_LAYER_MAP = {
    "perfil": "PERFIS", "perfil2": "PERFIS2", "poste": "POSTE",
    "chapa": "CHAPAS", "hachura": "HACHURA", "painel": "PAINEL",
    "cota": "COTAS",
    "texto": "TEXTOS", "label": "TEXTOS", "eixo": "TEXTOS",
}


def _new_doc() -> "ezdxf.document":
    doc = ezdxf.new("R2010", setup=True)
    for name, color in _LAYER_DEFS:
        doc.layers.add(name, color=color)
    return doc


def _draw_view(msp, view: View2D, ox: float = 0.0, oy: float = 0.0) -> None:
    for prim in view.prims:
        layer = _LAYER_MAP.get(prim.get("layer", "perfil"), "PERFIS")
        k = prim["k"]
        if k == "line":
            a, b = prim["a"], prim["b"]
            msp.add_line((a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy),
                         dxfattribs={"layer": layer})
        elif k == "circle":
            c, r = prim["c"], prim["r"]
            msp.add_circle((c[0] + ox, c[1] + oy), r, dxfattribs={"layer": layer})
        elif k == "text":
            p = prim["p"]
            t = msp.add_text(prim["t"], dxfattribs={"layer": layer, "height": prim["s"]})
            t.set_placement((p[0] + ox, p[1] + oy), align=TextEntityAlignment.LEFT)


def view_to_dxf(views: List[View2D], offsets: dict[str, tuple[float, float]]) -> "ezdxf.document":
    doc = _new_doc()
    msp = doc.modelspace()
    for view in views:
        ox, oy = offsets.get(view.name, (0.0, 0.0))
        _draw_view(msp, view, ox, oy)
    return doc


def view_to_dxf_bytes(view: View2D, doc_meta: dict[str, str] | None = None) -> bytes:
    """DXF de UMA vista em bytes (arquivo separado por vista, p/ zip).

    A vista é reposicionada para a origem (bounding → 0,0) para abrir
    "zoom extents" limpo no AutoCAD."""
    doc = _new_doc()
    msp = doc.modelspace()
    if view.box.valid:
        ox, oy = -view.box.min[0], -view.box.min[1]
    else:
        ox, oy = 0.0, 0.0
    _draw_view(msp, view, ox, oy)
    meta = doc_meta or {}
    try:
        md = doc.ezdxf_metadata()
        md["CREATED_BY"] = meta.get("author", "LED STRUCTURE CAD")
        if meta.get("title"):
            md["SUBJECT"] = meta["title"]
    except Exception:
        pass  # metadados são opcionais
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")
