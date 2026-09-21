"""Estimativa de carga de vento (informativa, simplificada).

Referência de raciocínio: NBR 6123 (Forças devidas ao vento em
construções) — porém INTENCIONALMENTE SIMPLIFICADO para orçamento:
  q = 0,613 · V₀²  [N/m²]  (pressão dinâmica)
  F = q · Ce · A     (Ce = coeficiente de forma; placa plana ≈ 1,2;
                      treliça/perfis expostos ≈ 1,3)

A área estrutural é obtida por PROJEÇÃO REAL das barras no plano
frontal (perpendicular ao vento): cada barra é "engrossada" pela
largura do perfil e as sobreposições (frente/fundo) contam UMA vez,
por faixas de altura de 50 mm. A parte da treliça atrás do painel é
sombreada — conta 30% (bordas/vazados). Nada substitui cálculo
estrutural: o resultado é uma ESTIMATIVA para orçamento.

100% Python — parte do core, usado por BOM/UI/PDF/IA.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Tuple

from models.element import Element, ProjectModel
from models.profile import get_profile

# V₀ padrão (m/s) — zona de vento básica típica do interior do Brasil.
DEFAULT_V0_MS = 35.0
CE_PANEL = 1.2       # placa plana perpendicular ao vento
CE_FRAME = 1.3       # membros estruturais expostos
SHADOW_FACTOR = 0.3  # treliça atrás do painel (sombreada)
G = 9.81             # m/s²
ROW_MM = 50.0        # faixa de altura para unir sobreposições

DIRECTIONS = {
    "frontal": "frontal (face do painel)",
    "traseira": "traseiro (costas do painel)",
    "lateral": "lateral (perfil/profundidade)",
}

# Abrigo por painéis vizinhos (sombreamento de arranjos, telhas, meios-fios
# de concreto etc.): reduz a pressão EFETIVA sobre o painel. A treliça
# exposta continua integral (está sempre acima/acima do obstáculo).
OBSTRUCTION_LEVELS = {
    0.0: "sem obstrução (campo aberto)",
    0.2: "parcial (~20% abrigado — vizinhos/telhados próximos)",
    0.4: "forte (~40% abrigado — arranjo fechado/pátio)",
}


def normalize_obstruction(value) -> float:
    """Aceita 0..0.6 (fração abrigada) ou rótulos pt-BR e limita ao intervalo."""
    if isinstance(value, str):
        s = value.strip().lower()
        if re.search(r"sem|nenhum|aberto", s):
            return 0.0
        if re.search(r"parcial|m[ée]dio", s):
            return 0.2
        if re.search(r"forte|alto|muito", s):
            return 0.4
        m = re.search(r"(\d+[.,]?\d*)\s*%", s)
        if m:
            return min(0.6, max(0.0, float(m.group(1).replace(",", ".")) / 100.0))
        try:
            value = float(s.replace(",", "."))
        except ValueError:
            return 0.0
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if 0.0 < v <= 60.0 and v == int(v) and v > 1.0:  # veio % (ex.: 20)
        v = v / 100.0
    return min(0.6, max(0.0, v))


def normalize_direction(direction: str | None) -> str:
    d = (direction or "frontal").strip().lower()
    if d in ("frente", "frontal"):
        return "frontal"
    if d in ("tras", "trás", "traseira", "fundo"):
        return "traseira"
    if d in ("lateral", "lado", "perfil"):
        return "lateral"
    return "frontal"


def _beam_width_mm(el: Element) -> float:
    """Largura exposta média da barra (média entre w e h do perfil)."""
    prof = get_profile(el.profile or "METALON_40x40x2")
    return (prof.w + prof.h) / 2.0


def _thickened_rows(a: Tuple[float, float], b: Tuple[float, float],
                    width_mm: float) -> Dict[int, List[Tuple[float, float]]]:
    """Segmento 2D (x,z) engrossado por width → intervalos X por faixa Z."""
    (x0, z0), (x1, z1) = a, b
    dx, dz = x1 - x0, z1 - z0
    ln = math.hypot(dx, dz)
    rows: Dict[int, List[Tuple[float, float]]] = {}
    if ln < 1e-6:
        rows.setdefault(int(z0 / ROW_MM), []).append(
            (x0 - width_mm / 2, x0 + width_mm / 2))
        return rows
    steps = max(1, int(ln / ROW_MM))
    for i in range(steps):
        t0, t1 = i / steps, (i + 1) / steps
        xa, xb = x0 + dx * t0, x0 + dx * t1
        za, zb = z0 + dz * t0, z0 + dz * t1
        key = int(((za + zb) / 2) / ROW_MM)
        rows.setdefault(key, []).append(
            (min(xa, xb) - width_mm / 2, max(xa, xb) + width_mm / 2))
    return rows


def _rows_area(rows: Dict[int, List[Tuple[float, float]]]) -> float:
    """Área (mm²) = soma por faixa do comprimento unido × ROW_MM."""
    total = 0.0
    for spans in rows.values():
        if not spans:
            continue
        spans.sort()
        cur0, cur1 = spans[0]
        row_len = 0.0
        for a0, a1 in spans[1:]:
            if a0 <= cur1:  # sobrepõe — une
                cur1 = max(cur1, a1)
            else:
                row_len += cur1 - cur0
                cur0, cur1 = a0, a1
        row_len += cur1 - cur0
        total += row_len * ROW_MM
    return total


def frame_projected_areas(model: ProjectModel,
                          direction: str = "frontal") -> Tuple[float, float]:
    """Área projetada (mm²) das barras no plano PERPENDICULAR ao vento, em
    (abaixo_do_painel [exposição plena], sombra_do_painel [conta 30%]).

    Ventos frontal/traseiro projetam no plano X-Z (largura × altura);
    vento lateral projeta no plano Y-Z (profundidade × altura — só as
    pontas da treliça e o perfil dos postes pegam vento)."""
    lateral = normalize_direction(direction) == "lateral"
    panel_z0 = model.installation.ground_clearance
    below_rows: Dict[int, List[Tuple[float, float]]] = {}
    shadow_rows: Dict[int, List[Tuple[float, float]]] = {}
    for el in model.elements:
        if el.type != "beam":
            continue
        w = _beam_width_mm(el)
        s, e = el.start.as_tuple(), el.end.as_tuple()
        if lateral:
            rows = _thickened_rows((s[1], s[2]), (e[1], e[2]), w)  # (y, z)
        else:
            rows = _thickened_rows((s[0], s[2]), (e[0], e[2]), w)  # (x, z)
        zmax = max(s[2], e[2]) + w / 2
        target = below_rows if zmax <= panel_z0 else shadow_rows
        for key, spans in rows.items():
            target.setdefault(key, []).extend(spans)
    return _rows_area(below_rows), _rows_area(shadow_rows)


# Abrigo marcado POR ELEMENTO (🛡): área projetada dos elementos marcados
# SOMBREA o painel — aproximacao de solidez (área abrigada / área do painel),
# limitada a 60% como o abrigo genérico. Placas marcadas como abrigo pegam
# vento DIRETO (força própria somada — não estão na treliça).
SHIELD_CAP = 0.6


def shield_projected_areas(model: ProjectModel,
                           direction: str = "frontal") -> Tuple[float, float, int]:
    """(área_barras_mm², área_placas_mm², n_elementos) projetada dos
    elementos marcados com shield=True na direção do vento."""
    lateral = normalize_direction(direction) == "lateral"
    beam_rows: Dict[int, List[Tuple[float, float]]] = {}
    plates_mm2 = 0.0
    n = 0
    for el in model.elements:
        if not getattr(el, "shield", False):
            continue
        n += 1
        if el.type == "beam" and el.start and el.end:
            w = _beam_width_mm(el)
            s, e = el.start.as_tuple(), el.end.as_tuple()
            if lateral:
                rows = _thickened_rows((s[1], s[2]), (e[1], e[2]), w)
            else:
                rows = _thickened_rows((s[0], s[2]), (e[0], e[2]), w)
            for key, spans in rows.items():
                beam_rows.setdefault(key, []).extend(spans)
        elif el.type == "plate" and el.center:
            # projeção da chapa: frontal/traseira → largura×altura;
            # lateral → profundidade×altura (soma simples entre placas)
            if lateral:
                plates_mm2 += el.size_y * el.size_z
            else:
                plates_mm2 += el.size_x * el.size_z
    return _rows_area(beam_rows), plates_mm2, n


def estimate_wind(model: ProjectModel, v0_ms: float = DEFAULT_V0_MS,
                  direction: str = "frontal", obstruction: float = 0.0) -> Dict[str, Any]:
    """Estimativa de força de vento + efeitos por tipo de instalação.

    `direction`: frontal | traseira | lateral — muda o plano de projeção
    (largura×altura ou profundidade×altura) e a área exposta do painel.
    `obstruction`: fração 0..0,6 de abrigo por painéis vizinhos/obstáculos
    — reduz a força sobre o PAINEL (treliça exposta permanece integral)."""
    p = model.panel
    inst = model.installation
    dir_key = normalize_direction(direction)
    obs = normalize_obstruction(obstruction)

    q_kn_m2 = 0.613 * v0_ms ** 2 / 1000.0
    if dir_key == "lateral":
        area_panel_m2 = (p.depth * p.height) / 1_000_000.0
    else:
        area_panel_m2 = (p.width * p.height) / 1_000_000.0
    below_mm2, shadow_mm2 = frame_projected_areas(model, dir_key)
    area_below_m2 = below_mm2 / 1_000_000.0
    area_shadow_m2 = shadow_mm2 / 1_000_000.0
    area_frame_m2 = (below_mm2 + shadow_mm2) / 1_000_000.0

    # ---- abrigo por elementos marcados (🛡) ----
    shield_beams_mm2, shield_plates_mm2, n_shield = shield_projected_areas(model, dir_key)
    shield_area_m2 = (shield_beams_mm2 + shield_plates_mm2) / 1_000_000.0
    shelter_shield = (min(SHIELD_CAP, shield_area_m2 / area_panel_m2)
                      if area_panel_m2 > 0 else 0.0)
    shelter_total = min(SHIELD_CAP, obs + shelter_shield)

    f_panel_kn = q_kn_m2 * CE_PANEL * area_panel_m2 * (1.0 - shelter_total)
    f_frame_kn = q_kn_m2 * CE_FRAME * (area_below_m2 + SHADOW_FACTOR * area_shadow_m2)
    # placas de abrigo pegam vento DIRETO (não estão na treliça de barras)
    f_shield_plates_kn = q_kn_m2 * CE_PANEL * (shield_plates_mm2 / 1_000_000.0)
    f_total_kn = f_panel_kn + f_frame_kn + f_shield_plates_kn

    # altura do centro de pressão — o painel domina (área >> treliça)
    panel_cz = inst.ground_clearance + p.height / 2.0

    out: Dict[str, Any] = {
        "v0_ms": v0_ms,
        "q_kn_m2": round(q_kn_m2, 3),
        "ce_panel": CE_PANEL,
        "ce_frame": CE_FRAME,
        "obstruction": obs,
        "obstruction_label": OBSTRUCTION_LEVELS.get(round(obs, 2),
                                                   f"abrigo ~{int(round(obs * 100))}%"),
        "shield_elements": n_shield,
        "shield_area_m2": round(shield_area_m2, 2),
        "shelter_shield": round(shelter_shield, 3),
        "shelter_total": round(shelter_total, 3),
        "area_panel_m2": round(area_panel_m2, 2),
        "area_frame_m2": round(area_frame_m2, 2),
        "area_frame_below_m2": round(area_below_m2, 2),
        "force_panel_kn": round(f_panel_kn, 2),
        "force_frame_kn": round(f_frame_kn, 2),
        "force_total_kn": round(f_total_kn, 2),
        "direction": dir_key,
        "direction_label": DIRECTIONS[dir_key],
        "pressure_center_z_mm": round(panel_cz, 0),
        "note": (f"Estimativa simplificada p/ orçamento (raciocínio NBR 6123, "
                 f"vento {DIRECTIONS[dir_key]} V₀={v0_ms:.0f} m/s, q={q_kn_m2:.2f} kN/m²"
                 + (f", abrigo de painéis vizinhos {int(round(obs * 100))}% sobre o painel"
                    if obs > 0 else "")
                 + (f", abrigo por {n_shield} elemento(s) marcado(s) 🛡 "
                    f"({shield_area_m2:.2f} m² projetados — "
                    f"{int(round(shelter_shield * 100))}% do painel)"
                    if n_shield > 0 else "") + "). "
                 "Não substitui cálculo estrutural nem ART."),
    }

    # ---- efeitos por tipo de instalação ----
    if inst.type == "post":
        arm_m = panel_cz / 1000.0
        moment = f_total_kn * arm_m
        posts = [e for e in model.elements if e.role == "post"]
        n = max(1, len(posts))
        out.update({
            "overturning_moment_knm": round(moment, 1),
            "shear_per_post_kn": round(f_total_kn / n, 2),
            "posts": len(posts),
            "effect": (f"Corte na base ≈ {f_total_kn:.1f} kN "
                       f"({f_total_kn / n:.1f} kN/poste) · momento de "
                       f"tombamento ≈ {moment:.0f} kN·m — confira chumbadores "
                       "e chapa de base."),
        })
    elif inst.type == "wall":
        # pontos de fixação = chapas de apoio da parede (WP..) ou, na falta,
        # chumbadores; pior caso: braçadas (BR..)
        plates = [e for e in model.elements
                  if e.type == "plate" and e.id.upper().startswith("WP")]
        if not plates:
            plates = [e for e in model.elements if e.type == "bolt"]
        if not plates:
            plates = [e for e in model.elements if e.type == "plate"]
        n_f = max(1, len(plates))
        out.update({
            "effect": (f"Corte total ≈ {f_total_kn:.1f} kN sobre as fixações "
                       f"({f_total_kn / n_f:.2f} kN por ponto, {n_f} pts) — "
                       "confira tipo/quantidade de âncoras na parede."),
        })
    elif inst.type == "suspended":
        ties = [e for e in model.elements
                if "TIR" in e.id or "tirante" in (e.label or "").lower()]
        n_t = max(1, len(ties))
        out.update({
            "effect": (f"Tração nos tirantes ≈ {f_total_kn:.1f} kN "
                       f"({f_total_kn / n_t:.2f} kN/tirante, {n_t} tirantes) — "
                       "confira ancoragem na viga de teto."),
        })
    elif inst.type == "rental":
        from core.bom import build_bom
        bom = build_bom(model)
        mass_kg = bom["total_mass_kg"]
        ys = [e.center.y for e in model.elements
              if e.type == "plate" and "LASTRO" in (e.label or "").upper()]
        half_base_m = (max(ys) - min(ys)) / 2000.0 if len(ys) >= 2 else 0.4
        m_stab = mass_kg * G * half_base_m / 1000.0  # kN·m
        m_tip = f_total_kn * (panel_cz / 1000.0)
        ratio = (m_stab / m_tip) if m_tip > 0 else 99.0
        out.update({
            "overturning_moment_knm": round(m_tip, 1),
            "stabilizing_moment_knm": round(m_stab, 1),
            "tipping_safety_factor": round(ratio, 2),
            "effect": (f"Momento de vento ≈ {m_tip:.1f} kN·m × estabilizador "
                       f"≈ {m_stab:.1f} kN·m → FS tombamento ≈ {ratio:.1f}"
                       + (" — OK (≥1,5)." if ratio >= 1.5 else
                          " — ATENÇÃO: aumente o lastro (<1,5).")),
        })
    return out
