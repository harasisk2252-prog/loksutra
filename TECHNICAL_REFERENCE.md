# LokSutra — India's Living Knowledge Universe

**Technical reference:** See [README.md](README.md) for setup and [TEST_REPORT.md](TEST_REPORT.md) for test coverage.

An existing FastAPI + SQLite + HTML/CSS/JavaScript prototype, improved in place for the Gnani AI Internship Challenge. Public visitors browse stories; the owner signs in to transcribe, create, and edit. The original visual theme, sample stories, archive, steps, and constellation are retained.

## Run locally on Windows

**Easiest:** double-click `Set Owner Password.cmd` for the private masked dialog, then double-click `Start LokSutra.cmd`. Both locate the project automatically. See [PASSWORD_SETUP.md](PASSWORD_SETUP.md) for CMD/VS Code instructions.


Open PowerShell in this folder:
```powershell
cd 'C:\Users\dell\Downloads\LokSutra_Hackathon_Project (2)\LokSutra'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Do not overwrite an existing .env:
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe setup_owner.py
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Open http://127.0.0.1:8000. Use your owner password in the capture studio. Restart the server after changing .env. Do not run more than one worker/instance for this prototype.

### Exactly where the API key goes

Edit this file locally, beside main.py:

**C:\Users\dell\Downloads\LokSutra_Hackathon_Project (2)\LokSutra\.env**

Enter the key after **GNANI_API_KEY=** on the first setting line. Never paste it into chat, screenshots, JavaScript, source code, or GitHub. The backend loads this exact file regardless of the shell's working directory; real environment variables take precedence. The owner password is separate from your Gnani key. setup_owner.py opens a masked graphical dialog on Windows and stores a salted scrypt hash, not the password. Mismatches can be corrected without restarting setup.

.env, databases, audio, temporary output, tools, and virtual environments are ignored by Git. .env.example contains empty placeholders only. The server serves only the frontend directory, not the project root.

### FFprobe

FFprobe is required for local audio validation. The original development folder used portable FFprobe and FFmpeg under `tools/`; source-only distributions exclude the binaries. On Windows, preserve your existing tools folder or install FFmpeg/FFprobe separately. The backend finds `tools/ffprobe.exe` automatically if present.

On another machine, install FFmpeg/FFprobe using the [FFmpeg download guidance](https://ffmpeg.org/download.html). Put ffprobe on PATH or set FFPROBE_PATH in .env to its absolute executable path. On macOS/Linux use python3 and .venv/bin/python in place of the Windows commands.

## Verified official Gnani contract

Reviewed against [REST transcription](https://docs.gnani.ai/api/STT/speech-to-text) and [limits](https://docs.gnani.ai/api/STT/limits).

- POST https://api.vachana.ai/stt/v3
- Authentication: X-API-Key-ID header, populated only by the backend.
- Multipart: audio_file (binary), language_code (locale), format=transcribe.
- model is omitted, selecting the documented Prisma v2.5 default. The returned model is not invented.
- Success requires success=true and a string transcript. Empty speech is shown without overwriting the draft. Truncation produces a warning.
- No configurable guesswork about endpoint, Bearer prefix, file field, or response field remains.

| Language | Code |
| --- | --- |
| Bengali | bn-IN |
| English | en-IN |
| Gujarati | gu-IN |
| Hindi | hi-IN |
| Kannada | kn-IN |
| Malayalam | ml-IN |
| Marathi | mr-IN |
| Punjabi | pa-IN |
| Tamil | ta-IN |
| Telugu | te-IN |

Audio: WAV, MP3, OGG, FLAC, AAC, M4A. This REST mode permits **up to 30 seconds**. The **12 MB size cap is LokSutra's own limit**, not an asserted Gnani limit. File suffix, nonempty content, bounded bytes, audio-stream metadata and duration are checked; FFprobe runs with a 10-second timeout and restricted protocols. Temporary audio is removed. Gnani can still reject malformed audio; these errors are handled safely.

The application has no built-in microphone recorder. Record using your device, then upload the resulting supported file.

## Workflow and guarantees

1. Owner signs in; visitors remain read-only.
2. Upload audio, select its language, confirm permission, and transcribe.
3. Review and correct the result. A late response cannot replace text you have edited. Existing text gets a separate result preview with an explicit replace action.
4. Save the story. Input remains on failure. A unique save identifier prevents duplicate creates when a committed response is lost and retried.
5. Search by title, transcript, contributor, region, language, category, or tags, including Hindi/Punjabi text. Search is debounced and stale requests cannot repaint newer results.
6. Browse metadata connections and open sentence-based learning steps. Pages show up to eight graph nodes; all matching stories remain reachable.
7. The owner can edit a story. New/edited contributions remain unverified; illustrative seeds keep their explicit sample label.

Saving clears the current search so the new story appears, refreshes archive counts and graph, and opens its details. Counts describe the full archive; the search status describes matches. If refreshing fails after saving, the app says the save succeeded and offers a refresh retry.

## Architecture — easy English

The browser displays stories and collects the owner's input. FastAPI checks the owner session, request size, CSRF token, and rate limits before accepting writes. For transcription, it checks the file locally and sends it to Gnani using a private key. Gnani returns words; the owner corrects them. SQLite stores the corrected story and metadata. Search is a case-insensitive text match. Graph edges mean shared category, language, or region, not AI-discovered meaning.

## Architecture — Hinglish

Browser par stories dikhti hain. Owner login karke audio upload karta hai. FastAPI pehle session, CSRF token, file size aur duration check karta hai. Phir backend secret API key se Gnani ko audio bhejta hai. Transcript wapas aata hai; owner galtiyan correct karke save karta hai. SQLite mein story aur metadata store hota hai. Search text match karta hai. Constellation shared category, language aur region dikhata hai—semantic AI nahi.

## API and security

Public: GET /api/health, /api/config, /api/stories?q=..., /api/auth/session.
Owner access: POST /api/auth/login, /api/auth/logout.
Owner writes: POST /api/stories, PUT /api/stories/{id}, POST /api/transcribe.

Login accepts JSON {password}; it returns a CSRF token and sets a one-hour HttpOnly, SameSite=Strict session cookie. Writes must send that cookie and X-CSRF-Token. POST /api/stories also accepts a UUID Idempotency-Key; reuse the same key only for a retry of the same payload. Existing story language names are preserved; STT uses locale codes. Error responses use a safe detail string, never raw credentials or upstream bodies.

No owner hash means writes are disabled. Sessions are stored server-side; changing the password hash invalidates existing sessions. Login has global and per-IP throttles. Writes have an owner-wide 30/minute budget; transcription has 6/minute and one-in-flight limits. A failed attempt can count against these limits. Do not trust arbitrary proxy headers.

Production requires APP_ENV=production, an HTTPS PUBLIC_ORIGIN, and a valid owner hash. Cookies become Secure and HSTS is enabled. Before any separately approved deployment: use HTTPS, a persistent private SQLite volume, one instance/worker, backups, trusted host/proxy settings, and platform request limits. Do not expose the development server directly. Authentication is implemented, but hosting infrastructure has not been deployed or audited.

Existing databases get an additive is_sample column and auth/idempotency tables; existing stories are retained. Only exact legacy seed matches are marked illustrative. Back up a real database before its first upgraded launch.

## Tests and live verification

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
node --check frontend/app.js
node --test tests/frontend_config.test.cjs
```

