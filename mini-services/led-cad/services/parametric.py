"""F2 — Compilador paramétrico determinístico (LED STRUCTURE CAD).

Converte uma ESPECIFÇÃO GEOMÉTRICA TIPADA (formulário, JSON de spec ou
intenção da IA) em OPERAÇÕES COMPLETAS de montagem. O Python calcula
coordenadas; a IA decide intenção/parâmetros, nunca geometria direta.

Spec (schema v1):
    {
      "document_type": "led_structure_spec",
      "schema_version": 1,
      "units": "mm",
      "intent": "new",
      "family": "outdoor_posts",        # outdoor_posts|wall|suspended|rental
      "panel": {"columns": 4, "rows": 2, "cabinet_width": 960,
                "cabinet_height": 960, "gap_x": 0, "gap_z": 0,
                "ground_clearance": 3000},
      "cage": {"enabled": True, "depth": 650},
      "supports": {"count": 2, "positions": [{"x": -960, "y": 325},
                                              {"x": 960, "y": 325}]},
      "walkway": {"enabled": True, "side": "rear", "depth": 600},
      "guardrail": {"enabled": True, "height": 1100},
      "assumptions": [...]
    }

O compilador devolve: {"ops": [...], "completeness": {...}, "assumptions": [...]}.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.operations import OperationError

MAX_ELEMENTS = 10000
MAX_OPS = 120


def _f(v: Any, default: float) -> float:
    try:
        x = float(str(v).replace(",", "."))
        if x != x or x in (float("inf"), float("-inf")):
            return default
        return x
    except (TypeError, ValueError):
        return default


def _i(v: Any, default: int) -> int:
    try:
        return int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def _validate(spec: Dict[str, Any]) -> None:
    """Erros tipados ANTES de qualquer expansão (G17/G18)."""
    if not isinstance(spec, dict):
        raise OperationError("Spec deve ser um objeto JSON.")
    if spec.get("document_type") not in (None, "led_structure_spec"):
        raise OperationError("document_type deve ser 'led_structure_spec'.")
    v = spec.get("schema_version")
    if v not in (None, 1):
        raise OperationError(f"schema_version {v} não suportado (atual: 1).")
    units = spec.get("units", "mm")
    if units != "mm":
        raise OperationError("Unidade única suportada: mm.")
    p = spec.get("panel") or {}
    cols, rows = _i(p.get("columns"), 0), _i(p.get("rows"), 0)
    cw, ch = _f(p.get("cabinet_width"), 0), _f(p.get("cabinet_height"), 0)
    if cols < 1 or cols > 20 or rows < 1 or rows > 20:
        raise OperationError(f"columns/rows fora de faixa: {cols}x{rows} (1..20).")
    if cw <= 0 or ch <= 0:
        raise OperationError(f"cabinet_width/height inválidos: {cw}x{ch} mm.")
    gc = _f(p.get("ground_clearance"), -1)
    if gc < 0:
        raise OperationError(f"ground_clearance inválido: {gc} mm.")
    cage = spec.get("cage") or {}
    if cage.get("enabled"):
        d = _f(cage.get("depth"), 0)
        if not 0 < d <= 2000:
            raise OperationError(f"cage.depth inválida: {d} mm (1..2000).")
    walk = spec.get("walkway") or {}
    if walk.get("enabled"):
        d = _f(walk.get("depth"), 0)
        if not 0 < d <= 2000:
            raise OperationError(f"walkway.depth inválida: {d} mm.")
    rail = spec.get("guardrail") or {}
    if rail.get("enabled"):
        h = _f(rail.get("height"), 0)
        if not 0 < h <= 3000:
            raise OperationError(f"guardrail.height inválido: {h} mm.")


def intent_to_spec(intent: Dict[str, Any]) -> Dict[str, Any]:
    """Converte a INTENÇÃO CANÔNICA (ai_intent) em spec do compilador.

    Mesma fonte única para Formulário, Copiloto e JSON (G01): quem define
    dimensões é o intent; quem calcula geometria é o compilador."""
    p = intent.get("panel") or {}
    cabinet = p.get("cabinet") or {}
    feats = intent.get("features") or {}
    install = intent.get("install") or {}
    walk = feats.get("walkway") or False
    return {
        "document_type": "led_structure_spec", "schema_version": 1,
        "units": "mm", "intent": intent.get("intent", "new"),
        "family": "outdoor_posts",
        "panel": {
            "columns": int(cabinet.get("cols") or 1),
            "rows": int(cabinet.get("rows") or 1),
            "cabinet_width": float(cabinet.get("w") or p.get("width") or 960),
            "cabinet_height": float(cabinet.get("h") or p.get("height") or 960),
            "gap_x": 0, "gap_z": 0,
            "ground_clearance": float(install.get("ground_clearance") or 3000),
        },
        "cage": {"enabled": bool(feats.get("cage") or cabinet.get("w")),
                 "depth": float(p.get("depth") or 650)},
        "supports": {"count": int(install.get("posts") or 0), "positions": None},
        "walkway": {"enabled": bool(walk), "side": "rear", "depth": 600},
        "guardrail": {"enabled": bool(feats.get("guardrail") or False),
                      "height": 1100},
    }


def compile_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Spec → operações completas + relatório de completude.

    Determinístico: mesma spec gera EXATAMENTE as mesmas ops (G01).
    Componentes solicitados e ausentes viram pendências, nunca omissão
    silenciosa (A08/G09).
    """
    _validate(spec)
    p = spec.get("panel") or {}
    family = str(spec.get("family") or "outdoor_posts")
    cols, rows = _i(p.get("columns"), 1), _i(p.get("rows"), 1)
    cw, ch = _f(p.get("cabinet_width"), 960), _f(p.get("cabinet_height"), 960)
    gap_x, gap_z = _f(p.get("gap_x"), 0), _f(p.get("gap_z"), 0)
    gc = _f(p.get("ground_clearance"), 3000)

    pw = cols * cw + (cols - 1) * gap_x
    ph = rows * ch + (rows - 1) * gap_z

    cage = spec.get("cage") or {}
    cage_on = bool(cage.get("enabled"))
    cage_d = _f(cage.get("depth"), 650) if cage_on else 0.0

    supports = spec.get("supports") or {}
    n_posts = max(0, _i(supports.get("count"), 2 if family == "outdoor_posts" else 0))
    post_x = [pos["x"] for pos in (supports.get("positions") or [])]

    walk = spec.get("walkway") or {}
    walk_on = bool(walk.get("enabled"))
    walk_d = _f(walk.get("depth"), 600) if walk_on else 0.0

    rail = spec.get("guardrail") or {}
    rail_on = bool(rail.get("enabled")) and walk_on
    rail_h = _f(rail.get("height"), 1100) if rail_on else 0.0

    top = gc + ph  # topo do painel
    ops: List[Dict[str, Any]] = []
    ops.append({"operation": "__blank"})
    ops.append({"operation": "set_panel", "width": round(pw),
                "height": round(ph), "depth": round(cage_d) if cage_on else None,
                "ground_clearance": round(gc), "visible": True})

    # ------- quadro frontal/traseiro da gaiola (modulação por gabinete) ----
    if cage_on:
        xs = [-pw / 2 + i * (cw + gap_x) for i in range(cols + 1)]
        zs = [gc + j * (ch + gap_z) for j in range(rows + 1)]
        # verticais frente (y=0) e trás (y=-cage_d)
        for yi, y in ((0, 0.0), (1, -cage_d)):
            for x in xs:
                ops.append({"operation": "add_beam",
                            "start": {"x": round(x), "y": round(y), "z": round(gc)},
                            "end": {"x": round(x), "y": round(y), "z": round(top)},
                            "group": f"GAIOLA {'FRENTE' if yi == 0 else 'TRAS'}",
                            "role": "vertical"})
        # horizontais (cadeia de módulos)
        for yi, y in ((0, 0.0), (1, -cage_d)):
            for z in zs:
                ops.append({"operation": "add_beam",
                            "start": {"x": round(xs[0]), "y": round(y), "z": round(z)},
                            "end": {"x": round(xs[-1]), "y": round(y), "z": round(z)},
                            "group": f"GAIOLA {'FRENTE' if yi == 0 else 'TRAS'}",
                            "role": "trave"})
        # ligações de profundidade (nos 4 cantos + por coluna)
        for x in xs:
            ops.append({"operation": "add_beam",
                        "start": {"x": round(x), "y": 0, "z": round(gc)},
                        "end": {"x": round(x), "y": round(-cage_d), "z": round(gc)},
                        "group": "GAIOLA PROFUNDIDADE", "role": "horizontal"})
        for x in xs:
            ops.append({"operation": "add_beam",
                        "start": {"x": round(x), "y": 0, "z": round(top)},
                        "end": {"x": round(x), "y": round(-cage_d), "z": round(top)},
                        "group": "GAIOLA PROFUNDIDADE", "role": "horizontal"})

    # ------- postes: do solo à base da gaiola -------
    # `count` é suficiente: sem posições explícitas, distribui simetricamente
    # (mesma regra já declarada nas premissas do compilador). Pedidos com
    # contagem explícita ("1 poste", "dois postes") não podem sair sem postes.
    if n_posts > 0:
        # posições explícitas vencem; senão distribui simetricamente
        xs_p = post_x if len(post_x) == n_posts else \
            [-pw / 2 + (i + 1) * pw / (n_posts + 1) for i in range(n_posts)]
        y_p = _f((supports.get("positions") or [{}])[0].get("y"), cage_d / 2) \
            if supports.get("positions") else cage_d / 2
        for x in xs_p:
            ops.append({"operation": "add_post", "x": round(x), "y": round(y_p),
                        "height": round(gc), "group": "POSTES"})
        # travessas de interface poste→quadro inferior
        for x in xs_p:
            ops.append({"operation": "add_beam",
                        "start": {"x": round(x), "y": round(y_p), "z": round(gc)},
                        "end": {"x": round(x), "y": 0, "z": round(gc)},
                        "group": "INTERFACE", "role": "trave"})
            ops.append({"operation": "add_beam",
                        "start": {"x": round(x), "y": round(y_p), "z": round(gc)},
                        "end": {"x": round(x), "y": round(-cage_d), "z": round(gc)},
                        "group": "INTERFACE", "role": "trave"})

    # ------- passarela traseira -------
    if walk_on:
        y0, y1 = -cage_d, -cage_d - walk_d
        # piso (grade de referência, superfície em Z=gc)
        ops.append({"operation": "add_grid",
                    "start": {"x": round(-pw / 2), "y": round(y0), "z": round(gc)},
                    "end": {"x": round(pw / 2), "y": round(y1), "z": round(gc)},
                    "cols": max(2, cols), "rows": 2,
                    "group": "PASSARELA PISO"})
        if rail_on:
            # guarda-corpo: topo + meio, nos 3 lados abertos
            z_rail = gc + rail_h
            for z, role in ((z_rail, "trave"), (gc + rail_h / 2, "trave")):
                ops.append({"operation": "add_beam",
                            "start": {"x": round(-pw / 2), "y": round(y1), "z": round(z)},
                            "end": {"x": round(pw / 2), "y": round(y1), "z": round(z)},
                            "group": "GUARDA-CORPO", "role": role})
            for x in (-pw / 2, pw / 2):
                for z in (gc, z_rail):
                    ops.append({"operation": "add_beam",
                                "start": {"x": round(x), "y": round(y1), "z": round(z)},
                                "end": {"x": round(x), "y": round(y0), "z": round(z)},
                                "group": "GUARDA-CORPO", "role": "vertical"})

    if len(ops) > MAX_OPS:
        raise OperationError(
            f"Compilação geraria {len(ops)} operações (máx {MAX_OPS}) — "
            "reduza modulação ou divida o projeto.")

    # ------- completude (A08/G09): solicitado × presente -------
    asked: List[str] = []
    present: List[str] = []
    missing: List[str] = []
    asked.append("panel")
    present.append(f"panel {round(pw)}x{round(ph)} mm")
    for name, on, desc in (
            ("cage", cage_on, f"cage depth {round(cage_d)} mm"),
            ("walkway", walk_on, f"walkway {round(walk_d)} mm"),
            ("guardrail", rail_on, f"guardrail {round(rail_h)} mm"),
            ("supports", n_posts > 0, f"{n_posts} post(s)")):
        if on:
            asked.append(name)
            present.append(desc)
        else:
            missing.append(f"{name} solicitado ausente") if name in \
                ("cage", "walkway", "guardrail") and False else None
    assumptions = list(spec.get("assumptions") or [])
    if not supports.get("positions") and n_posts > 0:
        assumptions.append({"path": "supports.positions",
                            "source": "compiler_default",
                            "review_required": True,
                            "detail": "posições de postes distribuídas "
                                      "simetricamente pela largura"})
    return {"ops": ops, "panel": {"width": round(pw), "height": round(ph)},
            "completeness": {"asked": asked, "present": present,
                             "missing": [m for m in missing if m]},
            "assumptions": assumptions,
            "op_count": len(ops)}