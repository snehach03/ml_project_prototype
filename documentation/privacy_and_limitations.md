# Privacy, security and limitations

## What the system collects
Per minute, only numbers: counts of keystrokes (by class), corrections, spaces, arrow/shortcut keys, mouse distance,
clicks, drags, scroll bursts, page blur/hidden events, typing-interval mean/std and idle seconds.

## What it never collects
Typed text or key identities (a key is classified and discarded inside `frontend/src/lib/tracker.js`), passwords
(password inputs and any element inside `data-private` are ignored entirely), messages, page content, URLs, window
titles, anything outside the tab. `src/test/tracker.test.js` asserts that a typed secret never appears in the output.
The API additionally rejects any field it does not know (`extra="forbid"`), so text cannot be uploaded even by a
modified client.

## Controls
- Explicit consent dialog before every start; the API refuses to start without `consent: true` and the current consent version.
- The user can stop at any time; a partial minute is discarded.
- Delete one session or all data from the History page (`DELETE /api/sessions/{id}`, `DELETE /api/data`).
- Retention: sessions older than `DATA_RETENTION_DAYS` (default 90) are purged at start-up.
- Sessions are scoped to an anonymous per-browser id; other ids get 404/closed sockets.
- Monitoring only runs while the tab is open and only observes that tab.

## Honest limitations
1. Trained on 25 participants / 75 labelled blocks; the stress model has weak held-out signal (see
   `model_evaluation_report.md`). The workload model showed **no reliable signal** and is labelled so in the UI.
2. Training data came from system-wide logging; browser events only approximate it (distribution shift).
3. The score is relative to the user's own baseline and is not a calibrated probability.
4. A provisional baseline taken from the current session damps real changes; real baselines need earlier sessions.
5. Not a diagnosis. Do not use for medical, hiring, performance-management or disciplinary decisions. Do not deploy to
   monitor other people without their informed consent and appropriate legal review.

## Production hardening still needed
The per-browser client id is not authentication. Before real use add user accounts (e.g. OAuth), HTTPS only, per-user
authorisation on every route, rate limiting at the proxy, database encryption at rest and backups, and a reviewed privacy policy.
