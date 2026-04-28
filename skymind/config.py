"""Constantes physiques et paramètres de la simulation.

Unités SI : mètres, kilogrammes, secondes, radians.
"""
from __future__ import annotations

# --- Fenêtre / rendu ---
WINDOW_W = 1280
WINDOW_H = 720
FOV_DEG = 55.0
RENDER_HZ = 60
RENDER_DT = 1.0 / RENDER_HZ

# --- Boîte (arène) ---
BOX_SIZE = 10.0          # côté intérieur de la boîte (m)
BOX_WALL_THICK = 0.50    # épais : anti-tunneling robuste même en cas d'impact violent

# --- Drone ---
DRONE_MASS = 0.5
DRONE_ARM = 0.18
DRONE_BODY_SIZE = (0.18, 0.18, 0.05)
DRONE_IXX = 2.3e-3
DRONE_IYY = 2.3e-3
DRONE_IZZ = 4.0e-3

GRAVITY = 9.81
HOVER_THRUST_TOTAL = DRONE_MASS * GRAVITY
THRUST_TO_WEIGHT = 2.2
MOTOR_THRUST_MAX = (HOVER_THRUST_TOTAL * THRUST_TO_WEIGHT) / 4.0
MOTOR_TORQUE_COEF = 0.016
MOTOR_TIME_CONSTANT = 0.025  # s : très réactif

# --- Commandes ---
# Sticks roulis/tangage/lacet = consigne de **vitesse angulaire** (acro mode FC).
# Quand le stick revient à 0, la consigne = 0 rad/s : le correcteur freine
# activement la rotation → le drone garde son angle, comme un vrai FPV.
MAX_RATE_RP = 2.5       # rad/s pour roulis/tangage à stick = ±1 (~145°/s, doux)
MAX_RATE_YAW = 1.8      # rad/s pour lacet  à stick = ±1 (~105°/s)
RATE_KP_RP = 0.07       # gain proportionnel boucle de taux roll/pitch
RATE_KP_YAW = 0.15      # gain proportionnel boucle de taux yaw
RATE_AUTHORITY_RP = 0.45   # différentiel moteur max produit par la boucle (RP)
RATE_AUTHORITY_YAW = 0.50  # différentiel moteur max produit par la boucle (yaw)
# Anciennes constantes conservées pour compat (non utilisées par la nouvelle
# boucle de taux, mais référencées ailleurs si besoin).
MAX_TILT_CMD = 0.10
MAX_YAW_CMD = 0.10
STICK_DEADZONE = 0.05  # zone morte clavier
THROTTLE_HOVER = HOVER_THRUST_TOTAL / (4.0 * MOTOR_THRUST_MAX)

STICK_RATE = 6.0          # 1/s : lissage tangage/roulis/lacet
THROTTLE_UP_RATE = 1.4    # 1/s : Z/W — même vitesse à la montée
THROTTLE_DN_RATE = 1.4    # 1/s : S  — et à la descente (vrai stick : on tient la position)

# --- FPV (caméra embarquée sur le drone) ---
FPV_W = 320
FPV_H = 180
FPV_FOV_DEG = 80.0
FPV_NOSE_OFFSET = (0.10, 0.0, 0.04)   # devant + légèrement au-dessus du corps
FPV_PITCH_RATE = 1.5                  # rad/s (touches I/K)
FPV_PITCH_MAX = 0.7                   # ~40°
FPV_PITCH_MIN = -0.7

# --- Simulation ---
SIM_HZ = 480
PHYSICS_SUBSTEPS = SIM_HZ // RENDER_HZ
TIMESTEP = 1.0 / SIM_HZ

# --- Cible ---
TARGET_RADIUS = 0.18
TARGET_REACH_DIST = 0.45

# --- Crash / atterrissage ---
WALL_HIT_SPEED_PENALTY = 8.0     # par m/s d'impact mur (x vitesse au contact)
WALL_HIT_FLAT_PENALTY = 5.0      # pénalité fixe à l'impact d'un mur
GROUND_INVERTED_PENALTY = 40.0   # gros malus si on finit sur le dos
GROUND_SOFT_LANDING_SPEED = 1.0  # m/s : en dessous = atterrissage doux ok
GROUND_HARD_LANDING_COEF = 4.0   # par m/s au-delà du seuil doux
INVERTED_DOT_THRESHOLD = -0.3    # cos(theta) du Z drone vs Z monde : <= -0.3 = retourné
SETTLED_SPEED = 0.25             # m/s : vitesse en dessous de laquelle on considère
                                 # qu'un drone moteurs coupés s'est posé

# --- Couleurs (R, G, B) — palette type "studio" ---
COLOR_BG       = (8, 9, 14)            # fond uni hors-boîte
COLOR_FLOOR    = (210, 212, 220)       # dalle claire (damier)
COLOR_FLOOR_2  = (180, 184, 196)       # dalle foncée (damier)
COLOR_FLOOR_LN = (130, 134, 150)
COLOR_WALL     = (38, 42, 58)
COLOR_WALL_BAND= (90, 100, 130)        # bande haute des murs
COLOR_WALL_LN  = (60, 66, 86)
COLOR_CEIL     = (18, 20, 28)
COLOR_CEIL_LN  = (40, 44, 60)

COLOR_DRONE        = (170, 90, 240)    # corps - violet
COLOR_DRONE_LO     = (90, 50, 150)
COLOR_DRONE_TOP    = (235, 235, 245)   # "chapeau" blanc sur le dessus
COLOR_ARM_FRONT    = (255, 70, 70)     # bras avant : rouge
COLOR_ARM_BACK     = (235, 235, 245)   # bras arrière : blanc
COLOR_PROP_FRONT   = (200, 50, 50)
COLOR_PROP_BACK    = (180, 180, 195)

COLOR_TARGET     = (90, 230, 110)
COLOR_TARGET_HL  = (200, 255, 220)

COLOR_HUD_PANEL = (22, 24, 32, 215)
COLOR_HUD_LINE  = (60, 66, 84)
COLOR_HUD_TEXT  = (230, 232, 240)
COLOR_HUD_DIM   = (140, 150, 170)
COLOR_HUD_ACC   = (120, 180, 255)
COLOR_STICK_L   = (255, 200, 70)
COLOR_STICK_R   = (90, 220, 255)

DRONE_NAME = "BOB"
