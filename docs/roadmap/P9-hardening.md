# P9 Production hardening

## S22 ★ Privacy, disclaimer and consent
- Privacy page: video is processed on the device, no analytics, and data is deleted by clearing it in Settings. The phone link sends video only phone-to-computer, peer to peer and encrypted; the signalling server sees only a temporary pairing code and network addresses. This has to be true, so verify the only network calls are to signalling (S16, P7).
- Health disclaimer: a wellness aid, not a medical device or diagnosis. Shown at first run, in the footer and in the PDF.
- First-run flow: explain the camera use → consent → create the profile → camera picker → calibration.
- **Done when:** a new user reaches their first recording without instructions.

## S23 ★ Security and supply chain
- Serve the MediaPipe WASM and models from the site itself; no CDN at runtime (fits the offline and privacy claims).
- Cloudflare `_headers` file: a strict Content-Security-Policy (`default-src 'self'`, with `wasm-unsafe-eval` for MediaPipe, and `connect-src` for the signalling Worker), `Permissions-Policy: camera=(self)`, `Referrer-Policy`, `X-Content-Type-Options`.
- Remove inline scripts and `innerHTML` built from data (use `textContent`). Run `npm audit` in CI.
- **Done when:** the deployed site has no CSP violations in the console, and the securityheaders.com grade is A.

## S24 ★ Accessibility and devices
- Keyboard navigation, focus states, labels on sliders and selects, text alternatives for charts, colour contrast in both themes.
- Layout at phone width. Recording is meant for desktop, but History and Export should work on a phone.
- Browser checks on Chrome, Edge, Firefox and Safari. Document any browser that isn't supported.
- **Done when:** Lighthouse accessibility ≥95, and there's no horizontal scroll at 375 px.

## S25 ★ Performance and end-to-end tests
- Frame budget: sample at about 15 fps, use lower-resolution input, and skip the pose model on alternate frames if needed. Pause detection when not recording. Check CPU and battery on a low-end laptop.
- Playwright smoke test in CI with a fake camera (`--use-fake-device-for-media-stream`): onboarding → record 10 s → history shows the session → PDF downloads.
- **Done when:** the end-to-end test runs in CI, and CPU usage is acceptable on the slowest test machine.
