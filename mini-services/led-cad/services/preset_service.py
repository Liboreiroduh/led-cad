"""Serviço de presets: interpreta a configuração declarativa e gera o modelo.

O preset NÃO é desenhado manualmente no frontend: este módulo Python é quem
constrói todos os elementos (quadro, verticais, horizontais, travessas,
diagonais, poste, bases e chumbadores) a partir de parâmetros.

IDs estáveis e semânticos:
  POSTE-01..        postes (tubo vertical)
  V01..Vnn          verticais da face frontal
  VB01..VBnn        verticais da face traseira
  HS01/HSB01        horizontal superior frontal/traseiro
  HI01/HIB01        horizontal inferior frontal/traseiro
  HM01/HMB01        horizontal intermediário frontal/traseiro
  TSnn/TInn/TMnn    travessas de profundidade (topo/inferior/meio)
  DSnn/DInn         diagonais das faces superior/inferior (zigzag)
  DL01..DL04        diagonais "X" das faces laterais
  BASE-01..         chapas de base (solo)
  PLACA-01..        chapas de ligação no topo do poste
  CH01..            chumbadores
  PAINEL-LED        superfície do painel (referência visual)
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional

from core.geometry import linspace
from models.element import Element, Installation, Panel, ProjectModel, Vec3

PRESETS_DIR = Path(__file__).resolve().parent.parent / "presets"
CUSTOM_DIR = PRESETS_DIR / "custom"


def _preset_records():
    """Read individual presets and the deduplicated PDF reference catalog."""
    for path in sorted(PRESETS_DIR.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data.get("presets"), list):
            for preset in data["presets"]:
                if isinstance(preset, dict) and preset.get("id"):
                    yield preset, path, False
        elif data.get("id"):
            yield data, path, path.parent == CUSTOM_DIR


def _resolved_preset(data: dict) -> dict:
    """Expand compact reference cards to the format used by PresetBuilder."""
    if "defaults" in data or data.get("kind") == "snapshot":
        return data
    width, height = data["size_mm"]
    template = data.get("template", "outdoor_2_posts")
    templates = {
        "outdoor_1_post": {"installation": {"type": "post", "posts": 1, "ground_clearance": 3000, "environment": "outdoor"}, "depth": 650, "post": "TUBO_219x4.75"},
        "outdoor_2_posts": {"installation": {"type": "post", "posts": 2, "ground_clearance": 3000, "environment": "outdoor"}, "depth": 650, "post": "TUBO_219x4.75"},
        "outdoor_2_heavy": {"installation": {"type": "post", "posts": 2, "ground_clearance": 4000, "environment": "outdoor"}, "depth": 800, "post": "TUBO_380_t4.8"},
        "wall": {"installation": {"type": "wall", "posts": 0, "ground_clearance": 2500, "environment": "outdoor"}, "depth": 500},
        "rental": {"installation": {"type": "rental", "posts": 2, "ground_clearance": 800, "environment": "indoor"}, "depth": 600},
        "suspended": {"installation": {"type": "suspended", "posts": 2, "ground_clearance": 3000, "environment": "indoor"}, "depth": 600},
    }
    t = templates[template]
    profiles = {
        "frame": "METALON_60x60x2", "secondary": "METALON_40x40x2",
        "post": t.get("post", "TUBO_219x4.75"), "bracket": "METALON_50x50x2",
        "hanger": "TUBO_76x3.2", "ceiling_beam": "METALON_100x100x3",
        "tower": "METALON_100x100x3", "outrigger": "METALON_50x50x2",
    }
    return {
        **data,
        "defaults": {
            "panel": {"width": width, "height": height, "depth": data.get("depth", t["depth"])},
            "installation": {**t["installation"], **data.get("installation", {})},
            "profiles": profiles,
        },
        "rules": {
            "vertical_spacing_max": data.get("vertical_spacing_max", 960),
            "top_bottom_diagonals": "zigzag", "side_bracing": "X", "mid_rail": True,
            "wall_gap": 120, "wall_plate": 220, "wall_plate_t": 10, "drop": 1200,
        },
    }

# ---------------------------------------------------------------- catálogo


def list_presets() -> List[dict]:
    out: List[dict] = []
    for data, path, is_custom in _preset_records():
        out.append({
            "id": data["id"],
            "name": data["name"],
            "category": data["category"],
            "description": data.get("description", ""),
            "file": str(path.relative_to(PRESETS_DIR)),
            "custom": is_custom,
        })
    return out


# ------------------------------------------------------------ presets do usuário


def save_custom_preset(name: str, model_dict: Dict, source_preset_id: str = "") -> Dict:
    """Salva a configuração ATUAL (modelo inteiro, com todas as edições do
    usuário) como preset reutilizável em presets/custom/{slug}.json.

    kind="snapshot": recarregar este preset restaura o modelo EXATO salvo
    (barras movidas, perfis trocados, elementos extras) — é um template.
    """
    CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
    name = (name or "").strip() or "Preset personalizado"
    slug = _slug(name)
    pid = f"CUSTOM_{slug.upper()}"
    n = 2
    base_slug = slug
    while (CUSTOM_DIR / f"{slug}.json").exists():
        # mesmo nome → SOBRESCREVE (intencional: iterar sobre a própria versão)
        data_exist = json.loads((CUSTOM_DIR / f"{slug}.json").read_text(encoding="utf-8"))
        if data_exist.get("id") == pid:
            break
        slug = f"{base_slug}-{n}"
        pid = f"CUSTOM_{slug.upper()}"
        n += 1
    payload = {
        "id": pid,
        "name": name,
        "category": "custom",
        "description": f"Preset personalizado do usuário (a partir de {source_preset_id or 'projeto livre'}) — {len(model_dict.get('elements', []))} elementos.",
        "kind": "snapshot",
        "source_preset_id": source_preset_id,
        "created_at": _now(),
        "model": model_dict,
    }
    (CUSTOM_DIR / f"{slug}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {"id": pid, "name": name, "file": f"custom/{slug}.json",
            "elements": len(model_dict.get("elements", []))}


def delete_custom_preset(preset_id: str) -> bool:
    """Exclui um preset custom (só arquivos em presets/custom/)."""
    if not CUSTOM_DIR.exists():
        return False
    for path in CUSTOM_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("id") == preset_id:
            path.unlink()
            return True
    return False


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    return s or "preset"


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")


def load_preset(preset_id: str) -> Optional[dict]:
    for data, _path, _is_custom in _preset_records():
        if data["id"] == preset_id:
            return _resolved_preset(data)
    return None


def PRESETS_TOKEN(preset_id: str):
    return [path for _data, path, _is_custom in _preset_records()]


# ------------------------------------------------------------- gerador


class PresetBuilder:
    """Gera o ProjectModel a partir de um preset + overrides do usuário.

    Overrides (defaults do preset preservados quando não informados):
      panel: {width, height, depth}
      installation: {posts, ground_clearance}
      profiles: {frame, secondary, post}
    """

    def __init__(self, preset: dict, overrides: Optional[dict] = None) -> None:
        self.preset = preset
        ov = overrides or {}
        d = preset.get("defaults", {})

        panel = {**d.get("panel", {}), **(ov.get("panel") or {})}
        inst = {**d.get("installation", {}), **(ov.get("installation") or {})}
        profiles = {**d.get("profiles", {}), **(ov.get("profiles") or {})}

        self.panel = Panel(**panel)
        self.installation = Installation(**inst)
        self.profiles = profiles
        self.base_plate = d.get("base_plate", {"size": 680, "thickness": 25})
        self.cap_plate = d.get("post_cap_plate", {"size": 600, "thickness": 12})
        self.bolts = d.get("bolts", {"count": 4, "length": 1000, "diameter": 25, "offset": 250})
        self.rules = preset.get("rules", {})

        self.elements: List[Element] = []

    # ---------------------------------------------------------- helpers
    def _beam(self, eid: str, start, end, profile: str, role: str, group: str, label: str = "") -> Element:
        return Element(
            id=eid, type="beam", role=role, profile=profile,
            start=Vec3(**dict(zip(("x", "y", "z"), start))),
            end=Vec3(**dict(zip(("x", "y", "z"), end))),
            label=label or eid, group=group,
        )

    # ---------------------------------------------------------- faces
    def build(self) -> ProjectModel:
        if self.preset.get("kind") == "cube":
            self._build_cube()
            return self._model()
        self._build_panel()
        self._build_frame()
        self._build_depth_traves()
        self._build_diagonals()
        self._build_supports()
        return self._model()

    def _model(self) -> ProjectModel:
        return ProjectModel(
            project={"name": self.preset["name"], "client": "", "units": "mm"},
            panel=self.panel,
            installation=self.installation,
            elements=self.elements,
            preset_id=self.preset["id"],
        )

    # ---------------------------------------------------------- painel
    def _panel_bounds(self):
        w, h, d = self.panel.width, self.panel.height, self.panel.depth
        c = self.installation.ground_clearance
        return {
            "x0": -w / 2, "x1": w / 2,
            "y0": -d / 2, "y1": d / 2,
            "z0": c, "z1": c + h,
        }

    def _build_panel(self) -> None:
        b = self._panel_bounds()
        self.elements.append(Element(
            id="PAINEL-LED", type="panel", role="panel",
            center=Vec3(x=0, y=(b["y0"] + b["y1"]) / 2, z=(b["z0"] + b["z1"]) / 2),
            size_x=b["x1"] - b["x0"], size_y=50, size_z=b["z1"] - b["z0"],
            label="PAINEL DE LED", group="PAINEL",
        ))

    def _build_cube(self) -> None:
        """Preset de geometria livre: cubo estrutural, sem painel LED."""
        side = self.panel.width
        a, b = -side / 2, side / 2
        z0, z1 = 0.0, side
        pts = [(a, a, z0), (a, b, z0), (b, a, z0), (b, b, z0),
               (a, a, z1), (a, b, z1), (b, a, z1), (b, b, z1)]
        edges = ((0, 1), (0, 2), (1, 3), (2, 3), (4, 5), (4, 6),
                 (5, 7), (6, 7), (0, 4), (1, 5), (2, 6), (3, 7))
        for n, (p0, p1) in enumerate(edges, 1):
            self.elements.append(self._beam(
                f"CUBO-{n:02d}", pts[p0], pts[p1], self.profiles["frame"],
                "other", "CUBO ESTRUTURAL", f"ARESTA {n:02d}"))

    # ---------------------------------------------------------- quadro
    def _vertical_xs(self) -> List[float]:
        w = self.panel.width
        spacing_max = float(self.rules.get("vertical_spacing_max", 1000))
        n_bays = max(2, math.ceil(w / spacing_max))
        return linspace(-w / 2, w / 2, n_bays + 1)

    def _build_frame(self) -> None:
        b = self._panel_bounds()
        prof = self.profiles["frame"]
        sec = self.profiles["secondary"]
        xs = self._vertical_xs()
        z0, z1 = b["z0"], b["z1"]
        has_mid = bool(self.rules.get("mid_rail", True))
        zm = (z0 + z1) / 2

        for i, x in enumerate(xs, start=1):
            self.elements.append(self._beam(
                f"V{i:02d}", (x, b["y1"], z0), (x, b["y1"], z1), prof, "vertical", "QUADRO"))
            self.elements.append(self._beam(
                f"VB{i:02d}", (x, b["y0"], z0), (x, b["y0"], z1), prof, "vertical", "QUADRO"))

        # horizontais topo/fundo/meio (frontal e traseiro)
        self.elements.append(self._beam(
            "HS01", (xs[0], b["y1"], z1), (xs[-1], b["y1"], z1), prof, "horizontal", "QUADRO"))
        self.elements.append(self._beam(
            "HI01", (xs[0], b["y1"], z0), (xs[-1], b["y1"], z0), prof, "horizontal", "QUADRO"))
        self.elements.append(self._beam(
            "HSB01", (xs[0], b["y0"], z1), (xs[-1], b["y0"], z1), prof, "horizontal", "QUADRO"))
        self.elements.append(self._beam(
            "HIB01", (xs[0], b["y0"], z0), (xs[-1], b["y0"], z0), prof, "horizontal", "QUADRO"))
        if has_mid:
            self.elements.append(self._beam(
                "HM01", (xs[0], b["y1"], zm), (xs[-1], b["y1"], zm), sec, "horizontal", "QUADRO"))
            self.elements.append(self._beam(
                "HMB01", (xs[0], b["y0"], zm), (xs[-1], b["y0"], zm), sec, "horizontal", "QUADRO"))

    # -------------------------------------------------- travessas prof.
    def _build_depth_traves(self) -> None:
        b = self._panel_bounds()
        sec = self.profiles["secondary"]
        has_mid = bool(self.rules.get("mid_rail", True))
        zm = (b["z0"] + b["z1"]) / 2
        n = 0
        for x in self._vertical_xs():
            n += 1
            self.elements.append(self._beam(
                f"TS{n:02d}", (x, b["y0"], b["z1"]), (x, b["y1"], b["z1"]), sec, "trave", "TRAVESSAS"))
            self.elements.append(self._beam(
                f"TIn{n:02d}", (x, b["y0"], b["z0"]), (x, b["y1"], b["z0"]), sec, "trave", "TRAVESSAS"))
            if has_mid:
                self.elements.append(self._beam(
                    f"TM{n:02d}", (x, b["y0"], zm), (x, b["y1"], zm), sec, "trave", "TRAVESSAS"))

    # -------------------------------------------------- diagonais
    def _build_diagonals(self) -> None:
        b = self._panel_bounds()
        sec = self.profiles["secondary"]
        xs = self._vertical_xs()
        pattern = self.rules.get("top_bottom_diagonals", "zigzag")
        n = 0
        for level, z in (("S", b["z1"]), ("I", b["z0"])):
            for i in range(len(xs) - 1):
                n += 1
                x0, x1 = xs[i], xs[i + 1]
                if pattern == "zigzag":
                    y_start = b["y0"] if i % 2 == 0 else b["y1"]
                    y_end = b["y1"] if i % 2 == 0 else b["y0"]
                else:  # "X"
                    y_start, y_end = b["y0"], b["y1"]
                self.elements.append(self._beam(
                    f"D{level}{n:02d}", (x0, y_start, z), (x1, y_end, z), sec, "diagonal",
                    "CONTRAVENTAMENTO"))
        # reinicia contagem para faces laterais
        n = 0
        if self.rules.get("side_bracing", "X") == "X":
            for side, x in (("L", b["x0"]), ("R", b["x1"])):
                for (ya, za) in ((b["y0"], b["z0"]), (b["y1"], b["z1"])):
                    pass
                n += 1
                self.elements.append(self._beam(
                    f"D{side}{n:02d}", (x, b["y0"], b["z0"]), (x, b["y1"], b["z1"]),
                    sec, "diagonal", "CONTRAVENTAMENTO"))
                n += 1
                self.elements.append(self._beam(
                    f"D{side}{n:02d}", (x, b["y0"], b["z1"]), (x, b["y1"], b["z0"]),
                    sec, "diagonal", "CONTRAVENTAMENTO"))

    # -------------------------------------------------- suportes (por tipo)
    def _build_supports(self) -> None:
        kind = getattr(self.installation, "type", "post")
        if kind == "wall":
            self._build_wall_brackets()
        elif kind == "suspended":
            self._build_suspended()
        elif kind == "rental":
            self._build_rental()
        else:
            self._build_posts()

    # -------------------------------------------------- postes/bases
    def _post_positions(self) -> List[float]:
        w = self.panel.width
        k = self.installation.posts
        if k <= 1:
            return [0.0]
        return [w * (i + 0.5) / k - w / 2 for i in range(k)]

    def _build_wall_brackets(self) -> None:
        """Fixação em parede: braçadas horizontais + chapas de apoio na parede.

        A parede fica atrás da face traseira (y0), a uma distância WALL_GAP.
        Uma chapa de apoio (WALL_PLATE² × t) em cada ponto de fixação.
        Sem postes, sem chumbadores de solo.
        """
        b = self._panel_bounds()
        gap = float(self.rules.get("wall_gap", 120.0))
        prof = self.profiles.get("bracket", "METALON_50x50x2")
        pw = float(self.rules.get("wall_plate", 220.0))
        pt = float(self.rules.get("wall_plate_t", 10.0))
        ys = b["y0"] - gap  # face da parede
        levels = [("I", b["z0"]), ("M", (b["z0"] + b["z1"]) / 2), ("S", b["z1"])]
        n = 0
        m = 0
        for x in self._vertical_xs():
            for tag, z in levels:
                n += 1
                self.elements.append(self._beam(
                    f"BR{n:02d}", (x, ys, z), (x, b["y0"], z), prof, "trave",
                    "FIXAÇÃO PAREDE", label=f"BRAÇADA {tag}"))
                m += 1
                self.elements.append(Element(
                    id=f"WP{m:02d}", type="plate", role="plate",
                    center=Vec3(x=x, y=ys - pt / 2, z=z),
                    size_x=pw, size_y=pt, size_z=pw,
                    label=f"CHAPA DE APOIO {pw:.0f}x{pw:.0f}x{pt:.0f}",
                    group="FIXAÇÃO PAREDE"))

    def _build_suspended(self) -> None:
        """Painel suspenso: tirantes verticais do topo do quadro até a
        estrutura de teto (viga + chapas de ancoragem). Sem base no solo."""
        b = self._panel_bounds()
        drop = float(self.rules.get("drop", 1200.0))
        prof = self.profiles.get("hanger", "TUBO_76x3.2")
        beam_prof = self.profiles.get("ceiling_beam", "METALON_100x100x3")
        at = self.profiles.get("anchor_plate", {"size": 300, "thickness": 12})
        a_size = float(at.get("size", 300))
        a_t = float(at.get("thickness", 12))
        zs = b["z1"]
        zt = zs + drop
        xs = self._post_positions()
        for i, x in enumerate(xs, start=1):
            self.elements.append(self._beam(
                f"TIR-{i:02d}", (x, 0, zs), (x, 0, zt), prof, "post",
                "SUSPENSÃO", label=f"TIRANTE Ø{prof.split('_')[1].split('x')[0]} x {drop:.0f}mm"))
            self.elements.append(Element(
                id=f"ANC-{i:02d}", type="plate", role="base",
                center=Vec3(x=x, y=0, z=zt + a_t / 2),
                size_x=a_size, size_y=a_size, size_z=a_t,
                label=f"CHAPA DE ANCORAGEM {a_size:.0f}x{a_size:.0f}x{a_t:.0f}",
                group="SUSPENSÃO"))
        if len(xs) >= 2:
            self.elements.append(self._beam(
                "VIGA-TETO", (min(xs), 0, zt + a_t), (max(xs), 0, zt + a_t),
                beam_prof, "horizontal", "SUSPENSÃO", label="VIGA DE TETO"))

    def _build_rental(self) -> None:
        """Estrutura rental/palco: torres temporárias sobre blocos de LASTRO
        de concreto (não perfura o piso do evento), chapa de distribuição de
        carga e escoras traseiras com contrapeso contra tombamento.
        O lastro entra como 'concreto' no BOM (densidade 2400 kg/m³ e preço
        próprio — não é aço)."""
        b = self._panel_bounds()
        prof = self.profiles.get("tower", "METALON_100x100x3")
        outr = self.profiles.get("outrigger", "METALON_50x50x2")
        blk = self.rules.get("ballast_block", {})
        bsx = float(blk.get("size_x", 1000))
        bsy = float(blk.get("size_y", 800))
        bsh = float(blk.get("height", 150))
        rblk = self.rules.get("rear_block", {})
        rsx = float(rblk.get("size_x", 800))
        rsy = float(rblk.get("size_y", 500))
        rsh = float(rblk.get("height", 150))
        reach = float(self.rules.get("outrigger_reach", 900))
        dp = self.rules.get("dist_plate", {"size": 400, "thickness": 12})
        dsz = float(dp.get("size", 400) if isinstance(dp, dict) else 400)
        dt = float(dp.get("thickness", 12) if isinstance(dp, dict) else 12)
        clearance = self.installation.ground_clearance
        tp = self.profiles.get("top_plate", {"size": 300, "thickness": 10})
        tp_s = float(tp.get("size", 300) if isinstance(tp, dict) else 300)
        tp_t = float(tp.get("thickness", 10) if isinstance(tp, dict) else 10)
        z_top = clearance  # topo da torre encosta na base do painel
        z_tow0 = bsh + dt  # torre nasce sobre a chapa de distribuição
        for i, x in enumerate(self._post_positions(), start=1):
            # bloco de lastro de concreto sob a torre
            self.elements.append(Element(
                id=f"LST-{i:02d}", type="plate", role="base",
                center=Vec3(x=x, y=0, z=bsh / 2),
                size_x=bsx, size_y=bsy, size_z=bsh,
                label=f"LASTRO CONCRETO {bsx:.0f}x{bsy:.0f}x{bsh:.0f}",
                group="LASTRO"))
            # torre vertical
            self.elements.append(self._beam(
                f"TORRE-{i:02d}", (x, 0, z_tow0), (x, 0, z_top), prof, "post",
                "TORRES RENTAL",
                label=f"TORRE {prof.replace('METALON_', '').replace('x', '×', 1)} x {max(0.0, z_top - z_tow0):.0f}mm"))
            # chapa de distribuição de carga entre bloco e torre
            self.elements.append(Element(
                id=f"DIST-{i:02d}", type="plate", role="plate",
                center=Vec3(x=x, y=0, z=bsh + dt / 2),
                size_x=dsz, size_y=dsz, size_z=dt,
                label=f"CHAPA DE DISTRIBUIÇÃO {dsz:.0f}x{dsz:.0f}x{dt:.0f}",
                group="TORRES RENTAL"))
            # chapa de ligação no topo da torre
            self.elements.append(Element(
                id=f"PLACA-{i:02d}", type="plate", role="plate",
                center=Vec3(x=x, y=0, z=z_top - tp_t / 2),
                size_x=tp_s, size_y=tp_s, size_z=tp_t,
                label=f"CHAPA DE LIGAÇÃO {tp_s:.0f}x{tp_s:.0f}x{tp_t:.0f}",
                group="TORRES RENTAL"))
            # escora traseira contra tombamento + bloco de contrapeso no pé
            yr = -(abs(b["y0"]) + reach)
            self.elements.append(self._beam(
                f"ESC-{i:02d}", (x, 0, z_top), (x, yr, rsh), outr,
                "diagonal", "ESCORAS",
                label=f"ESCORA {outr.replace('METALON_', '')}"))
            self.elements.append(Element(
                id=f"LBR-{i:02d}", type="plate", role="base",
                center=Vec3(x=x, y=yr - rsy / 2, z=rsh / 2),
                size_x=rsx, size_y=rsy, size_z=rsh,
                label=f"LASTRO CONCRETO {rsx:.0f}x{rsy:.0f}x{rsh:.0f}",
                group="LASTRO"))

    def _build_posts(self) -> None:
        b = self._panel_bounds()
        prof = self.profiles["post"]
        clearance = self.installation.ground_clearance
        tb = float(self.base_plate.get("thickness", 25))
        for i, x in enumerate(self._post_positions(), start=1):
            pid = f"POSTE-{i:02d}"
            self.elements.append(self._beam(
                pid, (x, 0, tb), (x, 0, clearance), prof, "post", "POSTES"))
            s = float(self.base_plate.get("size", 680))
            t = float(self.base_plate.get("thickness", 25))
            self.elements.append(Element(
                id=f"BASE-{i:02d}", type="plate", role="base",
                center=Vec3(x=x, y=0, z=t / 2),
                size_x=s, size_y=s, size_z=t,
                label=f"CHAPA DE BASE {s:.0f}x{s:.0f}x{t:.0f}", group="BASES"))
            cs = float(self.cap_plate.get("size", 600))
            ct = float(self.cap_plate.get("thickness", 12))
            self.elements.append(Element(
                id=f"PLACA-{i:02d}", type="plate", role="plate",
                center=Vec3(x=x, y=0, z=clearance - ct / 2),
                size_x=cs, size_y=cs, size_z=ct,
                label=f"CHAPA DE LIGAÇÃO {cs:.0f}x{cs:.0f}x{ct:.0f}", group="CHAPAS"))
            # chumbadores nos cantos da base
            off = float(self.bolts.get("offset", 250))
            bl = float(self.bolts.get("length", 1000))
            bd = float(self.bolts.get("diameter", 25))
            for j, (dx, dy) in enumerate(((-off, -off), (off, -off), (off, off), (-off, off)), start=1):
                self.elements.append(Element(
                    id=f"CH{i:02d}{j}", type="bolt", role="bolt",
                    start=Vec3(x=x + dx, y=dy, z=-bl + tb),
                    end=Vec3(x=x + dx, y=dy, z=tb),
                    label=f"CHUMBADOR \u00d8{bd:.0f} x {bl:.0f}mm", group="CHUMBADORES"))
