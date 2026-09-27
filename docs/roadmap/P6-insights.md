# P6 Premade insights (replaces Gemini)

Deterministic, offline, free. The output shape stays the same as the Gemini version (`risk_level`, `summary`, `suggestions[3-4]`), so the UI cards don't change. Code lives in `web/src/core/insights/`.

## Features computed from the last 14 scored sessions (per metric)
| Feature | Values |
|---|---|
| level | posture: good ≥85, fair 70–84, poor <70 · eye strain: low ≤2, moderate 2–5, high >5 |
| trend | slope over the last 5 sessions: improving / steady / worsening (steady = within ±2 posture points or ±0.5 strain) |
| dominant | largest average penalty: neck, torso, pitch, roll, shrug · blink, ear |
| modifiers (0–n) | `long_sessions` (average over 60 min), `late_night` (most sessions end after 22:00), `erratic` (high spread), `single_camera`, `few_sessions` (under 3) |

Pattern key = `metric.level.trend` (9 per metric). Suggestions are tagged by `dominant` and by modifier.

## Library format (`library.json`)
```json
{ "summaries": { "posture.poor.worsening": ["Your posture score dropped from {first} to {last} ..."] },
  "suggestions": { "posture.neck": ["Raise your monitor so the top edge is at eye level.", "..."] },
  "modifiers": { "late_night": ["Most sessions end after 10 PM ..."] } }
```
- Summaries: 3 variants per key. Suggestions: 6–8 per tag. Pick variants deterministically, seeded by the session count, so they rotate without random flicker.
- Picking suggestions: 2 from `dominant`, 1 from the strongest modifier, 1 general. No duplicates.
- Risk level: good → good; fair → moderate; poor → risky. A worsening trend moves up one level.
- Safety: a `risky` result always includes a suggestion to see a doctor or physical therapist, the disclaimer is always shown, and no text makes medical claims.

## S14 Classifier
- `classify(sessions, metric)` → `{key, dominant, modifiers, slots}`, and `render(classification, library)` → the insight object.
- **Done when:** Vitest covers every level/trend combination, and a coverage test proves every reachable key and tag has library text.

## S15 Library content
- Write about 200 strings: 18 summary keys × 3 variants, 7 tags × 7 suggestions, and the modifiers. Base the advice on common guidance (the 20-20-20 rule, monitor height, chin tucks, shoulder rolls, break timing).
- ★ The user reviews the tone and safety of the text before merging.
- **Done when:** the coverage test passes and the user has approved the text.

## S16 Wire up and remove Gemini
- History AI cards → insights engine, relabelled "Personalized report". The "Session insight" line under each chart and the PDF "Trend summary" section use the same engine.
- Remove `google-genai` and `python-dotenv` from requirements, `.env.example`, and every Gemini mention in the UI and README.
- **Done when:** the app makes no network requests after it has loaded, except phone pairing (P7).
