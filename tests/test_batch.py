"""Batch contract and recovery tests. Every provider request is mocked."""
import asyncio
import json
import uuid
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
import main
import batch_jobs
from test_backend import HASH, login, wav_bytes, ffprobe_path

PID = '019fa79e-81f9-7a8a-a446-6eff16ddec30'
TRANSCRIPT = '\u0a2b\u0a41\u0a32\u0a15\u0a3e\u0a30\u0a40 is a living tradition.'

@pytest.fixture
def batch(tmp_path, monkeypatch):
    monkeypatch.setenv('GNANI_BATCH_ENABLED','true')
    monkeypatch.setenv('APP_ENV','development')
    calls=[]
    state={'status':'COMPLETED','result_url':'https://gnaniasraudios.s3.amazonaws.com/results/test.json','fail':None}
    async def validate(*args, **kwargs):
        assert kwargs == {'max_seconds':600,'min_seconds':.1}
    monkeypatch.setattr(main,'validate_audio',validate)
    def handler(request):
        calls.append(request)
        if state['fail']:
            return httpx.Response(state['fail'],json={'secret':'must-not-return'})
        path=request.url.path
        if request.url.host == 'gnaniasraudios.s3.amazonaws.com':
            assert 'x-api-key-id' not in request.headers
            return httpx.Response(200,json={'full_transcript':TRANSCRIPT,'segments':[{'start_time':0,'end_time':31,'text':TRANSCRIPT}]})
        assert request.headers['X-API-Key-ID']=='mock-only'
        if path.endswith('/start'): return httpx.Response(202,json={'status':'STARTING'})
        if path.endswith('/cancel'): return httpx.Response(200,json={'status':'CANCELLED'})
        if path.endswith('/files'): return httpx.Response(200,json={'data':[{'status':'COMPLETED','transcript_url':state['result_url']}]})
        if request.method=='POST': return httpx.Response(201,json={'job_id':PID,'status':'CREATED'})
        return httpx.Response(200,json={'job_id':PID,'status':state['status']})
    app=main.create_app(db_path=tmp_path/'batch.db',owner_hash=HASH,gnani_key='mock-only',gnani_transport=httpx.MockTransport(handler))
    with TestClient(app) as client:
        yield app,client,calls,state

def upload(client,headers,key=None,**kwargs):
    return client.post('/api/batch/jobs',headers={**headers,'Idempotency-Key':key or str(uuid.uuid4())},
        files={'file':('story.ogg',kwargs.pop('content',b'test'),'audio/ogg')},
        data={'language':'pa-IN','consent':'true',**kwargs})

def test_batch_contract_recovery_and_import(batch):
    app,client,calls,state=batch
    headers=login(client);key=str(uuid.uuid4())
    row=upload(client,headers,key).json()
    assert row['status']=='CREATED'
    body=calls[0].content
    assert b'name="files"' in body and b'name="config"' in body
    assert b'application/json' in body and b'prisma-v2.5' in body and b'pa-IN' in body
    assert 'provider_id' not in row
    assert upload(client,headers,key).json()['id']==row['id']
    assert len(calls)==1
    assert upload(client,headers).status_code==409
    jid=row['id']
    assert client.post(f'/api/batch/jobs/{jid}/start',headers=headers).json()['status']=='STARTING'
    result=client.post(f'/api/batch/jobs/{jid}/refresh',headers=headers).json()
    assert result['transcript']==TRANSCRIPT and len(result['segments'])==1
    before=len(calls)
    assert client.post(f'/api/batch/jobs/{jid}/refresh',headers=headers).status_code==200
    assert len(calls)==before
    # Recreate app over the same database: neither audio nor a live worker is required.
    restarted=main.create_app(db_path=app.state.db,owner_hash=HASH,gnani_key='mock-only',gnani_transport=app.state.gnani_transport)
    with TestClient(restarted) as other:
        login(other)
        assert other.get('/api/batch/jobs').json()['jobs'][0]['transcript']==TRANSCRIPT
    assert client.post('/api/stories',headers=headers,json={'title':'Oral history','person':'Contributor','region':'Punjab','language':'pa-IN','category':'Craft','transcript':TRANSCRIPT}).status_code==200

