import os, cv2, mediapipe as mp, numpy as np, math, time, json, threading, subprocess, urllib.request, uuid, datetime, io, hashlib, secrets, platform, shutil
from functools import wraps
from flask import Flask, Response, jsonify, request

# pip install google-genai python-dotenv
try:
   from google import genai
   from google.genai import types
   GENAI_OK = True
except ImportError:
   GENAI_OK = False

try:
   from dotenv import load_dotenv
   load_dotenv()
except ImportError:
   pass


try:
   from reportlab.lib.pagesizes import letter
   from reportlab.lib import colors
   from reportlab.lib.units import inch
   from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
   from reportlab.platypus import (
       SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
   )
   from reportlab.lib.enums import TA_LEFT, TA_CENTER
   REPORTLAB_OK = True
except ImportError:
   REPORTLAB_OK = False


app = Flask(__name__)
app.config["SECRET_KEY"] = "backtrack-secret"


# ---------------- Gemini config ----------------
# Set the GEMINI_API_KEY environment variable before starting the backend, e.g.:
#   export GEMINI_API_KEY="your-key-here"
# Get a key from Google AI Studio: https://aistudio.google.com/apikey
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
_gemini_client = None
_gemini_client_lock = threading.Lock()


def get_gemini_client():
   global _gemini_client
   if not GENAI_OK:
       raise RuntimeError(
           "The google-genai package isn't installed. Install it with: pip install google-genai"
       )
   if not GEMINI_API_KEY:
       raise RuntimeError(
           "GEMINI_API_KEY is not set. Export it before starting the backend "
           "(e.g. `export GEMINI_API_KEY=your-key`), then restart."
       )
   with _gemini_client_lock:
       if _gemini_client is None:
           _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
       return _gemini_client


BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode


MODEL_DIR = os.path.join(os.path.expanduser("~"), ".backtrack")
FACE_MODEL_PATH = os.path.join(MODEL_DIR, "face_landmarker.task")
FACE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
POSE_MODEL_PATH = os.path.join(MODEL_DIR, "pose_landmarker_lite.task")
POSE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
SESSIONS_FILE = os.path.join(MODEL_DIR, "sessions.json")
USERS_FILE = os.path.join(MODEL_DIR, "users.json")


def ensure_model(path, url):
   if not os.path.exists(path):
       os.makedirs(MODEL_DIR, exist_ok=True)
       urllib.request.urlretrieve(url, path)


face_options = FaceLandmarkerOptions(
   base_options=BaseOptions(model_asset_path=FACE_MODEL_PATH),
   running_mode=RunningMode.VIDEO,
   num_faces=1,
)
pose_options = PoseLandmarkerOptions(
   base_options=BaseOptions(model_asset_path=POSE_MODEL_PATH),
   running_mode=RunningMode.VIDEO,
)


LEFT_EYE  = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33,  160, 158, 133, 153, 144]


NOSE_TIP = 4; CHIN = 152
LEFT_EYE_L = 263; RIGHT_EYE_R = 33
LEFT_MOUTH = 287; RIGHT_MOUTH = 57


LEFT_EAR = 7; RIGHT_EAR = 8
LEFT_SHOULDER = 11; RIGHT_SHOULDER = 12
LEFT_HIP = 23


POSE_LINKS = (
   (0,1),(1,2),(2,3),(3,7),(0,4),(4,5),(5,6),(6,8),(9,10),
   (11,12),(11,13),(13,15),(15,17),(15,19),(15,21),(17,19),
   (12,14),(14,16),(16,18),(16,20),(16,22),(18,20),
   (11,23),(12,24),(23,24),
   (23,25),(25,27),(27,29),(29,31),(27,31),
   (24,26),(26,28),(28,30),(30,32),(28,32),
)


# ==================================================================
# ============================ ACCOUNTS ===========================
# ==================================================================
# Users are stored in a single JSON file: { username_lower: {id, username,
# password_hash, salt, created_at} }. Auth is a simple bearer-token scheme —
# on login/signup we hand back an opaque token that maps (in memory only,
# not persisted) to a user id. Every data-touching endpoint requires that
# token via the Authorization: Bearer <token> header, and every dataset
# (sessions, settings) is tagged with / scoped to the caller's user id so
# separate accounts never see each other's data.

users_lock = threading.Lock()
users = {}  # username_lower -> user record

tokens_lock = threading.Lock()
tokens = {}  # token -> user_id


def load_users():
   global users
   try:
       if os.path.exists(USERS_FILE):
           with open(USERS_FILE) as f:
               users = json.load(f)
   except Exception as e:
       print(f"failed to load users: {e}")
       users = {}


def save_users():
   try:
       os.makedirs(MODEL_DIR, exist_ok=True)
       with open(USERS_FILE, "w") as f:
           json.dump(users, f, indent=2)
   except Exception as e:
       print(f"failed to save users: {e}")


def hash_password(password, salt):
   return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000).hex()


def issue_token(user_id):
   token = secrets.token_hex(24)
   with tokens_lock:
       tokens[token] = user_id
   return token


def user_id_from_request():
   auth = request.headers.get("Authorization", "")
   token = auth[7:] if auth.lower().startswith("bearer ") else auth
   if not token:
       return None
   with tokens_lock:
       return tokens.get(token)


def require_auth(fn):
   @wraps(fn)
   def wrapper(*args, **kwargs):
       uid = user_id_from_request()
       if not uid:
           return jsonify({"ok": False, "error": "Not signed in."}), 401
       request.user_id = uid
       return fn(*args, **kwargs)
   return wrapper


@app.route("/auth/signup", methods=["POST"])
def auth_signup():
   payload = request.get_json(force=True, silent=True) or {}
   username = (payload.get("username") or "").strip()
   password = payload.get("password") or ""
   display_name = (payload.get("name") or "").strip() or username

   if len(username) < 3:
       return jsonify({"ok": False, "error": "Username must be at least 3 characters."}), 400
   if len(password) < 6:
       return jsonify({"ok": False, "error": "Password must be at least 6 characters."}), 400

   key = username.lower()
   with users_lock:
       if key in users:
           return jsonify({"ok": False, "error": "That username is already taken."}), 400
       salt = secrets.token_hex(16)
       user_id = str(uuid.uuid4())
       users[key] = {
           "id": user_id,
           "username": username,
           "name": display_name,
           "salt": salt,
           "password_hash": hash_password(password, salt),
           "created_at": datetime.datetime.now().isoformat(),
       }
       save_users()

   with settings_store_lock:
       write_user_settings(user_id, dict(DEFAULT_SETTINGS))

   token = issue_token(user_id)
   return jsonify({"ok": True, "token": token, "user": {"id": user_id, "username": username, "name": display_name}})


@app.route("/auth/login", methods=["POST"])
def auth_login():
   payload = request.get_json(force=True, silent=True) or {}
   username = (payload.get("username") or "").strip().lower()
   password = payload.get("password") or ""

   with users_lock:
       record = users.get(username)

   if not record or hash_password(password, record["salt"]) != record["password_hash"]:
       return jsonify({"ok": False, "error": "Incorrect username or password."}), 401

   token = issue_token(record["id"])
   return jsonify({"ok": True, "token": token, "user": {
       "id": record["id"], "username": record["username"], "name": record.get("name", record["username"]),
   }})


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
   auth = request.headers.get("Authorization", "")
   token = auth[7:] if auth.lower().startswith("bearer ") else auth
   with tokens_lock:
       tokens.pop(token, None)
   return jsonify({"ok": True})


@app.route("/auth/me", methods=["GET"])
@require_auth
def auth_me():
   uid = request.user_id
   with users_lock:
       for rec in users.values():
           if rec["id"] == uid:
               return jsonify({"ok": True, "user": {"id": uid, "username": rec["username"], "name": rec.get("name", rec["username"])}})
   return jsonify({"ok": False, "error": "User not found."}), 404


