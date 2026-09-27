import time

import cv2
import numpy as np
import pytest

import backend_pm as bp
from cameras import PHONE, CameraManager
from fakes import FakeCapture


@pytest.fixture
def backend(tmp_path, monkeypatch):
    """backend_pm with its data folder, accounts, sessions and live state
    isolated in a temp dir, notifications silenced and no real cameras."""
    monkeypatch.setattr(bp, "MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(bp, "SESSIONS_FILE", str(tmp_path / "sessions.json"))
    monkeypatch.setattr(bp, "USERS_FILE", str(tmp_path / "users.json"))
    monkeypatch.setattr(bp, "users", {})
    monkeypatch.setattr(bp, "tokens", {})
    monkeypatch.setattr(bp, "sessions", [])
    monkeypatch.setattr(bp, "state", dict(bp.state))
    monkeypatch.setattr(bp, "recording_active", False)
    monkeypatch.setattr(bp, "current_session_accum", None)
    monkeypatch.setattr(bp, "send_desktop_notification", lambda title, msg: None)
    # The tracking threads don't run in tests; give the feeds a frame so a
    # streaming response has a first chunk to send.
    monkeypatch.setattr(bp, "front_frame", jpeg_bytes())
    monkeypatch.setattr(bp, "side_frame", jpeg_bytes())
    use_cameras(monkeypatch, local=())
    return bp


def use_cameras(monkeypatch, local):
    mgr = CameraManager(save_path=None,
                        open_camera=lambda i: FakeCapture() if i in local else None,
                        probe=lambda skip=(): sorted(local))
    mgr.start()
    monkeypatch.setattr(bp, "camera_manager", mgr)
    return mgr


@pytest.fixture
def client(backend):
    return backend.app.test_client()


def signup(client, username="sam"):
    resp = client.post("/auth/signup", json={"username": username, "password": "secret1"})
    return resp.get_json()["token"]


def auth(token):
    return {"Authorization": "Bearer " + token}


def jpeg_bytes():
    ok, buf = cv2.imencode(".jpg", np.full((360, 640, 3), 90, np.uint8))
    return buf.tobytes()


# ---------------- item 2: camera feeds need your login ----------------

@pytest.mark.parametrize("path", ["/feed/front", "/feed/side", "/stream"])
def test_feeds_and_live_stream_refuse_requests_without_login(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path, mimetype", [
    ("/feed/front", "multipart/x-mixed-replace"),
    ("/feed/side", "multipart/x-mixed-replace"),
    ("/stream", "text/event-stream"),
])
def test_feeds_accept_the_login_token_in_the_url(client, path, mimetype):
    # <img> and EventSource can't send an Authorization header.
    token = signup(client)
    resp = client.get(f"{path}?token={token}")
    try:
        assert resp.status_code == 200
        assert resp.mimetype == mimetype
    finally:
        resp.close()


def test_feed_refuses_a_made_up_token(client):
    signup(client)
    assert client.get("/feed/front?token=not-a-real-token").status_code == 401


@pytest.mark.parametrize("path", ["/recalibrate", "/recalibrate_front", "/recalibrate_side"])
def test_recalibrate_requires_login(client, path):
    assert client.post(path).status_code == 401
    assert client.post(path, headers=auth(signup(client, "u" + path[-4:]))).status_code == 200


def test_requests_addressed_to_another_host_name_are_refused(client):
    # Blocks DNS-rebinding: a website pointing its own domain at 127.0.0.1.
    assert client.get("/", headers={"Host": "evil.example:5050"}).status_code == 403
    assert client.get("/", headers={"Host": "127.0.0.1:5050"}).status_code == 200
    assert client.get("/", headers={"Host": "localhost:5050"}).status_code == 200


@pytest.mark.parametrize("origin, allowed", [
    ("https://evil.example", None),
    ("http://127.0.0.1.evil.example", None),
    ("null", "null"),                              # the page opened from a file
    ("http://localhost:8000", "http://localhost:8000"),
    ("http://127.0.0.1:5500", "http://127.0.0.1:5500"),
])
def test_only_local_pages_may_read_responses(client, origin, allowed):
    resp = client.get("/", headers={"Origin": origin})
    assert resp.headers.get("Access-Control-Allow-Origin") == allowed


# ---------------- camera slots ----------------

def test_cameras_endpoint_requires_login(client):
    assert client.get("/cameras").status_code == 401


def test_one_webcam_is_the_front_camera_and_phone_is_side(client, monkeypatch):
    use_cameras(monkeypatch, local=(0,))
    data = client.get("/cameras", headers=auth(signup(client))).get_json()

    assert data["assignment"] == {"front": "local:0", "side": PHONE}
    assert [s["id"] for s in data["sources"]] == ["local:0", PHONE]
    assert data["status"]["side"] == "waiting"


def test_cameras_can_be_reassigned_and_swapped(client, monkeypatch):
    use_cameras(monkeypatch, local=(0,))
    h = auth(signup(client))

    data = client.post("/cameras", json={"side": "local:0"}, headers=h).get_json()
    assert data["assignment"] == {"front": PHONE, "side": "local:0"}

    data = client.post("/cameras/swap", headers=h).get_json()
    assert data["assignment"] == {"front": "local:0", "side": PHONE}

    resp = client.post("/cameras", json={"front": "local:9"}, headers=h)
    assert resp.status_code == 400


# ---------------- phone link ----------------

def test_phone_link_gives_an_https_url_with_the_current_code_and_a_qr(client, monkeypatch):
    monkeypatch.setattr(bp.phone_link, "lan_addresses", lambda: ["192.168.1.20", "172.20.0.1"])
    data = client.get("/phone/link", headers=auth(signup(client))).get_json()

    code = bp.pairing.code
    assert data["url"] == f"https://192.168.1.20:5051/?code={code}"
    assert data["alternates"] == [f"https://172.20.0.1:5051/?code={code}"]
    assert data["qr_svg"].lstrip().startswith("<svg")


