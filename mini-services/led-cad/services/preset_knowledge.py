"""Biblioteca de conhecimento de presets para painel LED.

Integra o catálogo de referências (presets/referencias/catalogo.json) ao
fluxo do piloto CAD, permitindo que a IA use presets como base para projetar
estruturas, adaptando dimensões, instalação e componentes opcionais.

Não é um glossário: é conhecimento operacional que mapeia referência → spec
geométrica via parametric.compile_spec.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

CATALOG_FILE = Path(__file__).resolve().parent.parent / "presets" / "referencias" / "catalogo.json"


def _load_catalog() -> Dict[str, Any]:
    """Carrega o catálogo de presets deduplicado."""
    try:
        if CATALOG_FILE.exists():
            data = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def list_presets() -> List[Dict[str, Any]]:
    """Lista todos os presets disponíveis com metadados úteis."""
    catalog = _load_catalog()
    presets = catalog.get("presets", [])
    result = []
    for p in presets:
        item = {
            "id": p["id"],
            "name": p.get("name", p["id"]),
            "category": p.get("category", ""),
            "size_mm": p.get("size_mm", [0, 0]),
            "template": p.get("template", ""),
            "description": p.get("description", ""),
        }
        ref = p.get("reference_geometry") or {}
        if ref:
            # Geometria específica da referência vence o template genérico.
            item["reference_geometry"] = {
                "bays": ref.get("bays"),
                "posts": ref.get("posts"),
                "ground_clearance": ref.get("ground_clearance"),
                "depth": ref.get("depth"),
                "post_profile": ref.get("post_profile"),
                "mid_rail_spacing_mm": ref.get("mid_rail_spacing_mm"),
                "source_pdf": ref.get("source_pdf"),
                "notes": ref.get("notes", []),
            }
        result.append(item)
    return result


def find_preset_by_id(preset_id: str) -> Optional[Dict[str, Any]]:
    """Busca um preset específico por ID."""
    for p in list_presets():
        if p["id"] == preset_id:
            return p
    return None


def detect_preset_reference(text: str) -> Optional[str]:
    """Detecta INTENÇÃO EXPLÍCITA de referência no texto do usuário.

    Comportamento correto:
    - "preset 4x2", "referência 4x2", "use o modelo 4x2",
      "igual ao 4x2 Fabian" → mapeia para REF_4000X2000
    - "painel 4x2 metros", "painel de 2000x4000 mm" → NÃO mapeia
      (é DIMENSÃO comum, não referência)
    - "2x4 gabinetes de 960" → NÃO mapeia (é contagem de gabinetes, não referência nominal)
    - "2 colunas × 1 fileira de gabinetes 960×960" → NÃO mapeia (modulação explícita)

    Só seleção automática com palavra-chave de referência; dimensão
    declarada sem esse vocabulário nunca escolhe preset.
    """
    import re

    t = (text or "")

    # CONTAGEM de gabinetes/colunas/fileiras NÃO é referência nominal:
    # nunca transformar modulação explícita em preset de metros.
    if re.search(r"\d+\s*[×xX]\s*\d+\s*(?:gabinete|m[óo]dulo|c[ée]lula)", t, re.I):
        return None
    if re.search(r"(?:gabinete|m[óo]dulo|c[ée]lula)s?\s+de\s+\d", t, re.I):
        return None
    if re.search(r"\d+\s*colunas?\s*[×xX]", t, re.I):
        return None
    # Regra 5 (blindagem extra): "N fileiras de gabinetes ..."/"colunas de
    # gabinetes" é MODULAÇÃO explícita — nunca referência nominal em metros.
    if re.search(r"(?:colunas?|fileiras?)\s+de\s+(?:gabinetes?|m[óo]dulos?|c[ée]lulas?)",
                 t, re.I):
        return None

    # Somente INTENÇÃO EXPLÍCITA de referência seleciona preset.
    # Dimensão comum ("painel 4×2 metros") NÃO é referência.
    patterns = [
        r"(?:preset|referência|referencia)\s+(\d+)\s*[×xX]\s*(\d+)",  # "preset 4x2", "referência 4x2"
        r"(?:modelo|igual\s+(?:a|ao|à|as|aos|às))\s+(?:o\s+|a\s+)?(\d+)\s*[×xX]\s*(\d+)",  # "modelo 4x2", "igual ao 4x2 Fabian"
        r"(?:ref|REF)[-_]?(\d)\s*[×xX]\s*(\d)",                       # "REF_4x2" ou "REF-4x2"
    ]

    for pattern in patterns:
        match = re.search(pattern, t, re.I)
        if match:
            try:
                val1 = int(match.group(1))
                val2 = int(match.group(2))

                # Validação: valores devem ser plausíveis para dimensões em metros (1-20)
                if 1 <= val1 <= 20 and 1 <= val2 <= 20:
                    # Converter para mm: assumir que são metros
                    target_w = val1 * 1000
                    target_h = val2 * 1000

                    # Buscar preset mais próximo por dimensão nominal
                    best_match = None
                    best_diff = float('inf')

                    for p in list_presets():
                        sz = p.get("size_mm", [])
                        if len(sz) == 2:
                            diff = abs(sz[0] - target_w) + abs(sz[1] - target_h)
                            # Tolerância: deve corresponder exatamente ou dentro de 100mm
                            if diff < best_diff and diff <= 100:
                                best_diff = diff
                                best_match = p["id"]

                    if best_match:
                        return best_match
            except (ValueError, IndexError):
                continue

    return None


def preset_to_spec(preset: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Converte um preset em spec compatível com parametric.compile_spec.

    O preset define dimensões base (size_mm) e template de instalação.
    Overrides permitem adaptar: colunas/linhas de gabinetes, ground_clearance,
    presença de gaiola/passarela/guarda-corpo, etc.

    Preserva distinção entre nome comercial da referência e dimensão real.
    Medida explícita no override prevalece sobre size_mm do preset.

    NUNCA assume gabinete 960: sem informação explícita de gabinete, a
    modulação usada é a da PRÓPRIA referência (reference_geometry) ou, na
    ausência dela, o painel inteiro como módulo único — as dimensões nominais
    do painel nunca são transformadas.
    """
    size = preset.get("size_mm", [0, 0])
    template = preset.get("template", "outdoor_2_posts")
    ref = preset.get("reference_geometry") or {}
    width, height = size[0], size[1]

    # Mapeamento template → parâmetros de instalação (fallback genérico)
    template_params = {
        "outdoor_1_post": {"posts": 1, "ground_clearance": 3000},
        "outdoor_2_posts": {"posts": 2, "ground_clearance": 3000},
        "outdoor_2_heavy": {"posts": 2, "ground_clearance": 4000},
        "wall": {"posts": 0, "ground_clearance": 2500},
        "rental": {"posts": 2, "ground_clearance": 800},
        "suspended": {"posts": 2, "ground_clearance": 3000},
    }
    install = template_params.get(template, {"posts": 2, "ground_clearance": 3000})

    # Geometria específica da referência vence o fallback do template
    if ref.get("posts") is not None:
        install["posts"] = ref["posts"]
    if ref.get("ground_clearance") is not None:
        install["ground_clearance"] = ref["ground_clearance"]

    # Dimensão nominal do preset é a dimensão REAL do painel
    panel_w = width
    panel_h = height

    # Aplicar overrides de dimensão real ANTES de derivar a modulação
    if overrides:
        if "width" in overrides:
            panel_w = overrides["width"]
        if "height" in overrides:
            panel_h = overrides["height"]

    # Modulação (columns/rows/cabinet no compilador paramétrico).
    # Precedência: gabinete explícito no override > modulação da referência >
    # painel inteiro como módulo único (nunca gabinete 960 assumido).
    cabinet_w = None
    cabinet_h = None
    cols = None
    rows = None
    mod_note = None
    if overrides and "cabinet_width" in overrides and "cabinet_height" in overrides:
        cabinet_w = overrides["cabinet_width"]
        cabinet_h = overrides["cabinet_height"]
        # Só calcula cols/rows se ambos os tamanhos de gabinete forem fornecidos
        cols = max(1, round(panel_w / cabinet_w)) if cabinet_w > 0 else 1
        rows = max(1, round(panel_h / cabinet_h)) if cabinet_h > 0 else 1
    elif ref.get("bays"):
        # Modulação estrutural da referência: vãos dos montantes (X) e
        # travessas no spacing registrado (Z). NÃO representa gabinete.
        spacing = float(ref.get("mid_rail_spacing_mm") or 1000)
        cols = max(1, int(ref["bays"]))
        cabinet_w = panel_w / cols
        rows = max(1, round(panel_h / spacing))
        cabinet_h = panel_h / rows
        mod_note = ("modulacao estrutural da referencia (montantes/travessas); "
                    "NAO representa gabinete")
    else:
        # Fallback sem nenhuma informação de modulação: painel inteiro.
        cols = 1
        rows = 1
        cabinet_w = panel_w
        cabinet_h = panel_h
        mod_note = "modulo unico = painel inteiro (sem gabinete informado)"

    if overrides:
        if "columns" in overrides:
            cols = overrides["columns"]
        if "rows" in overrides:
            rows = overrides["rows"]
        if "posts" in overrides:
            install["posts"] = overrides["posts"]
        if "ground_clearance" in overrides:
            install["ground_clearance"] = overrides["ground_clearance"]

    # Features opcionais: defaults por template
    cage_enabled = template not in ("wall", "rental")
    walkway_enabled = template in ("outdoor_2_posts", "outdoor_2_heavy")
    guardrail_enabled = walkway_enabled

    if overrides:
        if "cage" in overrides:
            cage_enabled = bool(overrides["cage"])
        if "walkway" in overrides:
            walkway_enabled = bool(overrides["walkway"])
        if "guardrail" in overrides:
            guardrail_enabled = bool(overrides["guardrail"]) and walkway_enabled

    depth = ref.get("depth") if ref.get("depth") is not None else (650 if cage_enabled else 0)

    assumptions = [f"Baseado no preset {preset['id']}: {preset.get('name', '')}"]
    if mod_note:
        assumptions.append(mod_note)
    if ref.get("source_pdf"):
        assumptions.append(f"Geometria mapeada de: {ref['source_pdf']}")
    for note in ref.get("notes", []):
        assumptions.append(f"Referência: {note}")

    spec = {
        "document_type": "led_structure_spec",
        "schema_version": 1,
        "units": "mm",
        "intent": "new",
        "family": template.replace("outdoor_", "").replace("_heavy", "") if "outdoor" in template else template,
        "panel": {
            "width": panel_w,
            "height": panel_h,
            "depth": depth,
            "columns": cols,
            "rows": rows,
            "cabinet_width": cabinet_w,
            "cabinet_height": cabinet_h,
            "gap_x": 0,
            "gap_z": 0,
            "ground_clearance": install["ground_clearance"],
        },
        "cage": {"enabled": cage_enabled, "depth": depth if cage_enabled else 650},
        "supports": {"count": install["posts"], "positions": None},
        "walkway": {"enabled": walkway_enabled, "side": "rear", "depth": 600},
        "guardrail": {"enabled": guardrail_enabled, "height": 1100},
        "assumptions": assumptions,
    }

    return spec