# ---------------- Configurable thresholds (per user) ----------------
DEFAULT_SETTINGS = {
   "blink_thresh":   0.18,  # EAR value below which an eye is considered "closed" (blink detection)
   "ear_thresh":     0.22,  # EAR value below which eyes count as narrowed/strained
   "min_blink_win":  10,    # seconds of warm-up before blink rate is trusted
   "low_blink_rate": 15,    # blinks/min below this counts as a low blink rate
   "pitch_thresh":   25,    # degrees of head pitch before it's flagged
   "roll_thresh":    25,    # degrees of head roll before it's flagged
   "shrug_ratio":    0.90,  # shoulder must rise above this fraction of its calibrated baseline height to count as a shrug
   "neck_thresh":    20,    # degrees of forward neck angle before it's flagged (side view)
   "torso_thresh":   15,    # degrees of torso lean before it's flagged (side view)
   "ear_dur":        10,    # seconds eyes must stay narrowed before an eye-strain alert fires
   "head_dur":       10,    # seconds head tilt must be sustained before an alert fires
   "blink_dur":      10,    # seconds blink rate must stay low before an alert fires
   "shrug_dur":      10,    # seconds shoulders must stay shrugged before an alert fires
   "side_dur":       30,    # seconds hunching (neck/torso) must be sustained before an alert fires
   "cooldown":       60,    # minimum seconds between repeat notifications of the same kind
}


SETTINGS_BOUNDS = {
   "blink_thresh":   (0.05, 0.40, float),
   "ear_thresh":     (0.05, 0.40, float),
   "min_blink_win":  (2,    60,   float),
   "low_blink_rate": (2,    40,   float),
   "pitch_thresh":   (5,    60,   float),
   "roll_thresh":    (5,    60,   float),
   "shrug_ratio":    (0.50, 0.99, float),
   "neck_thresh":    (5,    60,   float),
   "torso_thresh":   (5,    60,   float),
   "ear_dur":        (1,    120,  float),
   "head_dur":       (1,    120,  float),
   "blink_dur":      (1,    120,  float),
   "shrug_dur":      (1,    120,  float),
   "side_dur":       (1,    180,  float),
   "cooldown":       (5,    600,  float),
}


def user_dir(user_id):
   d = os.path.join(MODEL_DIR, "users", user_id)
   os.makedirs(d, exist_ok=True)
   return d


settings_store_lock = threading.Lock()


def read_user_settings(user_id):
   path = os.path.join(user_dir(user_id), "settings.json")
   merged = dict(DEFAULT_SETTINGS)
   try:
       if os.path.exists(path):
           with open(path) as f:
               saved = json.load(f)
           for k in DEFAULT_SETTINGS:
               if k in saved:
                   merged[k] = saved[k]
   except Exception as e:
       print(f"failed to load settings for {user_id}: {e}")
   return merged


def write_user_settings(user_id, values):
   path = os.path.join(user_dir(user_id), "settings.json")
   with open(path, "w") as f:
       json.dump(values, f, indent=2)


# `settings` holds whichever user's thresholds are currently "live" for the
# detection loops — i.e. the thresholds of whoever most recently started a
# recording session (or logged in). Since there is a single physical webcam
# rig, only one person's session is ever being actively recorded at a time.
settings_lock = threading.Lock()
settings = dict(DEFAULT_SETTINGS)
active_settings_user = {"id": None}


def get_settings_snapshot():
   with settings_lock:
       return dict(settings)


def activate_settings_for_user(user_id):
   snap = read_user_settings(user_id)
   with settings_lock:
       settings.clear()
       settings.update(snap)
       active_settings_user["id"] = user_id
   return snap


lock = threading.Lock()
front_lock = threading.Lock()
side_lock = threading.Lock()


state = {
   "ear": 0.0, "blink_rate": 0.0, "pitch": 0.0, "roll": 0.0,
   "low_ear_secs": 0.0, "head_secs": 0.0, "blink_low_secs": 0.0,
   "shrug_secs": 0.0,
   "neck_angle": 0.0, "torso_angle": 0.0, "bad_side_secs": 0.0,
   "fatigue_alert": False, "posture_alert": False, "side_posture_alert": False,
   "alerts": [], "notifications": [],
   "calibrated_front": False, "calibrated_side": False,
   "progress": 0.0,  # 0-1, how close the *closest* threshold is to firing
   "durations": dict(DEFAULT_SETTINGS),  # current *_dur thresholds, for per-trigger progress bars
}


front_frame = None
side_frame = None


last_notif = {"ear": 0, "head": 0, "blink": 0, "shrug": 0, "side": 0}
recal_front = threading.Event()
recal_side = threading.Event()


# ---------------- Session recording state ----------------
sessions_lock = threading.Lock()
sessions = []


recording_lock = threading.Lock()
recording_active = False
current_session_accum = None
current_session_user = {"id": None}




def reset_accum():
   return {
       "start_time": None,
       "posture_scores": [],
       "eye_strain_scores": [],
       "neck_angles": [],
       "torso_angles": [],
       "blink_rates": [],
       "neck_penalties": [],
       "torso_penalties": [],
       "pitch_penalties": [],
       "roll_penalties": [],
       "shrug_penalties": [],
       "blink_penalties": [],
       "ear_penalties": [],
   }




def load_sessions():
   global sessions
   try:
       if os.path.exists(SESSIONS_FILE):
           with open(SESSIONS_FILE) as f:
               sessions = json.load(f)
   except Exception as e:
       print(f"failed to load sessions: {e}")
       sessions = []




def save_sessions():
   try:
       os.makedirs(MODEL_DIR, exist_ok=True)
       with open(SESSIONS_FILE, "w") as f:
           json.dump(sessions, f, indent=2)
   except Exception as e:
       print(f"failed to save sessions: {e}")




def compute_posture_score(neck_angle, torso_angle, pitch, roll, shrug_bad, cfg):
   score = 100.0
   if neck_angle > cfg["neck_thresh"]:
       score -= min(40.0, (neck_angle - cfg["neck_thresh"]) * 1.5)
   if torso_angle > cfg["torso_thresh"]:
       score -= min(30.0, (torso_angle - cfg["torso_thresh"]) * 1.5)
   if abs(pitch) > cfg["pitch_thresh"]:
       score -= min(15.0, (abs(pitch) - cfg["pitch_thresh"]) * 0.5)
   if abs(roll) > cfg["roll_thresh"]:
       score -= min(15.0, (abs(roll) - cfg["roll_thresh"]) * 0.5)
   if shrug_bad:
       score -= 10.0
   return max(0.0, min(100.0, score))




def compute_eye_strain(ear, blink_rate, cfg):
   strain = 0.0
   low_blink_rate = cfg["low_blink_rate"]
   ear_thresh = cfg["ear_thresh"]
   if blink_rate < low_blink_rate:
       strain += max(0.0, low_blink_rate - blink_rate) / low_blink_rate * 6.0
   if 0.0 < ear < ear_thresh:
       strain += max(0.0, ear_thresh - ear) / ear_thresh * 4.0
   return max(0.0, min(10.0, strain))




def compute_posture_breakdown(neck_angle, torso_angle, pitch, roll, shrug_bad, cfg):
   return {
       "neck":  min(40.0, (neck_angle - cfg["neck_thresh"]) * 1.5)   if neck_angle > cfg["neck_thresh"]   else 0.0,
       "torso": min(30.0, (torso_angle - cfg["torso_thresh"]) * 1.5) if torso_angle > cfg["torso_thresh"] else 0.0,
       "pitch": min(15.0, (abs(pitch) - cfg["pitch_thresh"]) * 0.5)  if abs(pitch) > cfg["pitch_thresh"]  else 0.0,
       "roll":  min(15.0, (abs(roll) - cfg["roll_thresh"]) * 0.5)    if abs(roll) > cfg["roll_thresh"]    else 0.0,
       "shrug": 10.0 if shrug_bad else 0.0,
   }




