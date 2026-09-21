"""Pacote completo de ENTREGA (.zip) — 100% Python.

Um único download com tudo que o serralheiro/o cliente precisa:
  LEIAME.txt ................ manifesto com conteúdo e avisos
  projeto.pdf ............... prancha técnica A2 (vistas + BOM)
  dxf/FRONTAL.dxf … ......... 5 vistas em DXF separados (zoom extents limpo)
  plano_de_corte.pdf ........ folha de serralheria (réguas de corte)
  plano_de_corte.csv ........ plano de corte em CSV
  lista_materiais.csv ....... BOM com pesos e custos
  projeto.json .............. modelo paramétrico (reimportável no app)
  modelo_3d.gltf ............ cena 3D (Blender/three.js)

Reaproveita os MESMOS builders das rotas individuais — zero lógica nova
de geometria/custo (fonte única de verdade).
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import date
from typing import Any, Dict

from models.element import ProjectModel


def _bom_csv(model: ProjectModel, bom: Dict[str, Any]) -> str:
    """Mesmo formato do endpoint /api/export/bom.csv (Excel ; e BOM UTF-8)."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["POS", "DESCRICAO", "COMPR", "UNID", "QUANT",
                "PESO UNIT", "PESO TOTAL (kg)", "CUSTO TOTAL (R$)"])
    for it in bom["items"]:
        w.writerow([f"{it['pos']:02d}", it["descr"], it["compr"], it["unid"],
                    it["quant"], it["peso_unit"],
                    f"{it['peso_total']:.2f}".replace(".", ","),
                    f"{it.get('custo_total', 0):.2f}".replace(".", ",")])
    w.writerow([])
    w.writerow(["", "PESO TOTAL GERAL", "", "", "", "",
                f"{bom['total_mass_kg']:.2f}".replace(".", ","),
                f"{bom['total_cost_brl']:.2f}".replace(".", ",")])
    w.writerow([])
    w.writerow(["AVISO", "PROJETO SOMENTE PARA ORCAMENTO - NAO UTILIZAR PARA FABRICACAO"])
    p = bom.get("pricing", {})
    w.writerow(["REF", f"PERFIL R$ {p.get('steel_profile_brl_kg', 0):.2f}/kg + "
                       f"CHAPA R$ {p.get('steel_plate_brl_kg', 0):.2f}/kg + "
                       f"PINTURA R$ {p.get('paint_brl_kg', 0):.2f}/kg + "
                       f"PERDA {int((p.get('waste_factor', 1) - 1) * 100)}%"])
    return "\ufeff" + buf.getvalue()


