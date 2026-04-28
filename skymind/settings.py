"""Réglages globaux modifiables au runtime depuis le menu.

Tout ce que l'utilisateur peut régler dans le menu se trouve ici. Les autres
modules (`arena`, `env`, `main`, `play`, `train`…) lisent ces valeurs au
moment du démarrage de la simulation.

Pour les subprocess d'entraînement (chaque worker recharge le module Python
de zéro), on passe les valeurs explicitement via les `env_kwargs` de l'env.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config as C


# ============================================================ Réglages
@dataclass
class Settings:
    # --- Arène (m) ---
    arena_x: float = C.BOX_SIZE   # longueur (axe X)
    arena_y: float = C.BOX_SIZE   # largeur  (axe Y)
    arena_z: float = C.BOX_SIZE   # hauteur  (axe Z)

    # --- Profils drone ---
    mass_profile: str = "Standard"     # "Léger" / "Standard" / "Lourd" / "Aléa"
    nerv_profile: str = "Normal"       # "Mou" / "Normal" / "Nerveux" / "Aléa"
    drag_profile: str = "Moyenne"      # "Faible" / "Moyenne" / "Forte" / "Aléa"
    sens_profile: str = "Normal"       # "Doux" / "Normal" / "Sport" / "Acro" / "Aléa"

    # --- Entraînement ---
    train_steps: int = 1_000_000
    train_n_envs: int = 4
    train_auto_resume: bool = True
    train_seed: int = 42
    train_lr: float = 3e-4
    # Domain randomization (utilisé seulement à l'entraînement)
    train_random_mass: bool = True
    train_random_nerv: bool = True
    train_random_drag: bool = True
    train_random_sens: bool = True

    # --- Lecture IA ---
    play_model_path: str = "runs/skymind_ppo.zip"


# Singleton global mis à jour par le menu.
current: Settings = Settings()


def reset():
    global current
    current = Settings()
