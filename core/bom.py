"""Lista de Materiais (BOM) extraída automaticamente da geometria.

Agrupa por perfil: quantidade, comprimento unitário (médio), comprimento
total e peso estimado. Chapas entram com peso calculado por área×espessura
(7850 kg/m³). Custos em R$ via services/pricing_service.py (editável).
Arquitetura preparada para precisão futura.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List

from models.element import ProjectModel
from models.profile import get_profile
from services.pricing_service import bolt_unit_price, get_pricing

STEEL_DENSITY = 7850.0  # kg/m3
CONCRETE_DENSITY = 2400.0  # kg/m3 (lastro/blocos de contrapeso)
KG_PER_M2_PER_MM = STEEL_DENSITY / 1000.0  # kg/m2 por mm de espessura


def is_concrete(el) -> bool:
    """Blocos de lastro (rental/palco) são concreto, não aço."""
    txt = (el.label or "").upper()
    return "LASTRO" in txt or "CONCRETO" in txt


def _plate_mass_kg(el) -> float:
    density = CONCRETE_DENSITY if is_concrete(el) else STEEL_DENSITY
    area_m2 = (el.size_x * el.size_y) / 1_000_000.0
    return area_m2 * el.size_z * (density / 1000.0)


def _bolt_mass_kg(el) -> float:
    d_m = 0.025
    try:
        d_m = float(el.label.split("Ø")[1].split("mm")[0]) / 1000.0
    except Exception:
        pass
    volume = 3.1416 * (d_m / 2) ** 2 * (el.length() / 1000.0)
    return volume * STEEL_DENSITY * 1.6  # rosca/porca aproximadas


def _bolt_diameter_mm(el) -> float:
    try:
        return float(re.search(r"Ø(\d+)", el.label or "").group(1))
    except Exception:
        return 25.0


def build_bom(model: ProjectModel) -> Dict[str, Any]:
    pricing = get_pricing()
    beams: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "descr": "", "unit": "PC", "count": 0, "total_len_mm": 0.0, "lengths": [],
    })
    plates: List[Dict[str, Any]] = []
    bolts: List[Dict[str, Any]] = []

    for el in model.elements:
        if el.type == "panel":
            continue
        if el.type == "beam":
            prof = get_profile(el.profile or "METALON_40x40x2")
            entry = beams[prof.name]
            entry["descr"] = prof.label
            entry["count"] += 1
            entry["total_len_mm"] += el.length()
            entry["lengths"].append(round(el.length(), 0))
            entry["kgm"] = prof.kgm
        elif el.type == "plate":
            plates.append({
                "descr": el.label or el.id, "id": el.id, "count": 1,
                "mass": round(_plate_mass_kg(el), 2),
                "size": f"{el.size_x:.0f}x{el.size_y:.0f}x{el.size_z:.0f}",
                "concrete": is_concrete(el),
            })
        elif el.type == "bolt":
            bolts.append({"descr": el.label or el.id, "mass": round(_bolt_mass_kg(el), 2),
                          "diameter": _bolt_diameter_mm(el)})

    items: List[Dict[str, Any]] = []
    pos = 0
    total_mass = 0.0
    total_cost = 0.0

    # agrupa chapas iguais por descrição
    plate_groups: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "mass": 0.0, "concrete": False})
    for p in plates:
        g = plate_groups[p["descr"]]
        g["count"] += p["count"]
        g["mass"] += p["mass"]
        g["size"] = p["size"]
        g["concrete"] = g["concrete"] or p.get("concrete", False)

    bolt_groups: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "mass": 0.0, "diameter": 25.0})
    for b in bolts:
        g = bolt_groups[b["descr"]]
        g["count"] += 1
        g["mass"] += b["mass"]
        g["diameter"] = b["diameter"]

    # ordem: perfis, chapas, chumbadores
    p_kg = float(pricing.get("steel_profile_brl_kg", 14.9))
    c_kg = float(pricing.get("steel_plate_brl_kg", 16.5))
    paint_kg = float(pricing.get("paint_brl_kg", 3.2))
    conc_kg = float(pricing.get("concrete_brl_kg", 0.22))
    waste = float(pricing.get("waste_factor", 1.08)) or 1.0
    for name in sorted(beams):
        e = beams[name]
        if e["count"] == 0:
            continue
        pos += 1
        unit_len = e["total_len_mm"] / e["count"]
        mass = (e["total_len_mm"] / 1000.0) * e["kgm"]
        cost = mass * (p_kg + paint_kg) * waste
        total_mass += mass
        total_cost += cost
        items.append({
            "pos": pos, "descr": e["descr"], "profile": name,
            "compr": f"{unit_len:.0f}mm", "unid": "PCS", "quant": e["count"],
            "peso_unit": f"{e['kgm']:.2f} KG/M",
            "peso_total": round(mass, 2), "kind": "perfil",
            "custo_total": round(cost, 2),
        })
    for descr, g in sorted(plate_groups.items()):
        pos += 1
        total_mass += g["mass"]
        if g.get("concrete"):
            # lastro de concreto: preço próprio, sem pintura nem perda de corte
            cost = g["mass"] * conc_kg
            kind = "concreto"
        else:
            cost = g["mass"] * (c_kg + paint_kg) * waste
            kind = "chapa"
        total_cost += cost
        items.append({
            "pos": pos, "descr": descr, "profile": "-",
            "compr": g["size"], "unid": "PCS", "quant": g["count"],
            "peso_unit": f"{g['mass'] / max(1, g['count']):.2f} KG",
            "peso_total": round(g["mass"], 2), "kind": kind,
            "custo_total": round(cost, 2),
        })
    for descr, g in sorted(bolt_groups.items()):
        pos += 1
        total_mass += g["mass"]
        d_mm = g.get("diameter", 25.0)
        unit_price = bolt_unit_price(pricing, d_mm)
        cost = g["count"] * unit_price
        total_cost += cost
        items.append({
            "pos": pos, "descr": descr, "profile": "-",
            "compr": "-", "unid": "PCS", "quant": g["count"],
            "peso_unit": f"{g['mass'] / max(1, g['count']):.2f} KG",
            "peso_total": round(g["mass"], 2), "kind": "chumbador",
            "custo_total": round(cost, 2),
        })

    return {
        "items": items,
        "total_mass_kg": round(total_mass, 2),
        "total_cost_brl": round(total_cost, 2),
        "pricing": {
            "currency": pricing.get("currency", "BRL"),
            "steel_profile_brl_kg": p_kg,
            "steel_plate_brl_kg": c_kg,
            "paint_brl_kg": paint_kg,
            "concrete_brl_kg": conc_kg,
            "waste_factor": waste,
            "updated_at": pricing.get("updated_at", ""),
        },
        "totals": {
            "perfis": sum(1 for i in items if i["kind"] == "perfil"),
            "chapas": sum(1 for i in items if i["kind"] == "chapa"),
            "chumbadores": sum(1 for i in items if i["kind"] == "chumbador"),
            "concreto": sum(1 for i in items if i["kind"] == "concreto"),
        },
    }
