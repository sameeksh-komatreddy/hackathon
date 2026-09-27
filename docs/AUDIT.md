# Audit findings (2026-09-26)

Taken from the Python version (`backend_pm.py` + `frontend_pm.html`). "Fix in" names the roadmap session that resolves each item. "Obsolete" means the browser-only design removes the problem.

## Bugs

| ID | Bug | Where | Fix in |
|----|-----|-------|--------|
| B1 | AI "Refresh" buttons share the `recal-btn` class, so each click also sends a side recalibration | `frontend_pm.html:735,779,1386` | S11/S12 |
| B2 | Notifications fire and the webcam stays on even when not recording or signed in | `backend_pm.py:1090-1094` | S08 |
| B3 | Starting a session silently discards another user's recording in progress | `backend_pm.py:1364` | Obsolete |
| B4 | "Sessions logged" and the averages stop at 30 sessions (`limit=30`) | `frontend_pm.html:1928` | S12 |
| B5 | The sidebar "latest score" isn't cleared for a user with no sessions | `setEmptyHistoryState` | S12 |
| B6 | The default export range is built in UTC, so it can be a day off in the evening | `frontend_pm.html:2104` | S13 |
| B7 | Opening Settings switches the live thresholds to that user's values mid-recording | `backend_pm.py:1230` | Obsolete |
| B8 | The root page says "Open index.html", which doesn't exist | `backend_pm.py:1181` | Obsolete |

## Placeholders and unfinished work

| ID | Item | Fix in |
|----|------|--------|
| U1 | Theme picker only moves the highlight; no dark theme exists | S12 |
| U2 | Reminder frequency and quiet hours are shown but never read | S08 (quiet hours); drop reminder frequency or add it in S20 |
| U3 | Side "Recalibrate" does nothing; front only resets the shrug baseline | S07 |
| U4 | README claims lighting analysis; none exists | S01 (fix claim), P11 |
| U5 | README says notifications come from trends; they're threshold timers | S01 |
| U6 | README sentence cut off ("…asking the") | S01 |
| U7 | `screen_distance.py` is an unconnected prototype | P11 |
| U8 | Old iteration files, unused `SECRET_KEY`, `.DS_Store`, Mac-only `.vscode/launch.json` | S01 |

## Gaps between local-testing quality and production

| ID | Gap | Resolution |
|----|-----|------------|
| G1 | Tracking runs in local Python; the page is only a viewer | P2–P3 |
| G2 | One global tracking state shared by all accounts | Obsolete (one user per browser) |
| G3 | Flask development server; a thread per open stream | Obsolete (static site) |
| G4 | Login tokens in memory only, no expiry, passed in URLs, weak password rules, no rate limit | Obsolete (no accounts, D2) |
| G5 | No password reset or account deletion | Obsolete; S10 adds "delete profile" |
| G6 | CORS allows origin `null` | Obsolete |
| G7 | All data in JSON files: non-atomic writes, no schema version, no backups | S09–S10 |
| G8 | Gemini key must be on the server; free-tier data may be used by Google | S16 (removed) |
| G9 | Shoulder baseline taken from the first frame with no prompt; head angles are absolute | S07 |
| G10 | Frame timestamps faked at 33 ms instead of real time | S06 |
| G11 | Notifications are sent by the desktop OS; `win10toast` missing from requirements | S20 |
| G12 | Phone link needs a self-signed certificate warning, the same Wi-Fi and firewall rules | S18–S19 (WebRTC) |
| G13 | The frontend has no tests | S05+, S25 |
