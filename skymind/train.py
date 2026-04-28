"""Entraînement PPO sur SkymindEnv avec Stable-Baselines3.

Les hyperparamètres sont lus depuis :class:`skymind.settings.Settings`.
Lancement direct :
    python -m skymind.train
ou via le menu : :mod:`skymind.app`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "stable-baselines3 n'est pas installé. Lance ./deploy.sh."
    ) from e

from . import settings as Stt
from .env import SkymindEnv


def _make_env(seed: int, st: Stt.Settings):
    arena_dims = (st.arena_x, st.arena_y, st.arena_z)
    rs = bool(st.train_random_sens)
    rm = bool(st.train_random_mass)
    rn = bool(st.train_random_nerv)
    rd = bool(st.train_random_drag)

    def _thunk():
        env = SkymindEnv(
            seed=seed,
            randomize_sensitivity=rs,
            randomize_mass=rm,
            randomize_nerv=rn,
            randomize_drag=rd,
            arena_dims=arena_dims,
        )
        env = Monitor(env)
        return env
    return _thunk


def run(st: Stt.Settings | None = None, out_dir: str = "runs"):
    if st is None:
        st = Stt.current
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "checkpoints").mkdir(exist_ok=True)
    log_dir = out / "tb"
    log_dir.mkdir(exist_ok=True)

    n_envs = max(1, int(st.train_n_envs))
    seed = int(st.train_seed)
    if n_envs > 1:
        env = SubprocVecEnv([_make_env(seed + i, st) for i in range(n_envs)])
    else:
        env = DummyVecEnv([_make_env(seed, st)])
    eval_env = DummyVecEnv([_make_env(seed + 10_000, st)])

    resume_path = None
    if st.train_auto_resume:
        candidate = out / "skymind_ppo.zip"
        if candidate.exists():
            resume_path = str(candidate)
            print(f"[train] auto-resume : modèle existant détecté ({candidate}).")

    if resume_path:
        print(f"[train] reprise depuis {resume_path}")
        model = PPO.load(resume_path, env=env, tensorboard_log=str(log_dir))
    else:
        print("[train] nouvel entraînement (départ de zéro).")
        model = PPO(
            policy="MlpPolicy",
            env=env,
            learning_rate=float(st.train_lr),
            n_steps=2048,
            batch_size=256,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.005,
            verbose=1,
            tensorboard_log=str(log_dir),
            seed=seed,
        )

    ckpt_cb = CheckpointCallback(
        save_freq=max(50_000 // n_envs, 1),
        save_path=str(out / "checkpoints"),
        name_prefix="skymind_ppo",
    )
    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=str(out),
        log_path=str(out / "eval"),
        eval_freq=max(20_000 // n_envs, 1),
        n_eval_episodes=5,
        deterministic=True,
    )

    print(f"[train] arène {st.arena_x:.1f}x{st.arena_y:.1f}x{st.arena_z:.1f} m, "
          f"{n_envs} env(s), {st.train_steps:,} pas, lr={st.train_lr:.0e}")
    model.learn(total_timesteps=int(st.train_steps), callback=[ckpt_cb, eval_cb])

    final_path = out / "skymind_ppo.zip"
    model.save(final_path)
    print(f"[train] modèle final -> {final_path}")
    env.close()
    eval_env.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--n-envs", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--out-dir", type=str, default="runs")
    args = ap.parse_args()

    st = Stt.current
    if args.steps is not None:
        st.train_steps = args.steps
    if args.n_envs is not None:
        st.train_n_envs = args.n_envs
    if args.seed is not None:
        st.train_seed = args.seed
    if args.no_resume:
        st.train_auto_resume = False
    run(st, out_dir=args.out_dir)


if __name__ == "__main__":
    main()
