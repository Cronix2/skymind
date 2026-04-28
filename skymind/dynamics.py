"""Profils de paramètres dynamiques du drone.

Deux axes **indépendants** :

- **Masse** (`MassProfile`)        : combien le drone pèse.
- **Nervosité** (`NervProfile`)    : à quel point il réagit vite — combinaison
  de l'inertie et du délai moteur. Un drone "mou" a plus d'inertie et un délai
  moteur plus long ; un drone "nerveux" a moins d'inertie et un délai court.

Les deux profils sont combinés en :class:`DynamicsParams` (le format que le
moteur physique consomme).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config as C


# ============================================================ DynamicsParams
@dataclass(frozen=True)
class DynamicsParams:
    mass: float
    ixx: float
    iyy: float
    izz: float
    motor_tc: float
    drag_lin: float = 0.05
    drag_ang: float = 0.20


# ============================================================ Masse
@dataclass(frozen=True)
class MassProfile:
    name: str
    mass: float


MASS_LEGER    = MassProfile("Léger",    0.35)
MASS_STANDARD = MassProfile("Standard", 0.50)
MASS_LOURD    = MassProfile("Lourd",    0.75)

MASS_PROFILES: dict[str, MassProfile] = {
    "Léger":    MASS_LEGER,
    "Standard": MASS_STANDARD,
    "Lourd":    MASS_LOURD,
}
DEFAULT_MASS = "Standard"
MASS_RANGE = (0.30, 0.80)


def sample_random_mass(rng) -> float:
    return float(rng.uniform(*MASS_RANGE))


def normalized_mass(mass: float) -> float:
    lo, hi = MASS_RANGE
    mid = 0.5 * (lo + hi)
    span = max(0.5 * (hi - lo), 1e-9)
    return (mass - mid) / span


# ============================================================ Nervosité
@dataclass(frozen=True)
class NervProfile:
    name: str
    ixx: float
    iyy: float
    izz: float
    motor_tc: float


# ixx/iyy : inertie sur les axes "horizontaux" (roll/pitch) — celle qui
# détermine la réactivité tangage/roulis.
# izz : inertie en lacet.
# motor_tc : constante de temps 1er ordre des moteurs (s).
NERV_MOU     = NervProfile("Mou",     ixx=3.0e-3, iyy=3.0e-3, izz=5.2e-3, motor_tc=0.055)
NERV_NORMAL  = NervProfile("Normal",  ixx=2.3e-3, iyy=2.3e-3, izz=4.0e-3, motor_tc=0.025)
NERV_NERVEUX = NervProfile("Nerveux", ixx=1.7e-3, iyy=1.7e-3, izz=3.0e-3, motor_tc=0.012)

NERV_PROFILES: dict[str, NervProfile] = {
    "Mou":     NERV_MOU,
    "Normal":  NERV_NORMAL,
    "Nerveux": NERV_NERVEUX,
}
DEFAULT_NERV = "Normal"

# Plages pour l'aléa
INERTIA_XY_RANGE = (1.4e-3, 3.4e-3)
INERTIA_Z_RANGE  = (2.4e-3, 6.0e-3)
MOTOR_TC_RANGE   = (0.010, 0.060)


# ============================================================ Traînée (frottements de l'air)
@dataclass(frozen=True)
class DragProfile:
    name: str
    drag_lin: float    # linearDamping pybullet (0 = sans frottement)
    drag_ang: float    # angularDamping pybullet


DRAG_FAIBLE  = DragProfile("Faible",  drag_lin=0.02, drag_ang=0.10)
DRAG_MOYENNE = DragProfile("Moyenne", drag_lin=0.05, drag_ang=0.20)
DRAG_FORTE   = DragProfile("Forte",   drag_lin=0.12, drag_ang=0.40)

DRAG_PROFILES: dict[str, DragProfile] = {
    "Faible":  DRAG_FAIBLE,
    "Moyenne": DRAG_MOYENNE,
    "Forte":   DRAG_FORTE,
}
DEFAULT_DRAG = "Moyenne"

DRAG_LIN_RANGE = (0.00, 0.20)
DRAG_ANG_RANGE = (0.00, 0.60)


def sample_random_drag(rng) -> DragProfile:
    return DragProfile(
        name="Aléa",
        drag_lin=float(rng.uniform(*DRAG_LIN_RANGE)),
        drag_ang=float(rng.uniform(*DRAG_ANG_RANGE)),
    )


def sample_random_nerv(rng) -> NervProfile:
    return NervProfile(
        name="Aléa",
        ixx=float(rng.uniform(*INERTIA_XY_RANGE)),
        iyy=float(rng.uniform(*INERTIA_XY_RANGE)),
        izz=float(rng.uniform(*INERTIA_Z_RANGE)),
        motor_tc=float(rng.uniform(*MOTOR_TC_RANGE)),
    )


def _norm(v: float, lo: float, hi: float) -> float:
    mid = 0.5 * (lo + hi)
    span = max(0.5 * (hi - lo), 1e-9)
    return (v - mid) / span


def normalized_nerv(nerv: NervProfile) -> tuple[float, float, float]:
    """Retourne (ixy, iz, tc) normalisés ~ [-1, 1]."""
    ixy = 0.5 * (nerv.ixx + nerv.iyy)
    return (
        _norm(ixy, *INERTIA_XY_RANGE),
        _norm(nerv.izz, *INERTIA_Z_RANGE),
        _norm(nerv.motor_tc, *MOTOR_TC_RANGE),
    )


# ============================================================ Combinaison
def make_params(mass: float, nerv: NervProfile,
                drag: DragProfile | None = None) -> DynamicsParams:
    drag = drag if drag is not None else DRAG_MOYENNE
    return DynamicsParams(
        mass=mass,
        ixx=nerv.ixx,
        iyy=nerv.iyy,
        izz=nerv.izz,
        motor_tc=nerv.motor_tc,
        drag_lin=drag.drag_lin,
        drag_ang=drag.drag_ang,
    )


def normalized(params: DynamicsParams) -> tuple[float, float, float, float]:
    """Retourne (mass_n, ixy_n, iz_n, tc_n) normalisés ~ [-1, 1]."""
    ixy = 0.5 * (params.ixx + params.iyy)
    return (
        normalized_mass(params.mass),
        _norm(ixy, *INERTIA_XY_RANGE),
        _norm(params.izz, *INERTIA_Z_RANGE),
        _norm(params.motor_tc, *MOTOR_TC_RANGE),
    )


# ============================================================ Compat / défaut
STANDARD = make_params(MASS_STANDARD.mass, NERV_NORMAL, DRAG_MOYENNE)


def sample_random(rng) -> DynamicsParams:
    """Tirage entièrement aléatoire (masse + nervosité + traînée)."""
    return make_params(
        sample_random_mass(rng),
        sample_random_nerv(rng),
        sample_random_drag(rng),
    )
