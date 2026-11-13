# Test report — Heritage Landing / Judge Edition

**Scope:** Updated hero illustration and layout; existing archive, authentication, SQLite, short Gnani adapter and optional Batch job implementation carried over intact. No live Gnani request was sent in this update.

## Verified in this container (November 11, 2026)

- **99 Python tests passed, 0 failed** in the supported subset (`pytest -q --ignore=tests/test_browser.py`) with Chromium, FFprobe and FFmpeg available, plus an Xvfb desktop for Tk tests. This includes the newly updated visual tests at desktop (1440), mobile (390) and narrow mobile (320), static asset serving, and an in-process browser workflow using the real FastAPI app and a temporary SQLite database.
- **2 Node tests passed** (`node --test tests/frontend_config.test.cjs`). `node --check` succeeded for the three frontend JavaScript files.
- The above browser checks confirmed the new heritage illustration loads, no horizontal overflow at 1440/390/320 widths, archive category filtering, story opening, Source Lens exact-text highlighting, and no captured JavaScript errors.
- The in-process browser check verified authenticated owner sign-in, manual creation of a story, refreshed archive totals, and sentence tracing against FastAPI; it did **not** transmit audio to Gnani.
- Source files are bundled with a manifest and tested archive integrity.

## Environment-limited checks (do not claim they passed)

The **9 pre-existing network-based browser cases** in `tests/test_browser.py` use Playwright to navigate to a temporary `http://127.0.0.1` server. Chrome in this hosted testing environment returns `ERR_BLOCKED_BY_ADMINISTRATOR` for that navigation. They therefore **could not be meaningfully executed here**; the initial broad suite with tools enabled showed 9 environment errors and 94 other passes. Separate offline + in-process coverage was run successfully. These localhost browser tests should be run on a normal Windows development machine before the final demo.

On a first run without Xvfb or configured FFprobe, Tk UI tests and one audio probe test also failed for missing local GUI/audio tooling. With Xvfb and external tools configured the supported subset was green; this does not establish the Windows password dialog's live behavior on the user's machine.

## Not performed / not verified

- Real Gnani REST transcription or Batch billing/result from the user's account.
- Final demo on a Windows 11 machine with the user's `.env`, installed FFprobe and recorded audio.
- Production hosting, public penetration testing, third-party cultural fact-checking, real-user accessibility review, or external judge evaluation.

## Reproduce on Windows

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
node --check frontend/app.js
node --check frontend/batch.js
node --check frontend/experience.js
node --test tests/frontend_config.test.cjs
```

All Gnani provider calls in automated tests are mocked; no credits are spent. `live_smoke.py` is a separate, consent-and-approval-gated option, not run by these commands.
