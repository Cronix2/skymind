import os
os.environ["SDL_VIDEODRIVER"]="dummy"
os.environ["SDL_AUDIODRIVER"]="dummy"
import unittest
from unittest.mock import patch, Mock
from pathlib import Path
from tempfile import TemporaryDirectory
import pygame
from skymind.radio import Axis, Radio

class RadioTests(unittest.TestCase):
    def test_profile_roundtrip_and_hotplug(self):
        with TemporaryDirectory() as folder, patch("skymind.radio.PROFILE",Path(folder)/"radio.json"), patch("pygame.joystick.get_count",return_value=0):
            radio=Radio()
            device=Mock()
            device.get_guid.return_value="test-guid"
            device.get_instance_id.return_value=42
            radio.device=device
            radio.axes["pitch"].inverted=True
            radio.save()
            loaded=Radio()
            self.assertTrue(loaded.calibrated)
            self.assertTrue(loaded.axes["pitch"].inverted)
            self.assertEqual(loaded.guid,"test-guid")
            radio.armed=True
            radio.event(pygame.event.Event(pygame.JOYDEVICEREMOVED,instance_id=42))
            self.assertIsNone(radio.device)
            self.assertFalse(radio.armed)

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
