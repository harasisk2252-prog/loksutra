# LokSutra — current verification status

Updated November 10, 2026. This report distinguishes actual provider results from isolated tests.

## Final checks
- Final full Python/browser run: **76 passed, 0 failed, 0 skipped**, 76.57 seconds.
- Frontend configuration regression tests: **2 passed, 0 failed**.
- Dependency check: **No broken requirements found**.
- PowerShell launcher and Python source-packager syntax checks passed.
- Local test evidence: test-results/owner-setup-pytest.xml (excluded from the source ZIP).
- One Starlette/httpx test-client deprecation warning remains; it did not fail tests.

The tests cover owner authentication, CSRF, sessions, throttling, production cookie settings, upload limits, safe provider errors, the documented request contract for all ten languages, story validation, Unicode search, idempotent create retries, persistence and additive legacy migration.

Real FFprobe/FFmpeg checks cover WAV, MP3, OGG, FLAC, AAC and M4A and reject corrupt/overlength samples. Chrome tests exercise upload → mocked transcription → correction → save → search → constellation → edit, at desktop, 390px and 320px widths. They also cover stale searches, failures, expired sessions, duplicate clicks and late transcription.

All automated provider responses are mocked. These tests alone do not prove live provider access or language accuracy.

## Actual Gnani results
1. The original Punjabi fulkari.ogg was measured locally at 25.966500 seconds, 66,823 bytes, mono OGG/Opus. A user-authorized real request returned HTTP 504, with no transcript.
2. With separate user permission, the first 10 seconds were copied into a 16kHz mono PCM WAV. One real request succeeded, returning model prisma-v2.5, live=true, empty=false and truncated=false.
3. The user reviewed the returned text positively. No numerical accuracy score or universal reliability claim is made.

Actual returned text:
ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ ਜੀ ਅੱਜ ਮੈਂ ਤੁਹਾਨੂੰ ਪੰਜਾਬ ਦੀ ਮਸ਼ਹੂਰ ਫੁਲਕਾਰੀ ਕਢਾਈ ਬਾਰੇ ਦੱਸਾਂਗੀ ਫੁਲਕਾਰੀ ਪੰਜਾਬ ਦੀ ਇੱਕ ਬਹੁਤ ਪੁਰਾਣੀ ਅਤੇ ਸੁੰਦਰ ਕਲਾ ਹੈ ਇਸ

The text ends at the cut-off point of the 10-second excerpt. The original recording was not modified. Live evidence is saved locally in test-results/live-result-fulkari-10s.json; audio and private test artifacts are excluded from the source ZIP.

## Implemented
The existing design, archive, sample stories and sentence-based learning view are retained. Owner-only writes, backend-only credentials, audio validation, safe errors, editing, retry protection, Unicode search and paginated metadata connections are implemented. A configuration-loading edit edge case has been fixed and regression-tested.

## Still required for submission
- Owner must choose a local password using setup_owner.py; the last configuration check found no owner hash. The API key is configured in ignored .env and .env.example is blank.
- Creator identity is now HARASIS KAUR, entering solo. SUBMISSION.md records contributions evidenced in this work and discloses AI coding assistance.
- Record the actual app workflow and obtain permission for any voice/audio used publicly.
- Publish the demo post and nominate its link in the submission form. Neither step has been performed.
- Review and submit the written explanation. No submission has been sent.

## Limits and future work
Long-audio Batch mode is researched but not implemented. Current REST input is at most 30 seconds with a local 12 MB size cap; one 10-second Punjabi call has succeeded. The user reports ₹5,000 in credits, but remaining dashboard balance, credit consumption, Batch entitlement and applicable pricing have not been verified.

No production deployment, push, production hosting test, independent security audit, real-device mobile test or screen-reader audit has been performed. Graph edges use metadata; lessons use sentence splitting. There is no semantic AI, automatic factual verification, community moderation, TTS, translation, offline mode or retained audio archive.

## Reproduce
Run the README test commands for isolated checks. Use live_smoke.py only for a separately authorized real request; it asks for SEND and never retries automatically. Use package_submission.py to regenerate the source-only ZIP after completing creator details; it rejects example credentials and scans included files for locally configured secrets without displaying them.

## Windows graphical password setup
Replaced the Windows default invisible terminal prompts with a local Tk dialog containing masked password and confirmation fields. Failed validation leaves the dialog open; cancellation writes nothing. Shared scrypt hashing remains compatible with existing backend sessions. The password setup no longer imports or initializes the FastAPI app. Configuration paths are anchored to the project root; UTF-8 BOM configuration files are supported.

Added Set Owner Password.cmd and Start LokSutra.cmd. They locate the project automatically. start_local.ps1 checks the virtual environment, dependencies, valid password hash and port availability. No Windows security/execution-policy settings were changed. Tcl/Tk 8.6.15 is available locally.

Nine new isolated tests verify validation, unchanged config on failures, preservation of existing settings, hash verification, no plaintext password output/storage, working-directory independence, masked GUI fields, mismatch/retry/success, cancellation and save errors. All use temporary credentials and temporary .env files, never the user's actual password. The first new test run caught a syntax typo in the test itself; it was fixed before the successful full 76-test run.

The real private setup window was opened for the user. Only the user enters the actual password. App startup verification follows after that private step; no real Gnani call was made during this setup repair.

November 11 discovery update: 77 pytest tests passed (97.38 seconds), including real Chrome desktop/mobile workflows against a mocked Gnani provider; 2 Node tests passed. New browser coverage verifies sample filtering, filter reset, local audio object URL without provider calls, attributed chapter download, and mobile width. One existing Starlette/httpx deprecation warning remains. No new live Gnani call, deployment or push. Long mode remains unimplemented.


## November 11 — long oral-history studio
Implemented separate default-disabled Batch jobs with local 10-minute / 10 MB limits.
Final application run: 93 passed, 0 failed, 1 Starlette/httpx deprecation warning
(`pytest --ignore=tests/test_owner_setup.py -q`, 125.50 seconds). This includes
24 Batch tests and 8 browser cases; all provider responses were mocked. Node tests: 2 passed.
Verified create/start/status/files contract, API-key isolation on result download,
auth/CSRF, consent, disabled mode, upload bounds, real FFprobe 31/601-second fixtures,
job deduplication, SQLite restart recovery, cancellation, timeouts, unsafe URL rejection,
malformed status handling and browser upload/reload/start/import/correct/save.
The 320px file-picker overflow was fixed; desktop/mobile regression tests pass.

Full suite initially: 100 passed, 2 failed. The obsolete 100 KB request-bound assertion
was updated to the new 650 KB bound needed for long Unicode transcripts and passed.
The remaining issue is intermittent Tk initialization in the pre-existing password GUI
tests (Windows reports missing scale.tcl/text.tcl on different runs). A separate recheck
had 9 passed/1 failed including the corrected request-bound test. The GUI test failure
is unresolved; the complete suite is NOT claimed green. No actual owner password changed.

Local homepage returned HTTP 200 with the long studio, health ready, and paid Batch false.
No live Batch request, deployment, push or credit spend was performed. Live Batch and
account-specific pricing/access remain unverified. No transcript-accuracy score is claimed.
