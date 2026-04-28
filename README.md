# Skymind

Simulateur de drone 3D en Python avec une IA qui apprend à voler par
renforcement (PPO). Une seule fenêtre pygame pour tout : rendu logiciel
custom, HUD, retour vidéo FPV embarqué, et physique PyBullet en arrière-plan.

## Sommaire

- [Skymind](#skymind)
  - [Sommaire](#sommaire)
  - [Aperçu](#aperçu)
  - [Installation](#installation)
  - [Lancement](#lancement)
  - [Pilotage manuel](#pilotage-manuel)
  - [Entraînement de l'IA](#entraînement-de-lia)
    - [Lancer un entraînement](#lancer-un-entraînement)
    - [Visualiser l'agent](#visualiser-lagent)
  - [Architecture](#architecture)
  - [Roadmap](#roadmap)

## Aperçu

- Arène 10×10×10 m fermée par 6 parois (collisions épaisses, anti-tunneling).
- Drone quadrirotor en X (4 moteurs, modèle de poussée + couple yaw, lissage
  premier ordre). Masse 0.5 kg, T/W = 2.2.
- Physique PyBullet à 480 Hz (8 substeps par frame), rendu pygame à 60 FPS.
- Rendu 3D logiciel custom (pas d'OpenGL) : projection pinhole, clipping
  Sutherland–Hodgman, painter's algorithm, ombrage Lambert. Caméra principale
  fixe en oblique depuis l'extérieur de la boîte (les murs avant sont cull).
- HUD intégré : barre verticale de gaz (0–100 %), indicateur de lacet, stick
  tangage/roulis, panneau télémétrie (position, vitesse, angles, gyro, accéléro,
  PWM moteurs), **écran FPV embarqué** sur le nez du drone (orientable I/K),
  panneau **Sensibilité** (menu déroulant + diagramme rate/expo) et panneau
  **Dynamique** (menu déroulant masse / inertie / délai moteur).
- Cible verte respawnée aléatoirement à chaque atteinte.
- Modèle de crash : touche un mur → moteurs coupés définitivement, le drone
  tombe ; au sol à l'envers → grosse pénalité (RL) / reset (manuel) ;
  atterrissage doux à l'endroit → aucune pénalité.

## Installation

Le script `deploy.sh` gère le venv et installe les dépendances. Compatible
Linux, macOS et Git Bash / WSL sous Windows.

```bash
./deploy.sh                 # crée .venv et installe tout
./deploy.sh --reinstall     # repart d'un venv vierge
```

Notes :

- `torch` est installé en version **CPU only** (≈ 200 Mo, depuis l'index
  PyTorch CPU). Pas de CUDA tiré inutilement — PPO + MlpPolicy + 4 envs
  parallèles tournent largement assez vite sur CPU.
- En WSL depuis `/mnt/c/...`, le script ajoute automatiquement
  `pip install --no-compile` pour contourner un bug `.pyc` sur NTFS.
- Pour de meilleures performances, cloner le repo dans le filesystem WSL
  natif (`~/skymind`) plutôt que `/mnt/c/...`.

## Lancement

```bash
./deploy.sh --run     # pilotage manuel clavier
./deploy.sh --train   # entraînement PPO (sans fenêtre)
./deploy.sh --play    # regarder l'IA piloter (charge runs/skymind_ppo.zip)
```

Équivalents Python directs (avec venv activé) :

```bash
python -m skymind.main
python -m skymind.train
python -m skymind.play
```

## Pilotage manuel

Mode 2 RC, sticks émulés au clavier :

| Touche      | Action                                      |
|-------------|---------------------------------------------|
| `Z` / `W`   | Gaz +                                       |
| `S`         | Gaz −                                       |
| `Q` / `D`   | Lacet gauche / droite                       |
| `↑` / `↓`   | Tangage avant / arrière                     |
| `←` / `→`   | Roulis gauche / droite                      |
| `I` / `K`   | Tilt de la caméra FPV (haut / bas)          |
| `J`         | Recentrer la caméra FPV                     |
| `R`         | Reset position + nouvelle cible             |
| `Échap`     | Quitter                                     |

Le gaz se comporte comme un vrai stick : il **reste** où on l'a laissé. À 0 %,
les moteurs sont coupés (chute libre). Aux alentours de 45 % on stationne.

Code couleur du drone, pour s'orienter :

- bras **avant rouges**, bras **arrière blancs** ;
- toit blanc avec un petit triangle rouge pointant vers l'avant
  (visible depuis le haut comme depuis la FPV).

## Entraînement de l'IA

L'environnement `SkymindEnv` (dans [skymind/env.py](skymind/env.py)) suit
l'API Gymnasium et est utilisé par
[skymind/train.py](skymind/train.py) avec PPO (Stable-Baselines3).

- **Action** : `Box([-1, 1]^4)` = `(roll, pitch, yaw, throttle_raw)`.
  Le throttle est remappé en `[0, 1]`. Roll/pitch/yaw passent par la **courbe
  de sensibilité** de l'épisode (tirée aléatoirement) avant d'être envoyés
  au drone : l'IA apprend donc à piloter sous des réglages stick variables.
- **Observation** : vecteur **22D** normalisé, *invariant à l'orientation monde* :
  cible relative en repère drone (3), vitesse linéaire repère drone (3),
  gyroscope (3), gravité vue par le drone (3), commandes moteurs précédentes (4),
  **(rate, expo) normalisés (2)**, **(masse, inertie_xy, inertie_z, tau_moteur)
  normalisés (4)**.
- **Récompense** :
  - dense : $-d \cdot dt$ (pénalise la distance qui dure) ;
  - shaping : $+5 \cdot (d_{prev} - d_{now})$ (avancer = bon) ;
  - smoothness : $-0.005 \cdot \lVert a_t - a_{t-1} \rVert^2$ ;
  - succès (cible à < 0.45 m) : **+100** + bonus de rapidité ;
  - **mur** : `-5` fixe `-8 · v` au moment de l'impact, *moteurs coupés* pour
    le reste de l'épisode (le drone tombe en chute libre) ;
  - **sol à l'envers** : `-40` + fin d'épisode ;
  - **sol violent** (vitesse > 1 m/s à l'endroit) : `-4 · (v - 1)` par m/s
    d'excès ;
  - **sol doux à l'endroit** : 0 (atterrissage propre toléré).
- **Épisode** : 15 s × 60 Hz = 900 pas max, terminé sur succès / crash,
  tronqué sinon.

### Lancer un entraînement

```bash
# Entraînement par défaut : 1M de pas, 4 envs en parallèle (SubprocVecEnv)
python -m skymind.train

# Test rapide pour valider la chaîne (~quelques minutes sur CPU)
python -m skymind.train --steps 100000 --n-envs 4

# Reprendre un run existant (chemin explicite)
python -m skymind.train --resume runs/skymind_ppo.zip

# Reprendre automatiquement runs/skymind_ppo.zip s'il existe, sinon nouveau
python -m skymind.train --auto-resume
```

> **⚠️** Sans `--resume` ni `--auto-resume`, l'entraînement repart à zéro
> et **écrase** `runs/skymind_ppo.zip` à la fin.

Sortie :

```txt
runs/
├── skymind_ppo.zip          # modèle final
├── best_model.zip           # meilleur modèle d'évaluation
├── checkpoints/             # snapshots réguliers
├── eval/                    # logs Monitor
└── tb/                      # logs TensorBoard
```

Suivi en direct :

```bash
tensorboard --logdir runs/tb
```

### Visualiser l'agent

```bash
python -m skymind.play                       # charge runs/skymind_ppo.zip
python -m skymind.play --model path.zip
python -m skymind.play --deterministic 0     # politique stochastique
```

Dans la fenêtre, **espace** met en pause, **R** régénère la cible, et la
caméra FPV reste pilotable au clavier.

## Architecture

```txt
skymind/
├── config.py     # toutes les constantes (physique, couleurs, FPV, etc.)
├── arena.py      # boîte de collision PyBullet
├── drone.py      # modèle quadrotor + IMU simulée
├── controls.py   # clavier -> sticks (mode 2 RC)
├── renderer.py   # rendu 3D logiciel pygame (cam principale + FPV)
├── hud.py        # overlay 2D : gaz, lacet, stick droit, télémétrie, FPV
├── main.py       # boucle pilotage manuel
├── env.py        # SkymindEnv (Gymnasium)
├── train.py      # entraînement PPO
└── play.py       # lecture d'un modèle entraîné
```

Disposition de la fenêtre :

```txt
+------------------------------------------------------------+
|  legende + titre                                    FPS    |
|                                                            |
|              rendu 3D (caméra extérieure)                  |
|                                                            |
|  GAZ | LACET |  TELEMETRIE  |  FPV (caméra drone)  | STICK |
+------------------------------------------------------------+
```

## Roadmap

- [x] Simulation manuelle clavier
- [x] HUD complet + FPV embarquée
- [x] Wrapper Gymnasium
- [x] Entraînement PPO (vecteur d'état)
- [x] Domain randomization de la sensibilité stick (rate / expo)
- [x] Domain randomization de la masse / inertie / délai moteur
- [x] Modèle de crash : coupure moteurs sur impact mur, pénalités différenciées
- [ ] Politique CNN sur l'image FPV en plus du vecteur d'état
- [ ] Obstacles dans l'arène
- [ ] Plusieurs cibles successives par épisode
