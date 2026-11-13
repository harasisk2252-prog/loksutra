"""Real Chrome tests against a local server; all Gnani responses use MockTransport."""
import asyncio
import os
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from playwright.sync_api import sync_playwright, expect

import main
from test_backend import HASH, PASSWORD, STORY, wav_bytes, ffprobe_path

@pytest.fixture
def browser_app(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.delenv("PUBLIC_ORIGIN",raising=False)
    probe=ffprobe_path()
    if not probe:
        pytest.skip("Install FFprobe before running end-to-end browser tests")
    requests=[]
    async def handler(request):
        requests.append(request)
        await asyncio.sleep(.35)
        return httpx.Response(200,json={"success":True,"transcript":"बीज सुखाएं। फिर सुरक्षित रखें।","model":"prisma-v2.5"})
    app=main.create_app(db_path=tmp_path/"browser.db",owner_hash=HASH,gnani_key="mock-browser-test-only",
                        gnani_transport=httpx.MockTransport(handler))
    app.state.ffprobe=probe
    sock=socket.socket();sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=port,log_level="error",access_log=False))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
    deadline=time.monotonic()+15
    while not server.started and time.monotonic()<deadline:
        time.sleep(.05)
    if not server.started: raise RuntimeError("Local test server did not start")
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(channel="chrome",headless=True)
        yield app,browser,f"http://127.0.0.1:{port}",requests
        browser.close()
    server.should_exit=True;thread.join(timeout=10);sock.close()


def sign_in(page,url):
    page.goto(url)
    expect(page.locator("#libraryStatus")).to_contain_text("3 matching")
    page.locator("#ownerPassword").fill(PASSWORD)
    page.locator("#loginButton").click()
    expect(page.locator("#authStatus")).to_contain_text("Owner signed in")


def select_audio(page):
    page.locator("#audio").set_input_files({"name":"test.wav","mimeType":"audio/wav","buffer":wav_bytes()})
    page.locator("#language").select_option("hi-IN")
    page.locator("#consent").check()


def fill_story(page,title="Browser test बीज"):
    page.locator("#title").fill(title)
    page.locator("#person").fill("Synthetic test contributor")
    page.locator("#region").fill("Punjab")
    page.locator("#category").select_option("Farming")
    page.locator("#tags").fill("ਬੀਜ,seeds")


@pytest.mark.parametrize("width,height",[(1440,1000),(390,844),(320,740)])
def test_complete_workflow(browser_app,width,height):
    app,browser,url,requests=browser_app
    page=browser.new_page(viewport={"width":width,"height":height},reduced_motion="reduce")
    errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
    sign_in(page,url);select_audio(page)
    page.locator("#transcribeButton").click()
    expect(page.locator("#transcript")).to_have_value("बीज सुखाएं। फिर सुरक्षित रखें।")
    assert len(requests)==1
    page.locator("#transcript").fill("बीज छाया में सुखाएं। फिर सुरक्षित रखें।")
    fill_story(page)
    page.locator("#saveButton").click()
    expect(page.locator("#saveStatus")).to_contain_text("Saved.")
    expect(page.locator("#detailTitle")).to_have_text("Browser test बीज")
    expect(page.locator("#detailSteps li")).to_have_count(2)
    expect(page.locator("#count")).to_have_text("4")
    page.locator("#search").fill("ਬੀਜ")
    expect(page.locator("#cards article")).to_have_count(1)
    expect(page.locator("#network button")).to_have_count(1)
    page.locator("#network button").click()
    page.once("dialog",lambda dialog:dialog.accept())
    page.locator("#editStory").click()
    page.locator("#transcript").fill("सुधारा हुआ विवरण।")
    page.locator("#saveButton").click()
    expect(page.locator("#detailTranscript")).to_have_text("सुधारा हुआ विवरण।")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors
    Path("test-results").mkdir(exist_ok=True)
    page.screenshot(path=f"test-results/workflow-{width}.png",full_page=True)
    page.reload()
    expect(page.locator("#count")).to_have_text("4")
    page.locator("#search").fill("सुधारा")
    expect(page.locator("#cards article")).to_have_count(1)
    page.close()


def test_late_transcription_and_session_expiry(browser_app):
    app,browser,url,requests=browser_app
    page=browser.new_page();sign_in(page,url);select_audio(page)
    page.locator("#transcribeButton").click()
    page.locator("#transcript").fill("My newer correction")
    expect(page.locator("#pendingResult")).to_be_visible()
    expect(page.locator("#transcript")).to_have_value("My newer correction")
    fill_story(page)
    with main.connect(app) as conn:
        conn.execute("UPDATE sessions SET expires=0")
    page.locator("#saveButton").click()
    expect(page.locator("#authStatus")).to_contain_text("session expired")
    expect(page.locator("#transcript")).to_have_value("My newer correction")
    expect(page.locator("#saveButton")).to_be_disabled()
    page.close()


