"""A real browser + real FastAPI app in-process (without localhost networking).
No Gnani API calls and no third-party uploads.
"""
import os
import re
from pathlib import Path
import base64

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect
import main

ROOT=Path(__file__).resolve().parents[1]

def test_real_backend_manual_preservation_in_browser(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.delenv("PUBLIC_ORIGIN",raising=False)
    app=main.create_app(db_path=tmp_path/"integration.db",
                        owner_hash=main.password_hash("local-test-pass"),
                        gnani_key="")
    html=(ROOT/"frontend/index.html").read_text(encoding="utf-8")
    html=re.sub(r'<script\b[^>]*>.*?</script>','',html,flags=re.I|re.S)
    html=re.sub(r'<link\b[^>]*href="/(?:cinematic|heritage-landing)\.css"[^>]*>','',html,flags=re.I)
    html=html.replace('/assets/heritage-illustration.webp', 'data:image/webp;base64,' + base64.b64encode((ROOT/'frontend/assets/heritage-illustration.webp').read_bytes()).decode())
    with TestClient(app) as client, sync_playwright() as pw:
        path=os.environ.get("LOKSUTRA_TEST_CHROMIUM")
        browser=pw.chromium.launch(executable_path=path,headless=True) if path else pw.chromium.launch(channel="chrome",headless=True)
        page=browser.new_page(viewport={"width":390,"height":844},reduced_motion="reduce")
        errors=[]
        page.on("pageerror",lambda error: errors.append(str(error)))
        page.set_content(html,wait_until="load")
        page.add_style_tag(content=(ROOT/"frontend/cinematic.css").read_text(encoding="utf-8"))
        page.add_style_tag(content=(ROOT/"frontend/heritage-landing.css").read_text(encoding="utf-8"))
        def request_backend(data):
            method=data.get('method','GET').upper()
            response=client.request(method,data['url'],headers=data.get('headers',{}),
                                    content=(data.get('body') or '').encode('utf-8'))
            return {'status':response.status_code,'text':response.text}
        page.expose_function("testBackendRequest",request_backend)
        page.evaluate("""() => {
          window.fetch = async (path, options={}) => {
            const result = await window.testBackendRequest({
              url:String(path), method:options.method||'GET',
              headers:Object.fromEntries(new Headers(options.headers||{})),
              body:typeof options.body==='string'?options.body:''
            });
            return new Response(result.text,{status:result.status,headers:{'Content-Type':'application/json'}});
          };
        }""")
        for file in ["experience.js","app.js","batch.js"]:
            page.add_script_tag(content=(ROOT/"frontend"/file).read_text(encoding="utf-8"))
        assert page.locator('.heritage-art').evaluate('(image) => image.complete && image.naturalWidth > 0')
        expect(page.locator("#count")).to_have_text("3")
        expect(page.locator("#apiStatus")).to_contain_text("not configured")
        page.locator("#ownerPassword").fill("local-test-pass")
        page.locator("#loginButton").click()
        expect(page.locator("#authStatus")).to_contain_text("Owner signed in")
        page.locator("#title").fill("Traditional farming lesson")
        page.locator("#person").fill("Consenting test contributor")
        page.locator("#region").fill("Punjab")
        page.locator("#category").select_option("Farming")
        page.locator("#language").select_option("pa-IN")
        page.locator("#tags").fill("seeds,care")
        page.locator("#transcript").fill("Dry seeds in shade. Store carefully.")
        # about:blank is not a secure origin, unlike http://127.0.0.1.
        # The production app uses crypto.randomUUID; provide it only in this offline test.
        page.evaluate("() => { if(!crypto.randomUUID) crypto.randomUUID=()=> '11111111-1111-4111-8111-111111111111'; }")
        page.locator("#saveButton").click()
        expect(page.locator("#saveStatus")).to_contain_text("Saved.")
        assert page.locator('.heritage-art').evaluate('(image) => image.complete && image.naturalWidth > 0')
        expect(page.locator("#count")).to_have_text("4")
        expect(page.locator("#detailTitle")).to_have_text("Traditional farming lesson")
        expect(page.locator("#spotlightHeading")).to_have_text("Traditional farming lesson")
        expect(page.locator("#spotlightType")).to_contain_text("Unverified")
        page.locator("#detailSteps button").last.click()
        expect(page.locator("#detailTranscript mark")).to_have_text("Store carefully.")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors
        assert len(client.get("/api/stories").json()) == 4
        assert client.get("/.env").status_code == 404
        browser.close()
