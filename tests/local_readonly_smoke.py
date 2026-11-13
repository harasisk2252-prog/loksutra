"""Read-only check of the running merged app; never calls speech providers."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

if __name__ == '__main__':
    output = Path(__file__).resolve().parents[1] / 'test-results'
    output.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True)
        for width, height in [(1440, 1000), (390, 844), (320, 740)]:
            page = browser.new_page(viewport={'width': width, 'height': height}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: errors.append(f'{response.status} {response.url}') if response.status >= 400 and '/api/batch/jobs' not in response.url else None)
            page.goto('http://127.0.0.1:8000', wait_until='networkidle')
            expect(page.locator('#libraryStatus')).to_contain_text('matching stories')
            assert page.locator('.heritage-art').evaluate('(img) => img.complete && img.naturalWidth > 0')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(output / f'merged-live-{width}.png'), full_page=True)
            page.locator('#spotlightOpen').click()
            page.locator('#detailSteps button').first.click()
            expect(page.locator('#detailTranscript mark')).to_be_visible()
            assert page.request.get('http://127.0.0.1:8000/.env').status == 404
            assert not errors, errors
            print(f'PASS: live app at {width}px, assets, archive, chapter, Source Lens and secret-path protection')
            page.close()
        browser.close()
