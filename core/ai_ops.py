"""Camada de OPERAÇÕES de edição (evolução CAD + Copiloto IA).

FLUXO OBRIGATÓRIO (nunca o contrário):
    IA (ou editor) → operation JSON → ESTE MÓDULO (Python) → modelo do
    projeto → nova geometria → Three.js (SÓ visualização/interação)

O que este módulo faz — sem ALTERAR o motor existente:
- `normalize_op()`: aceita o formato da IA ({"type":…, "delta":{x,y,z}})
  OU o formato canônico ({"operation":…, "delta_x":…}) e devolve canônico.
- Handlers NOVOS e SEMÂNTICOS (nunca mesh): add_element, add_diagonal,
  resize_element, replace_element, rotate_element, set_group, set_role,
  align_elements, distribute_elements, mirror_elements.
- `dry_run_diff()`: aplica as operações numa CÓPIA do modelo e devolve o
  DIFF (adicionados / removidos / alterados) SEM tocar no projeto —
  alimenta o PREVIEW no viewport antes do APLICAR.
- `apply_batch()`: aplica a lista inteira com UM snapshot de undo só
  (Ctrl+Z desfaz o lote inteiro) — histórico UNIFICADO com as operações
  manuais do editor (mesma pilha do ProjectStore).

Motor geométrico (core/operations.py), schema (models/element.py),
presets e geração: 100% intocados — os handlers originais são IMPORTADOS
e reutilizados.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from models.element import Element, ProjectModel, Vec3
from services.preset_service import PresetBuilder, load_preset

from core.operations import (
    OperationError,
    _get,
    _ids_from_op,
    _op_add_beam,
    _op_add_box,
    _op_add_circle,
    _op_add_grid,
    _op_add_plate,
    _op_add_post,
    _op_delete,
    _op_duplicate,
    _op_move,
    _op_multi_delete,
    _op_multi_duplicate,
    _op_multi_move,
    _op_multi_profile,
    _op_rename,
    _op_set_panel,
    _op_set_position,
    _op_set_post_height,
    _op_set_shield,
    _op_update_profile,
    _unique_id,
)

# --------------------------------------------------------------- normalizar

# Papéis canônicos aceitos pelo schema (models/element.py). Nenhum texto
# livre da IA chega ao campo Pydantic `role`: tudo passa por aqui.
ROLE_CANON = {"vertical", "horizontal", "trave", "diagonal", "post",
              "plate", "base", "bolt", "panel", "other"}

# Sinônimos semânticos → papel canônico (regra geral, não por caso de projeto)
ROLE_SYNONYMS: Dict[str, Tuple[str, ...]] = {
    "post": ("poste", "postes", "pilar", "pilares", "coluna", "colunas",
             "column", "columns", "pillar", "mastro"),
    "vertical": (),
    "horizontal": ("horizontal", "barra horizontal", "longarina"),
    "trave": ("trave", "travessa", "travessas", "viga", "vigas", "beam",
              "vao", "vão"),
    "diagonal": ("diagonal", "diagonais", "contraventamento", "tesoura",
                 "escora", "escoras"),
    "plate": ("plate", "chapa", "chapas", "placa", "placas"),
    "base": ("base", "bases", "fundacao", "fundação", "sapata", "sapatas",
             "pe de apoio", "pé de apoio"),
    "bolt": ("bolt", "chumbador", "chumbadores", "pino", "pinos",
             "ancora", "âncora", "parafuso de ancoragem"),
    "panel": ("panel", "painel", "tela", "display"),
    "other": ("other", "outro", "outros", "elemento"),
}


def _deduce_role_by_direction(op: Dict[str, Any]) -> str:
    """Deduz o papel GEOMÉTRICO pela direção real start/end (regra geral para
    descrições funcionais tipo 'guarda corpo', 'corrimão', 'suporte'):
    Z predominante = vertical; X/Y predominante = horizontal/trave; eixos
    mistos = diagonal; sem geometria = other."""
    s, e = op.get("start"), op.get("end")
    if not (isinstance(s, dict) and isinstance(e, dict)):
        return "other"
    try:
        dx = abs(float(e.get("x", 0)) - float(s.get("x", 0)))
        dy = abs(float(e.get("y", 0)) - float(s.get("y", 0)))
        dz = abs(float(e.get("z", 0)) - float(s.get("z", 0)))
    except (TypeError, ValueError):
        return "other"
    m = max(dx, dy, dz)
    if m <= 0.0:
        return "other"
    if dz == m:                       # predominância em altura
        return "vertical"
    other_h = dy if dx == m else dx   # segundo eixo horizontal
    if other_h >= 0.5 * m or dz >= 0.5 * m:
        return "diagonal"             # eixos mistos
    return "trave" if dy == m else "horizontal"


def _norm_role(op: Dict[str, Any]) -> None:
    """Normaliza o campo `role` (ou `element_role`) da operação IN PLACE.

    - papéis já válidos passam intactos;
    - sinônimos de poste/base/chapa/painel/etc. viram o papel canônico;
    - descrições funcionais (guarda corpo, corrimão, suporte, reforço…) são
      preservadas em `group` e o papel é deduzido pela direção real;
    - nada de texto livre chega ao Pydantic."""
    raw = op.get("role") or op.get("element_role")
    if not isinstance(raw, str) or not raw.strip():
        return
    rl = raw.strip().lower()
    if rl in ROLE_CANON:
        op["role"] = rl
        op.pop("element_role", None)
        return
    canon = None
    for target, syns in ROLE_SYNONYMS.items():
        if rl in syns or rl.rstrip("s") in syns:
            canon = target
            break
    if canon is None:
        canon = _deduce_role_by_direction(op)
        g = str(op.get("group") or "").strip()
        desc = raw.strip().upper()[:40]
        op["group"] = f"{g} · {desc}" if g else desc
    op["role"] = canon
    op.pop("element_role", None)


def normalize_op(op: Any) -> Dict[str, Any]:
    """Canoniza uma operação vinda da IA ou do editor.

    Formatos aceitos (ex. do usuário):
      {"type":"move_element","element_id":"V03","delta":{"x":-100,"y":0,"z":0}}
      {"operation":"move_element","element_id":"V03","delta_x":-100}
    """
    if not isinstance(op, dict):
        raise OperationError(f"Operação malformada: {str(op)[:120]}")
    o = dict(op)
    t = o.pop("type", None)
    if t and not o.get("operation"):
        o["operation"] = t
    d = o.pop("delta", None)
    if isinstance(d, dict):
        o.setdefault("delta_x", d.get("x", 0))
        o.setdefault("delta_y", d.get("y", 0))
        o.setdefault("delta_z", d.get("z", 0))
    elif isinstance(d, (list, tuple)) and len(d) == 3:
        o.setdefault("delta_x", d[0])
        o.setdefault("delta_y", d[1])
        o.setdefault("delta_z", d[2])
    kind = str(o.get("operation", "")).strip().lower()
    if not kind:
        raise OperationError(f"Operação sem 'operation'/'type': {str(op)[:120]}")
    o["operation"] = kind
    _norm_role(o)   # papel semântico → canônico (nunca texto livre no Pydantic)
    return o


# ---------------------------------------------------------------- geometria


def _axis_key(axis: str) -> str:
    a = str(axis or "x").strip().lower()
    if a not in ("x", "y", "z"):
        raise OperationError(f"Eixo inválido: '{axis}' (use x, y ou z).")
    return a


def _vec(v: Optional[Vec3], axis: str) -> float:
    if v is None:
        return 0.0
    return float(getattr(v, axis))


def _el_points(el: Element) -> List[Vec3]:
    """Pontos-chave do elemento (start/end p/ barra; centro p/ chapa)."""
    if el.start and el.end:
        return [el.start, el.end]
    if el.center:
        return [el.center]
    return []


def _el_center(el: Element) -> Vec3:
    if el.center:
        return el.center
    if el.start and el.end:
        return Vec3(
            x=(el.start.x + el.end.x) / 2,
            y=(el.start.y + el.end.y) / 2,
            z=(el.start.z + el.end.z) / 2,
        )
    return Vec3()


def _el_axis_span(el: Element, axis: str) -> Tuple[float, float]:
    """(min, max) do elemento no eixo — barras: start/end; chapas: ±tamanho/2."""
    if el.type == "plate" and el.center:
        half = float(getattr(el, f"size_{axis}", 0)) / 2.0
        c = _vec(el.center, axis)
        return (c - half, c + half)
    pts = [ _vec(p, axis) for p in _el_points(el) ] or [0.0]
    return (min(pts), max(pts))


def _rot_point(p: Vec3, c: Vec3, axis: str, ang: float) -> Vec3:
    """Rotaciona p em torno de c no plano perpendicular ao eixo."""
    x, y, z = p.x - c.x, p.y - c.y, p.z - c.z
    ca, sa = math.cos(ang), math.sin(ang)
    if axis == "x":
        return Vec3(x=p.x, y=c.y + y * ca - z * sa, z=c.z + y * sa + z * ca)
    if axis == "y":
        return Vec3(x=c.x + x * ca + z * sa, y=p.y, z=c.z - x * sa + z * ca)
    return Vec3(x=c.x + x * ca - y * sa, y=c.y + x * sa + y * ca, z=p.z)


# ------------------------------------------------------------ handlers NOVOS


def _op_add_element(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """Operação genérica: add_element {etype: 'beam'|'plate', …}."""
    etype = str(op.get("etype") or op.get("element_type") or "beam").lower()
    if etype in ("beam", "bolt", "barra", "post"):
        return _op_add_beam(model, op)
    if etype in ("plate", "chapa"):
        return _op_add_plate(model, op)
    raise OperationError(f"add_element: tipo desconhecido '{etype}'.")


def _op_add_diagonal(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """Diagonal: start/end explícitos OU ligando 2 elementos existentes
    (from_element/to_element — usa o par de extremidades mais próximas)."""
    op = dict(op)
    op["role"] = op.get("role", "diagonal")
    op.setdefault("group", "DIAGONAIS")
    if op.get("start") and op.get("end"):
        return _op_add_beam(model, op)
    fid, tid = op.get("from_element"), op.get("to_element")
    if not fid or not tid:
        raise OperationError("add_diagonal: informe start/end OU from_element/to_element.")
    fe, te = _get(model, fid), _get(model, tid)
    fp = [fe.start, fe.end] if fe.start and fe.end else ([fe.center] if fe.center else [])
    tp = [te.start, te.end] if te.start and te.end else ([te.center] if te.center else [])
    if not fp or not tp:
        raise OperationError("add_diagonal: elementos de referência sem geometria.")
    best, best_d = None, float("inf")
    for a in fp:
        for b in tp:
            d = math.dist(a.as_tuple(), b.as_tuple())
            if d < best_d:
                best_d, best = d, (a, b)
    op["start"] = {"x": best[0].x, "y": best[0].y, "z": best[0].z}
    op["end"] = {"x": best[1].x, "y": best[1].y, "z": best[1].z}
    return _op_add_beam(model, op)


def _op_resize(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """resize_element: barra por 'length' (âncora start|end|center) ou
    chapa por size_x/size_y/size_z."""
    el = _get(model, op["element_id"])
    if el.type in ("beam", "bolt") and el.start and el.end:
        if "length" not in op:
            raise OperationError("resize_element: informe 'length' (mm).")
        L = float(op["length"])
        if L <= 0:
            raise OperationError("Comprimento deve ser positivo.")
        s, e = el.start, el.end
        d = (e.x - s.x, e.y - s.y, e.z - s.z)
        cur = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1.0
        k = L / cur
        anchor = str(op.get("anchor", "start")).lower()
        if anchor == "end":
            # start move: novo start = end - dir*L
            el.start = Vec3(x=e.x - d[0] * k, y=e.y - d[1] * k, z=e.z - d[2] * k)
        elif anchor == "center":
            c = _el_center(el)
            half = (d[0] * k / 2, d[1] * k / 2, d[2] * k / 2)
            el.start = Vec3(x=c.x - half[0], y=c.y - half[1], z=c.z - half[2])
            el.end = Vec3(x=c.x + half[0], y=c.y + half[1], z=c.z + half[2])
        else:
            el.end = Vec3(x=s.x + d[0] * k, y=s.y + d[1] * k, z=s.z + d[2] * k)
        return {"element_id": el.id, "length": round(L, 1)}
    if el.type == "plate" and el.center:
        for ax in ("size_x", "size_y", "size_z"):
            if ax in op:
                v = float(op[ax])
                if v <= 0:
                    raise OperationError(f"{ax} deve ser positivo.")
                setattr(el, ax, v)
        return {"element_id": el.id,
                "size": [el.size_x, el.size_y, el.size_z]}
    raise OperationError("resize_element: elemento sem geometria editável.")


def _op_replace(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """replace_element: troca a geometria mantendo o MESMO ID (e grupo/papel
    por padrão). Útil p/ a IA corrigir um elemento sem apagar/recriar."""
    el = _get(model, op["element_id"])
    ntype = str(op.get("new_type") or op.get("etype") or el.type).lower()
    el.type = "beam" if ntype in ("beam", "bolt") else ("plate" if ntype == "plate" else el.type)
    if el.type == "beam":
        if "start" not in op or "end" not in op:
            raise OperationError("replace_element: informe start/end p/ barra.")
        el.start = Vec3(**op["start"])
        el.end = Vec3(**op["end"])
        el.center = None
    else:
        if "center" not in op:
            raise OperationError("replace_element: informe center p/ chapa.")
        el.center = Vec3(**op["center"])
        el.start = el.end = None
        for ax in ("size_x", "size_y", "size_z"):
            if ax in op:
                setattr(el, ax, float(op[ax]))
    if op.get("profile"):
        el.profile = op["profile"]
    if op.get("role"):
        el.role = op["role"]
    if "group" in op:
        el.group = op["group"]
    return {"element_id": el.id, "type": el.type}


def _op_rotate(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """rotate_element: rotação semântica (gira start/end em torno do centro).
    ângulo em graus (default 90), eixo x|y|z (default z), centro opcional."""
    el = _get(model, op["element_id"])
    axis = _axis_key(op.get("axis", "z"))
    ang = math.radians(float(op.get("angle_deg", 90)))
    if el.type == "plate" and el.center:
        c = el.center
        el.center = _rot_point(c, c, axis, ang)
        if axis == "z" and round(math.degrees(ang)) % 180 == 90:
            el.size_x, el.size_y = el.size_y, el.size_x
        return {"element_id": el.id, "axis": axis, "angle_deg": math.degrees(ang)}
    if not (el.start and el.end):
        raise OperationError("rotate_element: elemento sem geometria.")
    c = Vec3(**op["center"]) if op.get("center") else _el_center(el)
    el.start = _rot_point(el.start, c, axis, ang)
    el.end = _rot_point(el.end, c, axis, ang)
    return {"element_id": el.id, "axis": axis, "angle_deg": round(math.degrees(ang), 1)}


def _op_set_group(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    el = _get(model, op["element_id"])
    g = str(op.get("group", "")).strip()
    el.group = g
    return {"element_id": el.id, "group": g}


ROLE_VALUES = {"vertical", "horizontal", "trave", "diagonal", "post",
               "plate", "base", "bolt", "panel", "other"}


def _op_set_role(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    el = _get(model, op["element_id"])
    r = str(op.get("role", "")).strip().lower()
    if r not in ROLE_VALUES:
        raise OperationError(
            f"Papel inválido: '{r}'. Use: {', '.join(sorted(ROLE_VALUES))}.")
    el.role = r
    return {"element_id": el.id, "role": r}


def _op_align(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """align_elements: alinha a seleção num eixo (âncora min|center|max).
    O alvo é a CAIXA coletiva da seleção — cada elemento move o MÍNIMO
    necessário para sua âncora coincidir com a âncora da caixa."""
    ids = _ids_from_op(op)
    axis = _axis_key(op.get("axis", "x"))
    anchor = str(op.get("anchor", "center")).lower()
    els = []
    for i in ids:
        try:
            els.append(_get(model, i))
        except OperationError:
            continue  # IDs inexistentes são ignorados no alinhamento
    if len(els) < 2:
        raise OperationError("align_elements: selecione ao menos 2 elementos existentes.")
    spans = [_el_axis_span(e, axis) for e in els]
    lo = min(s[0] for s in spans)
    hi = max(s[1] for s in spans)
    target = {"min": lo, "max": hi, "center": (lo + hi) / 2}[anchor]
    moved: List[str] = []
    for el, (a, b) in zip(els, spans):
        own = {"min": a, "max": b, "center": (a + b) / 2}[anchor]
        delta = round(target - own, 6)
        if abs(delta) < 1e-6:
            continue
        d = {axis: delta}
        _op_move(model, {"element_id": el.id,
                         "delta_x": d.get("x", 0), "delta_y": d.get("y", 0),
                         "delta_z": d.get("z", 0)})
        moved.append(el.id)
    return {"count": len(moved), "ids": moved, "axis": axis,
            "anchor": anchor, "target": round(target, 1)}


def _op_distribute(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """distribute_elements: distribui os CENTROS uniformemente no eixo entre
    o primeiro e o último elemento (ordem pela coordenada atual)."""
    ids = _ids_from_op(op)
    axis = _axis_key(op.get("axis", "x"))
    els = []
    for i in ids:
        try:
            els.append(_get(model, i))
        except OperationError:
            continue
    if len(els) < 3:
        raise OperationError("distribute_elements: selecione ao menos 3 elementos.")
    els.sort(key=lambda e: _vec(_el_center(e), axis))
    a = _vec(_el_center(els[0]), axis)
    b = _vec(_el_center(els[-1]), axis)
    step = (b - a) / (len(els) - 1)
    moved: List[str] = []
    for idx, el in enumerate(els[1:-1], start=1):
        target = a + step * idx
        cur = _vec(_el_center(el), axis)
        delta = round(target - cur, 6)
        if abs(delta) < 1e-6:
            continue
        _op_move(model, {"element_id": el.id,
                         "delta_x": delta if axis == "x" else 0,
                         "delta_y": delta if axis == "y" else 0,
                         "delta_z": delta if axis == "z" else 0})
        moved.append(el.id)
    return {"count": len(moved), "ids": moved, "axis": axis,
            "from": round(a, 1), "to": round(b, 1)}


def _op_mirror(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """mirror_elements: espelha num plano perpendicular ao eixo (pivot mm).
    'copy': true (default) cria os espelhos mantendo os originais."""
    ids = _ids_from_op(op)
    axis = _axis_key(op.get("plane", op.get("axis", "x")))
    pivot = float(op.get("pivot", 0))
    copy = bool(op.get("copy", True))

    def refl(v: float) -> float:
        return 2 * pivot - v

    def mirror_el(src: Element) -> Element:
        c = src.model_copy(deep=True)
        if c.start and c.end:
            c.start = Vec3(x=refl(c.start.x) if axis == "x" else c.start.x,
                           y=refl(c.start.y) if axis == "y" else c.start.y,
                           z=refl(c.start.z) if axis == "z" else c.start.z)
            c.end = Vec3(x=refl(c.end.x) if axis == "x" else c.end.x,
                         y=refl(c.end.y) if axis == "y" else c.end.y,
                         z=refl(c.end.z) if axis == "z" else c.end.z)
        if c.center:
            c.center = Vec3(x=refl(c.center.x) if axis == "x" else c.center.x,
                            y=refl(c.center.y) if axis == "y" else c.center.y,
                            z=refl(c.center.z) if axis == "z" else c.center.z)
        return c

    created: List[str] = []
    mirrored: List[str] = []
    for i in ids:
        try:
            el = _get(model, i)
        except OperationError:
            continue
        if copy:
            clone = mirror_el(el)
            clone.id = _unique_id(model, el)
            if clone.id == el.id:  # _unique_id nunca devolve o mesmo, por garantia
                clone.id = el.id + "-M"
            model.elements.append(clone)
            created.append(clone.id)
        else:
            m = mirror_el(el)
            el.start, el.end, el.center = m.start, m.end, m.center
            mirrored.append(el.id)
    return {"count": len(created) + len(mirrored),
            "ids": created or mirrored, "copied": created, "axis": axis,
            "pivot": pivot}


HANDLERS: Dict[str, Any] = {
    # ---- handlers ORIGINAIS do motor (importados, sem alterá-los) ----
    "move_element": _op_move,
    "set_position": _op_set_position,
    "set_post_height": _op_set_post_height,
    "add_beam": _op_add_beam,
    "add_post": _op_add_post,
    "add_plate": _op_add_plate,
    "duplicate_element": _op_duplicate,
    "delete_element": _op_delete,
    "update_profile": _op_update_profile,
    "rename_element": _op_rename,
    "set_shield": _op_set_shield,
    "multi_delete": _op_multi_delete,
    "multi_move": _op_multi_move,
    "multi_duplicate": _op_multi_duplicate,
    "multi_profile": _op_multi_profile,
    # formas paramétricas do motor (gaiola, círculo, grelha, painel)
    "set_panel": _op_set_panel,
    "add_circle": _op_add_circle,
    "add_box": _op_add_box,
    "add_grid": _op_add_grid,
    # ---- NOVOS (esta camada) ----
    "change_profile": _op_update_profile,      # alias pedido pelo usuário
    "copy_element": _op_duplicate,             # alias
    "add_element": _op_add_element,
    "add_diagonal": _op_add_diagonal,
    "resize_element": _op_resize,
    "replace_element": _op_replace,
    "rotate_element": _op_rotate,
    "set_group": _op_set_group,
    "set_role": _op_set_role,
    "align_elements": _op_align,
    "distribute_elements": _op_distribute,
    "mirror_elements": _op_mirror,
}


# ------------------------------------------------------------------- simular


def _sim_reset(sim: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """Operações de projeto inteiro dentro da SIMULAÇÃO (dry run)."""
    kind = op["operation"]
    if kind == "__blank":
        sim.elements = [e for e in sim.elements if e.type == "panel"] or []
        return {"reset": "blank"}
    pid = str(op.get("preset_id") or "").strip()
    if kind == "__regen":
        pid = pid or sim.preset_id or "REF_4000X2000"
    preset = load_preset(pid)
    if preset is None:
        raise OperationError(f"Preset '{pid}' não encontrado.")
    if preset.get("kind") == "snapshot":
        m2 = ProjectModel(**preset["model"])
    else:
        m2 = PresetBuilder(preset, op.get("overrides")).build()
    sim.project = m2.project
    sim.panel = m2.panel
    sim.installation = m2.installation
    sim.elements = m2.elements
    sim.preset_id = pid
    return {"reset": pid}


def apply_to_model(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica UMA operação (já normalizada) ao modelo — usado na simulação
    e no apply_batch. Operações __* de projeto inteiro têm caminho próprio."""
    kind = op["operation"]
    if kind in ("__blank", "__preset", "__regen"):
        return _sim_reset(model, op)
    h = HANDLERS.get(kind)
    if h is None:
        raise OperationError(f"Operação desconhecida: '{kind}'.")
    return h(model, op)


