import time

import numpy as np


class FakeCapture:
    """Stands in for cv2.VideoCapture: either delivers frames or doesn't."""

    def __init__(self, works=True):
        self.works = works
        self.released = False

    def isOpened(self):
        return self.works

    def read(self):
        if not self.works or self.released:
            return False, None
        time.sleep(0.005)
        return True, np.zeros((480, 640, 3), np.uint8)

    def set(self, prop, value):
        return True

    def release(self):
        self.released = True


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now
