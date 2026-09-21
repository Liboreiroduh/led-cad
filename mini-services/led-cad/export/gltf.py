"""Exportação GLTF 2.0 (glTF 1.0-compatible JSON + buffer embutido base64).

Tudo em Python puro (sem dependências): converte o modelo (mm, Z-up) para
unidades em metros com eixo Y-up (convenção glTF) e gera malhas:
  - beam quadrado  → prisma de seção quadrada (w do perfil);
  - beam redondo   → prisma de 12 lados (Ø do perfil);
  - plate          → caixa alinhada aos eixos;
  - bolt           → prisma de 8 lados fino;
  - panel          → caixa fina translúcida (material próprio).
Resultado: um .gltf único, pronto para Blender/three.js/Babylon.
"""
from __future__ import annotations

import base64
import json
import math
import struct
from typing import Any, Dict, List, Tuple

from models.element import ProjectModel
from models.profile import get_profile

# --------------------------------------------------------------- utilidades

Pt3 = Tuple[float, float, float]


def _to_gltf_axes(p: Pt3) -> Pt3:
    """mm, Z-up (x, y, z) → m, Y-up (x, z, -y)."""
    return (p[0] / 1000.0, p[2] / 1000.0, -p[1] / 1000.0)


def _norm(v: Pt3) -> Pt3:
    n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: Pt3, b: Pt3) -> Pt3:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _perp(u: Pt3) -> Pt3:
    """Vetor unitário perpendicular a u (qualquer, determinístico)."""
    if abs(u[0]) < 0.9:
        return _norm(_cross(u, (1.0, 0.0, 0.0)))
    return _norm(_cross(u, (0.0, 0.0, 1.0)))