def compute_eye_breakdown(ear, blink_rate, cfg):
   low_blink_rate = cfg["low_blink_rate"]
   ear_thresh = cfg["ear_thresh"]
   return {
       "blink": (max(0.0, low_blink_rate - blink_rate) / low_blink_rate * 6.0) if blink_rate < low_blink_rate else 0.0,
       "ear":   (max(0.0, ear_thresh - ear) / ear_thresh * 4.0) if 0.0 < ear < ear_thresh else 0.0,
   }




def get_ear(lm, idx, w, h):
   pts = [np.array([lm[i].x * w, lm[i].y * h]) for i in idx]
   a = np.linalg.norm(pts[1] - pts[5])
   b = np.linalg.norm(pts[2] - pts[4])
   c = np.linalg.norm(pts[0] - pts[3])
   return (a + b) / (2.0 * c) if c > 0 else 0.0


def get_head_pose(lm, w, h):
   model = np.array([
       [0.0, 0.0, 0.0],      [0.0, -63.6, -12.5],
       [-43.3, 32.7, -26.0], [43.3, 32.7, -26.0],
       [-28.9, -28.9, -24.1],[28.9, -28.9, -24.1],
   ], dtype=np.float64)
   image = np.array([
       [lm[NOSE_TIP].x*w,   lm[NOSE_TIP].y*h],
       [lm[CHIN].x*w,       lm[CHIN].y*h],
       [lm[LEFT_EYE_L].x*w, lm[LEFT_EYE_L].y*h],
       [lm[RIGHT_EYE_R].x*w,lm[RIGHT_EYE_R].y*h],
       [lm[LEFT_MOUTH].x*w, lm[LEFT_MOUTH].y*h],
       [lm[RIGHT_MOUTH].x*w,lm[RIGHT_MOUTH].y*h],
   ], dtype=np.float64)
   cam = np.array([[w,0,w/2],[0,w,h/2],[0,0,1]], dtype=np.float64)
   ok, rvec, _ = cv2.solvePnP(model, image, cam, np.zeros((4,1)), flags=cv2.SOLVEPNP_ITERATIVE)
   if not ok: return 0.0, 0.0, 0.0
   rmat, _ = cv2.Rodrigues(rvec)
   angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
   return angles[0], angles[1], angles[2]


def get_angle(p1, p2):
   return abs(math.degrees(math.atan2(p2[0]-p1[0], p2[1]-p1[1])))


def check_notif(key, cond, now, cooldown):
   if cond and now - last_notif[key] >= cooldown:
       last_notif[key] = now; return True
   return False


# ---------------- Cross-platform desktop notifications ----------------
# These need to show up as real OS notification-center banners, over
# whatever else is on screen — not anything drawn inside the browser tab.
# On macOS specifically, `osascript -e 'display notification ...'` silently
# no-ops on modern macOS unless the calling process (Terminal, or whatever
# runs `python backend.py`) has been explicitly granted notification
# permission in System Settings, and in some configurations also needs
# Automation/Apple-Events permission for osascript itself — a very common
# source of "nothing visibly happened." `terminal-notifier` (a small
# standalone binary, not part of the OS) sidesteps the Apple-Events
# permission requirement entirely and is preferred when installed:
#     brew install terminal-notifier
# Every attempt is logged to the backend console so failures are visible
# instead of failing silently.
_SYSTEM = platform.system()
_HAS_TERMINAL_NOTIFIER = shutil.which("terminal-notifier") is not None


def send_desktop_notification(title, msg):
   try:
       if _SYSTEM == "Darwin":
           if _HAS_TERMINAL_NOTIFIER:
               result = subprocess.run(
                   ["terminal-notifier", "-title", title, "-message", msg, "-sound", "Ping"],
                   check=False, timeout=5, capture_output=True, text=True,
               )
               if result.returncode != 0:
                   print(f"[BackTrack] terminal-notifier failed ({result.returncode}): {result.stderr.strip()}")
               else:
                   print(f"[BackTrack] sent native notification via terminal-notifier: {title}")
               return
           result = subprocess.run(
               ["osascript", "-e", f'display notification "{msg}" with title "{title}" sound name "Ping"'],
               check=False, timeout=5, capture_output=True, text=True,
           )
           if result.returncode != 0:
               print(f"[BackTrack] osascript notification failed ({result.returncode}): {result.stderr.strip()}")
               print("[BackTrack] Fix: System Settings > Notifications > find Terminal (or your Python "
                     "app) > turn on 'Allow Notifications'. If that's already on, install "
                     "terminal-notifier instead (`brew install terminal-notifier`) — it's more "
                     "reliable and avoids macOS's Automation permission prompt.")
           else:
               print(f"[BackTrack] sent native notification via osascript: {title}")
           return
       if _SYSTEM == "Linux":
           result = subprocess.run(["notify-send", title, msg], check=False, timeout=5, capture_output=True, text=True)
           if result.returncode != 0:
               print(f"[BackTrack] notify-send failed ({result.returncode}): {result.stderr.strip()}")
           return
       if _SYSTEM == "Windows":
           try:
               from win10toast import ToastNotifier
               ToastNotifier().show_toast(title, msg, duration=6, threaded=True)
               print(f"[BackTrack] sent native notification via win10toast: {title}")
               return
           except Exception as e:
               print(f"[BackTrack] win10toast unavailable ({e}), trying plyer…")
       try:
           from plyer import notification as plyer_notification
           plyer_notification.notify(title=title, message=msg, timeout=6)
           print(f"[BackTrack] sent native notification via plyer: {title}")
       except Exception as e:
           print(f"[BackTrack] no native notifier available on {_SYSTEM}: {e}")
   except Exception as e:
       print(f"[BackTrack] notify error: {e}")


# kept for readability at call sites below
mac_notify = send_desktop_notification


def open_cap(idx):
   cap = cv2.VideoCapture(idx)
   cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
   cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
   return cap


def encode_jpg(frame):
   _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
   return buf.tobytes()


def put_text(frame, text, pos, color, scale=0.45, thick=1):
   cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, (0,0,0), 3, cv2.LINE_AA)
   cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, color,   thick, cv2.LINE_AA)


def draw_face_points(frame, lm, w, h):
   for i, p in enumerate(lm):
       if i % 2 != 0:
           continue
       cv2.circle(frame, (int(p.x*w), int(p.y*h)), 1, (80, 220, 80), -1, cv2.LINE_AA)


def draw_pose_links(frame, lm, w, h, color):
   for a, b in POSE_LINKS:
       pa = (int(lm[a].x*w), int(lm[a].y*h))
       pb = (int(lm[b].x*w), int(lm[b].y*h))
       cv2.line(frame, pa, pb, color, 2, cv2.LINE_AA)
   for p in lm:
       cv2.circle(frame, (int(p.x*w), int(p.y*h)), 3, color, -1, cv2.LINE_AA)


