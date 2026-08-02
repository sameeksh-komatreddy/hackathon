import os, cv2, mediapipe as mp, numpy as np, math, time, json, threading, subprocess, urllib.request
from flask import Flask, Response, jsonify, request

app = Flask(__name__)
app.config["SECRET_KEY"] = "backtrack-secret"

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

BLINK_THRESH  = 0.18
EAR_THRESH    = 0.22
MIN_BLINK_WIN = 10
LOW_BLINK_RATE = 15
PITCH_THRESH  = 25
ROLL_THRESH   = 25
SHRUG_RATIO   = 0.90
NECK_THRESH   = 20
TORSO_THRESH  = 15

EAR_DUR   = 10
HEAD_DUR  = 10
BLINK_DUR = 10
SHRUG_DUR = 10
SIDE_DUR  = 30
COOLDOWN  = 60

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
}

front_frame = None
side_frame = None

last_notif = {"ear": 0, "head": 0, "blink": 0, "shrug": 0, "side": 0}
recal_front = threading.Event()
recal_side = threading.Event()

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

def check_notif(key, cond, now):
    if cond and now - last_notif[key] >= COOLDOWN:
        last_notif[key] = now; return True
    return False

def mac_notify(title, msg):
    try:
        subprocess.run(["osascript", "-e",
            f'display notification "{msg}" with title "{title}" sound name "Ping"'],
            check=False, timeout=5)
    except Exception as e:
        print(f"notify error {e}")

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
    for p in lm:
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

            if face_result.face_landmarks:
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
                    cv2.ellipse(annotated, (cx,cy), (rx,ry), 0, 0, 360, eye_col, 2, cv2.LINE_AA)

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
            blink_col = (0,220,100) if rate>=15          else (0,200,245) if rate>=10          else (30,30,255)
            pitch_col = (0,220,100) if abs(pitch)<=25    else (30,30,255)
            roll_col  = (0,220,100) if abs(roll)<=25     else (30,30,255)
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
        with lock:
            s = state
            ear_secs   = s["low_ear_secs"]
            head_secs  = s["head_secs"]
            blink_secs = s["blink_low_secs"]
            shrug_secs = s["shrug_secs"]
            side_secs  = s["bad_side_secs"]

        fatigue      = (ear_secs>=EAR_DUR or head_secs>=HEAD_DUR or blink_secs>=BLINK_DUR)
        posture      = shrug_secs >= SHRUG_DUR
        side_posture = side_secs  >= SIDE_DUR

        alerts = []
        notifs = []
        if fatigue:      alerts.append("Fatigue detected — take a break.")
        if posture:      alerts.append("Shoulders too high — relax them.")
        if side_posture: alerts.append("Hunching detected — sit up straight.")

        if check_notif("ear",   ear_secs>=EAR_DUR,     now): mac_notify("Backtrack · Eye Strain","Your eyes are narrowing."); notifs.append("low_ear")
        if check_notif("head",  head_secs>=HEAD_DUR,   now): mac_notify("Backtrack · Head Tilt","Head tilt detected.");       notifs.append("head_tilt")
        if check_notif("blink", blink_secs>=BLINK_DUR, now): mac_notify("Backtrack · Blink Rate","Blink more often.");        notifs.append("low_blink")
        if check_notif("shrug", shrug_secs>=SHRUG_DUR, now): mac_notify("Backtrack · Posture","Relax your shoulders.");      notifs.append("shrug")
        if check_notif("side",  side_secs>=SIDE_DUR,   now): mac_notify("Backtrack · Posture","Sit up straight.");           notifs.append("hunching")

        with lock:
            state.update({"fatigue_alert":fatigue,"posture_alert":posture,
                           "side_posture_alert":side_posture,"alerts":alerts,"notifications":notifs})
        time.sleep(0.5)

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

@app.route("/recalibrate",       methods=["POST"])
def recalibrate():       recal_front.set(); recal_side.set(); return jsonify({"ok":True})
@app.route("/recalibrate_front", methods=["POST"])
def recalibrate_front(): recal_front.set();                   return jsonify({"ok":True})
@app.route("/recalibrate_side",  methods=["POST"])
def recalibrate_side():  recal_side.set();                    return jsonify({"ok":True})

if __name__ == "__main__":
    ensure_model(FACE_MODEL_PATH, FACE_MODEL_URL)
    ensure_model(POSE_MODEL_PATH, POSE_MODEL_URL)
    for t in [front_thread, side_thread, alert_thread]:
        threading.Thread(target=t, daemon=True).start()
    print("Backtrack backend  →  http://127.0.0.1:5050")
    print("  cam 0  iPhone/continuity  →  /feed/side")
    print("  cam 1  MacBook            →  /feed/front")
    app.run(host="127.0.0.1", port=5050, threaded=True)