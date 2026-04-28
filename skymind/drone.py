"""Modèle quadrirotor (physique uniquement, rendu géré séparément).

Drone modélisé comme un seul corps rigide. 4 moteurs symétriques en X
appliquent chacun une force selon Z local (poussée) et un couple yaw
selon Z local (réaction de l'hélice).
"""
from __future__ import annotations

import numpy as np
import pybullet as p

from . import config as C


# Position des 4 moteurs en repère drone (X vers l'avant, Y vers la gauche)
MOTOR_POSITIONS = np.array(
    [
        [+C.DRONE_ARM, -C.DRONE_ARM, 0.0],  # 0 avant-droit
        [-C.DRONE_ARM, +C.DRONE_ARM, 0.0],  # 1 arrière-gauche
        [+C.DRONE_ARM, +C.DRONE_ARM, 0.0],  # 2 avant-gauche
        [-C.DRONE_ARM, -C.DRONE_ARM, 0.0],  # 3 arrière-droit
    ]
)
MOTOR_SPIN = np.array([+1.0, +1.0, -1.0, -1.0])


class Drone:
    def __init__(self, start_pos=(0.0, 0.0, 1.2)):
        self.start_pos = tuple(start_pos)
        self.body_id = self._build()
        self._motor_target = np.zeros(4)
        self.motor_cmd = np.zeros(4)
        self._prev_lin_vel = np.zeros(3)
        self.motors_disabled = False
        # Consigne en mode acro : taux angulaire désiré (rad/s, body frame)
        self._target_rate = np.zeros(3)
        self._throttle = 0.0
        # Paramètres dynamiques courants (modifiables via apply_dynamics)
        self.mass = C.DRONE_MASS
        self.ixx = C.DRONE_IXX
        self.iyy = C.DRONE_IYY
        self.izz = C.DRONE_IZZ
        self.motor_tc = C.MOTOR_TIME_CONSTANT

    def _build(self) -> int:
        bx, by, bz = C.DRONE_BODY_SIZE
        col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[bx / 2, by / 2, bz / 2])
        body = p.createMultiBody(
            baseMass=C.DRONE_MASS,
            baseCollisionShapeIndex=col,
            baseVisualShapeIndex=-1,
            basePosition=self.start_pos,
            baseOrientation=[0, 0, 0, 1],
        )
        p.changeDynamics(
            body, -1,
            localInertiaDiagonal=[C.DRONE_IXX, C.DRONE_IYY, C.DRONE_IZZ],
            linearDamping=0.05,
            angularDamping=0.20,
            lateralFriction=0.6,
            restitution=0.05,
            ccdSweptSphereRadius=max(C.DRONE_BODY_SIZE) * 1.2,
        )
        return body

    def reset(self, pos=None):
        pos = pos or self.start_pos
        p.resetBasePositionAndOrientation(self.body_id, pos, [0, 0, 0, 1])
        p.resetBaseVelocity(self.body_id, [0, 0, 0], [0, 0, 0])
        self._motor_target[:] = 0.0
        self.motor_cmd[:] = 0.0
        self._prev_lin_vel[:] = 0.0
        self._target_rate[:] = 0.0
        self._throttle = 0.0
        self.motors_disabled = False

    def disable_motors(self):
        """Coupe définitivement les moteurs (impact mur). Le drone tombe."""
        self.motors_disabled = True
        self._motor_target[:] = 0.0
        self._target_rate[:] = 0.0
        self._throttle = 0.0

    def apply_dynamics(self, params):
        """Applique un jeu de paramètres dynamiques (masse, inertie, tau moteur,
        traînée linéaire/angulaire).

        `params` est un :class:`skymind.dynamics.DynamicsParams`.
        """
        self.mass = float(params.mass)
        self.ixx = float(params.ixx)
        self.iyy = float(params.iyy)
        self.izz = float(params.izz)
        self.motor_tc = float(params.motor_tc)
        drag_lin = float(getattr(params, "drag_lin", 0.05))
        drag_ang = float(getattr(params, "drag_ang", 0.20))
        p.changeDynamics(
            self.body_id, -1,
            mass=self.mass,
            localInertiaDiagonal=[self.ixx, self.iyy, self.izz],
            linearDamping=drag_lin,
            angularDamping=drag_ang,
        )

    def set_command(self, throttle: float, roll: float, pitch: float, yaw: float):
        """Mode acro : roll/pitch/yaw = consigne de **vitesse angulaire** [-1, 1].

        Le mixage moteur est fermé par la boucle de taux dans :meth:`apply_forces`,
        qui lit le gyro (ang_vel body) à chaque pas physique. Quand l'utilisateur
        relâche les sticks (consigne = 0 rad/s), le correcteur freine activement
        la rotation — le drone garde son angle, comme un vrai FPV.
        """
        if self.motors_disabled:
            self._target_rate[:] = 0.0
            self._throttle = 0.0
            return
        self._throttle = float(np.clip(throttle, 0.0, 1.0))
        # Convention de mixage (X-config) :
        #   +r  (mixer)  → +ωx (roll right)         → pas d'inversion
        #   +pi (mixer)  → -ωy (nose down)          → on inverse la consigne
        #   +y  (mixer)  → -ωz (yaw right)          → on inverse la consigne
        # En entrée, on garde les conventions historiques :
        #   stick pitch +1 (UP)   = nose down
        #   stick yaw   +1 (D)    = yaw right
        self._target_rate[0] =  float(np.clip(roll,  -1.0, 1.0)) * C.MAX_RATE_RP
        self._target_rate[1] = -float(np.clip(pitch, -1.0, 1.0)) * C.MAX_RATE_RP
        self._target_rate[2] = -float(np.clip(yaw,   -1.0, 1.0)) * C.MAX_RATE_YAW

    def apply_forces(self):
        if self.motors_disabled:
            # Lissage moteur vers 0 puis aucune force/torque
            alpha = C.TIMESTEP / max(self.motor_tc, C.TIMESTEP)
            self.motor_cmd += alpha * (0.0 - self.motor_cmd)
            return

        # --- Boucle de taux (PID gyro, ici P seul — D fait par damping) -------
        _, ang_vel_world = p.getBaseVelocity(self.body_id)
        _, orn = p.getBasePositionAndOrientation(self.body_id)
        rot = np.array(p.getMatrixFromQuaternion(orn)).reshape(3, 3)
        gyro = rot.T @ np.array(ang_vel_world)

        err = self._target_rate - gyro
        t = self._throttle
        # Sens du correcteur : pour roll, +r dans le mixer produit +ωx → gain +.
        # Pour pitch et yaw, +pi/+y dans le mixer produisent -ωy/-ωz : il faut
        # **inverser** la sortie sinon le bouclage est positif (le drone diverge).
        r  = float(np.clip( C.RATE_KP_RP  * err[0], -C.RATE_AUTHORITY_RP,  C.RATE_AUTHORITY_RP))
        pi = float(np.clip(-C.RATE_KP_RP  * err[1], -C.RATE_AUTHORITY_RP,  C.RATE_AUTHORITY_RP))
        y  = float(np.clip(-C.RATE_KP_YAW * err[2], -C.RATE_AUTHORITY_YAW, C.RATE_AUTHORITY_YAW))

        # Mixage moteur (X-config)
        target = np.array([
            t - r + pi - y,
            t + r - pi - y,
            t + r + pi + y,
            t - r - pi + y,
        ])
        self._motor_target = np.clip(target, 0.0, 1.0)

        # Lissage moteur 1er ordre (tau d'instance)
        alpha = C.TIMESTEP / max(self.motor_tc, C.TIMESTEP)
        self.motor_cmd += alpha * (self._motor_target - self.motor_cmd)

        for i in range(4):
            thrust = self.motor_cmd[i] * C.MOTOR_THRUST_MAX
            p.applyExternalForce(
                self.body_id, -1,
                forceObj=[0, 0, thrust],
                posObj=MOTOR_POSITIONS[i].tolist(),
                flags=p.LINK_FRAME,
            )
            torque_z = MOTOR_SPIN[i] * C.MOTOR_TORQUE_COEF * thrust
            p.applyExternalTorque(
                self.body_id, -1,
                torqueObj=[0, 0, torque_z],
                flags=p.LINK_FRAME,
            )

    def get_state(self) -> dict:
        pos, orn = p.getBasePositionAndOrientation(self.body_id)
        lin_vel, ang_vel = p.getBaseVelocity(self.body_id)
        rpy = p.getEulerFromQuaternion(orn)

        lin_vel_np = np.array(lin_vel)
        accel_world = (lin_vel_np - self._prev_lin_vel) / C.TIMESTEP + np.array([0, 0, C.GRAVITY])
        self._prev_lin_vel = lin_vel_np

        rot = np.array(p.getMatrixFromQuaternion(orn)).reshape(3, 3)
        accel_body = rot.T @ accel_world
        gyro_body = rot.T @ np.array(ang_vel)

        return {
            "pos": np.array(pos),
            "orn_quat": np.array(orn),
            "rot": rot,                 # 3x3 monde<-corps
            "rpy": np.array(rpy),
            "lin_vel": lin_vel_np,
            "ang_vel": np.array(ang_vel),
            "accel_body": accel_body,
            "gyro_body": gyro_body,
            "motor_cmd": self.motor_cmd.copy(),
        }