def front_thread():
   global front_frame
   ear_since = head_since = blink_since = shrug_since = None
   blinks = []; in_blink = False
   base_l = base_r = None
   start = time.time()
   ts = 0
   cap = open_cap(1)


   with FaceLandmarker.create_from_options(face_options) as face_landmarker, \
        PoseLandmarker.create_from_options(pose_options) as pose_landmarker:
       while True:
           if recal_front.is_set():
               base_l = base_r = None
               recal_front.clear()


           ok, frame = cap.read()
           if not ok or frame is None:
               time.sleep(0.05); continue


           cfg = get_settings_snapshot()
           BLINK_THRESH   = cfg["blink_thresh"]
           EAR_THRESH     = cfg["ear_thresh"]
           MIN_BLINK_WIN  = cfg["min_blink_win"]
           LOW_BLINK_RATE = cfg["low_blink_rate"]
           PITCH_THRESH   = cfg["pitch_thresh"]
           ROLL_THRESH    = cfg["roll_thresh"]
           SHRUG_RATIO    = cfg["shrug_ratio"]


           frame = cv2.flip(frame, 1)
           h, w = frame.shape[:2]
           now = time.time()
           elapsed = now - start
           rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
           ts += 33


           image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
           face_result = face_landmarker.detect_for_video(image, ts)
           pose_result = pose_landmarker.detect_for_video(image, ts)


           annotated = frame


           ear = pitch = roll = 0.0
           rate = ear_secs = head_secs = blink_secs = shrug_secs = 0.0
           calib_front = False
           face_seen = False


           if face_result.face_landmarks:
               face_seen = True
               lm = face_result.face_landmarks[0]
               ear = (get_ear(lm, LEFT_EYE, w, h) + get_ear(lm, RIGHT_EYE, w, h)) / 2


               if ear < BLINK_THRESH:
                   in_blink = True
               elif in_blink:
                   blinks.append(now); in_blink = False
               window = min(elapsed, 60)
               blinks = [t for t in blinks if now-t <= window]
               rate = (len(blinks)*60/window) if window > 0 else 0.0


               pitch, _, roll = get_head_pose(lm, w, h)
               head_bad = abs(pitch) > PITCH_THRESH or abs(roll) > ROLL_THRESH


               if ear < EAR_THRESH:
                   ear_since = ear_since or now
               else:
                   ear_since = None


               if head_bad:
                   head_since = head_since or now
               else:
                   head_since = None


               if elapsed >= MIN_BLINK_WIN and rate < LOW_BLINK_RATE:
                   blink_since = blink_since or now
               else:
                   blink_since = None


               ear_secs   = (now - ear_since)   if ear_since   else 0.0
               head_secs  = (now - head_since)  if head_since  else 0.0
               blink_secs = (now - blink_since) if blink_since else 0.0


               draw_face_points(annotated, lm, w, h)


               eye_col = (
                   (0, 220, 100) if ear >= EAR_THRESH  else
                   (0, 200, 245) if ear >= BLINK_THRESH else
                   (30,  30, 255)
               )
               for idx in [LEFT_EYE, RIGHT_EYE]:
                   pts = np.array([[int(lm[i].x*w), int(lm[i].y*h)] for i in idx])
                   cx, cy = pts.mean(axis=0).astype(int)
                   rx = int((pts[:,0].max() - pts[:,0].min()) / 2) + 5
                   ry = int((pts[:,1].max() - pts[:,1].min()) / 2) + 7
                   cv2.ellipse(annotated, (cx,cy), (rx,ry), 0, 0, 360, eye_col, 1, cv2.LINE_AA)


           if pose_result.pose_landmarks:
               plm = pose_result.pose_landmarks[0]
               left = plm[LEFT_SHOULDER].y - plm[LEFT_EAR].y
               right = plm[RIGHT_SHOULDER].y - plm[RIGHT_EAR].y
               if base_l is None:
                   base_l = left
                   base_r = right
               calib_front = True


               shrugging = (left < base_l * SHRUG_RATIO or right < base_r * SHRUG_RATIO)


               if shrugging:
                   shrug_since = shrug_since or now
               else:
                   shrug_since = None
               shrug_secs = (now - shrug_since) if shrug_since else 0.0


               sx1, sy1 = int(plm[LEFT_SHOULDER].x*w), int(plm[LEFT_SHOULDER].y*h)
               sx2, sy2 = int(plm[RIGHT_SHOULDER].x*w), int(plm[RIGHT_SHOULDER].y*h)
               shrug_col = (30, 30, 255) if shrugging else (0, 220, 100)
               draw_pose_links(annotated, plm, w, h, shrug_col)
               lx = (sx1+sx2)//2 - 30
               ly = min(sy1,sy2) - 12
               put_text(annotated, "SHRUG" if shrugging else "SHOULDERS OK",
                        (lx, ly), shrug_col, 0.5, 1)


           ear_col   = (0,220,100) if ear>=EAR_THRESH   else (0,200,245) if ear>=BLINK_THRESH else (30,30,255)
           blink_col = (0,220,100) if rate>=LOW_BLINK_RATE else (0,200,245) if rate>=LOW_BLINK_RATE*0.67 else (30,30,255)
           pitch_col = (0,220,100) if abs(pitch)<=PITCH_THRESH else (30,30,255)
           roll_col  = (0,220,100) if abs(roll)<=ROLL_THRESH   else (30,30,255)
           y = 20
           for text, col in [
               (f"EAR {ear:.3f}", ear_col),
               (f"BLINK {rate:.0f}/min", blink_col),
               (f"PITCH {abs(pitch):.1f}", pitch_col),
               (f"ROLL  {abs(roll):.1f}",  roll_col),
           ]:
               put_text(annotated, text, (8, y), col); y += 18


           with front_lock:
               front_frame = encode_jpg(annotated)


           with lock:
               s = state
               s["ear"]              = round(ear, 3)
               s["blink_rate"]       = round(rate, 1)
               s["pitch"]            = round(pitch, 1)
               s["roll"]             = round(roll, 1)
               s["low_ear_secs"]     = round(ear_secs, 1)
               s["head_secs"]        = round(head_secs, 1)
               s["blink_low_secs"]   = round(blink_secs, 1)
               s["shrug_secs"]       = round(shrug_secs, 1)
               s["calibrated_front"] = calib_front
               s["face_seen"]        = face_seen


           time.sleep(0.033)


def side_thread():
   global side_frame
   side_since = None
   ts = 0
   cap = open_cap(0)


   with PoseLandmarker.create_from_options(pose_options) as pose_landmarker:
       while True:
           if recal_side.is_set():
               recal_side.clear()


           ok, frame = cap.read()
           if not ok or frame is None:
               time.sleep(0.05); continue


           cfg = get_settings_snapshot()
           NECK_THRESH  = cfg["neck_thresh"]
           TORSO_THRESH = cfg["torso_thresh"]


           h, w = frame.shape[:2]
           now = time.time()
           rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
           ts += 33


           image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
           pose_result = pose_landmarker.detect_for_video(image, ts)


           annotated = frame


           neck = torso = side_secs = 0.0
           calib_side = False


           if pose_result.pose_landmarks:
               plm = pose_result.pose_landmarks[0]
               calib_side = True


               ear_pos = (int(plm[LEFT_EAR].x*w), int(plm[LEFT_EAR].y*h))
               sho_pos = (int(plm[LEFT_SHOULDER].x*w), int(plm[LEFT_SHOULDER].y*h))
               hip_pos = (int(plm[LEFT_HIP].x*w), int(plm[LEFT_HIP].y*h))


               neck  = get_angle(ear_pos, sho_pos)
               torso = get_angle(sho_pos, hip_pos)
               bad   = (neck > NECK_THRESH or torso > TORSO_THRESH)


               if bad:
                   side_since = side_since or now
               else:
                   side_since = None
               side_secs = (now - side_since) if side_since else 0.0


               spine_col = (30, 30, 255) if bad else (0, 220, 100)
               draw_pose_links(annotated, plm, w, h, spine_col)
               cv2.line(annotated, ear_pos, sho_pos, spine_col, 3, cv2.LINE_AA)
               cv2.line(annotated, sho_pos, hip_pos, spine_col, 3, cv2.LINE_AA)


               for pt, label in [(ear_pos,"EAR"),(sho_pos,"SHO"),(hip_pos,"HIP")]:
                   cv2.circle(annotated, pt, 9, spine_col, -1, cv2.LINE_AA)
                   cv2.circle(annotated, pt, 9, (255,255,255), 1, cv2.LINE_AA)
                   put_text(annotated, label, (pt[0]+12, pt[1]+5), spine_col, 0.45)


               cv2.line(annotated,
                        (hip_pos[0], hip_pos[1]),
                        (hip_pos[0], max(0, ear_pos[1]-10)),
                        (180,180,180), 1, cv2.LINE_AA)


               put_text(annotated,
                        f"N:{neck:.0f}  T:{torso:.0f}",
                        (max(0, sho_pos[0]-60), sho_pos[1]-18),
                        spine_col, 0.48)


               if bad:
                   msg = ("NECK FORWARD"    if neck>NECK_THRESH and torso<=TORSO_THRESH else
                          "TORSO TILTED"    if torso>TORSO_THRESH and neck<=NECK_THRESH else
                          "HUNCHING \u2014 SIT UP")
                   tw = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0][0]
                   bx = w//2 - tw//2
                   cv2.rectangle(annotated, (bx-8, 6), (bx+tw+8, 30), (20,20,20), -1)
                   cv2.rectangle(annotated, (bx-8, 6), (bx+tw+8, 30), spine_col, 1)
                   cv2.putText(annotated, msg, (bx, 25),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, spine_col, 2, cv2.LINE_AA)


           neck_col  = (0,220,100) if neck<=NECK_THRESH   else (30,30,255)
           torso_col = (0,220,100) if torso<=TORSO_THRESH else (30,30,255)
           put_text(annotated, f"NECK  {neck:.1f}", (8, 20), neck_col)
           put_text(annotated, f"TORSO {torso:.1f}", (8, 38), torso_col)


           with side_lock:
               side_frame = encode_jpg(annotated)


           with lock:
               s = state
               s["neck_angle"]      = round(neck, 1)
               s["torso_angle"]     = round(torso, 1)
               s["bad_side_secs"]   = round(side_secs, 1)
               s["calibrated_side"] = calib_side


           time.sleep(0.033)


