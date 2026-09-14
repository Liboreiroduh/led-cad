"""Intenção canônica de IA — Formulário rápido + Copiloto (LED STRUCTURE CAD).

Uma única representação interna do pedido, usada pelos DOIS caminhos para
montar contexto e prompt (sem banco, sem dependências novas):

    intent = build_intent(text=…, model=…, form=…)
    intent = {
      "intent":   "new" | "local_edit" | "global_resize",
      "panel":    {"width","height","depth","cabinet":{w,h,depth,cols,rows}},
      "install":  {"ground_clearance","posts"},
      "features": {"cage": bool|None, "walkway": bool|None, "guardrail": bool|None},
      "context":  {…estrutura existente…},
      "source":   "form" | "copiloto",
      "text":     pedido original,
    }

Contratos (mandatórios no prompt): cage/walkway/guardrail explícitos inclusive
quando falsos; guarda-corpo nunca existe sem passarela; painel elevado tem
ground_clearance = topo dos postes = base da gaiola; local_edit preserva o que
não foi citado; global_resize substitui UMA estrutura (nunca sobrepõe duas).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

_BOOL_KEYS = {"true": True, "false": False, "sim": True, "não": False,
              "nao": False, "1": True, "0": False}


def _f(v: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _i(v: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ contexto
def model_context(model: Any) -> Dict[str, Any]:
    """Leitura estrutural do modelo atual: painel, módulo de gabinete (deduzido
    das grades GABINETES-FRONT), gaiola, postes, passarela e guarda-corpo."""
    panel = getattr(model, "panel", None)
    inst = getattr(model, "installation", None)
    ctx: Dict[str, Any] = {
        "elements": len(model.elements),
        "panel": {"width": panel.width, "height": panel.height,
                  "depth": panel.depth,
                  "ground_clearance": inst.ground_clearance if inst else 0},
        "cabinet": None, "cage": False, "posts": [], "walkway": False,
        "guardrail": False,
    }
    xs: List[float] = []
    gx: set = set()
    gz: set = set()
    for el in model.elements:
        g = (getattr(el, "group", "") or "").upper()
        if "GAIOLA" in g:
            ctx["cage"] = True
        if "PASSARELA" in g:
            ctx["walkway"] = True
        if "GUARDA" in g:
            ctx["guardrail"] = True
        if "POSTE" in g or getattr(el, "role", "") == "post":
            if getattr(el, "start", None):
                xs.append(round(el.start.x, 1))
        if g.startswith("GABINETES-FRONT") and getattr(el, "start", None) \
                and getattr(el, "end", None):
            dx = abs(el.end.x - el.start.x)
            dz = abs(el.end.z - el.start.z)
            if dz > dx:
                gx.add(round(el.start.x, 1))
            elif dx > dz:
                gz.add(round(el.start.z, 1))
    if len(gx) >= 2:
        cols = len(gx) - 1
        cab: Dict[str, Any] = {"cols": cols,
                               "module_w": round((max(gx) - min(gx)) / cols, 1),
                               "rows": None, "module_h": None}
        if len(gz) >= 2:
            rows = len(gz) - 1
            cab["rows"] = rows
            cab["module_h"] = round((max(gz) - min(gz)) / rows, 1)
        ctx["cabinet"] = cab
    ctx["posts"] = sorted(set(xs))
    return ctx


# ------------------------------------------------------------- formulário
def from_form(form: Dict[str, Any], model: Any, text: str = "") -> Dict[str, Any]:
    """Intenção a partir do Formulário rápido (valores estruturados; os três
    booleanos vêm SEMPRE explícitos, inclusive falsos)."""
    form = form or {}
    gw = _f(form.get("gw"), 960.0)
    gh = _f(form.get("gh"), 960.0)
    gd = _f(form.get("gd"), 100.0)
    cols = max(1, _i(form.get("cols"), 1))
    rows = max(1, _i(form.get("rows"), 1))
    pd = max(0.0, _f(form.get("pd"), 0.0) or 0.0)
    posts = max(0, _i(form.get("posts"), 0))
    cage_d = _f(form.get("cage_d"), 650.0)

    def _bool(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        return _BOOL_KEYS.get(str(v).strip().lower(), False)

    cage = _bool(form.get("cage"))
    walk = _bool(form.get("walk"))
    rail = _bool(form.get("rail")) and walk  # guarda-corpo nunca sem passarela

    pw, ph = gw * cols, gh * rows
    ctx = model_context(model)
    intent = "new"
    if ctx["elements"] > 1:
        cur = ctx["panel"]
        if abs(cur["width"] - pw) > 1 or abs(cur["height"] - ph) > 1:
            intent = "global_resize"
    return {
        "intent": intent,
        "panel": {"width": pw, "height": ph, "depth": cage_d,
                  "cabinet": {"w": gw, "h": gh, "depth": gd,
                              "cols": cols, "rows": rows}},
        "install": {"ground_clearance": pd, "posts": posts},
        "features": {"cage": cage, "walkway": walk, "guardrail": rail},
        "context": ctx,
        "source": "form",
        "text": text,
    }


# --------------------------------------------------------------- texto livre
_WXH = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:m\b)?\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(?:m\b)?")
_RESIZE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(?:m\b)?\s*"
    r"(?:para|pra|virar|vire|em|mudar para|transformar em|"
    r"redimensionar para|redimensione para|aumentar para|aumente para)\s*"
    r"(\d+(?:[.,]?\d*)\s*[x×]\s*\d+(?:[.,]?\d*))", re.IGNORECASE)
_CLEAR = re.compile(
    r"(?:pé[- ]?direito|altura livre|base do painel)\s*(?:de\s*|em\s*)?"
    r"(\d+(?:[.,]\d+)?)\s*(m|mm)?|(?:a|a partir de)\s+(\d+(?:[.,]\d+)?)\s*"
    r"(m|mm)?\s*(?:do solo|do chão|do chao|do piso)", re.IGNORECASE)
_NEW_VERB = re.compile(
    r"\b(crie|criar|cria|monte|montar|construa|construir|desenhe|gere|gerar|"
    r"fa[çc]a|do zero|do in[íi]cio|novo projeto|projeto novo|nova estrutura)\b",
    re.IGNORECASE)
_NEW_RESET = re.compile(r"novo|do zero|do in[íi]cio|projeto novo|nova estrutura",
                        re.IGNORECASE)


def _to_mm(v: float) -> float:
    """Em contexto de painel, valores ≤ 50 são metros; acima disso já é mm."""
    return v * 1000.0 if v <= 50.0 else v


def derive_from_text(text: str, model: Any) -> Dict[str, Any]:
    """Deriva a MESMA intenção/contexto de texto livre do Copiloto."""
    ctx = model_context(model)
    has_struct = ctx["elements"] > 1
    t = (text or "").lower()

    intent = "local_edit"
    target_wh: Optional[Dict[str, float]] = None
    m = _RESIZE.search(text or "")
    if m:
        intent = "global_resize"
        target_wh = {"w": _to_mm(_f(m.group(1), 0.0) or 0.0),
                     "h": _to_mm(_f(m.group(2), 0.0) or 0.0)}
    elif _NEW_VERB.search(text or "") and (not has_struct or _NEW_RESET.search(t)):
        intent = "new"
    elif not has_struct:
        intent = "new"

    panel = None
    wm = _WXH.search(text or "")
    if wm:
        w = _to_mm(_f(wm.group(1), 0.0) or 0.0)
        h = _to_mm(_f(wm.group(2), 0.0) or 0.0)
        if intent == "global_resize" and target_wh:
            w, h = target_wh["w"], target_wh["h"]
        panel = {"width": round(w), "height": round(h)}

    gc = None
    cm = _CLEAR.search(text or "")
    if cm:
        raw = cm.group(1) or cm.group(3)
        unit = cm.group(2) or cm.group(4)
        val = _f(raw, 0.0) or 0.0
        gc = val * 1000.0 if (unit or "").lower() == "m" else _to_mm(val)

    def _has(*words: str) -> Optional[bool]:
        return True if any(w in t for w in words) else None

    cage = _has("gaiola", "gabinet")
    walk = _has("passarela")
    rail = _has("guarda", "corrim")
    if rail:
        walk = True  # guarda-corpo nunca existe sem passarela

    out: Dict[str, Any] = {"intent": intent, "panel": panel,
                           "install": {"ground_clearance": gc, "posts": None},
                           "features": {"cage": cage, "walkway": walk,
                                        "guardrail": rail},
                           "context": ctx, "source": "copiloto",
                           "text": text}
    if intent == "global_resize" and not out["panel"]:
        out["panel"] = {"width": None, "height": None}
    return out


def build_intent(text: str, model: Any,
                 form: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """PONTO ÚNICO compartilhado por Formulário e Copiloto: o formulário
    estruturado tem prioridade; texto livre deriva a mesma intenção."""
    if form:
        return from_form(form, model, text or "")
    return derive_from_text(text or "", model)


# ------------------------------------------------------------------- prompt
def _fmt_pair(a: Any, b: Any) -> str:
    ok = a is not None and b is not None
    return f"{a}×{b}" if ok else "—"


def _b(v: Optional[bool]) -> str:
    if v is None:
        return "não citado"
    return "TRUE" if v else "FALSE"


def intent_block(intent: Optional[Dict[str, Any]]) -> str:
    """Bloco de texto inserido no prompt de sistema (IGUAL para os dois
    caminhos): intenção, estrutura atual, alvo e contratos mandatórios."""
    if not intent:
        return ("## INTENÇÃO CANÔNICA\n"
                "Não estruturada — trate como EDIÇÃO LOCAL do projeto atual.")
    ctx = intent.get("context") or {}
    p = ctx.get("panel") or {}
    cab = ctx.get("cabinet") or {}
    posts = ctx.get("posts") or []
    lines = ["## INTENÇÃO CANÔNICA (mandatória — não reinterprete)",
             f"- intenção: {str(intent['intent']).upper()} "
             f"(fonte: {'formulário estruturado' if intent.get('source') == 'form' else 'texto livre'})",
             f"- estrutura ATUAL: painel {p.get('width')}×{p.get('height')} mm, "
             f"profundidade {p.get('depth')} mm, base {p.get('ground_clearance')} mm; "
             f"módulo de gabinete {_fmt_pair(cab.get('module_w'), cab.get('module_h'))} mm "
             f"em {_fmt_pair(cab.get('cols'), cab.get('rows'))}; "
             f"gaiola: {'sim' if ctx.get('cage') else 'não'}; "
             f"postes: {len(posts)}{(' em X=' + str(posts)) if posts else ''}; "
             f"passarela: {'sim' if ctx.get('walkway') else 'não'}; "
             f"guarda-corpo: {'sim' if ctx.get('guardrail') else 'não'}; "
             f"{ctx.get('elements')} elementos"]
    tp = intent.get("panel")
    if tp and (tp.get("width") or tp.get("height")):
        cab2 = tp.get("cabinet") or {}
        seg = f"- alvo: painel {tp.get('width')}×{tp.get('height')} mm"
        if tp.get("depth"):
            seg += f", profundidade da gaiola {tp.get('depth')} mm"
        if cab2.get("w"):
            seg += (f", gabinetes {cab2.get('w')}×{cab2.get('h')} mm em "
                    f"{cab2.get('cols')}×{cab2.get('rows')}")
        lines.append(seg)
    ti = intent.get("install") or {}
    if ti.get("ground_clearance") is not None or ti.get("posts") is not None:
        lines.append(f"- instalação alvo: base {ti.get('ground_clearance')} mm, "
                     f"{ti.get('posts')} poste(s)")
    f = intent.get("features") or {}
    if any(v is not None for v in f.values()):
        lines.append(
            f"- recursos MANDATÓRIOS: cage={_b(f.get('cage'))}, "
            f"walkway={_b(f.get('walkway'))}, guardrail={_b(f.get('guardrail'))}"
            + ("" if all(v is not None for v in f.values())
               else " — não citados: criação → gaiola+grades SIM, "
                    "passarela/guarda-corpo NÃO; edição → preserve o que existe"))
    lines.append(
        "CONTRATOS:\n"
        "- feature `false` é OBRIGATÓRIO: cage:false → NENHUMA gaiola e NENHUMA\n"
        "  grade de gabinetes; walkway:false → NENHUMA passarela; guardrail:false\n"
        "  → NENHUM guarda-corpo. guardrail:true exige passarela:true.\n"
        "- painel elevado: set_panel.ground_clearance = topo dos postes = base da\n"
        "  gaiola (MESMA cota em mm do solo). O painel é referência visual — não é\n"
        "  barra e não substitui a gaiola.\n"
        "- LOCAL_EDIT: altere somente o citado; preserve todos os demais elementos,\n"
        "  grupos e cotas (nunca __blank).\n"
        "- GLOBAL_RESIZE: substituição de UMA estrutura — infira o módulo atual,\n"
        "  preserve elevação/profundidade e recursos (existentes ou pedidos), comece\n"
        "  com __blank e recrie o conjunto completo; NUNCA sobreponha/ajunte duas\n"
        "  gaiolas.\n"
        "- NEW: comece com __blank e desenhe a estrutura completa coerente com o alvo.")
    return "\n".join(lines)


def intent_json(intent: Optional[Dict[str, Any]]) -> str:
    """JSON compacto da intenção para a mensagem do usuário (feature flags
    explícitos, inclusive falsos)."""
    if not intent:
        return "{}"
    slim = {k: intent.get(k) for k in
            ("intent", "panel", "install", "features", "source")}
    slim["context"] = dict(intent.get("context") or {})
    return json.dumps(slim, ensure_ascii=False)