Chrome must be installed for browser tests. FFprobe is required for real audio and browser tests; those tests explicitly skip if missing. Tests use temporary databases and httpx.MockTransport, never a real Gnani key. Browser tests run a local server with mocked transcription and real local audio validation.

See VERIFICATION.md for actual results and limitations. requirements-lock.txt records the installed test environment.

A live call is a separate opt-in step:
```powershell
.\.venv\Scripts\python.exe live_smoke.py --audio 'C:\Users\dell\Music\fulkari.ogg' --language pa-IN
```

The helper validates locally, then asks you to type SEND before transmitting. It makes one request, prints the actual transcript or safe failure, and saves a local result under ignored test-results. It never prints the API key. A real response is not proof of transcript accuracy; compare with the speaker.

## Longer cultural recordings

The original 30-second cap belongs to REST, not to the preservation use case. Gnani documents a separate asynchronous Batch API for longer audio. See LONG_AUDIO.md for verified endpoints/limits and the unresolved account-credit check. Long mode is implemented as a separate, default-disabled 10-minute / 10 MB Batch studio with durable jobs. Confirm pricing, entitlement and a consented test before enabling GNANI_BATCH_ENABLED=true locally. Live Batch remains unverified.

## Challenge handoff

At the time of the original documentation, the [official challenge](https://www.gnani.ai/internship) listed a November 10, 2026, 11:59 PM IST deadline (check the organizers for the current deadline). It requested a public working-demo post, a written explanation, model/API identification, and contributor roles. Prepare those items honestly; publication/submission is the owner's action. No deployment, GitHub push, public post, or submission has been performed.

Limitations: no community accounts, moderation, factual verification, source-audio retention, automatic translation, TTS, semantic search, generated lessons, offline mode, or live-verified long-audio processing. No award, shortlist, or internship is guaranteed.

## Submission materials
SUBMISSION.md contains the project explanation and clearly marked creator/team fields that still require your input. DEMO_AND_SUBMISSION_CHECKLIST.md contains the narration, story fields, post draft and final submission steps. Run .\start_local.ps1 to set up owner access if needed and start the app locally.

Build the source-only ZIP with:
```powershell
.\.venv\Scripts\python.exe -B package_submission.py
```
The ZIP is written to submission/LokSutra_Submission_Source.zip. The packager uses an explicit source-file allowlist and checks included files for local credentials without printing them. It excludes .env, databases, audio, tools, the virtual environment and private test artifacts. Rebuild it after filling creator details. No publishing, deployment or Git push is performed by packaging.

## Heritage discovery update — November 11
Language, category, region and sample/contribution filters combine with Unicode search.
The constellation follows the filtered results. Related reading trails explain shared metadata.
Download a Unicode text chapter with attribution and explicit review status. Local audio preview
uses a temporary browser object URL; selecting or playing audio makes no Gnani request.
No audio is retained by these additions. Long-audio Batch is implemented behind a default-off local setting; live Batch and synthetic voice remain unverified/unimplemented respectively.

The official challenge page now lists November 15, 2026 at 18:00 IST as the deadline:
https://www.gnani.ai/internship . Aim to finish submission before 6 PM IST.
The owner reports approximately INR 4,900 credit remaining; account pricing and balance are
not independently verified. No credits were spent developing these discovery features.


See LONG_AUDIO.md for Batch enablement, documented limits, recovery boundaries and private transcript handling. Use Upload, Start processing, Refresh status, then Use in a new story to correct and save. Credits are never estimated from an unverified account balance.
