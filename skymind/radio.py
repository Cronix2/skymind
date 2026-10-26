"""USB HID radio input, shared by the hangar and flight loop."""
from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path
import pygame

PROFILE = Path(os.environ.get("SKYMIND_CONFIG_DIR", Path.home() / ".skymind")) / "radio.json"

@dataclass
class Axis:
    index: int = 0
    low: float = -1.0
    center: float = 0.0
    high: float = 1.0
    inverted: bool = False

    def value(self, raw, throttle=False):
        if throttle:
            v = max(0.0, min(1.0, (raw-self.low) / max(.01, self.high-self.low)))
            return 1-v if self.inverted else v
        span = self.high-self.center if raw >= self.center else self.center-self.low
        v = max(-1., min(1., (raw-self.center) / max(.01, span)))
        v = 0. if abs(v) < .04 else (1 if v > 0 else -1) * (abs(v)-.04)/.96
        return -v if self.inverted else v

class Radio:
    def __init__(self):
        pygame.joystick.init()
        self.device = None
        self.guid = None
        self.axes = {n: Axis(i) for i,n in enumerate(("roll", "pitch", "throttle", "yaw"))}
        self.calibrated = False
        self.armed = False
        self.message = "Radio absente • clavier disponible"
        try:
            data = json.loads(PROFILE.read_text(encoding="utf-8"))
            axes = {n: Axis(**data["axes"][n]) for n in self.axes}
            if any(a.index < 0 or not a.low < a.center < a.high for a in axes.values()):
                raise ValueError("Invalid calibration")
            self.axes = axes
            self.guid = data["guid"]
            self.calibrated = True
        except (OSError, ValueError, TypeError, KeyError):
            pass
        self.scan()

    def scan(self):
        if self.device is not None:
            return
        for i in range(pygame.joystick.get_count()):
            device = pygame.joystick.Joystick(i)
            if self.guid is None or device.get_guid() == self.guid:
                self.device = device
                self.armed = False
                break

    def event(self, event):
        if event.type == pygame.JOYDEVICEREMOVED and self.device and event.instance_id == self.device.get_instance_id():
            self.device = None
            self.armed = False
            self.message = "Radio débranchée • moteurs coupés"
        elif event.type == pygame.JOYDEVICEADDED:
            self.scan()

    def raw(self):
        if not self.device:
            return []
        try:
            return [self.device.get_axis(i) for i in range(self.device.get_numaxes())]
        except pygame.error:
            self.device = None
            self.armed = False
            return []

    def read(self):
        raw = self.raw()
        if not raw or not self.calibrated or any(a.index >= len(raw) for a in self.axes.values()):
            self.armed = False
            return dict(throttle=0., roll=0., pitch=0., yaw=0.)
        result = {n:a.value(raw[a.index], n == "throttle") for n,a in self.axes.items()}
        if not self.armed:
            self.message = "Baisser les gaz pour activer la radio"
            if result["throttle"] < .05:
                self.armed = True
                self.message = "Radio active"
            else:
                result = dict(throttle=0., roll=0., pitch=0., yaw=0.)
        return result

    def save(self):
        if not self.device:
            raise ValueError("Aucune radio connectée")
        PROFILE.parent.mkdir(parents=True, exist_ok=True)
        data = dict(guid=self.device.get_guid(), axes={n:asdict(a) for n,a in self.axes.items()})
        temp = PROFILE.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.replace(PROFILE)
        self.guid = data["guid"]
        self.calibrated = True
        self.armed = False
