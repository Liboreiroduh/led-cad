"""Núcleo geométrico: vetores, AABB e utilidades em milímetros."""
from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

Pt3 = Tuple[float, float, float]


def add(a: Pt3, b: Pt3) -> Pt3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Pt3, b: Pt3) -> Pt3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Pt3, k: float) -> Pt3:
    return (a[0] * k, a[1] * k, a[2] * k)


def dist(a: Pt3, b: Pt3) -> float:
    return math.dist(a, b)


def midpoint(a: Pt3, b: Pt3) -> Pt3:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)


def normalize(v: Pt3) -> Pt3:
    n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


class AABB:
    """Caixa envolvente alinhada aos eixos (mm)."""

    def __init__(self) -> None:
        self.min: Pt3 = (math.inf, math.inf, math.inf)
        self.max: Pt3 = (-math.inf, -math.inf, -math.inf)

    def add_point(self, p: Pt3) -> None:
        self.min = tuple(min(a, b) for a, b in zip(self.min, p))  # type: ignore
        self.max = tuple(max(a, b) for a, b in zip(self.max, p))  # type: ignore

    def add_points(self, pts: Iterable[Pt3]) -> None:
        for p in pts:
            self.add_point(p)

    def add_aabb(self, other: "AABB") -> None:
        self.add_points([other.min, other.max])

    @property
    def valid(self) -> bool:
        return all(a <= b for a, b in zip(self.min, self.max))

    @property
    def size(self) -> Pt3:
        return sub(self.max, self.min)

    @property
    def center(self) -> Pt3:
        return midpoint(self.min, self.max)

    def padded(self, pad: float) -> "AABB":
        box = AABB()
        box.add_points([
            (self.min[0] - pad, self.min[1] - pad, self.min[2] - pad),
            (self.max[0] + pad, self.max[1] + pad, self.max[2] + pad),
        ])
        return box


def linspace(start: float, stop: float, n: int) -> List[float]:
    """n valores igualmente espaçados incluindo start e stop."""
    if n < 2:
        return [start]
    step = (stop - start) / (n - 1)
    return [start + i * step for i in range(n)]


def bbox_of_points(pts: Sequence[Pt3]) -> AABB:
    box = AABB()
    box.add_points(pts)
    return box
