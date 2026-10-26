"""Skymind — pilotage manuel.

Une seule fenêtre pygame. Caméra fixe à l'extérieur de la boîte.
Physique PyBullet en mode DIRECT (sans fenêtre).

Lancement direct :
    python -m skymind.main
ou via le menu : :mod:`skymind.app`.
"""
from __future__ import annotations

import os
import time
import random

import numpy as np
import pygame
import pybullet as p

from . import config as C
from . import settings as Stt
from . import sensitivity as Sens
from . import dynamics as D
from .arena import build_box, random_target_pos
from .controls import KeyboardController
from .drone import Drone
from .flight_hud import FlightHUD as HUDOverlay
from .renderer import Renderer3D, draw_box, draw_target, draw_drone


def _cam_for_arena(st: Stt.Settings) -> tuple[np.ndarray, np.ndarray]:
    eye = np.array([-st.arena_x * 0.95, -st.arena_y * 0.95, st.arena_z * 1.20])
    target = np.array([0.0, 0.0, st.arena_z * 0.40])
    return eye, target


def _setup_physics():
    p.connect(p.DIRECT)
    p.setGravity(0, 0, -C.GRAVITY)
    p.setTimeStep(C.TIMESTEP)
    p.setRealTimeSimulation(0)


def _is_out_of_box(pos: np.ndarray, st: Stt.Settings) -> bool:
    sx = st.arena_x / 2.0 + 0.05
    sy = st.arena_y / 2.0 + 0.05
    return bool(
        abs(pos[0]) > sx or abs(pos[1]) > sy
        or pos[2] < -0.05 or pos[2] > st.arena_z + 0.05
    )


def run(st: Stt.Settings | None = None):
    """Boucle de pilotage manuel avec les réglages fournis."""
    if st is None:
        st = Stt.current
    else:
        Stt.current = st

    os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
    pygame.init()
    pygame.display.set_caption(f"Skymind — {C.DRONE_NAME}")
    screen = pygame.display.set_mode((C.WINDOW_W, C.WINDOW_H))

    _setup_physics()
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
    if st.input_mode == "Radio USB":
        from .radio import Radio
        controls.radio = Radio()
    drone.apply_dynamics(controls.dyn_params)

    rd = Renderer3D(screen)
    cam_eye, cam_tgt = _cam_for_arena(st)
    rd.cam.look_at(cam_eye, cam_tgt)

    fpv_surface = pygame.Surface((C.WINDOW_W, C.WINDOW_H) if st.fpv_fullscreen else (C.FPV_W, C.FPV_H))
    rd_fpv = Renderer3D(fpv_surface, fov_deg=C.FPV_FOV_DEG)

    hud = HUDOverlay(screen)
    clock = pygame.time.Clock()

    sim_time = 0.0
    fps_smooth = 0.0
    last_t = time.perf_counter()
    frame_idx = 0  # pour cadencer le FPV à 30 Hz

    print(f"Skymind — fenêtre {C.WINDOW_W}x{C.WINDOW_H}, cap {C.RENDER_HZ} FPS, physique {C.SIM_HZ} Hz.")
    print(f"  arène {st.arena_x:.1f} x {st.arena_y:.1f} x {st.arena_z:.1f} m")

    def do_reset():
        nonlocal sim_time, target_pos
        drone.reset()
        if controls.radio is not None:
            controls.radio.armed = False
        target_pos[:] = np.array(random_target_pos(rng, arena_dims))
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

    running = True
    while running:
        for event in pygame.event.get():
            if hud.handle_event(event, controls):
                continue
            if event.type == pygame.KEYDOWN and event.key == pygame.K_v:
                st.fpv_fullscreen = not st.fpv_fullscreen
            controls.handle_event(event)
        if controls.request_quit:
            break

        now = time.perf_counter()
        dt = now - last_t
        last_t = now
        if dt > 0:
            fps_smooth = 0.9 * fps_smooth + 0.1 * (1.0 / dt) if fps_smooth > 0 else 1.0 / dt

        sticks_raw = controls.update(C.RENDER_DT)
        if controls.request_reset:
            controls.request_reset = False
            do_reset()

        sticks = controls.shaped_sticks()
        drone.set_command(
            throttle=sticks.throttle,
            roll=sticks.roll,
            pitch=sticks.pitch,
            yaw=sticks.yaw,
        )

        for _ in range(C.PHYSICS_SUBSTEPS):
            drone.apply_forces()
            p.stepSimulation()
            sim_time += C.TIMESTEP

        state = drone.get_state()
        speed = float(np.linalg.norm(state["lin_vel"]))

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
                do_reset()

        if (not drone.motors_disabled
                and np.linalg.norm(state["pos"] - target_pos) < C.TARGET_REACH_DIST):
            target_pos = np.array(random_target_pos(rng, arena_dims))

        if _is_out_of_box(state["pos"], st):
            do_reset()

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

        if st.fpv_fullscreen:
            screen.blit(pygame.transform.scale(fpv_surface, screen.get_size()), (0, 0))
        hud.draw(sticks, state, target_pos, sim_time, fps=fps_smooth,
                 fpv_surface=pygame.transform.scale(fpv_surface, (C.FPV_W, C.FPV_H)), fpv_pitch=controls.fpv_pitch,
                 controls=controls, motors_disabled=drone.motors_disabled)

        if controls.radio is not None:
            status = pygame.font.SysFont("DejaVu Sans", 18).render(controls.radio.message, True, (80, 230, 210))
            screen.blit(status, (24, 94))
        pygame.display.flip()
        clock.tick(C.RENDER_HZ)

    pygame.quit()
    if p.isConnected():
        p.disconnect()


def main():
    run(Stt.current)


if __name__ == "__main__":
    main()
