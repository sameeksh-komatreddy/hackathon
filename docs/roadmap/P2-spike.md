# P2 Feasibility check (go/no-go)

## S04 ★ MediaPipe in the browser
The whole plan depends on this, so test it before porting anything.

- Throwaway page `web/spike.html`: `@mediapipe/tasks-vision` running FaceLandmarker (with `outputFacialTransformationMatrixes: true`) and PoseLandmarker lite in `VIDEO` mode on a `getUserMedia` stream. Draw the landmarks on a canvas.
- Measure and record:
  1. Frame rate on the team's slowest laptop, with both models on, GPU and CPU delegates.
  2. **Background tab:** switch tabs for 2 minutes. Does detection keep running, and at what rate? Browsers throttle hidden tabs, and `requestAnimationFrame` stops entirely. Try `requestVideoFrameCallback` and a `setInterval` loop.
  3. Chrome, Edge, Firefox and Safari (macOS and iOS if possible).
  4. Two webcams open at once (replaces the Python side camera).
- **Gate:** if hidden-tab tracking drops below about 1 frame per second, record a fallback in the ROADMAP decisions table. Options: tell users to keep the tab visible or in a small window; run in a Document Picture-in-Picture window (Chromium); or accept lower-rate sampling (posture changes slowly, but blink rate needs more than 10 fps).
- **Done when:** the results and the gate decision are written into this file under "Results", and the spike page is deleted.

## Results

### Round 1: Windows, Chrome and Edge (2026-10-03)
Tested on the dev laptop, driven by script with the browser's fake camera (a moving test pattern with no face in it), so the absolute speeds are only a guide. The hidden-tab results come from the browser itself, so they should hold on real cameras.

**Hidden tab (switched away for 2 minutes, GPU, 1 camera):**

| Loop | Chrome hidden fps | Edge hidden fps |
|------|-------------------|-----------------|
| requestAnimationFrame | 0 (stops) | not run (same engine) |
| requestVideoFrameCallback | 0 (stops) | 0 (stops) |
| setInterval 33 ms | 30 | 30 |
| Worker timer 33 ms | 30 | 31 |

- 6 minutes hidden (past the 5-minute point where Chrome throttles harder): Worker timer 31 fps (min 28), setInterval 30 fps (min 24, one 244 ms gap).
- Minimized window, 60 s: Worker timer 24 fps, setInterval 30 fps.
- Why timers aren't throttled: Chrome does not throttle tabs that are using a camera. So this only holds while the camera is live, which is fine because we only track while recording.

**Speed while visible (fake camera):**
- GPU, 1 camera: face ~8-10 ms + pose ~9-10 ms per frame, so ~30 fps (capped by the 33 ms loop).
- CPU, 1 camera: face ~15 ms + pose ~31 ms, ~21 fps.
- GPU, 2 cameras (face+pose on front, pose on side): ~38 fps each, still fine when hidden.
- CPU, 2 cameras: ~22 fps each, 23 fps hidden.

**Bug found and fixed:** a Worker that ticks every 33 ms no matter what froze the page when a frame took longer than 33 ms (CPU, 2 cameras), because ticks queued up faster than they were handled. The fixed loop waits for each frame to finish before sending the next tick. The real tracking loop (S06) must do the same.

**Gate:** passed on Chrome and Edge. Hidden-tab tracking stays at about 24-31 fps, far above 1 fps, so no fallback is needed there.

### Still to test (needs other machines)
- [ ] The team's slowest laptop, real webcam with a face in view, GPU and CPU
- [ ] Firefox (not installed on the dev laptop)
- [ ] Safari on macOS, and iOS if possible
- [ ] Two real webcams at once

How to run: `cd web && npm run dev`, open `http://localhost:5173/spike.html`, pick settings, Start, wait 10 s, switch tabs for 2 minutes, come back, press "Copy results" and paste the output here. Safari/iOS need HTTPS for the camera unless on localhost.

