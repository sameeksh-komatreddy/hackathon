## Inspiration

We were inspired by our own lives. Hunched over hours of schoolwork, we noticed our posture slowly worsening and our eyes becoming strained from long, late night study sessions. Given the opportunity to focus on the home life and bring some improvement, we decided to develop an application that would benefit students just like us. Additionally, we wanted to help people like our parents, facing similar issues hunched over their work from home.

## What it does

AL-I (Analytics Lifestyle Interface), which is a pun on the word Ally, as we hope this application will be for our users, utilizes video detection software to obtain certain landmarks on the user's body. For example, our application detects the position of your eyelid, ear, shoulder, hip, etc. Then, based on the position and angles between the different landmarks, the application is capable of identifying when you have a bad posture, are straining your eyes, etc. and for how long. Then, if a problem lasts past a set time (for example, slouching for a few minutes), it sends a notification reminding the user to fix it.

We used MediaPipe and openCV to extract the landmarks from the user's camera and to overlay the relative positions and angles on top of the video itself to enable layman analyzation.

For example, one of our datapoints is the user's EAR value, which determines how open their eyes are to be used for fatigue. Here is the equation we had to use:

$$\\text{EAR} = \frac{||p_2 - p_6| + |p_3 - p_5||}{2|p_1 - p_4|}$$

Additionally, to find the proximity of the shoulders to the ear (in order to detect sustained shoulder elevation), we used this equation:

$$\text{Ratio} = \left( \frac{|\text{Shoulder}_y - \text{Ear}_y|}{\text{Torso Height}} \right) \times 100$$

Additionally, in order to obtain the angle of inclination for their cervical (head) posture, we utilized this equation:

$$\theta = \tan^{-1} \left( \frac{\Delta y}{\Delta x} \right)$$

Lastly, we connected a Gemini API key to the application which analyzes the collected data and recognizes trends and incorporates more long-term changes the user can make.

## Challenges we ran into

While we originally thought splitting into different teams would be a good way to ensure work runs as smoothly, we faced issues when we had to merge all of our code. Some of us worked on the backend, with little care for the front end, while others worked on the front end, with little care for the backend making this process very tedious. There were times we thought that we wouldn't finish with the stress that we were facing. All of our concerns were alleviated when one of our laptops suddenly got a notification telling us to sit up straight; our app had worked!

## Running locally

The current version is `backend_pm.py` + `frontend_pm.html` (with `cameras.py`, `phone_link.py` and `phone_camera.html`). Earlier iterations are kept in `legacy/`.

### 1. Install

Works on Windows, macOS and Linux. Tested with Python 3.12.

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

For AI tips, copy `.env.example` to `.env` and paste in a Gemini API key. Everything else works without it.

### 2. Start

```
python backend_pm.py
```

Then open `frontend_pm.html` in your browser and create an account. The first run downloads the MediaPipe models into `~/.backtrack`, which is also where accounts, sessions and settings are kept.

- **macOS:** allow Terminal (or your editor) to use the camera under System Settings → Privacy & Security → Camera.
- **Windows / macOS:** you'll be asked whether Python may accept network connections. Allow it on private networks; that's what lets a phone connect.

### 3. Cameras

BackTrack has two camera slots:

- **Front** faces you and tracks your eyes, head tilt and shoulders.
- **Side** sits beside you and tracks your neck and back angle.

With a single webcam, it becomes the front camera and the side slot waits for a phone. Pick or swap cameras in the **Cameras** card on the Record tab; your choice is remembered. You can record with just one camera: the scores use whatever that camera can see.

### 4. Using a phone as a camera

Any phone with a browser works with any computer. No app is needed.

1. Put the phone on the same Wi-Fi as the computer.
2. On the Record tab, scan the QR code with the phone's camera.
3. The phone warns that the connection isn't private. BackTrack uses its own certificate because the link never leaves your Wi-Fi. Tap **Show Details → visit this website** (iPhone) or **Advanced → Proceed** (Android). You only do this once.
4. Tap **Start camera** and allow camera access.

If it won't connect:

- Check the computer's firewall allows Python (on Linux: `sudo ufw allow 5051/tcp`).
- School, work and guest Wi-Fi often block devices from reaching each other. Use your phone's hotspot instead, then press **New code**.

### 5. Tests

```
pip install pytest
python -m pytest tests
```