def alert_thread():
   while True:
       now = time.time()
       cfg = get_settings_snapshot()
       EAR_DUR   = cfg["ear_dur"]
       HEAD_DUR  = cfg["head_dur"]
       BLINK_DUR = cfg["blink_dur"]
       SHRUG_DUR = cfg["shrug_dur"]
       SIDE_DUR  = cfg["side_dur"]
       COOLDOWN  = cfg["cooldown"]
       with lock:
           s = state
           ear_secs   = s["low_ear_secs"]
           head_secs  = s["head_secs"]
           blink_secs = s["blink_low_secs"]
           shrug_secs = s["shrug_secs"]
           side_secs  = s["bad_side_secs"]
           ear        = s["ear"]
           blink_rate = s["blink_rate"]
           pitch      = s["pitch"]
           roll       = s["roll"]
           neck_angle = s["neck_angle"]
           torso_angle= s["torso_angle"]
           calibrated_front = s["calibrated_front"]
           calibrated_side  = s["calibrated_side"]
           face_seen  = s.get("face_seen", False)


       fatigue      = (ear_secs>=EAR_DUR or head_secs>=HEAD_DUR or blink_secs>=BLINK_DUR)
       posture      = shrug_secs >= SHRUG_DUR
       side_posture = side_secs  >= SIDE_DUR

       # Progress bar: how close is the *closest* active threshold to firing,
       # as a 0-1 fraction. The Record screen fills this bar in real time and
       # the desktop notification fires the instant it hits 1.0.
       progress = max(
           (ear_secs / EAR_DUR) if EAR_DUR else 0,
           (head_secs / HEAD_DUR) if HEAD_DUR else 0,
           (blink_secs / BLINK_DUR) if BLINK_DUR else 0,
           (shrug_secs / SHRUG_DUR) if SHRUG_DUR else 0,
           (side_secs / SIDE_DUR) if SIDE_DUR else 0,
       )
       progress = max(0.0, min(1.0, progress))


       alerts = []
       notifs = []
       if fatigue:      alerts.append("Fatigue detected — take a break.")
       if posture:      alerts.append("Shoulders too high — relax them.")
       if side_posture: alerts.append("Hunching detected — sit up straight.")


       if check_notif("ear",   ear_secs>=EAR_DUR,     now, COOLDOWN): send_desktop_notification("Backtrack · Eye Strain","Your eyes are narrowing."); notifs.append("low_ear")
       if check_notif("head",  head_secs>=HEAD_DUR,   now, COOLDOWN): send_desktop_notification("Backtrack · Head Tilt","Head tilt detected.");       notifs.append("head_tilt")
       if check_notif("blink", blink_secs>=BLINK_DUR, now, COOLDOWN): send_desktop_notification("Backtrack · Blink Rate","Blink more often.");        notifs.append("low_blink")
       if check_notif("shrug", shrug_secs>=SHRUG_DUR, now, COOLDOWN): send_desktop_notification("Backtrack · Posture","Relax your shoulders.");      notifs.append("shrug")
       if check_notif("side",  side_secs>=SIDE_DUR,   now, COOLDOWN): send_desktop_notification("Backtrack · Posture","Sit up straight.");           notifs.append("hunching")


       with lock:
           state.update({"fatigue_alert":fatigue,"posture_alert":posture,
                          "side_posture_alert":side_posture,"alerts":alerts,"notifications":notifs,
                          "progress": progress,
                          "durations": {
                              "ear_dur": EAR_DUR, "head_dur": HEAD_DUR, "blink_dur": BLINK_DUR,
                              "shrug_dur": SHRUG_DUR, "side_dur": SIDE_DUR,
                          }})


       with recording_lock:
           if recording_active and current_session_accum is not None:
               if calibrated_side:
                   shrug_bad = shrug_secs > 0
                   p_score = compute_posture_score(neck_angle, torso_angle, pitch, roll, shrug_bad, cfg)
                   p_breakdown = compute_posture_breakdown(neck_angle, torso_angle, pitch, roll, shrug_bad, cfg)
                   current_session_accum["posture_scores"].append(p_score)
                   current_session_accum["neck_angles"].append(neck_angle)
                   current_session_accum["torso_angles"].append(torso_angle)
                   current_session_accum["neck_penalties"].append(p_breakdown["neck"])
                   current_session_accum["torso_penalties"].append(p_breakdown["torso"])
                   current_session_accum["pitch_penalties"].append(p_breakdown["pitch"])
                   current_session_accum["roll_penalties"].append(p_breakdown["roll"])
                   current_session_accum["shrug_penalties"].append(p_breakdown["shrug"])
               if calibrated_front and face_seen:
                   e_score = compute_eye_strain(ear, blink_rate, cfg)
                   e_breakdown = compute_eye_breakdown(ear, blink_rate, cfg)
                   current_session_accum["eye_strain_scores"].append(e_score)
                   current_session_accum["blink_rates"].append(blink_rate)
                   current_session_accum["blink_penalties"].append(e_breakdown["blink"])
                   current_session_accum["ear_penalties"].append(e_breakdown["ear"])


       time.sleep(0.5)


@app.after_request
def add_cors_headers(resp):
   resp.headers["Access-Control-Allow-Origin"] = "*"
   resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
   resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
   return resp


@app.route("/")
def index():
   return "Backtrack backend running. Open index.html in your browser.", 200


@app.route("/stream")
def stream():
   def gen():
       while True:
           with lock:
               payload = {k: state[k] for k in [
                   "ear","blink_rate","pitch","roll",
                   "neck_angle","torso_angle","shrug_secs",
                   "low_ear_secs","head_secs","blink_low_secs","bad_side_secs",
                   "fatigue_alert","posture_alert","side_posture_alert",
                   "alerts","notifications","calibrated_front","calibrated_side",
                   "progress","durations",
               ]}
           yield f"data: {json.dumps(payload)}\n\n"
           time.sleep(0.1)
   return Response(gen(), mimetype="text/event-stream",
                   headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no",
                            "Access-Control-Allow-Origin":"*"})


def mjpeg_gen(lk, get_frame):
   while True:
       with lk:
           frame = get_frame()
       if frame:
           yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
       time.sleep(0.033)


@app.route("/feed/front")
def feed_front():
   return Response(mjpeg_gen(front_lock, lambda: front_frame),
                   mimetype="multipart/x-mixed-replace; boundary=frame",
                   headers={"Access-Control-Allow-Origin":"*"})


@app.route("/feed/side")
def feed_side():
   return Response(mjpeg_gen(side_lock, lambda: side_frame),
                   mimetype="multipart/x-mixed-replace; boundary=frame",
                   headers={"Access-Control-Allow-Origin":"*"})


