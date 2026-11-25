"""R0 public URL observation, disposable Chromium context only.

No accounts or user data. No production writes. Non-read HTTP methods and
service workers are blocked for this storage-only observation.
The candidate sandbox is applied only in the test browser's DOM.
"""
import json
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from r0_frame_probe import STATE_PROBE, privacy_preserving_chromium

HUB = 'https://kinoko34077.github.io/kinotch-hub/'
PAGES = 'https://kinoko34077.github.io'
STANDBY = 'https://standby-display.kinotch.workers.dev/'


def origin(url):
    u = urlsplit(url)
    return f'{u.scheme}://{u.netloc}'


def disposable(browser):
    context = browser.new_context(viewport={'width':390,'height':844},
                                  service_workers='block')
    context.route('**/*', lambda route: route.continue_()
                  if route.request.method in ('GET','HEAD','OPTIONS')
                  else route.abort())
    return context


def app_candidates(browser):
    context = disposable(browser)
    try:
        resp = context.request.get(HUB+'catalog.json', timeout=20000)
        assert resp.ok and resp.url == HUB+'catalog.json', resp.status
        data = resp.json()
        repos = {r['id']:r for r in data['repositories']
                 if r['visibility']=='public'}
        found = {}
        for app in data['applications']:
            repo = repos.get(app['repositoryId'])
            if not repo or app['kind']=='documentation':
                continue
            url = app['canonicalUrl']
            root = PAGES+'/'+repo['fullName'].split('/')[1]+'/'
            if (repo['fullName'].startswith('kinoko34077/') and
                url.startswith(root) and origin(url)==PAGES):
                if app['id']=='repo:1408820750:main':
                    found['tarot']=app
                elif repo['fullName'].lower()=='kinoko34077/gesture-ime':
                    found['gesture']=app
            elif url==STANDBY:
                found['standby']=app
        return data['generatedAt'], found
    finally:
        context.close()


def snapshot(target, value=None):
    return target.evaluate(STATE_PROBE, {'value':value})


def vals(state):
    return tuple(state[k].get('value') for k in ('local','idb'))


def enter(page, app):
    url = app['canonicalUrl']
    page.goto(HUB,wait_until='domcontentloaded',timeout=20000)
    assert page.url==HUB, page.url
    tile = page.locator('button[data-app-id="'+app['id']+'"]')
    tile.wait_for(state='visible',timeout=15000)
    tile.click(timeout=10000)
    old=page.locator('#surface iframe')
    old.wait_for(state='attached',timeout=10000)
    assert old.get_attribute('sandbox')=='allow-scripts'
    assert old.get_attribute('src')==url
    page.evaluate("""() => {
      const old=document.querySelector('#surface iframe');
      const f=document.createElement('iframe');
      f.title=old.title;
      f.setAttribute('sandbox','allow-scripts allow-same-origin allow-downloads');
      f.referrerPolicy=old.referrerPolicy;
      f.src=old.src;
      old.replaceWith(f);
    }""")
    handle=page.locator('#surface iframe').element_handle(timeout=10000)
    frame=handle.content_frame()
    assert frame is not None
    frame.wait_for_url(lambda u: origin(u)==origin(url),
                       wait_until='domcontentloaded',timeout=20000)
    assert origin(frame.url)==origin(url), frame.url
    assert page.url==HUB
    return frame


def probe(browser, label, app):
    context=disposable(browser)
    try:
        page=context.new_page()
        page.set_default_timeout(12000)
        url=app['canonicalUrl']
        page.goto(url,wait_until='domcontentloaded',timeout=20000)
        assert origin(page.url)==origin(url), page.url
        seed=snapshot(page,'direct')
        assert vals(seed)==('direct','direct'), seed
        frame=enter(page,app)
        before=snapshot(frame)
        written=snapshot(frame,'embedded')
        reopened=snapshot(enter(page,app))
        page.goto(url,wait_until='domcontentloaded',timeout=20000)
        after=snapshot(page)
        same=origin(url)==PAGES
        passed=(
            vals(before)==(('direct','direct') if same else (None,None))
            and vals(written)==('embedded','embedded')
            and vals(reopened)==('embedded','embedded')
            and vals(after)==(('embedded','embedded') if same else ('direct','direct'))
            and before['parentAccess']==same
        )
        return {'app':label,'url':url,'status':'PASS' if passed else 'FAIL',
                'seed':seed,'before':before,'written':written,
                'reopened':reopened,'after':after}
    finally:
        context.close()


def main():
    with sync_playwright() as p:
        harness=p.chromium.launch(args=['--enable-automation'])
        try:
            browser=privacy_preserving_chromium(p,harness,None)
            try:
                generated,apps=app_candidates(browser)
                reports=[]
                for label in ('tarot','gesture','standby'):
                    if label not in apps:
                        reports.append({'app':label,'status':'UNVERIFIED','reason':'catalog candidate absent'})
                        continue
                    try:
                        reports.append(probe(browser,label,apps[label]))
                    except Exception as exc:
                        reports.append({'app':label,'status':'UNVERIFIED',
                                        'reason':type(exc).__name__+': '+str(exc)[:350]})
                print('R0_PUBLIC_CONTINUITY '+json.dumps(
                    {'catalogGeneratedAt':generated,'browser':browser.version,
                     'serviceWorkers':'blocked','reports':reports},ensure_ascii=False))
                if any(r['status']!='PASS' for r in reports):
                    raise SystemExit(2)
            finally:
                browser.close()
        finally:
            harness.close()


if __name__=='__main__':
    main()
