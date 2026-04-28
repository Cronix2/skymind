"""Lecture clavier et conversion en positions de joysticks (mode 2 RC).

- Joystick GAUCHE : Y = gaz (Z/W = +, S = −, se tient), X = lacet (Q/D)
- Joystick DROIT  : Y = tangage (↑/↓), X = roulis (←/→)

Les axes non-throttle sont en réponse instantanée pour un pilotage réactif.
La sensibilité (courbe rate/expo) est appliquée *après* la lecture clavier
quand on appelle :func:`KeyboardController.shaped_sticks` — ce qui donne
au pilote (humain ou IA) un comportement type radiocommande.

Cette classe stocke aussi les profils de dynamique (masse, inertie,
délai moteur) — pas appliqués ici, mais consultés par main.py / play.py
au moment du reset.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import pygame

from . import config as C
from . import sensitivity as S
from . import dynamics as D


@dataclass
class Sticks:
    throttle: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0


class KeyboardController:
    def __init__(self, profile_name: str = S.DEFAULT_PROFILE,
                 mass_profile_name: str = D.DEFAULT_MASS,
                 nerv_profile_name: str = D.DEFAULT_NERV,
                 drag_profile_name: str = D.DEFAULT_DRAG):
        self.sticks = Sticks()
        self.request_reset = False
        self.request_quit = False
        self.fpv_pitch = 0.0  # rad — orientation verticale de la caméra FPV

        # Sensibilité courante
        self.profile_name: str = profile_name
        self.rate: float = 1.0
        self.expo: float = 0.4
        self.randomize_each_reset: bool = False
        self._set_from_profile(profile_name)

        # Dynamique courante : masse + nervosité + traînée (séparées)
        self.mass_profile_name: str = mass_profile_name
        self.nerv_profile_name: str = nerv_profile_name
        self.drag_profile_name: str = drag_profile_name
        self.mass: float = D.MASS_PROFILES[D.DEFAULT_MASS].mass
        self.nerv: D.NervProfile = D.NERV_PROFILES[D.DEFAULT_NERV]
        self.drag: D.DragProfile = D.DRAG_PROFILES[D.DEFAULT_DRAG]
        self.randomize_mass_each_reset: bool = False
        self.randomize_nerv_each_reset: bool = False
        self.randomize_drag_each_reset: bool = False
        self.set_mass_profile(mass_profile_name)
        self.set_nerv_profile(nerv_profile_name)
        self.set_drag_profile(drag_profile_name)

    # ------------------------------------------------------------------ profils sensi
    def _set_from_profile(self, name: str):
        if name == "Aléa":
            self.randomize_each_reset = True
            import random as _r
            self.rate, self.expo = S.sample_random(_r.Random())
        else:
            self.randomize_each_reset = False
            self.rate, self.expo = S.PROFILES.get(name, S.PROFILES[S.DEFAULT_PROFILE])
        self.profile_name = name

    def set_profile(self, name: str):
        self._set_from_profile(name)

    def randomize_sensitivity(self, rng=None):
        import random as _r
        rng = rng or _r.Random()
        self.rate, self.expo = S.sample_random(rng)

    # ------------------------------------------------------------------ profils dynamique
    def set_mass_profile(self, name: str):
        if name == "Aléa":
            self.randomize_mass_each_reset = True
            import random as _r
            self.mass = D.sample_random_mass(_r.Random())
        else:
            self.randomize_mass_each_reset = False
            self.mass = D.MASS_PROFILES.get(name, D.MASS_PROFILES[D.DEFAULT_MASS]).mass
        self.mass_profile_name = name

    def set_nerv_profile(self, name: str):
        if name == "Aléa":
            self.randomize_nerv_each_reset = True
            import random as _r
            self.nerv = D.sample_random_nerv(_r.Random())
        else:
            self.randomize_nerv_each_reset = False
            self.nerv = D.NERV_PROFILES.get(name, D.NERV_PROFILES[D.DEFAULT_NERV])
        self.nerv_profile_name = name

    def randomize_mass(self, rng=None):
        import random as _r
        rng = rng or _r.Random()
        self.mass = D.sample_random_mass(rng)

    def randomize_nerv(self, rng=None):
        import random as _r
        rng = rng or _r.Random()
        self.nerv = D.sample_random_nerv(rng)

    def set_drag_profile(self, name: str):
        if name == "Aléa":
            self.randomize_drag_each_reset = True
            import random as _r
            self.drag = D.sample_random_drag(_r.Random())
        else:
            self.randomize_drag_each_reset = False
            self.drag = D.DRAG_PROFILES.get(name, D.DRAG_PROFILES[D.DEFAULT_DRAG])
        self.drag_profile_name = name

    def randomize_drag(self, rng=None):
        import random as _r
        rng = rng or _r.Random()
        self.drag = D.sample_random_drag(rng)

    @property
    def dyn_params(self) -> D.DynamicsParams:
        return D.make_params(self.mass, self.nerv, self.drag)

    # ------------------------------------------------------------------ events
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.request_quit = True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.request_quit = True
            elif event.key == pygame.K_r:
                self.request_reset = True

    # ------------------------------------------------------------------ update
    def update(self, dt: float):
        keys = pygame.key.get_pressed()

        thr = self.sticks.throttle
        if keys[pygame.K_z] or keys[pygame.K_w]:
            thr = min(1.0, thr + dt * C.THROTTLE_UP_RATE)
        if keys[pygame.K_s]:
            thr = max(0.0, thr - dt * C.THROTTLE_DN_RATE)
        self.sticks.throttle = thr

        yaw_t = (-1.0 if keys[pygame.K_q] else 0.0) + (1.0 if keys[pygame.K_d] else 0.0)
        pitch_t = (1.0 if keys[pygame.K_UP] else 0.0) + (-1.0 if keys[pygame.K_DOWN] else 0.0)
        roll_t = (-1.0 if keys[pygame.K_LEFT] else 0.0) + (1.0 if keys[pygame.K_RIGHT] else 0.0)
        k = min(1.0, C.STICK_RATE * dt)
        self.sticks.yaw += (yaw_t - self.sticks.yaw) * k
        self.sticks.pitch += (pitch_t - self.sticks.pitch) * k
        self.sticks.roll += (roll_t - self.sticks.roll) * k

        dz = C.STICK_DEADZONE
        for attr in ("yaw", "pitch", "roll"):
            v = getattr(self.sticks, attr)
            if abs(v) < dz:
                setattr(self.sticks, attr, 0.0)

        if keys[pygame.K_i]:
            self.fpv_pitch = min(C.FPV_PITCH_MAX, self.fpv_pitch + C.FPV_PITCH_RATE * dt)
        if keys[pygame.K_k]:
            self.fpv_pitch = max(C.FPV_PITCH_MIN, self.fpv_pitch - C.FPV_PITCH_RATE * dt)
        if keys[pygame.K_j]:
            self.fpv_pitch *= max(0.0, 1.0 - 5.0 * dt)
        return self.sticks

    # ------------------------------------------------------------------ shaping
    def shaped_sticks(self) -> Sticks:
        """Sticks après application de la courbe rate/expo
        (sur roll, pitch, yaw uniquement — le throttle reste linéaire)."""
        return replace(
            self.sticks,
            roll=S.apply_curve(self.sticks.roll, self.rate, self.expo),
            pitch=S.apply_curve(self.sticks.pitch, self.rate, self.expo),
            yaw=S.apply_curve(self.sticks.yaw, self.rate, self.expo),
        )
