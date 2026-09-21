"""Piloto CAD — Z.ai GLM-4.5.

Pacote de conhecimento operacional + roteador de intenção + memória leve por
projeto/revisão. Este módulo NÃO chama provedor: ele prepara contexto,
classifica a rota e guarda o essencial do diálogo. O LLM continua decidindo
parâmetros de texto livre; Python calcula, valida e aplica.

Regras de segurança:
- nunca persiste chave, reasoning ou conteúdo privado;
- memória invalidada quando projeto ou revisão mudam;
- nenhuma rota contorna preview → aplicar → undo.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Importar intent_block de ai_intent (onde está definida)
from services.ai_intent import intent_block
# Importar biblioteca de conhecimento de presets
from services import preset_knowledge as pk

# -------------------------------------------------------- integração presets
def enrich_intent_with_preset(text: str, intent: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Detecta referência a preset no texto e enriquece a intenção com dados do preset.
    Se o usuário menciona um preset (ex: 'REF_4000X2000' ou '4x2 outdoor'),
    recupera o preset, converte para spec e ajusta a intenção canônica.
    """
    preset_id = pk.detect_preset_reference(text)
    if not preset_id:
        return None
    preset = pk.find_preset_by_id(preset_id)
    if not preset:
        return None
    # Converter preset em spec paramétrica
    spec = pk.preset_to_spec(preset)
    # Enriquecer intenção com dados do preset
    enriched = intent or {}
    enriched["preset_id"] = preset_id
    enriched["preset_name"] = preset.get("name", "")
    # Ajustar dimensões do painel baseado no preset
    panel = enriched.get("panel") or {}
    panel["width"] = spec["panel"]["width"]
    panel["height"] = spec["panel"]["height"]
    panel["depth"] = spec["panel"]["depth"]
    panel["cabinet"] = {
        "w": spec["panel"]["cabinet_width"],
        "h": spec["panel"]["cabinet_height"],
        "cols": spec["panel"]["columns"],
        "rows": spec["panel"]["rows"],
    }
    enriched["panel"] = panel
    # Ajustar instalação
    install = enriched.get("install") or {}
    install["posts"] = spec["supports"]["count"]
    install["ground_clearance"] = spec["panel"]["ground_clearance"]
    enriched["install"] = install
    # Ajustar features opcionais
    features = enriched.get("features") or {}
    features["cage"] = spec["cage"]["enabled"]
    features["walkway"] = spec["walkway"]["enabled"]
    features["guardrail"] = spec["guardrail"]["enabled"]
    enriched["features"] = features
    return enriched
# Importar biblioteca de conhecimento de presets
from services import preset_knowledge as pk

# Endpoint oficial Z.ai (OpenAI-compatível) e identificador do modelo.
ZAI_BASE_URL = "https://api.z.ai/api/paas/v4"
ZAI_PILOT_MODEL = "glm-4.5-flash"
ZAI_PILOT_NAME = "Z.ai · GLM-4.5-Flash · Piloto CAD"

MEMORY_FILE = Path(__file__).resolve().parent.parent / "data" / "pilot_memory.json"
KNOWLEDGE_VERSION = 1

QUESTION_WORDS = re.compile(
    r"\b(qual|quais|quanto|quantos|quantas|como|onde|por que|porque|me explique|"
    r"explica|explique|significa|o que é)\b", re.I)
REVIEW_WORDS = re.compile(r"\b(revise|revis[aã]o|confer(e|ir)|confira|pend[eê]ncias?|checar)\b", re.I)
CREATE_WORDS = re.compile(
    r"\b(crie|criar|cria|monte|montar|monta|faça|fazer|novo projeto|comece|"
    r"come[cç]ar|projeto novo|painel \d|esbo[cç]o)\b", re.I)
EDIT_WORDS = re.compile(
    r"\b(suba|sobe|subir|des[cç]a|mova|mover|mude|mudar|troque|trocar|adicione|"
    r"adicionar|apague|apagar|exclua|excluir|duplicar|duplicque|gire|girar|"
    r"estique|encurte|alongue|aumente|reduza|espelhe|rotacione)\b", re.I)
NEGATION_ONLY = re.compile(r"^\s*(sem|n[aã]o quero|tir[ae]|remov[ae])\b.*", re.I)


def is_zai_pilot(conn: Optional[Dict[str, Any]]) -> bool:
    """Detecta se a conexão é o perfil Piloto CAD (Z.ai + GLM-4.5)."""
    if not conn:
        return False
    host = (conn.get("base_url") or "").lower()
    model = (conn.get("model") or "").lower()
    return "api.z.ai" in host and model.startswith("glm-4.5")


