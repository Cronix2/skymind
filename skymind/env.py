"""Environnement Gymnasium pour Skymind.

Observation (18D) :
    [rel_target_body(3), vel_body(3), gyro(3), gravity_body(3),
     motor_cmd(4), sens_rate_norm(1), sens_expo_norm(1)]

Action : Box [-1, 1]^4 = (roll, pitch, yaw, throttle_raw).
- Le throttle est remappé en [0, 1].
- (roll, pitch, yaw) passent par la courbe de sensibilité (rate, expo)
  tirée aléatoirement à chaque épisode pour entraîner l'IA à pilotes
  des "réglages stick" différents (domain randomization). L'IA voit
  rate/expo dans son observation.

Crash :
- Impact mur : pénalité fixe + pénalité ∝ vitesse, *moteurs coupés
  définitivement* pour le reste de l'épisode (tombe au sol).
- Sol à l'envers : grosse pénalité, fin d'épisode.
- Sol doux et à l'endroit : pas de pénalité.
- Sol violent : pénalité ∝ excès de vitesse au-delà du seuil doux.
"""
from __future__ import annotations

import random
from typing import Optional

import numpy as np
import pybullet as p

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "gymnasium n'est pas installé. Lance ./deploy.sh."
    ) from e

from . import config as C
from . import sensitivity as S
from . import dynamics as D
from .arena import build_box, random_target_pos
from .drone import Drone


OBS_CLIP = 50.0
OBS_DIM = 22


