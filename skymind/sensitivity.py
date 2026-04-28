"""Profils et courbe de sensibilité des joysticks (rate / expo).

Modélisation type radiocommande : l'entrée stick `x ∈ [-1, 1]` est
transformée en sortie pilote `y` selon

    y = sign(x) * rate * ((1 - expo) * |x| + expo * |x|^3)

- `rate` ∈ [0.5, 2.0] : gain global. >1 = stick plus mordant
  (saturation rapide), <1 = stick plus mou.
- `expo` ∈ [0, 1] : courbure. 0 = réponse linéaire,
  1 = très progressif autour du centre puis brutal en bout de course.

La sortie peut excéder 1 si rate > 1 ; le drone clippe à ±1 ensuite,
ce qui imite le comportement d'un vrai RC où des rates élevés font
saturer la commande avant la fin de la course.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np


# (rate, expo) — du plus doux au plus sportif
PROFILES: dict[str, Tuple[float, float]] = {
    "Doux":   (0.6, 0.7),
    "Normal": (1.0, 0.4),
    "Sport":  (1.4, 0.2),
    "Acro":   (1.8, 0.0),
}

DEFAULT_PROFILE = "Normal"

# Plages de randomisation pour l'entraînement IA
RATE_RANGE = (0.5, 1.8)
EXPO_RANGE = (0.0, 0.8)


def apply_curve(x: float, rate: float, expo: float) -> float:
    """Applique la courbe rate/expo à une valeur de stick scalaire."""
    x = float(np.clip(x, -1.0, 1.0))
    s = 1.0 if x >= 0.0 else -1.0
    a = abs(x)
    return s * rate * ((1.0 - expo) * a + expo * a * a * a)


def apply_curve_array(arr: np.ndarray, rate: float, expo: float) -> np.ndarray:
    a = np.clip(arr, -1.0, 1.0)
    s = np.sign(a)
    aa = np.abs(a)
    return s * rate * ((1.0 - expo) * aa + expo * aa ** 3)


def sample_random(rng) -> Tuple[float, float]:
    """Tire (rate, expo) aléatoires dans les plages d'entraînement."""
    return (
        float(rng.uniform(*RATE_RANGE)),
        float(rng.uniform(*EXPO_RANGE)),
    )


def normalized(rate: float, expo: float) -> Tuple[float, float]:
    """Mappe (rate, expo) en ~[-1, 1] pour servir d'entrée à un réseau."""
    rmid = 0.5 * (RATE_RANGE[0] + RATE_RANGE[1])
    rspan = 0.5 * (RATE_RANGE[1] - RATE_RANGE[0])
    emid = 0.5 * (EXPO_RANGE[0] + EXPO_RANGE[1])
    espan = 0.5 * (EXPO_RANGE[1] - EXPO_RANGE[0])
    return ((rate - rmid) / max(rspan, 1e-6), (expo - emid) / max(espan, 1e-6))
