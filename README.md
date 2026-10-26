# SkyMind · Flight deck

Simulateur FPV local en Python : hangar interactif, pilotage acro, physique PyBullet et radio USB HID (RadioMaster Pocket ou autre joystick). La simulation existante et ses modèles sont conservés ; le nouveau parcours remplace le menu d’accueil.

## Démarrer

Prérequis source : Python 3.10 à 3.12, conseillé **3.11**, connexion Internet au premier lancement. PyBullet peut nécessiter un compilateur C++ lorsque sa distribution binaire n’existe pas pour votre système/version Python.

- Windows : installez Python 3.12 puis double-cliquez `Start-SkyMind.cmd`.
- macOS / Linux : `bash deploy.sh`.
- Tous : `python bootstrap.py` (depuis le dossier du projet).

Le lanceur crée un environnement isolé et installe seulement le simulateur. Pas de PyTorch pour le vol manuel.

IA facultative : `python bootstrap.py --ai --install-only`, puis relancez. Cette option télécharge les dépendances Gymnasium, Stable-Baselines3 et PyTorch via pip ; la taille dépend de votre plateforme. Les modèles restent dans `runs/`, relativement au dossier de lancement. Lancez depuis la racine du dépôt pour retrouver les modèles fournis.

## Brancher la RadioMaster Pocket

1. Allumez la radio et branchez son port USB de données avec un câble de données.
2. Choisissez **USB Joystick (HID)** sur la radio.
3. Dans le hangar, ouvrez **Radio / Connexion et calibration**.
4. Bougez un seul stick à la fois pour repérer son axe dans les barres. Attribuez quatre axes distincts à roll, pitch, throttle et yaw ; inversez le sens si nécessaire.
5. Centrez tous les sticks, gaz compris, et démarrez la calibration. Parcourez toutes les extrémités puis sauvegardez.
6. Sélectionnez **Radio USB**, lancez le vol et baissez les gaz pour activer les commandes.

Le profil est enregistré dans `~/.skymind/radio.json` (ou le dossier `SKYMIND_CONFIG_DIR`). Une modification d’axe exige une nouvelle calibration. La radio doit être reconnue par le système comme joystick. La coupure USB met toutes les commandes à zéro et demande à nouveau des gaz bas après reconnexion. Aucun basculement automatique vers le clavier pendant un vol radio.

Clavier : Z/W et S pour les gaz, Q/D pour le lacet, flèches pour tangage/roulis. R réinitialise, V bascule FPV / vue extérieure, I/K oriente la caméra, Échap revient au hangar. Le clavier reste disponible pour ces raccourcis en mode radio.

## Distribution et validation

Le workflow `Desktop builds` prépare des dossiers autonomes avec PyInstaller pour Windows, Linux x86-64 et macOS. Téléchargez l’artefact de votre plateforme après un build réussi ; les builds doivent encore être vérifiés sur chaque système avant publication. Les bundles couvrent le simulateur manuel, pas l’IA facultative. Il n’y a pas encore de signature, de mises à jour automatiques ni d’installateur mobile/console. Raspberry Pi, Android et iOS ne sont pas validés.

Tests : `python -m unittest discover -s tests -v`. Les tests couvrent la conversion des axes et le verrouillage des gaz ; une validation matérielle Pocket reste nécessaire.

Les détails de la physique, de l’entraînement et de l’architecture originale sont dans [docs/legacy.md](docs/legacy.md).
