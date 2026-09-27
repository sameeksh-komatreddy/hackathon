import time

import cv2
import numpy as np
import pytest

import cameras
from cameras import PHONE, CameraManager, FrameBuffer
from fakes import FakeCapture, FakeClock


# ---------------- opening webcams on each OS ----------------

@pytest.mark.parametrize("system, first_api", [
    ("Windows", cv2.CAP_DSHOW),
    ("Darwin", cv2.CAP_AVFOUNDATION),
    ("Linux", cv2.CAP_V4L2),
])
def test_open_local_camera_uses_the_native_driver_for_each_os(system, first_api):
    tried = []

    def opener(index, api):
        tried.append((index, api))
        return FakeCapture(works=True)

    cap = cameras.open_local_camera(2, system=system, opener=opener)

    assert cap is not None
    assert tried == [(2, first_api)]


def test_open_local_camera_falls_back_to_media_foundation_on_windows():
    made = {}

    def opener(index, api):
        made[api] = FakeCapture(works=(api == cv2.CAP_MSMF))
        return made[api]

    cap = cameras.open_local_camera(0, system="Windows", opener=opener)

    assert cap is made[cv2.CAP_MSMF]
    assert made[cv2.CAP_DSHOW].released


def test_open_local_camera_returns_none_when_nothing_delivers_frames():
    caps = []

    def opener(index, api):
        caps.append(FakeCapture(works=False))
        return caps[-1]

    assert cameras.open_local_camera(5, system="Windows", opener=opener) is None
    assert caps and all(c.released for c in caps)


def test_probe_skips_cameras_already_open_but_still_lists_them():
    opened = []

    def opener(index, api):
        opened.append(index)
        return FakeCapture(works=index in (0, 1))

    found = cameras.probe_local_cameras(max_index=4, skip={0}, system="Linux", opener=opener)

    assert found == [0, 1]
    assert 0 not in opened


# ---------------- which camera goes in which slot ----------------

@pytest.mark.parametrize("local, front, side", [
    ([], PHONE, None),
    ([0], "local:0", PHONE),          # one webcam -> it is the face view
    ([0, 1], "local:0", "local:1"),
    ([2], "local:2", PHONE),
])
def test_default_assignment(local, front, side):
    assert cameras.default_assignment(local) == {"front": front, "side": side}


def test_resolve_keeps_a_saved_swap_when_both_cameras_still_exist():
    saved = {"front": "local:1", "side": "local:0"}
    assert cameras.resolve_assignment(saved, [0, 1]) == saved


def test_resolve_falls_back_to_defaults_when_saved_camera_is_gone():
    saved = {"front": "local:1", "side": "local:0"}
    assert cameras.resolve_assignment(saved, [0]) == {"front": "local:0", "side": PHONE}


def test_resolve_keeps_an_explicitly_empty_slot():
    saved = {"front": "local:0", "side": None}
    assert cameras.resolve_assignment(saved, [0, 1]) == {"front": "local:0", "side": None}


# ---------------- the manager ----------------

def make_manager(tmp_path, local=(0,), clock=None):
    caps = {}

    def open_camera(index):
        if index not in local:
            return None
        caps[index] = FakeCapture()
        return caps[index]

    def probe(skip=()):
        return sorted(local)

    mgr = CameraManager(save_path=str(tmp_path / "cameras.json"),
                        open_camera=open_camera, probe=probe,
                        clock=clock or time.monotonic)
    mgr.start()
    return mgr, caps


def test_single_webcam_starts_as_front_and_side_waits_for_phone(tmp_path):
    mgr, _ = make_manager(tmp_path, local=(0,))
    try:
        assert mgr.assignment == {"front": "local:0", "side": PHONE}
        deadline = time.time() + 2
        while mgr.latest("front") is None and time.time() < deadline:
            time.sleep(0.01)
        assert mgr.latest("front").source == "local:0"
        assert mgr.latest("side") is None
        assert mgr.status("side") == "waiting"
    finally:
        mgr.close()


def test_assigning_a_source_used_by_the_other_slot_swaps_them(tmp_path):
    mgr, _ = make_manager(tmp_path, local=(0,))
    try:
        mgr.assign("side", "local:0")
        assert mgr.assignment == {"front": PHONE, "side": "local:0"}
    finally:
        mgr.close()


def test_assigning_an_unknown_source_is_rejected(tmp_path):
    mgr, _ = make_manager(tmp_path, local=(0,))
    try:
        with pytest.raises(ValueError):
            mgr.assign("front", "local:7")
        with pytest.raises(ValueError):
            mgr.assign("top", PHONE)
    finally:
        mgr.close()


def test_unused_webcam_is_released(tmp_path):
    mgr, caps = make_manager(tmp_path, local=(0,))
    try:
        mgr.assign("front", None)
        assert caps[0].released
    finally:
        mgr.close()


def test_assignment_is_remembered_across_restarts(tmp_path):
    mgr, _ = make_manager(tmp_path, local=(0, 1))
    mgr.swap()
    mgr.close()

    again, _ = make_manager(tmp_path, local=(0, 1))
    try:
        assert again.assignment == {"front": "local:1", "side": "local:0"}
    finally:
        again.close()


def test_phone_frames_feed_the_slot_the_phone_is_in_until_they_go_stale(tmp_path):
    clock = FakeClock()
    mgr, _ = make_manager(tmp_path, local=(0,), clock=clock)
    try:
        img = np.full((360, 640, 3), 7, np.uint8)
        mgr.phone_frame(img)

        frame = mgr.latest("side")
        assert frame.source == PHONE
        assert frame.image[0, 0, 0] == 7
        assert mgr.status("side") == "live"
        assert mgr.role_of(PHONE) == "side"

        clock.now += cameras.STALE_AFTER + 0.5
        assert mgr.latest("side") is None
        assert mgr.status("side") == "waiting"
    finally:
        mgr.close()


def test_frame_buffer_counts_frames():
    buf = FrameBuffer(clock=FakeClock(5.0))
    assert buf.latest() == (None, 0, 0.0)
    buf.put("a")
    buf.put("b")
    assert buf.latest() == ("b", 2, 5.0)
