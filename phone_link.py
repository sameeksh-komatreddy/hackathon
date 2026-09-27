"""Use a phone as a BackTrack camera over Wi-Fi.

The phone scans a QR code, opens a page served here over HTTPS (phone
browsers only allow camera access on secure pages), and uploads JPEG frames.
Uploads must carry the current pairing code from the QR code; nothing on
this server can be read back, so the rest of BackTrack stays on localhost.
"""
import datetime
import hmac
import ipaddress
import os
import secrets
import socket
import threading

import cv2
import numpy as np
from flask import Flask, jsonify, request, send_file
from werkzeug.serving import WSGIRequestHandler, make_server

PHONE_PORT = 5051
MAX_FRAME_BYTES = 4 * 1024 * 1024


# ---------------- pairing ----------------

class Pairing:
    """The secret the QR code carries. A new code cancels the old one."""

    def __init__(self):
        self._lock = threading.Lock()
        self.rotate()

    @property
    def code(self):
        with self._lock:
            return self._code

    def rotate(self):
        with self._lock:
            self._code = secrets.token_urlsafe(16)

    def matches(self, candidate):
        return bool(candidate) and hmac.compare_digest(candidate.encode(), self.code.encode())


def phone_url(host, code, port=PHONE_PORT):
    return f"https://{host}:{port}/?code={code}"


def qr_svg(text):
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    svg = img.to_string(encoding="unicode")
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[1].lstrip()
    return svg


# ---------------- finding this computer on the network ----------------

def pick_lan_addresses(candidates, primary=None):
    """IPv4 addresses a phone could reach, primary first, without loopback
    or link-local (169.254.x.x) addresses."""
    ordered = ([primary] if primary else []) + list(candidates)
    out = []
    for addr in ordered:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.version != 4 or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
            continue
        if addr not in out:
            out.append(addr)
    return out


def _primary_address():
    # Connecting a UDP socket sends nothing; it just asks the OS which
    # interface would carry traffic out, i.e. the Wi-Fi/Ethernet address.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def lan_addresses():
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        candidates = [info[4][0] for info in infos]
    except OSError:
        candidates = []
    return pick_lan_addresses(candidates, primary=_primary_address())


# ---------------- certificate ----------------

def ensure_certificate(cert_path, key_path, hosts=()):
    """Create a self-signed certificate on first run and reuse it after, so
    the phone only has to accept the browser warning once."""
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "BackTrack phone link")])
    alt_names = [x509.DNSName("localhost")]
    for host in hosts:
        try:
            alt_names.append(x509.IPAddress(ipaddress.ip_address(host)))
        except ValueError:
            alt_names.append(x509.DNSName(host))
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(key, hashes.SHA256())
    )

    os.makedirs(os.path.dirname(cert_path) or ".", exist_ok=True)
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.TraditionalOpenSSL,
                                  serialization.NoEncryption()))
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


# ---------------- the phone-facing server ----------------

def create_phone_app(pairing, on_frame, page_path):
    """`on_frame(image)` receives each decoded BGR frame and may return a
    dict that is echoed to the phone (e.g. which slot it is filling)."""
    app = Flask("backtrack_phone")
    app.config["MAX_CONTENT_LENGTH"] = MAX_FRAME_BYTES

    @app.get("/")
    def page():
        resp = send_file(page_path, mimetype="text/html", max_age=0)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.post("/frame")
    def frame():
        if not pairing.matches(request.headers.get("X-Pair-Code", "")):
            return jsonify({"ok": False, "error": "This link has expired. Scan the QR code on your computer again."}), 403
        data = np.frombuffer(request.get_data(), np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
        if image is None:
            return jsonify({"ok": False, "error": "That wasn't a JPEG image."}), 400
        info = on_frame(image) or {}
        return jsonify({"ok": True, **info})

    return app


class _QuietHandler(WSGIRequestHandler):
    def log_request(self, code="-", size="-"):
        # The phone uploads ~15 frames a second; logging each would bury
        # everything else in the console.
        if str(code).startswith(("4", "5")):
            super().log_request(code, size)


def start_phone_server(app, cert_path, key_path, host="0.0.0.0", port=PHONE_PORT):
    """Serve the phone app over HTTPS on a background thread. Raises OSError
    if the port is taken."""
    server = make_server(host, port, app, threaded=True,
                         request_handler=_QuietHandler,
                         ssl_context=(cert_path, key_path))
    threading.Thread(target=server.serve_forever, daemon=True, name="phone-server").start()
    return server
