"""Lance la simulation pygame en laissant un modèle PPO piloter le drone.

Lancement direct :
    python -m skymind.play
ou via le menu : :mod:`skymind.app`.
"""
from __future__ import annotations

import argparse
import os
import random
import time
from pathlib import Path

import numpy as np
import pygame
import pybullet as p

try:
    from stable_baselines3 import PPO
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "stable-baselines3 n'est pas installé. Lance ./deploy.sh."
    ) from e

from . import config as C
from . import settings as Stt
from . import sensitivity as S
from .arena import build_box, random_target_pos
from .controls import KeyboardController, Sticks
from .drone import Drone
from .env import build_obs_external
from .hud import HUDOverlay
from .renderer import Renderer3D, draw_box, draw_target, draw_drone


def _cam_for_arena(st: Stt.Settings) -> tuple[np.ndarray, np.ndarray]:
    eye = np.array([-st.arena_x * 0.95, -st.arena_y * 0.95, st.arena_z * 1.20])
    target = np.array([0.0, 0.0, st.arena_z * 0.40])
    return eye, target


def run(st: Stt.Settings | None = None):
    if st is None:
        st = Stt.current
    else:
        Stt.current = st

    model_path = Path(st.play_model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Modèle introuvable : {model_path}.")
    model = PPO.load(str(model_path), device="cpu")
    print(f"[play] modèle chargé : {model_path}")

    os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
    pygame.init()
    pygame.display.set_caption(f"Skymind — IA {C.DRONE_NAME}")
    screen = pygame.display.set_mode((C.WINDOW_W, C.WINDOW_H))

    p.connect(p.DIRECT)
    p.setGravity(0, 0, -C.GRAVITY)
    p.setTimeStep(C.TIMESTEP)
    arena_dims = (st.arena_x, st.arena_y, st.arena_z)
    arena_ids = build_box(arena_dims)
    floor_id = arena_ids[0]
    ceiling_id = arena_ids[1]
    side_walls = set(arena_ids[2:])

    rng = random.Random(0)
    target_pos = np.array(random_target_pos(rng, arena_dims))
    drone = Drone(start_pos=(0.0, 0.0, 1.2))
    controls = KeyboardController(
        profile_name=st.sens_profile,
        mass_profile_name=st.mass_profile,
        nerv_profile_name=st.nerv_profile,
        drag_profile_name=st.drag_profile,
    )
    if controls.randomize_each_reset:
        controls.randomize_sensitivity(rng)
    drone.apply_dynamics(controls.dyn_params)

    rd = Renderer3D(screen)
    cam_eye, cam_tgt = _cam_for_arena(st)
    rd.cam.look_at(cam_eye, cam_tgt)
    fpv_surface = pygame.Surface((C.FPV_W, C.FPV_H))
    rd_fpv = Renderer3D(fpv_surface, fov_deg=C.FPV_FOV_DEG)
    hud = HUDOverlay(screen)
    clock = pygame.time.Clock()

    sim_time = 0.0
    fps_smooth = 0.0
    last_t = time.perf_counter()
    sticks_view = Sticks()
    deterministic = True
    frame_idx = 0  # pour cadencer le FPV à 30 Hz

    print("[play] R=reset cible/drone   Esc=quitter   Espace=pause   I/K/J=FPV pitch")

    paused = False
    running = True
    while running:
        for event in pygame.event.get():
            if hud.handle_event(event, controls):
                continue
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    drone.reset()
                    target_pos = np.array(random_target_pos(rng, arena_dims))
                    sim_time = 0.0
                    if controls.randomize_each_reset:
                        controls.randomize_sensitivity(rng)
                    if controls.randomize_mass_each_reset:
                        controls.randomize_mass(rng)
                    if controls.randomize_nerv_each_reset:
                        controls.randomize_nerv(rng)
                    if controls.randomize_drag_each_reset:
                        controls.randomize_drag(rng)
                    drone.apply_dynamics(controls.dyn_params)
                elif event.key == pygame.K_SPACE:
                    paused = not paused

        keys = pygame.key.get_pressed()
        if keys[pygame.K_i]:
            controls.fpv_pitch = min(C.FPV_PITCH_MAX, controls.fpv_pitch + C.FPV_PITCH_RATE * C.RENDER_DT)
        if keys[pygame.K_k]:
            controls.fpv_pitch = max(C.FPV_PITCH_MIN, controls.fpv_pitch - C.FPV_PITCH_RATE * C.RENDER_DT)
        if keys[pygame.K_j]:
            controls.fpv_pitch *= max(0.0, 1.0 - 5.0 * C.RENDER_DT)

        now = time.perf_counter()
        dt = now - last_t
        last_t = now
        if dt > 0:
            fps_smooth = 0.9 * fps_smooth + 0.1 * (1.0 / dt) if fps_smooth > 0 else 1.0 / dt

        if not paused:
            state = drone.get_state()
            obs = build_obs_external(state, target_pos, controls.rate, controls.expo,
                                     controls.dyn_params, arena_dims)
            action, _ = model.predict(obs, deterministic=deterministic)
            roll, pitch, yaw, thr_raw = [float(x) for x in action]
            throttle = float(np.clip((thr_raw + 1.0) * 0.5, 0.0, 1.0))
            roll_s  = float(S.apply_curve(roll, controls.rate, controls.expo))
            pitch_s = float(S.apply_curve(pitch, controls.rate, controls.expo))
            yaw_s   = float(S.apply_curve(yaw, controls.rate, controls.expo))
            drone.set_command(throttle=throttle, roll=roll_s, pitch=pitch_s, yaw=yaw_s)
            sticks_view.throttle = throttle
            sticks_view.roll  = float(np.clip(roll, -1.0, 1.0))
            sticks_view.pitch = float(np.clip(pitch, -1.0, 1.0))
            sticks_view.yaw   = float(np.clip(yaw, -1.0, 1.0))

            for _ in range(C.PHYSICS_SUBSTEPS):
                drone.apply_forces()
                p.stepSimulation()
                sim_time += C.TIMESTEP

        state = drone.get_state()

        contacts = p.getContactPoints(bodyA=drone.body_id)
        wall_hit = False
        floor_hit = False
        for c in contacts:
            other = c[2]
            if other == floor_id:
                floor_hit = True
            elif other in side_walls or other == ceiling_id:
                wall_hit = True
        if wall_hit and not drone.motors_disabled:
            drone.disable_motors()
        if floor_hit:
            up_dot = float(state["rot"][2, 2])
            if up_dot <= C.INVERTED_DOT_THRESHOLD:
                drone.reset()
                target_pos = np.array(random_target_pos(rng, arena_dims))
                sim_time = 0.0
                if controls.randomize_each_reset:
                    controls.randomize_sensitivity(rng)
                if controls.randomize_mass_each_reset:
                    controls.randomize_mass(rng)
                if controls.randomize_nerv_each_reset:
                    controls.randomize_nerv(rng)
                if controls.randomize_drag_each_reset:
                    controls.randomize_drag(rng)
                drone.apply_dynamics(controls.dyn_params)

        if (not drone.motors_disabled
                and np.linalg.norm(state["pos"] - target_pos) < C.TARGET_REACH_DIST):
            target_pos = np.array(random_target_pos(rng, arena_dims))
        sx = st.arena_x / 2 + 0.05
        sy = st.arena_y / 2 + 0.05
        if (abs(state["pos"][0]) > sx
                or abs(state["pos"][1]) > sy
                or state["pos"][2] < -0.05
                or state["pos"][2] > st.arena_z + 0.05):
            drone.reset()
            sim_time = 0.0

        screen.fill(C.COLOR_BG)
        rd.reset()
        draw_box(rd)
        draw_target(rd, target_pos)
        draw_drone(rd, state["pos"], state["rot"])
        rd.render()

        # FPV cadencé à ~30 Hz pour garder >= 40 FPS même en arrènes larges.
        if frame_idx % 2 == 0:
            fpv_surface.fill(C.COLOR_BG)
            rot = state["rot"]
            nose_offset_world = rot @ np.array(C.FPV_NOSE_OFFSET)
            eye_fpv = state["pos"] + nose_offset_world
            cp, sp = np.cos(controls.fpv_pitch), np.sin(controls.fpv_pitch)
            fwd_world = rot @ np.array([cp, 0.0, sp])
            up_world = rot @ np.array([-sp, 0.0, cp])
            rd_fpv.cam.look_at(eye_fpv, eye_fpv + fwd_world, up=up_world)
            rd_fpv.reset()
            draw_box(rd_fpv)
            draw_target(rd_fpv, target_pos)
            rd_fpv.render()
        frame_idx += 1

        hud.draw(sticks_view, state, target_pos, sim_time, fps=fps_smooth,
                 fpv_surface=fpv_surface, fpv_pitch=controls.fpv_pitch,
                 controls=controls, motors_disabled=drone.motors_disabled)

        font = pygame.font.SysFont("DejaVu Sans", 18, bold=True)
        tag = font.render("AUTOPILOT — IA", True, (90, 220, 255))
        screen.blit(tag, (C.WINDOW_W // 2 - tag.get_width() // 2, 8))
        if drone.motors_disabled:
            font2 = pygame.font.SysFont("DejaVu Sans", 16, bold=True)
            t2 = font2.render("CRASH — chute libre", True, (255, 90, 90))
            screen.blit(t2, (C.WINDOW_W // 2 - t2.get_width() // 2, 30))

        pygame.display.flip()
        clock.tick(C.RENDER_HZ)

    pygame.quit()
    if p.isConnected():
        p.disconnect()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    if args.model:
        Stt.current.play_model_path = args.model
    run(Stt.current)


if __name__ == "__main__":
    main()
