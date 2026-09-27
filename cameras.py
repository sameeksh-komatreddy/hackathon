"""Camera sources for BackTrack.

Two slots feed the tracker: "front" (face and eyes) and "side" (posture).
Each slot is filled by a source: a local webcam ("local:<index>"), the
phone ("phone", frames pushed over Wi-Fi by phone_link), or nothing (None).

Every open source keeps only its latest frame, so the tracking loops always
work on the newest image and a slot can be switched to another source
without reopening anything in the tracking code.
"""
import json
import os
import platform
import threading
import time
from collections import namedtuple

import cv2

try:
    # Probing camera indices that don't exist makes OpenCV print a wall of
    # warnings on some platforms; real errors still come through.
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:
    pass


ROLES = ("front", "side")
PHONE = "phone"
STALE_AFTER = 2.0  # seconds without a new frame before a source counts as gone
FRAME_WIDTH, FRAME_HEIGHT = 640, 480

Frame = namedtuple("Frame", "image frame_id age source")


def local_id(index):
    return f"local:{index}"


def parse_local(source):
    if isinstance(source, str) and source.startswith("local:"):
        try:
            return int(source.split(":", 1)[1])
        except ValueError:
            return None
    return None


def capture_apis(system=None):
    """OpenCV capture drivers to try, best first, for this OS."""
    system = system or platform.system()
    if system == "Windows":
        # DirectShow opens in well under a second; Media Foundation can take
        # several but supports a few cameras DirectShow doesn't.
        return [cv2.CAP_DSHOW, cv2.CAP_MSMF]
    if system == "Darwin":
        return [cv2.CAP_AVFOUNDATION]
    if system == "Linux":
        return [cv2.CAP_V4L2]
    return [cv2.CAP_ANY]


def open_local_camera(index, system=None, opener=cv2.VideoCapture):
    """Open webcam `index` with the native driver, or return None.

    A camera only counts as open once it delivers a frame: some drivers
    report success for devices that never produce video (for example the
    metadata nodes Linux creates next to each webcam).
    """
    for api in capture_apis(system):
        cap = opener(index, api)
        if cap is None:
            continue
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
            ok, frame = cap.read()
            if ok and frame is not None:
                return cap
        cap.release()
    return None


def probe_local_cameras(max_index=4, skip=(), system=None, opener=cv2.VideoCapture):
    """Indices of webcams that deliver video. Indices in `skip` are already
    open elsewhere (opening them twice fails on most OSes) and are listed
    without being touched."""
    found = []
    for index in range(max_index):
        if index in skip:
            found.append(index)
            continue
        cap = open_local_camera(index, system=system, opener=opener)
        if cap is not None:
            cap.release()
            found.append(index)
    return found


def default_assignment(local_indices):
    """With one webcam it is the face view and the phone becomes the side
    view; with none, the phone is the face view."""
    local = sorted(local_indices)
    if not local:
        return {"front": PHONE, "side": None}
    if len(local) == 1:
        return {"front": local_id(local[0]), "side": PHONE}
    return {"front": local_id(local[0]), "side": local_id(local[1])}


def resolve_assignment(saved, local_indices):
    """Keep the saved choice for each slot while its source still exists;
    otherwise use the default for that slot."""
    defaults = default_assignment(local_indices)

    def valid(source):
        return source is None or source == PHONE or parse_local(source) in local_indices

    result = {}
    for role in ROLES:
        if isinstance(saved, dict) and role in saved and valid(saved[role]):
            result[role] = saved[role]
        else:
            result[role] = defaults[role]
    if result["front"] is not None and result["front"] == result["side"]:
        result["side"] = defaults["side"] if defaults["side"] != result["front"] else None
    return result


