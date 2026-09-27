# P5 UI on local data

Replace `web/src/api.js` (from S02b) with calls to `storage/repo.js`, and subscribe to `core/tracker.js` through a `useTracker` hook. Remove the login screen (D2). Add a profile switcher only if more than one profile exists.

## S11 Record tab
- Live canvases from `core/tracker.js` replace the MJPEG `<img>` feeds. Threshold bars, live readout, timer, Start/Stop → `repo.addSession`.
- Give the Recalibrate buttons their own class (B1).
- **Done when:** a recorded session appears in IndexedDB with the full shape.

## S12 History and Settings
- History: read every session, not just the last 30 (B4). Clear the sidebar score when there's no data (B5). Keep the SVG charts.
- Settings: sliders save to the `settings` table and apply live. Quiet hours control. Remove reminder frequency unless S20 adds it (U2).
- Dark theme (U1): tokens on `:root`, a `[data-theme=dark]` override, following `prefers-color-scheme` by default. Remember the choice in settings.
- **Done when:** both tabs work offline with the Python backend stopped.

## S13 ⚙ Export tab
- Port `generate_pdf_report` to jsPDF with `jspdf-autotable` (the tables and colours from `backend_pm.py:1669`).
- Build the date range from local time (B6).
- **Done when:** the downloaded PDF matches the old report's sections.
