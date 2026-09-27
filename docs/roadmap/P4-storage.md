# P4 Local storage

## S09 Schema and data layer
- Use Dexie (`npm i dexie`) for IndexedDB; test with `fake-indexeddb`.
- Schema v1, in `storage/db.ts`:
  - `profiles`: `id`, `name`, `createdAt`. Optional; one profile is created automatically on first run.
  - `sessions`: same fields as the Python `session_record`, plus `profileId` and `schemaVersion`. Index on `[profileId+startTime]`.
  - `settings`: `profileId`, then the threshold values, quiet hours and theme.
- `storage/repo.ts`: the only module the UI talks to (listSessions, addSession, getSettings, saveSettings, deleteProfileData).
- ★ Write down the migration rule: bump the Dexie version and add an upgrade function whenever the schema changes.
- **Done when:** the data layer tests pass.

## S10 ★ Data durability
Browsers can clear IndexedDB under storage pressure, or when the user clears site data.
- Call `navigator.storage.persist()` after the first saved session; show the result in Settings.
- Settings → "Back up data" (downloads JSON) and "Restore" (validate the file, then merge by session id).
- Save the in-progress session every 30 s. On reload, offer to recover a session that was never finished (a closed tab otherwise loses it).
- "Delete all my data" and "Delete profile" (G5). Handle a full disk (`QuotaExceededError`) with a clear message.
- Optional: import the old `~/.backtrack/sessions.json` from the Python version.
- **Done when:** a round trip through backup and restore gives identical data, and killing the tab mid-session offers recovery.