class FrameBuffer:
    """Holds the most recent frame from one source."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._image = None
        self._frame_id = 0
        self._stamp = 0.0

    def put(self, image):
        with self._lock:
            self._image = image
            self._frame_id += 1
            self._stamp = self._clock()

    def latest(self):
        with self._lock:
            return self._image, self._frame_id, self._stamp

    def age(self):
        with self._lock:
            if self._image is None:
                return float("inf")
            return self._clock() - self._stamp


class LocalCamera:
    """Reads a webcam on its own thread into a FrameBuffer."""

    def __init__(self, index, cap, clock=time.monotonic):
        self.index = index
        self.buffer = FrameBuffer(clock)
        self._cap = cap
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name=f"camera-{index}")
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            ok, frame = self._cap.read()
            if ok and frame is not None:
                self.buffer.put(frame)
            else:
                time.sleep(0.05)
        self._cap.release()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=2)


class CameraManager:
    def __init__(self, save_path=None, open_camera=open_local_camera,
                 probe=probe_local_cameras, clock=time.monotonic):
        self._save_path = save_path
        self._open_camera = open_camera
        self._probe = probe
        self._clock = clock
        self._lock = threading.RLock()
        self._open = {}          # index -> LocalCamera
        self._failed = set()     # indices that were assigned but wouldn't open
        self.available = []
        self.assignment = {role: None for role in ROLES}
        self.phone = FrameBuffer(clock)

    # ---- lifecycle ----

    def start(self):
        with self._lock:
            self.available = self._probe(skip=set())
            self.assignment = resolve_assignment(self._load(), self.available)
            self._sync()

    def rescan(self):
        with self._lock:
            self.available = self._probe(skip=set(self._open))
            self._failed.clear()
            self.assignment = resolve_assignment(self.assignment, self.available)
            self._sync()

    def close(self):
        with self._lock:
            for cam in self._open.values():
                cam.close()
            self._open.clear()

    # ---- choosing sources ----

    def sources(self):
        return [local_id(i) for i in self.available] + [PHONE]

    def assign(self, role, source):
        with self._lock:
            if role not in ROLES:
                raise ValueError(f"unknown camera slot: {role}")
            if source not in (None, PHONE) and parse_local(source) not in self.available:
                raise ValueError(f"unknown camera: {source}")
            other = "side" if role == "front" else "front"
            if source is not None and self.assignment[other] == source:
                self.assignment[other] = self.assignment[role]
            self.assignment[role] = source
            self._sync()
            self._save()

    def swap(self):
        with self._lock:
            self.assignment = {"front": self.assignment["side"],
                               "side": self.assignment["front"]}
            self._save()

    def role_of(self, source):
        with self._lock:
            for role in ROLES:
                if self.assignment[role] == source:
                    return role
        return None

    # ---- frames ----

    def phone_frame(self, image):
        self.phone.put(image)

    def phone_connected(self):
        return self.phone.age() <= STALE_AFTER

    def latest(self, role):
        """Newest frame for a slot, or None if it has no live source."""
        with self._lock:
            source = self.assignment.get(role)
            buf = self._buffer_for(source)
        if buf is None:
            return None
        image, frame_id, stamp = buf.latest()
        if image is None:
            return None
        age = self._clock() - stamp
        if age > STALE_AFTER:
            return None
        return Frame(image, frame_id, age, source)

    def status(self, role):
        """'none' (no source picked), 'live', 'waiting' (phone not sending)
        or 'unavailable' (webcam won't open or stopped sending)."""
        with self._lock:
            source = self.assignment.get(role)
        if source is None:
            return "none"
        if self.latest(role) is not None:
            return "live"
        return "waiting" if source == PHONE else "unavailable"

    def describe(self):
        with self._lock:
            return {
                "sources": [{"id": s, "label": "Phone" if s == PHONE else f"Camera {parse_local(s)}"}
                            for s in self.sources()],
                "assignment": dict(self.assignment),
                "status": {role: self.status(role) for role in ROLES},
                "phone_connected": self.phone_connected(),
            }

    # ---- internals ----

    def _buffer_for(self, source):
        if source == PHONE:
            return self.phone
        index = parse_local(source)
        cam = self._open.get(index)
        return cam.buffer if cam else None

    def _sync(self):
        """Open webcams that a slot needs and release the rest."""
        needed = {parse_local(s) for s in self.assignment.values()} - {None}
        for index in list(self._open):
            if index not in needed:
                self._open.pop(index).close()
        for index in needed:
            if index in self._open or index in self._failed:
                continue
            cap = self._open_camera(index)
            if cap is None:
                self._failed.add(index)
            else:
                self._open[index] = LocalCamera(index, cap, self._clock)

    def _load(self):
        if not self._save_path or not os.path.exists(self._save_path):
            return None
        try:
            with open(self._save_path) as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _save(self):
        if not self._save_path:
            return
        try:
            os.makedirs(os.path.dirname(self._save_path), exist_ok=True)
            with open(self._save_path, "w") as f:
                json.dump(self.assignment, f)
        except OSError as e:
            print(f"[BackTrack] couldn't save camera choice: {e}")
