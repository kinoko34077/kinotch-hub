"""Test the actual preview entry without deploying. External URLs are intercepted, not verified."""
from datetime import datetime, timedelta, timezone
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
def catalog_fixture():
    now=datetime.now(timezone.utc).replace(microsecond=0)
    ts=lambda d:d.isoformat().replace('+00:00','Z')
    definitions=[
        ('1408820750','tarot-draw','Tarot Draw','https://kinoko34077.github.io/tarot-draw/','favicon.svg'),
        ('1235346464','Micro-Chordbot','μChordbot','https://kinoko34077.github.io/Micro-Chordbot/','icons/icon-192.svg'),
        ('1416615773','frequency-warp-vst','Frequency Warp','https://kinoko34077.github.io/frequency-warp-vst/',None),
        ('969335914','standby-display','Standby Display','https://standby-display.kinotch.workers.dev/','icon-192.png')]
    repos,apps=[],[]
    for ident,name,title,url,icon in definitions:
        repos.append(dict(id=ident,fullName='kinoko34077/'+name,visibility='public',archived=False,observedAt=ts(now)))
        app=dict(id='repo:'+ident+':main',repositoryId=ident,title=title,kind='application',canonicalUrl=url,publication=dict(basis='public-deployment' if name=='standby-display' else 'github-pages',observedAt=ts(now)))
        if icon:app['iconUrl']='https://kinoko34077.github.io/'+name+'/'+icon
        apps.append(app)
    return dict(schemaVersion=1,generatedAt=ts(now),validUntil=ts(now+timedelta(days=3)),repositories=repos,applications=apps)
def mock_catalog(page,data):
    page.route('**/catalog.json',lambda route:route.fulfill(status=200,json=data))

