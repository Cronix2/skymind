"""HUD 2D dessiné en surimpression sur la fenêtre principale.

Disposition (1280x720) :
- top-droit   : panneau sensibilité (dropdown des profils + courbe rate/expo)
- bas-gauche  : barre verticale de gaz (0..1) + indicateur de lacet
- bas-centre  : panneau télémétrie + écran FPV embarqué
- bas-droit   : stick tangage / roulis (centré sur 0)
"""
from __future__ import annotations

import numpy as np
import pygame

from . import config as C
from . import sensitivity as S
from . import dynamics as D


SENS_PANEL_W = 320
SENS_PANEL_H = 110
DYN_PANEL_W = 320
DYN_PANEL_H = 130


class SensitivityWidget:
    """Dropdown + diagramme de la courbe rate/expo.

    L'état (open/closed) est interne. Les changements de profil sont
    appliqués sur un objet "controls" (tout objet ayant `set_profile(name)`,
    `profile_name`, `rate`, `expo`).
    """

    PROFILE_NAMES = list(S.PROFILES.keys()) + ["Aléa"]
    ROW_H = 22

    def __init__(self, anchor_topright: tuple[int, int]):
        x = anchor_topright[0] - SENS_PANEL_W
        y = anchor_topright[1]
        self.rect = pygame.Rect(x, y, SENS_PANEL_W, SENS_PANEL_H)

        # Bouton dropdown (titre + flèche), à gauche du panneau
        bx = self.rect.x + 10
        by = self.rect.y + 28
        self.dropdown_rect = pygame.Rect(bx, by, 130, self.ROW_H)
        # Diagramme à droite
        self.curve_rect = pygame.Rect(
            self.rect.right - 10 - 90,
            self.rect.y + 12,
            90, 90,
        )
        # Liste déroulante (rectangles calculés à l'ouverture)
        self.open = False

    # ------------------------------------------------------------------ events
    def handle_event(self, event, controls) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        mx, my = event.pos
        # Si dropdown ouvert : test sur les options
        if self.open:
            for i, name in enumerate(self.PROFILE_NAMES):
                rr = pygame.Rect(
                    self.dropdown_rect.x,
                    self.dropdown_rect.bottom + i * self.ROW_H,
                    self.dropdown_rect.w,
                    self.ROW_H,
                )
                if rr.collidepoint(mx, my):
                    controls.set_profile(name)
                    self.open = False
                    return True
            # Click ailleurs : on referme
            self.open = False
            return False
        # Sinon, click sur le bouton ouvre la liste
        if self.dropdown_rect.collidepoint(mx, my):
            self.open = True
            return True
        return False

    # ------------------------------------------------------------------ draw
    def draw(self, screen: pygame.Surface, font, font_small, controls):
        # Panneau de fond
        s = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        s.fill(C.COLOR_HUD_PANEL)
        screen.blit(s, self.rect.topleft)
        pygame.draw.rect(screen, C.COLOR_HUD_LINE, self.rect, 1, border_radius=8)

        # Titre
        title = font.render("SENSIBILITE", True, C.COLOR_HUD_ACC)
        screen.blit(title, (self.rect.x + 10, self.rect.y + 6))

        # Bouton dropdown (toujours visible)
        self._draw_button(screen, font_small, self.dropdown_rect,
                          f"{controls.profile_name}  v",
                          highlighted=self.open)

        # Texte rate/expo sous le bouton
        info = font_small.render(
            f"rate={controls.rate:.2f}  expo={controls.expo:.2f}",
            True, C.COLOR_HUD_TEXT,
        )
        screen.blit(info, (self.dropdown_rect.x,
                           self.dropdown_rect.bottom + 4))

        # Courbe
        self._draw_curve(screen, controls.rate, controls.expo)

        # Liste déroulante (par-dessus, si ouverte) — dessinée en dernier
        # mais le draw() est appelé une fois par frame ; on s'en occupe
        # via draw_overlay() pour passer au-dessus du reste si besoin.

    def draw_overlay(self, screen: pygame.Surface, font_small, controls):
        """À appeler APRÈS tous les autres widgets pour que le dropdown
        ouvert apparaisse devant."""
        if not self.open:
            return
        for i, name in enumerate(self.PROFILE_NAMES):
            rr = pygame.Rect(
                self.dropdown_rect.x,
                self.dropdown_rect.bottom + i * self.ROW_H,
                self.dropdown_rect.w,
                self.ROW_H,
            )
            highlighted = (name == controls.profile_name)
            self._draw_button(screen, font_small, rr, name, highlighted=highlighted)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _draw_button(screen, font, rect, label, highlighted=False):
        bg = (60, 70, 96) if highlighted else (32, 36, 50)
        pygame.draw.rect(screen, bg, rect, border_radius=4)
        pygame.draw.rect(screen, C.COLOR_HUD_LINE, rect, 1, border_radius=4)
        surf = font.render(label, True, C.COLOR_HUD_TEXT)
        screen.blit(surf, (rect.x + 8, rect.y + (rect.h - surf.get_height()) // 2))

    def _draw_curve(self, screen, rate, expo):
        r = self.curve_rect
        pygame.draw.rect(screen, (14, 16, 22), r, border_radius=4)
        pygame.draw.rect(screen, C.COLOR_HUD_LINE, r, 1, border_radius=4)
        cx, cy = r.centerx, r.centery
        # axes
        pygame.draw.line(screen, C.COLOR_HUD_LINE, (r.x + 4, cy), (r.right - 4, cy), 1)
        pygame.draw.line(screen, C.COLOR_HUD_LINE, (cx, r.y + 4), (cx, r.bottom - 4), 1)
        # cadre +/- 1
        for k in (-1, 1):
            x = int(cx + k * (r.w / 2 - 6))
            pygame.draw.line(screen, (40, 46, 60), (x, r.y + 4), (x, r.bottom - 4), 1)
            y = int(cy - k * (r.h / 2 - 6))
            pygame.draw.line(screen, (40, 46, 60), (r.x + 4, y), (r.right - 4, y), 1)
        # y-scale : on borne à ±max(1, rate) pour bien voir la saturation
        ymax = max(1.0, rate)
        N = 33
        pts = []
        for i in range(N):
            xn = -1.0 + 2.0 * i / (N - 1)
            yn = S.apply_curve(xn, rate, expo)
            px = int(cx + xn * (r.w / 2 - 6))
            py = int(cy - (yn / ymax) * (r.h / 2 - 6))
            pts.append((px, py))
        if len(pts) >= 2:
            pygame.draw.lines(screen, C.COLOR_STICK_R, False, pts, 2)


class HUDOverlay:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.font = pygame.font.SysFont("DejaVu Sans Mono", 15)
        self.font_big = pygame.font.SysFont("DejaVu Sans", 17, bold=True)
        self.font_small = pygame.font.SysFont("DejaVu Sans", 12)

        margin = 20
        bottom_h = 200
        y_top = self.h - margin - bottom_h

        self.thr_rect = pygame.Rect(margin, y_top, 60, bottom_h)
        self.yaw_rect = pygame.Rect(margin + 60 + 14, y_top + bottom_h - 60, 170, 60)

        self.right_stick_size = 95
        rcx = self.w - margin - self.right_stick_size
        rcy = self.h - margin - self.right_stick_size
        self.right_center = (rcx, rcy)
        self.right_rect = pygame.Rect(rcx - self.right_stick_size, rcy - self.right_stick_size,
                                      2 * self.right_stick_size, 2 * self.right_stick_size)

        fpv_w = C.FPV_W
        fpv_h = C.FPV_H
        fpv_x = self.right_rect.x - 16 - fpv_w
        fpv_y = y_top + (bottom_h - fpv_h) // 2
        self.fpv_rect = pygame.Rect(fpv_x, fpv_y, fpv_w, fpv_h)

        tele_x = self.yaw_rect.right + 16
        tele_w = self.fpv_rect.x - 16 - tele_x
        self.tele_rect = pygame.Rect(tele_x, y_top, tele_w, bottom_h)

    # ------------------------------------------------------------------ events
    def handle_event(self, event, controls) -> bool:
        return False

    # ------------------------------------------------------------------ utils
    def _panel(self, rect: pygame.Rect):
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        s.fill(C.COLOR_HUD_PANEL)
        self.screen.blit(s, rect.topleft)
        pygame.draw.rect(self.screen, C.COLOR_HUD_LINE, rect, 1, border_radius=8)

    # ------------------------------------------------------------------ gaz
    def _draw_throttle(self, throttle: float, motors_disabled: bool = False):
        r = self.thr_rect
        self._panel(r)
        for frac in (0.25, 0.5, 0.75):
            ty = int(r.bottom - frac * r.h)
            pygame.draw.line(self.screen, C.COLOR_HUD_LINE,
                             (r.x + 6, ty), (r.right - 6, ty), 1)
        t = float(np.clip(throttle, 0.0, 1.0))
        fill_h = int((r.h - 12) * t)
        if fill_h > 0:
            color = (160, 60, 60) if motors_disabled else C.COLOR_STICK_L
            fill = pygame.Rect(r.x + 8, r.bottom - 6 - fill_h, r.w - 16, fill_h)
            pygame.draw.rect(self.screen, color, fill, border_radius=4)
        cy = r.bottom - 6 - fill_h
        pygame.draw.line(self.screen, (255, 255, 255),
                         (r.x + 4, cy), (r.right - 4, cy), 2)
        pct = self.font.render(f"{int(round(t * 100)):>3d}%", True, C.COLOR_HUD_TEXT)
        self.screen.blit(pct, (r.centerx - pct.get_width() // 2, r.y - 18))
        lbl_text = "DEAD" if motors_disabled else "GAZ"
        lbl_color = (255, 90, 90) if motors_disabled else C.COLOR_HUD_DIM
        lbl = self.font_small.render(lbl_text, True, lbl_color)
        self.screen.blit(lbl, (r.centerx - lbl.get_width() // 2, r.bottom + 4))

    # ------------------------------------------------------------------ lacet
    def _draw_yaw(self, yaw: float):
        r = self.yaw_rect
        self._panel(r)
        cx = r.centerx
        cy = r.centery + 4
        pygame.draw.line(self.screen, C.COLOR_HUD_LINE,
                         (r.x + 10, cy), (r.right - 10, cy), 1)
        pygame.draw.line(self.screen, C.COLOR_HUD_LINE, (cx, cy - 8), (cx, cy + 8), 1)
        v = float(np.clip(yaw, -1.0, 1.0))
        sx = int(cx + v * (r.w / 2 - 14))
        pygame.draw.line(self.screen, C.COLOR_STICK_L, (cx, cy), (sx, cy), 4)
        pygame.draw.circle(self.screen, C.COLOR_STICK_L, (sx, cy), 7)
        pygame.draw.circle(self.screen, (10, 12, 18), (sx, cy), 7, 2)
        lbl = self.font_small.render("LACET   Q  <  |  >  D", True, C.COLOR_HUD_DIM)
        self.screen.blit(lbl, (r.centerx - lbl.get_width() // 2, r.y + 4))

    # ------------------------------------------------------------------ stick droit
    def _draw_right_stick(self, x, y):
        cx, cy = self.right_center
        s = self.right_stick_size
        self._panel(self.right_rect)
        pygame.draw.line(self.screen, C.COLOR_HUD_LINE, (cx - s + 8, cy), (cx + s - 8, cy), 1)
        pygame.draw.line(self.screen, C.COLOR_HUD_LINE, (cx, cy - s + 8), (cx, cy + s - 8), 1)
        pygame.draw.circle(self.screen, C.COLOR_HUD_LINE, (cx, cy), int(s * 0.8), 1)
        x = float(np.clip(x, -1.0, 1.0))
        y = float(np.clip(y, -1.0, 1.0))
        sx = int(cx + x * (s - 14))
        sy = int(cy - y * (s - 14))
        pygame.draw.line(self.screen, C.COLOR_STICK_R, (cx, cy), (sx, sy), 3)
        pygame.draw.circle(self.screen, C.COLOR_STICK_R, (sx, sy), 9)
        pygame.draw.circle(self.screen, (10, 12, 18), (sx, sy), 9, 2)
        lbl = self.font_small.render("TANGAGE / ROULIS", True, C.COLOR_HUD_DIM)
        self.screen.blit(lbl, (cx - lbl.get_width() // 2, cy + s + 4))

    # ------------------------------------------------------------------ télémétrie
    def _draw_telemetry(self, state, target_pos, sim_time, dist):
        r = self.tele_rect
        self._panel(r)
        title = self.font_big.render("TELEMETRIE", True, C.COLOR_HUD_ACC)
        self.screen.blit(title, (r.x + 12, r.y + 6))

        pos = state["pos"]
        rpy = np.degrees(state["rpy"])
        gyro = np.degrees(state["gyro_body"])
        acc = state["accel_body"]
        vel = state["lin_vel"]
        m = state["motor_cmd"]
        speed = float(np.linalg.norm(vel))

        lines = [
            f"t {sim_time:6.2f}s   v {speed:5.2f}m/s   d {dist:5.2f}m",
            f"pos  x{pos[0]:+5.2f}  y{pos[1]:+5.2f}  z{pos[2]:5.2f}",
            f"vit  x{vel[0]:+5.2f}  y{vel[1]:+5.2f}  z{vel[2]:+5.2f}",
            f"ang  r{rpy[0]:+5.1f}  p{rpy[1]:+5.1f}  y{rpy[2]:+5.1f}",
            f"gyr  p{gyro[0]:+5.1f}  q{gyro[1]:+5.1f}  r{gyro[2]:+5.1f}",
            f"acc  x{acc[0]:+5.2f}  y{acc[1]:+5.2f}  z{acc[2]:+5.2f}",
            f"mot  {m[0]:.2f} {m[1]:.2f} {m[2]:.2f} {m[3]:.2f}",
        ]
        for i, line in enumerate(lines):
            surf = self.font.render(line, True, C.COLOR_HUD_TEXT)
            self.screen.blit(surf, (r.x + 12, r.y + 28 + i * 18))

    # ------------------------------------------------------------------ FPV
    def _draw_fpv(self, fpv_surface, fpv_pitch: float):
        r = self.fpv_rect
        self._panel(r)
        if fpv_surface is not None:
            self.screen.blit(fpv_surface, r.topleft)
            pygame.draw.rect(self.screen, C.COLOR_HUD_LINE, r, 1, border_radius=2)
        tag = self.font_small.render(
            f" FPV  pitch {np.degrees(fpv_pitch):+5.1f} deg   I/K  J=reset ",
            True, C.COLOR_HUD_TEXT,
        )
        bg = pygame.Surface((tag.get_width() + 8, tag.get_height() + 4), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        self.screen.blit(bg, (r.x + 4, r.y + 4))
        self.screen.blit(tag, (r.x + 8, r.y + 6))
        cx, cy = r.centerx, r.centery
        pygame.draw.line(self.screen, (255, 255, 255), (cx - 8, cy), (cx + 8, cy), 1)
        pygame.draw.line(self.screen, (255, 255, 255), (cx, cy - 8), (cx, cy + 8), 1)

    # ------------------------------------------------------------------ légende
    def _draw_legend_and_fps(self, fps: float):
        msg = ("Z/W,S : gaz   Q,D : lacet   Up/Dn : tangage   Lf/Rt : roulis   "
               "I/K : FPV pitch   R : reset   Esc : quitter")
        surf = self.font_small.render(msg, True, C.COLOR_HUD_DIM)
        self.screen.blit(surf, (20, 14))

        title = self.font_big.render("Skymind - " + C.DRONE_NAME, True, C.COLOR_HUD_TEXT)
        self.screen.blit(title, (20, 32))

        if fps > 0:
            fps_surf = self.font.render(f"{fps:5.1f} FPS", True, C.COLOR_HUD_DIM)
            self.screen.blit(fps_surf, (self.w - fps_surf.get_width() - 16, 16))

    # ------------------------------------------------------------------ draw
    def draw(self, sticks, state, target_pos, sim_time, fps=0.0,
             fpv_surface=None, fpv_pitch: float = 0.0,
             controls=None, motors_disabled: bool = False):
        self._draw_throttle(sticks.throttle, motors_disabled=motors_disabled)
        self._draw_yaw(sticks.yaw)
        self._draw_right_stick(sticks.roll, sticks.pitch)
        dist = float(np.linalg.norm(state["pos"] - target_pos))
        self._draw_telemetry(state, target_pos, sim_time, dist)
        self._draw_fpv(fpv_surface, fpv_pitch)
        self._draw_legend_and_fps(fps)
