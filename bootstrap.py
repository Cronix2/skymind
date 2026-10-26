"""Portable source installer, using only the Python standard library."""
import argparse
from pathlib import Path
import subprocess
import sys
import venv

def main():
    parser=argparse.ArgumentParser(description="Install and launch SkyMind")
    parser.add_argument("--ai",action="store_true",help="Install optional AI dependencies")
    parser.add_argument("--install-only",action="store_true")
    args=parser.parse_args()
    if not (3,10)<=sys.version_info[:2]<(3,13):
        parser.exit(1,"SkyMind requires Python 3.10–3.12. Install Python 3.12 and retry.\n")
    root=Path(__file__).resolve().parent
    env=root/".venv"
    if not env.exists():
        venv.create(env,with_pip=True)
    python=env/("Scripts/python.exe" if sys.platform=="win32" else "bin/python")
    target=str(root)+("[ai]" if args.ai else "")
    subprocess.run([str(python),"-m","pip","install","-e",target],check=True,cwd=root)
    if not args.install_only:
        subprocess.run([str(python),"-m","skymind"],check=True,cwd=root)

if __name__=="__main__":
    main()
