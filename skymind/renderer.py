"""Rendu 3D logiciel léger en pygame.

Pas d'OpenGL : on projette à la main les sommets, on trie les polygones
en peintre (back-to-front) et on utilise pygame.draw. Suffisant pour la
scène très simple de Skymind (boîte + drone + cible).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pygame

from . import config as C


NEAR = 0.15  # plan de coupe avant


# --------------------------------------------------------------------------- camera
@dataclass
class Camera:
    w: int
    h: int
    fov: float
    f: float
    eye: np.ndarray
    basis: np.ndarray  # 3x3, lignes = (right, up, -forward)

    @classmethod
    def make(cls, w: int, h: int, fov_deg: float = C.FOV_DEG) -> "Camera":
        fov = math.radians(fov_deg)
        f = (h / 2.0) / math.tan(fov / 2.0)
        return cls(w, h, fov, f, np.array([0.0, 0.0, 1.0]), np.eye(3))

    def look_at(self, eye, target, up=(0.0, 0.0, 1.0)):
        eye = np.asarray(eye, dtype=float)
        target = np.asarray(target, dtype=float)
        up_v = np.asarray(up, dtype=float)
        fwd = target - eye
        n = np.linalg.norm(fwd)
        if n < 1e-9:
            return
        fwd /= n
        right = np.cross(fwd, up_v)
        rn = np.linalg.norm(right)
        if rn < 1e-9:
            right = np.array([1.0, 0.0, 0.0])
        else:
            right /= rn
        cam_up = np.cross(right, fwd)
        self.eye = eye
        self.basis = np.stack([right, cam_up, -fwd], axis=0)


# --------------------------------------------------------------------------- helpers
def _to_screen(local_xyz: np.ndarray, cam: Camera):
    """local_xyz : (N,3) en repère caméra. Retourne (xs, ys, depth)."""
    z = local_xyz[:, 2]
    depth = -z  # >0 devant
    xs = cam.w * 0.5 + cam.f * local_xyz[:, 0] / depth
    ys = cam.h * 0.5 - cam.f * local_xyz[:, 1] / depth
    return xs, ys, depth


def _clip_polygon(verts_local: list[np.ndarray]) -> list[np.ndarray]:
    """Sutherland-Hodgman contre le plan z = -NEAR (devant la caméra)."""
    out: list[np.ndarray] = []
    n = len(verts_local)
    if n == 0:
        return out
    for i in range(n):
        a = verts_local[i]
        b = verts_local[(i + 1) % n]
        a_in = (-a[2]) >= NEAR
        b_in = (-b[2]) >= NEAR
        if a_in:
            out.append(a)
        if a_in != b_in:
            t = (-NEAR - a[2]) / (b[2] - a[2])
            out.append(a + t * (b - a))
    return out


def _clip_segment(a: np.ndarray, b: np.ndarray):
    a_in = (-a[2]) >= NEAR
    b_in = (-b[2]) >= NEAR
    if a_in and b_in:
        return a, b
    if not a_in and not b_in:
        return None
    t = (-NEAR - a[2]) / (b[2] - a[2])
    inter = a + t * (b - a)
    return (a, inter) if a_in else (inter, b)


# --------------------------------------------------------------------------- scene
class Renderer3D:
    """Accumule des primitives world-space puis les dessine triées par profondeur."""

    LIGHT_DIR = np.array([0.4, 0.5, 1.0])

    def __init__(self, screen: pygame.Surface, fov_deg: float = C.FOV_DEG):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.cam = Camera.make(self.w, self.h, fov_deg)
        self._items: list = []  # (depth, kind, payload)
        self.LIGHT_DIR = self.LIGHT_DIR / np.linalg.norm(self.LIGHT_DIR)

    # --- ajouts -----------------------------------------------------------
    def reset(self):
        self._items.clear()

    def add_quad(self, verts_world, color, edge_color=None, shaded=True, normal=None):
        verts = np.asarray(verts_world, dtype=float)
        if shaded:
            if normal is None:
                e1 = verts[1] - verts[0]
                e2 = verts[2] - verts[0]
                n = np.cross(e1, e2)
                ln = np.linalg.norm(n)
                if ln > 1e-9:
                    n /= ln
                else:
                    n = np.array([0, 0, 1.0])
            else:
                n = normal / (np.linalg.norm(normal) + 1e-9)
            shade = 0.55 + 0.45 * max(0.0, float(np.dot(n, self.LIGHT_DIR)))
            color = (
                int(color[0] * shade),
                int(color[1] * shade),
                int(color[2] * shade),
            )
        local = (verts - self.cam.eye) @ self.cam.basis.T
        clipped = _clip_polygon(list(local))
        if len(clipped) < 3:
            return
        arr = np.stack(clipped)
        xs, ys, d = _to_screen(arr, self.cam)
        pts = list(zip(xs.tolist(), ys.tolist()))
        depth = float(np.mean(d))
        self._items.append((depth, "poly", (pts, color, edge_color)))

    def add_line(self, a, b, color, width=1):
        a = np.asarray(a, dtype=float)
        b = np.asarray(b, dtype=float)
        la = (a - self.cam.eye) @ self.cam.basis.T
        lb = (b - self.cam.eye) @ self.cam.basis.T
        seg = _clip_segment(la, lb)
        if seg is None:
            return
        arr = np.stack(seg)
        xs, ys, d = _to_screen(arr, self.cam)
        depth = float((d[0] + d[1]) * 0.5)
        self._items.append((depth, "line", ((xs[0], ys[0]), (xs[1], ys[1]), color, width)))

    def add_billboard(self, center, radius_world, color, edge_color=None):
        c = np.asarray(center, dtype=float)
        local = (c - self.cam.eye) @ self.cam.basis.T
        depth = -local[2]
        if depth < NEAR:
            return
        x = self.w * 0.5 + self.cam.f * local[0] / depth
        y = self.h * 0.5 - self.cam.f * local[1] / depth
        r = max(2, int(self.cam.f * radius_world / depth))
        self._items.append((depth, "circle", ((x, y), r, color, edge_color)))

    # --- rendu ------------------------------------------------------------
    def render(self):
        # Tri painter : plus loin d'abord
        self._items.sort(key=lambda it: -it[0])
        scr = self.screen
        for _, kind, payload in self._items:
            if kind == "poly":
                pts, color, edge = payload
                if len(pts) >= 3:
                    pygame.draw.polygon(scr, color, pts)
                    if edge is not None:
                        pygame.draw.polygon(scr, edge, pts, 1)
            elif kind == "line":
                a, b, color, width = payload
                pygame.draw.line(scr, color, a, b, width)
            elif kind == "circle":
                center, r, color, edge = payload
                ix, iy = int(center[0]), int(center[1])
                pygame.draw.circle(scr, color, (ix, iy), r)
                if edge is not None:
                    pygame.draw.circle(scr, edge, (ix, iy), r, 2)
        self._items.clear()


# --------------------------------------------------------------------------- scene helpers
def draw_box(rd: Renderer3D):
    """Sol damier + 4 murs + plafond, avec culling depuis la caméra.

    Si la caméra est *à l'extérieur* de la boîte sur un côté donné,
    le mur correspondant n'est pas dessiné : on voit l'intérieur à travers,
    et le fond uni (couleur BG) reste visible autour de la boîte.
    """
    s = C.BOX_SIZE / 2.0
    H = C.BOX_SIZE
    eye = rd.cam.eye
    margin = 0.01  # tolérance

    from . import settings as _S
    _st = _S.current
    sx = _st.arena_x / 2.0
    sy = _st.arena_y / 2.0
    H = _st.arena_z

    # --- Sol en damier (~ 1 m, mais capé à ~16x16 = 256 tuiles max) ---------
    if eye[2] > 0 - margin:  # caméra au-dessus du sol → on voit le sol
        nx = max(1, min(16, int(round(_st.arena_x))))
        ny = max(1, min(16, int(round(_st.arena_y))))
        for ix in range(nx):
            for iy in range(ny):
                x0 = -sx + ix * (_st.arena_x / nx)
                y0 = -sy + iy * (_st.arena_y / ny)
                w = _st.arena_x / nx
                h = _st.arena_y / ny
                color = C.COLOR_FLOOR if (ix + iy) % 2 == 0 else C.COLOR_FLOOR_2
                rd.add_quad(
                    [(x0, y0, 0), (x0 + w, y0, 0), (x0 + w, y0 + h, 0), (x0, y0 + h, 0)],
                    color, shaded=True, normal=np.array([0, 0, 1.0]),
                )
        # Lignes de la grille (par-dessus, légèrement sur-élevées)
        for i in range(nx + 1):
            u = -sx + i * (_st.arena_x / nx)
            rd.add_line((u, -sy, 0.002), (u, sy, 0.002), C.COLOR_FLOOR_LN, 1)
        for j in range(ny + 1):
            u = -sy + j * (_st.arena_y / ny)
            rd.add_line((-sx, u, 0.002), (sx, u, 0.002), C.COLOR_FLOOR_LN, 1)

    # --- Plafond ------------------------------------------------------------
    if eye[2] < H + margin:
        rd.add_quad(
            [(-sx, -sy, H), (-sx, sy, H), (sx, sy, H), (sx, -sy, H)],
            C.COLOR_CEIL, shaded=False,
        )

    # --- 4 murs (normales pointant vers l'intérieur) -----------------------
    # On dessine seulement ceux qui ne sont PAS entre la caméra et l'arène.
    walls = [
        # (vertices, normale_intérieure, condition_cull_si_camera_au_delà)
        ([(sx, -sy, 0), (sx, sy, 0), (sx, sy, H), (sx, -sy, H)],
         np.array([-1, 0, 0.0]), eye[0] > sx + margin),  # mur +X
        ([(-sx, sy, 0), (-sx, -sy, 0), (-sx, -sy, H), (-sx, sy, H)],
         np.array([1, 0, 0.0]), eye[0] < -sx - margin),  # mur -X
        ([(sx, sy, 0), (-sx, sy, 0), (-sx, sy, H), (sx, sy, H)],
         np.array([0, -1, 0.0]), eye[1] > sy + margin),  # mur +Y
        ([(-sx, -sy, 0), (sx, -sy, 0), (sx, -sy, H), (-sx, -sy, H)],
         np.array([0, 1, 0.0]), eye[1] < -sy - margin),  # mur -Y
    ]
    for verts, normal, culled in walls:
        if culled:
            continue
        rd.add_quad(verts, C.COLOR_WALL, shaded=True, normal=normal)
        # Bande horizontale aux 3/4 de la hauteur (touche déco "studio")
        zb = H * 0.75
        zb2 = zb + 0.18
        v = verts
        # Reconstruit une bande à hauteur fixe entre les 2 sommets supérieurs.
        a, b = v[0], v[1]  # base
        # remplace z=0 par zb / zb2 et z=H par zb2 — bande mince à zb..zb2
        band = [
            (a[0], a[1], zb), (b[0], b[1], zb),
            (b[0], b[1], zb2), (a[0], a[1], zb2),
        ]
        rd.add_quad(band, C.COLOR_WALL_BAND, shaded=True, normal=normal)

    # Pas d'arêtes verticales aux coins : elles tombaient pile au centre de
    # l'image et coupaient la scène en deux. La bande haute des murs suffit
    # à donner du volume.


def draw_target(rd: Renderer3D, pos: np.ndarray):
    rd.add_billboard(pos, C.TARGET_RADIUS, C.COLOR_TARGET, edge_color=C.COLOR_TARGET_HL)
    # Halo plus petit clair pour donner du volume
    rd.add_billboard(pos + np.array([-0.04, 0, 0.05]), C.TARGET_RADIUS * 0.35, C.COLOR_TARGET_HL, None)


def draw_drone(rd: Renderer3D, pos: np.ndarray, rot: np.ndarray):
    """Drone en X. `rot` = matrice 3x3 monde<-corps. X local = avant.

    Code couleur pour s'orienter :
    - bras AVANT  : rouge
    - bras ARRIERE: blanc
    - dessus      : "chapeau" blanc / corps violet en dessous
    """
    bx, by, bz = C.DRONE_BODY_SIZE
    hx, hy, hz = bx / 2, by / 2, bz / 2

    def to_world(local_pts):
        local = np.asarray(local_pts, dtype=float)
        return (rot @ local.T).T + pos

    # Corps : 6 faces d'une boîte
    box_local = np.array([
        [-hx, -hy, -hz], [+hx, -hy, -hz], [+hx, +hy, -hz], [-hx, +hy, -hz],  # bas
        [-hx, -hy, +hz], [+hx, -hy, +hz], [+hx, +hy, +hz], [-hx, +hy, +hz],  # haut
    ])
    bw = to_world(box_local)
    # (verts, color, edge)
    body_faces = [
        ((bw[4], bw[5], bw[6], bw[7]), C.COLOR_DRONE_TOP, C.COLOR_DRONE_LO),  # haut (blanc)
        ((bw[1], bw[0], bw[3], bw[2]), C.COLOR_DRONE_LO, None),               # bas (sombre)
        ((bw[0], bw[1], bw[5], bw[4]), C.COLOR_DRONE, C.COLOR_DRONE_LO),      # -y
        ((bw[2], bw[3], bw[7], bw[6]), C.COLOR_DRONE, C.COLOR_DRONE_LO),      # +y
        ((bw[1], bw[2], bw[6], bw[5]), C.COLOR_DRONE, C.COLOR_DRONE_LO),      # +x (avant)
        ((bw[3], bw[0], bw[4], bw[7]), C.COLOR_DRONE, C.COLOR_DRONE_LO),      # -x
    ]
    for f, col, edge in body_faces:
        rd.add_quad(list(f), col, edge_color=edge, shaded=True)

    # Petit "chapeau" blanc sur le dessus pour bien voir l'orientation par le haut.
    # C'est un petit toit pointant vers l'avant (X+), comme une flèche.
    cap_local = np.array([
        [+hx * 1.1, 0.0, hz + 0.005],   # pointe avant
        [-hx * 0.6, +hy * 0.6, hz + 0.005],
        [-hx * 0.6, -hy * 0.6, hz + 0.005],
    ])
    cw = to_world(cap_local)
    rd.add_quad([cw[0], cw[1], cw[2]], C.COLOR_ARM_FRONT, edge_color=(60, 0, 0), shaded=False)

    # 4 bras, avec couleurs distinctes avant / arrière
    arms = [
        # (extrémité_local, color_arm, color_prop, is_front)
        ([+C.DRONE_ARM, -C.DRONE_ARM, 0.0], C.COLOR_ARM_FRONT, C.COLOR_PROP_FRONT, True),   # avant-droit
        ([+C.DRONE_ARM, +C.DRONE_ARM, 0.0], C.COLOR_ARM_FRONT, C.COLOR_PROP_FRONT, True),   # avant-gauche
        ([-C.DRONE_ARM, +C.DRONE_ARM, 0.0], C.COLOR_ARM_BACK,  C.COLOR_PROP_BACK,  False),  # arrière-gauche
        ([-C.DRONE_ARM, -C.DRONE_ARM, 0.0], C.COLOR_ARM_BACK,  C.COLOR_PROP_BACK,  False),  # arrière-droit
    ]
    for end_local, col_arm, col_prop, _is_front in arms:
        ends = to_world([[0.0, 0.0, 0.0], end_local])
        rd.add_line(ends[0], ends[1], col_arm, 4)
        prop_world = to_world([[end_local[0], end_local[1], 0.02]])[0]
        rd.add_billboard(prop_world, 0.07, col_prop, edge_color=(20, 22, 30))
