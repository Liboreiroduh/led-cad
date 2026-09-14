"""IA de comandos: interpreta linguagem natural (PT-BR) e converte em
OPERAÇÕES estruturadas. A IA NUNCA desenha geometria — quem executa é o
core Python (core/operations.py).

DOIS motores:
1. Parser determinístico (regras/regex) — sem dependências externas;
   funciona offline e é o fallback automático.
2. IA REAL (LLM) via services/ai_llm.py — z.ai GLM gratuito (padrão),
   Gemini, OpenAI ou qualquer API compatível com OpenAI. O prompt com o
   modelo JSON/operacoes vive em services/ai_prompts.py.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from core.operations import OperationError, ProjectStore, apply_operation
from services.preset_service import list_presets, load_preset

NUM = r"(-?\d+(?:[.,]\d+)?)"
DEFAULT_V0_MS_AI = 35.0  # V₀ padrão p/ consultas de vento pela IA

DIRECTIONS = {
    "direita": ("x", +1), "esquerda": ("x", -1),
    "cima": ("z", +1), "para cima": ("z", +1), "acima": ("z", +1), "sobe": ("z", +1),
    "baixo": ("z", -1), "para baixo": ("z", -1), "abaixo": ("z", -1), "desce": ("z", -1),
    "frente": ("y", +1), "para frente": ("y", +1),
    "tras": ("y", -1), "trás": ("y", -1), "para trás": ("y", -1), "para tras": ("y", -1),
}


def _num(text: str, pattern: str) -> Optional[float]:
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def _find_element_id(model, text: str) -> Optional[str]:
    """Procura IDs existentes citados no texto (case-insensitive)."""
    up = text.upper().replace(" ", "")
    ids = sorted((e.id for e in model.elements), key=len, reverse=True)
    for eid in ids:
        if eid.replace("-", "") in up.replace("-", ""):
            return eid
    # apelidos
    if re.search(r"poste central|o poste", text, re.IGNORECASE):
        posts = [e.id for e in model.elements if e.role == "post"]
        return posts[0] if posts else None
    return None


ROLE_KEYWORDS = {
    "post": ("postes?", "pilares?", "colunas?"),
    "vertical": ("verticais?", "montantes?"),
    "horizontal": ("horizontais?", "travessas?"),
    "diagonal": ("diagonais?", "treli[cç]a"),
    "plate": ("chapas?", "placas?", "bases?"),
    "bolt": ("chumbadores?", "parafusos?"),
}


def _find_ids_multi(model, text: str) -> List[str]:
    """Todos os IDs citados no texto (para comandos em lote: 'exclua V01 e V02')."""
    up = text.upper().replace(" ", "")
    clean = up.replace("-", "")
    found: List[str] = []
    for el in sorted(model.elements, key=lambda e: len(e.id), reverse=True):
        if el.id.replace("-", "") in clean and el.id not in found:
            found.append(el.id)
    return found


def _ids_by_role(model, text: str) -> Optional[List[str]]:
    """Resolve 'todos os postes / verticais / chapas…' para lista de IDs."""
    low = text.lower()
    for role, kws in ROLE_KEYWORDS.items():
        for kw in kws:
            if re.search(rf"\b{kw}\b", low):
                ids = [e.id for e in model.elements if e.role == role]
                return ids or None
    return None


def parse_command(model, text: str) -> List[Dict[str, Any]]:
    """Converte texto em lista de operações (sem aplicar)."""
    t = text.strip()
    low = t.lower()
    ops: List[Dict[str, Any]] = []

    # ---- trocar/regerar preset ----
    if re.search(r"\bpreset\b|novo projeto|trocar para \d+ postes?", low):
        # salvar a configuração atual como preset pessoal
        if re.search(r"salv|cri[ae]|nov\w+ preset|guarde", low):
            mname = re.search(r"preset\w*\s+(?:como\s+)?(.+)$", t, re.IGNORECASE)
            name = (mname.group(1) if mname else "").strip(" \"'“”‘’")
            if not name:
                raise OperationError("Informe o nome: 'salve preset Painel 6x3 Vira-Lata'.")
            return [{"operation": "__save_preset", "name": name}]
        m2 = re.search(r"(\d+)\s*postes?", low)
        if m2:
            n = int(m2.group(1))
            for p in list_presets():
                data = load_preset(p["id"]) or {}
                if data.get("defaults", {}).get("installation", {}).get("posts") == n:
                    ops.append({"operation": "__preset", "preset_id": p["id"]})
                    return ops
            # não há preset pronto com N postes: regenera o atual com N postes
            ops.append({"operation": "__regen", "overrides": {"installation": {"posts": n}}})
            return ops
        # palavra-chave por tipo de instalação (parede, suspenso, rental…)
        kind_keywords = {
            "wall": ("parede", "fachada", "muro", "pared"),
            "suspended": ("suspenso", "teto", "galp", "pendente", "pendurado"),
            "rental": ("rental", "palco", "evento", "torre", "stage"),
            "post": ("outdoor", "dooh", "pilar", "poste"),
        }
        # 1º: nome próprio de preset do usuário ("preset Painel 6x3")
        stop = {"preset", "do", "da", "o", "a", "para", "com"}
        words = [w for w in re.findall(r"[\w\-]+", low) if w not in stop and not w.isdigit()]
        best, best_hits = None, 0
        for p in list_presets():
            pname = p["name"].lower()
            hits = sum(1 for w in words if len(w) > 2 and w in pname)
            if hits > best_hits:
                best, best_hits = p["id"], hits
        if best:
            ops.append({"operation": "__preset", "preset_id": best})
            return ops
        for p in list_presets():
            data = load_preset(p["id"]) or {}
            itype = data.get("defaults", {}).get("installation", {}).get("type", "post")
            for kw in kind_keywords.get(itype, ()):
                if kw in low:
                    ops.append({"operation": "__preset", "preset_id": p["id"]})
                    return ops
        raise OperationError(
            "Presets disponíveis: "
            + ", ".join(f"{p['id']} ({p['name']})" for p in list_presets())
            + ". Ex.: 'preset 2 postes', 'preset parede', 'preset suspenso', 'preset rental', "
              "'salve preset Meu Painel'."
        )

    # ---- desfazer ----
    if re.search(r"\b(desfa|undo|ctrl z)\w*", low):
        return [{"operation": "__undo"}]

    # ---- histórico ----
    if re.search(r"hist[óo]ric|o que (voc[êe]|vc) (fez|fez)|\blog\b", low):
        return [{"operation": "__history"}]

    # ---- custo / orçamento ----
    if re.search(r"custo|or[çc]amento|quanto (custa|fica)|pre[çc]o|valor", low):
        return [{"operation": "__cost"}]

    # ---- perguntas abertas → IA real ----
    # "qual o melhor perfil…?", "como está o projeto?", "devo usar tubo…?" —
    # são PERGUNTAS (o usuário quer conversa/opinião), não estimativas
    # pontuais: o copiloto responde com os dados do projeto atual.
    if re.search(
        r"^\s*(qual|quais|como|por que|porque|por qu[êe]|quando|onde|"
        r"devo|posso|pode|existe|h[áa]|tem)\b", low) \
        and not re.search(r"custo|or[çc]amento|pre[çc]o|valor|hist[óo]ric", low):
        raise OperationError("Pergunta aberta → IA real")

    # ---- vento ----
    if re.search(r"\bvento\w*|carga (de )?vento|for[çc]a do vento", low):
        direction = "frontal"
        if re.search(r"lateral|de lado|perfil", low):
            direction = "lateral"
        elif re.search(r"traseir|por tr[áa]s|de tr[áa]s|fundo", low):
            direction = "traseira"
        obs = 0.0
        if re.search(r"obstru|sombra|abrig|vizinh", low):
            if re.search(r"sem (obstru|abrigo|sombra)|nenhum", low):
                obs = 0.0
            elif re.search(r"forte|alto|muito", low):
                obs = 0.4
            elif re.search(r"parcial|m[ée]dio", low):
                obs = 0.2
            else:
                m_pct = re.search(r"(\d+[.,]?\d*)\s*%", low)
                if m_pct:
                    obs = min(0.6, max(0.0, float(m_pct.group(1).replace(",", ".")) / 100.0))
                else:
                    obs = 0.2
        return [{"operation": "__wind", "dir": direction, "obs": obs}]

    # ---- plano de corte ----
    if re.search(r"plano de corte|cut ?list|lista de corte|corte das barras", low):
        m_len = re.search(r"(\d+)\s*m\b", low)
        bar_len = float(m_len.group(1)) * 1000.0 if m_len else None
        return [{"operation": "__cutlist", "bar_len": bar_len}]

    # ---- seleção (frontend aplica no lote) ----
    if re.search(r"selecion|marcar (todos|tudo)|limpe (a )?sele|desmarc|desselec", low):
        if re.search(r"limpe|desmarc|desselec", low):
            return [{"operation": "__select", "ids": []}]
        if re.search(r"\b(tudo|todos)\b", low) and not re.search(r"todos? (os|as) \w+", low):
            ids = [e.id for e in model.elements if e.type != "panel"]
            return [{"operation": "__select", "ids": ids}]
        ids = _ids_by_role(model, t)
        if not ids:
            raise OperationError(
                "Não entendi o que selecionar. Ex.: 'selecione todos os postes', "
                "'selecione tudo', 'limpe a seleção'.")
        return [{"operation": "__select", "ids": ids}]

    # ---- TUDO MAIS → IA REAL (desenho livre) ----
    # Direção do produto (pedido do usuário): a barra de texto é a IA —
    # "ou eu desenho livremente (Barra A→B), ou escolho um painel salvo
    # (preset), ou peço à IA para criar entendendo a ferramenta". O parser
    # rápido NÃO cria nem edita estrutura — só resolve as UTILIDADES acima
    # (desfaça, histórico, custo, vento, plano de corte, preset, seleção).
    # Qualquer outro texto é pedido de desenho/pergunta → copiloto de IA
    # (services/ai_prompts.py), que devolve ops validadas pelo motor.
    raise OperationError(
        "Desenho é com a IA real ✨ — escreva livre: 'crie um painel 2x1 com "
        "gabinetes de 0,96x0,96, 1 poste central e passarela', 'desenhe um "
        "círculo de 2 m suspenso a 5 m', 'construa um cubo de 1 m', "
        "'monte uma casa 4x3 m'…")


HELP_TEXT = (
    "Escreva LIVRE — a IA desenha com a ferramenta (cria do zero, sem preset):\n"
    "• crie um painel outdoor 2x1 com gabinetes de 0,96x0,96, 1 poste central e passarela atrás\n"
    "• desenhe um painel circular de 2 m de diâmetro suspenso a 5 m do solo\n"
    "• construa um cubo de 1 m com METALON 40x40x2\n"
    "• monte uma casa 4x3 m (esboço) com telhado de duas águas\n"
    "• crie um pórtico com 2 postes de 3 m e travessa no topo\n"
    "• adicione mais um poste (acréscimos preservam o que já existe)\n"
    "Utilidades diretas (sem IA): desfaça · histórico · quanto custa · vento? · "
    "plano de corte · preset 2 postes · preset parede · salve preset Nome\n"
    "Toda criação pode ser desfeita com Ctrl+Z."
)


def execute_command(store: ProjectStore, text: str) -> Dict[str, Any]:
    """Modo rápido (parser determinístico): interpreta + aplica."""
    model = store.ensure_loaded()
    ops = parse_command(model, text)
    return execute_ops(store, ops)


def execute_ops(store: ProjectStore, ops: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aplica uma lista de operações estruturadas (do parser rápido OU da IA
    real via LLM — services/ai_llm.py). Retorna log legível p/ a UI."""
    from core.bom import build_bom
    from core.cutlist import build_cutlist, normalize_bar_len
    from core.wind import estimate_wind, normalize_direction, normalize_obstruction
    from services.pricing_service import get_pricing

    if not isinstance(ops, list):
        raise OperationError("'ops' deve ser uma lista de operações.")
    if len(ops) > 120:
        raise OperationError("Máximo de 120 operações por comando.")

    applied: List[Dict[str, Any]] = []
    messages: List[str] = []
    selection: List[str] = []

    for op in ops:
        model = store.ensure_loaded()  # ops anteriores podem ter trocado o modelo
        if not isinstance(op, dict) or not str(op.get("operation", "")).strip():
            raise OperationError(f"Operação malformada: {json.dumps(op, ensure_ascii=False)[:120]}")
        kind = op.get("operation", "")
        if kind == "__blank":
            store.new_blank()
            messages.append("Projeto EM BRANCO criado — monte a estrutura com as "
                            "ferramentas livres ou pedindo à IA.")
            applied.append(op)
        elif kind == "__preset":
            pid = op["preset_id"]
            store.new_from_preset(pid)
            preset = load_preset(pid)
            messages.append(f"Preset carregado: {preset['name']}.")
            applied.append(op)
        elif kind == "__undo":
            store.undo()
            messages.append("Última operação desfeita.")
            applied.append(op)
        elif kind == "__history":
            tail = store.history_tail(8)
            if tail:
                lines = [f"{h['time']} — {h['detail'] or h['action']}" for h in tail]
                messages.append("Histórico recente: " + " | ".join(lines))
            else:
                messages.append("Histórico vazio (nenhuma ação registrada ainda).")
            applied.append(op)
        elif kind == "__cost":
            bom = build_bom(model)
            p = get_pricing()
            messages.append(
                f"Custo estimado de material: R$ {bom['total_cost_brl']:,.2f} "
                f"({bom['total_mass_kg']:,.2f} kg · perfil R$ {p['steel_profile_brl_kg']:.2f}/kg "
                f"+ pintura R$ {p['paint_brl_kg']:.2f}/kg + perda {int((p['waste_factor'] - 1) * 100)}%). "
                f"Referência para orçamento — não é cotação formal.")
            applied.append(op)
        elif kind == "__wind":
            w = estimate_wind(model, DEFAULT_V0_MS_AI, normalize_direction(op.get("dir")),
                              normalize_obstruction(op.get("obs", 0.0)))
            dir_txt = w.get("direction_label", "frontal")
            obs_txt = (f", abrigo {int(round(w['obstruction'] * 100))}%"
                       if w.get("obstruction", 0) > 0 else "")
            messages.append(
                f"Vento {dir_txt} (V₀={w['v0_ms']:.0f} m/s, q={w['q_kn_m2']:.2f} kN/m²{obs_txt}): "
                f"F ≈ {w['force_total_kn']:.1f} kN — painel {w['area_panel_m2']:.1f} m² "
                f"({w['force_panel_kn']:.1f} kN) + treliça {w['area_frame_m2']:.1f} m² "
                f"({w['force_frame_kn']:.1f} kN). {w.get('effect', '')}")
            applied.append({**op, "wind": w})
        elif kind == "__cutlist":
            bl = normalize_bar_len(op.get("bar_len"))
            cl = build_cutlist(model, bl)
            lines = [f"{g['label']}: {g['piece_count']} pçs / {g['total_m']:.1f} m "
                     f"→ {g['bars']} barras {int(bl/1000)} m"
                     for g in cl["groups"]]
            messages.append("Plano de corte (barras de "
                            f"{int(cl['bar_len_mm']/1000)} m): " + " | ".join(lines)
                            + f" · total {cl['total_bars']} barras "
                              "(detalhe na aba PLANO DE CORTE dos Materiais).")
            applied.append(op)
        elif kind == "__save_preset":
            from services.preset_service import save_custom_preset
            out = save_custom_preset(op["name"], model.model_dump(), store.preset_id or "")
            store.log("save", f"Preset personalizado '{out['name']}' criado "
                              f"({out['elements']} elementos).")
            messages.append(f"Preset personalizado '{out['name']}' salvo "
                            f"({out['elements']} elementos) — aparece na lista de presets.")
            applied.append({**op, "preset": out})
        elif kind == "__select":
            selection = op.get("ids", [])
            if selection:
                messages.append(f"{len(selection)} elemento(s) selecionados "
                                "(aplicados na multi-seleção).")
            else:
                messages.append("Seleção limpa.")
            applied.append(op)
        elif kind == "__regen":
            # preset_id explícito na op (ensinado ao LLM): permite regenerar
            # a partir de uma FAMÍLIA base mesmo com o projeto EM BRANCO —
            # ex. {"operation":"__regen","preset_id":"DOOH_4X2_1_POSTE",
            #      "overrides":{"panel":{"width":1920,"height":960}}}
            pid = str(op.get("preset_id") or "").strip() \
                or store.preset_id or "REF_4000X2000"
            if load_preset(pid) is None:
                raise OperationError(
                    f"Preset '{pid}' não encontrado. Disponíveis: "
                    + ", ".join(p["id"] for p in list_presets()) + ".")
            store.new_from_preset(pid, op.get("overrides"),
                                  keep_undo=True, undo_action="regen")
            messages.append(f"Projeto regenerado a partir de {pid} com novos "
                            "parâmetros (desfazível — edições manuais foram "
                            "substituídas).")
            applied.append(op)
        else:
            res = apply_operation(store, op)
            applied.append(res)
            el = res.get("element_id", "")
            if kind == "move_element":
                d = [res.get("delta", [0, 0, 0])[i] for i in range(3)]
                parts = [f"{int(v):+d}mm {a}" for a, v in zip(("X", "Y", "Z"), d) if v]
                messages.append(f"{el} movido ({', '.join(parts) or '0'}).")
            elif kind == "add_post":
                messages.append(f"Poste {el} criado em X={op.get('x', 0):.0f}.")
            elif kind == "delete_element":
                messages.append(f"{el} excluído.")
            elif kind == "duplicate_element":
                messages.append(f"{el} duplicado como {res.get('element_id')}.")
            elif kind == "update_profile":
                messages.append(f"Perfil de {el} alterado para {res.get('profile')}.")
            elif kind == "add_beam":
                messages.append(f"Barra {el} criada ({res.get('length')} mm).")
            elif kind == "multi_delete":
                messages.append(f"{res.get('count', 0)} elemento(s) excluídos em lote ({', '.join(res.get('ids', [])[:5])}).")
            elif kind == "multi_move":
                d = res.get("delta", [0, 0, 0])
                parts = [f"{int(v):+d}mm {a}" for a, v in zip(("X", "Y", "Z"), d) if v]
                messages.append(f"{res.get('count', 0)} elemento(s) movidos ({', '.join(parts) or '0'}).")
            elif kind == "multi_duplicate":
                messages.append(f"{res.get('count', 0)} elemento(s) duplicados ({', '.join(res.get('ids', [])[:5])}).")
            elif kind == "multi_profile":
                messages.append(f"Perfil de {res.get('count', 0)} elemento(s) → {res.get('profile')}.")
            elif kind == "set_panel":
                messages.append(f"Painel de referência: {res.get('changed', 'atualizado')}.")
            elif kind == "add_circle":
                messages.append(f"Círculo Ø{res.get('radius', 0):.0f} mm criado "
                                f"({res.get('segments', 0)} segmentos, plano {res.get('plane', '')}).")
            elif kind == "add_box":
                messages.append(f"Gaiola/caixa criada — {res.get('count', 0)} arestas "
                                f"({', '.join(res.get('ids', [])[:4])}…).")
            elif kind == "add_grid":
                messages.append(f"Grelha {res.get('cols', 1)}×{res.get('rows', 1)} criada — "
                                f"{res.get('count', 0)} barras.")
            else:
                messages.append(f"{kind} aplicado em {el}.") if el else messages.append(f"{kind} aplicado.")

    return {"ok": True, "message": " | ".join(messages) or "Feito.",
            "applied": applied, "help": HELP_TEXT, "selection": selection}
