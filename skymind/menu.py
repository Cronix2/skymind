"""Menu pygame : page d'accueil + pages de réglages.

Lance via :mod:`skymind.app`. Retourne, depuis :func:`run`, un tuple
``(mode, settings)`` où ``mode`` vaut ``"manual"``, ``"play"`` ou
``"train"`` (ou ``None`` si l'utilisateur ferme la fenêtre).

L'objet ``settings`` est l'instance de :class:`skymind.settings.Settings`
modifiée par l'utilisateur depuis le menu.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

import pygame

from . import settings as Stt
from . import sensitivity as Sens
from . import dynamics as D


# -------------------------------------------------------------------- thème
WIDTH, HEIGHT = 1280, 720
BG       = (16, 18, 26)
PANEL    = (28, 32, 44)
TEXT     = (230, 232, 240)
DIM      = (140, 150, 170)
ACC      = (120, 180, 255)
BTN      = (52, 60, 84)
BTN_HV   = (78, 92, 120)
GO       = (60, 140, 90)
GO_HV    = (80, 180, 120)


def _load_models() -> list[str]:
    """Liste des .zip dans runs/."""
    p = Path("runs")
    if not p.exists():
        return []
    return sorted(str(f) for f in p.rglob("*.zip"))


# ============================================================ widgets
class Button:
    def __init__(self, rect, label, on_click, *, color=BTN, hover=BTN_HV, big=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.color = color
        self.hover = hover
        self.big = big

    def handle(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.on_click()
                return True
        return False

    def draw(self, screen, font, font_big):
        c = self.hover if self.rect.collidepoint(pygame.mouse.get_pos()) else self.color
        pygame.draw.rect(screen, c, self.rect, border_radius=8)
        f = font_big if self.big else font
        s = f.render(self.label, True, TEXT)
        screen.blit(s, s.get_rect(center=self.rect.center))


class Field:
    """Ligne « label  [-]  valeur  [+] »."""
    X0 = 340
    W = 600
    H = 38

    def __init__(self, y, label, on_left, on_right, value_getter):
        self.y = y
        self.label = label
        self.on_left = on_left
        self.on_right = on_right
        self.value_getter = value_getter

    def _rects(self):
        left = pygame.Rect(self.X0, self.y, 38, self.H)
        right = pygame.Rect(self.X0 + self.W - 38, self.y, 38, self.H)
        value = pygame.Rect(self.X0 + 40, self.y, self.W - 80, self.H)
        return left, right, value

    def handle(self, event) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        l, r, _ = self._rects()
        if l.collidepoint(event.pos):
            self.on_left()
            return True
        if r.collidepoint(event.pos):
            self.on_right()
            return True
        return False

    def draw(self, screen, font, font_big):
        l, r, v = self._rects()
        lab = font.render(self.label, True, DIM)
        screen.blit(lab, (60, self.y + 10))
        for rect, sym in ((l, "<"), (r, ">")):
            c = BTN_HV if rect.collidepoint(pygame.mouse.get_pos()) else BTN
            pygame.draw.rect(screen, c, rect, border_radius=6)
            s = font.render(sym, True, TEXT)
            screen.blit(s, s.get_rect(center=rect.center))
        pygame.draw.rect(screen, PANEL, v, border_radius=6)
        val_str = self.value_getter()
        s = font.render(val_str, True, TEXT)
        screen.blit(s, s.get_rect(center=v.center))


# --------------------------------------------------------- factories Field
def int_field(y, label, getter, setter, step, lo, hi, fmt=str):
    def left():  setter(max(lo, getter() - step))
    def right(): setter(min(hi, getter() + step))
    return Field(y, label, left, right, lambda: fmt(getter()))


def float_field(y, label, getter, setter, step, lo, hi, fmt="{:.2f}"):
    def left():  setter(round(max(lo, getter() - step), 4))
    def right(): setter(round(min(hi, getter() + step), 4))
    return Field(y, label, left, right, lambda: fmt.format(getter()))


def choice_field(y, label, choices, getter, setter):
    def cycle(d):
        try:    i = choices.index(getter())
        except ValueError: i = 0
        setter(choices[(i + d) % len(choices)])
    return Field(y, label, lambda: cycle(-1), lambda: cycle(+1), getter)


def bool_field(y, label, getter, setter):
    return Field(y, label,
                 lambda: setter(not getter()),
                 lambda: setter(not getter()),
                 lambda: "Oui" if getter() else "Non")


# ============================================================ pages
SENS_CHOICES = list(Sens.PROFILES.keys()) + ["Aléa"]
MASS_CHOICES = list(D.MASS_PROFILES.keys()) + ["Aléa"]
NERV_CHOICES = list(D.NERV_PROFILES.keys()) + ["Aléa"]
DRAG_CHOICES = list(D.DRAG_PROFILES.keys()) + ["Aléa"]
LR_CHOICES = [1e-4, 3e-4, 5e-4, 1e-3]


def _arena_fields(y0: int, st: Stt.Settings) -> list[Field]:
    return [
        float_field(y0 + 0*50, "Arène longueur (X) m",
                    lambda: st.arena_x,
                    lambda v: setattr(st, "arena_x", v),
                    0.5, 4.0, 30.0, "{:.1f}"),
        float_field(y0 + 1*50, "Arène largeur (Y) m",
                    lambda: st.arena_y,
                    lambda v: setattr(st, "arena_y", v),
                    0.5, 4.0, 30.0, "{:.1f}"),
        float_field(y0 + 2*50, "Arène hauteur (Z) m",
                    lambda: st.arena_z,
                    lambda v: setattr(st, "arena_z", v),
                    0.5, 4.0, 30.0, "{:.1f}"),
    ]


def _drone_fields(y0: int, st: Stt.Settings) -> list[Field]:
    return [
        choice_field(y0 + 0*50, "Sensibilité",
                     SENS_CHOICES,
                     lambda: st.sens_profile,
                     lambda v: setattr(st, "sens_profile", v)),
        choice_field(y0 + 1*50, "Masse",
                     MASS_CHOICES,
                     lambda: st.mass_profile,
                     lambda v: setattr(st, "mass_profile", v)),
        choice_field(y0 + 2*50, "Nervosité",
                     NERV_CHOICES,
                     lambda: st.nerv_profile,
                     lambda v: setattr(st, "nerv_profile", v)),
        choice_field(y0 + 3*50, "Traînée (frottements air)",
                     DRAG_CHOICES,
                     lambda: st.drag_profile,
                     lambda v: setattr(st, "drag_profile", v)),
    ]


def build_main_page(menu) -> tuple[str, list]:
    """Page d'accueil : 3 gros boutons."""
    cx = WIDTH // 2
    bw, bh = 360, 80
    spacing = 24
    y = 240
    btns = [
        Button((cx - bw//2, y + 0*(bh+spacing), bw, bh),
               "Pilotage manuel",
               lambda: menu.goto("manual_setup"),
               color=BTN, hover=BTN_HV, big=True),
        Button((cx - bw//2, y + 1*(bh+spacing), bw, bh),
               "Lecture IA",
               lambda: menu.goto("play_setup"),
               color=BTN, hover=BTN_HV, big=True),
        Button((cx - bw//2, y + 2*(bh+spacing), bw, bh),
               "Entraînement",
               lambda: menu.goto("train_setup"),
               color=BTN, hover=BTN_HV, big=True),
    ]
    return "Skymind", btns


def build_manual_setup(menu) -> tuple[str, list]:
    st = menu.settings
    widgets = []
    widgets += _arena_fields(80, st)
    widgets += _drone_fields(80 + 3*50 + 20, st)
    widgets += [
        Button((60, HEIGHT - 70, 160, 44), "Retour",
               lambda: menu.goto("main")),
        Button((WIDTH - 60 - 220, HEIGHT - 70, 220, 44), "Lancer",
               lambda: menu.finish("manual"),
               color=GO, hover=GO_HV, big=True),
    ]
    return "Pilotage manuel — paramètres", widgets


def build_play_setup(menu) -> tuple[str, list]:
    st = menu.settings
    models = _load_models()
    if not models:
        models = ["(aucun modèle dans runs/)"]
    if st.play_model_path not in models:
        st.play_model_path = models[0]
    widgets = []
    widgets.append(choice_field(40, "Modèle",
                                models,
                                lambda: st.play_model_path,
                                lambda v: setattr(st, "play_model_path", v)))
    widgets += _arena_fields(40 + 1*50 + 20, st)
    widgets += _drone_fields(40 + 4*50 + 40, st)
    widgets += [
        Button((60, HEIGHT - 70, 160, 44), "Retour",
               lambda: menu.goto("main")),
        Button((WIDTH - 60 - 220, HEIGHT - 70, 220, 44), "Lancer",
               lambda: menu.finish("play"),
               color=GO, hover=GO_HV, big=True),
    ]
    return "Lecture IA — paramètres", widgets


def build_train_setup(menu) -> tuple[str, list]:
    st = menu.settings
    widgets = []
    y = 30
    widgets += _arena_fields(y, st); y += 3*50 + 16
    widgets += [
        int_field(y + 0*50, "Pas d'entraînement",
                  lambda: st.train_steps,
                  lambda v: setattr(st, "train_steps", v),
                  100_000, 50_000, 50_000_000,
                  fmt=lambda n: f"{n:,}".replace(",", " ")),
        int_field(y + 1*50, "Envs parallèles",
                  lambda: st.train_n_envs,
                  lambda v: setattr(st, "train_n_envs", v),
                  1, 1, 32),
        int_field(y + 2*50, "Seed",
                  lambda: st.train_seed,
                  lambda v: setattr(st, "train_seed", v),
                  1, 0, 99999),
        choice_field(y + 3*50, "Learning rate",
                     [f"{x:.0e}" for x in LR_CHOICES],
                     lambda: f"{st.train_lr:.0e}",
                     lambda v: setattr(st, "train_lr", float(v))),
        bool_field(y + 4*50, "Reprendre modèle existant",
                   lambda: st.train_auto_resume,
                   lambda v: setattr(st, "train_auto_resume", v)),
        bool_field(y + 5*50, "Randomiser sensibilité",
                   lambda: st.train_random_sens,
                   lambda v: setattr(st, "train_random_sens", v)),
        bool_field(y + 6*50, "Randomiser masse",
                   lambda: st.train_random_mass,
                   lambda v: setattr(st, "train_random_mass", v)),
        bool_field(y + 7*50, "Randomiser nervosité",
                   lambda: st.train_random_nerv,
                   lambda v: setattr(st, "train_random_nerv", v)),
        bool_field(y + 8*50, "Randomiser traînée",
                   lambda: st.train_random_drag,
                   lambda v: setattr(st, "train_random_drag", v)),
    ]
    widgets += [
        Button((60, HEIGHT - 70, 160, 44), "Retour",
               lambda: menu.goto("main")),
        Button((WIDTH - 60 - 220, HEIGHT - 70, 220, 44), "Lancer",
               lambda: menu.finish("train"),
               color=GO, hover=GO_HV, big=True),
    ]
    return "Entraînement — paramètres", widgets


PAGES: dict[str, Callable] = {
    "main":         build_main_page,
    "manual_setup": build_manual_setup,
    "play_setup":   build_play_setup,
    "train_setup":  build_train_setup,
}


# ============================================================ controller
class Menu:
    def __init__(self):
        self.settings = Stt.current
        self.page = "main"
        self.result: Optional[str] = None
        self._done = False

    def goto(self, page: str):
        self.page = page

    def finish(self, mode: str):
        self.result = mode
        self._done = True


def run() -> tuple[Optional[str], Stt.Settings]:
    """Affiche le menu jusqu'à ce que l'utilisateur lance ou ferme.

    Retourne (mode, settings). mode ∈ {'manual','play','train',None}.
    """
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Skymind — Menu")
    font       = pygame.font.SysFont("DejaVu Sans", 18)
    font_big   = pygame.font.SysFont("DejaVu Sans", 22, bold=True)
    font_title = pygame.font.SysFont("DejaVu Sans", 38, bold=True)
    clock = pygame.time.Clock()

    menu = Menu()

    while not menu._done:
        title, widgets = PAGES[menu.page](menu)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.display.quit()
                pygame.quit()
                return None, menu.settings
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                if menu.page == "main":
                    pygame.display.quit()
                    pygame.quit()
                    return None, menu.settings
                menu.goto("main")
                break
            for w in widgets:
                if w.handle(ev):
                    break

        screen.fill(BG)
        # titre
        ts = font_title.render(title, True, ACC)
        screen.blit(ts, ts.get_rect(midtop=(WIDTH // 2, 14)))
        for w in widgets:
            w.draw(screen, font, font_big)
        pygame.display.flip()
        clock.tick(60)

    pygame.display.quit()
    pygame.quit()
    return menu.result, menu.settings
