'use strict';
const $ = id => document.getElementById(id);
const fields = ['title', 'person', 'region', 'language', 'category', 'transcript', 'tags'];
let searchMatches = [];
let all = [], shown = [], selected = null, editing = null, graphPage = 0;
let auth = {authenticated: false}, config = null, transcribing = false, saving = false;
let revision = 0, pending = null, searchSequence = 0, searchController = null, searchTimer;
let saveKey = null, savedPayload = null;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function message(id, text, error = false) { $(id).textContent = text; $(id).classList.toggle('error', error); }
function scrollToId(id) { $(id).scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block:'start'}); }
function syncButtons() {
  if (typeof loadBatch === 'function') loadBatch();
  $('captureFields').disabled = !auth.authenticated;
  $('transcribeButton').disabled = transcribing || saving || !config;
  $('saveButton').disabled = saving || transcribing;
  $('newStory').disabled = saving || transcribing;
  $('editStory').classList.toggle('hidden', !auth.authenticated);
  $('editStory').disabled = saving || transcribing;
  $('loginForm').classList.toggle('hidden', auth.authenticated || auth.owner_configured === false);
  $('logoutButton').classList.toggle('hidden', !auth.authenticated);
}
async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.method && options.method !== 'GET' && auth.csrf_token) headers.set('X-CSRF-Token', auth.csrf_token);
  const response = await fetch(path, {...options, headers, credentials:'same-origin'});
  let body;
  try { body = await response.json(); } catch { throw new Error('The server returned an unreadable response. Please retry.'); }
  if (!response.ok) {
    if (response.status === 401 && path !== '/api/auth/login') {
      auth = {...auth, authenticated:false, csrf_token:null}; syncButtons();
      message('authStatus', 'Your session expired. Sign in again; your draft is still here.', true);
    }
    const error = new Error(typeof body.detail === 'string' ? body.detail : 'Request failed. Please check your input and retry.');
    error.status = response.status;
    throw error;
  }
  return body;
}
async function refreshSession() {
  try {
    auth = await api('/api/auth/session');
    message('authStatus', auth.authenticated ? 'Owner signed in. Only you can transcribe, save and edit.' :
      auth.owner_configured ? 'Public browsing is open. Sign in to preserve or edit a story.' :
      'Owner access is not configured. Run setup_owner.py locally, then restart the server.');
    syncButtons();
  } catch (e) { message('authStatus', e.message, true); }
}
$('loginForm').addEventListener('submit', async event => {
  event.preventDefault();
  if ($('loginButton').disabled) return;
  $('loginButton').disabled = true;
  try {
    auth = {...await api('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password:$('ownerPassword').value})}), owner_configured:true};
    $('ownerPassword').value = '';
    message('authStatus', 'Owner signed in. Your draft is ready.');
    syncButtons();
  } catch (e) { message('authStatus', e.message, true); }
  finally { $('ownerPassword').value = ''; $('loginButton').disabled = false; }
});
$('logoutButton').addEventListener('click', async () => {
  try { await api('/api/auth/logout', {method:'POST'}); auth = {authenticated:false, owner_configured:true}; syncButtons(); message('authStatus', 'Signed out. Browsing is still available.'); }
  catch (e) { message('authStatus', e.message, true); }
});
function storyStatus(story) { return story.is_sample ? 'Illustrative sample' : story.verified ? 'Legacy reviewed record' : 'Unverified contribution'; }
function renderCards() {
  const cards = $('cards'); cards.replaceChildren();
  if (!shown.length) { const p = document.createElement('p'); p.textContent = 'No matching stories. Try another search or preserve a new story.'; cards.append(p); }
  for (const story of shown) {
    const card = document.createElement('article'); card.className = 'story';
    card.innerHTML = '<div class="emoji" aria-hidden="true">' + (story.category === 'Farming' ? '🌱' : story.category === 'Food' ? '🍲' : '🧵') +
      '</div><div class="tag">' + esc(story.category) + ' · ' + esc(story.region) +
      '</div><h3><button type="button">' + esc(story.title) + '</button></h3><p>' +
      esc(story.transcript.slice(0,125)) + (story.transcript.length > 125 ? '…' : '') +
      '</p><footer>✧ ' + esc(story.person) + ' · ' + esc(story.language) + ' · ' + storyStatus(story) + '</footer>';
    card.addEventListener('click', () => openStory(story.id)); cards.append(card);
  }
  $('count').textContent = all.length;
  $('regions').textContent = new Set(all.map(s => s.region).filter(Boolean)).size;
  $('languages').textContent = new Set(all.map(s => s.language).filter(Boolean)).size;
  drawGraph();
  if (typeof renderThemes === 'function') renderThemes();
  if (typeof showSpotlight === 'function') showSpotlight(shown[0]);
}
async function loadLibrary(refreshAll = false) {
  clearTimeout(searchTimer);
  const sequence = ++searchSequence;
  if (searchController) searchController.abort();
  searchController = new AbortController();
  const signal = searchController.signal;
  $('cards').setAttribute('aria-busy', 'true');
  message('libraryStatus', 'Loading stories…'); $('retryLibrary').classList.add('hidden');
  try {
    const q = $('search').value;
    const result = await api('/api/stories?q=' + encodeURIComponent(q), {signal});
    let complete = all;
    if (refreshAll || !q) complete = q ? await api('/api/stories', {signal}) : result;
    if (sequence !== searchSequence) return false;
    searchMatches = result; all = complete; populateFilters(); applyFilters();
    message('libraryStatus', shown.length + ' matching stories · ' + all.length + ' in the archive');
    return true;
  } catch (e) {
    if (e.name === 'AbortError' || sequence !== searchSequence) return false;
    message('libraryStatus', 'Could not refresh stories. ' + e.message, true);
    $('retryLibrary').classList.remove('hidden'); return false;
  } finally { if (sequence === searchSequence) $('cards').setAttribute('aria-busy', 'false'); }
}
$('search').addEventListener('input', () => {
  // Invalidate immediately, before the debounce, so old responses cannot repaint.
  ++searchSequence; searchController?.abort(); clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadLibrary(), 220);
});
$('retryLibrary').addEventListener('click', () => loadLibrary(true));
function shared(a,b) {
  return ['category'].filter(key => a[key] && b[key] &&
    a[key].trim().toLocaleLowerCase() === b[key].trim().toLocaleLowerCase());
}
function drawGraph() {
  const pageSize = 8, pages = Math.max(1, Math.ceil(shown.length / pageSize));
  graphPage = Math.min(graphPage, pages - 1);
  const nodes = shown.slice(graphPage * pageSize, (graphPage + 1) * pageSize);
  const net = $('network'); net.replaceChildren();
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 100 100'); svg.setAttribute('preserveAspectRatio','none'); svg.setAttribute('aria-hidden','true');
  const positions = nodes.map((s,i) => ({x:50+33*Math.cos(i*2*Math.PI/nodes.length-Math.PI/2),y:50+38*Math.sin(i*2*Math.PI/nodes.length-Math.PI/2)}));
  const connections = [];
  nodes.forEach((a,i) => nodes.slice(i+1).forEach((b, offset) => {
    const j = i+1+offset, reasons = shared(a,b); if (!reasons.length) return;
    const line = document.createElementNS('http://www.w3.org/2000/svg','line');
    Object.entries({x1:positions[i].x,y1:positions[i].y,x2:positions[j].x,y2:positions[j].y,stroke:'#65d7c780','stroke-width':'.5'}).forEach(([k,v]) => line.setAttribute(k,v));
    svg.append(line); connections.push(a.title + ' ↔ ' + b.title + ': ' + reasons.join(', '));
  }));
  net.append(svg);
  const center = document.createElement('div'); center.className='node center'; center.style.left='50%'; center.style.top='50%'; center.textContent='LokSutra'; net.append(center);
  nodes.forEach((story,i) => {
    const node = document.createElement('button'); node.className='node'; node.style.left=positions[i].x+'%'; node.style.top=positions[i].y+'%';
    node.textContent=story.title; node.title=story.title; node.addEventListener('click',()=>openStory(story.id)); net.append(node);
  });
  $('graphPage').textContent = 'Page ' + (graphPage+1) + ' of ' + pages + ' · ' + shown.length + ' stories';
  $('previousGraph').disabled = graphPage === 0; $('nextGraph').disabled = graphPage >= pages - 1;
  $('connectionList').replaceChildren();
  const explanation = document.createElement('p');
  explanation.textContent = 'Lines connect stories on this page that share metadata. Search to bring related stories together.';
  $('connectionList').append(explanation);
  const list = document.createElement('ul');
  for (const connection of connections) { const li=document.createElement('li'); li.textContent=connection; list.append(li); }
  if (!connections.length) { const li=document.createElement('li'); li.textContent='No shared metadata connections on this page.'; list.append(li); }
  $('connectionList').append(list);
}
$('previousGraph').addEventListener('click',()=>{graphPage--;drawGraph();});
$('nextGraph').addEventListener('click',()=>{graphPage++;drawGraph();});
function openStory(id) {
  const story = all.find(s=>s.id===id) || shown.find(s=>s.id===id); if (!story) return;
  selected=story; $('detail').classList.remove('hidden');
  $('detailTitle').textContent=story.title; $('detailMeta').textContent=[story.person,story.region,story.language].join(' · ');
  $('detailTranscript').textContent=story.transcript;
  $('detailSteps').replaceChildren();
  const steps = story.transcript.match(/[^.!?।॥\n]+[.!?।॥]?/gu) || [story.transcript];
  for (const step of steps.filter(s=>s.trim())) { const li=document.createElement('li'); li.textContent=step.trim(); $('detailSteps').append(li); }
  $('detailStatus').textContent=storyStatus(story) + ' — check cultural and factual accuracy with the contributor.';
  renderRelated(story);
  if (typeof enhanceChapter === 'function') enhanceChapter(story);
  syncButtons(); scrollToId('detail');
}
$('closeDetail').addEventListener('click',()=>{$('detail').classList.add('hidden');});
$('editStory').addEventListener('click',()=>{
  if (!selected || !auth.authenticated || saving || transcribing) return;
  if (fields.some(id=>['title','person','region','transcript','tags'].includes(id) && $(id).value.trim()) && !confirm('Replace the current draft with this story for editing?')) return;
  editing=selected.id;
  for (const id of fields) {
    let value=selected[id];
    if (id==='language') value=Object.keys(config?.languages || {}).find(k=>config.languages[k]===value) || value;
    if ($(id).tagName==='SELECT' && !Array.from($(id).options).some(o=>o.value===value)) $(id).add(new Option(value,value));
    $(id).value=value;
  }
  revision++; pending=null; $('pendingResult').classList.add('hidden');
  $('captureTitle').textContent='Edit preserved story'; $('saveButton').textContent='Save changes →';
  message('saveStatus','Editing: '+selected.title); scrollToId('capture');
});
$('storyForm').addEventListener('input',()=>{revision++;});
$('audio').addEventListener('change',()=>{revision++;$('consent').checked=false;});
function resetDraft() {
  $('storyForm').reset(); $('language').value='pa-IN'; editing=null; pending=null; revision++;
  saveKey=null;savedPayload=null;$('pendingResult').classList.add('hidden');
  $('captureTitle').textContent='Give a tradition its voice';$('saveButton').textContent='Save to knowledge universe →';
  message('saveStatus','');message('transcribeStatus','');
}
$('newStory').addEventListener('click',()=>{
  if (fields.some(id=>['title','person','region','transcript','tags'].includes(id) && $(id).value.trim()) && !confirm('Discard this draft and start a new story?')) return;
  resetDraft();
});
$('transcribeButton').addEventListener('click',async()=>{
  if (transcribing || saving || !auth.authenticated || !config) return;
  const file=$('audio').files[0], code=$('language').value;
  if (!file) return message('transcribeStatus','Choose an audio file first.',true);
  const extension=file.name.split('.').pop().toLowerCase();
  if (!config.formats.includes(extension) || !file.size || file.size>config.max_audio_bytes)
    return message('transcribeStatus','Choose a nonempty WAV, MP3, OGG, FLAC, AAC or M4A file, at most 12 MB.',true);
  if (!config.languages[code]) return message('transcribeStatus','Select a supported language for transcription.',true);
  if (!$('consent').checked) return message('transcribeStatus','Confirm you have permission to send this recording to Gnani.',true);
  const initialRevision=revision, initialText=$('transcript').value;
  const form=new FormData();form.append('file',file);form.append('language',code);
  transcribing=true;pending=null;$('pendingResult').classList.add('hidden');syncButtons();
  message('transcribeStatus','Validating audio and requesting Gnani transcription… This may take up to a minute.');
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),75000);
  try {
    const result=await api('/api/transcribe',{method:'POST',body:form,signal:controller.signal});
    if (result.empty || !result.transcript.trim()) { message('transcribeStatus','Gnani returned no speech. Your draft was kept. Try a clearer recording.'); return; }
    const suffix=result.truncated ? ' Warning: this result is incomplete. Retry with shorter audio.' : ' Review the wording before saving.';
    if (revision!==initialRevision || initialText.trim()) {
      pending=result.transcript;$('pendingTranscript').value=pending;$('pendingResult').classList.remove('hidden');
      message('transcribeStatus','Transcript received. Your existing or edited draft was kept; compare it below.'+suffix);
    } else { $('transcript').value=result.transcript;revision++;message('transcribeStatus','Gnani transcription received.'+suffix); }
  } catch (e) { message('transcribeStatus',e.name==='AbortError'?'The request timed out. The provider may still be processing it; wait before retrying.':e.message,true); }
  finally { clearTimeout(timer);transcribing=false;syncButtons(); }
});
$('useTranscript').addEventListener('click',()=>{
  if (pending===null || !confirm('Replace your current transcript with the received transcription?')) return;
  $('transcript').value=pending;revision++;pending=null;$('pendingResult').classList.add('hidden');
});
$('storyForm').addEventListener('submit',async event=>{
  event.preventDefault(); if (saving || transcribing || !auth.authenticated) return;
  const data=Object.fromEntries(fields.map(id=>[id,$(id).value.trim()]));
  data.language=config?.languages[data.language] || data.language;data.verified=false;
  if (!data.title || !data.person || !data.region || !data.transcript) return message('saveStatus','Enter a title, contributor, region and transcript.',true);
  const payload=JSON.stringify(data);
  if (payload!==savedPayload) {saveKey=crypto.randomUUID();savedPayload=payload;}
  saving=true;syncButtons();message('saveStatus','Saving your story…');
  try {
    const result=await api(editing?'/api/stories/'+encodeURIComponent(editing):'/api/stories',{
      method:editing?'PUT':'POST',headers:{'Content-Type':'application/json','Idempotency-Key':saveKey},body:payload});
    const id=result.id || editing; editing=id;
    $('captureTitle').textContent='Edit preserved story';$('saveButton').textContent='Save changes →';
    $('search').value=''; resetFilters();
    const refreshed=await loadLibrary(true);
    if (refreshed) {message('saveStatus','Saved. This contribution remains unverified. Start a new story when ready.');openStory(id);}
    else message('saveStatus','Saved successfully, but the archive could not refresh. Use Retry loading stories; do not create another copy.',true);
  } catch(e) {message('saveStatus',e.message+' Your draft is still here.',true);}
  finally {saving=false;syncButtons();}
});
document.querySelectorAll('[data-scroll]').forEach(button=>button.addEventListener('click',()=>scrollToId(button.dataset.scroll)));
async function initialize() {
  await Promise.allSettled([refreshSession(),loadLibrary(true),(async()=>{
    try {
      config=await api('/api/config');
      const current=$('language').value;
      $('language').replaceChildren(...Object.entries(config.languages).map(([code,name])=>new Option(name,code)));
      $('language').value=current in config.languages ? current : 'pa-IN';
      const health=await api('/api/health');
      $('apiStatus').textContent =
  !health.gnani_configured
    ? 'Gnani key not configured'
    : !health.audio_validation_ready
      ? 'FFprobe setup needed'
      : '';
      $('apiStatus').classList.toggle('hidden', health.gnani_configured && health.audio_validation_ready);
    } catch(e) {$('apiStatus').textContent='Configuration unavailable';message('transcribeStatus',e.message+' Reload to retry.',true);}
    syncButtons();
  })()]);
}
initialize();

