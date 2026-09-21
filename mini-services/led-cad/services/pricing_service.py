"""Parâmetros de orçamento (preços) — seção "somente para orçamento".

Valores de referência em R$ (BRL), editáveis pela UI e persistidos em
data/pricing.json. O BOM multiplica peso × preço/kg + fator de perda.
NÃO é uma cotação formal — referência rápida para orçamento.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRICING_FILE = DATA_DIR / "pricing.json"

DEFAULTS: Dict[str, Any] = {
    "steel_profile_brl_kg": 14.90,   # R$/kg tubo quadrado/redondo laminado
    "steel_plate_brl_kg": 16.50,     # R$/kg chapa cortada
    "bolt_brl_unit_by_diameter": {   # chumbador/perna por diâmetro (mm)
        "16": 22.00,
        "20": 34.00,
        "25": 52.00,
        "32": 88.00,
    },
    "bolt_brl_unit_default": 45.00,
    "waste_factor": 1.08,            # 8% de perda de corte/sucata
    "paint_brl_kg": 3.20,            # pintura/tratamento por kg
    "concrete_brl_kg": 0.22,         # lastro/bloco de contrapeso (rental)
    "currency": "BRL",
    "updated_at": "",
}


def get_pricing() -> Dict[str, Any]:
    data = dict(DEFAULTS)
    if PRICING_FILE.exists():
        try:
            data.update(json.loads(PRICING_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return data


def save_pricing(patch: Dict[str, Any]) -> Dict[str, Any]:
    import time
    current = get_pricing()
    for key in ("steel_profile_brl_kg", "steel_plate_brl_kg", "waste_factor",
                "paint_brl_kg", "bolt_brl_unit_default", "concrete_brl_kg"):
        if key in patch:
            try:
                current[key] = max(0.0, float(patch[key]))
            except (TypeError, ValueError):
                pass
    if isinstance(patch.get("bolt_brl_unit_by_diameter"), dict):
        merged = dict(current["bolt_brl_unit_by_diameter"])
        for k, v in patch["bolt_brl_unit_by_diameter"].items():
            try:
                merged[str(int(float(k)))] = max(0.0, float(v))
            except (TypeError, ValueError):
                pass
        current["bolt_brl_unit_by_diameter"] = merged
    current["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    DATA_DIR.mkdir(exist_ok=True)
    PRICING_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8")
    return current


def bolt_unit_price(pricing: Dict[str, Any], diameter_mm: float) -> float:
    table = pricing.get("bolt_brl_unit_by_diameter", {})
    return float(table.get(str(int(diameter_mm)), pricing.get("bolt_brl_unit_default", 45.0)))


# ------------------------------------------------------------------ import CSV
# Formato aceito (separador ; ou , — cabeçalho opcional):
#   campo;valor            OU      perfil;14,90
#   perfil;14,90                   chapa;16.50
#   chapa;16,50                    pintura;3,20
#   pintura;3,20                   concreto;0,25
#   concreto;0,25                  perda;10
#   perda;10                       chumbador;45   (preço default)
#   chumbador_20;36,00             chumbador_20;36,00 (diâmetro específico)
CSV_ALIASES = {
    "perfil": "steel_profile_brl_kg",
    "perfil_kg": "steel_profile_brl_kg",
    "steel_profile": "steel_profile_brl_kg",
    "chapa": "steel_plate_brl_kg",
    "chapa_kg": "steel_plate_brl_kg",
    "steel_plate": "steel_plate_brl_kg",
    "pintura": "paint_brl_kg",
    "paint": "paint_brl_kg",
    "concreto": "concrete_brl_kg",
    "concrete": "concrete_brl_kg",
    "perda": "__waste_pct",
    "waste": "__waste_pct",
    "chumbador": "bolt_brl_unit_default",
    "bolt": "bolt_brl_unit_default",
}


def import_pricing_csv(text: str) -> Dict[str, Any]:
    """Importa preços de um CSV textual. Retorna {applied, ignored, patch}.

    Aceita 'campo;valor' (também ','), valores com vírgula decimal,
    cabeçalho opcional e chumbadores por diâmetro (chumbador_20).
    """
    import csv as _csv
    import io as _io

    applied: Dict[str, float] = {}
    ignored: list = []
    for row in _csv.reader(_io.StringIO(text.strip()), delimiter=";"):
        # fallback: tentar vírgula quando a linha não veio com ';'
        if len(row) == 1 and "," in row[0]:
            row = [c.strip() for c in row[0].split(",")]
        if len(row) < 2:
            continue
        key = str(row[0]).strip().lower().replace(" ", "_").replace("-", "_")
        val_raw = str(row[1]).strip().replace("R$", "").replace(" ", "").replace(",", ".")
        try:
            val = float(val_raw)
        except ValueError:
            ignored.append(f"{row[0]} (valor inválido)")
            continue
        if key.startswith("chumbador_"):
            dia = key.split("_", 1)[1].replace("mm", "").strip()
            try:
                dia_mm = int(float(dia))
            except ValueError:
                ignored.append(f"{row[0]} (diâmetro inválido)")
                continue
            current = get_pricing()
            table = dict(current.get("bolt_brl_unit_by_diameter", {}))
            table[str(dia_mm)] = max(0.0, val)
            save_pricing({"bolt_brl_unit_by_diameter": table})
            applied[f"chumbador_{dia_mm}"] = val
            continue
        target = CSV_ALIASES.get(key)
        if target is None:
            ignored.append(f"{row[0]} (campo desconhecido)")
            continue
        if target == "__waste_pct":
            save_pricing({"waste_factor": 1.0 + max(0.0, val) / 100.0})
            applied["perda_%"] = val
        else:
            save_pricing({target: val})
            applied[key] = val
    return {"applied": applied, "ignored": ignored}
