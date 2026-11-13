# Long oral histories — implementation and verification

Checked November 11, 2026. The working short REST mode is preserved.

## Implemented local scope
- Separate owner-only Batch studio: one file, at most 10 minutes / 10,000,000 bytes.
- WAV, MP3, OGG, FLAC, AAC and M4A; the same ten language codes, including Punjabi pa-IN.
- FFprobe checks audio duration before upload (0.1–600 seconds).
- Upload creates a job; a separate Start processing button initiates processing.
- SQLite stores the local request ID, provider job ID, status, text and returned timestamps.
- Refresh/browser/server restart recovery, explicit cancellation, manual transcript import into a new story.
- Existing draft text is never replaced automatically. Story text limit is 100,000 characters; oversized responses are rejected rather than truncated.
- Audio is temporary locally; provider retention is governed by Gnani, not by LokSutra.
- Authenticated reads, CSRF-protected writes, request limits, throttling, one pending job, UUID request deduplication.
- Uncertain uploads block a second upload. Inspect Gnani's dashboard before resolving such a record; no automatic resubmission or dashboard reconciliation is implemented.
- Result URLs must use HTTPS and the exact documented gnaniasraudios.s3.amazonaws.com/results/ host/path. No redirects, API key or cookies are sent to object storage. A changed provider host requires a reviewed code update.
- Response downloads are capped at 2 MB and 75 seconds. Status refreshes are spaced at least 10 seconds server-side.

## Live enablement
Default is disabled. No real Batch request has been made.
Only after confirming account access, pricing and a specific consented test, set
GNANI_BATCH_ENABLED=true in the private .env beside main.py and restart LokSutra.
Do not put the API key in .env.example. The existing GNANI_API_KEY in .env is reused privately.
The user reports INR 4,900 remaining; this is not independently verified and is not converted to audio minutes.

## Documented provider contract
POST https://api.vachana.ai/stt/v3/batch/jobs with X-API-Key-ID and multipart:
files=(one audio file); config=(application/json with model prisma-v2.5, language_code,
mode transcribe, with_diarization false, is_multi_channel false).
201 returns job_id/status CREATED. POST /{job_id}/start returns 202 STARTING.
GET /{job_id} returns status. GET /{job_id}/files returns data[].transcript_url;
download that URL without the API key and read full_transcript and segments.
POST /{job_id}/cancel sends a JSON reason; cancellation does not guarantee a refund.
Provider terminal states: COMPLETED, PARTIAL_FAILURE, FAILED, START_FAILED, CANCELLED.

Gnani documents a four-hour per-file duration ceiling and 10 MB direct uploads.
LokSutra deliberately implements a smaller limit; large-file presigned upload, cloud URLs,
multiple files, diarization, speaker identification and four-hour recordings are not implemented.

## Sources
- https://docs.gnani.ai/api/STTBatch/Introduction
- https://docs.gnani.ai/api/STTBatch/Create_Job
- https://docs.gnani.ai/api/STTBatch/Start_Job
- https://docs.gnani.ai/api/STTBatch/Get_Job
- https://docs.gnani.ai/api/STTBatch/Get_Job_Files
- https://docs.gnani.ai/api/STTBatch/Cancel_Job

Earlier live short-demo evidence is separate: a 10-second Punjabi excerpt succeeded;
the original 25.97-second request timed out. Neither is a live Batch verification.