# ------------------------------------------------------------ conhecimento
def knowledge_package() -> Dict[str, Any]:
    """Pacote versionado — exibível como resumo no diagnóstico, sem chaves."""
    return {
        "version": KNOWLEDGE_VERSION,
        "glossario": {
            "face": "superfície frontal onde ficam os gabinetes de LED",
            "gabinete": "módulo de LED; 960 mm é a autoridade quando o contexto indicar",
            "modulação": "grade de gabinetes (colunas × fileiras)",
            "gaiola": "quadro estrutural atrás do painel, no módulo dos gabinetes",
            "quadro": "moldura perimetral da gaiola",
            "travessa": "barra horizontal",
            "diagonal": "barra inclinada de reforço",
            "poste": "coluna vertical que sustenta o painel",
            "base": "chapa/lastro no solo sob o poste",
            "parede": "instalação apoiada em parede, sem postes",
            "suspensão": "painel suspenso por tirantes/estrutura superior",
            "passarela": "plataforma de manutenção atrás do painel",
            "guarda-corpo": "proteção perimetral da passarela (1,10 m)",
            "cota ao solo": "altura livre entre o solo e a base do painel",
        },
        "unidades": {
            "regra": "mm interno; aceitar cm/m com vírgula decimal e converter",
            "ambiguidade": "'4×2 m' é metros; '4×2 gabinetes' é contagem — nunca confundir",
        },
        "coordenadas": {"x": "largura", "y": "profundidade", "z": "altura", "solo": "Z=0"},
        "produto": {
            "gabinete_960_autoridade": "960 mm permanece autoridade quando a "
                                       "receita/contexto indicar 960; não trocar por suposição",
            "receitas": ["parede", "um poste", "dois postes", "suspenso", "rental/totem"],
            "pendencia_declarada": ["dupla face", "circular"],
        },
        "limites": ("esboço geométrico — não é aprovação estrutural, cálculo, "
                    "preço ou lista de corte"),
    }


def knowledge_block() -> str:
    """Bloco de conhecimento injetado no prompt do piloto (compacto)."""
    k = knowledge_package()
    g = k["glossario"]
    return f"""## PACOTE DO PILOTO CAD (v{k["version"]})
- Glossário: {"; ".join(f"{t}={d}" for t, d in list(g.items())[:14])}.
- Unidades: {k["unidades"]["regra"]}. {k["unidades"]["ambiguidade"]}.
- Coordenadas: X={k["coordenadas"]["x"]}, Y={k["coordenadas"]["y"]}, Z={k["coordenadas"]["z"]}, solo em Z=0.
- Produto: gabinete de {k["produto"]["gabinete_960_autoridade"]}.
  Receitas prontas: {", ".join(k["produto"]["receitas"])}. Declare pendência para: {", ".join(k["produto"]["pendencia_declarada"])}.
- {k["limites"].capitalize()}.
- Roteiro: pedido completo → spec paramétrica; cita seleção → edição local preservando o resto; pergunta → resposta curta; ambíguo → UMA pergunta objetiva."""


# ------------------------------------------------------------- roteador
def classify(text: str, intent: Optional[Dict[str, Any]] = None) -> str:
    """Classifica a mensagem: new_project | local_edit | question |
    ambiguous | review. Python decide a rota ANTES do LLM."""
    t = (text or "").strip()
    if not t:
        return "ambiguous"
    if REVIEW_WORDS.search(t) and not CREATE_WORDS.search(t):
        return "review"
    base = (intent or {}).get("intent")
    if base in ("new", "global_resize"):
        # pedido de criação sem medidas de painel → ambíguo (perguntar)
        if not (intent or {}).get("panel"):
            if QUESTION_WORDS.search(t) and not CREATE_WORDS.search(t):
                return "question"
            return "ambiguous"
        return "new_project"
    if QUESTION_WORDS.search(t) and not EDIT_WORDS.search(t) and not CREATE_WORDS.search(t):
        return "question"
    if EDIT_WORDS.search(t) or NEGATION_ONLY.match(t):
        return "local_edit"
    if base == "local_edit":
        return "local_edit"
    return "ambiguous"