def _cutlist_csv(cl: Dict[str, Any], bar_len: float) -> str:
    """Mesmo formato do endpoint /api/export/cutlist.csv."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["PERFIL", "DESCRICAO", "PECA (mm)", "QTD", "TOTAL (m)",
                f"BARRAS {int(bar_len / 1000)}M", "SOBRA %"])
    for g in cl["groups"]:
        for p in g["pieces"]:
            w.writerow([g["profile"], g["label"], p["len_mm"], p["qty"],
                        f"{g['total_m']:.2f}".replace(".", ","),
                        g["bars"], f"{g['waste_pct']:.1f}".replace(".", ",")])
    w.writerow([])
    w.writerow(["TOTAL", "", "", "", "", cl["total_bars"], ""])
    w.writerow([])
    w.writerow(["PLANO POR BARRA (primeiras de cada perfil)"])
    for g in cl["groups"]:
        for i, bar in enumerate(g.get("bar_plan", []), 1):
            w.writerow([f"{g['profile']} barra {i}",
                        " + ".join(f"{p}mm" for p in bar["pieces"]),
                        f"sobra {bar['rest_mm']}mm"])
    return "\ufeff" + buf.getvalue()


def build_package_zip(model: ProjectModel, views: Dict[str, Any],
                      bom: Dict[str, Any], bar_len: float = 6000.0,
                      preset_name: str = "") -> bytes:
    """Monta o .zip de entrega com todos os artefatos do projeto atual."""
    from core.cutlist import build_cutlist
    from drawing.dxf import view_to_dxf_bytes
    from export.cutlist_pdf import build_cutlist_pdf
    from export.gltf import build_gltf
    from export.pdf import build_pdf

    meta_pdf = {
        "obra": model.project.name or preset_name or "PAINEL LED",
        "obra_short": (preset_name or "PAINEL LED OUTDOOR")[:24].upper(),
        "sheet": "LC-FL01",
        "number": "LC-2024-001",
    }
    projeto_pdf = build_pdf(model, views, meta=meta_pdf)

    dxf_meta = {"author": "LED STRUCTURE CAD",
                "title": model.project.name or "estrutura LED"}

    cl = build_cutlist(model, bar_len)
    cut_pdf = build_cutlist_pdf(cl, project_name=model.project.name,
                                preset_id=preset_name or "")

    leiame = (
        "LED STRUCTURE CAD — PACOTE DE ENTREGA\n"
        "=====================================\n"
        f"Projeto: {model.project.name or '-'}\n"
        + (f"Preset base: {preset_name}\n" if preset_name else "")
        + f"Data do pacote: {date.today().strftime('%d/%m/%Y')}\n"
        f"Elementos: {len(model.elements)} · Painel: "
        f"{model.panel.width:.0f}×{model.panel.height:.0f}×{model.panel.depth:.0f} mm · "
        f"Instalação: {model.installation.type}\n"
        f"Peso total: {bom.get('total_mass_kg', 0):.1f} kg · "
        f"Custo estimado: R$ {bom.get('total_cost_brl', 0):.2f}\n"
        "\n"
        "CONTEÚDO\n"
        "--------\n"
        "  projeto.pdf ............ prancha técnica A2 (vistas + lista de materiais)\n"
        "  dxf/ ................... 5 vistas em DXF 1:1 (mm) + LEIAME_DXF.txt\n"
        f"  plano_de_corte.pdf ..... folha de serralheria (barra {int(bar_len/1000)} m)\n"
        f"  plano_de_corte.csv ..... plano de corte em CSV (barra {int(bar_len/1000)} m)\n"
        "  lista_materiais.csv .... BOM com pesos e custos (Excel)\n"
        "  projeto.json ........... modelo paramétrico — reimporte no app (⤒)\n"
        "  modelo_3d.gltf ......... cena 3D (Blender/three.js/Babylon)\n"
        "\n"
        "⚠ PROJETO SOMENTE PARA ORÇAMENTO — não substitui cálculo estrutural\n"
        "  nem ART. Confira as medidas antes de cortar.\n"
    )
    leiame_dxf = (
        "DXF por vista (1:1, mm, geometria na origem — zoom extents limpo):\n"
        + "".join(f"  {n}.dxf\n" for n in views)
        + "Camadas: PERFIS, PERFIS2, POSTE, CHAPAS, HACHURA, PAINEL, COTAS, TEXTOS.\n"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("LEIAME.txt", leiame)
        z.writestr("projeto.pdf", projeto_pdf)
        for name, view in views.items():
            z.writestr(f"dxf/{name}.dxf", view_to_dxf_bytes(view, dxf_meta))
        z.writestr("dxf/LEIAME_DXF.txt", leiame_dxf)
        z.writestr("plano_de_corte.pdf", cut_pdf)
        z.writestr("plano_de_corte.csv", _cutlist_csv(cl, bar_len))
        z.writestr("lista_materiais.csv", _bom_csv(model, bom))
        z.writestr("projeto.json",
                   __import__("json").dumps(model.model_dump(), ensure_ascii=False, indent=1))
        z.writestr("modelo_3d.gltf", build_gltf(model))
    return buf.getvalue()
