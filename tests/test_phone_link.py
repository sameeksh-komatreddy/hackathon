import ssl
import xml.etree.ElementTree as ET

import cv2
import numpy as np
import pytest

import phone_link
from cameras import FrameBuffer


def jpeg_bytes(value=40, shape=(360, 640, 3)):
    ok, buf = cv2.imencode(".jpg", np.full(shape, value, np.uint8))
    assert ok
    return buf.tobytes()


@pytest.fixture
def link(tmp_path):
    page = tmp_path / "phone.html"
    page.write_text("<!doctype html><title>phone page</title>", encoding="utf-8")
    pairing = phone_link.Pairing()
    buffer = FrameBuffer()

    def on_frame(image):
        buffer.put(image)
        return {"role": "side"}

    app = phone_link.create_phone_app(pairing, on_frame, str(page))
    return app.test_client(), pairing, buffer


def test_frame_with_current_code_reaches_the_camera(link):
    client, pairing, buffer = link
    resp = client.post("/frame", data=jpeg_bytes(40),
                       headers={"X-Pair-Code": pairing.code, "Content-Type": "image/jpeg"})

    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True, "role": "side"}
    image, count, _ = buffer.latest()
    assert count == 1
    assert image.shape == (360, 640, 3)
    assert abs(int(image[10, 10, 0]) - 40) <= 3  # JPEG is lossy


def test_frame_with_wrong_or_missing_code_is_refused(link):
    client, _, buffer = link
    assert client.post("/frame", data=jpeg_bytes(), headers={"X-Pair-Code": "guess"}).status_code == 403
    assert client.post("/frame", data=jpeg_bytes()).status_code == 403
    assert buffer.latest()[1] == 0


def test_new_code_cancels_the_old_one(link):
    client, pairing, _ = link
    old = pairing.code
    pairing.rotate()

    assert pairing.code != old
    assert client.post("/frame", data=jpeg_bytes(), headers={"X-Pair-Code": old}).status_code == 403
    assert client.post("/frame", data=jpeg_bytes(), headers={"X-Pair-Code": pairing.code}).status_code == 200


def test_frame_that_is_not_an_image_is_rejected(link):
    client, pairing, buffer = link
    resp = client.post("/frame", data=b"not a jpeg", headers={"X-Pair-Code": pairing.code})
    assert resp.status_code == 400
    assert buffer.latest()[1] == 0


def test_phone_page_is_served(link):
    client, _, _ = link
    resp = client.get("/?code=whatever")
    assert resp.status_code == 200
    assert b"phone page" in resp.data
    assert resp.mimetype == "text/html"


def test_certificate_is_created_once_and_loads(tmp_path):
    cert = tmp_path / "phone-cert.pem"
    key = tmp_path / "phone-key.pem"

    phone_link.ensure_certificate(str(cert), str(key), hosts=["192.168.1.20"])
    first = cert.read_bytes()
    phone_link.ensure_certificate(str(cert), str(key), hosts=["10.0.0.9"])

    assert cert.read_bytes() == first
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert), str(key))  # raises if the pair is unusable


def test_lan_addresses_drop_loopback_and_link_local_and_put_primary_first():
    got = phone_link.pick_lan_addresses(
        ["127.0.0.1", "169.254.3.3", "10.0.0.5", "192.168.1.20", "10.0.0.5"],
        primary="192.168.1.20")
    assert got == ["192.168.1.20", "10.0.0.5"]


def test_phone_url_carries_the_code():
    assert phone_link.phone_url("192.168.1.20", "abc123") == "https://192.168.1.20:5051/?code=abc123"


def test_qr_svg_is_valid_svg():
    root = ET.fromstring(phone_link.qr_svg("https://192.168.1.20:5051/?code=abc123"))
    assert root.tag.endswith("svg")
