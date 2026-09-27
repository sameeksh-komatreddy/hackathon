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
_(fill in)_