def _sig(e: Element) -> tuple:
    """Assinatura geométrica — detecta o que MUDOU no diff."""
    def v3(v):
        return None if v is None else (round(v.x, 3), round(v.y, 3), round(v.z, 3))
    return (e.type, e.role, e.profile, v3(e.start), v3(e.end), v3(e.center),
            round(e.size_x, 3), round(e.size_y, 3), round(e.size_z, 3), e.group)


def dry_run_diff(model: ProjectModel, ops: List[Any]) -> Dict[str, Any]:
    """Simula a lista de operações numa CÓPIA e devolve o diff SEM aplicar.

    retorno: {operations (normalizadas), added[], removed[], changed[],
              counts{add,edit,del,total}, errors[], elements_after}
    """
    sim = model.model_copy(deep=True)
    old = {e.id: e for e in model.elements}
    norm: List[Dict[str, Any]] = []
    errors: List[str] = []
    for raw in (ops or [])[:120]:
        try:
            op = normalize_op(raw)
        except OperationError as e:
            errors.append(str(e))
            continue
        norm.append(op)
        try:
            apply_to_model(sim, op)
        except OperationError as e:
            errors.append(f"{op['operation']}: {e}")
    added = [e.model_dump() for e in sim.elements if e.id not in old]
    removed = [old[i].model_dump() for i in old if i not in {e.id for e in sim.elements}]
    changed = []
    for e in sim.elements:
        o = old.get(e.id)
        if o is not None and _sig(o) != _sig(e):
            changed.append({"id": e.id, "before": o.model_dump(),
                            "after": e.model_dump()})
    return {"operations": norm, "added": added, "removed": removed,
            "changed": changed,
            "counts": {"add": len(added), "edit": len(changed),
                       "del": len(removed),
                       "total": len(added) + len(changed) + len(removed)},
            "errors": errors, "elements_after": len(sim.elements)}


