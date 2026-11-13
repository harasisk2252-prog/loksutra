"""Explicit opt-in one-request live smoke test. Never used by pytest."""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException
from main import BASE, FORMATS, LANGUAGES, MAX_AUDIO_BYTES, create_app, gnani_request, validate_audio

async def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio",required=True)
    parser.add_argument("--language",required=True,choices=list(LANGUAGES))
    args=parser.parse_args()
    path=Path(args.audio).resolve()
    extension=path.suffix.lower().lstrip(".")
    if extension not in FORMATS:
        raise SystemExit("Unsupported audio format.")
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_AUDIO_BYTES:
        raise SystemExit("File must exist and contain 1 byte to 12 MB.")
    app=create_app()
    if not app.state.gnani_key:
        raise SystemExit("Set GNANI_API_KEY in .env beside main.py locally. Do not paste it into chat.")
    content=path.read_bytes()
    try:
        await validate_audio(content,extension,app.state.ffprobe)
    except HTTPException as error:
        raise SystemExit(error.detail) from None
    print("Validated locally: "+path.name+"; language "+args.language+"; at most 30 seconds.")
    print("This will upload this recording to Gnani and may consume account credits. No automatic retry.")
    if input("Type SEND to authorize this one real request: ").strip()!="SEND":
        raise SystemExit("Cancelled. No audio was sent.")
    report={"utc_time":datetime.now(timezone.utc).isoformat(),"audio_name":path.name,
            "language":args.language,"provider":"Gnani","mocked":False}
    try:
        result=await gnani_request(app,content,extension,args.language)
        report.update({"ok":True,"result":result})
        print("Actual Gnani response received:")
        print(result["transcript"] or "(No speech returned)")
        if result["truncated"]: print("Warning: provider marked the transcript as truncated.")
    except HTTPException as error:
        report.update({"ok":False,"status":error.status_code,"message":error.detail})
        print("Live request failed: "+error.detail)
    folder=BASE/"test-results";folder.mkdir(exist_ok=True)
    target=folder/"live-result.json"
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Local result saved to "+str(target))
    if not report["ok"]: raise SystemExit(1)

if __name__=="__main__":
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(run())
