"""Test the actual preview entry without deploying. External URLs are intercepted, not verified."""
import functools
import http.server
import json
import pathlib
import threading
from playwright.sync_api import sync_playwright, expect
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
            page.route('**/tarot-draw/favicon.svg',lambda route:route.fulfill(status=200,content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="red"/></svg>'))
            page.route('**/standby-display/icon-192.png',lambda route:route.abort())
            page.goto(base)
            assert page.locator('#apps button').count()==5
            assert page.locator('.app-icon').count()==5
            page.locator('[data-app-id=tarot] img').wait_for(state='visible')
            assert page.locator('[data-app-id=tarot] img').evaluate('img=>img.naturalWidth')==32
            assert not page.locator('[data-app-id=tarot] .glyph').is_visible()
            expect(page.locator('[data-app-id=clock] img')).to_have_js_property('complete', True)
            assert page.locator('[data-app-id=clock] .glyph').is_visible()
            assert not page.locator('[data-app-id=clock] img').is_visible()
            if viewport['width']==390:
                assert page.locator('#apps').evaluate("el=>getComputedStyle(el).gridTemplateColumns.split(' ').length")==4
            tile=page.locator('[data-app-id=tarot]')
            tile.click(button='right')
            assert page.locator('#app-menu').is_visible()
            assert page.locator('#menu-title').inner_text()=='Tarot Draw'
            assert page.locator('iframe').count()==0
            page.evaluate("Object.defineProperty(navigator,'share',{configurable:true,value:async data=>{window.shared=data}})")
            page.locator('#menu-share').click()
            page.locator('#app-menu').wait_for(state='hidden')
            assert page.evaluate("() => window.shared.url")=='https://kinoko34077.github.io/tarot-draw/'
            tile.focus()
            page.keyboard.press('Shift+F10')
            assert page.locator('#app-menu').is_visible()
            page.evaluate("""Object.defineProperty(navigator,'share',{configurable:true,value:undefined});
              Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async url=>{window.copied=url}}})""")
            page.locator('#menu-share').click()
            page.locator('#app-menu').wait_for(state='hidden')
            assert page.evaluate("() => window.copied")=='https://kinoko34077.github.io/tarot-draw/'
            tile.click(button='right')
            page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw Error('denied')}}})")
            page.locator('#menu-share').click()
            page.locator('#manual-share').wait_for(state='visible')
            assert page.locator('#share-url').input_value()=='https://kinoko34077.github.io/tarot-draw/'
            page.keyboard.press('Escape')
            page.locator('#app-menu').wait_for(state='hidden')
            assert page.locator('iframe').count()==0
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
        context=browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True)
        page=context.new_page()
        page.route('https://**/*',lambda route:route.fulfill(status=200,body='<h1>Mock external candidate</h1>',content_type='text/html'))
        page.goto(base)
        tile=page.locator('[data-app-id=probe]')
        rect=tile.bounding_box()
        x,y=rect['x']+rect['width']/2,rect['y']+rect['height']/2
        session=context.new_cdp_session(page)
        def touch(kind, points):
            session.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':points})
        touch('touchStart',[{'x':x,'y':y}])
        page.locator('#app-menu').wait_for(state='visible')
        touch('touchEnd',[])
        page.wait_for_timeout(150)
        assert page.locator('#app-menu').is_visible(), 'long press release dismissed menu'
        assert page.locator('iframe').count()==0
        page.locator('#menu-cancel').tap()
        page.locator('#app-menu').wait_for(state='hidden')
        touch('touchStart',[{'x':x,'y':y}])
        touch('touchMove',[{'x':x,'y':y+30}])
        page.wait_for_timeout(650)
        touch('touchEnd',[])
        assert not page.locator('#app-menu').is_visible(), 'scroll triggered long press'
        assert page.locator('iframe').count()==0
        tile.tap()
        page.frame_locator('iframe').locator('#draft').wait_for()
        page.locator('#back').tap()
        context.close()
        browser.close()
    print('PASS: icon grid, context menu, native share mock, clipboard fallback, manual copy, keyboard, touch long press/scroll/tap, 2 viewports, input, isolation, return, allowlisted routing (mocked), manifest, offline shell')
finally:
    server.shutdown()
    server.server_close()
