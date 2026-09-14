"""Catálogo de perfis metálicos.

Cada perfil é reutilizável e conhecido pelo nome (ex.: METALON_60x60x2).
A geometria interna trabalha sempre em MILÍMETROS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class Profile:
    """Perfil laminado/tubular para barras.

    kind: "square" (metalon quadrado/retangular) ou "round" (tubo circular).
    Para perfis "square": w = largura (X), h = altura (Y) da seção.
    Para perfis "round": d = diâmetro externo (w = h = d).
    kgm: peso linear estimado em kg/m (referências: lista de materiais do
    projeto de orçamento LED EXPERT 222-2023-11-FL01).
    """

    name: str
    kind: str  # "square" | "round"
    w: float
    h: float
    t: float  # espessura (mm)
    kgm: float  # kg/m
    description: str = ""

    @property
    def label(self) -> str:
        if self.description:
            return self.description
        if self.kind == "round":
            return f"TUBO \u00d8{self.w:.0f} x {self.t:.1f}mm"
        return f"METALON {self.w:.0f}x{self.h:.0f} x {self.t:.1f}mm"


def _round(name: str, d: float, t: float, kgm: float) -> Profile:
    return Profile(name=name, kind="round", w=d, h=d, t=t, kgm=kgm,
                   description=f"TUBO \u00d8{d:.0f} x {t:.1f}mm")


CATALOG: Dict[str, Profile] = {
    p.name: p
    for p in [
        Profile("METALON_20x20x1.2", "square", 20, 20, 1.2, 0.67),
        Profile("METALON_25x25x1.5", "square", 25, 25, 1.5, 1.06),
        Profile("METALON_30x30x1.5", "square", 30, 30, 1.5, 1.28),
        Profile("METALON_40x40x2", "square", 40, 40, 2.0, 2.41),
        Profile("METALON_50x50x2", "square", 50, 50, 2.0, 2.89),
        Profile("METALON_60x60x2", "square", 60, 60, 2.0, 3.66),
        Profile("METALON_80x80x3", "square", 80, 80, 3.0, 7.13),
        Profile("METALON_100x100x3", "square", 100, 100, 3.0, 8.96),
        Profile("METALON_120x120x3", "square", 120, 120, 3.0, 10.83),
        Profile("METALON_150x150x4.75", "square", 150, 150, 4.75, 21.04),
        _round("TUBO_76x3.2", 76.0, 3.2, 5.72),
        _round("TUBO_114x3.75", 114.0, 3.75, 10.22),
        _round("TUBO_168x4.75", 168.0, 4.75, 19.06),
        _round("TUBO_219x4.75", 219.0, 4.75, 25.08),
        _round("TUBO_273x4.75", 273.0, 4.75, 31.45),
        _round("TUBO_380_t4.8", 380.0, 4.8, 44.63),
    ]
}

DEFAULT_PROFILE = "METALON_40x40x2"


def get_profile(name: str) -> Profile:
    """Retorna o perfil pelo nome; lança erro clara se não existir."""
    if name in CATALOG:
        return CATALOG[name]
    raise KeyError(
        f"Perfil '{name}' não existe no catálogo. Disponíveis: {', '.join(CATALOG)}"
    )


def profile_names() -> list[str]:
    return list(CATALOG.keys())
