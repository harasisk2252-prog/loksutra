"""Owner-only, durable single-file Gnani Batch jobs. No background paid retries."""
import asyncio
import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import File, Form, HTTPException, Request, UploadFile

URL = "https://api.vachana.ai/stt/v3/batch/jobs"
MAX_BYTES = 10_000_000
MAX_SECONDS = 600
TERMINAL = {"COMPLETED", "PARTIAL_FAILURE", "FAILED", "START_FAILED", "CANCELLED"}
STATUSES = TERMINAL | {"CREATED", "STARTING", "QUEUED", "IN_PROGRESS", "CANCELLING"}
RESULT_HOST = "gnaniasraudios.s3.amazonaws.com"


def initialize(app, connect):
    with connect(app) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS batch_jobs (
          id TEXT PRIMARY KEY, digest TEXT NOT NULL, provider_id TEXT,
          language TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL,
          checked REAL NOT NULL DEFAULT 0, transcript TEXT, segments TEXT NOT NULL DEFAULT '[]',
          error TEXT NOT NULL DEFAULT '')""")


async def request_json(app, method, url, expected=200, authenticated=True, **kwargs):
    headers = {"X-API-Key-ID": app.state.gnani_key} if authenticated else {}
    try:
        async with asyncio.timeout(75), httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10), follow_redirects=False,
                                     trust_env=False, transport=app.state.gnani_transport) as client:
            async with client.stream(method, url, headers=headers, **kwargs) as response:
                if response.status_code != expected:
                    status = response.status_code
                    if status in (401, 403):
                        raise HTTPException(502, "Gnani authentication/access failed, or the result link expired. Check local account access and retry refresh.")
                    if status == 429:
                        raise HTTPException(429, "Gnani rate limit reached. Wait before refreshing.")
                    if status in (400, 413, 415, 422):
                        raise HTTPException(400, "Gnani rejected this Batch request. Check audio, language and account access.")
                    raise HTTPException(502, "Gnani Batch is unavailable or returned an unexpected status. Refresh the saved job; do not re-upload.")
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2_000_000:
                        raise HTTPException(502, "Gnani result exceeded the safe download limit.")
                try:
                    result = json.loads(raw)
                    if not isinstance(result, dict):
                        raise ValueError()
                    return result
                except (ValueError, UnicodeError):
                    raise HTTPException(502, "Gnani returned malformed Batch data.") from None
    except (httpx.TimeoutException, TimeoutError):
        raise HTTPException(504, "Gnani Batch timed out. The saved job may still exist; do not re-upload.") from None
    except httpx.RequestError:
        raise HTTPException(502, "Could not reach Gnani Batch. Refresh the saved job; do not re-upload.") from None


def result_url(value):
    try:
        url = urlsplit(value)
        if (url.scheme != "https" or url.hostname != RESULT_HOST or url.port not in (None, 443)
                or url.username or url.password or url.fragment or not url.path.startswith("/results/")):
            raise ValueError()
        return value
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(502, "Result URL was not on the documented Gnani storage host. No download attempted.") from None


def install(app, connect, session_for, languages, formats, validate_audio):
    app.state.batch_enabled = os.getenv("GNANI_BATCH_ENABLED", "false").lower() == "true"
    app.state.batch_lock = asyncio.Lock()

    def owner(request):
        if not session_for(app, request):
            raise HTTPException(401, "Sign in as owner to access oral-history jobs.")

    def get(jid):
        with connect(app) as db:
            row = db.execute("SELECT * FROM batch_jobs WHERE id=?", (jid,)).fetchone()
        if not row:
            raise HTTPException(404, "Oral-history job not found.")
        return dict(row)

    def update(jid, **fields):
        with connect(app) as db:
            db.execute("UPDATE batch_jobs SET " + ','.join(k+'=?' for k in fields) + " WHERE id=?", (*fields.values(), jid))
        return get(jid)

    def public(row):
        return {k: v for k, v in row.items() if k not in {"digest", "provider_id", "segments"}} | {"segments": json.loads(row["segments"])}

    @app.get("/api/batch/jobs")
    def jobs(request: Request):
        owner(request)
        with connect(app) as db:
            rows = [public(dict(r)) for r in db.execute("SELECT * FROM batch_jobs ORDER BY created DESC LIMIT 30")]
        return {"enabled": app.state.batch_enabled, "max_seconds": MAX_SECONDS, "max_bytes": MAX_BYTES, "jobs": rows}

    @app.post("/api/batch/jobs")
    async def create(request: Request, file: UploadFile = File(...), language: str = Form(...), consent: bool = Form(False)):
        try:
            if not app.state.batch_enabled:
                raise HTTPException(503, "Long mode awaits pricing and live-test approval. Short transcription still works.")
            if not app.state.gnani_key:
                raise HTTPException(503, "Configure GNANI_API_KEY locally.")
            if not consent:
                raise HTTPException(400, "Confirm permission to send this audio to Gnani and accept possible credit use.")
            if language not in languages:
                raise HTTPException(400, "Choose a supported language.")
            ext = Path(file.filename or "").suffix.lower().lstrip('.')
            if ext not in formats:
                raise HTTPException(415, "Use WAV, MP3, OGG, FLAC, AAC or M4A.")
            content = await file.read(MAX_BYTES + 1)
            if not content or len(content) > MAX_BYTES:
                raise HTTPException(413, "Select a nonempty recording up to 10 MB.")
            try:
                jid = str(uuid.UUID(request.headers.get("Idempotency-Key", "")))
            except ValueError:
                raise HTTPException(400, "A valid upload request ID is required.") from None
            digest = hashlib.sha256(language.encode()+b'\0'+content).hexdigest()
            async with app.state.batch_lock:
                with connect(app) as db:
                    prior = db.execute("SELECT * FROM batch_jobs WHERE id=?", (jid,)).fetchone()
                    active = db.execute("SELECT id FROM batch_jobs WHERE status NOT IN ('COMPLETED','PARTIAL_FAILURE','FAILED','START_FAILED','CANCELLED')").fetchone()
                if prior:
                    if prior['digest'] != digest:
                        raise HTTPException(409, "Upload request ID was already used for different audio.")
                    return public(dict(prior))
                if active:
                    raise HTTPException(409, "An oral-history job is already pending. Recover or cancel it before uploading another.")
                await validate_audio(content, ext, app.state.ffprobe, max_seconds=MAX_SECONDS, min_seconds=.1)
                with connect(app) as db:
                    db.execute("INSERT INTO batch_jobs(id,digest,language,status,created) VALUES (?,?,?,?,?)", (jid,digest,language,'UPLOAD_UNCERTAIN',time.time()))
                try:
                    data = await request_json(app, 'POST', URL, expected=201, files=[
                        ('config', (None, json.dumps({'model':'prisma-v2.5','language_code':language,'mode':'transcribe','with_diarization':False,'is_multi_channel':False}), 'application/json')),
                        ('files', ('oral-history.'+ext,content,formats[ext]))])
                    try:
                        pid = str(uuid.UUID(data['job_id']))
                        if data.get('status') != 'CREATED': raise ValueError()
                    except (KeyError, ValueError, TypeError):
                        raise HTTPException(502, "Unexpected Batch creation response; check your Gnani dashboard before another upload.") from None
                    return public(update(jid, provider_id=pid, status='CREATED', error=''))
                except HTTPException as exc:
                    update(jid, error=exc.detail)
                    raise
        finally:
            await file.close()

    async def refresh(jid):
        row = get(jid)
        if not row['provider_id']:
            return public(row)
        if time.time()-row['checked'] < 10 or row['transcript'] is not None or row['status'] in {'FAILED','START_FAILED','CANCELLED'}:
            return public(row)
        update(jid, checked=time.time())
        try:
            data = await request_json(app, 'GET', URL+'/'+row['provider_id'])
            status = data.get('status')
            if not isinstance(status, str) or status not in STATUSES:
                raise HTTPException(502, "Unknown Gnani job status. The job was kept for recovery.")
            row = update(jid, status=status, error='')
            if status in {'COMPLETED','PARTIAL_FAILURE'}:
                data = await request_json(app, 'GET', URL+'/'+row['provider_id']+'/files')
                files = data.get('data')
                if not isinstance(files,list) or len(files)!=1 or not isinstance(files[0],dict) or files[0].get('status')!='COMPLETED':
                    raise HTTPException(502, "The recording has no complete transcript. No partial text was imported.")
                doc = await request_json(app, 'GET', result_url(files[0].get('transcript_url')), authenticated=False)
                text = doc.get('full_transcript')
                if not isinstance(text,str) or len(text)>100000:
                    raise HTTPException(502, "Invalid or oversized transcript. No text was truncated or imported.")
                segments=[]
                for seg in doc.get('segments', []) if isinstance(doc.get('segments', []),list) else []:
                    if not isinstance(seg,dict): continue
                    start,end=seg.get('start_time'),seg.get('end_time')
                    if (type(start) in (int,float) and type(end) in (int,float) and 0<=start<=end<=MAX_SECONDS+1 and isinstance(seg.get('text'),str)):
                        segments.append({'start':start,'end':end,'text':seg['text'][:10000]})
                row = update(jid, transcript=text, segments=json.dumps(segments[:5000]), error='' if text.strip() else 'No speech text was returned.')
            elif status in {'FAILED','START_FAILED','CANCELLED'}:
                row = update(jid,error='Job '+status.lower().replace('_',' ')+'. No transcript imported. Cancellation does not guarantee a refund.')
            return public(row)
        except HTTPException as exc:
            update(jid,error=exc.detail)
            raise

    @app.post("/api/batch/jobs/{jid}/refresh")
    async def refresh_job(jid: str):
        async with app.state.batch_lock:
            return await refresh(jid)

    @app.post("/api/batch/jobs/{jid}/start")
    async def start(jid: str):
        async with app.state.batch_lock:
            row=get(jid)
            if not app.state.batch_enabled:
                raise HTTPException(503,"Paid long mode is not enabled.")
            if row['status'] != 'CREATED' or not row['provider_id']:
                raise HTTPException(409,"Only a confirmed created job can start. Refresh this job first.")
            update(jid,status='START_UNCERTAIN',checked=0)
            try:
                data=await request_json(app,'POST',URL+'/'+row['provider_id']+'/start',expected=202)
                if data.get('status')!='STARTING':
                    raise HTTPException(502,'Unexpected start response. Refresh before retrying.')
                return public(update(jid,status='STARTING',error=''))
            except HTTPException as exc:
                update(jid,error=exc.detail)
                raise

    @app.post("/api/batch/jobs/{jid}/cancel")
    async def cancel(jid: str):
        async with app.state.batch_lock:
            row=get(jid)
            if not row['provider_id'] or row['status'] in TERMINAL:
                raise HTTPException(409,'This job cannot be cancelled here. Check the Gnani dashboard if upload status is uncertain.')
            data=await request_json(app,'POST',URL+'/'+row['provider_id']+'/cancel',json={'reason':'LokSutra owner requested cancellation'})
            if data.get('status') not in {'CANCELLED','CANCELLING'}:
                raise HTTPException(502,'Cancellation was not confirmed. Refresh job status.')
            return public(update(jid,status=data['status'],checked=0,error='Cancellation does not guarantee a credit refund.'))