class SkymindEnv(gym.Env):
    metadata = {"render_modes": []}

    EP_DURATION_S = 15.0
    REWARD_REACH = 100.0
    DIST_PENALTY_COEF = 1.0
    SHAPING_COEF = 5.0
    ACTION_RATE_PENALTY = 0.005

    def __init__(self, seed: Optional[int] = None, control_hz: int = C.RENDER_HZ,
                 randomize_sensitivity: bool = True,
                 randomize_mass: bool = True,
                 randomize_nerv: bool = True,
                 randomize_drag: bool = True,
                 arena_dims: Optional[tuple[float, float, float]] = None):
        super().__init__()
        self._client_id: Optional[int] = None
        self.control_hz = int(control_hz)
        self.physics_substeps = max(1, C.SIM_HZ // self.control_hz)
        self.dt = 1.0 / self.control_hz
        self.max_steps = int(self.EP_DURATION_S * self.control_hz)
        self.randomize_sensitivity = randomize_sensitivity
        self.randomize_mass = randomize_mass
        self.randomize_nerv = randomize_nerv
        self.randomize_drag = randomize_drag
        self.arena_dims = tuple(arena_dims) if arena_dims is not None else None

        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(4,), dtype=np.float32
        )
        self.observation_space = spaces.Box(
            low=-OBS_CLIP, high=OBS_CLIP, shape=(OBS_DIM,), dtype=np.float32
        )

        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)

        self._initialized = False
        self.drone: Optional[Drone] = None
        self.target_pos = np.zeros(3, dtype=np.float32)
        self._steps = 0
        self._prev_dist = 0.0
        self._prev_action = np.zeros(4, dtype=np.float32)

        # Sensibilité courante (épisode)
        self.sens_rate = 1.0
        self.sens_expo = 0.4

        # Dynamique courante (épisode)
        self.dyn_params: D.DynamicsParams = D.STANDARD

        # Crash state
        self._wall_hit_logged = False  # garde-fou pour ne payer la fixed penalty qu'une fois
        self._wall_ids: list[int] = []
        self._floor_id: int = -1
        self._ceiling_id: int = -1

    # ------------------------------------------------------------------ setup
    def _ensure_world(self):
        if self._initialized:
            return
        self._client_id = p.connect(p.DIRECT)
        p.setGravity(0, 0, -C.GRAVITY, physicsClientId=self._client_id)
        p.setTimeStep(C.TIMESTEP, physicsClientId=self._client_id)
        p.setRealTimeSimulation(0, physicsClientId=self._client_id)
        ids = build_box(self.arena_dims)
        # build_box renvoie [floor, ceiling, +X, -X, +Y, -Y]
        self._floor_id = ids[0]
        self._ceiling_id = ids[1]
        self._wall_ids = list(ids[2:])  # 4 murs verticaux + on inclura le plafond
        self.drone = Drone(start_pos=(0.0, 0.0, 1.2))
        self._initialized = True

    def close(self):
        if self._client_id is not None and p.isConnected(self._client_id):
            p.disconnect(self._client_id)
        self._client_id = None
        self._initialized = False
        self.drone = None

    # ------------------------------------------------------------------ reset
    def reset(self, *, seed: Optional[int] = None, options=None):
        if seed is not None:
            self.rng = random.Random(seed)
            self.np_rng = np.random.default_rng(seed)
        self._ensure_world()
        assert self.drone is not None

        x0 = self.np_rng.uniform(-0.5, 0.5)
        y0 = self.np_rng.uniform(-0.5, 0.5)
        z0 = self.np_rng.uniform(0.8, 1.6)
        p.resetBasePositionAndOrientation(
            self.drone.body_id, [x0, y0, z0], [0, 0, 0, 1],
            physicsClientId=self._client_id,
        )
        p.resetBaseVelocity(
            self.drone.body_id, [0, 0, 0], [0, 0, 0],
            physicsClientId=self._client_id,
        )
        self.drone._motor_target[:] = 0.0
        self.drone.motor_cmd[:] = 0.0
        self.drone._prev_lin_vel[:] = 0.0
        self.drone.motors_disabled = False

        # Sensibilité aléatoire pour cet épisode
        if self.randomize_sensitivity:
            self.sens_rate, self.sens_expo = S.sample_random(self.rng)
        else:
            self.sens_rate, self.sens_expo = S.PROFILES[S.DEFAULT_PROFILE]

        # Dynamique aléatoire pour cet épisode (masse + nervosité + traînée indépendantes)
        if self.randomize_mass:
            mass = D.sample_random_mass(self.rng)
        else:
            mass = D.MASS_PROFILES[D.DEFAULT_MASS].mass
        if self.randomize_nerv:
            nerv = D.sample_random_nerv(self.rng)
        else:
            nerv = D.NERV_PROFILES[D.DEFAULT_NERV]
        if self.randomize_drag:
            drag = D.sample_random_drag(self.rng)
        else:
            drag = D.DRAG_PROFILES[D.DEFAULT_DRAG]
        self.dyn_params = D.make_params(mass, nerv, drag)
        self.drone.apply_dynamics(self.dyn_params)

        self.target_pos = np.array(random_target_pos(self.rng, self.arena_dims), dtype=np.float32)
        self._steps = 0
        self._prev_action[:] = 0.0
        self._wall_hit_logged = False
        state = self.drone.get_state()
        self._prev_dist = float(np.linalg.norm(state["pos"] - self.target_pos))

        obs = self._build_obs(state)
        info = {
            "target": self.target_pos.copy(),
            "sens_rate": self.sens_rate,
            "sens_expo": self.sens_expo,
            "dyn": self.dyn_params,
        }
        return obs, info

    # ------------------------------------------------------------------ step
    def step(self, action):
        assert self.drone is not None
        action = np.asarray(action, dtype=np.float32).reshape(4)
        action = np.clip(action, -1.0, 1.0)

        roll, pitch, yaw, thr_raw = action
        # Throttle : linéaire [-1,1] -> [0,1]
        throttle = float((thr_raw + 1.0) * 0.5)
        # Roll/pitch/yaw : passent par la courbe de sensibilité de l'épisode
        roll_s = float(S.apply_curve(float(roll), self.sens_rate, self.sens_expo))
        pitch_s = float(S.apply_curve(float(pitch), self.sens_rate, self.sens_expo))
        yaw_s = float(S.apply_curve(float(yaw), self.sens_rate, self.sens_expo))
        # set_command clippera à ±1
        self.drone.set_command(throttle=throttle, roll=roll_s,
                               pitch=pitch_s, yaw=yaw_s)

        # ----------- physique
        for _ in range(self.physics_substeps):
            self.drone.apply_forces()
            p.stepSimulation(physicsClientId=self._client_id)

        state = self.drone.get_state()
        pos = state["pos"]
        vel = state["lin_vel"]
        speed = float(np.linalg.norm(vel))
        dist = float(np.linalg.norm(pos - self.target_pos))

        # ----------- reward dense
        reward = -self.DIST_PENALTY_COEF * dist * self.dt
        reward += self.SHAPING_COEF * (self._prev_dist - dist)
        reward -= self.ACTION_RATE_PENALTY * float(
            np.sum((action - self._prev_action) ** 2)
        )
        self._prev_dist = dist
        self._prev_action = action

        terminated = False
        truncated = False
        success = (not self.drone.motors_disabled) and dist < C.TARGET_REACH_DIST
        info_extra = {}

        if success:
            reward += self.REWARD_REACH
            reward += 2.0 * (self.max_steps - self._steps) * self.dt
            terminated = True

        # ----------- contacts
        if not terminated:
            contacts = p.getContactPoints(
                bodyA=self.drone.body_id, physicsClientId=self._client_id
            )
            wall_hit = False
            floor_hit = False
            ceiling_hit = False
            for c in contacts:
                other = c[2]
                if other == self._floor_id:
                    floor_hit = True
                elif other == self._ceiling_id:
                    ceiling_hit = True
                elif other in self._wall_ids:
                    wall_hit = True

            # Mur ou plafond : coupure moteurs + pénalité
            if (wall_hit or ceiling_hit) and not self._wall_hit_logged:
                self._wall_hit_logged = True
                reward -= C.WALL_HIT_FLAT_PENALTY
                reward -= C.WALL_HIT_SPEED_PENALTY * speed
                self.drone.disable_motors()
                info_extra["wall_hit_speed"] = speed

            # Sol : selon orientation et vitesse
            if floor_hit:
                # Z du drone exprimé dans le repère monde, composante Z monde
                up_dot = float(state["rot"][2, 2])  # cos(theta) entre Z drone et Z monde
                inverted = up_dot <= C.INVERTED_DOT_THRESHOLD
                if inverted:
                    reward -= C.GROUND_INVERTED_PENALTY
                    info_extra["floor_inverted"] = True
                    terminated = True
                else:
                    excess = max(0.0, speed - C.GROUND_SOFT_LANDING_SPEED)
                    if excess > 0.0:
                        reward -= C.GROUND_HARD_LANDING_COEF * excess
                        info_extra["floor_hard_landing_speed"] = speed
                    # Atterrissage doux à l'endroit : pas de pénalité
                    # On termine si moteurs coupés ET drone quasi immobile
                    if self.drone.motors_disabled and speed < C.SETTLED_SPEED:
                        terminated = True

        self._steps += 1
        if not terminated and self._steps >= self.max_steps:
            truncated = True

        obs = self._build_obs(state)
        info = {
            "dist": dist,
            "success": success,
            "speed": speed,
            "target": self.target_pos.copy(),
            "pos": pos.copy(),
            "sens_rate": self.sens_rate,
            "sens_expo": self.sens_expo,
            "dyn": self.dyn_params,
            "motors_disabled": self.drone.motors_disabled,
            **info_extra,
        }
        return obs, float(reward), terminated, truncated, info

    # ------------------------------------------------------------------ obs
    def _build_obs(self, state) -> np.ndarray:
        rot = state["rot"]
        pos = state["pos"]
        rel_world = self.target_pos - pos
        rel_body = rot.T @ rel_world
        vel_body = rot.T @ state["lin_vel"]
        gyro = state["gyro_body"]
        gravity_world = np.array([0.0, 0.0, -1.0])
        gravity_body = rot.T @ gravity_world
        motors = state["motor_cmd"]
        rate_n, expo_n = S.normalized(self.sens_rate, self.sens_expo)
        m_n, ixy_n, iz_n, tc_n = D.normalized(self.dyn_params)

        obs = np.concatenate([
            rel_body / (self._half_diag()),
            vel_body / 5.0,
            gyro / 6.0,
            gravity_body,
            motors,
            np.array([rate_n, expo_n,
                      m_n, ixy_n, iz_n, tc_n], dtype=np.float32),
        ]).astype(np.float32)
        return np.clip(obs, -OBS_CLIP, OBS_CLIP)

    def _half_diag(self) -> float:
        from .arena import get_dims
        bx, by, bz = get_dims(self.arena_dims)
        return 0.5 * float(np.linalg.norm([bx, by, bz]))


