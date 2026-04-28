"""Arène (collisions PyBullet seulement).

Les dimensions sont passées explicitement (X, Y, Z en mètres). Si non
fournies, lecture des valeurs courantes dans `settings.current`.
"""
from __future__ import annotations

import random
import pybullet as p

from . import config as C
from . import settings as S


def _create_wall_collider(half_extents, position):
    col = p.createCollisionShape(p.GEOM_BOX, halfExtents=half_extents)
    body = p.createMultiBody(
        baseMass=0.0,
        baseCollisionShapeIndex=col,
        baseVisualShapeIndex=-1,
        basePosition=position,
    )
    p.changeDynamics(body, -1, restitution=0.05, lateralFriction=0.9, spinningFriction=0.05)
    return body


def get_dims(dims=None) -> tuple[float, float, float]:
    if dims is not None:
        return tuple(dims)  # type: ignore[return-value]
    s = S.current
    return (s.arena_x, s.arena_y, s.arena_z)


def build_box(dims=None) -> list[int]:
    """Sol + 4 murs + plafond.

    `dims` : (X, Y, Z) en mètres. Sol en z=0, plafond en z=Z.
    """
    bx, by, bz = get_dims(dims)
    bodies: list[int] = []
    sx = bx / 2.0
    sy = by / 2.0
    sz = bz / 2.0
    t = C.BOX_WALL_THICK / 2.0

    # sol et plafond couvrent tout l'XY
    bodies.append(_create_wall_collider((sx, sy, t), (0, 0, -t)))                 # sol
    bodies.append(_create_wall_collider((sx, sy, t), (0, 0, bz + t)))             # plafond
    # murs sur ±X (épaisseur sur X, pleine largeur Y, pleine hauteur Z)
    bodies.append(_create_wall_collider((t, sy, sz), (sx + t, 0, sz)))            # +X
    bodies.append(_create_wall_collider((t, sy, sz), (-sx - t, 0, sz)))           # -X
    # murs sur ±Y
    bodies.append(_create_wall_collider((sx, t, sz), (0, sy + t, sz)))            # +Y
    bodies.append(_create_wall_collider((sx, t, sz), (0, -sy - t, sz)))           # -Y
    return bodies


def random_target_pos(rng: random.Random, dims=None) -> tuple[float, float, float]:
    bx, by, bz = get_dims(dims)
    margin = 0.7
    sx = bx / 2.0 - margin
    sy = by / 2.0 - margin
    return (
        rng.uniform(-sx, sx),
        rng.uniform(-sy, sy),
        rng.uniform(margin, bz - margin),
    )