def test_save_failure_duplicate_clicks_and_search_races(browser_app):
    app,browser,url,requests=browser_app
    page=browser.new_page();sign_in(page,url);fill_story(page)
    page.locator("#transcript").fill("A retained draft.")
    page.route("**/api/stories",lambda route:route.fulfill(status=503,json={"detail":"Test outage"}) if route.request.method=="POST" else route.continue_())
    page.locator("#saveButton").click()
    expect(page.locator("#saveStatus")).to_contain_text("Test outage")
    expect(page.locator("#transcript")).to_have_value("A retained draft.")
    page.unroute("**/api/stories")
    page.locator("#saveButton").evaluate("(button)=>{button.click();button.click();}")
    expect(page.locator("#saveStatus")).to_contain_text("Saved.")
    expect(page.locator("#count")).to_have_text("4")
    page.locator("#search").fill("Phulkari")
    page.locator("#search").fill("Clay")
    expect(page.locator("#cards article")).to_have_count(1)
    expect(page.locator("#cards")).to_contain_text("Clay diya making")
    page.route("**/api/stories?*",lambda route:route.fulfill(status=500,json={"detail":"Search unavailable"}))
    page.locator("#search").fill("none")
    expect(page.locator("#libraryStatus")).to_contain_text("Could not refresh")
    expect(page.locator("#retryLibrary")).to_be_visible()
    page.unroute("**/api/stories?*")
    page.locator("#retryLibrary").click()
    expect(page.locator("#cards")).to_contain_text("No matching stories")
    page.close()


def test_graph_pagination_metadata_and_public_write_lock(browser_app):
    app,browser,url,requests=browser_app
    with main.connect(app) as conn:
        for index in range(7):
            conn.execute("INSERT INTO stories VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (f"extra-{index}",f"Extra story {index}","Synthetic contributor","Punjab","Punjabi","Craft",
                          "Step one. Step two.","test",0,0))
    page=browser.new_page(viewport={"width":390,"height":844})
    page.goto(url)
    expect(page.locator("#count")).to_have_text("10")
    expect(page.locator("#saveButton")).to_be_disabled()
    expect(page.locator("#network button")).to_have_count(8)
    assert page.locator("#network line").count()>0
    expect(page.locator("#connectionList")).to_contain_text("category")
    page.locator("#nextGraph").click()
    expect(page.locator("#network button")).to_have_count(2)
    expect(page.locator("#graphPage")).to_contain_text("Page 2 of 2")
    page.locator("#network button").first.click()
    expect(page.locator("#detail")).to_be_visible()
    expect(page.locator("#editStory")).to_be_hidden()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.close()


def test_heritage_discovery_and_export(browser_app):
    app,browser,url,requests=browser_app
    page=browser.new_page(viewport={"width":390,"height":844})
    sign_in(page,url)
    select_audio(page)
    expect(page.locator("#audioPreview")).to_be_visible()
    assert page.locator("#audioPreview").get_attribute("src").startswith("blob:")
    assert requests == []
    page.locator("#filterKind").select_option("real")
    expect(page.locator("#cards article")).to_have_count(0)
    page.locator("#clearFilters").click()
    expect(page.locator("#cards article")).to_have_count(3)
    page.locator("#cards article button").first.click()
    title=page.locator("#detailTitle").inner_text()
    with page.expect_download() as download_info:
        page.locator("#exportChapter").click()
    download=download_info.value
    text=Path(download.path()).read_text(encoding="utf-8")
    assert title in text
    assert "Illustrative sample" in text
    assert "Contributor:" in text
    assert "not independently fact-checked" in text
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.close()


def test_long_history_browser_recovery(browser_app):
    app,browser,url,requests=browser_app
    app.state.batch_enabled=True
    async def batch_handler(request):
        requests.append(request)
        if request.url.host=='gnaniasraudios.s3.amazonaws.com':
            return httpx.Response(200,json={'full_transcript':'Long oral history for review.','segments':[{'start_time':0,'end_time':31,'text':'Long oral history for review.'}]})
        if request.url.path.endswith('/files'):
            return httpx.Response(200,json={'data':[{'status':'COMPLETED','transcript_url':'https://gnaniasraudios.s3.amazonaws.com/results/test.json'}]})
        if request.url.path.endswith('/start'):return httpx.Response(202,json={'status':'STARTING'})
        if request.method=='POST':return httpx.Response(201,json={'job_id':'019fa79e-81f9-7a8a-a446-6eff16ddec30','status':'CREATED'})
        return httpx.Response(200,json={'status':'COMPLETED'})
    app.state.gnani_transport=httpx.MockTransport(batch_handler)
    page=browser.new_page(viewport={'width':390,'height':844})
    sign_in(page,url)
    page.locator('#batchAudio').set_input_files({'name':'history.wav','mimeType':'audio/wav','buffer':wav_bytes(31)})
    page.locator('#batchConsent').check()
    page.locator('#batchUpload').click()
    expect(page.locator('#batchJobs')).to_contain_text('CREATED')
    page.reload()
    expect(page.locator('#batchJobs')).to_contain_text('CREATED')
    page.get_by_role('button',name='Start processing',exact=True).click()
    expect(page.locator('#batchJobs')).to_contain_text('STARTING')
    page.get_by_role('button',name='Refresh status',exact=True).click()
    expect(page.locator('#batchJobs')).to_contain_text('COMPLETED')
    page.locator('#transcript').fill('My draft must stay until I choose import.')
    assert page.locator('#transcript').input_value()=='My draft must stay until I choose import.'
    page.once('dialog',lambda dialog:dialog.accept())
    page.get_by_role('button',name='Use in a new story',exact=True).click()
    expect(page.locator('#transcript')).to_have_value('Long oral history for review.')
    fill_story(page,'Long oral history')
    page.locator('#saveButton').click()
    expect(page.locator('#detailTitle')).to_have_text('Long oral history')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.close()
