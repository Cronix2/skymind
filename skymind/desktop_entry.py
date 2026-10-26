"""Standalone bundle entry point."""
import multiprocessing
import sys
from skymind.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if "--smoke-test" in sys.argv:
        import pygame
        from skymind.main import run
        from skymind.settings import Settings
        def close_after_frame():
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        pygame.display.flip=close_after_frame
        run(Settings())
    else:
        main()
