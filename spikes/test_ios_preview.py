"""Test the actual preview entry without deploying. External URLs are intercepted, not verified."""
import functools
import http.server
import json
import pathlib
import threading
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[1]
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}/preview/'
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for viewport in ({'width':390,'height':844},{'width':844,'height':390}):
            page = browser.new_page(viewport=viewport)
            page.route('https://**/*',lambda route:route.fulfill(status=200,body='<h1>Mock external candidate</h1>',content_type='text/html'))
            page.goto(base)
            assert page.locator('#apps button').count()==5
            manifest=page.request.get(base+'manifest.webmanifest').json()
            assert manifest['scope']=='./' and manifest['start_url']=='./' and manifest['display']=='standalone'
            page.locator('[data-app-id=probe]').click()
            frame=page.frame_locator('iframe')
            frame.locator('#draft').fill('test')
            assert frame.locator('#draft').input_value()=='test'
            frame.locator('#check').click()
            assert json.loads(frame.locator('#result').inner_text())=={'storage':False,'parentAccess':False}
            assert page.url==base
            rect=page.locator('iframe').bounding_box()
            assert rect['width']==viewport['width'] and rect['height']==viewport['height'],rect
            page.locator('#back').click()
            assert page.locator('iframe').count()==0
            for app_id,url in [('tarot','https://kinoko34077.github.io/tarot-draw/'),('chord','https://kinoko34077.github.io/Micro-Chordbot/'),('warp','https://kinoko34077.github.io/frequency-warp-vst/'),('clock','https://standby-display.kinotch.workers.dev/')]:
                page.locator(f'[data-app-id={app_id}]').click()
                assert page.locator('iframe').get_attribute('src')==url
                assert page.locator('iframe').get_attribute('sandbox')=='allow-scripts'
                assert page.url==base
                page.locator('#back').click()
            page.evaluate('navigator.serviceWorker.ready')
            page.reload()
            page.context.set_offline(True)
            page.reload()
            assert page.locator('#apps button').count()==5
            page.context.set_offline(False)
            page.close()
        browser.close()
    print('PASS: 2 viewports, input, isolation, return, allowlisted routing (mocked), manifest, offline shell')
finally:
    server.shutdown()
    server.server_close()
