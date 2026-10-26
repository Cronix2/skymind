import os
os.environ["SDL_VIDEODRIVER"]="dummy"
os.environ["SDL_AUDIODRIVER"]="dummy"
import unittest
from unittest.mock import patch
import pygame
from skymind.radio import Axis, Radio

class RadioTests(unittest.TestCase):
    def test_calibrated_ranges(self):
        a=Axis(low=-.8,center=.1,high=.9)
        self.assertEqual(a.value(.1),0)
        self.assertEqual(a.value(-.8),-1)
        self.assertEqual(a.value(.9),1)
        self.assertEqual(a.value(-.8,True),0)
        self.assertEqual(a.value(.9,True),1)
        a.inverted=True
        self.assertEqual(a.value(.9,True),0)

    def test_wait_for_low_throttle_and_disconnect(self):
        with patch("skymind.radio.PROFILE") as profile, patch("pygame.joystick.get_count",return_value=0):
            profile.read_text.side_effect=OSError
            radio=Radio()
        radio.calibrated=True
        radio.raw=lambda:[0.,0.,1.,0.]
        self.assertEqual(radio.read()["throttle"],0)
        self.assertFalse(radio.armed)
        radio.raw=lambda:[0.,0.,-1.,0.]
        radio.read()
        self.assertTrue(radio.armed)
        radio.raw=lambda:[0.,0.,1.,0.]
        self.assertEqual(radio.read()["throttle"],1)
        radio.raw=lambda:[]
        self.assertEqual(radio.read()["throttle"],0)
        self.assertFalse(radio.armed)

if __name__=="__main__": unittest.main()
