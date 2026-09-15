"""Contrato estruturado único da resposta de IA do CAD (LED STRUCTURE CAD).

Fonte única para:
1. JSON Schema de resposta {explain, ops} (structured output do Groq);
2. validação local da resposta ANTES do dry-run;
3. texto curto de contrato operacional para o prompt;
4. avaliação semântica (normalização + dry_run_diff em CÓPIA do modelo) e
   orquestração com no MÁXIMO 1 retry guiado.

O discriminador canônico é `operation` (nunca `op`; `type` só existe como
compatibilidade de ENTRADA em normalize_op e não aparece neste contrato).
Sem dependências novas: JSON Schema montado a partir da tabela real de
operações aceitas por core.ai_ops.HANDLERS / apply_to_model.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

_NUM, _STR, _BOOL = "num", "str", "bool"
_VEC, _ARR, _OBJ = "vec", "arr", "obj"
_SELECT = "__select"

# {operation: (obrigatórios, opcionais)} — mm; campos não listados não existem
OPS: Dict[str, Tuple[Dict[str, str], Dict[str, str]]] = {
    "__blank": ({}, {}),
    "__preset": ({"preset_id": _STR}, {"overrides": _OBJ}),
    "__regen": ({}, {"preset_id": _STR, "overrides": _OBJ}),
    "set_panel": ({}, {"width": _NUM, "height": _NUM, "depth": _NUM,
                       "ground_clearance": _NUM, "visible": _BOOL}),
    "add_box": ({}, {"center": _VEC, "width": _NUM, "depth": _NUM,
                     "height": _NUM, "corner1": _VEC, "corner2": _VEC,
                     "group": _STR, "role": _STR, "profile": _STR}),
    "add_grid": ({"start": _VEC, "end": _VEC},
                 {"cols": _NUM, "rows": _NUM, "border": _BOOL,
                  "group": _STR, "profile": _STR}),
    "add_circle": ({"radius": _NUM},
                   {"center": _VEC, "segments": _NUM, "plane": _STR,
                    "closed": _BOOL, "group": _STR, "role": _STR,
                    "profile": _STR}),
    "add_beam": ({"start": _VEC, "end": _VEC},
                 {"role": _STR, "group": _STR, "profile": _STR,
                  "label": _STR}),
    "add_post": ({}, {"x": _NUM, "y": _NUM, "height": _NUM, "profile": _STR}),
    "add_plate": ({}, {"center": _VEC, "size_x": _NUM, "size_y": _NUM,
                       "size_z": _NUM, "group": _STR, "label": _STR}),
    "add_element": ({}, {"etype": _STR, "element_type": _STR, "start": _VEC,
                         "end": _VEC, "center": _VEC, "size_x": _NUM,
                         "size_y": _NUM, "size_z": _NUM, "role": _STR,
                         "group": _STR, "profile": _STR}),
    "add_diagonal": ({}, {"start": _VEC, "end": _VEC, "from_element": _STR,
                          "to_element": _STR, "role": _STR, "group": _STR,
                          "profile": _STR}),
    "move_element": ({"element_id": _STR},
                     {"delta_x": _NUM, "delta_y": _NUM, "delta_z": _NUM}),
    "set_position": ({"element_id": _STR},
                     {"start": _VEC, "end": _VEC, "center": _VEC,
                      "keep_length": _BOOL}),
    "set_post_height": ({"element_id": _STR, "height": _NUM}, {}),
    "resize_element": ({"element_id": _STR},
                       {"length": _NUM, "anchor": _STR, "size_x": _NUM,
                        "size_y": _NUM, "size_z": _NUM}),
    "replace_element": ({"element_id": _STR},
                        {"new_type": _STR, "etype": _STR, "start": _VEC,
                         "end": _VEC, "center": _VEC, "profile": _STR,
                         "role": _STR, "group": _STR, "size_x": _NUM,
                         "size_y": _NUM, "size_z": _NUM}),
    "rotate_element": ({"element_id": _STR},
                       {"axis": _STR, "angle_deg": _NUM, "center": _VEC}),
    "duplicate_element": ({"element_id": _STR},
                          {"delta_x": _NUM, "delta_y": _NUM, "delta_z": _NUM}),
    "copy_element": ({"element_id": _STR},
                     {"delta_x": _NUM, "delta_y": _NUM, "delta_z": _NUM}),
    "delete_element": ({"element_id": _STR}, {}),
    "update_profile": ({"element_id": _STR, "profile": _STR}, {}),
    "change_profile": ({"element_id": _STR, "profile": _STR}, {}),
    "rename_element": ({"element_id": _STR, "new_id": _STR}, {}),
    "set_group": ({"element_id": _STR}, {"group": _STR}),
    "set_role": ({"element_id": _STR, "role": _STR}, {}),
    "set_shield": ({}, {"element_ids": _ARR, "element_id": _STR,
                        "value": _BOOL}),
    "multi_delete": ({"element_ids": _ARR}, {}),
    "multi_move": ({"element_ids": _ARR},
                   {"delta_x": _NUM, "delta_y": _NUM, "delta_z": _NUM}),
    "multi_duplicate": ({"element_ids": _ARR},
                        {"delta_x": _NUM, "delta_y": _NUM, "delta_z": _NUM}),
    "multi_profile": ({"element_ids": _ARR, "profile": _STR}, {}),
    "align_elements": ({"element_ids": _ARR},
                       {"axis": _STR, "anchor": _STR}),
    "distribute_elements": ({"element_ids": _ARR}, {"axis": _STR}),
    "mirror_elements": ({"element_ids": _ARR},
                        {"plane": _STR, "axis": _STR, "pivot": _NUM,
                         "copy": _BOOL}),
    "__select": ({"ids": _ARR}, {}),
}

_JSON_TYPE = {"str": "string", "num": "number", "bool": "boolean",
              "arr": "array"}


def _vec_schema() -> Dict[str, Any]:
    return {"type": ["object", "null"],
            "properties": {k: {"type": ["number", "null"]}
                           for k in ("x", "y", "z")},
            "required": ["x", "y", "z"], "additionalProperties": False}


def _prop_schema(t: str, nullable: bool) -> Dict[str, Any]:
    """Schema de UM campo. ÚNICA implementação canônica.

    Arrays do contrato são listas de IDs → `items: {"type":"string"}` explícito
    (exigência do structured output estrito)."""
    if t == _VEC:
        s = _vec_schema()
        if not nullable:
            s["type"] = "object"
        return s
    if t == _OBJ:
        s = {"type": "object"}
        return {"type": ["object", "null"]} if nullable else s
    if t == _ARR:
        items = {"type": "string"}
        return ({"type": ["array", "null"], "items": items} if nullable
                else {"type": "array", "items": items})
    base = {"type": _JSON_TYPE[t]}
    return {"type": [base["type"], "null"]} if nullable else base


def response_schema(strict: bool = True) -> Dict[str, Any]:
    """JSON Schema {explain, ops} com variantes reais por `operation` (anyOf).
    Campos opcionais ficam `required` porém anuláveis — exigência do modo
    estrito do Groq/OpenAI. Em modo estrito, operações com objeto livre
    (`__preset`/`__regen` overrides) ficam de fora (não expressáveis em schema
    estrito); a validação local continua as aceitando. Não ensina `type` nem `op`."""
    variants: List[Dict[str, Any]] = []
    for name, (req, opt) in OPS.items():
        if strict and any(t == _OBJ for t in list(req.values()) + list(opt.values())):
            continue
        props: Dict[str, Any] = {"operation": {"const": name}}
        required = ["operation"]
        for fname, t in req.items():
            props[fname] = _prop_schema(t, False)
            required.append(fname)
        for fname, t in opt.items():
            props[fname] = _prop_schema(t, True)
            required.append(fname)
        variants.append({"type": "object", "properties": props,
                         "required": required, "additionalProperties": False})
    return {
        "type": "object",
        "properties": {
            "explain": {"type": "string"},
            "ops": {"type": "array", "items": {"anyOf": variants}},
        },
        "required": ["explain", "ops"],
        "additionalProperties": False,
    }


RESPONSE_SCHEMA = response_schema(strict=True)  # constante usada por main.py


def contract_text() -> str:
    """Complemento curto de contrato operacional para o prompt (usado quando
    o provedor tem structured output). Não substitui o guia técnico."""
    names = ", ".join(sorted(OPS.keys()))
    return (
        "EXECUTION CONTRACT\n"
        'Retorne somente {"explain":"...","ops":[...]}.\n'
        "Use somente `operation` e os campos documentados.\n"
        "Se intent for NEW, GLOBAL_RESIZE ou LOCAL_EDIT e os dados forem "
        "suficientes, ops precisa alterar realmente o modelo. Não descreva o "
        "que faria.\n"
        "ops=[] só é permitido para pergunta ou ambiguidade geométrica real.\n"
        "Antes de responder, confirme mentalmente: aplicar minhas ops muda o "
        f"canvas?\nOperações válidas: {names}.\n"
        "add_box usa center+width/depth/height OU corner1/corner2 (nunca x/y/z "
        "soltos); add_post usa x/y/height.")


# ------------------------------------------------------------------ validação
def _sanitize_strict_nulls(op: Dict[str, Any], spec_req: Dict[str, str],
                           spec_opt: Dict[str, str]) -> Dict[str, Any]:
    """Traduz a resposta STRICT (structured output Groq GPT-OSS: TODO campo
    declarado vem presente, opcionais podem vir `null`) para o formato
    canônico ESPARSO que o motor (`normalize_op`/handlers) consome:

    - opcional com `null` → chave REMOVIDA (nunca chega `None` ao executor);
    - obrigatório com `null` → chave removida e o check de obrigatórios
      abaixo gera erro claro;
    - `operation` NUNCA é removida;
    - `False`, `0`, `[]` e `""` permanecem (só `None` é descartado);
    - Vec com componente nula (`{"x":0,"y":null,"z":0}`) → tratado como
      campo ausente (opcional) ou obrigatório faltante."""
    clean: Dict[str, Any] = {}
    for k, v in op.items():
        if v is None and k != "operation":
            continue
        clean[k] = v
    for k in list(clean):
        if k == "operation":
            continue
        t = spec_req.get(k) or spec_opt.get(k)
        if t == _VEC and isinstance(clean[k], dict) and any(
                clean[k].get(c) is None for c in ("x", "y", "z")):
            del clean[k]
    return clean


def validate_payload(data: Any) -> Tuple[List[str], List[Dict[str, Any]],
                                         List[Dict[str, Any]]]:
    """Valida a resposta contra o contrato. Retorna (erros, selects, ops).

    - resposta strict é SANITIZADA na borda (`_sanitize_strict_nulls`) antes
      de qualquer handler/dry-run — o motor nunca vê `None`;
    - `op` e `type` são REJEITADOS (o canônico é `operation`);
    - `__select` é separado para a UI (tratado em ai_plan);
    - obrigatórios ausentes e campos desconhecidos geram erro claro."""
    errors: List[str] = []
    selects: List[Dict[str, Any]] = []
    clean: List[Dict[str, Any]] = []
    if not isinstance(data, dict):
        return ["resposta não é um objeto JSON"], selects, clean
    if data.get("explain") is not None and not isinstance(data.get("explain"), str):
        errors.append("'explain' deve ser string")
    ops = data.get("ops", None)
    if ops is None:
        errors.append("'ops' ausente (use [] para pergunta)")
        ops = []
    if not isinstance(ops, list):
        return ["campo 'ops' não é uma lista"], selects, clean
    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            errors.append(f"ops[{i}]: não é um objeto")
            continue
        if "op" in op:
            errors.append(f"ops[{i}]: campo 'op' não existe — use 'operation'")
            continue
        if "type" in op and "operation" not in op:
            errors.append(f"ops[{i}]: campo 'type' não faz parte do contrato — use 'operation'")
            continue
        name = str(op.get("operation") or "").strip()
        if not name:
            errors.append(f"ops[{i}]: sem 'operation'")
            continue
        if name not in OPS:
            errors.append(f"ops[{i}]: operation desconhecida '{name}'")
            continue
        spec_req, spec_opt = OPS[name]
        op = _sanitize_strict_nulls(op, spec_req, spec_opt)
        bad = False
        if name == "add_box":
            has_center = all(op.get(k) is not None
                             for k in ("center", "width", "depth", "height"))
            has_corners = op.get("corner1") is not None and op.get("corner2") is not None
            if not (has_center or has_corners):
                errors.append(f"ops[{i}]: add_box exige center+width/depth/height OU corner1+corner2")
                bad = True
        if name == "add_diagonal":
            if not ((op.get("start") is not None and op.get("end") is not None)
                    or (op.get("from_element") and op.get("to_element"))):
                errors.append(f"ops[{i}]: add_diagonal exige start+end OU from_element+to_element")
                bad = True
        for fname in spec_req:
            if op.get(fname) in (None, ""):
                errors.append(f"ops[{i}] ({name}): campo obrigatório ausente '{fname}'")
                bad = True
        unknown = [k for k in op.keys()
                   if k != "operation" and k not in spec_req and k not in spec_opt]
        if unknown:
            errors.append(f"ops[{i}] ({name}): campos desconhecidos {unknown[:4]}")
            bad = True
        if bad:
            continue
        if name == _SELECT:
            selects.append(op)
        else:
            clean.append(op)
    return errors, selects, clean


_ACTION_RE = re.compile(
    r"\b(mova|mover|adicione|adicionar|duplique|duplicar|exclua|excluir|"
    r"gire|girar|redimensione|troque|mude|aumente|diminua|reme|renomeie)\b",
    re.IGNORECASE)
_TARGET_RE = re.compile(
    r"\b(esse|esta|isso|o selecionado|a selecionada|selecionad\w+)\b", re.IGNORECASE)
_NOUN_RE = re.compile(
    r"\b(poste|barra|chapa|painel|viga|travessa|diagonal|gabinete)\b", re.IGNORECASE)


def mutation_required(intent: Optional[Dict[str, Any]], text: str) -> bool:
    """ops:[] é FALHA quando NEW/GLOBAL_RESIZE/LOCAL_EDIT estão suficientemente
    definidos; pergunta/ambiguidade genuína é resposta válida."""
    it = (intent or {}).get("intent")
    if it in ("new", "global_resize"):
        return True
    if it == "local_edit":
        t = text or ""
        has_action = bool(_ACTION_RE.search(t))
        has_target = bool(_TARGET_RE.search(t)) or (
            (intent or {}).get("context", {}).get("elements", 0) > 1
            and bool(_NOUN_RE.search(t)))
        return bool(has_action and has_target)
    return False


def evaluate_cad_response(data: Any, model: Any,
                          intent: Optional[Dict[str, Any]],
                          text: str = "") -> Dict[str, Any]:
    """Valida contrato + normaliza + dry_run_diff em CÓPIA do modelo.

    Retorna resultado semântico estruturado SEM aplicar nada:
    {ok, question, retry, reason, errors, ops(normalizadas), selects, diff,
     explain}. `ok=True` garante diff efetivo (ou pergunta válida)."""
    from core.ai_ops import normalize_op, dry_run_diff  # motor real

    errors, selects, clean = validate_payload(data)
    explain = str((data or {}).get("explain") or "").strip() \
        if isinstance(data, dict) else ""
    norm: List[Dict[str, Any]] = []
    for op in clean:
        try:
            norm.append(normalize_op(op))
        except Exception as e:  # OperationError e afins
            errors.append(f"normalização falhou: {e}")
    diff: Dict[str, Any] = {"counts": {"total": 0}, "errors": [],
                            "operations": norm}
    if norm and not errors:
        diff = dry_run_diff(model, norm)
        errors.extend(f"dry-run: {e}"
                      for e in diff.get("errors", [])[:3])

    must_mutate = mutation_required(intent, text)
    total = diff.get("counts", {}).get("total", 0)
    is_question = (not clean and not selects and "?" in explain
                   and not must_mutate)
    reason = ""
    retry = False
    if errors:
        reason = "; ".join(errors[:2])
        retry = True
    elif must_mutate and total == 0:
        reason = "sem diff: as operações não alteram o modelo"
        retry = True
    elif must_mutate and not clean and not selects:
        reason = "ops vazia em pedido de desenho definido"
        retry = True
    return {"ok": not retry, "question": is_question and not retry,
            "retry": retry, "reason": reason, "errors": errors[:4],
            "ops": norm, "selects": selects, "diff": diff, "explain": explain}


def retry_user_message(base_user: str, result: Dict[str, Any]) -> str:
    """Bloco curto de correção para o ÚNICO retry: conserva a mensagem
    original e anexa tipo do erro + até 2 operations problemáticas."""
    import json as _json
    reason = result.get("reason") or ""
    kind = ("ops vazia" if "ops vazia" in reason
            else "operation inválida" if any("desconhecida" in e or "campo" in e
                                             for e in result.get("errors", []))
            else "dry-run inválido/sem diff")
    sample = ""
    ops = (result.get("diff") or {}).get("operations") or []
    if ops:
        sample = " Operations problemáticas (exemplos): " + "; ".join(
            _json.dumps(o, ensure_ascii=False)[:160] for o in ops[:2])
    return (base_user
            + f"\n\n[CORREÇÃO — 1 retry] Sua resposta anterior foi rejeitada na "
              f"validação semântica ({kind}).{sample}\n"
              'Responda NOVAMENTE somente {"explain":"...","ops":[...]} com '
              "operações EFETIVAS (use `operation` e campos documentados; para "
              "projeto novo comece por __blank; ops=[] só para pergunta real). "
              "Não repita a resposta anterior.")


def run_cad_plan(call: Callable[[List[Dict[str, str]]], str],
                 extract_fn: Callable[[str], Dict[str, Any]],
                 model: Any, intent: Optional[Dict[str, Any]], text: str,
                 sys_p: str, user_base: str,
                 attempts: int = 2) -> Dict[str, Any]:
    """Orquestração comum (usada por ai_plan e ai_command): chamada LLM →
    extração → validação semântica → dry-run; NO MÁXIMO 1 retry guiado
    (2 chamadas totais). `call(messages)` fecha por cima de
    chat_completion/cfg/response_schema. O modelo original NUNCA é mutado:
    o dry-run roda em cópia e o apply continua sendo autoridade de
    /api/ops/apply (apply_batch)."""
    import json as _json
    messages = [{"role": "system", "content": sys_p},
                {"role": "user", "content": user_base}]
    last: Optional[Dict[str, Any]] = None
    attempts = max(1, min(int(attempts), 2))
    for attempt in range(attempts):
        raw = call(messages)
        data = extract_fn(raw)
        res = evaluate_cad_response(data, model, intent, text)
        res["explain"] = str((data or {}).get("explain")
                             or res.get("explain") or "").strip()
        if res["ok"]:
            res["attempts"] = attempt + 1
            return res
        last = res
        if attempt == 0:
            messages = [{"role": "system", "content": sys_p},
                        {"role": "user", "content": user_base},
                        {"role": "assistant", "content":
                            _json.dumps((data if isinstance(data, dict) else {}),
                                        ensure_ascii=False)[:800]},
                        {"role": "user",
                         "content": retry_user_message(user_base, res)}]
    out = dict(last or {})
    out["ok"] = False
    out["attempts"] = attempts
    out["reason"] = out.get("reason") or "a IA não produziu operações efetivas"
    return out
