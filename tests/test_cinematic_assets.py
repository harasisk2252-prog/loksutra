"""Serve the actual cinematic assets through the FastAPI app."""
from fastapi.testclient import TestClient
import main

def test_cinematic_files_are_served(tmp_path):
    app=main.create_app(db_path=tmp_path/"assets.db",owner_hash="")
    with TestClient(app) as client:
        index=client.get("/")
        assert index.status_code==200
        assert "cinematic.css" in index.text
        assert "experience.js" in index.text
        assert "script-src 'self'" in index.headers["content-security-policy"]
        stylesheet=client.get("/cinematic.css")
        script=client.get("/experience.js")
        assert stylesheet.status_code==200 and "text/css" in stylesheet.headers["content-type"]
        assert 'heritage-landing.css' in index.text
        assert 'assets/heritage-illustration.webp' in index.text
        hero_css=client.get('/heritage-landing.css')
        image=client.get('/assets/heritage-illustration.webp')
        assert hero_css.status_code==200 and 'text/css' in hero_css.headers['content-type']
        assert image.status_code==200 and image.headers['content-type'].startswith('image/webp')
        assert len(image.content) > 10000
        assert script.status_code==200 and "javascript" in script.headers["content-type"]
        assert "showSpotlight" in script.text
        assert "Gnani key present" not in client.get("/app.js").text
        assert client.get("/.env").status_code==404
