"""LED STRUCTURE CAD — FastAPI (fonte de verdade Python).

Sobe: uvicorn main:app --host 0.0.0.0 --port 3100 --reload
Serve o frontend estático (HTML/CSS/JS vanilla + Three.js) e a API.
"""
from __future__ import annotations

import re
from datetime import date

from reportlab.lib.colors import HexColor as _rl_color
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core import bom as bom_mod
from core.cutlist import build_cutlist, normalize_bar_len
from core.operations import OperationError, ProjectStore, apply_operation
from core.select import marquee_frustum, marquee_select
from core.snap import snap_point
from core.wind import estimate_wind, normalize_direction, normalize_obstruction
from drawing.dimensions import add_dimensions
from drawing.projections import project_view
from drawing.svg import render_svg
from models.element import ProjectModel
from models.profile import CATALOG
from services import project_service, pricing_service, preset_service
from services.ai_service import HELP_TEXT, execute_command, execute_ops, parse_command
from services.preset_service import list_presets, load_preset
from services.project_service import (
    delete_version, diff_two_saved, diff_version_vs_current,
    load_version, read_versions,
)

app = FastAPI(title="LED STRUCTURE CAD", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

STORE = ProjectStore()

VIEW_NAMES = ["FRONTAL", "TRASEIRA", "LATERAL", "SUPERIOR", "INFERIOR", "ISOMETRICA"]
SVG_VIEWS = ["FRONTAL", "TRASEIRA", "LATERAL", "SUPERIOR", "INFERIOR"]


def build_views(model, names=None, titles: bool = True):
    out = {}
    for name in (names or SVG_VIEWS):
        v = project_view(model, name)
        add_dimensions(model, v, name)
        if titles:
            from drawing.dimensions import view_title
            view_title(v)
        out[name] = v
    return out


def bom_full(model):
    """BOM + estimativa de vento (uma única assinatura p/ todo o app)."""
    b = bom_mod.build_bom(model)
    try:
        b["wind"] = estimate_wind(model)
    except Exception:
        b["wind"] = None
    return b


# ------------------------------------------------------------------ API

class NewProjectIn(BaseModel):
    preset_id: str = "REF_4000X2000"
    overrides: Optional[Dict[str, Any]] = None


class OperationIn(BaseModel):
    operation: str
    element_id: Optional[str] = None
    payload: Dict[str, Any] = {}


@app.get("/api/health")
def health():
    model = STORE.ensure_loaded()
    return {"ok": True, "service": "led-cad", "elements": len(model.elements),
            "preset_id": STORE.preset_id,
            "revision": STORE.revision, "project_id": STORE.project_id,
            "persist_state": STORE.persist_state}


@app.get("/api/meta")
def meta():
    return {
        "profiles": [
            {"name": p.name, "label": p.label, "kind": p.kind, "w": p.w, "h": p.h,
             "t": p.t, "kgm": p.kgm}
            for p in CATALOG.values()
        ],
        "ai_help": HELP_TEXT,
        "warnings": [
            "PROJETO SOMENTE PARA ORÇAMENTO — NÃO UTILIZAR PARA FABRICAÇÃO.",
            "Esta ferramenta não substitui cálculo estrutural, ART ou engenheiro.",
        ],
    }


@app.get("/api/presets")
def get_presets():
    return list_presets()


@app.post("/api/project/new")
def new_project(body: NewProjectIn):
    try:
        model = STORE.new_from_preset(body.preset_id, body.overrides)
    except OperationError as e:
        raise HTTPException(400, str(e))
    return {"model": model.model_dump(), "bom": bom_full(model)}


class ImportIn(BaseModel):
    model_config = {"extra": "allow"}
    data: Optional[Dict[str, Any]] = None


@app.post("/api/project/regen")
def regen_project(body: NewProjectIn):
    """Regenera o preset atual com novos parâmetros — MANTÉM o undo.

    Diferente de /new (troca de projeto): aqui o usuário só ajustou
    parâmetros do MESMO projeto, então a ação é desfazível.
    """
    try:
        model = STORE.new_from_preset(body.preset_id or STORE.preset_id or "REF_4000X2000",
                                      body.overrides, keep_undo=True, undo_action="regen")
    except OperationError as e:
        raise HTTPException(400, str(e))
    return {"model": model.model_dump(), "bom": bom_full(model),
            "preset_id": STORE.preset_id, "can_undo": STORE.can_undo}


@app.post("/api/project/import")
def import_project(body: ImportIn):
    """Importa um projeto JSON (mesmo formato do /api/export/json).

    Aceita o modelo puro OU um envelope {"model": …}. Valida com o
    ProjectModel (Pydantic) — qualquer elemento fora do schema rejeita
    a importação com mensagem clara. Undo é limpo (nova sessão)."""
    raw = body.data if isinstance(body.data, dict) else body.model_dump(exclude_none=True)
    raw = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    if isinstance(raw.get("model"), dict) and "elements" not in raw:
        raw = raw["model"]  # envelope de sessão {model, preset_id, ...}
    if not isinstance(raw, dict) or "elements" not in raw:
        raise HTTPException(400, "JSON sem 'elements' — este arquivo não é um "
                                 "projeto do LED STRUCTURE CAD.")
    try:
        model = ProjectModel(**raw)
    except Exception as e:
        detail = str(e).replace("\n", " ")[:300]
        raise HTTPException(400, f"JSON de projeto inválido: {detail}")
    if not model.elements:
        raise HTTPException(400, "O projeto importado não tem elementos.")
    # valida PERFIS contra o catálogo (Pydantic valida o schema, não os nomes)
    from models.profile import get_profile
    bad: List[str] = []
    for el in model.elements:
        if not el.profile:
            continue
        try:
            get_profile(el.profile)
        except KeyError:
            bad.append(el.profile)
    if bad:
        uniq = sorted(set(bad))
        raise HTTPException(
            422, f"Perfis não encontrados no catálogo: {', '.join(uniq)}. "
                 f"Corrija o JSON (os nomes válidos estão em /api/meta) e importe novamente.")
    STORE.model = model
    STORE.preset_id = ""
    STORE._undo.clear()
    STORE.log("load", f"Projeto importado (JSON) — {len(model.elements)} elementos.")
    STORE._persist()
    return {"model": model.model_dump(), "bom": bom_full(model),
            "preset_id": "", "can_undo": False}


@app.get("/api/project")
def get_project():
    model = STORE.ensure_loaded()
    return {"model": model.model_dump(), "bom": bom_full(model),
            "preset_id": STORE.preset_id, "can_undo": STORE.can_undo}


@app.post("/api/operations")
def run_operation(op: Dict[str, Any]):
    try:
        summary = apply_operation(STORE, op)
    except OperationError as e:
        raise HTTPException(400, str(e))
    model = STORE.ensure_loaded()
    return {"summary": summary, "model": model.model_dump(),
            "bom": bom_full(model), "can_undo": STORE.can_undo}


@app.post("/api/undo")
def undo():
    try:
        STORE.undo()
    except OperationError as e:
        raise HTTPException(400, str(e))
    model = STORE.ensure_loaded()
    STORE.commit("undo")
    return {"model": model.model_dump(), "bom": bom_full(model),
            "can_undo": STORE.can_undo, "revision": STORE.revision,
            "project_id": STORE.project_id,
            "persist_state": STORE.persist_state}


# -------------------------------------------- compilador paramétrico (F2)
@app.post("/api/compile/preview")
def compile_preview(body: Dict[str, Any]):
    """Spec geométrica tipada → operações completas + diff de preview.

    NÃO MUTA: devolve ops + completeness + assumptions para o front
    aplicar via /api/ops/apply (com revisão-base/idempotência).
    """
    from services.parametric import compile_spec
    from core.ai_ops import dry_run_diff
    try:
        out = compile_spec(body)
        diff = dry_run_diff(STORE.ensure_loaded(), out["ops"])
    except OperationError as e:
        raise HTTPException(422, str(e))
    return {"ops": out["ops"], "panel": out["panel"],
            "completeness": out["completeness"],
            "assumptions": out["assumptions"],
            "op_count": out["op_count"], "diff": diff,
            "base_revision": STORE.revision,
            "project_id": STORE.project_id}


# -------------------------------------------- camada de operações (preview/aplicar)


class OpsBatchIn(BaseModel):
    operations: List[Dict[str, Any]] = []
    action: str = "ia"  # "ia" (copiloto) | "editor" (inspector/ferramentas)
    # F1: revisão-base + idempotência — plano antigo não é aplicado
    # silenciosamente sobre desenho novo; clique duplo gera 1 commit só.
    base_revision: Optional[int] = None
    idempotency_key: Optional[str] = None


@app.post("/api/ops/preview")
def ops_preview(body: OpsBatchIn):
    """SIMULA a lista de operações (IA ou editor) numa cópia do modelo e
    devolve o DIFF sem tocar no projeto — alimenta o preview no viewport:
    novos = translúcidos · movidos = original + fantasma · removidos = vermelho."""
    from core.ai_ops import dry_run_diff
    model = STORE.ensure_loaded()
    try:
        return dry_run_diff(model, body.operations)
    except OperationError as e:
        raise HTTPException(400, str(e))


@app.post("/api/ops/apply")
def ops_apply(body: OpsBatchIn):
    """Aplica o LOTE inteiro com UM snapshot de undo (histórico unificado:
    Ctrl+Z desfaz operações manuais e da IA da mesma pilha).
    Nunca deixa a IA tocar em meshes do Three.js — o fluxo é
    IA → operations → Python → modelo → nova geometria → Three.js."""
    from core.ai_ops import apply_batch
    if not body.operations:
        raise HTTPException(400, "Nenhuma operação para aplicar.")
    STORE.ensure_loaded()
    # F1: idempotência — mesma chave + mesmo payload devolve o resultado
    # original (clique duplo/repetição após resposta perdida = 1 commit).
    idem_key = body.idempotency_key
    if idem_key:
        cached = STORE.idempotency(idem_key, body.operations)
        if cached and cached.get("conflict"):
            raise HTTPException(409, "Chave de idempotência já usada com "
                                      "outra carga de operações.")
        if cached:
            return cached
    # F1: revisão-base — plano gerado sobre revisão antiga não é aplicado
    # sobre desenho novo (G11/G12); 409 explícito para regenerar preview.
    if body.base_revision is not None and body.base_revision != STORE.revision:
        raise HTTPException(409, f"Plano obsoleto: criado na revisão "
                                 f"{body.base_revision}, projeto está na "
                                 f"{STORE.revision}. Gere o preview novamente.")
    try:
        summary = apply_batch(STORE, body.operations,
                              action="ia" if body.action != "editor" else "editor")
    except OperationError as e:
        raise HTTPException(400, str(e))
    STORE.commit(f"apply {body.action}")
    model = STORE.ensure_loaded()
    res = {"summary": summary, "model": model.model_dump(),
           "bom": bom_full(model), "can_undo": STORE.can_undo,
           "revision": STORE.revision, "project_id": STORE.project_id,
           "persist_state": STORE.persist_state}
    if idem_key:
        STORE.remember(idem_key, body.operations, res)
    return res


@app.get("/api/bom")
def get_bom():
    return bom_full(STORE.ensure_loaded())


@app.get("/api/wind")
def wind(v0: float = Query(35.0, gt=0, le=60, description="velocidade básica V₀ (m/s)"),
         dir: str = Query("frontal", description="frontal | traseira | lateral"),
         obs: float = Query(0.0, ge=0.0, le=0.6,
                            description="abrigo por painéis vizinhos (0 a 0,6)")):
    """Estimativa de vento (raciocínio NBR 6123 simplificado).

    A direção muda o plano de projeção: frontal/traseira → largura×altura;
    lateral → profundidade×altura (só o perfil da treliça pega vento).
    `obs` é o abrigo por painéis vizinhos — reduz a força sobre o painel."""
    return estimate_wind(STORE.ensure_loaded(), v0, normalize_direction(dir),
                         normalize_obstruction(obs))


@app.get("/api/cutlist")
def cutlist(bar_len: float = Query(6000.0, ge=2000, le=15000,
                                   description="comprimento da barra comercial (mm)")):
    """Plano de corte por perfil (barras comerciais 4/6/8/12 m, FFD)."""
    return build_cutlist(STORE.ensure_loaded(), normalize_bar_len(bar_len))


@app.get("/api/views")
def get_views(all: bool = Query(False, description="incluir isométrica")):
    model = STORE.ensure_loaded()
    names = VIEW_NAMES if all else SVG_VIEWS
    views = build_views(model, names)
    return {name: render_svg(v, 660, 500) for name, v in views.items()}


@app.get("/api/views/{name}")
def get_view(name: str):
    if name.upper() not in VIEW_NAMES:
        raise HTTPException(404, "Vista inexistente.")
    model = STORE.ensure_loaded()
    v = project_view(model, name.upper())
    add_dimensions(model, v, name.upper())
    return Response(render_svg(v, 660, 500), media_type="image/svg+xml")


@app.get("/api/export/pdf")
def export_pdf():
    from export.pdf import build_pdf
    model = STORE.ensure_loaded()
    views = build_views(model, ["FRONTAL", "TRASEIRA", "LATERAL", "SUPERIOR", "ISOMETRICA"],
                        titles=False)
    preset = load_preset(STORE.preset_id or "REF_4000X2000")
    obra = preset["name"] if preset else model.project.name
    pdf = build_pdf(model, views, meta={
        "obra": model.project.name or obra,
        "obra_short": "PAINEL LED OUTDOOR",
        "sheet": "LC-FL01",
        "number": "LC-2024-001",
    })
    return Response(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="prancha_led_cad.pdf"'},
    )


@app.get("/api/export/pdf/presentation")
def export_ledcollor_presentation_pdf():
    """Prancha LED Collor: folhas e cotas derivadas da geometria atual."""
    from export.ledcollor import build_presentation_pdf

    model = STORE.ensure_loaded().model_copy(deep=True)
    project_id, revision = STORE.project_id, STORE.revision
    try:
        pdf = build_presentation_pdf(model, meta={
            "title": model.project.name or "Projeto LED",
            "project_id": project_id,
            "revision": revision,
        })
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(
        pdf, media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="prancha_ledcollor.pdf"',
            "Cache-Control": "no-store",
            "X-Project-Id": str(project_id),
            "X-Project-Revision": str(revision),
        },
    )