def apply_batch(store, ops: List[Any], action: str = "ia") -> Dict[str, Any]:
    """Aplica a lista inteira com UM snapshot de undo (histórico unificado).

    ATÔMICO: as operações são SIMULADAS primeiro (dry run) — se qualquer uma
    for inválida, NADA é aplicado (sem lote pela metade).
    Operações __blank/__preset/__regen (projeto novo/regenerado) são roteadas
    para os métodos do ProjectStore mantendo a desfazibilidade.
    """
    norm = [normalize_op(op) for op in (ops or [])]
    if len(norm) > 120:
        raise OperationError("Máximo de 120 operações por lote.")
    if not norm:
        raise OperationError("Nenhuma operação para aplicar.")
    # —— validação prévia (all-or-nothing): simula e reprova se houver erro
    errs = dry_run_diff(store.ensure_loaded(), norm).get("errors", [])
    if errs:
        raise OperationError("Lote recusado (nada foi aplicado): " + " · ".join(errs[:3]))
    store.push_undo(action)  # UM snapshot — Ctrl+Z desfaz o lote inteiro
    model = store.ensure_loaded()
    applied: List[str] = []
    for op in norm:
        kind = op["operation"]
        if kind == "__preset":
            store.new_from_preset(op["preset_id"], keep_undo=True)
        elif kind == "__regen":
            pid = str(op.get("preset_id") or "").strip() or store.preset_id \
                or "REF_4000X2000"
            store.new_from_preset(pid, op.get("overrides"), keep_undo=True,
                                  undo_action="regen")
        else:
            # __blank e handlers semânticos mutam o modelo do store
            model = store.ensure_loaded()
            apply_to_model(model, op)
        applied.append(kind)
    store.log(action, f"Lote de {len(applied)} operação(ões): "
                      + ", ".join(applied[:8]) + ("…" if len(applied) > 8 else ""))
    store._persist()
    return {"count": len(applied), "operations": applied}
