# LokSutra — India's Living Knowledge Universe

**For judges:** [Open the one-page project pitch](submission-pitch/) · **Live demo:** [loksutra.netlify.app](https://loksutra.netlify.app) · **Creator:** Harasis Kaur, solo

> LokSutra helps preserve traditional knowledge in the words of the people who hold it. It turns short, consented voice stories into reviewed, attributed, searchable chapters that readers can explore and trace back to their saved source sentences.

## The problem and solution

Craft, farming, and community knowledge are often passed on by speaking. A recording alone is hard to search, credit, correct, or connect with other stories. LokSutra brings those steps together:

**Capture → Review → Preserve → Discover**

## What the prototype offers

- **Voice capture and transcript review:** An owner can submit a consented recording up to 30 seconds. Optional Gnani speech-to-text can help create a draft; the owner reviews and edits it before saving.
- **Searchable public archive:** Stories can be explored by text, contributor, region, language, category, and tags.
- **Source Lens:** Selecting a reading step highlights the exact saved transcript sentence behind it.
- **Knowledge Constellation:** Stories connect through explicit shared metadata, such as category or region; links do not claim historical influence or semantic AI discovery.
- **Long oral histories:** A separate Batch workflow is implemented but remains disabled pending live provider verification.

## For judges and reviewers

The live site opens to a public archive; no owner password is needed to browse it. The capture studio is owner-only, so use the separately submitted demo video to see that workflow. Sample stories are illustrative, not independently verified field recordings. Only describe live transcription as successful when the video shows an actual returned result.

## Technology

HTML, CSS, and JavaScript · Python/FastAPI · SQLite · optional Gnani STT. The short workflow preserves reviewed text and story metadata; it does not permanently store the source audio.

## Further details

[Judge notes](JUDGES_README.md) · [Demo storyboard](DEMO_STORYBOARD.md) · [Technical reference](TECHNICAL_REFERENCE.md) · [Verification and test report](VERIFICATION.md) · [Long-audio status](LONG_AUDIO.md)
