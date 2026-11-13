"""Offline visual regression: the browser loads real UI files with a simulated local API.
No HTTP requests or Gnani credits are used. Run: pytest -q tests/test_cinematic_offline.py
"""
from pathlib import Path
import base64
import json
import os
import pytest
import re
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
STORIES = [
    {"id":"sample-1","title":"Phulkari embroidery","person":"Gurmeet Kaur",
     "region":"Punjab","language":"Punjabi","category":"Craft",
     "transcript":"Choose a cotton cloth. Stretch the cloth. Pick bright silk threads. Make small patterns with careful stitches. Finish the edges.",
     "tags":"textiles,phulkari","verified":False,"is_sample":True},
    {"id":"sample-2","title":"Seed preservation","person":"Baldev Singh",
     "region":"Punjab","language":"Punjabi","category":"Farming",
     "transcript":"Select healthy mature seeds. Dry them in shade. Store in a dry airtight container.",
     "tags":"seeds,farming","verified":False,"is_sample":True},
    {"id":"sample-3","title":"Clay diya making","person":"Meera Devi",
     "region":"Rajasthan","language":"Hindi","category":"Craft",
     "transcript":"Prepare clean clay. Knead it with water. Shape a small bowl.",
     "tags":"pottery,diya","verified":False,"is_sample":True},
]

@pytest.mark.parametrize("width,height", [(1440,900),(390,844),(320,740)])
def test_cinematic_design_offline(width, height, tmp_path):
    markup = (ROOT/"frontend/index.html").read_text(encoding="utf-8")
    markup = re.sub(r'<script\b[^>]*>.*?</script>', '', markup, flags=re.IGNORECASE|re.DOTALL)
    markup = re.sub(r'<link\b[^>]*href="/(?:cinematic|heritage-landing)\.css"[^>]*>', '', markup, flags=re.IGNORECASE)
    markup = markup.replace('/assets/heritage-illustration.webp', 'data:image/webp;base64,' + base64.b64encode((ROOT/'frontend/assets/heritage-illustration.webp').read_bytes()).decode())
    with sync_playwright() as pw:
        path = os.environ.get("LOKSUTRA_TEST_CHROMIUM")
        browser = pw.chromium.launch(executable_path=path, headless=True) if path else pw.chromium.launch(channel="chrome",headless=True)
        page = browser.new_page(viewport={"width":width,"height":height},reduced_motion="reduce")
        errors=[]
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content(markup,wait_until="load")
        page.add_style_tag(content=(ROOT/"frontend/cinematic.css").read_text(encoding="utf-8"))
        page.add_style_tag(content=(ROOT/"frontend/heritage-landing.css").read_text(encoding="utf-8"))
        # Simulate only PUBLIC read endpoints. No live audio calls.
        page.evaluate("""(stories) => {
          window.fetch = async (path) => {
            let url=String(path); let payload, status=200;
            if (url.startsWith('/api/stories')) {
              const q=new URLSearchParams(url.split('?')[1]||'').get('q')||'';
              payload=stories.filter(s=>!q || Object.values(s).join(' ').toLowerCase().includes(q.toLowerCase()));
            } else if(url==='/api/config')payload={languages:{'pa-IN':'Punjabi','hi-IN':'Hindi','en-IN':'English'},formats:['wav','mp3'],max_audio_seconds:30};
            else if(url==='/api/health')payload={ok:true,gnani_configured:true,audio_validation_ready:true};
            else if(url==='/api/auth/session')payload={authenticated:false,owner_configured:true,csrf_token:null};
            else if(url==='/api/batch/jobs'){status=401;payload={detail:'Owner access required'};}
            else {status=404;payload={detail:'Not found (offline mock)'};}
            return new Response(JSON.stringify(payload),{status,headers:{'Content-Type':'application/json'}});
          };
        }""", STORIES)
        # Install feature script before base script so first render is always enhanced.
        for file in ["experience.js","app.js","batch.js"]:
            page.add_script_tag(content=(ROOT/"frontend"/file).read_text(encoding="utf-8"))
        assert page.locator('.heritage-art').evaluate('(image) => image.complete && image.naturalWidth > 0')
        expect(page.locator('#heroTitle')).to_contain_text('Every voice')
        page.locator('.heritage-copy button[data-scroll="capture"]').click()
        assert page.evaluate('scrollY > 50'), 'Hero preservation button must scroll to a real section'
        page.locator('.heritage-copy button[data-scroll="library"]').click()
        assert page.evaluate("Math.abs(document.querySelector('#library').getBoundingClientRect().top) < innerHeight"), 'Explore action must navigate to the archive'
        expect(page.locator("#count")).to_have_text("3")
        expect(page.locator("#spotlightHeading")).to_have_text("Phulkari embroidery")
        expect(page.locator("#apiStatus")).to_be_hidden()
        expect(page.locator("#themeChips button")).to_have_count(3)
        expect(page.locator("#network line")).to_have_count(1)  # Craft relationship only; same region alone does not create a link.
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Horizontal overflow"
        if width==1440:
            page.screenshot(path=str(tmp_path/"desktop.png"),full_page=True)
            output=os.environ.get("LOKSUTRA_PREVIEW_DEST")
            if output: page.screenshot(path=output,full_page=True)
        page.locator("#themeChips button").filter(has_text="Craft").click()
        expect(page.locator("#cards article")).to_have_count(2)
        page.locator("#spotlightOpen").click()
        expect(page.locator("#detailTitle")).to_have_text("Phulkari embroidery")
        page.locator("#detailSteps button").first.click()
        expect(page.locator("#detailTranscript mark")).to_have_text("Choose a cotton cloth.")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Horizontal overflow after interactions"
        assert not errors, errors
        browser.close()