def classify_with_selection(text: str, intent: Optional[Dict[str, Any]] = None,
                            selection_count: int = 0) -> str:
    """Classifica considerando seleção real: com elementos selecionados + verbos
    de edição → local_edit; sem seleção + pedido vago → ambiguous."""
    # Enriquecer intenção com preset se detectado
    enriched = enrich_intent_with_preset(text, intent)
    if enriched:
        intent = enriched
    base = classify(text, intent)
    if selection_count > 0 and EDIT_WORDS.search(text or ""):
        return "local_edit"
    if base == "local_edit" and selection_count == 0 and not NEGATION_ONLY.match(text or ""):
        # Edição local sem seleção específica pode ser ambígua
        if not any(w in (text or "").lower() for w in ["todos", "todas", "painel", "gaiola", "postes"]):
            return "ambiguous"
    return base


# -------------------------------------------------------- resposta factual
def answer_factual(model: Any, text: str) -> Optional[str]:
    """Perguntas factuais respondidas sem LLM e sem mutação (rota question)."""
    t = (text or "").lower()
    p = model.panel
    inst = model.installation
    checks = [
        ("largura", f"A largura do painel é {p.width:.0f} mm."),
        ("altura", f"A altura do painel é {p.height:.0f} mm."),
        ("profundidade", f"A profundidade é {p.depth:.0f} mm."),
        ("altura total", f"A altura total (solo + painel) é "
                         f"{(inst.ground_clearance or 0) + p.height:.0f} mm."),
        ("cota", f"A cota ao solo é {inst.ground_clearance or 0:.0f} mm."),
        ("quantos elementos", f"O projeto tem {len(model.elements)} elementos."),
        ("elementos", f"O projeto tem {len(model.elements)} elementos."),
    ]
    for key, ans in checks:
        if key in t and "?" in t or key in t and QUESTION_WORDS.search(text or ""):
            if key in t:
                return ans
    return None


# ------------------------------------------------------------- memória
def _load() -> Dict[str, Any]:
    try:
        if MEMORY_FILE.exists():
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save(doc: Dict[str, Any]) -> None:
    try:
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    except Exception:
        pass


def memory_get(project_id: str) -> Optional[Dict[str, Any]]:
    return _load().get(project_id) or None


def memory_valid(project_id: str, revision: int) -> Optional[Dict[str, Any]]:
    """Memória só vale para o MESMO projeto na MESMA revisão."""
    m = memory_get(project_id)
    if m and m.get("revision") == revision:
        return m
    return None


def memory_update(project_id: str, revision: int,
                  **fields: Any) -> Dict[str, Any]:
    doc = _load()
    entry = doc.get(project_id) or {}
    if entry.get("revision") != revision:
        entry = {"revision": revision}  # troca de revisão invalida o anterior
    entry.update({k: v for k, v in fields.items() if v is not None})
    entry["updated_at"] = time.time()
    doc[project_id] = entry
    _save(doc)
    return entry


def memory_clear_pending(project_id: str) -> None:
    m = memory_get(project_id)
    if not m:
        return
    m.pop("pending_question", None)
    m.pop("pending_plan", None)
    memory_update(project_id, m.get("revision", 0), **{k: v for k, v in m.items()
                                                       if k not in ("revision", "updated_at", "pending_question", "pending_plan")})


def complete_short_answer(project_id: str, revision: int,
                          text: str) -> Optional[str]:
    """Se a memória tem pergunta pendente e a mensagem é uma resposta curta,
    devolve o texto combinado (pergunta anterior + resposta)."""
    m = memory_valid(project_id, revision)
    if not m or not m.get("pending_question"):
        return None
    t = (text or "").strip()
    if not t or len(t) > 60:
        return None
    if re.search(r"\d", t) or re.search(r"\b(sim|não|nao)\b", t, re.I):
        return f"{m['pending_question']} — resposta do usuário: {t}"
    return None