class MeshBuilder:
    """Acumula posições/índices de triângulos em um único buffer."""

    def __init__(self) -> None:
        self.positions: List[float] = []
        self.indices: List[int] = []

    def add_prism(self, base_center_s: Pt3, base_center_e: Pt3,
                  u: Pt3, v: Pt3, half_sides: List[Tuple[float, float]]) -> None:
        """Prisma entre dois centros com seção definida por (du, dv) por vértice."""
        ring_s: List[Pt3] = []
        ring_e: List[Pt3] = []
        for du, dv in half_sides:
            off = (u[0] * du + v[0] * dv, u[1] * du + v[1] * dv, u[2] * du + v[2] * dv)
            ring_s.append((base_center_s[0] + off[0], base_center_s[1] + off[1], base_center_s[2] + off[2]))
            ring_e.append((base_center_e[0] + off[0], base_center_e[1] + off[1], base_center_e[2] + off[2]))
        n = len(half_sides)
        start = len(self.positions) // 3
        for p in ring_s + ring_e:
            self.positions.extend(_to_gltf_axes(p))
        # laterais
        for i in range(n):
            j = (i + 1) % n
            a = start + i
            b = start + j
            c = start + n + i
            d = start + n + j
            self.indices += [a, b, d, a, d, c]
        # tampas
        cs = start + 2 * n  # centro start
        ce = cs + 1
        self.positions.extend(_to_gltf_axes(base_center_s))
        self.positions.extend(_to_gltf_axes(base_center_e))
        for i in range(n):
            j = (i + 1) % n
            self.indices += [cs, start + j, start + i]
            self.indices += [ce, start + n + i, start + n + j]

    def add_box(self, minp: Pt3, maxp: Pt3) -> None:
        cx = ((minp[0] + maxp[0]) / 2, (minp[1] + maxp[1]) / 2, (minp[2] + maxp[2]) / 2)
        hx, hy, hz = (maxp[0] - minp[0]) / 2, (maxp[1] - minp[1]) / 2, (maxp[2] - minp[2]) / 2
        sides = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
        self.add_prism((cx[0], minp[2], cx[2]), (cx[0], maxp[2], cx[2]),
                       (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
                       [(s[0], s[1]) for s in sides])

    def to_bytes(self) -> bytes:
        blob = b""
        for v in self.positions:
            blob += struct.pack("<f", v)
        idx_blob = b""
        for i in self.indices:
            idx_blob += struct.pack("<I", i)
        return blob + idx_blob

    @property
    def pos_byte_len(self) -> int:
        return len(self.positions) * 4

    @property
    def idx_byte_len(self) -> int:
        return len(self.indices) * 4

    @property
    def idx_offset(self) -> int:
        return self.pos_byte_len


# ---------------------------------------------------------------- conversão

def _collect(model: ProjectModel) -> Tuple[MeshBuilder, MeshBuilder]:
    steel = MeshBuilder()
    panel = MeshBuilder()
    for el in model.elements:
        if el.type == "beam":
            prof = get_profile(el.profile or "METALON_40x40x2")
            s, e = el.start.as_tuple(), el.end.as_tuple()
            u = _norm((e[0] - s[0], e[1] - s[1], e[2] - s[2]))
            v = _perp(u)
            w = _cross(u, v)
            if prof.kind == "round":
                r = prof.w / 2.0
                sides = [(r * math.cos(2 * math.pi * i / 12),
                          r * math.sin(2 * math.pi * i / 12)) for i in range(12)]
            else:
                hw = prof.w / 2.0
                hh = prof.h / 2.0
                sides = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
            steel.add_prism(s, e, v, w, sides)
        elif el.type == "bolt":
            s, e = el.start.as_tuple(), el.end.as_tuple()
            u = _norm((e[0] - s[0], e[1] - s[1], e[2] - s[2]))
            v = _perp(u)
            w = _cross(u, v)
            r = 12.0
            sides = [(r * math.cos(2 * math.pi * i / 8), r * math.sin(2 * math.pi * i / 8))
                     for i in range(8)]
            steel.add_prism(s, e, v, w, sides)
        elif el.type == "plate":
            c = el.center.as_tuple()
            steel.add_box(
                (c[0] - el.size_x / 2, c[1] - el.size_y / 2, c[2] - el.size_z / 2),
                (c[0] + el.size_x / 2, c[1] + el.size_y / 2, c[2] + el.size_z / 2))
        elif el.type == "panel":
            c = el.center.as_tuple()
            panel.add_box(
                (c[0] - el.size_x / 2, c[1] - 25.0, c[2] - el.size_z / 2),
                (c[0] + el.size_x / 2, c[1] + 25.0, c[2] + el.size_z / 2))
    return steel, panel


def build_gltf(model: ProjectModel) -> bytes:
    steel, panel = _collect(model)
    buffers_bin = b""
    buffer_views = []
    accessors = []
    meshes = []

    def add_primitive(mb: MeshBuilder, material: int) -> None:
        nonlocal buffers_bin
        if not mb.indices:
            return
        bin_chunk = mb.to_bytes()
        bv_pos = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": len(buffers_bin),
                             "byteLength": mb.pos_byte_len, "target": 34962})
        bv_idx = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": len(buffers_bin) + mb.pos_byte_len,
                             "byteLength": mb.idx_byte_len, "target": 34963})
        buffers_bin += bin_chunk
        acc_pos = len(accessors)
        accessors.append({
            "bufferView": bv_pos, "componentType": 5126, "count": len(mb.positions) // 3,
            "type": "VEC3", "min": [min(mb.positions[i::3]) for i in range(3)],
            "max": [max(mb.positions[i::3]) for i in range(3)],
        })
        acc_idx = len(accessors)
        accessors.append({
            "bufferView": bv_idx, "componentType": 5125, "count": len(mb.indices),
            "type": "SCALAR",
            "min": [min(mb.indices)], "max": [max(mb.indices)],
        })
        meshes.append({
            "name": "Estrutura" if material == 0 else "PainelLED",
            "primitives": [{"attributes": {"POSITION": acc_pos}, "indices": acc_idx,
                            "material": material}],
        })

    add_primitive(steel, 0)
    add_primitive(panel, 1)

    b64 = base64.b64encode(buffers_bin).decode("ascii")
    doc: Dict[str, Any] = {
        "asset": {"version": "2.0",
                  "generator": "LED STRUCTURE CAD (Python) — projeto somente para orçamento"},
        "scene": 0,
        "scenes": [{"nodes": [0, 1]}],
        "nodes": [
            {"name": f"{model.project.name} — estrutura", "mesh": 0},
            {"name": "PAINEL-LED", "mesh": 1},
        ],
        "meshes": meshes,
        "materials": [
            {"name": "AcoPintado", "pbrMetallicRoughness": {
                "baseColorFactor": [0.30, 0.34, 0.39, 1.0],
                "metallicFactor": 0.75, "roughnessFactor": 0.45}},
            {"name": "PainelLED", "pbrMetallicRoughness": {
                "baseColorFactor": [0.06, 0.55, 0.50, 1.0],
                "metallicFactor": 0.1, "roughnessFactor": 0.8}},
        ],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "buffers": [{"byteLength": len(buffers_bin),
                     "uri": "data:application/octet-stream;base64," + b64}],
    }
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