def go_home(page):
    if not page.locator('#back').is_visible():page.locator('#home-handle').click()
    page.locator('#back').click()

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for viewport in ({'width':390,'height':844},{'width':844,'height':390}):
            page = browser.new_page(viewport=viewport)
            page.route('https://**/*',lambda route:route.fulfill(status=200,body='<h1>Mock external candidate</h1>',content_type='text/html'))
            page.route('**/tarot-draw/favicon.svg',lambda route:route.fulfill(status=200,content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="red"/></svg>'))
            page.route('**/standby-display/icon-192.png',lambda route:route.abort())
            mock_catalog(page,catalog_fixture())
            page.goto(base+'#fixture')
            expect(page.locator('#apps button')).to_have_count(5)
            assert page.locator('.app-icon').count()==5
            page.locator('[data-alias=tarot] img').wait_for(state='visible')
            assert page.locator('[data-alias=tarot] img').evaluate('img=>img.naturalWidth')==32
            assert not page.locator('[data-alias=tarot] .glyph').is_visible()
            expect(page.locator('[data-alias=clock] img')).to_have_js_property('complete', True)
            assert page.locator('[data-alias=clock] .glyph').is_visible()
            assert not page.locator('[data-alias=clock] img').is_visible()
            if viewport['width']==390:
                assert page.locator('#apps').evaluate("el=>getComputedStyle(el).gridTemplateColumns.split(' ').length")==4
            tile=page.locator('[data-alias=tarot]')
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
            assert page.url==base+'#fixture'
            rect=page.locator('iframe').bounding_box()
            assert rect['width']==viewport['width'] and rect['height']==viewport['height'],rect
            go_home(page)
            assert page.locator('iframe').count()==0
            for app_id,url in [('tarot','https://kinoko34077.github.io/tarot-draw/'),('chord','https://kinoko34077.github.io/Micro-Chordbot/'),('warp','https://kinoko34077.github.io/frequency-warp-vst/'),('clock','https://standby-display.kinotch.workers.dev/')]:
                page.locator(f'[data-alias={app_id}]').click()
                assert page.locator('iframe').get_attribute('src')==url
                assert page.locator('iframe').get_attribute('sandbox')=='allow-scripts'
                assert page.url==base+'#fixture'
                go_home(page)
            page.evaluate('navigator.serviceWorker.ready')
            page.goto(base)
            page.reload()
            page.wait_for_function('!!navigator.serviceWorker.controller')
            expect(page.locator('#apps button')).to_have_count(4)
            page.unroute('**/catalog.json')
            page.route('**/catalog.json',lambda route:route.abort())
            page.context.set_offline(True)
            page.reload()
            expect(page.locator('#apps button')).to_have_count(4)
            page.context.set_offline(False)
            page.close()
        context=browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True)
        page=context.new_page()
        page.route('https://**/*',lambda route:route.fulfill(status=200,body='<h1>Mock external candidate</h1>',content_type='text/html'))
        mock_catalog(page,catalog_fixture())
        page.goto(base+'#fixture')
        tile=page.locator('[data-app-id=probe]')
        tile.wait_for()
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
        handle=page.locator('#home-handle')
        expect(page.locator('#back')).to_be_hidden()
        expect(page.locator('#stage-browser,#stage-retry')).to_have_count(0)
        box=handle.bounding_box()
        assert box['width']<=16 and box['height']<=56
        def swipe(dx,dy):
            r=handle.bounding_box()
            sx,sy=r['x']+r['width']/2,r['y']+r['height']/2
            touch('touchStart',[{'x':sx,'y':sy}])
            touch('touchMove',[{'x':sx+dx,'y':sy+dy}])
            touch('touchEnd',[])
        swipe(-65,0)
        expect(page.locator('#back')).to_be_visible()
        # No iframe replacement when changing the dock.
        page.frame_locator('iframe').locator('#draft').fill('keep')
        swipe(35,0)
        expect(page.locator('#back')).to_be_hidden()
        handle.tap()
        expect(page.locator('#back')).to_be_visible()
        handle.tap()
        expect(page.locator('#back')).to_be_hidden()
        y0=handle.bounding_box()['y']
        swipe(0,100)
        assert handle.bounding_box()['y']>y0+50
        expect(page.locator('#back')).to_be_hidden()
        swipe(-300,0)
        expect(page.locator('#home-dock')).to_have_attribute('data-side','left')
        expect(page.locator('#back')).to_be_hidden()
        swipe(70,0)
        expect(page.locator('#back')).to_be_visible()
        expect(page.frame_locator('iframe').locator('#draft')).to_have_value('keep')
        page.locator('#back').tap()
        context.close()
        # New application arrives as data, with no individual launch permission.
        ctx=browser.new_context()
        page=ctx.new_page()
        page.route('https://**/*',lambda route:route.fulfill(status=200,body='<h1>Mock external candidate</h1>',content_type='text/html'))
        data=catalog_fixture()
        now=data['generatedAt']
        data['repositories'].append(dict(id='99',fullName='kinoko34077/new-app',visibility='public',archived=True,observedAt=now))
        data['applications'].append(dict(id='repo:99:main',repositoryId='99',title='New app',kind='application',canonicalUrl='https://kinoko34077.github.io/new-app/',publication=dict(basis='github-pages',observedAt=now)))
        mock_catalog(page,data)
        page.goto(base)
        fresh=page.locator('[data-app-id="repo:99:main"]')
        expect(page.locator('#repo-summary')).to_have_text('公開リポジトリ (5)')
        page.locator('#repo-summary').click()
        expect(page.locator('#repo-list [data-repo-id="99"]')).to_have_attribute('href','https://github.com/kinoko34077/new-app')
        page.locator('#repo-summary').click()
        fresh.click()
        assert not page.locator('#app-menu').is_visible()
        expect(page.locator('iframe')).to_have_attribute('src','https://kinoko34077.github.io/new-app/')
        expect(page.locator('iframe')).to_have_attribute('sandbox','allow-scripts')
        expect(page.locator('#stage-browser,#stage-retry')).to_have_count(0)
        page.frame_locator('iframe').locator('h1').wait_for()
        expect(page.locator('iframe')).to_have_attribute('src','https://kinoko34077.github.io/new-app/')
        go_home(page)
        fresh.click(button='right')
        expect(page.locator('#app-menu')).to_be_visible()
        page.locator('#menu-cancel').click()
        # Removal in a newer snapshot replaces cached state, never merges.
        page.unroute('**/catalog.json')
        data['repositories'].pop();data['applications'].pop()
        t=datetime.fromisoformat(now)+timedelta(seconds=1)
        data['generatedAt']=t.isoformat().replace('+00:00','Z')
        mock_catalog(page,data)
        page.reload()
        expect(page.locator('#apps button')).to_have_count(4)
        assert fresh.count()==0
        expect(page.locator('#repo-list [data-repo-id="99"]')).to_have_count(0)
        # Stale catalog retains usable links; known removals do not return.
        page.unroute('**/catalog.json')
        expired=datetime.now(timezone.utc)-timedelta(days=4)
        data['generatedAt']=expired.replace(microsecond=0).isoformat().replace('+00:00','Z')
        for item in data['repositories']:item['observedAt']=data['generatedAt']
        for item in data['applications']:item['publication']['observedAt']=data['generatedAt']
        data['validUntil']=(expired+timedelta(days=3)).replace(microsecond=0).isoformat().replace('+00:00','Z')
        page.evaluate("(data)=>localStorage.setItem('kinotch-hub.catalog.v1',JSON.stringify(data))",data)
        mock_catalog(page,data)
        page.reload()
        expect(page.locator('#catalog-status')).to_contain_text('更新遅延')
        expect(page.locator('#apps button')).to_have_count(4)
        page.locator('[data-alias=tarot]').click()
        expect(page.locator('iframe')).to_have_attribute('src','https://kinoko34077.github.io/tarot-draw/')
        go_home(page)
        assert fresh.count()==0
        ctx.close()
        # Live refresh must not replace unchanged controls, dismiss a valid
        # menu, reload a running frame, or keep a removed target launchable.
        ctx=browser.new_context(viewport={'width':390,'height':844})
        page=ctx.new_page()
        page.route('https://**/*',lambda route:route.fulfill(status=200,body='<input id="draft">',content_type='text/html'))
        data=catalog_fixture()
        def advance():
            data['generatedAt']=(datetime.fromisoformat(data['generatedAt'])+timedelta(seconds=1)).isoformat().replace('+00:00','Z')
            data['validUntil']=(datetime.fromisoformat(data['generatedAt'])+timedelta(days=3)).isoformat().replace('+00:00','Z')
            page.evaluate('refreshCatalog()')
        mock_catalog(page,data)
        page.goto(base)
        tile=page.locator('[data-alias=tarot]')
        tile.wait_for()
        tile.evaluate('el=>window.originalTile=el')
        tile.focus()
        advance()
        assert tile.evaluate('el=>el===window.originalTile&&document.activeElement===el')
        tile.click(button='right')
        page.locator('#menu-share').focus()
        advance()
        expect(page.locator('#app-menu')).to_be_visible()
        assert page.locator('#menu-share').evaluate('el=>document.activeElement===el')
        assert tile.evaluate('el=>el===window.originalTile')
        # Metadata change is not a changed URL. Keep the dialog/selection.
        data['applications'][0]['title']='Tarot Draw renamed'
        advance()
        expect(page.locator('#menu-title')).to_have_text('Tarot Draw renamed')
        expect(page.locator('#app-menu')).to_be_visible()
        page.locator('#menu-open').click()
        frame=page.frame_locator('iframe')
        frame.locator('#draft').fill('unsaved draft')
        page.locator('iframe').evaluate('el=>window.originalFrame=el')
        advance()
        assert page.locator('iframe').evaluate('el=>el===window.originalFrame')
        expect(frame.locator('#draft')).to_have_value('unsaved draft')
        # Removal must revoke new actions, without replacing the active page.
        data['applications'].pop(0);data['repositories'].pop(0)
        advance()
        expect(page.locator('#stage-browser,#stage-retry')).to_have_count(0)
        expect(page.locator('#home-handle')).to_be_visible()
        expect(frame.locator('#draft')).to_have_value('unsaved draft')
        go_home(page)
        expect(tile).to_have_count(0)
        chord=page.locator('[data-alias=chord]')
        chord.click(button='right')
        data['applications'].pop(0);data['repositories'].pop(0)
        advance()
        expect(page.locator('#app-menu')).to_be_hidden()
        expect(chord).to_have_count(0)
        assert page.locator('iframe').count()==0
        ctx.close()
        # Real generated artifact (not the fixture) must be admitted by the
        # actual launcher. Mock only off-origin images, never catalog.json.
        ctx=browser.new_context()
        page=ctx.new_page()
        page.route('https://**/*',lambda route:route.abort())
        real=json.loads((ROOT/'preview/catalog.json').read_text(encoding='utf-8'))
        page.goto(base)
        expect(page.locator('#catalog-status')).to_contain_text('更新 ')
        expect(page.locator('#apps button')).to_have_count(sum(a['kind']!='documentation' for a in real['applications']))
        for item in real['applications']:
            if item['kind']!='documentation':
                expect(page.locator('[data-app-id="'+item['id']+'"]')).to_have_count(1)
        expect(page.locator('#repo-list a')).to_have_count(len(real['repositories']))
        # Client guards independently reject bad publication/visibility data.
        assert page.evaluate("""() => {
            const raw=JSON.parse(localStorage.getItem('kinotch-hub.catalog.v1'));
            const bad=structuredClone(raw);bad.repositories[0].visibility='private';
            try{CatalogRuntime.admit(bad);return false}catch{return true}
        }""")
        ctx.close()
        browser.close()
    print('PASS: icon grid, context menu, native share mock, clipboard fallback, manual copy, keyboard, touch long press/scroll/tap, 2 viewports, input, isolation, return, data-driven routing (mocked), stale links retained, edge home dock/swipe/reposition, public repository references, live refresh interaction continuity, manifest, offline shell')
finally:
    server.shutdown()
    server.server_close()