@app.route("/settings", methods=["GET"])
@require_auth
def get_settings_route():
   snap = activate_settings_for_user(request.user_id)
   return jsonify({"settings": snap, "defaults": DEFAULT_SETTINGS, "bounds": {
       k: {"min": lo, "max": hi} for k, (lo, hi, _t) in SETTINGS_BOUNDS.items()
   }})


@app.route("/settings", methods=["POST"])
@require_auth
def update_settings_route():
   uid = request.user_id
   payload = request.get_json(force=True, silent=True) or {}
   errors = {}
   current = read_user_settings(uid)
   for key, (lo, hi, typ) in SETTINGS_BOUNDS.items():
       if key not in payload:
           continue
       try:
           val = typ(payload[key])
       except (TypeError, ValueError):
           errors[key] = "must be a number"
           continue
       if not (lo <= val <= hi):
           errors[key] = f"must be between {lo} and {hi}"
           continue
       current[key] = val

   if errors:
       return jsonify({"ok": False, "errors": errors, "settings": current}), 400

   with settings_store_lock:
       write_user_settings(uid, current)
   activate_settings_for_user(uid)
   return jsonify({"ok": True, "settings": current})


@app.route("/settings/reset", methods=["POST"])
@require_auth
def reset_settings_route():
   uid = request.user_id
   snap = dict(DEFAULT_SETTINGS)
   with settings_store_lock:
       write_user_settings(uid, snap)
   activate_settings_for_user(uid)
   return jsonify({"ok": True, "settings": snap})


@app.route("/notify/test", methods=["POST"])
@require_auth
def notify_test():
   send_desktop_notification("Backtrack · Test", "If you can see this, native notifications are working.")
   return jsonify({"ok": True, "note": "Sent — check the backend console log if nothing appeared."})


@app.route("/recalibrate",       methods=["POST"])
def recalibrate():       recal_front.set(); recal_side.set(); return jsonify({"ok":True})
@app.route("/recalibrate_front", methods=["POST"])
def recalibrate_front(): recal_front.set();                   return jsonify({"ok":True})
@app.route("/recalibrate_side",  methods=["POST"])
def recalibrate_side():  recal_side.set();                    return jsonify({"ok":True})


# ---------------- Session endpoints (per user) ----------------


@app.route("/session/start", methods=["POST"])
@require_auth
def session_start():
   global recording_active, current_session_accum
   uid = request.user_id
   activate_settings_for_user(uid)
   with recording_lock:
       recording_active = True
       current_session_accum = reset_accum()
       current_session_accum["start_time"] = time.time()
       current_session_user["id"] = uid
   return jsonify({"ok": True})


@app.route("/session/stop", methods=["POST"])
@require_auth
def session_stop():
   global recording_active, current_session_accum
   uid = request.user_id
   with recording_lock:
       if not recording_active or current_session_accum is None or current_session_user["id"] != uid:
           return jsonify({"ok": False, "error": "not recording"}), 400
       accum = current_session_accum
       recording_active = False
       current_session_accum = None
       current_session_user["id"] = None


   start_ts = accum["start_time"] or time.time()
   end_ts = time.time()
   duration = max(0, int(end_ts - start_ts))


   def avg(lst):
       return round(sum(lst) / len(lst), 1) if lst else None


   session_record = {
       "id": str(uuid.uuid4()),
       "user_id": uid,
       "start_time": datetime.datetime.fromtimestamp(start_ts).isoformat(),
       "end_time": datetime.datetime.fromtimestamp(end_ts).isoformat(),
       "duration_seconds": duration,
       "posture_score": avg(accum["posture_scores"]),
       "eye_strain_index": avg(accum["eye_strain_scores"]),
       "avg_neck_angle": avg(accum["neck_angles"]),
       "avg_torso_angle": avg(accum["torso_angles"]),
       "avg_blink_rate": avg(accum["blink_rates"]),
       "sample_count": len(accum["posture_scores"]),
       "posture_breakdown": {
           "neck":  avg(accum["neck_penalties"]),
           "torso": avg(accum["torso_penalties"]),
           "pitch": avg(accum["pitch_penalties"]),
           "roll":  avg(accum["roll_penalties"]),
           "shrug": avg(accum["shrug_penalties"]),
       },
       "eye_breakdown": {
           "blink": avg(accum["blink_penalties"]),
           "ear":   avg(accum["ear_penalties"]),
       },
   }


   with sessions_lock:
       sessions.append(session_record)
       save_sessions()


   return jsonify({"ok": True, "session": session_record})


@app.route("/session/status", methods=["GET"])
@require_auth
def session_status():
   uid = request.user_id
   with recording_lock:
       active = recording_active and current_session_user["id"] == uid
       started = current_session_accum["start_time"] if (current_session_accum and active) else None
   return jsonify({"recording": active, "start_time": started})


@app.route("/sessions", methods=["GET"])
@require_auth
def get_sessions():
   uid = request.user_id
   limit = request.args.get("limit", default=50, type=int)
   with sessions_lock:
       mine = [s for s in sessions if s.get("user_id") == uid]
   result = mine[-limit:] if limit else mine
   return jsonify({"sessions": result})


# ---------------- Gemini helpers ----------------


def summarize_sessions_for_prompt(user_id, limit=30):
   """Plain-text table of this user's recent sessions, fed to Gemini as
   grounding data. Nothing here is hardcoded analysis — it's just the raw
   numbers so the model can reason over them itself. Scoped to user_id so
   one account's report is never built from another account's data."""
   with sessions_lock:
       mine = [s for s in sessions if s.get("user_id") == user_id]
       recent = mine[-limit:] if limit else mine
   if not recent:
       return "No sessions have been recorded yet."
   lines = []
   for s in recent:
       lines.append(
           f"- end_time={s.get('end_time','?')}, duration_sec={s.get('duration_seconds',0)}, "
           f"posture_score={s.get('posture_score')}, eye_strain_index={s.get('eye_strain_index')}, "
           f"avg_neck_angle={s.get('avg_neck_angle')}, avg_torso_angle={s.get('avg_torso_angle')}, "
           f"avg_blink_rate={s.get('avg_blink_rate')}, "
           f"posture_breakdown={s.get('posture_breakdown')}, eye_breakdown={s.get('eye_breakdown')}"
       )
   return "\n".join(lines)


def call_gemini(contents, system_instruction=None, response_mime_type=None):
   """Thin wrapper around the Gemini API. Returns response.text — never a
   pre-written string, always whatever the model actually generated."""
   client = get_gemini_client()
   cfg_kwargs = {}
   if system_instruction:
       cfg_kwargs["system_instruction"] = system_instruction
   if response_mime_type:
       cfg_kwargs["response_mime_type"] = response_mime_type
   config = types.GenerateContentConfig(**cfg_kwargs) if cfg_kwargs else None
   response = client.models.generate_content(
       model=GEMINI_MODEL,
       contents=contents,
       config=config,
   )
   return response.text or ""


def extract_json(text):
   t = (text or "").strip()
   if t.startswith("```"):
       t = t.strip("`")
       if t.lower().startswith("json"):
           t = t[4:]
   return json.loads(t.strip())


def build_insight_prompt(user_id, metric):
   history_text = summarize_sessions_for_prompt(user_id, limit=30)
   if metric == "posture":
       focus = (
           "Focus on posture_score (0-100, higher is better), avg_neck_angle, avg_torso_angle, "
           "and posture_breakdown (neck, torso, pitch, roll, shrug — each is points LOST, so "
           "higher means a bigger problem in that specific area)."
       )
   else:
       focus = (
           "Focus on eye_strain_index (0-10, lower is better), avg_blink_rate, and eye_breakdown "
           "(blink, ear — each is points contributing to strain, so higher is worse)."
       )
   return f"""You are a posture and eye-health analytics assistant for an app called BackTrack.
A user has recorded the following tracking sessions (most recent last):

{history_text}

{focus}

Write a short personalized report as a JSON object with exactly these keys:
- "risk_level": one of "good", "moderate", "risky", based on the recent data.
- "summary": 2-3 sentences, plain non-clinical language, explaining what the data shows and whether the trend is improving, worsening, or steady.
- "suggestions": a list of 3-4 short, specific, actionable suggestions (concrete stretches, eye exercises such as the 20-20-20 rule, desk/monitor setup changes, break scheduling) tailored to the actual patterns above — not generic advice.

Respond with ONLY the JSON object and nothing else. This is not a medical diagnosis: keep suggestions general and safe, and if risk_level is "risky" include a suggestion to consult a doctor or physical therapist."""