@app.get("/api/export/sheetpack")
def export_sheetpack():
    from export.sheetpack import build_sheetpack_pdf
    model = STORE.ensure_loaded()
    preset = load_preset(STORE.preset_id or "REF_4000X2000")
    obra = preset["name"] if preset else (model.project.name or "")
    pdf = build_sheetpack_pdf(model, meta={
        "obra": obra or model.project.name,
        "cliente": getattr(model.project, "client", "") or "",
    })
    return Response(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="prancha_fabricacao_7folhas.pdf"'},
    )


@app.get("/api/export/sheetpack/{n}.svg")
def export_sheetpack_svg(n: int):
    from export.sheetpack import build_sheet_svg
    model = STORE.ensure_loaded()
    preset = load_preset(STORE.preset_id or "REF_4000X2000")
    obra = preset["name"] if preset else (model.project.name or "")
    svg = build_sheet_svg(model, sheet_index=n - 1, meta={
        "obra": obra or model.project.name,
        "cliente": getattr(model.project, "client", "") or "",
    })
    return Response(svg, media_type="image/svg+xml")


@app.get("/api/export/presentation.pdf")
def export_presentation_pdf():
    """P3 — PDF de apresentação visual (cliente comercial): capa editorial,
    vistas frontais/lateral/superior em vetor (mesma projeção da prancha)
    e ficha do projeto — mesma revisão da prancha técnica."""
    import io
    from reportlab.lib.units import mm as _mm
    from reportlab.pdfgen import canvas as _cv

    model = STORE.ensure_loaded()
    p = model.panel
    gc = model.installation.ground_clearance

    buf = io.BytesIO()
    W, H = 210.0, 297.0
    c = _cv.Canvas(buf, pagesize=(W * _mm, H * _mm))
    c.scale(_mm, _mm)

    # capa editorial
    c.setFillColor(_rl_color("#1b2530"))
    c.rect(0, H - 60, W, 60, fill=1, stroke=0)
    c.setFillColor(_rl_color("#e8edf2"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(14, H - 32, (model.project.name or "PROJETO LED").upper())
    c.setFont("Helvetica", 8)
    c.drawString(14, H - 44, "Apresentação comercial · esboço geométrico")
    c.setFillColor(_rl_color("#e8730c"))
    c.rect(14, 26, 40, 2, fill=1, stroke=0)
    c.setFillColor(_rl_color("#5b6b7b"))
    c.setFont("Helvetica", 9)
    c.drawString(14, 18, f"Revisão {STORE.revision} · mm · "
                         f"{date.today().strftime('%d/%m/%Y')}")
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(_rl_color("#1e2833"))
    c.drawString(14, H - 90, "PAINEL")
    c.setFont("Helvetica", 10)
    c.setFillColor(_rl_color("#1e2833"))
    c.drawString(14, H - 104, f"{round(p.width)} × {round(p.height)} mm "
                              f"(face LED)")
    c.drawString(14, H - 118, f"Profundidade {round(p.depth or 0)} mm · "
                              f"altura ao solo {round(gc)} mm")
    groups: Dict[str, int] = {}
    for el in model.elements:
        groups[el.group or "—"] = groups.get(el.group or "—", 0) + 1
    y = H - 140
    c.setFont("Helvetica-Bold", 11)
    c.drawString(14, y, "CONTEÚDO ESTRUTURAL"); y -= 16
    c.setFont("Helvetica", 9)
    for g, n in list(groups.items())[:14]:
        c.drawString(18, y, f"{g}: {n}"); y -= 13
    c.setFillColor(_rl_color("#5b6b7b"))
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(14, 40, "Documento de apresentação — não é cálculo nem "
                         "aprovação estrutural.")
    c.showPage()

    # vistas em vetor
    try:
        from export.sheetpack import _render_view_into, _rl_color as _c2
    except ImportError:
        _c2 = None
    views = [("FRONTAL", "VISTA FRONTAL"), ("LATERAL", "VISTA LATERAL"),
             ("SUPERIOR", "VISTA SUPERIOR")]
    for vname, vtitle in views:
        c.setFillColor(_rl_color("#f2f4f7"))
        c.rect(0, 0, W, H, fill=1, stroke=0)
        try:
            v = project_view(model, vname)
            from export.sheetpack import _render_view_into
            _render_view_into(c, v, 10, 40, W - 20, H - 70, pad_mm=300.0)
        except Exception:
            c.setFillColor(_rl_color("#5b6b7b"))
            c.setFont("Helvetica", 10)
            c.drawCentredString(W / 2, H / 2, "Vista indisponível")
        c.setFillColor(_rl_color("#1e2833"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(14, H - 24, vtitle)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(_rl_color("#5b6b7b"))
        c.drawString(14, 16, f"{model.project.name or ''} · Revisão "
                             f"{STORE.revision} · mm")
        c.showPage()

    c.save()
    return Response(
        buf.getvalue(), media_type="application/pdf",
        headers={"Content-Disposition":
                 'attachment; filename="apresentacao_cliente.pdf"'},
    )


@app.get("/api/export/dxf")
def export_dxf():
    from drawing.dxf import view_to_dxf
    model = STORE.ensure_loaded()
    views = build_views(model, ["FRONTAL", "LATERAL", "SUPERIOR", "INFERIOR"], titles=False)
    # offsets simples lado a lado
    offsets = {
        "VISTA FRONTAL": (0.0, 0.0),
        "VISTA LATERAL": (6000.0, 0.0),
        "VISTA SUPERIOR": (12000.0, 0.0),
        "VISTA INFERIOR": (18000.0, 0.0),
    }
    doc = view_to_dxf(list(views.values()), offsets)
    import io
    buf = io.StringIO()
    doc.write(buf)
    data = buf.getvalue().encode("utf-8")
    return Response(
        data, media_type="image/vnd.dxf",
        headers={"Content-Disposition": 'attachment; filename="led_cad.dxf"'},
    )


@app.get("/api/export/dxf.zip")
def export_dxf_zip():
    """DXF por vista em ARQUIVOS SEPARADOS dentro de um .zip.

    Cada vista vira um .dxf independente (geometria levada à origem para
    abrir com zoom extents limpo) + LEIAME.txt com metadados do projeto."""
    import io
    import zipfile
    from datetime import date
    from drawing.dxf import view_to_dxf_bytes

    model = STORE.ensure_loaded()
    views = build_views(model, ["FRONTAL", "TRASEIRA", "LATERAL", "SUPERIOR", "INFERIOR"],
                        titles=False)
    meta = {
        "author": "LED STRUCTURE CAD",
        "title": model.project.name or "estrutura LED",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, view in views.items():
            data = view_to_dxf_bytes(view, meta)
            z.writestr(f"{name}.dxf", data)
        leiame = (
            "LED STRUCTURE CAD — DXF por vista\n"
            "=================================\n"
            f"Projeto: {model.project.name or '-'}\n"
            f"Data: {date.today().strftime('%d/%m/%Y')}\n"
            f"Elementos: {len(model.elements)}\n\n"
            "Arquivos:\n"
            + "".join(f"  {n}.dxf — vista {n.title()} (escala 1:1, mm, origem no canto)\n"
                      for n in views)
            + "\nCamadas: PERFIS, PERFIS2, POSTE, CHAPAS, HACHURA, PAINEL, COTAS, TEXTOS.\n"
              "Cada arquivo abre com zoom extents preenchendo a tela.\n"
        )
        z.writestr("LEIAME.txt", leiame)
    data = buf.getvalue()
    return Response(
        data, media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="led_cad_dxf_por_vista.zip"'},
    )


@app.get("/api/export/diff.pdf")
def export_diff_pdf(pid: str, other: Optional[str] = Query(
        None, description="projeto salvo do lado B — omitir para comparar com a sessão atual")):
    """PDF do comparativo A ↔ B entre projetos salvos (ou salvo ↔ atual)."""
    from export.diff_pdf import build_diff_pdf
    if other:
        result = diff_two_saved(pid, other)
    else:
        model = STORE.ensure_loaded()
        result = project_service.diff_saved_vs_current(pid, bom_mod.build_bom(model),
                                                       len(model.elements))
    if result is None:
        raise HTTPException(404, f"Projeto '{other or pid}' não encontrado.")
    if result.get("ok") is False:
        raise HTTPException(409, result.get("reason", "projeto sem snapshot de materiais"))
    pdf = build_diff_pdf(result)
    fname = f"comparativo_{pid}" + (f"_vs_{other}" if other else "_vs_atual") + ".pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@app.get("/api/export/json")
def export_json():
    model = STORE.ensure_loaded()
    return JSONResponse(model.model_dump(),
                        headers={"Content-Disposition": 'attachment; filename="projeto.json"'})


@app.get("/api/export/gltf")
def export_gltf():
    """Cena 3D em glTF 2.0 (abre em Blender/three.js/Babylon)."""
    from export.gltf import build_gltf
    model = STORE.ensure_loaded()
    data = build_gltf(model)
    return Response(
        data, media_type="model/gltf+json",
        headers={"Content-Disposition": 'attachment; filename="estrutura_led.gltf"'},
    )


@app.get("/api/export/package.zip")
def export_package_zip(bar_len: float = Query(6000.0, ge=2000, le=15000)):
    """PACOTE DE ENTREGA (.zip): prancha PDF + DXF por vista + plano de
    corte (PDF/CSV) + BOM CSV + projeto.json + GLTF + LEIAME — um clique
    baixa tudo que a serralheria/o cliente precisa."""
    from export.package import build_package_zip

    model = STORE.ensure_loaded()
    views = build_views(model, ["FRONTAL", "TRASEIRA", "LATERAL", "SUPERIOR", "INFERIOR"],
                        titles=False)
    bom = bom_full(model)
    preset = load_preset(STORE.preset_id or "REF_4000X2000")
    data = build_package_zip(model, views, bom, bar_len=normalize_bar_len(bar_len),
                             preset_name=preset["name"] if preset else "")
    import re as _re
    base = _re.sub(r"[^A-Za-z0-9_-]+", "_",
                   (model.project.name or "painel_led").strip()) or "painel_led"
    return Response(
        data, media_type="application/zip",
        headers={"Content-Disposition":
                 f'attachment; filename="entrega_{base[:60]}.zip"'},
    )


@app.get("/api/export/bom.csv")
def export_bom_csv():
    """Lista de materiais em CSV (abre direto no Excel)."""
    import csv
    import io

    model = STORE.ensure_loaded()
    bom = bom_mod.build_bom(model)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["POS", "DESCRICAO", "COMPR", "UNID", "QUANT", "PESO UNIT", "PESO TOTAL (kg)", "CUSTO TOTAL (R$)"])
    for it in bom["items"]:
        w.writerow([f"{it['pos']:02d}", it["descr"], it["compr"], it["unid"],
                    it["quant"], it["peso_unit"], f"{it['peso_total']:.2f}".replace(".", ","),
                    f"{it.get('custo_total', 0):.2f}".replace(".", ",")])
    w.writerow([])
    w.writerow(["", "PESO TOTAL GERAL", "", "", "", "", f"{bom['total_mass_kg']:.2f}".replace(".", ","),
                f"{bom['total_cost_brl']:.2f}".replace(".", ",")])
    w.writerow([])
    w.writerow(["AVISO", "PROJETO SOMENTE PARA ORCAMENTO - NAO UTILIZAR PARA FABRICACAO"])
    p = bom.get("pricing", {})
    w.writerow(["REF", f"PERFIL R$ {p.get('steel_profile_brl_kg', 0):.2f}/kg + CHAPA R$ {p.get('steel_plate_brl_kg', 0):.2f}/kg + PINTURA R$ {p.get('paint_brl_kg', 0):.2f}/kg + PERDA {int((p.get('waste_factor', 1) - 1) * 100)}%"])
    return Response(
        "\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="lista_materiais.csv"'},
    )


# ---------------------------------------------------- histórico


@app.get("/api/history")
def get_history(n: int = Query(40, ge=1, le=120)):
    STORE.ensure_loaded()
    return {"items": STORE.history_tail(n)}


# ---------------------------------------------------- parâmetros de orçamento


@app.get("/api/pricing")
def pricing_get():
    return pricing_service.get_pricing()


class PricingIn(BaseModel):
    steel_profile_brl_kg: Optional[float] = None
    steel_plate_brl_kg: Optional[float] = None
    paint_brl_kg: Optional[float] = None
    concrete_brl_kg: Optional[float] = None
    waste_factor: Optional[float] = None
    bolt_brl_unit_default: Optional[float] = None
    bolt_brl_unit_by_diameter: Optional[Dict[str, float]] = None


@app.put("/api/pricing")
def pricing_put(body: PricingIn):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    pricing_service.save_pricing(patch)
    model = STORE.ensure_loaded()
    return {"ok": True, "pricing": pricing_service.get_pricing(),
            "bom": bom_full(model)}


class PricingCsvIn(BaseModel):
    csv: str


@app.post("/api/pricing/import-csv")
def pricing_import_csv(body: PricingCsvIn):
    """Importa preços de um CSV textual ('perfil;14,90' por linha)."""
    try:
        result = pricing_service.import_pricing_csv(body.csv)
    except Exception as e:
        raise HTTPException(400, f"CSV inválido: {e}")
    if not result["applied"]:
        msg = "Nenhum preço reconhecido"
        if result["ignored"]:
            msg += ": " + ", ".join(result["ignored"][:5])
        raise HTTPException(400, msg + ".")
    model = STORE.ensure_loaded()
    return {"ok": True, **result, "pricing": pricing_service.get_pricing(),
            "bom": bom_full(model)}


# ---------------------------------------------------- projetos salvos


class SaveIn(BaseModel):
    name: Optional[str] = None


@app.get("/api/projects")
def projects_list():
    return project_service.list_projects()


@app.post("/api/projects/save")
def projects_save(body: SaveIn):
    model = STORE.ensure_loaded()
    # thumbnail (vista frontal) desenhado pelo motor Python
    try:
        v = project_view(model, "FRONTAL")
        thumb = render_svg(v, 320, 200)
    except Exception:
        thumb = None
    # snapshot do BOM — base do comparador de versões
    try:
        snap = project_service.bom_snapshot_from(bom_mod.build_bom(model), len(model.elements))
    except Exception:
        snap = None
    out = project_service.save_project(model, STORE.preset_id, body.name, thumb_svg=thumb,
                                       bom_snapshot=snap)
    extra = f" (v{out['version']} arquivada)" if out.get("version") else ""
    STORE.log("save", f"Projeto '{out['name']}' salvo{extra}.")
    return out


@app.get("/api/projects/{pid}/diff")
def projects_diff(pid: str, other: Optional[str] = Query(
        None, description="segundo projeto salvo — diff A ↔ B em vez de salvo ↔ atual")):
    """Comparador de versões: BOM do projeto SALVO vs. projeto ATUAL,
    ou — com `other` — entre DOIS projetos salvos (A ↔ B).

    Diffs calculados em Python (quantidade, peso e custo por item + totais)."""
    if other:
        result = diff_two_saved(pid, other)
    else:
        model = STORE.ensure_loaded()
        result = project_service.diff_saved_vs_current(pid, bom_mod.build_bom(model),
                                                       len(model.elements))
    if result is None:
        missing = other if (other and other == pid) else (other or pid)
        raise HTTPException(404, f"Projeto '{missing}' não encontrado.")
    return result


@app.get("/api/projects/{pid}/versions")
def projects_versions(pid: str):
    """Histórico de versões arquivadas do projeto (mais recente por último)."""
    if project_service.load_project(pid) is None and not read_versions(pid):
        raise HTTPException(404, f"Projeto '{pid}' não encontrado.")
    return {"id": pid, "versions": read_versions(pid),
            "max_versions": project_service.MAX_VERSIONS}


@app.get("/api/projects/{pid}/versions/spark.svg")
def projects_versions_spark(pid: str):
    """Mini-gráfico SVG da evolução de peso/custo pelas versões arquivadas
    (gerado 100% em Python — drawing/sparkline.py)."""
    from drawing.sparkline import versions_spark_svg
    if project_service.load_project(pid) is None and not read_versions(pid):
        raise HTTPException(404, f"Projeto '{pid}' não encontrado.")
    svg = versions_spark_svg(read_versions(pid))
    return Response(svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "no-cache"})


# ATENÇÃO: registrada ANTES da rota /versions/{v} — "export.zip" seria
# capturado pelo parse int de {v} e viraria 422.
@app.get("/api/projects/{pid}/versions/export.zip")
def projects_versions_zip(pid: str):
    """Exporta o histórico completo de versões do projeto como .zip
    (LEIAME + versoes/vN.json reimportáveis + evolucao.svg)."""
    data = project_service.build_versions_zip(pid)
    if data is None:
        raise HTTPException(404, f"Projeto '{pid}' não encontrado.")
    return Response(
        data, media_type="application/zip",
        headers={"Content-Disposition":
                 f'attachment; filename="historico_{pid}.zip"'})


@app.get("/api/projects/{pid}/versions/{v}")
def projects_version_load(pid: str, v: int):
    """Carrega uma versão arquivada na sessão (undo é limpo)."""
    entry = load_version(pid, v)
    if entry is None:
        raise HTTPException(404, f"Versão v{v} de '{pid}' não encontrada.")
    model = ProjectModel(**entry["model"])
    STORE.model = model
    STORE.preset_id = entry.get("preset_id", "")
    STORE._undo.clear()
    STORE.log("load", f"Versão v{v} de '{entry.get('name', pid)}' carregada "
                      f"({entry.get('saved_at', '')}).")
    STORE._persist()
    return {"model": model.model_dump(), "bom": bom_full(model),
            "preset_id": STORE.preset_id, "can_undo": False,
            "loaded_version": {"pid": pid, "v": v}}


@app.get("/api/projects/{pid}/versions/{v}/diff")
def projects_version_diff(pid: str, v: int):
    """Diff entre a versão arquivada (v) e o projeto ATUAL da sessão."""
    model = STORE.ensure_loaded()
    result = diff_version_vs_current(pid, v, bom_mod.build_bom(model),
                                     len(model.elements))
    if result is None:
        raise HTTPException(404, f"Versão v{v} de '{pid}' não encontrada.")
    return result


@app.get("/api/projects/{pid}/versions/{v}/diff.pdf")
def projects_version_diff_pdf(pid: str, v: int):
    """PDF do comparativo versão arquivada (A) ↔ projeto atual (B)."""
    from export.diff_pdf import build_diff_pdf
    model = STORE.ensure_loaded()
    result = diff_version_vs_current(pid, v, bom_mod.build_bom(model),
                                     len(model.elements))
    if result is None:
        raise HTTPException(404, f"Versão v{v} de '{pid}' não encontrada.")
    pdf = build_diff_pdf(result)
    fname = f"comparativo_{pid}_v{v}.pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@app.delete("/api/projects/{pid}/versions/{v}")
def projects_version_delete(pid: str, v: int):
    if not delete_version(pid, v):
        raise HTTPException(404, f"Versão v{v} de '{pid}' não encontrada.")
    STORE.log("delete_projeto", f"Versão v{v} de '{pid}' excluída do histórico.")
    return {"deleted": {"pid": pid, "v": v}, "versions": read_versions(pid)}


@app.get("/api/projects/{pid}/thumb.svg")
def projects_thumb(pid: str):
    p = project_service.thumb_path(pid)
    if p is None:
        raise HTTPException(404, "Thumbnail não encontrado.")
    return Response(p.read_text(encoding="utf-8"), media_type="image/svg+xml",
                    headers={"Cache-Control": "no-cache"})


@app.get("/api/projects/load/{pid}")
def projects_load(pid: str):
    data = project_service.load_project(pid)
    if data is None:
        raise HTTPException(404, f"Projeto '{pid}' não encontrado.")
    model = ProjectModel(**data["model"])
    STORE.model = model
    STORE.preset_id = data.get("preset_id", "")
    STORE._undo.clear()
    STORE.log("load", f"Projeto '{data.get('display_name', pid)}' carregado.")
    STORE._persist()
    return {"model": model.model_dump(), "bom": bom_full(model),
            "preset_id": STORE.preset_id, "can_undo": False}


@app.delete("/api/projects/{pid}")
def projects_delete(pid: str):
    if not project_service.delete_project(pid):
        raise HTTPException(404, f"Projeto '{pid}' não encontrado.")
    STORE.log("delete_projeto", f"Projeto salvo '{pid}' excluído.")
    return {"deleted": pid}


# ---------------------------------------------------- presets personalizados


class CustomPresetIn(BaseModel):
    name: str


@app.post("/api/presets/custom")
def presets_custom_save(body: CustomPresetIn):
    """Salva o projeto ATUAL como preset pessoal (template snapshot).

    Recarregar este preset restaura TODAS as edições (barras movidas,
    perfis trocados, elementos adicionados) — não só os parâmetros."""
    model = STORE.ensure_loaded()
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Informe um nome para o preset.")
    out = preset_service.save_custom_preset(name, model.model_dump(),
                                            STORE.preset_id or "")
    STORE.log("save", f"Preset personalizado '{out['name']}' criado "
                      f"({out['elements']} elementos).")
    return out


@app.delete("/api/presets/custom/{pid}")
def presets_custom_delete(pid: str):
    if not preset_service.delete_custom_preset(pid):
        raise HTTPException(404, f"Preset personalizado '{pid}' não encontrado.")
    STORE.log("delete_projeto", f"Preset personalizado '{pid}' excluído.")
    return {"deleted": pid}


# ---------------------------------------------------- snap / medição


class SnapIn(BaseModel):
    point: Dict[str, float]
    want_grid: bool = True
    want_endpoints: bool = True
    want_centers: bool = True
    want_edges: bool = True


@app.post("/api/snap")
def snap(body: SnapIn):
    """Snap determinístico (seção 17): extremidades > centros > aresta > grade."""
    return snap_point(STORE.ensure_loaded(), body.point, body.want_grid,
                      body.want_endpoints, body.want_centers, body.want_edges)


# ---------------------------------------------------- seleção (marquee)


class MarqueeIn(BaseModel):
    origin: Dict[str, float]
    right: Optional[Dict[str, float]] = None
    up: Optional[Dict[str, float]] = None
    u0: Optional[float] = None
    v0: Optional[float] = None
    u1: Optional[float] = None
    v1: Optional[float] = None
    # modo frustum (perspectiva): 4 direções de raio dos cantos
    dirs: Optional[List[Dict[str, float]]] = None


@app.post("/api/select/marquee")
def select_marquee(body: MarqueeIn):
    """Seleção por retângulo: a projeção/teste acontece no core Python.

    Com `dirs` (4 raios dos cantos) usa o tronco de pirâmide exato;
    sem `dirs`, cai no teste planar (right/up) p/ câmeras ortográficas.
    """
    def p3(d: Dict[str, float]):
        return (float(d.get("x", 0)), float(d.get("y", 0)), float(d.get("z", 0)))
    if body.dirs and len(body.dirs) == 4:
        return marquee_frustum(STORE.ensure_loaded(), p3(body.origin),
                               [p3(x) for x in body.dirs])
    if body.right and body.up and None not in (body.u0, body.v0, body.u1, body.v1):
        return marquee_select(STORE.ensure_loaded(), p3(body.origin),
                              p3(body.right), p3(body.up),
                              body.u0, body.v0, body.u1, body.v1)
    raise HTTPException(400, "Envie 'dirs' (4 raios) ou right/up + u0..v1.")


class AiIn(BaseModel):
    text: str
    mode: str = "auto"  # auto = IA real com fallback rápido | llm | quick
    form: Optional[Dict[str, Any]] = None  # respostas do assistente "Novo projeto"


def _repair_truncated_json(s: str) -> Optional[str]:
    """Tenta fechar um JSON TRUNCADO (resposta cortada por max_tokens):
    remove o fragmento incompleto final e fecha strings/chaves/colchetes
    abertos. Suficiente p/ {'explain':…, 'ops':[…,…} — as ops do fim que
    ficaram pela metade são descartadas, as completas são executadas."""
    s = s.rstrip()
    # remove fragmento incompleto após a última vírgula/fechamento válido
    cut = max(s.rfind(","), s.rfind("}"), s.rfind("]"))
    if cut > 0:
        s = s[:cut + 1]
    in_str = False
    esc = False
    stack: list[str] = []
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    if in_str:
        s += '"'
    if not s.rstrip().endswith(("}", "]")):
        s = s.rstrip().rstrip(",")
    for op in reversed(stack):
        s += "}" if op == "{" else "]"
    return s


def _extract_json_obj(raw: str) -> Dict[str, Any]:
    """Extrai o primeiro objeto JSON de uma resposta de LLM (tolerante a
    ```json fences, texto fora do lugar e JSON TRUNCADO por limite de
    tokens — repara fechando os colchetes abertos)."""
    import json as _json
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", s).strip()
    a, b = s.find("{"), s.rfind("}")
    if a < 0:
        raise ValueError("resposta sem objeto JSON")
    candidates = [s[a:b + 1]] if b > a else []
    fixed = _repair_truncated_json(s[a:])
    if fixed:
        candidates.append(fixed)
    last_err: Exception | None = None
    for c in candidates:
        try:
            return _json.loads(c)
        except _json.JSONDecodeError as e:
            last_err = e
    raise ValueError(f"JSON inválido na resposta da IA: {last_err}")


def _cohere_new_panel_elevation(ops: Any) -> Any:
    """Completa uma relação geométrica inequívoca omitida pela IA.

    Em um projeto novo, se ela cria painel e poste(s) de mesma altura mas
    esquece `ground_clearance`, a referência visual do painel não pode ficar
    no solo: sua base coincide com o topo dos postes/gaiola. Não altera
    projetos existentes, nem sobrescreve uma cota explicitamente enviada.
    """
    if not isinstance(ops, list):
        return ops
    valid = [op for op in ops if isinstance(op, dict)]
    if not any(str(op.get("operation", "")).strip().lower() == "__blank" for op in valid):
        return ops
    heights: List[float] = []
    for op in valid:
        if str(op.get("operation", "")).strip().lower() != "add_post":
            continue
        try:
            height = float(op.get("height"))
        except (TypeError, ValueError):
            continue
        if height > 0:
            heights.append(height)
    if not heights or any(abs(height - heights[0]) > 1e-6 for height in heights[1:]):
        return ops
    for op in valid:
        if (str(op.get("operation", "")).strip().lower() == "set_panel"
                and "ground_clearance" not in op):
            op["ground_clearance"] = heights[0]
    return ops


def _quick_form_ops(intent: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Operações determinísticas do Formulário rápido.

    O formulário já possui todas as dimensões e escolhas geométricas; não deve
    gastar uma chamada de LLM nem ficar aguardando thinking para desenhar um
    painel retangular, gaiola, postes e acessórios explicitamente marcados.
    """
    panel = intent["panel"]
    cabinet = panel["cabinet"]
    install = intent["install"]
    features = intent["features"]
    width, height = float(panel["width"]), float(panel["height"])
    depth = float(panel["depth"])
    base = float(install["ground_clearance"])
    posts = int(install["posts"])
    cage = bool(features["cage"])
    walkway = bool(features["walkway"])
    guardrail = bool(features["guardrail"]) and walkway
    visual_depth = depth if cage else max(50.0, float(cabinet.get("depth") or 50))

    ops: List[Dict[str, Any]] = [
        {"operation": "__blank"},
        {"operation": "set_panel", "width": width, "height": height,
         "depth": visual_depth, "ground_clearance": base},
    ]
    if cage:
        y_front, y_back = depth / 2, -depth / 2
        ops += [
            {"operation": "add_box", "center": {"x": 0, "y": 0,
             "z": base + height / 2}, "width": width, "depth": depth,
             "height": height, "group": "GAIOLA"},
            {"operation": "add_grid", "start": {"x": -width / 2, "y": y_front, "z": base},
             "end": {"x": width / 2, "y": y_front, "z": base + height},
             "cols": int(cabinet["cols"]), "rows": int(cabinet["rows"]),
             "border": True, "group": "GABINETES-FRONT"},
            {"operation": "add_grid", "start": {"x": -width / 2, "y": y_back, "z": base},
             "end": {"x": width / 2, "y": y_back, "z": base + height},
             "cols": int(cabinet["cols"]), "rows": int(cabinet["rows"]),
             "border": True, "group": "GABINETES-TRASEIRA"},
        ]
    if posts:
        xs = [0.0] if posts == 1 else [
            -width * .4 + (width * .8 * i / (posts - 1)) for i in range(posts)]
        ops.extend({"operation": "add_post", "x": x, "y": 0, "height": base}
                   for x in xs)
    if walkway:
        y_near = -(depth / 2 if cage else visual_depth / 2)
        y_far = y_near - max(650.0, depth)
        ops.append({"operation": "add_grid",
                    "start": {"x": -width / 2, "y": y_far, "z": base},
                    "end": {"x": width / 2, "y": y_near, "z": base},
                    "cols": max(1, int(cabinet["cols"])), "rows": 1,
                    "border": True, "group": "PASSARELA"})
        if guardrail:
            for x in (-width / 2, 0.0, width / 2):
                ops.append({"operation": "add_beam",
                            "start": {"x": x, "y": y_far, "z": base},
                            "end": {"x": x, "y": y_far, "z": base + 1100},
                            "role": "vertical", "group": "GUARDA-CORPO"})
            for z in (base + 550, base + 1100):
                ops.append({"operation": "add_beam",
                            "start": {"x": -width / 2, "y": y_far, "z": z},
                            "end": {"x": width / 2, "y": y_far, "z": z},
                            "role": "horizontal", "group": "GUARDA-CORPO"})
    return ops


@app.post("/api/ai/command")
def ai_command(body: AiIn):
    """Comando de IA. Fluxo 'auto' (padrão): LLM REAL (z.ai GLM gratuito por
    padrão; Gemini/OpenAI/compatível quando configurado em /api/ai/config)
    interpreta o pedido com o prompt do modelo JSON (ai_prompts) e devolve
    {explain, ops}; o motor Python valida e executa. Sem conexão com o
    provedor → cai no parser determinístico offline ('modo rápido')."""
    from services.ai_llm import AiError, chat_completion, load_config
    from services.ai_prompts import build_system_prompt, build_user_message
    from services.ai_intent import build_intent

    def _payload(res: Dict[str, Any]) -> Dict[str, Any]:
        m = STORE.ensure_loaded()
        res["model"] = m.model_dump()
        res["bom"] = bom_full(m)
        res["can_undo"] = STORE.can_undo
        return res

    intent = None
    if body.mode != "quick":
        # INTENÇÃO CANÔNICA (a MESMA do Copiloto): formulário estruturado tem
        # prioridade; texto livre deriva new/local_edit/global_resize.
        intent = build_intent(text=body.text, model=STORE.ensure_loaded(),
                              form=body.form)
        if body.form:
            # F2: formulário usa o MESMO compilador paramétrico da spec/IA
            try:
                from services.parametric import intent_to_spec, compile_spec
                spec = intent_to_spec(intent)
                out = compile_spec(spec)
                result = execute_ops(STORE, out["ops"])
                result["mode"] = "form"
                result["completeness"] = out["completeness"]
                result["engine"] = "form"
                result["message"] = "Estrutura criada pelo formulário rápido."
                return _payload(result)
            except OperationError as e:
                return _payload({"ok": False, "engine": "form", "message": str(e)})
        if body.mode == "auto" and intent["intent"] in ("new", "global_resize"):
            # Criação/redimensionamento NUNCA caem no parser rápido: o fallback
            # offline não desenha estruturas e produziria geometria diferente
            # da intenção (ex.: só set_panel num pedido 2x1 → 4x2).
            body.mode = "llm"
    if body.mode != "quick":
        if body.mode == "auto":
            # Segurança primeiro: em 'auto', comandos determinísticos (desfaça,
            # custo, preset, exclua ID…) são resolvidos pelo parser rápido ANTES
            # da IA — evita mal-entendidos destrutivos do LLM (ex.: responder
            # "desfaça" com __blank, apagando o projeto) e responde na hora.
            # - Parse falhou (comando desconhecido) → segue para a IA real.
            # - Parse OK mas execução falhou (ex. "nada para desfazer") →
            #   responde o erro real na hora (NÃO vai para a IA: a intenção
            #   já era um comando conhecido — a IA só inventaria uma resposta).
            try:
                ops = parse_command(STORE.ensure_loaded(), body.text)
            except OperationError:
                ops = None  # desconhecido → IA real
            if ops is not None:
                try:
                    return _payload(execute_ops(STORE, ops))
                except OperationError as e:
                    return _payload({"ok": False, "engine": "quick",
                                     "message": str(e)})
        try:
            cfg = load_config()
            model = STORE.ensure_loaded()
            from services.ai_llm import provider_capabilities
            from services.ai_contract import (RESPONSE_SCHEMA, contract_text,
                                              run_cad_plan)
            caps = provider_capabilities(cfg)
            sys_p = build_system_prompt(
                model, bom_full(model),
                [{"id": p["id"], "name": p["name"]} for p in list_presets()],
                intent=intent)
            if caps.get("structured_output"):
                sys_p += "\n\n" + contract_text()
            schema = RESPONSE_SCHEMA if caps.get("strict_schema") else None

            def _call(msgs):
                return chat_completion(msgs, cfg, response_schema=schema)

            out = run_cad_plan(
                _call, _extract_json_obj, model, intent, body.text,
                sys_p=sys_p,
                user_base=build_user_message(body.text, body.form, intent=intent))
            if not out["ok"]:
                # falha semântica após (no máx.) 1 retry: erro claro, nada aplicado
                return {"ok": False, "engine": "llm",
                        "message": "A IA não produziu operações efetivas para "
                                   "este pedido: " + (out.get("reason") or ""),
                        "errors": out.get("errors", [])[:2]}
            ops = _cohere_new_panel_elevation(out["ops"])
            result = execute_ops(STORE, ops)
            explain = str(out.get("explain") or "").strip()
            result["engine"] = "llm"
            result["explain"] = explain
            if explain:
                result["message"] = explain
            return _payload(result)
        except (AiError, ValueError) as e:
            # JSONDecodeError é subclasse de ValueError — coberto aqui
            print(f"[ai] provedor falhou (modo {body.mode}): {e}", flush=True)
            if body.mode == "llm":
                return {"ok": False, "engine": "llm",
                        "message": f"IA real indisponível: {e}",
                        "ai_status": getattr(e, "status", None),
                        "ai_retry_after": getattr(e, "retry_after", None)}
            # auto → segue para o modo rápido (offline)
        except OperationError as e:
            # a IA respondeu, mas as operações eram inválidas — reportar claro
            return {"ok": False, "engine": "llm",
                    "message": f"A IA devolveu operações inválidas: {e}"}

    # -------- modo rápido (parser determinístico, offline) --------
    try:
        result = execute_command(STORE, body.text)
    except OperationError as e:
        return {"ok": False, "message": str(e), "help": HELP_TEXT}
    result.setdefault("engine", "quick")
    return _payload(result)


# ------------------------------------------------ copiloto IA (modo PLANO)


class AiPlanIn(BaseModel):
    text: str
    view: str = ""                     # vista atual do usuário (contexto da IA)
    selection_ids: List[str] = []      # elementos selecionados (contexto da IA)


@app.post("/api/ai/plan")
def ai_plan(body: AiPlanIn):
    """Copiloto OPERACIONAL — o chat NÃO aplica nada sozinho.

    1) Utilidades determinísticas (desfaça, histórico, vento, custo, plano de
       corte, preset, seleção) → executadas na hora (modo 'executed').
    2) Desenho/edição → a IA (ai_prompts, com contexto VIVO: vista, seleção,
       grupos) devolve APENAS OPERAÇÕES; o endpoint SIMULA (dry run) e
       devolve o diff p/ o viewport mostrar o PREVIEW. NADA é aplicado —
       só quando o usuário clica APLICAR (/api/ops/apply).
    Projeto novo (pedido de criação completa) pode usar __blank — o diff
    mostra tudo que entra; pequenas alterações NUNCA regeneram o projeto.
    """
    from services.ai_llm import AiError, chat_completion, load_config
    from services.ai_prompts import build_system_prompt
    from services.ai_intent import build_intent
    from services import zai_cad_pilot as pilot

    text = (body.text or "").strip()
    if not text:
        return {"ok": False, "mode": "answer", "message": "Escreva um pedido."}

    model0 = STORE.ensure_loaded()

    # ---- trilha de desenvolvimento: intent → preset → route → engine ----
    flow: Dict[str, Any] = {"intent": None, "preset": None,
                            "route": None, "engine": None}

    def _out(res: Dict[str, Any]) -> Dict[str, Any]:
        flow["engine"] = res.get("engine") or flow["engine"]
        res["flow"] = dict(flow)
        return res

    # 1) INTERPRETAÇÃO CANÔNICA — SEMPRE a base do pedido (informação
    #    explícita do usuário). O preset NUNCA vem antes dela.
    intent = build_intent(text=text, model=model0)
    flow["intent"] = {"type": intent.get("intent"),
                      "source": intent.get("source"),
                      "panel": intent.get("panel") or None}

    # 2) ENRIQUECIMENTO pela referência citada — SOMENTE campos ausentes
    #    (precedência: USUÁRIO EXPLÍCITO > REFERÊNCIA/PRESET > DEFAULT).
    pilot.enrich_intent_with_preset(text, intent)
    if intent.get("preset"):
        flow["preset"] = intent["preset"]

    # 3) ROTEADOR determinístico (única classify_with_selection do fluxo) —
    #    a rota é decidida em Python ANTES de qualquer chamada ao LLM;
    #    nenhuma rota contorna preview → aplicar.
    cfg0 = load_config()
    conn0 = next((c for c in cfg0["connections"]
                  if c["id"] == cfg0["active_connection_id"]), None)
    pilot_on = pilot.is_zai_pilot(conn0)
    sel_count = len(body.selection_ids or [])
    route = pilot.classify_with_selection(text, intent, sel_count)
    flow["route"] = route

    # ---------------- PILOTO CAD (Z.ai GLM-4.5) ----------------
    if pilot_on:
        # resposta curta à pergunta pendente funde no texto (memória por
        # projeto/revisão) e reprocessa o fluxo canônico sobre o texto cheio
        merged = pilot.complete_short_answer(STORE.project_id, STORE.revision, text)
        if merged:
            text = merged
            intent = build_intent(text=text, model=model0)
            pilot.enrich_intent_with_preset(text, intent)
            if intent.get("preset"):
                flow["preset"] = intent["preset"]
            flow["intent"] = {"type": intent.get("intent"),
                              "source": intent.get("source"),
                              "panel": intent.get("panel") or None}
            route = pilot.classify_with_selection(text, intent, sel_count)
            flow["route"] = route
        pilot.memory_update(STORE.project_id, STORE.revision,
                            last_text=(body.text or text)[:400],
                            last_route=route, pending_question=None)
        # Validação de ausências explícitas antes do LLM
        if route == "local_edit":
            absences = pilot.detect_explicit_absences(text)
            if absences:
                validation = pilot.validate_absences_against_model(model0, absences)
                if validation["message"]:
                    return _out({"ok": True, "mode": "answer", "engine": "pilot",
                                 "explain": validation["message"],
                                 "model": model0.model_dump(),
                                 "bom": bom_full(model0), "can_undo": STORE.can_undo})
        if route == "question":
            fact = pilot.answer_factual(model0, text)
            if fact:
                pilot.memory_update(STORE.project_id, STORE.revision,
                                    last_answer=fact[:400])
                return _out({"ok": True, "mode": "answer", "engine": "pilot",
                             "explain": fact, "model": model0.model_dump(),
                             "bom": bom_full(model0), "can_undo": STORE.can_undo})
            # pergunta não factual segue para o GLM (compreensão semântica)
        elif route == "ambiguous":
            q = ("Quais dimensões de painel você quer (largura × altura em mm, "
                 "ou N×M gabinetes de 960 mm)?" if intent["intent"] in ("new", "global_resize")
                 else "Você quer criar algo novo, editar a seleção ou apenas perguntar?")
            pilot.memory_update(STORE.project_id, STORE.revision,
                                pending_question=q)
            return _out({"ok": True, "mode": "answer", "engine": "pilot",
                         "explain": q + "\n(responda aqui para completar o pedido)",
                         "model": model0.model_dump(),
                         "bom": bom_full(model0), "can_undo": STORE.can_undo})
        elif route == "review":
            # revisão determinística (mesma conferência do /api/ai/review)
            groups = {}
            for el in model0.elements:
                g = (el.group or "—").upper()
                groups[g] = groups.get(g, 0) + 1

            def _present(name: str) -> bool:
                return any(name in g for g in groups)

            inst0 = model0.installation
            checks = [
                {"componente": "painel", "presente":
                    model0.panel.width > 0 and model0.panel.height > 0,
                 "detalhe": f"{model0.panel.width:.0f}x{model0.panel.height:.0f} mm"},
                {"componente": "gaiola", "presente": _present("GAIOLA"),
                 "detalhe": f"profundidade {model0.panel.depth or 0:.0f} mm"},
                {"componente": "postes", "presente":
                    any(e.type == "post" for e in model0.elements),
                 "detalhe": f"{inst0.posts} previsto(s)"},
                {"componente": "passarela", "presente": _present("PASSARELA"),
                 "detalhe": "acesso traseiro"},
                {"componente": "guarda-corpo", "presente": _present("GUARDA"),
                 "detalhe": "proteção da passarela"},
            ]
            missing = [c["componente"] for c in checks if not c["presente"]]
            lines = "\n".join(
                f"{'✓' if c['presente'] else '⚠'} {c['componente']}: {c['detalhe']}"
                for c in checks)
            pilot.memory_update(STORE.project_id, STORE.revision,
                                last_answer=f"revisão: {len(missing)} pendência(s)")
            return _out({"ok": True, "mode": "answer", "engine": "pilot",
                         "explain": f"Revisão geométrica (rev {STORE.revision}, "
                                    f"{len(model0.elements)} elementos):\n{lines}"
                                    + ("\nPendências: " + ", ".join(missing)
                                       if missing else "\nNenhuma pendência."),
                         "model": model0.model_dump(),
                         "bom": bom_full(model0), "can_undo": STORE.can_undo})

    # 1) utilidades determinísticas (mesma política do modo auto) — só quando
    #    a intenção é utilitária/edição local
    if intent["intent"] not in ("new", "global_resize"):
        try:
            ops = parse_command(STORE.ensure_loaded(), text)
        except OperationError:
            ops = None
        if ops is not None:
            # A09: planejar é NÃO-MUTANTE. Utilidades que alteram o projeto
            # (__undo/__preset/__regen/__save_preset/__blank) respondem com
            # orientação; o usuário executa pela ação explícita
            # (/api/undo, /api/ops/apply, modais). Somente leitura
            # (histórico, custo, vento, corte, seleção) continua respondendo.
            mutating = {"__undo", "__preset", "__regen", "__save_preset",
                        "__blank"}
            if any(str(op.get("operation", "")) in mutating for op in ops):
                m = STORE.ensure_loaded()
                return _out({"ok": True, "mode": "answer", "engine": "quick",
                        "explain": "Planejamento não altera o projeto. "
                                   "Para executar, use o botão Desfazer "
                                   "(Ctrl+Z) ou o modal Novo/Presets.",
                        "model": m.model_dump(),
                        "bom": bom_full(m),
                        "can_undo": STORE.can_undo})
            try:
                res = execute_ops(STORE, ops)
                res["mode"] = "executed"
                res["engine"] = "quick"
            except OperationError as e:
                res = {"ok": False, "mode": "executed", "engine": "quick",
                       "message": str(e)}
            m = STORE.ensure_loaded()
            res["model"] = m.model_dump()
            res["bom"] = bom_full(m)
            res["can_undo"] = STORE.can_undo
            return _out(res)

    # 4) Pedido trivial COMPLETAMENTE estruturado (regra 8) → compilador
    #    paramétrico determinístico. O compilador calcula geometria — ele NÃO
    #    substitui compreensão semântica: só roda com dims explícitas e
    #    features resolvidas; intenção incompleta segue para o GLM abaixo.
    #    Criação: não-citados seguem o contrato canônico (gaiola+grades SIM,
    #    passarela/guarda-corpo NÃO). global_resize: preserva o que existe.
    if intent["intent"] in ("new", "global_resize"):
        panel_i = intent.get("panel") or {}
        if panel_i.get("width") or panel_i.get("height"):
            feats = dict(intent.get("features") or {})
            if intent["intent"] == "new":
                defaults = {"cage": True, "walkway": False, "guardrail": False}
            else:
                ctx = intent.get("context") or {}
                defaults = {"cage": bool(ctx.get("cage")),
                            "walkway": bool(ctx.get("walkway")),
                            "guardrail": bool(ctx.get("guardrail"))}
            for k, dv in defaults.items():
                if feats.get(k) is None:
                    feats[k] = dv
            intent["features"] = feats
            from services.parametric import intent_to_spec, compile_spec
            try:
                spec = intent_to_spec(intent)
                out = compile_spec(spec)
                ops = _cohere_new_panel_elevation(out["ops"])
                from core.ai_ops import dry_run_diff
                diff = dry_run_diff(model0, ops)
                if diff["errors"]:
                    return _out({"ok": False, "mode": "plan", "engine": "compiler",
                                 "message": "Compilação recusada: "
                                            + " · ".join(diff["errors"][:3])})
                return _out({"ok": True, "mode": "plan", "engine": "compiler",
                             "explain": f"Proposta completa via compilador "
                                        f"paramétrico: painel "
                                        f"{out['panel']['width']}x"
                                        f"{out['panel']['height']} mm, "
                                        f"{out['op_count']} operações.",
                             "operations": ops, "diff": diff,
                             "completeness": out["completeness"],
                             "assumptions": out["assumptions"],
                             "base_revision": STORE.revision,
                             "project_id": STORE.project_id,
                             "model": model0.model_dump(),
                             "can_undo": STORE.can_undo})
            except OperationError as e:
                return _out({"ok": False, "mode": "plan", "engine": "compiler",
                             "message": str(e)})

    # 2) IA real → OPERAÇÕES (sem aplicar) + diff de preview — validação
    #    semântica comum (contrato → normalização → dry-run) e no máx. 1 retry
    try:
        cfg = load_config()
        model = STORE.ensure_loaded()
        from services.ai_llm import provider_capabilities
        from services.ai_contract import (RESPONSE_SCHEMA, contract_text,
                                          run_cad_plan)
        caps = provider_capabilities(cfg)
        sys_p = build_system_prompt(
            model, bom_full(model),
            [{"id": p["id"], "name": p["name"]} for p in list_presets()],
            view=body.view, selection_ids=body.selection_ids, intent=intent)
        if pilot_on:
            # pacote de conhecimento do piloto + memória viva do projeto
            sys_p += "\n\n" + pilot.knowledge_block()
            mem = pilot.memory_valid(STORE.project_id, STORE.revision)
            if mem:
                sys_p += (f"\n\n## CONTEXTO DA CONVERSA (rev {STORE.revision})\n"
                          f"- último pedido: {str(mem.get('last_text') or '')[:200]}")
            else:
                sys_p += "\n\n(sem memória de conversa nesta revisão)"
        # regra 7: o GLM recebe a REFERÊNCIA PERTINENTE citada no pedido
        pblock = pilot.preset_block(intent)
        if pblock:
            sys_p += "\n\n" + pblock
        if caps.get("structured_output"):
            sys_p += "\n\n" + contract_text()
        schema = RESPONSE_SCHEMA if caps.get("strict_schema") else None

        def _call(msgs):
            return chat_completion(msgs, cfg, response_schema=schema)

        out = run_cad_plan(
            _call, _extract_json_obj, model, intent, text,
            sys_p=sys_p, user_base=pilot.build_user_message(text, intent=intent,
                                                       selection_ids=body.selection_ids,
                                                       model=model))
        if not out["ok"]:
            return _out({"ok": False, "mode": "plan", "engine": "llm",
                         "message": "A IA não produziu operações efetivas para "
                                    "este pedido: " + (out.get("reason") or ""),
                         "errors": out.get("errors", [])[:2]})
        if out["question"]:
            return _out({"ok": True, "mode": "answer", "engine": "llm",
                         "explain": out.get("explain") or "—"})
        selection: List[str] = []
        for s in out.get("selects", []):
            selection = s.get("ids", []) or selection
        if not out["ops"] and selection:
            return _out({"ok": True, "mode": "select", "engine": "llm",
                         "explain": out.get("explain") or "—",
                         "selection": selection,
                         "message": f"{len(selection)} elemento(s) selecionados."})
        # coere elevação e recompute o diff sobre as ops finais (preview fiel)
        ops = _cohere_new_panel_elevation(out["ops"])
        from core.ai_ops import dry_run_diff
        diff = dry_run_diff(model, ops)
        if diff["errors"]:
            return _out({"ok": False, "mode": "plan", "engine": "llm",
                         "message": "A IA gerou operações inválidas para esta ferramenta: "
                                    + " · ".join(diff["errors"][:2])})
        return _out({"ok": True, "mode": "plan", "engine": "llm",
                     "explain": out.get("explain") or "",
                     "operations": diff["operations"], "preview": diff,
                     "view": body.view, "selection_ids": body.selection_ids})
    except (AiError, ValueError) as e:
        # logs em CP1252 (Windows) quebram com emojis da mensagem do provedor
        safe = str(e).encode("ascii", "backslashreplace").decode("ascii")
        print(f"[ai-plan] provedor falhou: {safe}", flush=True)
        return _out({"ok": False, "mode": "plan",
                     "message": f"IA indisponível: {e}",
                     "ai_status": getattr(e, "status", None),
                     "ai_retry_after": getattr(e, "retry_after", None)})
    except OperationError as e:
        return _out({"ok": False, "mode": "plan",
                     "message": f"A IA devolveu operações inválidas: {e}"})


# ------------------------------------------- conector IA (conexões manuais)
class AiConnIn(BaseModel):
    id: Optional[str] = None
    name: str = ""
    base_url: str = ""
    model: str = ""
    api_key: Optional[str] = None


class AiConnIdIn(BaseModel):
    id: str


def _ai_err(e: AiError) -> Dict[str, Any]:
    """Erro curto para a UI + status/retry_after (quando o provedor informa).
    Nunca inclui chave/header."""
    return {"ok": False, "error": str(e), "status": getattr(e, "status", None),
            "retry_after": getattr(e, "retry_after", None)}


@app.get("/api/ai/config")
def ai_config_get():
    from services.ai_llm import public_config
    return public_config()


@app.get("/api/ai/review")
def ai_review():
    """P4 — REVISOR GEOMÉTRICO (determinístico, sem LLM): confere componentes
    solicitados × presentes a partir do modelo real e devolve pendências."""
    model = STORE.ensure_loaded()
    panel = model.panel
    inst = model.installation
    groups = {}
    for el in model.elements:
        g = (el.group or "—").upper()
        groups[g] = groups.get(g, 0) + 1

    def present(name: str) -> bool:
        return any(name in g for g in groups)

    checks = [
        {"componente": "painel", "solicitado": True,
         "presente": panel.width > 0 and panel.height > 0,
         "detalhe": f"{round(panel.width)}x{round(panel.height)} mm"},
        {"componente": "gaiola", "solicitado": True, "presente": present("GAIOLA"),
         "detalhe": f"profundidade {round(panel.depth or 0)} mm"},
        {"componente": "postes", "solicitado": inst.posts > 0,
         "presente": any(el.type == "post" for el in model.elements),
         "detalhe": f"{inst.posts} previsto(s)"},
        {"componente": "passarela", "solicitado": True,
         "presente": present("PASSARELA"),
         "detalhe": "acesso traseiro"},
        {"componente": "guarda-corpo", "solicitado": present("PASSARELA"),
         "presente": present("GUARDA"), "detalhe": "proteção da passarela"},
    ]
    missing = [c["componente"] for c in checks
               if c["solicitado"] and not c["presente"]]
    return {"ok": True, "revision": STORE.revision,
            "checks": checks, "missing": missing,
            "elements": len(model.elements)}


class AiRefIn(BaseModel):
    text: str


@app.post("/api/ai/reference")
def ai_reference(body: AiRefIn):
    """P4 — LEITOR DE REFERÊNCIA: extrai candidatos numéricos de um texto
    (medidas de referência coladas pelo usuário) com procedência linha/coluna.
    Não aplica nada — devolve dados para validação/preview."""
    import re as _re
    text = (body.text or "")[:20000]
    if not text.strip():
        raise HTTPException(400, "Cole o texto da referência.")
    candidates = []
    for i, line in enumerate(text.splitlines(), 1):
        for m in _re.finditer(r"(\d{2,5})\s*(?:mm|milímetros?)?\b", line, _re.I):
            v = int(m.group(1))
            if 50 <= v <= 30000:
                candidates.append({
                    "value": v, "unit": "mm",
                    "context": line.strip()[:120],
                    "provenance": {"line": i, "col": m.start() + 1},
                    "tag": "width" if "larg" in line.lower() else
                           ("height" if "alt" in line.lower() else
                            "unknown"),
                })
    return {"ok": True, "count": len(candidates),
            "candidates": candidates[:80],
            "note": "Candidatos extraídos com procedência — validação e "
                    "aplicação passam pelo compilador/preview."}


@app.post("/api/ai/config")
def ai_config_post(body: AiConnIn):
    """Cria/atualiza uma conexão manual e a torna ATIVA (chave só no backend;
    api_key vazio preserva a chave já salva da conexão)."""
    from services.ai_llm import AiError, save_connection
    try:
        return save_connection(body.model_dump())
    except AiError as e:
        return _ai_err(e)


@app.post("/api/ai/config/activate")
def ai_config_activate(body: AiConnIdIn):
    """Torna a conexão informada a ativa do copiloto (persistente)."""
    from services.ai_llm import AiError, activate_connection
    try:
        return activate_connection(body.id)
    except AiError as e:
        return _ai_err(e)


@app.post("/api/ai/config/delete")
def ai_config_delete(body: AiConnIdIn):
    """Exclui uma conexão salva (a UI confirma antes de chamar)."""
    from services.ai_llm import AiError, delete_connection
    try:
        return delete_connection(body.id)
    except AiError as e:
        return _ai_err(e)


@app.post("/api/ai/test")
def ai_test():
    """Teste de conexão REAL com a conexão ATIVA (pergunta trivial)."""
    from services.ai_llm import AiError, test_provider
    try:
        return test_provider()
    except AiError as e:
        return _ai_err(e)


@app.post("/api/ai/test-dry")
def ai_test_dry(body: AiConnIn):
    """Teste EFÊMERO com os valores do formulário (antes de salvar).

    Não grava ai_config.json, não altera a conexão ativa e não troca a chave
    salva (api_key vazio usa a chave guardada da conexão apenas em memória).
    A resposta nunca inclui a chave."""
    from services.ai_llm import AiError, test_connection
    try:
        return test_connection(body.model_dump())
    except AiError as e:
        return _ai_err(e)


@app.post("/api/project/blank")
def project_blank():
    """Novo projeto EM BRANCO: só a superfície do painel (ocultável) — o
    usuário monta a estrutura do zero com Barra A→B / IA."""
    STORE.new_blank()
    model = STORE.ensure_loaded()
    return {"ok": True, "message": "Projeto em branco criado — monte a estrutura "
                                   "do zero (Barra A→B ou IA).",
            "model": model.model_dump(), "bom": bom_full(model),
            "can_undo": STORE.can_undo}


@app.get("/api/export/cutlist.pdf")
def export_cutlist_pdf(bar_len: float = Query(6000.0, ge=2000, le=15000)):
    """Plano de corte em PDF imprimível (folha de serralheria A4 paisagem):
    cards por perfil com a régua de corte de cada barra comercial."""
    from export.cutlist_pdf import build_cutlist_pdf
    bar_len_v = normalize_bar_len(bar_len)
    model = STORE.ensure_loaded()
    cl = build_cutlist(model, bar_len_v)
    pdf = build_cutlist_pdf(cl, project_name=model.project.name,
                            preset_id=STORE.preset_id)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition":
                             'attachment; filename="plano_de_corte.pdf"'})


@app.get("/api/export/cutlist.csv")
def export_cutlist_csv(bar_len: float = Query(6000.0, ge=2000, le=15000)):
    """Plano de corte em CSV (serralheria abre direto no Excel)."""
    import csv
    import io

    bar_len_v = normalize_bar_len(bar_len)
    cl = build_cutlist(STORE.ensure_loaded(), bar_len_v)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["PERFIL", "DESCRICAO", "PECA (mm)", "QTD", "TOTAL (m)",
                f"BARRAS {int(bar_len_v/1000)}M", "SOBRA %"])
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
    return Response(
        "\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="plano_de_corte.csv"'},
    )


# ------------------------------------------------------------ estáticos
class NoCacheHTMLStaticFiles(StaticFiles):
    """StaticFiles com Cache-Control: no-cache — o navegador sempre revalida
    o index.html (etag/last-modified), evitando servir cópia antiga do app."""

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


app.mount("/", NoCacheHTMLStaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3100)
