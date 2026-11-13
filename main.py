"""LokSutra: public knowledge archive with an owner-only capture studio."""
import batch_jobs
import asyncio
import hashlib
import hmac
import json
import math
import os
import secrets
import shutil
import sqlite3
import tempfile
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from owner_auth import password_hash, password_matches, valid_hash
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env", override=False, encoding="utf-8-sig")
STT_URL = "https://api.vachana.ai/stt/v3"
LANGUAGES = {"bn-IN": "Bengali", "en-IN": "English", "gu-IN": "Gujarati",
             "hi-IN": "Hindi", "kn-IN": "Kannada", "ml-IN": "Malayalam",
             "mr-IN": "Marathi", "pa-IN": "Punjabi", "ta-IN": "Tamil", "te-IN": "Telugu"}
FORMATS = {"wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg",
           "flac": "audio/flac", "aac": "audio/aac", "m4a": "audio/mp4"}
MAX_AUDIO_BYTES = 12_000_000  # Local policy, not a claimed Gnani limit.
EXAMPLES = [
    ("Phulkari embroidery", "Gurmeet Kaur", "Punjab", "Punjabi", "Craft",
     "Choose a cotton cloth. Stretch the cloth. Pick bright silk threads. Make small patterns with careful stitches. Finish the edges.", "textiles,phulkari"),
    ("Seed preservation", "Baldev Singh", "Punjab", "Punjabi", "Farming",
     "Select healthy mature seeds. Dry them in shade. Remove damaged seeds. Store in a dry airtight container. Label the container with a date.", "seeds,farming"),
    ("Clay diya making", "Meera Devi", "Rajasthan", "Hindi", "Craft",
     "Prepare clean clay. Knead it with water. Shape a small bowl. Create space for a cotton wick. Dry the diya. Fire it safely with an experienced artisan.", "pottery,diya")
]


@contextmanager
def connect(app):
    conn = sqlite3.connect(app.state.db, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize(app):
    with connect(app) as conn:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='stories'").fetchone()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""CREATE TABLE IF NOT EXISTS stories (
            id TEXT PRIMARY KEY, title TEXT, person TEXT, region TEXT, language TEXT,
            category TEXT, transcript TEXT, tags TEXT, verified INTEGER, is_sample INTEGER NOT NULL DEFAULT 0)""")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(stories)")}
        if "is_sample" not in columns:
            conn.execute("ALTER TABLE stories ADD COLUMN is_sample INTEGER NOT NULL DEFAULT 0")
            for example in EXAMPLES:
                conn.execute("""UPDATE stories SET is_sample=1 WHERE title=? AND person=? AND region=?
                    AND language=? AND category=? AND transcript=? AND tags=? AND verified=0""", example)
        if not exists:
            for example in EXAMPLES:
                conn.execute("INSERT INTO stories VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (str(uuid.uuid4()), *example, 0, 1))
        conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL, owner_version TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS rate_limits (
            bucket TEXT PRIMARY KEY, starts REAL NOT NULL, count INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS story_requests (
            request_id TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, story_id TEXT NOT NULL)""")


class Story(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    person: str = Field(min_length=1, max_length=120)
    region: str = Field(min_length=1, max_length=120)
    language: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=80)
    transcript: str = Field(min_length=1, max_length=100000)
    tags: str = Field(default="", max_length=500)
    verified: bool = False

    @field_validator("verified")
    @classmethod
    def no_self_verification(cls, value):
        if value:
            raise ValueError("Contributor verification is not implemented; stories remain unverified")
        return False

    @field_validator("language")
    @classmethod
    def readable_language(cls, value):
        return LANGUAGES.get(value, value)


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=256)


def session_for(app, request):
    token = request.cookies.get("loksutra_session", "")
    if not token or len(token) > 128 or not valid_hash(app.state.owner_hash):
        return None
    with connect(app) as conn:
        conn.execute("DELETE FROM sessions WHERE expires<=?", (time.time(),))
        row = conn.execute("SELECT * FROM sessions WHERE token_hash=? AND owner_version=?",
                           (hashlib.sha256(token.encode()).hexdigest(), app.state.owner_version)).fetchone()
    return dict(row) if row else None


