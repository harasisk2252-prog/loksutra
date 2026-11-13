'use strict';
// Enhancements are called by the archive after its data has loaded.
function showSpotlight(story) {
  const host = document.getElementById('spotlight');
  if (!host) return;
  host.classList.toggle('hidden', !story);
  if (!story) return;
  document.getElementById('spotlightHeading').textContent = story.title;
  document.getElementById('spotlightType').textContent = storyStatus(story);
  document.getElementById('spotlightExcerpt').textContent = story.transcript.slice(0, 220);
  document.getElementById('spotlightMeta').textContent = [story.person, story.region, story.language].join(' · ');
  document.getElementById('spotlightOpen').onclick = () => openStory(story.id);
  document.getElementById('spotlightOpen').disabled = false;
}
function renderThemes() {
  const host = document.getElementById('themeChips');
  if (!host) return;
  host.replaceChildren();
  for (const category of ['', ...new Set(all.map(story => story.category).filter(Boolean))]) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'secondary';
    button.textContent = category || 'All traditions';
    button.setAttribute('aria-pressed', String(document.getElementById('filterCategory').value === category));
    button.onclick = () => { document.getElementById('filterCategory').value = category; applyFilters(); };
    host.append(button);
  }
}
function enhanceChapter(story) {
  showSpotlight(story);
  document.getElementById('detailProvenance').textContent = storyStatus(story);
  document.getElementById('detailSourceNote').textContent = 'Select a step to trace it to its source sentence.';
  let cursor = 0;
  for (const item of document.querySelectorAll('#detailSteps li')) {
    const sentence = item.textContent;
    const start = story.transcript.indexOf(sentence, cursor);
    cursor = start + sentence.length;
    const button = document.createElement('button'); button.type = 'button'; button.className = 'source-step'; button.textContent = sentence;
    button.onclick = () => {
      const mark = document.createElement('mark'); mark.textContent = sentence;
      document.getElementById('detailTranscript').replaceChildren(document.createTextNode(story.transcript.slice(0, start)), mark, document.createTextNode(story.transcript.slice(start + sentence.length)));
      document.querySelectorAll('.source-step').forEach(step => step.setAttribute('aria-pressed', String(step === button)));
      document.getElementById('detailSourceNote').textContent = 'Source Lens: exact words from the saved transcript.';
    };
    item.replaceChildren(button);
  }
}
