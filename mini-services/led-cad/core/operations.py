"""Operações semânticas sobre o modelo (fonte de verdade em Python).

Toda edição (editor 3D ou IA) chega aqui como comando estruturado.
Exemplos:
  {"operation": "move_element", "element_id": "POSTE-01", "delta_x": -400}
  {"operation": "add_post", "x": 1200, "y": 0, "height": 3000}
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import geometry
from models.element import Element, Installation, Panel, ProjectMeta, ProjectModel, Vec3
from models.profile import get_profile
from services.preset_service import PresetBuilder, load_preset

UndoEntry = Dict[str, Any]
HistoryEntry = Dict[str, Any]

# Operações que afetam vários elementos de uma vez: 1 snapshot de undo só
# (Ctrl+Z desfaz o lote inteiro) e 1 linha no histórico.
BATCH_OPS = {"multi_delete", "multi_move", "multi_duplicate", "multi_profile"}

HISTORY_LIMIT = 120

SESSION_FILE = Path(__file__).resolve().parent.parent / "data" / "_session.json"


class OperationError(ValueError):
    pass


class ProjectStore:
    """Estado em memória do projeto ativo + pilha de undo (MVP sem DB).

    Mantém também um LOG de histórico (somente leitura na UI) das últimas
    ações — diferente do undo, o histórico nunca é descartado ao regenerar.
    """

    def __init__(self) -> None:
        self.model: Optional[ProjectModel] = None
        self.preset_id: str = ""
        self._undo: List[UndoEntry] = []
        self.history: List[HistoryEntry] = []
        self._seq: int = 0
        # F1: revisão monotônica (nunca retrocede com undo) e idempotência
        # de apply (reenvio da mesma chave + mesmo payload → mesmo resultado).
        self.revision: int = 0
        self.project_id: str = ""
        self._idem: Dict[str, Any] = {}  # key -> {"result", "payload_hash"}
        self.persist_state: str = "idle"  # idle|saving|saved|failed

    def bump_revision(self) -> int:
        """Commit validado: revisão avança sempre; undo NÃO retrocede."""
        self.revision += 1
        return self.revision

    def commit(self, action: str) -> int:
        """Fecha uma transação: revisão nova + persistência com estado visível
        (A17): falha de gravação é sinalizada, nunca engolida em silêncio."""
        self.bump_revision()
        if not self.project_id:
            self.project_id = f"proj-{int(time.time())}-{self._seq}"
            self._seq += 1
        self._persist()
        self.log("commit", f"Revisão {self.revision} — {action}.")
        return self.revision

    def idempotency(self, key: str, payload: Any) -> Optional[Dict[str, Any]]:
        """Devolve resultado memorizado p/ (chave, payload) repetidos, ou None.
        Mesma chave com payload diferente é CONFLITO (409)."""
        h = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        entry = self._idem.get(key)
        if entry is None:
            return None
        if entry["payload_hash"] != h:
            return {"conflict": True}
        return entry["result"]

    def remember(self, key: str, payload: Any, result: Dict[str, Any]) -> None:
        h = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        # retenção simples: últimas 64 chaves
        if len(self._idem) > 64:
            self._idem.pop(next(iter(self._idem)))
        self._idem[key] = {"payload_hash": h, "result": result}

    # ------------------------------------------------------------ ciclo
    def _persist(self) -> None:
        """Salva a sessão para sobreviver a reload do servidor.

        A17: falha de gravação é SINALIZADA (persist_state), nunca engolida —
        a UI pode mostrar 'falhou ao salvar' em vez de sucesso silencioso."""
        if self.model is None:
            return
        self.persist_state = "saving"
        try:
            SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
            SESSION_FILE.write_text(json.dumps({
                "model": self.model.model_dump(),
                "preset_id": self.preset_id,
                "project_id": self.project_id,
                "revision": self.revision,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }, ensure_ascii=False), encoding="utf-8")
            self.persist_state = "saved"
        except Exception:
            self.persist_state = "failed"  # sessão nunca derruba a API

    def _restore_session(self) -> bool:
        """Tenta restaurar a última sessão do disco. True se restaurou."""
        try:
            if not SESSION_FILE.exists():
                return False
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            model = ProjectModel(**data["model"])
            self.model = model
            self.preset_id = data.get("preset_id", "")
            self.project_id = data.get("project_id", "")
            self.revision = int(data.get("revision", 0) or 0)
            self.log("load", f"Sessão anterior restaurada ({data.get('saved_at', '')}) — "
                             f"{len(model.elements)} elementos.")
            return True
        except Exception:
            return False

    def new_from_preset(self, preset_id: str, overrides: Optional[dict] = None,
                        keep_undo: bool = False, undo_action: str = "regen") -> ProjectModel:
        preset = load_preset(preset_id)
        if preset is None:
            raise OperationError(f"Preset '{preset_id}' não encontrado.")
        if keep_undo:
            # regeneração paramétrica do MESMO projeto: é desfazível
            self.push_undo(undo_action)
        else:
            self._undo.clear()
        if preset.get("kind") == "snapshot":
            # Preset personalizado do usuário: modelo EXATO salvo (template).
            # Overrides paramétricos não se aplicam a snapshots.
            self.model = ProjectModel(**preset["model"])
        else:
            self.model = PresetBuilder(preset, overrides).build()
        # o preset ATIVO é sempre o que foi pedido (snapshot aponta o modelo
        # p/ o id do preset custom, não p/ o preset de origem)
        self.model.preset_id = preset_id
        self.preset_id = preset_id
        ov = overrides or {}
        detail = ", ".join(f"{k}={json_short(v)}" for k, v in ov.items()) or preset["name"]
        self.log("regen" if keep_undo else "novo",
                 f"{'Regenerado com' if keep_undo else 'Novo projeto'}: {detail}")
        self._persist()
        return self.model

    def ensure_loaded(self) -> ProjectModel:
        if self.model is None:
            if not self._restore_session():
                self.new_from_preset("REF_4000X2000")
        assert self.model is not None
        return self.model

    def new_blank(self) -> ProjectModel:
        """Novo projeto EM BRANCO para montagem LIVRE do zero: remove toda a
        estrutura e mantém apenas a superfície do painel como referência
        visual (pode ser ocultada pelo chip 'Painel'). Compatível com as
        ferramentas livres (Barra A→B com perfil escolhido) e com a IA."""
        cur = self.model
        if cur is not None:
            self.push_undo("blank")  # voltar ao estado anterior com Ctrl+Z
        panel = cur.panel if cur else Panel()
        inst = cur.installation if cur else Installation()
        model = ProjectModel(
            project=ProjectMeta(name="Projeto em branco"),
            panel=panel,
            installation=Installation(type=inst.type, posts=0,
                                      ground_clearance=inst.ground_clearance,
                                      environment=inst.environment),
            elements=[Element(
                id="PAINEL-LED", type="panel", role="panel",
                center=Vec3(x=0, y=0,
                            z=inst.ground_clearance + panel.height / 2),
                size_x=panel.width, size_y=50, size_z=panel.height,
                label="PAINEL DE LED", group="PAINEL",
            )],
            preset_id="BLANK",
        )
        self.model = model
        self.preset_id = "BLANK"
        self.log("novo", "Projeto EM BRANCO criado — montagem livre do zero "
                         "(Barra A→B, IA ou coordenadas).")
        self._persist()
        return model

    # ------------------------------------------------------------ undo
    def _snapshot(self, action: str) -> UndoEntry:
        return {"action": action, "model": self.model.model_copy(deep=True),
                "preset_id": self.preset_id}

    def push_undo(self, action: str) -> None:
        self._undo.append(self._snapshot(action))
        if len(self._undo) > 50:
            self._undo.pop(0)

    def undo(self) -> ProjectModel:
        if not self._undo:
            raise OperationError("Nada para desfazer.")
        snap = self._undo.pop()
        self.model = snap["model"]
        # o preset ativo também é estado: sem isto, desfazer um __blank deixava
        # preset_id="BLANK" e o próximo __regen falhava ('Preset BLANK não encontrado')
        if "preset_id" in snap:
            self.preset_id = snap["preset_id"]
        self.log("undo", f"Desfeita ação '{snap['action']}'.")
        self._persist()
        return self.model

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    # ------------------------------------------------------- histórico
    def log(self, action: str, detail: str = "") -> None:
        self.history.append({
            "time": time.strftime("%H:%M:%S"),
            "action": action,
            "detail": detail,
        })
        if len(self.history) > HISTORY_LIMIT:
            del self.history[: len(self.history) - HISTORY_LIMIT]

    def history_tail(self, n: int = 40) -> List[HistoryEntry]:
        return self.history[-n:][::-1]


# ------------------------------------------------------------- aplicar ops


def apply_operation(store: ProjectStore, op: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica uma operação semântica ao projeto ativo. Retorna resumo."""
    model = store.ensure_loaded()
    kind = str(op.get("operation", "")).strip().lower()

    handlers = {
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
        "multi_delete": _op_multi_delete,
        "multi_move": _op_multi_move,
        "multi_duplicate": _op_multi_duplicate,
        "multi_profile": _op_multi_profile,
        "set_shield": _op_set_shield,
        # ---- desenho LIVRE (IA): formas paramétricas que geram várias barras
        # com 1 operação (1 passo de undo só) ----
        "set_panel": _op_set_panel,
        "add_circle": _op_add_circle,
        "add_box": _op_add_box,
        "add_grid": _op_add_grid,
    }
    if kind not in handlers:
        raise OperationError(f"Operação desconhecida: '{kind}'.")
    # A07: undo somente APÓS a operação validar e executar — snapshot
    # órfão faz Ctrl+Z consumir um passo sem mudança.
    store.push_undo(kind)
    summary = handlers[kind](model, op)
    store.log(kind, _history_detail(kind, op, summary))
    store._persist()
    return {"operation": kind, **summary}


