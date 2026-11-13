# LokSutra — India's Living Knowledge Universe

## Project explanation
India's traditional skills are often passed down through speech rather than searchable records. LokSutra helps preserve those explanations as attributed, editable stories. Its first working example uses Punjabi speech about Phulkari embroidery.

The owner uploads a consented audio clip and selects the language. Gnani Prisma v2.5 returns a transcript, which the owner reviews and corrects before saving. Visitors can search the archive by text, contributor, region, language, category or tags. A visual constellation links stories through shared metadata, and the story view presents sentence-based reading steps.

## Intended users
Students documenting local traditions, cultural clubs, educators and community archivists. The current prototype has one owner/editor and public read-only access. It does not yet provide separate contributor accounts or a community moderation process.

## Gnani technology actually used
Gnani Prisma v2.5 Speech-to-Text through POST https://api.vachana.ai/stt/v3. The backend authenticates using X-API-Key-ID and submits multipart audio_file, language_code and format=transcribe. Punjabi uses pa-IN. The API key stays on the backend.

A real 10-second Punjabi recording about Phulkari successfully returned a transcript from prisma-v2.5. The participant reviewed the returned text positively. No measured accuracy percentage is claimed. A prior 25.97-second request returned HTTP 504; the app handles provider failures without discarding the draft.

## Architecture
HTML/CSS/JavaScript browser interface → FastAPI → SQLite.
For transcription: FastAPI validates the audio locally with FFprobe → Gnani → editable transcript.
Owner sessions, CSRF checks, request limits and rate limits protect paid transcription and story writes. Idempotent saves prevent duplicates when the same create request is retried.

## What makes it useful
The project joins speech transcription with the correction, attribution, storage and discovery steps needed for a small cultural archive. It preserves the original project's visual design and adds practical reliability and owner access controls.

## Honest boundaries
- Current REST mode accepts up to 30 seconds and a local 12 MB cap.
- Gnani Batch supports longer audio in its documentation, but LokSutra now implements a default-disabled 10-minute / 10 MB Batch studio; live Batch remains unverified.
- Connections are based on metadata, not semantic AI.
- Learning steps are sentence splits, not generated lessons.
- Sample stories are illustrative; contributions are not automatically fact-checked.
- No TTS, translation, source-audio archive, offline mode or community moderation.
- The deployed production environment has not been verified; no deployment has been performed.

## Development and testing
The existing project was improved in place with AI coding assistance. Backend tests use temporary databases and mocked provider responses; browser tests cover desktop and narrow mobile viewports. Real codec validation and a separate real Gnani request were also performed. See VERIFICATION.md for exact results and distinctions.

## Creator and submission details
- Creator name: HARASIS KAUR
- Entry type: Solo
- Teammate: None
- HARASIS KAUR: directed the cultural-preservation use case and requirements, supplied the Punjabi test recording, configured the local Gnani API key, authorized live tests, and reviewed the successful transcript.
- Demo video link/file: [recording still required]
- Nominated LinkedIn/X post URL: [posting still required]
- Repository URL, if the form asks: [not pushed; approval required]

AI coding assistance was used to implement and test improvements to the existing project and prepare documentation. This is disclosed separately from the participant contributions above. Demo and public-post fields still require completion; do not submit those placeholders.
