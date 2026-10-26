"""Standalone bundle entry point."""
import multiprocessing
from skymind.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