def test_phone_link_explains_when_there_is_no_network(client, monkeypatch):
    monkeypatch.setattr(bp.phone_link, "lan_addresses", lambda: [])
    data = client.get("/phone/link", headers=auth(signup(client))).get_json()
    assert data["url"] is None
    assert data["error"]


def test_new_phone_code_cancels_the_old_link(client, monkeypatch):
    monkeypatch.setattr(bp.phone_link, "lan_addresses", lambda: ["192.168.1.20"])
    old = bp.pairing.code
    data = client.post("/phone/link/new", headers=auth(signup(client))).get_json()

    assert old not in data["url"]
    assert not bp.pairing.matches(old)


def test_phone_link_requires_login(client):
    assert client.get("/phone/link").status_code == 401
    assert client.post("/phone/link/new").status_code == 401


def test_frames_from_the_phone_fill_the_side_slot(backend, monkeypatch):
    use_cameras(monkeypatch, local=(0,))
    phone = bp.phone_app.test_client()

    resp = phone.post("/frame", data=jpeg_bytes(), headers={"X-Pair-Code": bp.pairing.code})

    assert resp.get_json() == {"ok": True, "role": "side"}
    frame = bp.camera_manager.latest("side")
    assert frame is not None and frame.source == PHONE


# ---------------- item 3: one-camera sessions still count ----------------

def test_posture_score_from_the_front_camera_alone():
    cfg = dict(bp.DEFAULT_SETTINGS)
    # head pitch 40 is 15 over the 25 threshold -> 15 * 0.5 = 7.5 off
    assert bp.compute_posture_score(None, None, 40.0, 0.0, False, cfg) == 92.5


def test_posture_score_from_the_side_camera_alone():
    cfg = dict(bp.DEFAULT_SETTINGS)
    # neck 30 is 10 over the 20 threshold -> 10 * 1.5 = 15 off
    assert bp.compute_posture_score(30.0, 10.0, None, None, None, cfg) == 85.0


def record_one_tick(client, token, **readings):
    assert client.post("/session/start", headers=auth(token)).status_code == 200
    bp.state.update(readings)
    bp.alert_tick(time.time())
    return client.post("/session/stop", headers=auth(token)).get_json()["session"]


def test_front_camera_only_session_gets_posture_and_eye_scores(client):
    s = record_one_tick(client, signup(client),
                        face_seen=True, calibrated_front=True, calibrated_side=False,
                        pitch=40.0, roll=0.0, ear=0.30, blink_rate=20.0,
                        neck_angle=0.0, torso_angle=0.0)

    assert s["posture_score"] == 92.5
    assert s["eye_strain_index"] == 0.0
    assert s["avg_neck_angle"] is None
    assert s["posture_breakdown"]["pitch"] == 7.5
    assert s["posture_breakdown"]["neck"] is None
    assert s["cameras_used"] == {"front": True, "side": False}


def test_side_camera_only_session_has_posture_but_no_eye_score(client):
    s = record_one_tick(client, signup(client),
                        face_seen=False, calibrated_front=False, calibrated_side=True,
                        pitch=0.0, roll=0.0, ear=0.0, blink_rate=0.0,
                        neck_angle=30.0, torso_angle=10.0)

    assert s["posture_score"] == 85.0
    assert s["eye_strain_index"] is None
    assert s["posture_breakdown"]["pitch"] is None
    assert s["cameras_used"] == {"front": False, "side": True}


def make_session(user_id, day, posture=None, eye=None, cameras_used=None):
    return {
        "id": day, "user_id": user_id,
        "start_time": f"{day}T10:00:00", "end_time": f"{day}T10:30:00",
        "duration_seconds": 1800, "posture_score": posture, "eye_strain_index": eye,
        "avg_neck_angle": None, "avg_torso_angle": None,
        "avg_blink_rate": 17.0 if eye is not None else None, "sample_count": 10,
        "posture_breakdown": {"neck": None, "torso": None, "pitch": 3.0, "roll": 0.0, "shrug": 0.0},
        "eye_breakdown": {"blink": None, "ear": None},
        "cameras_used": cameras_used or {"front": True, "side": False},
    }


def test_pdf_report_uses_sessions_that_have_no_eye_data(client, monkeypatch):
    import reportlab.rl_config
    monkeypatch.setattr(reportlab.rl_config, "pageCompression", 0)  # so text is searchable
    token = signup(client)
    uid = bp.tokens[token]
    bp.sessions.extend([make_session(uid, "2026-09-20", posture=80.0),
                        make_session(uid, "2026-09-21", posture=90.0)])

    resp = client.post("/export/pdf", headers=auth(token), json={
        "sections": {"posture": True, "trend": True}, "from": "2026-09-01", "to": "2026-09-30"})

    assert resp.status_code == 200
    assert b"85.0 / 100" in resp.data
    assert b"Posture Data" in resp.data
    assert b"from 80 to 90" in resp.data


def test_gemini_is_told_which_cameras_each_session_used(backend):
    backend.sessions.extend([
        make_session("u1", "2026-09-20", posture=80.0, cameras_used={"front": True, "side": False}),
        make_session("u1", "2026-09-21", posture=80.0, cameras_used={"front": True, "side": True}),
    ])
    text = backend.summarize_sessions_for_prompt("u1")
    assert "cameras_used=front" in text.splitlines()[0]
    assert "cameras_used=front+side" in text.splitlines()[1]
