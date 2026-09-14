"""Modelos de elementos estruturais (Pydantic).

Todo elemento tem ID estável e semântica (ex.: POSTE-01, V01, D03).
Coordenadas em MILÍMETROS; sistema: X=largura, Y=profundidade, Z=altura,
origem no solo, centro da estrutura em X=0, Y=0.
"""
from __future__ import annotations

import math
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

ElementRole = Literal[
    "vertical", "horizontal", "trave", "diagonal", "post",
    "plate", "base", "bolt", "panel", "other",
]
ElementType = Literal["beam", "plate", "bolt", "panel"]


class Vec3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(x=self.x + other.x, y=self.y + other.y, z=self.z + other.z)


class Element(BaseModel):
    """Elemento estrutural semântico.

    - beam: barra definida por START e END + perfil (funciona para poste,
      travessa, diagonal, quadro...). O engine calcula comprimento/orientação.
    - plate: chapa retangular (base, ligação) por centro + dimensões.
    - bolt: chumbador/pino (cilindro) por start/end.
    - panel: superfície do painel de LED (referência visual, não estrutural).
    """

    id: str = Field(min_length=1)
    type: ElementType = "beam"
    role: ElementRole = "other"
    profile: Optional[str] = None
    start: Optional[Vec3] = None
    end: Optional[Vec3] = None
    # para plates:
    center: Optional[Vec3] = None
    size_x: float = 0.0
    size_y: float = 0.0
    size_z: float = 0.0  # espessura vertical da chapa
    label: str = ""
    group: str = ""  # ex.: "QUADRO", "POSTES", "CONTRAVENTAMENTO"
    # abrigo de vento marcado pelo usuário: o elemento projetado na direção
    # do vento SOMBREA o painel (reduz a força sobre ele) — ver core/wind.py
    shield: bool = False

    @field_validator("id")
    @classmethod
    def _id_upper(cls, v: str) -> str:
        return v.strip().upper()

    # ------- utilitários geométricos -------
    def length(self) -> float:
        if self.type in ("beam", "bolt") and self.start and self.end:
            s, e = self.start.as_tuple(), self.end.as_tuple()
            return math.dist(s, e)
        return 0.0

    def is_circular(self) -> bool:
        return self.type in ("beam", "bolt") and self.profile and (
            "TUBO" in (self.profile or "") or self.type == "bolt"
        )


class Panel(BaseModel):
    """Painel de LED (dimensões nominais)."""

    width: float = 4000.0
    height: float = 2000.0
    depth: float = 800.0


class Installation(BaseModel):
    """Condições de instalação."""

    type: Literal["post", "wall", "suspended", "rental"] = "post"
    posts: int = 1
    ground_clearance: float = 3000.0  # face inferior do painel em relação ao solo
    environment: Literal["outdoor", "indoor"] = "outdoor"

    @field_validator("posts", mode="before")
    @classmethod
    def _posts_none_ok(cls, v):
        """Preset 'parede' não tem postes: None/NaN → 0 (sem suportes ao solo)."""
        if v is None:
            return 0
        if isinstance(v, float) and v != v:  # NaN
            return 0
        return v


class ProjectMeta(BaseModel):
    name: str = "Painel LED"
    client: str = ""
    units: Literal["mm"] = "mm"


class ProjectModel(BaseModel):
    """Modelo canônico do projeto (JSON é a autoridade)."""

    project: ProjectMeta = Field(default_factory=ProjectMeta)
    panel: Panel = Field(default_factory=Panel)
    installation: Installation = Field(default_factory=Installation)
    elements: List[Element] = Field(default_factory=list)
    preset_id: str = ""
    revisions: List[str] = Field(default_factory=list)

    def index(self) -> dict[str, Element]:
        return {e.id: e for e in self.elements}

    def next_id(self, prefix: str) -> str:
        """Gera próximo ID estável para o prefixo (V -> V06, D -> D12...)."""
        n = 1
        used = {e.id for e in self.elements}
        while f"{prefix}{n:02d}" in used:
            n += 1
        return f"{prefix}{n:02d}"
