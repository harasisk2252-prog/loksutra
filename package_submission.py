"""Build a local source-only submission ZIP from an explicit allowlist."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from dotenv import dotenv_values

BASE = Path(__file__).resolve().parent
FILES = [
    "main.py", "batch_jobs.py", "frontend/batch.js", "tests/test_batch.py", "owner_auth.py", "PASSWORD_SETUP.md", "Start LokSutra.cmd", "Set Owner Password.cmd", "setup_owner.py", "live_smoke.py", "start_local.ps1",
    "package_submission.py", ".env.example", ".gitignore",
    "requirements.txt", "requirements-dev.txt", "requirements-lock.txt", "pytest.ini",
    "README.md", "VERIFICATION.md", "LONG_AUDIO.md",
    "SUBMISSION.md", "DEMO_AND_SUBMISSION_CHECKLIST.md",
    "frontend/index.html", "frontend/app.js",
    "frontend/cinematic.css", "frontend/experience.js",
    "frontend/heritage-landing.css", "frontend/assets/heritage-illustration.webp",
    "docs/landing-preview.png",
    "JUDGES_README.md", "TECHNICAL_REFERENCE.md",
    "DEMO_STORYBOARD.md", "TEST_REPORT.md",
    "tests/test_owner_setup.py", "tests/test_backend.py", "tests/test_browser.py",
    "tests/test_cinematic_assets.py", "tests/test_cinematic_offline.py",
    "tests/test_cinematic_inprocess.py", "tests/frontend_config.test.cjs",
]
def build():
    example = dotenv_values(BASE / ".env.example")
    if example.get("GNANI_API_KEY") or example.get("OWNER_PASSWORD_HASH"):
        raise SystemExit("Refusing to package: .env.example contains a credential.")
    local = dotenv_values(BASE / ".env") if (BASE / ".env").exists() else {}
    secrets = [str(local.get(name) or "").encode() for name in ("GNANI_API_KEY", "OWNER_PASSWORD_HASH")]
    contents = {}
    for name in FILES:
        source = BASE / name
        data = source.read_bytes()
        if any(secret and secret in data for secret in secrets):
            raise SystemExit("Refusing to package: a local credential appears in an allowlisted file. Secret not displayed.")
        contents["LokSutra/" + name] = data
    manifest = {name:hashlib.sha256(data).hexdigest() for name,data in contents.items()}
    contents["LokSutra/SOURCE_MANIFEST.json"] = json.dumps(manifest,indent=2).encode()
    folder = BASE / "submission"
    folder.mkdir(exist_ok=True)
    target = folder / "LokSutra_Submission_Source.zip"
    with ZipFile(target,"w",compression=ZIP_DEFLATED) as archive:
        for name,data in contents.items():
            archive.writestr(name,data)
    with ZipFile(target) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(contents):
            raise SystemExit("Archive verification failed.")
        for name,data in contents.items():
            if archive.read(name) != data:
                raise SystemExit("Archive content mismatch.")
    print("Created and verified: " + str(target))
    print("Source files: " + str(len(FILES)))
    print("Excluded: .env, databases, audio, tools, virtual environment, private test artifacts.")
    print("SHA256: " + hashlib.sha256(target.read_bytes()).hexdigest())

if __name__ == "__main__":
    build()
