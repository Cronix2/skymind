"""Point d'entrée Skymind.

Affiche le menu et lance le mode choisi (manuel / lecture IA / entraînement).

Lancement :
    python -m skymind
ou via deploy.sh :
    ./deploy.sh --launch
"""
from __future__ import annotations

from . import hangar as menu


def main():
    while True:
        mode, st = menu.run()
        if mode is None:
            return
        if mode == "manual":
            from . import main as _m
            _m.run(st)
        elif mode == "play":
            from . import play as _p
            _p.run(st)
        elif mode == "train":
            from . import train as _t
            _t.run(st)
        # Après que la simulation/entraînement se termine, on revient au menu.


if __name__ == "__main__":
    main()