// Discovery remains a transparent metadata operation over public archive records.
function populateFilters() {
  for (const [id,key] of [['filterLanguage','language'],['filterCategory','category'],['filterRegion','region']]) {
    const select=$(id), value=select.value, label=select.options[0].textContent;
    const values=[...new Set(all.map(story=>story[key]).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
    select.replaceChildren(new Option(label,''),...values.map(v=>new Option(v,v)));
    select.value=values.includes(value)?value:'';
  }
}
function resetFilters() { for(const id of ['filterLanguage','filterCategory','filterRegion','filterKind']) $(id).value=''; }
function applyFilters() {
  shown=searchMatches.filter(story=>[['filterLanguage','language'],['filterCategory','category'],['filterRegion','region']].every(([id,key])=>!$(id).value||story[key]===$(id).value) && (!$('filterKind').value || Boolean(story.is_sample)===($('filterKind').value==='sample')));
  graphPage=0;renderCards();message('libraryStatus',shown.length+' matching stories · '+all.length+' in the archive');
}
for(const id of ['filterLanguage','filterCategory','filterRegion','filterKind']) $(id).addEventListener('change',applyFilters);
$('clearFilters').addEventListener('click',()=>{resetFilters();$('search').value='';loadLibrary(true);});
function renderRelated(story) {
  const host=$('relatedStories');host.replaceChildren();message('exportStatus','');
  const related=all.filter(s=>s.id!==story.id).map(s=>({story:s,reasons:shared(story,s)})).filter(s=>s.reasons.length).sort((a,b)=>b.reasons.length-a.reasons.length).slice(0,4);
  for(const item of related) {const button=document.createElement('button');button.type='button';button.className='secondary';button.textContent=item.story.title+' · shared '+item.reasons.join(', ');button.addEventListener('click',()=>openStory(item.story.id));host.append(button);}
  if(!related.length) {const p=document.createElement('p');p.textContent='No related records yet. Preserve another story from this region, language or tradition.';host.append(p);}
}
$('exportChapter').addEventListener('click',()=>{
  if(!selected)return;
  const story=selected;
  const text=['LokSutra — Knowledge chapter',story.title,'','Contributor: '+story.person,'Region: '+story.region,'Language: '+story.language,'Category: '+story.category,'Status: '+storyStatus(story),'Tags: '+story.tags,'','TRANSCRIPT',story.transcript,'','This record is not independently fact-checked. Confirm cultural accuracy and reuse permission with the contributor.','Connections in LokSutra use metadata, not semantic AI.'].join('\n');
  const url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));
  const link=document.createElement('a');link.href=url;link.download='LokSutra-chapter-'+story.id+'.txt';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  message('exportStatus','Chapter downloaded with contributor attribution and review status.');
});
let previewUrl=null;
function clearPreview(){const audio=$('audioPreview');audio.pause();audio.removeAttribute('src');audio.load();audio.classList.add('hidden');if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=null;message('previewStatus','');}
$('audio').addEventListener('change',()=>{
  clearPreview();const file=$('audio').files[0];if(!file)return;
  previewUrl=URL.createObjectURL(file);$('audioPreview').src=previewUrl;$('audioPreview').classList.remove('hidden');
  message('previewStatus','Local preview only. Nothing is sent until you consent and click Transcribe.');
});
$('audioPreview').addEventListener('error',()=>message('previewStatus','This browser cannot preview the recording. Server-side audio validation still runs before transcription.',true));
$('storyForm').addEventListener('reset',clearPreview);
window.addEventListener('beforeunload',()=>{if(previewUrl)URL.revokeObjectURL(previewUrl);});