def build_obs_external(state, target_pos, sens_rate: float, sens_expo: float,
                       dyn_params: D.DynamicsParams,
                       arena_dims=None) -> np.ndarray:
    """Construit une observation au format `SkymindEnv` depuis l'extérieur
    (utilisé par play.py)."""
    from .arena import get_dims
    bx, by, bz = get_dims(arena_dims)
    half_diag = 0.5 * float(np.linalg.norm([bx, by, bz]))
    rot = state["rot"]
    rel_world = target_pos - state["pos"]
    rel_body = rot.T @ rel_world
    vel_body = rot.T @ state["lin_vel"]
    gyro = state["gyro_body"]
    grav_body = rot.T @ np.array([0.0, 0.0, -1.0])
    rate_n, expo_n = S.normalized(sens_rate, sens_expo)
    m_n, ixy_n, iz_n, tc_n = D.normalized(dyn_params)
    obs = np.concatenate([
        rel_body / half_diag,
        vel_body / 5.0,
        gyro / 6.0,
        grav_body,
        state["motor_cmd"],
        np.array([rate_n, expo_n,
                  m_n, ixy_n, iz_n, tc_n], dtype=np.float32),
    ]).astype(np.float32)
    return np.clip(obs, -OBS_CLIP, OBS_CLIP)