def _ids_from_op(op: Dict[str, Any]) -> List[str]:
    """Normaliza a lista de IDs de uma operação em lote (element_ids)."""
    raw = op.get("element_ids") or []
    if isinstance(raw, str):
        raw = [raw]
    ids: List[str] = []
    for x in raw:
        s = str(x).strip().upper()
        if s and s not in ids:
            ids.append(s)
    if not ids:
        raise OperationError("Informe 'element_ids' (lista de IDs).")
    return ids


def _op_set_shield(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """Marca/desmarca elementos como ABRIGO de vento (sombreiam o painel).

    Aceita 'element_ids' (lote) ou 'element_id' único; 'value' define o
    estado (default True). O efeito no vento é calculado em core/wind.py
    pela ÁREA PROJETADA dos elementos marcados na direção do vento."""
    raw = op.get("element_ids") or ([op["element_id"]] if op.get("element_id") else [])
    ids = _ids_from_op({**op, "element_ids": raw})
    value = bool(op.get("value", True))
    known = model.index()
    changed: List[str] = []
    for eid in ids:
        el = known.get(eid)
        if el is not None and bool(el.shield) != value:
            el.shield = value
            changed.append(eid)
    if not changed and value:
        # todos já estavam marcados — não é erro, mas informa
        return {"count": 0, "ids": [], "shield": value,
                "already": [i for i in ids if i in known]}
    return {"count": len(changed), "ids": changed, "shield": value}


def _op_multi_delete(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    ids = _ids_from_op(op)
    known = model.index()
    found = [i for i in ids if i in known]
    if not found:
        raise OperationError(f"Nenhum dos elementos existe: {', '.join(ids)}.")
    found_set = set(found)
    before = len(model.elements)
    model.elements = [e for e in model.elements if e.id not in found_set]
    return {"count": len(found), "ids": found,
            "skipped": [i for i in ids if i not in found_set]}


def _op_multi_move(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    ids = _ids_from_op(op)
    dx, dy, dz = float(op.get("delta_x", 0)), float(op.get("delta_y", 0)), float(op.get("delta_z", 0))
    if abs(dx) + abs(dy) + abs(dz) < 1e-9:
        raise OperationError("Informe delta_x/delta_y/delta_z (em mm).")
    moved: List[str] = []
    for eid in ids:
        try:
            _op_move(model, {"element_id": eid, "delta_x": dx, "delta_y": dy, "delta_z": dz})
            moved.append(eid)
        except OperationError:
            continue
    if not moved:
        raise OperationError("Nenhum elemento válido para mover.")
    return {"count": len(moved), "ids": moved, "delta": [dx, dy, dz]}


def _op_multi_duplicate(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    ids = _ids_from_op(op)
    created: List[str] = []
    for eid in ids:
        try:
            res = _op_duplicate(model, {"element_id": eid,
                                        "delta_x": op.get("delta_x", 0),
                                        "delta_y": op.get("delta_y", 0),
                                        "delta_z": op.get("delta_z", 0)})
            created.append(res["element_id"])
        except OperationError:
            continue
    if not created:
        raise OperationError("Nenhum elemento válido para duplicar.")
    return {"count": len(created), "ids": created}


def _op_multi_profile(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    ids = _ids_from_op(op)
    profile = op.get("profile")
    if not profile:
        raise OperationError("Informe o novo 'profile'.")
    get_profile(profile)  # valida antes de tocar no modelo
    changed: List[str] = []
    for eid in ids:
        try:
            _op_update_profile(model, {"element_id": eid, "profile": profile})
            changed.append(eid)
        except OperationError:
            continue
    if not changed:
        raise OperationError("Nenhum elemento válido para trocar o perfil.")
    return {"count": len(changed), "ids": changed, "profile": profile}


def _get(model: ProjectModel, element_id: str) -> Element:
    el = model.index().get(element_id.strip().upper())
    if el is None:
        raise OperationError(f"Elemento '{element_id}' não existe.")
    return el


def _op_move(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    el = _get(model, op["element_id"])
    dx, dy, dz = float(op.get("delta_x", 0)), float(op.get("delta_y", 0)), float(op.get("delta_z", 0))
    if el.start and el.end:
        el.start = Vec3(x=el.start.x + dx, y=el.start.y + dy, z=el.start.z + dz)
        el.end = Vec3(x=el.end.x + dx, y=el.end.y + dy, z=el.end.z + dz)
    if el.center:
        el.center = Vec3(x=el.center.x + dx, y=el.center.y + dy, z=el.center.z + dz)
    return {"element_id": el.id, "delta": [dx, dy, dz]}


def _op_set_position(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    el = _get(model, op["element_id"])
    if el.type == "beam" and el.start and el.end:
        dx = el.end.x - el.start.x
        dy = el.end.y - el.start.y
        dz = el.end.z - el.start.z
        if "start" in op:
            el.start = Vec3(**op["start"])
        if "end" in op:
            el.end = Vec3(**op["end"])
        if op.get("keep_length") and ("start" in op) ^ ("end" in op):
            el.end = Vec3(x=el.start.x + dx, y=el.start.y + dy, z=el.start.z + dz)
    elif el.center is not None and "center" in op:
        el.center = Vec3(**op["center"])
    return {"element_id": el.id}


def _op_set_post_height(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """Ajusta um poste de solo e translada a superestrutura apoiada nele."""
    post = _get(model, op["element_id"])
    if post.type != "beam" or post.role != "post" or not post.start or not post.end:
        raise OperationError("set_post_height so pode ser usado em um poste.")
    if (abs(post.start.x - post.end.x) > 1e-6 or
            abs(post.start.y - post.end.y) > 1e-6 or
            min(post.start.z, post.end.z) > 100.0):
        raise OperationError("O poste precisa ser vertical e estar ancorado no solo.")
    height = float(op.get("height", 0))
    if height <= 0:
        raise OperationError("A altura do poste deve ser maior que zero.")

    base_is_start = post.start.z <= post.end.z
    old_top = post.end.z if base_is_start else post.start.z
    base_z = post.start.z if base_is_start else post.end.z
    new_top = base_z + height
    delta_z = new_top - old_top
    if abs(delta_z) < 1e-6:
        return {"element_id": post.id, "old_height": height, "height": height,
                "delta_z": 0.0, "moved_ids": [], "linked_posts": [post.id]}

    # Tolera chapas de ligacao na cota de apoio, sem capturar a fundacao.
    tolerance = 50.0
    linked_posts: List[str] = []
    for el in model.elements:
        if (el.type != "beam" or el.role != "post" or not el.start or not el.end):
            continue
        if (abs(el.start.x - el.end.x) > 1e-6 or abs(el.start.y - el.end.y) > 1e-6
                or min(el.start.z, el.end.z) > 100.0):
            continue
        top_is_end = el.end.z >= el.start.z
        top_z = el.end.z if top_is_end else el.start.z
        if abs(top_z - old_top) <= tolerance:
            if top_is_end:
                el.end = Vec3(x=el.end.x, y=el.end.y, z=el.end.z + delta_z)
            else:
                el.start = Vec3(x=el.start.x, y=el.start.y, z=el.start.z + delta_z)
            linked_posts.append(el.id)

    moved_ids: List[str] = []
    linked_set = set(linked_posts)
    for el in model.elements:
        if el.id in linked_set or el.role == "base":
            continue
        if el.start and el.end:
            # Geometria que parte do solo permanece como contraventamento.
            if min(el.start.z, el.end.z) < old_top - tolerance:
                continue
            el.start = Vec3(x=el.start.x, y=el.start.y, z=el.start.z + delta_z)
            el.end = Vec3(x=el.end.x, y=el.end.y, z=el.end.z + delta_z)
            moved_ids.append(el.id)
        elif el.center:
            bottom_z = el.center.z - (el.size_z / 2 if el.type == "plate" else 0)
            if bottom_z < old_top - tolerance:
                continue
            el.center = Vec3(x=el.center.x, y=el.center.y, z=el.center.z + delta_z)
            moved_ids.append(el.id)

    return {"element_id": post.id, "old_height": old_top, "height": height,
            "delta_z": delta_z, "moved_ids": moved_ids,
            "linked_posts": linked_posts}


def _op_add_beam(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    profile = op.get("profile") or "METALON_40x40x2"
    get_profile(profile)  # valida
    el = Element(
        id=model.next_id("BX"),
        type="beam", role=op.get("role", "other"), profile=profile,
        start=Vec3(**op["start"]), end=Vec3(**op["end"]),
        label=op.get("label", ""), group=op.get("group", "ADICIONADOS"),
    )
    model.elements.append(el)
    return {"element_id": el.id, "length": round(el.length(), 1)}


def _op_add_post(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    x = float(op.get("x", 0))
    y = float(op.get("y", 0))
    height = float(op.get("height", model.installation.ground_clearance))
    profile = op.get("profile") or "TUBO_219x4.75"
    get_profile(profile)
    el = Element(
        id=model.next_id("POSTE-"),
        type="beam", role="post", profile=profile,
        start=Vec3(x=x, y=y, z=0), end=Vec3(x=x, y=y, z=height),
        label="", group="POSTES",
    )
    model.elements.append(el)
    return {"element_id": el.id}


def _op_add_plate(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    el = Element(
        id=model.next_id("PLACA-"),
        type="plate", role="plate",
        center=Vec3(**op.get("center", {"x": 0, "y": 0, "z": 0})),
        size_x=float(op.get("size_x", 200)), size_y=float(op.get("size_y", 200)),
        size_z=float(op.get("size_z", 10)),
        label=op.get("label", ""), group="CHAPAS",
    )
    model.elements.append(el)
    return {"element_id": el.id}


def _op_duplicate(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    src = _get(model, op["element_id"])
    clone = src.model_copy(deep=True)
    clone.id = _unique_id(model, src)
    dx, dy, dz = float(op.get("delta_x", 0)), float(op.get("delta_y", 0)), float(op.get("delta_z", 0))
    if clone.start and clone.end:
        clone.start = Vec3(x=clone.start.x + dx, y=clone.start.y + dy, z=clone.start.z + dz)
        clone.end = Vec3(x=clone.end.x + dx, y=clone.end.y + dy, z=clone.end.z + dz)
    if clone.center:
        clone.center = Vec3(x=clone.center.x + dx, y=clone.center.y + dy, z=clone.center.z + dz)
    model.elements.append(clone)
    return {"element_id": clone.id, "from": src.id}


def _unique_id(model: ProjectModel, src: Element) -> str:
    """Próximo ID mantendo o PADRÃO do original (V01 -> V11, BASE-01 -> BASE-03)."""
    m = re.match(r"^(.*?)(\d+)$", src.id)
    base = (m.group(1) if m and m.group(1) else "EL").upper()
    used = {e.id for e in model.elements}
    n = 1
    while f"{base}{n:02d}" in used:
        n += 1
    return f"{base}{n:02d}"


def _op_delete(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    el = _get(model, op["element_id"])
    model.elements = [e for e in model.elements if e.id != el.id]
    return {"element_id": el.id, "deleted": True}


def _op_update_profile(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    el = _get(model, op["element_id"])
    profile = op.get("profile")
    if not profile:
        raise OperationError("Informe o novo 'profile'.")
    get_profile(profile)
    el.profile = profile
    return {"element_id": el.id, "profile": profile}


def _op_rename(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    el = _get(model, op["element_id"])
    new_id = str(op.get("new_id", "")).strip().upper()
    if not new_id:
        raise OperationError("Informe 'new_id'.")
    if new_id in model.index():
        raise OperationError(f"ID '{new_id}' já está em uso.")
    el.id = new_id
    return {"element_id": new_id}


# ==================================================================== DESENHO
# LIVRE — formas paramétricas p/ o copiloto de IA construir QUALQUER coisa
# (painéis, círculos, cubos, casas, torres…) sem depender de preset.


def _op_set_panel(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """Dimensiona a SUPERFÍCIE DE REFERÊNCIA do painel (ou área de desenho).

    Aceita width/height/depth (mm), ground_clearance (base do painel ao solo)
    e visible (true/false — oculta/exibe a referência visual, p/ desenho
    livre como painéis circulares). NÃO toca nas barras já desenhadas."""
    p = model.panel
    changed: List[str] = []
    if "width" in op:
        p.width = max(200.0, float(op["width"]))
        changed.append("largura")
    if "height" in op:
        p.height = max(200.0, float(op["height"]))
        changed.append("altura")
    if "depth" in op:
        p.depth = max(50.0, float(op["depth"]))
        changed.append("profundidade")
    if "ground_clearance" in op:
        model.installation.ground_clearance = max(0.0, float(op["ground_clearance"]))
        changed.append("pé-direito")
    visible = op.get("visible")
    panel_el = next((e for e in model.elements if e.type == "panel"), None)
    if visible is False:
        if panel_el is not None:
            model.elements = [e for e in model.elements if e.type != "panel"]
            changed.append("referência oculta")
    else:
        gc = model.installation.ground_clearance
        center = Vec3(x=0, y=0, z=gc + p.height / 2)
        if panel_el is None:
            panel_el = Element(
                id="PAINEL-LED", type="panel", role="panel", center=center,
                size_x=p.width, size_y=50, size_z=p.height,
                label="PAINEL DE LED", group="PAINEL")
            model.elements.append(panel_el)
            changed.append("referência criada")
        else:
            panel_el.center = center
            panel_el.size_x = p.width
            panel_el.size_z = p.height
            if changed:
                changed.append("referência atualizada")
    if not changed:
        raise OperationError(
            "set_panel: informe width/height/depth/ground_clearance (mm) "
            "e/ou visible true|false.")
    return {"count": len(changed), "panel": p.model_dump(),
            "changed": ", ".join(changed)}


def _ring_points(cx: float, cy: float, cz: float, radius: float,
                 segments: int, plane: str) -> List[Vec3]:
    """Vértices de um polígono regular (anel) no plano pedido."""
    pts: List[Vec3] = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        cos_a, sin_a = math.cos(a), math.sin(a)
        if plane == "horizontal":      # plano XY (teto/piso)
            pts.append(Vec3(x=cx + radius * cos_a, y=cy + radius * sin_a, z=cz))
        elif plane == "lateral":       # plano YZ
            pts.append(Vec3(x=cx, y=cy + radius * cos_a, z=cz + radius * sin_a))
        else:                          # "frontal" — plano XZ (padrão)
            pts.append(Vec3(x=cx + radius * cos_a, y=cy, z=cz + radius * sin_a))
    return pts


def _op_add_circle(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """CÍRCULO/ANEL/POLÍGONO regular de barras (desenho livre).

    {"operation":"add_circle","center":{"x":0,"y":0,"z":5000},"radius":1000,
     "segments":16,"plane":"frontal","profile":"METALON_40x40x2"}
    segments: 3–48 (16–24 = círculo liso; 6 = hexágono; 8 = octógono).
    plane: frontal (XZ) | horizontal (XY) | lateral (YZ).
    closed: false → arco aberto (não fecha o anel)."""
    c = op.get("center") or {"x": 0, "y": 0, "z": 0}
    cx, cy, cz = float(c.get("x", 0)), float(c.get("y", 0)), float(c.get("z", 0))
    radius = float(op.get("radius", 0))
    if radius <= 0:
        raise OperationError("add_circle: informe 'radius' em mm (> 0).")
    segments = int(op.get("segments", 16))
    if not 3 <= segments <= 48:
        raise OperationError("add_circle: 'segments' deve ser 3–48.")
    plane = str(op.get("plane", "frontal")).lower()
    profile = op.get("profile") or "METALON_40x40x2"
    get_profile(profile)
    closed = bool(op.get("closed", True))
    group = op.get("group", "CÍRCULO")
    role = op.get("role", "other")
    pts = _ring_points(cx, cy, cz, radius, segments, plane)
    created: List[str] = []
    n_edges = segments if closed else segments - 1
    for i in range(n_edges):
        a, b = pts[i], pts[(i + 1) % segments]
        el = Element(
            id=model.next_id("CIR"), type="beam", role=role, profile=profile,
            start=a, end=b, group=group,
            label=f"{group} seg {i + 1}/{segments}")
        model.elements.append(el)
        created.append(el.id)
    return {"count": len(created), "ids": created,
            "segments": segments, "radius": radius, "plane": plane}


def _box_vertices(op: Dict[str, Any]) -> List[Vec3]:
    """8 vértices de um paralelepípedo a partir de center+w/d/h OU corner1/corner2."""
    if "corner1" in op and "corner2" in op:
        c1, c2 = op["corner1"], op["corner2"]
        x0, x1 = sorted((float(c1["x"]), float(c2["x"])))
        y0, y1 = sorted((float(c1["y"]), float(c2["y"])))
        z0, z1 = sorted((float(c1["z"]), float(c2["z"])))
    else:
        c = op.get("center") or {"x": 0, "y": 0, "z": 0}
        cx, cy, cz = float(c.get("x", 0)), float(c.get("y", 0)), float(c.get("z", 0))
        w = float(op.get("width", 0))
        d = float(op.get("depth", 0))
        h = float(op.get("height", 0))
        if min(w, d, h) <= 0:
            raise OperationError(
                "add_box: informe width/depth/height (mm) OU corner1+corner2.")
        x0, x1 = cx - w / 2, cx + w / 2
        y0, y1 = cy - d / 2, cy + d / 2
        z0, z1 = cz - h / 2, cz + h / 2
    return [Vec3(x=x, y=y, z=z)
            for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def _op_add_box(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """GAIOLA/PARALELEPÍPEDO de barras — as 12 arestas (desenho livre).

    {"operation":"add_box","center":{"x":0,"y":0,"z":3480},
     "width":1920,"depth":800,"height":960,"profile":"METALON_60x60x2"}"""
    profile = op.get("profile") or "METALON_40x40x2"
    get_profile(profile)
    v = _box_vertices(op)
    edges = [
        (0, 1), (2, 3), (4, 5), (6, 7),          # verticais (Z)
        (0, 2), (1, 3), (4, 6), (5, 7),          # profundas (Y)
        (0, 4), (1, 5), (2, 6), (3, 7),          # horizontais (X)
    ]
    group = op.get("group", "GAIOLA")
    created: List[str] = []
    for i, (a, b) in enumerate(edges, start=1):
        el = Element(
            id=model.next_id("BX"), type="beam",
            role=op.get("role", "other"), profile=profile,
            start=v[a], end=v[b], group=group,
            label=f"{group} aresta {i}/12")
        model.elements.append(el)
        created.append(el.id)
    return {"count": len(created), "ids": created}


def _op_add_grid(model: ProjectModel, op: Dict[str, Any]) -> Dict[str, Any]:
    """GRELHA retangular de barras (montantes/travessas de gabinetes etc.).

    {"operation":"add_grid","start":{"x":-960,"y":400,"z":3000},
     "end":{"x":960,"y":400,"z":3960},"cols":2,"rows":1,
     "profile":"METALON_60x60x2","border":true}
    cols/rows = nº de MÓDULOS (bays) ao longo dos DOIS eixos do retângulo
    → barras internas = cols-1 / rows-1 (paralelas ao outro eixo).
    border:true inclui também as 4 arestas do perímetro.
    start/end devem estar NO MESMO PLANO (um eixo com extensão 0)."""
    s, e = op.get("start"), op.get("end")
    if not s or not e:
        raise OperationError("add_grid: informe 'start' e 'end' (cantos do retângulo).")
    sv = Vec3(**{k: float(s.get(k, 0)) for k in ("x", "y", "z")})
    ev = Vec3(**{k: float(e.get(k, 0)) for k in ("x", "y", "z")})
    ext = {"x": abs(ev.x - sv.x), "y": abs(ev.y - sv.y), "z": abs(ev.z - sv.z)}
    fixed = min(ext, key=ext.get)
    if ext[fixed] > 1e-6:
        raise OperationError("add_grid: start/end devem estar NO MESMO PLANO "
                             "(um dos eixos com a mesma coordenada).")
    spans = [a for a in ("x", "y", "z") if a != fixed]
    cols = max(1, int(op.get("cols", 1)))
    rows = max(1, int(op.get("rows", 1)))
    profile = op.get("profile") or "METALON_40x40x2"
    get_profile(profile)
    border = bool(op.get("border", False))
    group = op.get("group", "GRELHA")

    def at(v: Vec3, axis: str, newval: float) -> Vec3:
        d = {"x": v.x, "y": v.y, "z": v.z}
        d[axis] = newval
        return Vec3(**d)

    created: List[str] = []

    def bar(p0: Vec3, p1: Vec3) -> None:
        r = "vertical" if abs(p1.z - p0.z) >= max(abs(p1.x - p0.x),
                                                 abs(p1.y - p0.y)) else "horizontal"
        el = Element(id=model.next_id("G"), type="beam", role=r, profile=profile,
                     start=p0, end=p1, group=group, label=group)
        model.elements.append(el)
        created.append(el.id)

    s0, s1 = spans
    if border:
        bar(sv, at(sv, s0, getattr(ev, s0)))
        bar(at(sv, s1, getattr(ev, s1)), ev)
        bar(sv, at(sv, s1, getattr(ev, s1)))
        bar(at(sv, s0, getattr(ev, s0)), ev)
    # internas ao longo de s0 (cols módulos) — barras paralelas a s1
    for i in range(1, cols):
        t = i / cols
        v0 = getattr(sv, s0) + (getattr(ev, s0) - getattr(sv, s0)) * t
        p0 = at(sv, s0, v0)
        bar(p0, at(p0, s1, getattr(ev, s1)))
    # internas ao longo de s1 (rows módulos) — barras paralelas a s0
    for j in range(1, rows):
        t = j / rows
        v1 = getattr(sv, s1) + (getattr(ev, s1) - getattr(sv, s1)) * t
        p0 = at(sv, s1, v1)
        bar(p0, at(p0, s0, getattr(ev, s0)))
    if not created:
        raise OperationError("add_grid: nada a criar (cols/rows=1 e border=false).")
    return {"count": len(created), "ids": created, "cols": cols, "rows": rows}


# ------------------------------------------------------------- histórico
def _fmt_delta(op: Dict[str, Any]) -> str:
    parts = []
    for axis in ("x", "y", "z"):
        v = float(op.get(f"delta_{axis}", 0) or 0)
        if abs(v) >= 1e-9:
            parts.append(f"{v:+.0f}mm {axis.upper()}")
    return ", ".join(parts) or "0mm"


def _history_detail(kind: str, op: Dict[str, Any], summary: Dict[str, Any]) -> str:
    eid = summary.get("element_id", op.get("element_id", ""))
    if kind == "move_element":
        return f"{eid} movido ({_fmt_delta(op)})"
    if kind == "set_position":
        return f"{eid}: posição atualizada"
    if kind == "set_post_height":
        moved = len(summary.get("moved_ids", []))
        return (f"{eid}: altura ajustada para {summary.get('height', 0):.0f} mm; "
                f"superestrutura acompanhou ({moved} elemento(s))")
    if kind == "add_beam":
        return f"Barra {eid} criada ({summary.get('length', 0):.0f} mm)"
    if kind == "add_post":
        return f"Poste {eid} criado em X={float(op.get('x', 0)):.0f}"
    if kind == "add_plate":
        return f"Chapa {eid} criada"
    if kind == "duplicate_element":
        return f"{op.get('element_id', '')} duplicado como {eid}"
    if kind == "delete_element":
        return f"{eid} excluído"
    if kind == "update_profile":
        return f"Perfil de {eid} → {summary.get('profile', '')}"
    if kind == "rename_element":
        return f"{op.get('element_id', '')} renomeado para {eid}"
    # ---- em lote ----
    n = summary.get("count", 0)
    ids = summary.get("ids", [])
    shown = ", ".join(ids[:4]) + (f" … (+{n - 4})" if n > 4 else "")
    if kind == "multi_delete":
        return f"{n} elemento(s) excluídos em lote: {shown}"
    if kind == "multi_move":
        d = summary.get("delta", [0, 0, 0])
        delta = ", ".join(f"{v:+.0f}{a}" for a, v in zip(("X", "Y", "Z"), d) if abs(v) >= 1e-9) or "0"
        return f"{n} elemento(s) movidos ({delta}): {shown}"
    if kind == "multi_duplicate":
        return f"{n} elemento(s) duplicados: {shown}"
    if kind == "multi_profile":
        return f"Perfil de {n} elemento(s) → {summary.get('profile', '')}: {shown}"
    if kind == "set_shield":
        verb = "marcados como abrigo 🛡" if summary.get("shield") else "desmarcados do abrigo"
        if n == 0:
            return "Abrigo de vento: nenhum elemento alterado (já estava no estado pedido)"
        return f"{n} elemento(s) {verb}: {shown}"
    # ---- desenho livre ----
    if kind == "set_panel":
        return f"Painel de referência: {summary.get('changed', 'atualizado')}"
    if kind == "add_circle":
        return (f"Círculo Ø{summary.get('radius', 0):.0f} mm criado "
                f"({summary.get('segments', 0)} segmentos, plano {summary.get('plane', '')})")
    if kind == "add_box":
        return f"Gaiola/pé direito: {n} arestas criadas ({', '.join(ids[:4])}…)"
    if kind == "add_grid":
        return f"Grelha {summary.get('cols', 1)}×{summary.get('rows', 1)}: {n} barras ({', '.join(ids[:4])}…)"
    return kind


def json_short(v: Any) -> str:
    if isinstance(v, dict):
        inner = ", ".join(f"{k}={json_short(x)}" for k, x in v.items())
        return f"{{{inner}}}"
    if isinstance(v, float):
        return f"{v:.0f}"
    return str(v)