def rate_limit(app, bucket, maximum, seconds=60):
    now = time.time()
    with connect(app) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM rate_limits WHERE starts < ?", (now - 3600,))
        row = conn.execute("SELECT * FROM rate_limits WHERE bucket=?", (bucket,)).fetchone()
        if not row or now - row["starts"] >= seconds:
            conn.execute("INSERT OR REPLACE INTO rate_limits VALUES (?,?,1)", (bucket, now))
        elif row["count"] >= maximum:
            raise HTTPException(429, "Too many requests. Wait before trying again.",
                                headers={"Retry-After": str(max(1, math.ceil(seconds - (now - row["starts"]))))})
        else:
            conn.execute("UPDATE rate_limits SET count=count+1 WHERE bucket=?", (bucket,))


class WriteGuard:
    """Authenticate and bound request bodies before multipart parsing or disk spooling."""
    def __init__(self, app, owner_app):
        self.app, self.owner_app = app, owner_app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            return await self.app(scope, receive, send)
        app = self.owner_app
        request = Request(scope)
        path = scope["path"]
        if not path.startswith("/api/"):
            return await self.app(scope, receive, send)
        try:
            origin = request.headers.get("origin")
            expected = app.state.public_origin or str(request.base_url).rstrip("/")
            if origin and origin.rstrip("/") != expected:
                raise HTTPException(403, "Cross-origin writes are not allowed.")
            if not valid_hash(app.state.owner_hash):
                raise HTTPException(503, "Owner access is not configured. Run setup_owner.py locally.")
            if path == "/api/auth/login":
                if request.headers.get("content-type", "").split(";")[0] != "application/json":
                    raise HTTPException(415, "Login requires JSON.")
                rate_limit(app, "login:global", 20, 300)
                rate_limit(app, "login:" + (request.client.host if request.client else "unknown"), 5, 300)
                limit = 4096
            else:
                session = session_for(app, request)
                if not session:
                    raise HTTPException(401, "Sign in as the owner. Your draft has not been cleared.")
                if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session["csrf"]):
                    raise HTTPException(403, "Session protection failed. Sign in again.")
                scope.setdefault("state", {})["owner_session"] = session
                rate_limit(app, "writes:owner", 30)
                if path == "/api/batch/jobs":
                    rate_limit(app, "batch:owner", 10, 300)
                if path == "/api/transcribe":
                    rate_limit(app, "transcribe:owner", 6)
                limit = MAX_AUDIO_BYTES + 65536 if path in {"/api/transcribe", "/api/batch/jobs"} else 650000
            length = request.headers.get("content-length")
            if length and (not length.isdecimal() or int(length) > limit):
                raise HTTPException(413, "Request is too large.")
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > limit:
                    raise HTTPException(413, "Request is too large.")
                if not message.get("more_body", False):
                    break
        except HTTPException as error:
            return await JSONResponse({"detail": error.detail}, status_code=error.status_code,
                                      headers=error.headers)(scope, receive, send)
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        await self.app(scope, bounded_receive, send)