def test_batch_auth_consent_disabled_and_validation(batch):
    app,client,calls,state=batch
    assert client.get('/api/batch/jobs').status_code==401
    assert upload(client,{}).status_code==401
    headers=login(client)
    assert upload(client,{}).status_code==403
    app.state.batch_enabled=False
    assert upload(client,headers).status_code==503
    app.state.batch_enabled=True
    assert upload(client,headers,consent='false').status_code==400
    assert upload(client,headers,language='xx').status_code==400
    assert upload(client,headers,content=b'').status_code==413
    assert upload(client,headers,content=b'a'*10_000_001).status_code==413
    assert not calls

@pytest.mark.parametrize('status',[401,403,429,500,400])
def test_batch_errors_do_not_leak_or_duplicate(batch,status):
    app,client,calls,state=batch;headers=login(client);state['fail']=status;key=str(uuid.uuid4())
    response=upload(client,headers,key)
    assert response.status_code>=400 and 'must-not-return' not in response.text
    state['fail']=None
    assert upload(client,headers,key).json()['status']=='UPLOAD_UNCERTAIN'
    assert len(calls)==1
    assert upload(client,headers).status_code==409

@pytest.mark.parametrize('url',['http://127.0.0.1/private','https://localhost/results/x','https://gnaniasraudios.s3.amazonaws.com.evil.test/results/x','https://user@gnaniasraudios.s3.amazonaws.com/results/x','https://gnaniasraudios.s3.amazonaws.com:444/results/x'])
def test_result_url_rejects_unsafe_destinations(url):
    with pytest.raises(HTTPException):batch_jobs.result_url(url)

@pytest.mark.parametrize('status',['QUEUED','IN_PROGRESS','PARTIAL_FAILURE','FAILED','START_FAILED','CANCELLING','CANCELLED'])
def test_batch_statuses(batch,status):
    app,client,calls,state=batch;headers=login(client);jid=upload(client,headers).json()['id'];state['status']=status
    response=client.post(f'/api/batch/jobs/{jid}/refresh',headers=headers)
    assert response.status_code==200 and response.json()['status']==status
    before=len(calls)
    client.post(f'/api/batch/jobs/{jid}/refresh',headers=headers)
    assert len(calls)==before

def test_cancel_contract(batch):
    app,client,calls,state=batch;headers=login(client);jid=upload(client,headers).json()['id']
    response=client.post(f'/api/batch/jobs/{jid}/cancel',headers=headers)
    assert response.json()['status']=='CANCELLED'
    assert json.loads(calls[-1].content)=={'reason':'LokSutra owner requested cancellation'}

def test_long_audio_real_probe_limits():
    probe=ffprobe_path()
    assert probe, 'FFprobe required for duration verification'
    # The same 31-second valid WAV passes Batch validation and fails short mode.
    content=wav_bytes(31)
    asyncio.run(main.validate_audio(content,'wav',probe,max_seconds=600,min_seconds=.1))
    with pytest.raises(HTTPException):asyncio.run(main.validate_audio(content,'wav',probe))
    with pytest.raises(HTTPException):asyncio.run(main.validate_audio(wav_bytes(601),'wav',probe,max_seconds=600,min_seconds=.1))


def test_start_timeout_is_recovered_without_second_start(batch):
    app,client,calls,state=batch;headers=login(client);jid=upload(client,headers).json()['id']
    original=app.state.gnani_transport
    def timeout(request):raise httpx.ReadTimeout('private details',request=request)
    app.state.gnani_transport=httpx.MockTransport(timeout)
    response=client.post(f'/api/batch/jobs/{jid}/start',headers=headers)
    assert response.status_code==504 and 'private details' not in response.text
    assert client.post(f'/api/batch/jobs/{jid}/start',headers=headers).status_code==409
    app.state.gnani_transport=original;state['status']='IN_PROGRESS'
    assert client.post(f'/api/batch/jobs/{jid}/refresh',headers=headers).json()['status']=='IN_PROGRESS'

def test_unsafe_result_not_downloaded(batch):
    app,client,calls,state=batch;headers=login(client);jid=upload(client,headers).json()['id']
    state['result_url']='https://localhost/private'
    response=client.post(f'/api/batch/jobs/{jid}/refresh',headers=headers)
    assert response.status_code==502
    assert all(request.url.host=='api.vachana.ai' for request in calls)

def test_malformed_status_saved_safely(batch):
    app,client,calls,state=batch;headers=login(client);jid=upload(client,headers).json()['id']
    state['status']={'not':'a status'}
    assert client.post(f'/api/batch/jobs/{jid}/refresh',headers=headers).status_code==502
    assert client.get('/api/batch/jobs').json()['jobs'][0]['status']=='CREATED'
