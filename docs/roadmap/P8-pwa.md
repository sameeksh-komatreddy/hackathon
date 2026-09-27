# P8 Notifications and offline

## S20 Browser notifications
- Ask for notification permission only when the user first presses Start recording, with a short explanation first. Browsers penalise sites that ask on page load.
- Use `new Notification()`, or `registration.showNotification()` once S21 adds a service worker. Show the in-page toast when the tab is visible.
- If permission is denied: in-page toast plus an optional sound, and a note in Settings.
- Apply what S04 found about hidden tabs (for example, a "keep this tab visible" hint).
- **Done when:** an alert reaches the OS notification centre while another app is focused, on Windows and macOS Chrome.

## S21 ★ Offline and installable
- Use `vite-plugin-pwa` (Workbox). Precache the app shell, the MediaPipe WASM files and the `.task` model files (several MB) so the app works fully offline after the first visit.
- Web manifest: name, icons, `display: standalone`.
- Update flow: a "New version available — reload" prompt. Never reload silently in the middle of a recording.
- **Done when:** a Lighthouse PWA check passes, and the installed app records a session with the network off.
