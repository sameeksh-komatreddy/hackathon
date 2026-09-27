# P3 Detection port

Source of truth: `backend_pm.py` (grep function names; don't read the whole file). Everything goes in `web/src/core/`.

## S05 ⚙ Metrics and scoring
- Port these as pure functions to `core/metrics.js`: `get_ear`, `get_angle`, `compute_posture_breakdown`, `compute_posture_score`, `compute_eye_strain`, `compute_eye_breakdown`.
- Head pose: take pitch and roll from the face model's transformation matrix instead of OpenCV `solvePnP`/`RQDecomp3x3`. Check the sign conventions match the Python output.
- Port `DEFAULT_SETTINGS` and `SETTINGS_BOUNDS` to `core/settings.js`.
- Port the matching cases from `tests/test_backend.py` to Vitest.
- **Done when:** the ported tests pass with the same numbers as Python.

## S06 Tracking loops
- `core/tracker.js`: front loop (eye openness, blink detection and rate over a 60 s window, head pitch/roll, shrug) and side loop (neck and torso angles). This replaces `front_thread`/`side_thread`.
- Use real frame timestamps (G10). Mirror the front view only on the display canvas.
- Emit the same state shape the old `/stream` sent, so the UI port is easier.
- **Done when:** a dev page shows live values that match the Python app for the same pose.

## S07 ★ Calibration and camera picker
- Guided calibration: "Sit up straight and look at the screen" → 3-second countdown → record baselines for shrug, pitch, roll, and neck/torso. Scores then measure the difference from your own neutral position (G9, U3). Both Recalibrate buttons rerun it.
- Camera picker with `enumerateDevices()`: front and side slots, remembered by `deviceId`. Handle permissions and unplugged cameras. This replaces `cameras.py`.
- **Done when:** both slots work with two webcams, and recalibrating visibly moves the baseline.

## S08 Alert engine
- Port `alert_tick`: duration timers, the progress value, and a cooldown per alert type. **Only active while recording** (B2); release the cameras when not recording or previewing.
- Quiet hours (U2): suppress notifications, not tracking.
- Output events only; delivery comes in S20.
- **Done when:** Vitest covers the timer and cooldown logic, and no alert fires while not recording.
