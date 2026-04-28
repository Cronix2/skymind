#!/usr/bin/env bash
# Deploy / setup script pour Skymind.
#
# Usage :
#   ./deploy.sh                # lance le menu (installe seulement la 1ère fois)
#   ./deploy.sh --launch       # idem
#   ./deploy.sh --reinstall    # supprime .venv puis recrée tout, puis lance
#
# Compatible Linux / macOS / Git Bash sur Windows / WSL.

set -euo pipefail

# --- Config ---------------------------------------------------------------
VENV_DIR=".venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REQ_FILE="requirements.txt"
INSTALL_MARKER=".venv/.skymind_installed"   # touché après une install réussie

REINSTALL=0

for arg in "$@"; do
  case "$arg" in
    --launch) ;;                       # défaut, rien à faire
    --reinstall) REINSTALL=1 ;;
    -h|--help)
      sed -n '2,9p' "$0"
      exit 0
      ;;
    *)
      echo "Argument inconnu : $arg" >&2
      exit 1
      ;;
  esac
done

# --- Helpers --------------------------------------------------------------
log() { printf '\033[1;36m[skymind]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[skymind]\033[0m %s\n' "$*" >&2; }

cd "$(dirname "$0")"

# Détection Python
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    err "Python introuvable. Installe Python 3.10+ et relance."
    exit 1
  fi
fi

# Chemins venv
if [[ "${OS:-}" == "Windows_NT" || -d "$VENV_DIR/Scripts" ]]; then
  VENV_PY="$VENV_DIR/Scripts/python.exe"
else
  VENV_PY="$VENV_DIR/bin/python"
fi

# --- Reinstall -----------------------------------------------------------
if [[ "$REINSTALL" -eq 1 && -d "$VENV_DIR" ]]; then
  log "Suppression du venv existant..."
  rm -rf "$VENV_DIR"
fi

# --- Installation (uniquement si nécessaire) -----------------------------
NEED_INSTALL=0
if [[ ! -d "$VENV_DIR" ]]; then
  NEED_INSTALL=1
elif [[ ! -f "$INSTALL_MARKER" ]]; then
  NEED_INSTALL=1
elif [[ "$REQ_FILE" -nt "$INSTALL_MARKER" ]]; then
  log "requirements.txt modifié, réinstallation des dépendances..."
  NEED_INSTALL=1
fi

if [[ "$NEED_INSTALL" -eq 1 ]]; then
  if [[ ! -d "$VENV_DIR" ]]; then
    PY_VERSION=$("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
    log "Création du venv ($PYTHON_BIN $PY_VERSION) dans $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  # Recalcule les chemins après création
  if [[ -d "$VENV_DIR/Scripts" ]]; then
    VENV_PY="$VENV_DIR/Scripts/python.exe"
  else
    VENV_PY="$VENV_DIR/bin/python"
  fi

  log "Mise à jour de pip..."
  "$VENV_PY" -m pip install --upgrade pip >/dev/null

  PIP_FLAGS=()
  if [[ "$PWD" == /mnt/* ]]; then
    log "Détecté /mnt/* (WSL on NTFS) : --no-compile."
    PIP_FLAGS+=(--no-compile)
  fi

  log "Installation de torch (CPU-only)..."
  "$VENV_PY" -m pip install "${PIP_FLAGS[@]}" \
    --index-url https://download.pytorch.org/whl/cpu \
    "torch>=2.1"

  if [[ -f "$REQ_FILE" ]]; then
    log "Installation des dépendances ($REQ_FILE)..."
    "$VENV_PY" -m pip install "${PIP_FLAGS[@]}" -r "$REQ_FILE"
  else
    err "Fichier $REQ_FILE introuvable."
    exit 1
  fi

  touch "$INSTALL_MARKER"
  log "Installation terminée."
else
  log "Venv prêt, dépendances déjà installées."
fi

# --- Lancement -----------------------------------------------------------
log "Lancement du menu Skymind..."
exec "$VENV_PY" -m skymind
