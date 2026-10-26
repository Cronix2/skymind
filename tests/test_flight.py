"""Exercise the real physics/render loop when PyBullet is installed."""
import importlib.util
import os
os.environ["SDL_VIDEODRIVER"]="dummy"
os.environ["SDL_AUDIODRIVER"]="dummy"
import unittest
from unittest.mock import patch
import pygame

@unittest.skipUnless(importlib.util.find_spec("pybullet"), "PyBullet not installed")
class FlightTests(unittest.TestCase):
    def test_manual_and_radio_without_device(self):
        from skymind.main import run
        from skymind.settings import Settings
        import pybullet
        for mode in ("Clavier", "Radio USB"):
            def close_after_frame():
                pygame.event.post(pygame.event.Event(pygame.QUIT))
            with patch("pygame.display.flip",side_effect=close_after_frame):
                run(Settings(input_mode=mode))
            self.assertFalse(pybullet.isConnected())