# -------------------------------------------------- seleção e edição local
def build_selection_context(model: Any, selection_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Constrói contexto estrutural da seleção real do modelo."""
    if not selection_ids:
        return {"selected": [], "count": 0}

    selected = []
    for el in model.elements:
        if getattr(el, "id", None) in selection_ids:
            selected.append({
                "id": el.id,
                "type": el.type,
                "group": el.group or "",
                "profile": el.profile or "",
            })
    return {"selected": selected, "count": len(selected)}


def classify_with_selection(text: str, intent: Optional[Dict[str, Any]] = None,
                            selection_count: int = 0) -> str:
    """Classifica considerando seleção real: com elementos selecionados + verbos
    de edição → local_edit; sem seleção + pedido vago → ambiguous."""
    base = classify(text, intent)
    if selection_count > 0 and EDIT_WORDS.search(text or ""):
        return "local_edit"
    if base == "local_edit" and selection_count == 0 and not NEGATION_ONLY.match(text or ""):
        # Edição local sem seleção específica pode ser ambígua
        if not any(w in (text or "").lower() for w in ["todos", "todas", "painel", "gaiola", "postes"]):
            return "ambiguous"
    return base


# -------------------------------------------------- ausências explícitas
def detect_explicit_absences(text: str) -> List[str]:
    """Detecta pedidos explícitos de ausência: 'sem passarela', 'sem guarda-corpo'."""
    t = (text or "").lower()
    absences = []

    patterns = [
        (r"\bsem\s+passarela\b", "passarela"),
        (r"\bsem\s+guarda[- ]?corpo\b", "guarda-corpo"),
        (r"\bsem\s+gaiola\b", "gaiola"),
        (r"\bsem\s+poste[s]?\b", "postes"),
        (r"(?:não quero|tirar|remover|excluir)\s+(?:a\s+)?passarela\b", "passarela"),
        (r"(?:não quero|tirar|remover|excluir)\s+(?:o\s+)?guarda[- ]?corpo\b", "guarda-corpo"),
    ]

    for pattern, feature in patterns:
        if re.search(pattern, t):
            if feature not in absences:
                absences.append(feature)

    return absences


def validate_absences_against_model(model: Any, absences: List[str]) -> Dict[str, Any]:
    """Valida ausências pedidas contra o estado real do modelo."""
    panel = model.panel
    inst = model.installation
    groups = {}
    for el in model.elements:
        g = (el.group or "").upper()
        for key in ["GAIOLA", "PASSARELA", "GUARDA"]:
            if key in g:
                groups[key.lower()] = True

    result = {
        "already_absent": [],
        "to_remove": [],
        "message": None,
    }

    for feature in absences:
        present = groups.get(feature, False)
        if feature == "passarela":
            present = present or ("PASSARELA" in groups)
        if feature == "guarda-corpo":
            present = present or ("GUARDA" in groups)

        if present:
            result["to_remove"].append(feature)
        else:
            result["already_absent"].append(feature)

    if result["already_absent"] and not result["to_remove"]:
        items = ", ".join(result["already_absent"])
        result["message"] = f"Já atendido: {items} não está(ão) presente(s)."

    return result


# -------------------------------------------------- mensagem do usuário
def build_user_message(text: str, intent: Optional[Dict[str, Any]] = None,
                       selection_ids: Optional[List[str]] = None,
                       model: Any = None) -> str:
    """Mensagem do usuário com contexto canônico + seleção real + ausências."""
    parts = [intent_block(intent)]
    # Contexto de seleção real
    if selection_ids and model:
        sel_ctx = build_selection_context(model, selection_ids)
        if sel_ctx["count"] > 0:
            ids_str = ", ".join(s["id"] for s in sel_ctx["selected"][:5])
            parts.append(f"SELEÇÃO REAL ({sel_ctx['count']} elemento(s)): {ids_str}")
    # Ausências explícitas
    absences = detect_explicit_absences(text)
    if absences:
        parts.append(f"AUSÊNCIAS EXPLÍCITAS PEDIDAS: {', '.join(absences)}")
    parts.append(f"Pergunta: {text}")
    return "\n".join(parts)


def build_review_response(model: Any, absences: List[str] = None) -> Dict[str, Any]:
    """Constrói resposta de revisão honesta: presentes, ausentes, pendências."""
    panel = model.panel
    inst = model.installation
    groups = {}
    for el in model.elements:
        g = (el.group or "").upper()
        for key in ["GAIOLA", "PASSARELA", "GUARDA"]:
            if key in g:
                groups[key.lower()] = True
    presentes = []
    if panel.width > 0 and panel.height > 0:
        presentes.append(f"painel {round(panel.width)}x{round(panel.height)} mm")
    if groups.get("gaiola"):
        presentes.append(f"gaiola (prof {round(panel.depth or 0)} mm)")
    if any(el.type == "post" for el in model.elements):
        presentes.append(f"{inst.posts} poste(s)")
    if groups.get("passarela"):
        presentes.append("passarela")
    if groups.get("guarda-corpo"):
        presentes.append("guarda-corpo")
    ausentes_solicitados = []
    if absences:
        for a in absences:
            norm = a.replace("-", "-")
            if not groups.get(norm):
                ausentes_solicitados.append(a)
    pendencias = []
    # Apenas pendências geométricas reais, não opcionais não solicitados
    return {
        "presentes": presentes,
        "ausentes_solicitados": ausentes_solicitados,
        "pendencias": pendencias,
        "premissas": [],
    }