# ---------------- AI insight endpoints (per user) ----------------

# Cached per (user_id, metric) so switching accounts never shows a stale
# report, and each report is only regenerated when that user's session
# count actually changes (or they hit Refresh).
INSIGHT_CACHE = {}
INSIGHT_CACHE_LOCK = threading.Lock()


@app.route("/gemini/status", methods=["GET"])
def gemini_status():
   return jsonify({"configured": bool(GENAI_OK and GEMINI_API_KEY), "model": GEMINI_MODEL})


@app.route("/insights/<metric>", methods=["GET"])
@require_auth
def get_insights(metric):
   if metric not in ("posture", "eye"):
       return jsonify({"ok": False, "error": "metric must be 'posture' or 'eye'"}), 400

   uid = request.user_id
   with sessions_lock:
       session_count = len([s for s in sessions if s.get("user_id") == uid])
   if session_count == 0:
       return jsonify({"ok": False, "error": "No sessions recorded yet."}), 400

   cache_key = (uid, metric)
   force = request.args.get("refresh") == "1"
   with INSIGHT_CACHE_LOCK:
       cached = INSIGHT_CACHE.get(cache_key)
       if cached and not force and cached["session_count"] == session_count:
           return jsonify({"ok": True, "insight": cached["insight"], "cached": True})

   try:
       raw = call_gemini(build_insight_prompt(uid, metric), response_mime_type="application/json")
       insight = extract_json(raw)
   except RuntimeError as e:
       return jsonify({"ok": False, "error": str(e)}), 400
   except (json.JSONDecodeError, ValueError):
       return jsonify({"ok": False, "error": "Gemini returned an unexpected format. Try refreshing."}), 502
   except Exception as e:
       return jsonify({"ok": False, "error": f"Gemini request failed: {e}"}), 502

   with INSIGHT_CACHE_LOCK:
       INSIGHT_CACHE[cache_key] = {"insight": insight, "session_count": session_count}

   return jsonify({"ok": True, "insight": insight, "cached": False})


# ---------------- Delete all data ----------------


@app.route("/account/delete_data", methods=["POST"])
@require_auth
def delete_data():
   uid = request.user_id
   with sessions_lock:
       remaining = [s for s in sessions if s.get("user_id") != uid]
       removed = len(sessions) - len(remaining)
       sessions[:] = remaining
       save_sessions()
   with settings_store_lock:
       write_user_settings(uid, dict(DEFAULT_SETTINGS))
   activate_settings_for_user(uid)
   with INSIGHT_CACHE_LOCK:
       INSIGHT_CACHE.pop((uid, "posture"), None)
       INSIGHT_CACHE.pop((uid, "eye"), None)
   return jsonify({"ok": True, "sessions_deleted": removed, "settings": dict(DEFAULT_SETTINGS)})


# ---------------- PDF export ----------------


def _avg(lst):
   return round(sum(lst) / len(lst), 1) if lst else None


def filter_sessions_by_range(all_sessions, date_from, date_to):
   lo = hi = None
   try:
       if date_from: lo = datetime.date.fromisoformat(date_from)
   except ValueError:
       pass
   try:
       if date_to: hi = datetime.date.fromisoformat(date_to)
   except ValueError:
       pass
   out = []
   for s in all_sessions:
       try:
           d = datetime.datetime.fromisoformat(s["start_time"]).date()
       except Exception:
           continue
       if lo and d < lo:
           continue
       if hi and d > hi:
           continue
       out.append(s)
   return out


def _posture_insight(scored):
   vals = [s["posture_score"] for s in scored]
   necks = [s["avg_neck_angle"] for s in scored if s.get("avg_neck_angle") is not None]
   first, last = vals[0], vals[-1]
   direction = "trending upward" if last > first + 2 else "trending downward" if last < first - 2 else "holding fairly steady"
   text = f"Over these {len(vals)} sessions your posture score is {direction}, moving from {round(first)} to {round(last)}."
   if necks:
       text += f" Average neck angle across these sessions was {_avg(necks)} degrees."
   return text


def _eye_insight(scored):
   vals = [s["eye_strain_index"] for s in scored]
   blinks = [s["avg_blink_rate"] for s in scored if s.get("avg_blink_rate") is not None]
   first, last = vals[0], vals[-1]
   direction = "climbing" if last > first + 0.5 else "easing" if last < first - 0.5 else "holding steady"
   text = f"Your eye strain index is {direction} across these {len(vals)} sessions, from {round(first,1)} to {round(last,1)}."
   if blinks:
       text += f" Average blink rate over that span was {_avg(blinks)} per minute."
   return text


