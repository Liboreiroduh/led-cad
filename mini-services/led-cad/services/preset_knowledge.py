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
        result.append({
            "id": p["id"],
            "name": p.get("name", p["id"]),
            "category": p.get("category", ""),
            "size_mm": p.get("size_mm", [0, 0]),
            "template": p.get("template", ""),
            "description": p.get("description", ""),
        })
    return result


def find_preset_by_id(preset_id: str) -> Optional[Dict[str, Any]]:
    """Busca um preset específico por ID."""
    for p in list_presets():
        if p["id"] == preset_id:
            return p
    return None


def find_presets_by_category(category: str) -> List[Dict[str, Any]]:
    """Filtra presets por categoria."""
    return [p for p in list_presets() if p.get("category") == category]


def find_presets_by_template(template: str) -> List[Dict[str, Any]]:
    """Filtra presets por template de instalação."""
    return [p for p in list_presets() if p.get("template") == template]


def preset_to_spec(preset: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Converte um preset em spec compatível com parametric.compile_spec.

    O preset define dimensões base (size_mm) e template de instalação.
    Overrides permitem adaptar: colunas/linhas de gabinetes, ground_clearance,
    presença de gaiola/passarela/guarda-corpo, etc.

    Preserva distinção entre nome comercial da referência e dimensão real.
    Medida explícita no override prevalece sobre size_mm do preset.
    """
    size = preset.get("size_mm", [0, 0])
    template = preset.get("template", "outdoor_2_posts")
    width, height = size[0], size[1]

    # Mapeamento template → parâmetros de instalação
    template_params = {
        "outdoor_1_post": {"posts": 1, "ground_clearance": 3000},
        "outdoor_2_posts": {"posts": 2, "ground_clearance": 3000},
        "outdoor_2_heavy": {"posts": 2, "ground_clearance": 4000},
        "wall": {"posts": 0, "ground_clearance": 2500},
        "rental": {"posts": 2, "ground_clearance": 800},
        "suspended": {"posts": 2, "ground_clearance": 3000},
    }
    install = template_params.get(template, {"posts": 2, "ground_clearance": 3000})

    # Defaults de gabinete: inferir de size_mm se não houver override
    # Não assumir 960 automaticamente — usar size_mm como base
    cabinet_w = 960  # default
    cabinet_h = 960
    cols = max(1, round(width / cabinet_w)) if width > 0 else 1
    rows = max(1, round(height / cabinet_h)) if height > 0 else 1

    # Aplicar overrides
    if overrides:
        if "cabinet_width" in overrides:
            cabinet_w = overrides["cabinet_width"]
            cols = max(1, round(width / cabinet_w)) if width > 0 else cols
        if "cabinet_height" in overrides:
            cabinet_h = overrides["cabinet_height"]
            rows = max(1, round(height / cabinet_h)) if height > 0 else rows
        if "columns" in overrides:
            cols = overrides["columns"]
        if "rows" in overrides:
            rows = overrides["rows"]
        if "posts" in overrides:
            install["posts"] = overrides["posts"]
        if "ground_clearance" in overrides:
            install["ground_clearance"] = overrides["ground_clearance"]

    # Calcular dimensões reais do painel baseado em colunas × gabinete
    panel_w = cols * cabinet_w
    panel_h = rows * cabinet_h

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

    spec = {
        "document_type": "led_structure_spec",
        "schema_version": 1,
        "units": "mm",
        "intent": "new",
        "family": template.replace("outdoor_", "").replace("_heavy", "") if "outdoor" in template else template,
        "panel": {
            "width": panel_w,
            "height": panel_h,
            "depth": 650 if cage_enabled else 0,
            "columns": cols,
            "rows": rows,
            "cabinet_width": cabinet_w,
            "cabinet_height": cabinet_h,
            "gap_x": 0,
            "gap_z": 0,
            "ground_clearance": install["ground_clearance"],
        },
        "cage": {"enabled": cage_enabled, "depth": 650},
        "supports": {"count": install["posts"], "positions": None},
        "walkway": {"enabled": walkway_enabled, "side": "rear", "depth": 600},
        "guardrail": {"enabled": guardrail_enabled, "height": 1100},
        "assumptions": [f"Baseado no preset {preset['id']}: {preset.get('name', '')}"],
    }

    return spec


def detect_preset_reference(text: str) -> Optional[str]:
    """Detecta menção a preset no texto do usuário.
    Foca em extrair padrões simples como '2x1', '4x3' mesmo em textos longos.
    """
    import re

    # Padrões robustos para capturar "NxM" ou "N.M" mesmo cercados por texto
    patterns = [
        r"(\d+)\s*[×xX\.]\s*(\d+)",  # 2x1, 2.1, 4X2
        r"(\d+)\s+por\s+(\d+)",       # 2 por 1
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            try:
                cols = int(match.group(1))
                rows = int(match.group(2))

                # Validação: colunas/linhas devem ser plausíveis (1-20)
                if 1 <= cols <= 20 and 1 <= rows <= 20:
                    # Calcula dimensão alvo baseada em gabinete padrão 960mm
                    target_w = cols * 960
                    target_h = rows * 960

                    # Busca preset mais próximo
                    best_match = None
                    best_diff = float('inf')

                    for p in list_presets():
                        sz = p.get("size_mm", [])
                        if len(sz) == 2:
                            diff = abs(sz[0] - target_w) + abs(sz[1] - target_h)
                            # Tolerância de 10% ou 200mm
                            if diff < best_diff and diff < max(target_w * 0.1, 200):
                                best_diff = diff
                                best_match = p["id"]

                    if best_match:
                        return best_match
            except (ValueError, IndexError):
                continue

    return None


def build_preset_context(preset_id: str, model: Any = None) -> Dict[str, Any]:
    """Constrói contexto de preset para envio ao LLM.

    Inclui:
    - Dados do preset (dimensões, template, descrição)
    - Spec gerada a partir do preset
    - Estado atual do modelo (se disponível) para comparação

    Não despeja todo o catálogo: envia apenas o preset relevante.
    """
    preset = find_preset_by_id(preset_id)
    if not preset:
        return {"error": f"Preset {preset_id} não encontrado"}

    spec = preset_to_spec(preset)

    context = {
        "preset": preset,
        "spec": spec,
        "model_state": None,
    }

    if model:
        context["model_state"] = {
            "panel": {
                "width": model.panel.width,
                "height": model.panel.height,
                "depth": model.panel.depth,
            },
            "elements_count": len(model.elements),
            "installation": {
                "ground_clearance": model.installation.ground_clearance,
                "posts": model.installation.posts,
            } if model.installation else None,
        }

    return context