async def validate_audio(content, extension, executable, max_seconds=30, min_seconds=0):
    if not executable:
        raise HTTPException(503, "Audio validation unavailable. Install FFprobe and set FFPROBE_PATH locally.")
    with tempfile.TemporaryDirectory(prefix="loksutra-") as directory:
        path = Path(directory) / ("audio." + extension)
        path.write_bytes(content)
        try:
            process = await asyncio.create_subprocess_exec(
                executable, "-v", "error", "-protocol_whitelist", "file",
                "-show_entries", "format=duration:stream=codec_type,duration",
                "-of", "json", str(path),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            try:
                stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
            except (TimeoutError, asyncio.CancelledError):
                process.kill()
                await process.communicate()
                raise
            data = json.loads(stdout)
            audio = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
            durations = [float(x) for x in [data.get("format", {}).get("duration"),
                         *[s.get("duration") for s in audio]] if x not in (None, "N/A")]
            if process.returncode or not audio or not durations or not all(math.isfinite(x) and x > 0 for x in durations):
                raise ValueError()
            if max(durations) > max_seconds or max(durations) < min_seconds:
                raise HTTPException(400, f"Audio must be between {min_seconds} and {max_seconds} seconds.")
        except FileNotFoundError:
            raise HTTPException(503, "FFprobe was not found. Set FFPROBE_PATH locally.") from None
        except TimeoutError:
            raise HTTPException(400, "Audio validation timed out. Try a shorter, valid recording.") from None
        except (OSError, ValueError, TypeError):
            raise HTTPException(400, "Audio cannot be decoded or its duration could not be verified.") from None


async def gnani_request(app, content, extension, code):
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10), follow_redirects=False,
                                     transport=app.state.gnani_transport) as client:
            response = await client.post(
                STT_URL, headers={"X-API-Key-ID": app.state.gnani_key},
                files={"audio_file": ("recording." + extension, content, FORMATS[extension])},
                data={"language_code": code, "format": "transcribe"})
    except httpx.TimeoutException:
        raise HTTPException(504, "Gnani timed out. Your draft is safe; retry when ready.") from None
    except httpx.RequestError:
        raise HTTPException(502, "Gnani could not be reached. Check your connection and retry.") from None
    status = response.status_code
    if status in (401, 403):
        raise HTTPException(502, "Gnani rejected the credentials. Check GNANI_API_KEY locally.")
    if status == 429:
        raise HTTPException(429, "Gnani rate limit reached. Wait before retrying.", headers={"Retry-After": "60"})
    if status == 504:
        raise HTTPException(504, "Gnani timed out. Try again with a shorter clip.")
    if status in (400, 413, 415, 422):
        raise HTTPException(400, "Gnani rejected this audio or language. Check the format and 30-second limit.")
    if status != 200:
        raise HTTPException(502, "Gnani is unavailable. Try again later.")
    try:
        payload = response.json()
    except ValueError:
        raise HTTPException(502, "Gnani returned an invalid response.") from None
    if not isinstance(payload, dict) or payload.get("success") is not True or not isinstance(payload.get("transcript"), str):
        raise HTTPException(502, "Gnani returned an unexpected response format.")
    return {"transcript": payload["transcript"], "live": True,
            "empty": not payload["transcript"].strip(), "truncated": payload.get("truncated") is True,
            "model": payload.get("model") if isinstance(payload.get("model"), str) else None}