def generate_pdf_report(filtered, scored, sections, date_from, date_to, patient_name):
   if not REPORTLAB_OK:
       raise RuntimeError("The reportlab package is required for PDF export. Install it with: pip install reportlab")


   buf = io.BytesIO()
   doc = SimpleDocTemplate(
       buf, pagesize=letter,
       topMargin=0.75*inch, bottomMargin=0.75*inch,
       leftMargin=0.75*inch, rightMargin=0.75*inch,
       title="BackTrack Report",
   )


   PRIMARY = colors.HexColor("#5D7052")
   SECONDARY = colors.HexColor("#C18C5D")
   FG = colors.HexColor("#2C2C24")
   MUTED_FG = colors.HexColor("#78786C")
   BORDER = colors.HexColor("#DED8CF")
   MUTED_BG = colors.HexColor("#F0EBE5")


   styles = getSampleStyleSheet()
   h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=FG, fontSize=22, spaceAfter=2, alignment=TA_LEFT)
   meta = ParagraphStyle("meta", parent=styles["Normal"], textColor=MUTED_FG, fontSize=9.5, spaceAfter=14)
   h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=PRIMARY, fontSize=14, spaceBefore=16, spaceAfter=8)
   body = ParagraphStyle("body", parent=styles["Normal"], textColor=FG, fontSize=10, leading=15)
   note = ParagraphStyle("note", parent=styles["Normal"], textColor=MUTED_FG, fontSize=8.5, leading=12, spaceBefore=10)


   story = []
   story.append(Paragraph("BackTrack Report", h1))
   generated = datetime.datetime.now().strftime("%B %d, %Y")
   range_txt = f"{date_from or 'earliest'} to {date_to or 'latest'}"
   story.append(Paragraph(f"Prepared for {patient_name} &nbsp;·&nbsp; Generated {generated} &nbsp;·&nbsp; Range {range_txt}", meta))
   story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=12))


   if not filtered:
       story.append(Paragraph("No sessions were recorded in the selected date range.", body))
       doc.build(story)
       return buf.getvalue()


   avg_posture = _avg([s["posture_score"] for s in scored]) if scored else None
   avg_eye = _avg([s["eye_strain_index"] for s in scored]) if scored else None
   total_minutes = round(sum(s.get("duration_seconds", 0) for s in filtered) / 60)


   overview_data = [
       ["Sessions in range", str(len(filtered))],
       ["Average posture score", f"{avg_posture} / 100" if avg_posture is not None else "—"],
       ["Average eye strain index", f"{avg_eye} / 10" if avg_eye is not None else "—"],
       ["Total tracked time", f"{total_minutes} min"],
   ]
   t = Table(overview_data, colWidths=[2.6*inch, 3.4*inch])
   t.setStyle(TableStyle([
       ("FONTSIZE", (0,0), (-1,-1), 10),
       ("TEXTCOLOR", (0,0), (0,-1), MUTED_FG),
       ("TEXTCOLOR", (1,0), (1,-1), FG),
       ("FONTNAME", (1,0), (1,-1), "Helvetica-Bold"),
       ("BOTTOMPADDING", (0,0), (-1,-1), 6),
       ("TOPPADDING", (0,0), (-1,-1), 6),
       ("LINEBELOW", (0,0), (-1,-2), 0.5, BORDER),
   ]))
   story.append(t)


   def breakdown_table(title, rows):
       story.append(Paragraph(title, h2))
       data = [["Factor", "Avg. deduction"]] + [[label, (f"-{val}" if val is not None else "—")] for label, val in rows]
       tbl = Table(data, colWidths=[3.6*inch, 2.4*inch])
       tbl.setStyle(TableStyle([
           ("FONTSIZE", (0,0), (-1,-1), 9.5),
           ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
           ("TEXTCOLOR", (0,0), (-1,0), colors.white),
           ("BACKGROUND", (0,0), (-1,0), PRIMARY),
           ("BACKGROUND", (0,1), (-1,-1), MUTED_BG),
           ("TEXTCOLOR", (0,1), (-1,-1), FG),
           ("TOPPADDING", (0,0), (-1,-1), 6),
           ("BOTTOMPADDING", (0,0), (-1,-1), 6),
           ("LEFTPADDING", (0,0), (-1,-1), 10),
           ("LINEBELOW", (0,0), (-1,-2), 0.5, BORDER),
           ("BOX", (0,0), (-1,-1), 0.5, BORDER),
       ]))
       story.append(tbl)


   if sections.get("posture") and scored:
       avg_neck  = _avg([s["avg_neck_angle"] for s in scored if s.get("avg_neck_angle") is not None])
       avg_torso = _avg([s["avg_torso_angle"] for s in scored if s.get("avg_torso_angle") is not None])
       story.append(Paragraph("Posture Data", h2))
       story.append(Paragraph(
           f"Average neck angle was {avg_neck if avg_neck is not None else '—'} degrees and average torso "
           f"lean was {avg_torso if avg_torso is not None else '—'} degrees across {len(scored)} scored sessions.",
           body))
       pb = {}
       for f in ["neck","torso","pitch","roll","shrug"]:
           vals = [s["posture_breakdown"][f] for s in scored if s.get("posture_breakdown") and s["posture_breakdown"].get(f) is not None]
           pb[f] = _avg(vals)
       breakdown_table("Score breakdown — where posture points are lost", [
           ("Neck angle", pb.get("neck")), ("Torso lean", pb.get("torso")),
           ("Head pitch", pb.get("pitch")), ("Head roll", pb.get("roll")),
           ("Shoulder shrug", pb.get("shrug")),
       ])


   if sections.get("eye") and scored:
       avg_blink = _avg([s["avg_blink_rate"] for s in scored if s.get("avg_blink_rate") is not None])
       story.append(Paragraph("Eye Strain Data", h2))
       story.append(Paragraph(
           f"Average blink rate was {avg_blink if avg_blink is not None else '—'} blinks per minute "
           f"across {len(scored)} scored sessions.", body))
       eb = {}
       for f in ["blink","ear"]:
           vals = [s["eye_breakdown"][f] for s in scored if s.get("eye_breakdown") and s["eye_breakdown"].get(f) is not None]
           eb[f] = _avg(vals)
       breakdown_table("Score breakdown — sources of eye strain index", [
           ("Low blink rate", eb.get("blink")), ("Eye narrowing", eb.get("ear")),
       ])


   if sections.get("trend") and len(scored) >= 2:
       trend = scored[-14:]
       story.append(Paragraph("Trend Summary", h2))
       story.append(Paragraph(_posture_insight(trend), body))
       story.append(Spacer(1, 4))
       story.append(Paragraph(_eye_insight(trend), body))
   elif sections.get("trend"):
       story.append(Paragraph("Trend Summary", h2))
       story.append(Paragraph("Not enough sessions in range yet for a trend — record at least two.", body))


   if sections.get("sessions"):
       story.append(Paragraph("Session Log", h2))
       header = ["Date", "Duration", "Posture", "Eye strain", "Avg neck", "Avg torso", "Avg blink"]
       rows = [header]
       for s in filtered:
           try:
               d = datetime.datetime.fromisoformat(s["start_time"]).strftime("%b %d, %Y")
           except Exception:
               d = "—"
           mins = round(s.get("duration_seconds", 0) / 60)
           rows.append([
               d, f"{mins} min",
               f'{round(s["posture_score"])}' if s.get("posture_score") is not None else "—",
               f'{s["eye_strain_index"]}' if s.get("eye_strain_index") is not None else "—",
               f'{s["avg_neck_angle"]}°' if s.get("avg_neck_angle") is not None else "—",
               f'{s["avg_torso_angle"]}°' if s.get("avg_torso_angle") is not None else "—",
               f'{s["avg_blink_rate"]}' if s.get("avg_blink_rate") is not None else "—",
           ])
       tbl = Table(rows, colWidths=[0.95*inch, 0.7*inch, 0.65*inch, 0.75*inch, 0.75*inch, 0.75*inch, 0.7*inch], repeatRows=1)
       tbl.setStyle(TableStyle([
           ("FONTSIZE", (0,0), (-1,-1), 8.5),
           ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
           ("TEXTCOLOR", (0,0), (-1,0), colors.white),
           ("BACKGROUND", (0,0), (-1,0), SECONDARY),
           ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, MUTED_BG]),
           ("TEXTCOLOR", (0,1), (-1,-1), FG),
           ("ALIGN", (1,0), (-1,-1), "CENTER"),
           ("TOPPADDING", (0,0), (-1,-1), 5),
           ("BOTTOMPADDING", (0,0), (-1,-1), 5),
           ("BOX", (0,0), (-1,-1), 0.5, BORDER),
           ("INNERGRID", (0,0), (-1,-1), 0.4, BORDER),
       ]))
       story.append(tbl)


   story.append(Paragraph(
       "Generated by BackTrack. Figures are derived from webcam-based pose and eye-landmark estimation and are "
       "intended as a general wellness aid, not a medical diagnosis.", note))


   doc.build(story)
   return buf.getvalue()


@app.route("/export/pdf", methods=["POST"])
@require_auth
def export_pdf():
   uid = request.user_id
   payload = request.get_json(force=True, silent=True) or {}
   sections = payload.get("sections") or {}
   date_from = payload.get("from")
   date_to = payload.get("to")
   patient_name = (payload.get("patient_name") or "").strip() or "BackTrack User"


   if not any(sections.values()):
       return jsonify({"ok": False, "error": "Select at least one section to include."}), 400


   with sessions_lock:
       all_sessions = [s for s in sessions if s.get("user_id") == uid]


   filtered = filter_sessions_by_range(all_sessions, date_from, date_to)
   scored = [s for s in filtered if s.get("posture_score") is not None and s.get("eye_strain_index") is not None]


   try:
       pdf_bytes = generate_pdf_report(filtered, scored, sections, date_from, date_to, patient_name)
   except RuntimeError as e:
       return jsonify({"ok": False, "error": str(e)}), 500
   except Exception as e:
       return jsonify({"ok": False, "error": f"Failed to generate report: {e}"}), 500


   return Response(
       pdf_bytes,
       mimetype="application/pdf",
       headers={
           "Content-Disposition": 'attachment; filename="backtrack-report.pdf"',
           "Access-Control-Allow-Origin": "*",
           "Access-Control-Expose-Headers": "Content-Disposition",
       },
   )


if __name__ == "__main__":
   ensure_model(FACE_MODEL_PATH, FACE_MODEL_URL)
   ensure_model(POSE_MODEL_PATH, POSE_MODEL_URL)
   load_users()
   load_sessions()
   for t in [front_thread, side_thread, alert_thread]:
       threading.Thread(target=t, daemon=True).start()
   print("Backtrack backend  →  http://127.0.0.1:5050")
   print("  cam 0  iPhone/continuity  →  /feed/side")
   print("  cam 1  MacBook            →  /feed/front")
   app.run(host="127.0.0.1", port=5050, threaded=True)
