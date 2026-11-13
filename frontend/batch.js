"use strict";
let batchBusy=false, batchEnabled=false, batchRequestId=null, batchTimer=null;
const batchTerminal=new Set(['COMPLETED','PARTIAL_FAILURE','FAILED','START_FAILED','CANCELLED']);
function batchButton(label, action, disabled=false) {
  const button=document.createElement('button');button.type='button';button.className='secondary';button.textContent=label;button.disabled=disabled;
  button.addEventListener('click',action);return button;
}
async function loadBatch() {
  clearTimeout(batchTimer);
  if(!auth.authenticated){$('batchJobs').replaceChildren();$('batchFields').disabled=true;message('batchStatus','Sign in to view private oral-history jobs.');return;}
  if(batchBusy)return;
  try {
    const data=await api('/api/batch/jobs');
    if(!auth.authenticated)return;
    batchEnabled=data.enabled;$('batchFields').disabled=!batchEnabled;
    $('batchLanguage').replaceChildren(...Object.entries(config?.languages||{'pa-IN':'Punjabi'}).map(([code,name])=>new Option(name,code)));
    $('batchLanguage').value=batchLanguageChoice;
    message('batchStatus',batchEnabled?'Long mode enabled. Upload creates a job; Start processing sends the paid processing request.':'Long mode prepared but disabled until pricing and a live test are approved. The short demo is available below.');
    renderBatch(data.jobs);
    if(data.jobs.some(job=>!batchTerminal.has(job.status)&&job.status!=='CREATED'&&job.status!=='UPLOAD_UNCERTAIN')) {
      batchTimer=setTimeout(async()=>{
        if(!auth.authenticated||batchBusy)return;
        const job=data.jobs.find(j=>!batchTerminal.has(j.status)&&j.status!=='CREATED'&&j.status!=='UPLOAD_UNCERTAIN');
        await batchAction(job.id,'refresh');
      },11000);
    }
  }catch(error){message('batchStatus',error.message+' Use Recover saved jobs to retry.',true);}
}
let batchLanguageChoice='pa-IN';
$('batchLanguage').addEventListener('change',()=>{batchLanguageChoice=$('batchLanguage').value;});
$('batchAudio').addEventListener('change',()=>{batchRequestId=null;$('batchConsent').checked=false;});
$('batchLanguage').addEventListener('change',()=>{batchRequestId=null;});
function renderBatch(jobs) {
  const host=$('batchJobs');host.replaceChildren();
  if(!jobs.length){const p=document.createElement('p');p.textContent='No oral histories uploaded yet.';host.append(p);}
  for(const job of jobs){
    const article=document.createElement('article');article.className='panel';
    const title=document.createElement('h3');title.textContent=(config?.languages[job.language]||job.language)+' oral history';
    const status=document.createElement('p');status.textContent=job.status.replaceAll('_',' ')+' · '+new Date(job.created*1000).toLocaleString();
    const note=document.createElement('p');note.className='small';note.textContent=job.error||'';
    const actions=document.createElement('div');actions.className='actions';
    if(job.status==='CREATED')actions.append(batchButton('Start processing',()=>batchAction(job.id,'start'),!batchEnabled));
    actions.append(batchButton('Refresh status',()=>batchAction(job.id,'refresh')));
    if(!batchTerminal.has(job.status)&&job.status!=='UPLOAD_UNCERTAIN')actions.append(batchButton('Cancel job',()=>{if(confirm('Request cancellation? Credits already used may not be refunded.'))batchAction(job.id,'cancel');}));
    if(job.status==='UPLOAD_UNCERTAIN'){note.textContent+=' Upload outcome is uncertain. Check your Gnani dashboard before another upload; automatic re-upload is blocked.';}
    article.append(title,status,note,actions);
    if(typeof job.transcript==='string'){
      const details=document.createElement('details'),summary=document.createElement('summary'),text=document.createElement('p');
      summary.textContent='Review transcript and timestamps';text.textContent=job.transcript||'No speech text returned.';details.append(summary,text);
      const list=document.createElement('ol');
      for(const seg of job.segments){const li=document.createElement('li');li.textContent=seg.start.toFixed(1)+'–'+seg.end.toFixed(1)+' s: '+seg.text;list.append(li);}
      details.append(list);article.append(details);
      actions.append(batchButton('Use in a new story',()=>{
        if(saving||transcribing)return message('batchStatus','Wait for the current save or short transcription to finish.',true);
        if(!confirm('Open this transcript as a new story? This replaces your current unsaved draft.'))return;
        resetDraft();$('language').value=job.language;$('transcript').value=job.transcript;revision++;
        message('saveStatus','Imported oral history. Correct the text, add attribution and save when ready.');scrollToId('capture');
      },!job.transcript.trim()));
    }
    host.append(article);
  }
}
async function batchAction(id,action){
  if(batchBusy||!auth.authenticated)return;
  batchBusy=true;clearTimeout(batchTimer);$('batchFields').disabled=true;
  $('batchJobs').querySelectorAll('button').forEach(b=>b.disabled=true);
  message('batchStatus',action==='start'?'Starting processing…':'Checking saved job…');
  try{await api('/api/batch/jobs/'+encodeURIComponent(id)+'/'+action,{method:'POST'});}
  catch(error){message('batchStatus',error.message,true);batchBusy=false;await loadBatch();message('batchStatus',error.message+' The saved job remains available.',true);return;}
  batchBusy=false;await loadBatch();
}
$('batchForm').addEventListener('submit',async event=>{
  event.preventDefault();if(batchBusy||!auth.authenticated||!batchEnabled)return;
  const file=$('batchAudio').files[0];
  if(!file||!file.size||file.size>10000000)return message('batchStatus','Choose a nonempty recording up to 10 MB.',true);
  if(!$('batchConsent').checked)return message('batchStatus','Confirm contributor permission first.',true);
  const form=new FormData();form.append('file',file);form.append('language',$('batchLanguage').value);form.append('consent','true');
  batchRequestId ||= crypto.randomUUID();batchBusy=true;clearTimeout(batchTimer);$('batchFields').disabled=true;
  message('batchStatus','Validating and uploading one recording. Do not re-upload if the connection drops.');
  let problem=null;
  try{await api('/api/batch/jobs',{method:'POST',headers:{'Idempotency-Key':batchRequestId},body:form});}
  catch(error){problem=error.message;}
  finally{batchBusy=false;await loadBatch();if(problem)message('batchStatus',problem+' Recover saved jobs before trying again.',true);}
});
$('batchReload').addEventListener('click',loadBatch);
loadBatch();