def create_app(db_path=None, owner_hash=None, gnani_key=None, gnani_transport=None, audio_validator=None):
    @asynccontextmanager
    async def lifespan(app):
        initialize(app)
        batch_jobs.initialize(app, connect)
        yield

    app = FastAPI(title="LokSutra", lifespan=lifespan)
    app.state.db = Path(db_path) if db_path else BASE / "loksutra.db"
    app.state.owner_hash = os.getenv("OWNER_PASSWORD_HASH", "") if owner_hash is None else owner_hash
    app.state.owner_version = hashlib.sha256(app.state.owner_hash.encode()).hexdigest()
    app.state.gnani_key = os.getenv("GNANI_API_KEY", "") if gnani_key is None else gnani_key
    app.state.gnani_transport = gnani_transport
    app.state.audio_validator = audio_validator or validate_audio
    app.state.ffprobe = os.getenv("FFPROBE_PATH") or shutil.which("ffprobe") or (str(BASE / "tools" / "ffprobe.exe") if (BASE / "tools" / "ffprobe.exe").is_file() else None)
    app.state.production = os.getenv("APP_ENV", "development") == "production"
    app.state.public_origin = os.getenv("PUBLIC_ORIGIN", "").rstrip("/")
    app.state.session_seconds = 3600
    if app.state.production and (not valid_hash(app.state.owner_hash) or not app.state.public_origin.startswith("https://")):
        raise RuntimeError("Production requires OWNER_PASSWORD_HASH and an HTTPS PUBLIC_ORIGIN.")
    app.state.transcribe_lock = asyncio.Lock()
    app.add_middleware(WriteGuard, owner_app=app)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if app.state.production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        fields = ", ".join(dict.fromkeys(str(e["loc"][-1]) for e in exc.errors()))
        return JSONResponse({"detail": "Invalid or missing fields: " + fields}, status_code=422)

    @app.get("/api/health")
    def health():
        return {"ok": True, "gnani_configured": bool(app.state.gnani_key),
                "audio_validation_ready": bool(app.state.ffprobe)}

    @app.get("/api/config")
    def config():
        return {"languages": LANGUAGES, "formats": list(FORMATS), "max_audio_bytes": MAX_AUDIO_BYTES,
                "max_audio_seconds": 30}

    @app.get("/api/auth/session")
    def auth_session(request: Request):
        session = session_for(app, request)
        return {"authenticated": bool(session), "owner_configured": valid_hash(app.state.owner_hash),
                "csrf_token": session["csrf"] if session else None}

    @app.post("/api/auth/login")
    async def login(data: Login, response: Response):
        if not await asyncio.to_thread(password_matches, data.password, app.state.owner_hash):
            raise HTTPException(401, "Incorrect owner password.")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with connect(app) as conn:
            conn.execute("DELETE FROM sessions WHERE expires<=? OR owner_version<>?", (time.time(), app.state.owner_version))
            conn.execute("INSERT INTO sessions VALUES (?,?,?,?)",
                         (hashlib.sha256(token.encode()).hexdigest(), csrf, time.time() + app.state.session_seconds, app.state.owner_version))
        response.set_cookie("loksutra_session", token, max_age=app.state.session_seconds,
                            httponly=True, secure=app.state.production, samesite="strict", path="/")
        return {"authenticated": True, "csrf_token": csrf}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response):
        with connect(app) as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (request.state.owner_session["token_hash"],))
        response.delete_cookie("loksutra_session", path="/", secure=app.state.production, httponly=True, samesite="strict")
        return {"ok": True}

    @app.get("/api/stories")
    def stories(q: str = Query(default="", max_length=200)):
        with connect(app) as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM stories ORDER BY rowid DESC")]
        needle = q.strip().casefold()
        fields = ("title", "person", "region", "language", "category", "transcript", "tags")
        return [row for row in rows if any(needle in str(row[field] or "").casefold() for field in fields)]

    @app.post("/api/stories")
    def add(story: Story, request: Request):
        sid = str(uuid.uuid4())
        request_id = request.headers.get("idempotency-key", "")
        if request_id:
            try:
                request_id = str(uuid.UUID(request_id))
            except ValueError:
                raise HTTPException(400, "Invalid save request identifier.") from None
        digest = hashlib.sha256(story.model_dump_json().encode()).hexdigest()
        with connect(app) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if request_id:
                previous = conn.execute("SELECT * FROM story_requests WHERE request_id=?", (request_id,)).fetchone()
                if previous:
                    if previous["payload_hash"] != digest:
                        raise HTTPException(409, "This save identifier was already used for a different draft.")
                    return {"id": previous["story_id"]}
            conn.execute("INSERT INTO stories VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (sid, story.title, story.person, story.region, story.language, story.category,
                          story.transcript, story.tags, 0, 0))
            if request_id:
                conn.execute("INSERT INTO story_requests VALUES (?,?,?)", (request_id, digest, sid))
        return {"id": sid}

    @app.put("/api/stories/{sid}")
    def edit(sid: str, story: Story):
        with connect(app) as conn:
            result = conn.execute("""UPDATE stories SET title=?,person=?,region=?,language=?,
                category=?,transcript=?,tags=?,verified=0 WHERE id=?""",
                (story.title, story.person, story.region, story.language, story.category,
                 story.transcript, story.tags, sid))
            if not result.rowcount:
                raise HTTPException(404, "Story not found.")
        return {"ok": True, "id": sid}

    @app.post("/api/transcribe")
    async def transcribe(file: UploadFile = File(...), language: str = Form(...)):
        try:
            if not app.state.gnani_key:
                raise HTTPException(503, "Set GNANI_API_KEY in the local .env file beside main.py.")
            code = language if language in LANGUAGES else next((k for k, v in LANGUAGES.items() if v == language), None)
            if not code:
                raise HTTPException(400, "Choose a supported transcription language.")
            extension = Path(file.filename or "").suffix.lower().lstrip(".")
            if extension not in FORMATS:
                raise HTTPException(415, "Supported audio: WAV, MP3, OGG, FLAC, AAC, M4A.")
            content = await file.read(MAX_AUDIO_BYTES + 1)
            if not content:
                raise HTTPException(400, "The audio file is empty.")
            if len(content) > MAX_AUDIO_BYTES:
                raise HTTPException(413, "Audio exceeds the local 12 MB upload limit.")
            if app.state.transcribe_lock.locked():
                raise HTTPException(429, "A transcription is already running. Please wait.")
            async with app.state.transcribe_lock:
                await app.state.audio_validator(content, extension, app.state.ffprobe)
                return await gnani_request(app, content, extension, code)
        finally:
            await file.close()

    batch_jobs.install(app, connect, session_for, LANGUAGES, FORMATS, validate_audio)
    app.mount("/", StaticFiles(directory=BASE / "frontend", html=True), name="frontend")
    return app


app = create_app()
