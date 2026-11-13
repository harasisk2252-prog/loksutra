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

## 2-minute walkthrough for a reviewer

**00:00–00:20 / Problem:** Traditional skills often survive as voices, not indexed documents. Explain who is being preserved, and what may be lost.

**00:20–00:40 / First look:** Open the homepage. The new India heritage illustration is AI-generated **concept artwork**, not a real field recording or a portrait of an actual contributor.

**00:40–01:10 / Discovery:** Search the archive; try Craft or Farming. Open a chapter. Show provenance (illustrative vs owner contribution). Click a learning step and identify its exact source sentence.

**01:10–01:30 / Connections:** Open the knowledge constellation and inspect the reason for a relationship (shared category/tags). Emphasize transparency over unsupported AI claims.

**01:30–02:00 / Creation:** Explain and, when safe, demonstrate owner login and reviewed story save. If a real Gnani recording has been verified on your own machine, show the transcription; otherwise explain that the external provider integration is implemented but unverified live. Never call a mocked transcript a live result.

## Why this engineering direction

The most important product decision is **human-in-the-loop preservation**. Automatic transcription can contain mistakes, especially with regional names and domain-specific terms. LokSutra therefore treats the transcript as a draft until its human editor saves it. Source Lens also avoids pretending a generated lesson is authoritative: every displayed step is backed by the saved transcript sentence.

A second deliberate choice is an **explainable, not mystical, constellation**. Relationship labels are based on saved metadata rather than a black-box cultural inference. A relationship is an invitation to explore, not evidence of influence, lineage, or common origin.

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
