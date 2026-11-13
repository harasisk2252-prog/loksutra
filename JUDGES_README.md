# LokSutra — Judge briefing

**Tagline:** Every voice holds a universe. **Mission:** Preserve traditional knowledge with the voice and consent of its source, then make that knowledge accessible without losing context.

## The 30-second pitch

LokSutra is a living knowledge universe for India's craft, farming and community traditions. Its distinctive workflow starts with consented oral testimony, uses Gnani speech-to-text as an optional transcription tool, requires human correction, and creates searchable, attributed stories. A source-traceable chapter links reading steps to the exact recorded text, while a constellation explains related themes without making up cultural connections.

**Prototype audience:** Community archivists, teachers, heritage organizations, students and families. **Current editor:** One authenticated owner. **Readers:** Public, read-only.

## What can actually be demonstrated

| Area | Implemented | Verification scope |
| --- | --- | --- |
| Cinematic, responsive homepage | Yes — local illustrated hero, animation, archive navigation | Chromium browser layout and action tests |
| Public archive and searchable records | Yes | FastAPI and browser checks |
| Category/language/region/sample filtering | Yes | Client-side browser tests |
| Owner login, manual story save and edit | Yes | Backend + browser integration with temporary SQLite |
| Sentence-based source highlighting | Yes | Browser + real-backend in-process check |
| Metadata-based graph, explained edges | Yes | Browser tests; **not semantic AI** |
| Gnani short-recording adapter | Implemented | Mocked provider tests. **Current account's live result unverified here** |
| Recoverable Gnani Batch workflow | Implemented, disabled by default | Mocked provider tests; live pricing and completion unverified |
| Native audio recording | No | Upload an existing supported audio file |
| AI-verified historical accuracy | No | Owner review and external research required |
| Persistent source-audio library | No | Short-form flow stores reviewed text, not source audio |
| Public submissions, multiuser moderation | No | One owner only |


## 🌟 Key Features & Innovations

### 1. Multilingual Heritage Preservation with Gnani AI
LokSutra integrates Gnani AI speech-to-text to help preserve oral traditions in regional languages, including Punjabi and Hindi. Contributors' recordings can be converted into editable transcripts, helping transform spoken knowledge into searchable digital heritage.

### 2. Human-in-the-Loop Transcription
Traditional names, local expressions and cultural terminology must be preserved accurately. LokSutra lets the authenticated owner review and correct transcripts before saving them as permanent knowledge records.

### 3. Interactive Knowledge Universe
Instead of presenting stories as isolated documents, LokSutra visualizes related traditions as an interactive constellation. Connections are explained using shared categories, themes and tags rather than unsupported historical assumptions.

### 4. Source Lens — Traceable Knowledge
Readers can explore structured learning steps and identify the corresponding sentences in a saved transcript. This creates a transparent link between the original documented knowledge and its educational presentation.

### 5. Recoverable Long-Audio Transcription
LokSutra includes a separate owner-controlled workflow for longer recordings using Gnani Batch transcription. It supports job-status tracking, duplicate-request safeguards, restart recovery and manual transcript import.

*Live Batch processing remains subject to verified account access, pricing and successful provider testing.*

### 6. Searchable Digital Heritage Archive
A searchable archive helps visitors explore preserved knowledge by categories, languages, regions and relevant themes. Each story can retain contributor attribution and descriptive metadata.

### 7. Cinematic Heritage Experience
LokSutra combines culturally inspired visuals, a responsive interface, animated transitions, and interactive storytelling to make traditional knowledge appealing to younger generations.

### 8. Privacy-Conscious, Owner-Reviewed Publishing
The prototype uses authenticated owner access for editing, with public read-only exploration. API credentials remain on the backend, and transcripts require human approval before publication.

---

## What Makes LokSutra Different?

**LokSutra does not merely convert speech into text. It creates a pathway from spoken memories to discoverable, explainable and human-reviewed cultural knowledge.**

Its innovation lies in combining multilingual transcription, editorial review, source traceability and interactive cultural exploration in one preservation workflow.

## Technical outline

```text
                       ┌──────────────────┐
 Public browser  ──────▶│ HTML/CSS/JS UI   │
                       └────────┬─────────┘
                                │ same-origin HTTP
                       ┌────────▼─────────┐
                       │ FastAPI          │
                       │ auth, CSRF, caps │
                       └────────┬─────────┘
                                │
                  ┌─────────────┴────────────────┐
                  ▼                              ▼
              SQLite stories,                 Gnani STT REST
              session & Batch jobs            (private backend key)
                                                 │
                  reviewed transcript ◀───────────┘
```

**Stack:** Python, FastAPI, SQLite, HTML/CSS/JavaScript, Gnani REST/Batch adapters, pytest, Playwright, Node. No React build step. Config and credentials live in backend-only `.env`.

## Evaluation-ready evidence and limitations

- **Automated:** Python/Node suites and desktop/mobile browsers; see [TEST_REPORT.md](TEST_REPORT.md) for the actual current run. Provider responses are mocked. These tests are not evidence that a live paid Batch job completed.
- **Consent:** Only test with a recording for which you have permission. A publicly shared recording and its transcript can reveal personal details; the submitter must confirm permission to publish.
- **Privacy:** API key is not bundled or printed. Owner has a password hash, CSRF checks and restricted writes. This prototype is not a security-audited multiuser system.
- **Accessibility:** Semantic sections, labelled buttons, focus states, `prefers-reduced-motion`; automated checks do not substitute for a full assistive-technology review.
- **Credit management:** No paid Gnani request is started by simply opening the site; Batch mode remains disabled until intentionally enabled after pricing/access approval.
- **Samples:** Default examples are illustrative. Their titles, people and regions are not independent historical verification.

## Local launch (Windows)

Extract the ZIP, run `Set Owner Password.cmd`, then `Start LokSutra.cmd` and visit `http://127.0.0.1:8000`. To use audio uploads, install `ffprobe` or keep the portable tool from your existing original folder. Enter the Gnani key only in local `.env`. Complete instructions are in [README.md](README.md).

## Submission honesty checklist

- Provide your own name, institution, roles and project link in `SUBMISSION.md` (no personal information is fabricated here).
- Show the actual application rather than the concept illustration alone.
- Describe Gnani as *integrated* rather than *live verified* until an explicit successful provider test is observed.
- If the original Batch test is not run, say so. Never claim all audio lengths, languages, or provider models have been tested.
- Confirm the organizers' final submission form and deadline directly before publishing.

**What is next?** Field validation with consenting storytellers, regional-language transcription quality evaluation, preserving source audio with explicit retention consent, contributor-level provenance, moderation and human-review tooling. These are **future work**, not present functionality.
