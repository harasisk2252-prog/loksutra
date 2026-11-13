"""Isolated tests. Gnani is always mocked; these tests never call the real API."""
import asyncio
import io
import json
import os
import sqlite3
import subprocess
import uuid
import wave
from contextlib import ExitStack
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
import main

PASSWORD = "test-owner-password-only"
HASH = main.password_hash(PASSWORD)
STORY = dict(title="बीज संरक्षण", person="Test contributor", region="Punjab", language="Punjabi",
             category="Farming", transcript="बीज सुखाएं। फिर सुरक्षित रखें।", tags="ਬੀਜ,seeds", verified=False)


def wav_bytes(seconds=1):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * int(seconds * 16000))
    return buffer.getvalue()


async def accept_audio(*args):
    """Contract tests isolate Gnani from codec checks (tested separately below)."""


@pytest.fixture
def factory(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("PUBLIC_ORIGIN", raising=False)
    with ExitStack() as stack:
        def make(handler=None, **kwargs):
            handler = handler or (lambda request: httpx.Response(200, json={
                "success": True, "transcript": "बीज सुखाएं।", "model": "prisma-v2.5"}))
            settings = dict(db_path=tmp_path / (str(uuid.uuid4()) + ".db"),
                            owner_hash=HASH, gnani_key="test-key-never-real",
                            gnani_transport=httpx.MockTransport(handler), audio_validator=accept_audio)
            settings.update(kwargs)
            app = main.create_app(**settings)
            client = stack.enter_context(TestClient(app))
            return app, client
        yield make


def login(client):
    response = client.post("/api/auth/login", json={"password": PASSWORD})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def upload(client, headers, content=b"fake-codec-contract-fixture", name="sample.wav", language="pa-IN"):
    return client.post("/api/transcribe", headers=headers,
                       files={"file": (name, content, "audio/wav")}, data={"language": language})


def test_public_reads_and_secret_paths(factory):
    app, client = factory()
    assert len(client.get("/api/stories").json()) == 3
    assert all(s["is_sample"] for s in client.get("/api/stories").json())
    assert client.get("/").status_code == 200
    assert "script-src 'self'" in client.get("/").headers["content-security-policy"]
    for path in ("/.env", "/main.py", "/loksutra.db", "/../.env"):
        assert client.get(path).status_code == 404
    text = client.get("/api/config").text + client.get("/api/health").text
    assert "test-key-never-real" not in text and HASH not in text


def test_missing_auth_disables_writes(factory):
    _, client = factory(owner_hash="")
    assert client.get("/api/auth/session").json()["owner_configured"] is False
    assert client.post("/api/stories", json=STORY).status_code == 503
    assert upload(client, {}).status_code == 503


@pytest.mark.parametrize("path,method", [("/api/stories","post"),("/api/stories/not-found","put"),("/api/transcribe","post")])
def test_unauthorized_writes(factory, path, method):
    _, client = factory()
    assert getattr(client, method)(path, json=STORY).status_code == 401


def test_login_cookie_csrf_origin_expiry_logout(factory):
    app, client = factory()
    response = client.post("/api/auth/login", json={"password": PASSWORD})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    headers = {"X-CSRF-Token": response.json()["csrf_token"]}
    assert client.post("/api/stories", json=STORY).status_code == 403
    assert client.post("/api/stories", json=STORY, headers={**headers, "Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.post("/api/stories", json=STORY, headers=headers).status_code == 401
    headers = login(client)
    with main.connect(app) as conn:
        conn.execute("UPDATE sessions SET expires=0")
    assert client.post("/api/stories", json=STORY, headers=headers).status_code == 401


def test_login_rate_limit_and_redaction(factory):
    _, client = factory()
    response = client.post("/api/auth/login", json={"password": "secret-input", "extra": "private"})
    assert response.status_code == 422
    assert "secret-input" not in response.text and "private" not in response.text
    for _ in range(4):
        assert client.post("/api/auth/login", json={"password":"wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"password":PASSWORD}).status_code == 429


def test_write_rate_limit(factory):
    app, client = factory()
    headers = login(client)
    for _ in range(30):
        main.rate_limit(app, "writes:owner", 30)
    response = client.post("/api/stories", json=STORY, headers=headers)
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_story_save_idempotency_search_edit_persistence(factory):
    app, client = factory()
    headers = {**login(client), "Idempotency-Key": str(uuid.uuid4())}
    saved = client.post("/api/stories", json=STORY, headers=headers)
    assert saved.status_code == 200
    sid = saved.json()["id"]
    assert client.post("/api/stories", json=STORY, headers=headers).json()["id"] == sid
    assert len(client.get("/api/stories").json()) == 4
    assert client.post("/api/stories", json={**STORY,"title":"Different"}, headers=headers).status_code == 409
    for query in ("बीज", "ਬੀਜ", "test contributor", "PUNJAB", "seeds"):
        assert sid in [s["id"] for s in client.get("/api/stories", params={"q":query}).json()]
    updated = {**STORY, "title":"Corrected story", "language":"hi-IN", "transcript":"मिट्टी तैयार करें।"}
    assert client.put("/api/stories/"+sid, json=updated, headers=headers).status_code == 200
    row = client.get("/api/stories", params={"q":"मिट्टी"}).json()[0]
    assert row["id"] == sid and row["language"] == "Hindi" and not row["is_sample"] and not row["verified"]
    with main.connect(app) as conn:
        assert conn.execute("SELECT title FROM stories WHERE id=?", (sid,)).fetchone()[0] == "Corrected story"
    _, restarted = factory(db_path=app.state.db)
    assert len(restarted.get("/api/stories").json()) == 4


@pytest.mark.parametrize("change", [{"title":"  "},{"person":""},{"region":""},{"transcript":" "},{"verified":True},{"title":"x"*201}])
def test_create_and_edit_validation(factory, change):
    _, client = factory()
    headers = login(client)
    for method, path in [("post","/api/stories"),("put","/api/stories/not-found")]:
        assert getattr(client, method)(path, json={**STORY,**change}, headers=headers).status_code == 422


def test_edit_missing(factory):
    _, client = factory()
    assert client.put("/api/stories/missing", json=STORY, headers=login(client)).status_code == 404


def test_legacy_migration_preserves_records(factory, tmp_path):
    db = tmp_path/"legacy.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE stories (id TEXT PRIMARY KEY,title TEXT,person TEXT,region TEXT,language TEXT,category TEXT,transcript TEXT,tags TEXT,verified INTEGER)")
        conn.execute("INSERT INTO stories VALUES (?,?,?,?,?,?,?,?,?)", ("sample",*main.EXAMPLES[0],0))
        conn.execute("INSERT INTO stories VALUES (?,?,?,?,?,?,?,?,?)", ("real",*main.EXAMPLES[0][:-2],"Different actual transcript",main.EXAMPLES[0][-1],0))
    _, client = factory(db_path=db)
    rows = {row["id"]:row for row in client.get("/api/stories").json()}
    assert len(rows)==2 and rows["sample"]["is_sample"]==1 and rows["real"]["is_sample"]==0


@pytest.mark.parametrize("code", list(main.LANGUAGES))
def test_documented_request_contract(factory, code):
    requests = []
    def handler(request):
        requests.append(request)
        assert str(request.url) == "https://api.vachana.ai/stt/v3"
        assert request.headers["X-API-Key-ID"] == "test-key-never-real"
        assert "authorization" not in request.headers
        body = request.content
        for field in (b'name="audio_file"', b'name="language_code"', b'name="format"'):
            assert field in body
        assert code.encode() in body and b"transcribe" in body
        assert b'name="model"' not in body and b'name="language"' not in body
        return httpx.Response(200, json={"success":True,"transcript":"ਸਤ ਸ੍ਰੀ ਅਕਾਲ","model":"prisma-v2.5"})
    _, client = factory(handler)
    response = upload(client, login(client), language=code)
    assert response.status_code == 200 and response.json()["transcript"] == "ਸਤ ਸ੍ਰੀ ਅਕਾਲ"
    assert len(requests)==1


@pytest.mark.parametrize("extension", list(main.FORMATS))
def test_supported_upload_extensions(factory, extension):
    _, client = factory()
    assert upload(client, login(client), name="sample."+extension).status_code == 200


@pytest.mark.parametrize("name,content,language,status", [
    ("sample.webm",b"x","pa-IN",415),("sample.wav",b"","pa-IN",400),
    ("sample.wav",b"x","xx-IN",400),("sample.wav",b"x"*12_000_001,"pa-IN",413)])
def test_invalid_uploads_never_call_provider(factory, name, content, language, status):
    def no_network(request):
        pytest.fail("Invalid audio reached the provider")
    _, client = factory(no_network)
    assert upload(client, login(client), name=name, content=content, language=language).status_code == status


def test_missing_key_and_request_body_bound(factory):
    _, client = factory(gnani_key="")
    headers = login(client)
    assert upload(client, headers).status_code == 503
    assert client.post("/api/stories", content=b"x"*650001, headers=headers).status_code == 413


@pytest.mark.parametrize("upstream,expected", [(401,502),(403,502),(429,429),(400,400),(422,400),(500,502),(504,504),(302,502)])
def test_provider_errors_are_safe(factory, upstream, expected):
    _, client = factory(lambda request:httpx.Response(upstream, json={"detail":"test-key-never-real private provider body"}))
    response = upload(client, login(client))
    assert response.status_code == expected
    assert "test-key-never-real" not in response.text and "private provider body" not in response.text


@pytest.mark.parametrize("payload", [{"text":"wrong field"},{"success":False,"transcript":"x"},
                                     {"success":True,"transcript":{}},["not an object"]])
def test_malformed_responses(factory,payload):
    _, client = factory(lambda request:httpx.Response(200,json=payload))
    assert upload(client,login(client)).status_code==502


def test_invalid_json_empty_speech_and_truncation(factory):
    _, client = factory(lambda request:httpx.Response(200,text="<html>not JSON"))
    assert upload(client,login(client)).status_code==502
    _, client = factory(lambda request:httpx.Response(200,json={"success":True,"transcript":""}))
    assert upload(client,login(client)).json()["empty"] is True
    _, client = factory(lambda request:httpx.Response(200,json={"success":True,"transcript":"partial","truncated":True}))
    assert upload(client,login(client)).json()["truncated"] is True


@pytest.mark.parametrize("exception,status", [(httpx.ReadTimeout,504),(httpx.ConnectError,502)])
def test_network_errors(factory,exception,status):
    def handler(request):
        raise exception("private internal detail",request=request)
    _,client=factory(handler)
    response=upload(client,login(client))
    assert response.status_code==status and "private internal detail" not in response.text


def test_missing_ffprobe_is_explicit():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.validate_audio(wav_bytes(),"wav",None))
    assert exc.value.status_code==503


def ffprobe_path():
    configured=os.getenv("FFPROBE_PATH")
    return configured or next((str(p) for p in (main.BASE/"tools").rglob("ffprobe.exe")),None)


def test_real_wav_duration_and_corrupt_audio():
    probe=ffprobe_path()
    if not probe: pytest.skip("FFprobe is not installed")
    asyncio.run(main.validate_audio(wav_bytes(1),"wav",probe))
    asyncio.run(main.validate_audio(wav_bytes(30),"wav",probe))
    for content in (wav_bytes(30.1),b"invalid wav bytes"):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(main.validate_audio(content,"wav",probe))
        assert exc.value.status_code==400


@pytest.mark.parametrize("extension",["mp3","ogg","flac","aac","m4a"])
def test_real_encoded_formats(tmp_path,extension):
    probe=ffprobe_path()
    if not probe: pytest.skip("FFprobe is not installed")
    ffmpeg=str(Path(probe).with_name("ffmpeg.exe"))
    if not Path(ffmpeg).exists(): pytest.skip("FFmpeg is not installed")
    source=tmp_path/"input.wav";source.write_bytes(wav_bytes())
    target=tmp_path/("encoded."+extension)
    subprocess.run([ffmpeg,"-v","error","-i",str(source),str(target)],check=True,timeout=15,capture_output=True)
    asyncio.run(main.validate_audio(target.read_bytes(),extension,probe))


def test_production_cookie_and_configuration(factory,monkeypatch):
    monkeypatch.setenv("APP_ENV","production")
    monkeypatch.setenv("PUBLIC_ORIGIN","https://archive.example")
    with pytest.raises(RuntimeError):
        main.create_app(owner_hash="")
    app=main.create_app(db_path=Path(factory()[0].state.db).with_name("production.db"),owner_hash=HASH,gnani_key="")
    with TestClient(app,base_url="https://archive.example") as client:
        response=client.post("/api/auth/login",json={"password":PASSWORD})
        assert response.status_code==200 and "Secure" in response.headers["set-cookie"]
        assert "max-age=" in response.headers["strict-transport-security"]
