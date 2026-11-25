"""R0 browser spike — synthetic loopback only, no production or network access.
Run in an authorized local browser environment:
  python -m pip install playwright
  python -m playwright install chromium
  python spikes/r0_frame_probe.py
Optional CHROMIUM_EXECUTABLE points to an existing Chromium installation.
This is not a PWA install test or evidence of real-site compatibility.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright

APP = '''<!doctype html><meta charset="utf-8">
<input aria-label="draft"><button id="probe">Probe</button><output id="result"></output>
<script>
document.querySelector('#probe').onclick = () => {
  const result = {storage: false, parentAccess: false};
  try { localStorage.setItem('probe','1'); result.storage = localStorage.getItem('probe') === '1'; } catch(e) {}
  try { result.parentAccess = !!parent.document.body; } catch(e) {}
  try { top.location.href = '/escaped'; } catch(e) {}
  document.querySelector('#result').textContent = JSON.stringify(result);
};
</script>'''

SHELL = '''<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{margin:0}iframe{width:100%;height:100dvh;border:0;display:block}
#home{position:fixed;z-index:1;right:8px;bottom:8px}</style>
<button id="home" hidden>Home</button><main id="stage"></main>
<script>
const stage = document.querySelector('#stage'), home = document.querySelector('#home');
window.launch = (url, flags) => {
  const frame = document.createElement('iframe'); frame.title='Probe app';
  frame.setAttribute('sandbox',flags); frame.src=url;
  stage.replaceChildren(frame); home.hidden=false;
};
home.onclick=()=>{stage.replaceChildren();home.hidden=true;};
</script>'''


def start_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/app':
                body = APP
            elif self.path == '/escaped':
                body = '<p>unexpected navigation</p>'
            elif self.path == '/hub/':
                body = SHELL
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server



# Data continuity is distinct from storage availability. All values below are
# synthetic, scoped to one disposable browser context per case.
STATE_PROBE = r"""async ({value}) => {
  const result = {origin: self.origin, parentAccess: false};
  try { result.parentAccess = parent !== self && !!parent.document.body; } catch(e) {}
  try {
    if (value !== null) localStorage.setItem('r0-continuity', value);
    result.local = {value: localStorage.getItem('r0-continuity')};
  } catch(e) { result.local = {error: e.name}; }
  try {
    const db = await new Promise((resolve,reject) => {
      const req = indexedDB.open('r0-continuity',1);
      req.onupgradeneeded=()=>req.result.createObjectStore('state');
      req.onsuccess=()=>resolve(req.result);
      req.onerror=()=>reject(req.error);
      req.onblocked=()=>reject(new Error('blocked'));
    });
    try {
      const mode = value === null ? 'readonly' : 'readwrite';
      result.idb = {value: await new Promise((resolve,reject) => {
        const tx=db.transaction('state',mode), store=tx.objectStore('state');
        if(value !== null) store.put(value,'draft');
        const req=store.get('draft');
        tx.oncomplete=()=>resolve(req.result ?? null);
        tx.onabort=()=>reject(tx.error || new Error('aborted'));
        tx.onerror=()=>reject(tx.error || req.error);
      })};
    } finally { db.close(); }
  } catch(e) { result.idb = {error: e.name}; }
  return result;
}"""


def continuity_probe(browser, base, cross, cross_site, partitioned=False):
    """Exercise read/write visibility in both directions, not just open()."""
    flags = 'allow-scripts allow-same-origin'
    cases = (
        ('opaque', base, 'allow-scripts', False),
        ('same-origin-trusted', base, flags, False),
        ('same-site-cross-origin', cross, flags, False),
        ('cross-site-cross-origin', cross_site, flags, False),
        ('top-level-sibling-path', base, None, True),
    )
    reports = []

    def snapshot(target, value=None):
        return target.evaluate(STATE_PROBE, {'value': value})

    def values(state):
        return tuple(state[k].get('value') for k in ('local', 'idb'))

    def enter(page, app_url, sandbox, top_level):
        page.goto(base+'/hub/')
        if top_level:
            page.goto(app_url)
            return page
        page.evaluate('([u,f]) => launch(u,f)', [app_url, sandbox])
        page.frame_locator('iframe').get_by_label('draft').wait_for()
        frame = page.frame_locator('iframe').get_by_label('draft').element_handle().owner_frame()
        assert frame is not None
        return frame

    for label, origin, sandbox, top_level in cases:
        context = browser.new_context(viewport={'width':390, 'height':844})
        try:
            page = context.new_page()
            app_url = origin+'/app'
            page.goto(app_url)
            seed = snapshot(page, 'direct')
            assert values(seed) == ('direct','direct'), (label,seed)
            target = enter(page, app_url, sandbox, top_level)
            before = snapshot(target)
            written = snapshot(target, 'embedded')
            target = enter(page, app_url, sandbox, top_level)
            reopened = snapshot(target)
            page.goto(app_url)
            direct_after = snapshot(page)
            assert values(direct_after)[0] in ('direct','embedded'), (label,direct_after)
            assert values(direct_after)[1] in ('direct','embedded'), (label,direct_after)
            if label == 'opaque':
                assert 'error' in before['local'] and 'error' in before['idb'], before
                assert not before['parentAccess'], before
                assert values(direct_after) == ('direct','direct'), direct_after
            elif label in ('same-origin-trusted','top-level-sibling-path'):
                assert values(before) == ('direct','direct'), (label,before)
                assert values(written) == ('embedded','embedded'), (label,written)
                assert values(reopened) == ('embedded','embedded'), (label,reopened)
                assert values(direct_after) == ('embedded','embedded'), (label,direct_after)
                assert before['parentAccess'] == (label=='same-origin-trusted'), before
            else:
                assert not before['parentAccess'], before
                if partitioned and label == 'cross-site-cross-origin':
                    assert values(before) == (None,None), (label,before)
                    assert values(written) == ('embedded','embedded'), (label,written)
                    assert values(reopened) == ('embedded','embedded'), (label,reopened)
                    assert values(direct_after) == ('direct','direct'), (label,direct_after)
                elif partitioned and label == 'same-site-cross-origin':
                    assert values(before) == ('direct','direct'), (label,before)
                    assert values(direct_after) == ('embedded','embedded'), (label,direct_after)
                # Default automation mode is only an observation.
            reports.append({
                'case':label,'appUrl':app_url,'topSite':base,
                'directSeed':seed,'embeddedBefore':before,
                'embeddedWritten':written,'embeddedReopened':reopened,
                'directAfter':direct_after,
                'directToEmbedded':{
                    k:before[k].get('value')=='direct' for k in ('local','idb')
                },
                'embeddedToDirect':{
                    k:direct_after[k].get('value')=='embedded' for k in ('local','idb')
                },
            })
        finally:
            context.close()
    print(('R0_PARTITIONED_CONTINUITY ' if partitioned else 'R0_CONTINUITY ') + json.dumps(reports,ensure_ascii=False))
    return reports




def privacy_preserving_chromium(p, browser, executable):
    """Restore Chromium storage partitioning disabled by the test harness.
    Preserve all unrelated default arguments. No production/client settings.
    """
    session = browser.new_browser_cdp_session()
    try:
        args = session.send('Browser.getBrowserCommandLine')['arguments']
    finally:
        session.detach()
    feature = 'ThirdPartyStoragePartitioning'
    ignored = []
    replacements = []
    disabled = False
    enabled = False
    for prefix in ('--disable-features=', '--enable-features='):
        switches = [arg for arg in args if arg.startswith(prefix)]
        if not switches:
            if prefix.startswith('--enable'):
                replacements.append(prefix + feature)
            continue
        # Playwright supplies one combined feature switch. Preserve its
        # unrelated entries rather than replacing the entire feature list.
        assert len(switches) == 1, 'ambiguous feature arguments'
        original = switches[0]
        entries = original[len(prefix):].split(',')
        present = feature in entries
        if prefix.startswith('--disable'):
            disabled = present
            entries = [entry for entry in entries if entry != feature]
        else:
            enabled = present
            if not present:
                entries.append(feature)
        if ','.join(entries) != original[len(prefix):]:
            ignored.append(original)
            if entries:
                replacements.append(prefix + ','.join(entries))
    print('R0_AUTOMATION_FLAGS ' + json.dumps({
        'partitionDisabledByDefault':disabled,
        'partitionExplicitlyEnabledByDefault':enabled,
    }))
    # All names are reserved .test hostnames and resolve solely to the
    # existing synthetic loopback servers. No proxy, TLS or origin bypass.
    replacements.append('--host-resolver-rules=MAP hub.r0-a.test 127.0.0.1, MAP app.r0-a.test 127.0.0.1, MAP app.r0-b.test 127.0.0.1')
    private = p.chromium.launch(executable_path=executable,
                                ignore_default_args=ignored,args=['--enable-automation', *replacements])
    session = private.new_browser_cdp_session()
    try:
        effective = session.send('Browser.getBrowserCommandLine')['arguments']
    finally:
        session.detach()
    assert not any(feature in arg.split('=',1)[-1].split(',')
                   for arg in effective if arg.startswith('--disable-features='))
    assert any(feature in arg.split('=',1)[-1].split(',')
               for arg in effective if arg.startswith('--enable-features='))
    return private



def main():
    shell, other = start_server(), start_server()
    base = f'http://127.0.0.1:{shell.server_port}'
    cross = f'http://127.0.0.1:{other.server_port}'
    reports = []
    try:
        with sync_playwright() as p:
            executable = os.environ.get('CHROMIUM_EXECUTABLE')
            browser = p.chromium.launch(executable_path=executable, args=['--enable-automation'])
            print('Chromium:', browser.version)
            for viewport in ({'width':390,'height':844}, {'width':844,'height':390}):
                page = browser.new_page(viewport=viewport)
                for label, origin, flags, expected_storage in (
                    ('same-origin-opaque', base, 'allow-scripts', False),
                    ('cross-origin-storage', cross, 'allow-scripts allow-same-origin', True),
                ):
                    page.goto(base + '/hub/')
                    page.evaluate('([u,f]) => launch(u,f)', [origin+'/app', flags])
                    frame = page.frame_locator('iframe')
                    frame.get_by_label('draft').fill('draft text')
                    assert frame.get_by_label('draft').input_value() == 'draft text'
                    frame.locator('#probe').click()
                    result = json.loads(frame.locator('#result').inner_text())
                    assert result['storage'] == expected_storage, result
                    assert not result['parentAccess'], result
                    assert page.url == base+'/hub/', page.url
                    rect = page.locator('iframe').bounding_box()
                    assert rect and rect['width'] == viewport['width'] and rect['height'] == viewport['height'], rect
                    page.locator('#home').click()
                    assert page.locator('iframe').count() == 0
                    reports.append({'case':label,'viewport':viewport,**result,
                                    'topUrlUnchanged':True,'fullViewport':True,'returnHome':True})
                page.close()
            continuity_probe(browser, base, cross, f'http://localhost:{other.server_port}')
            partitioned = privacy_preserving_chromium(p, browser, executable)
            try:
                continuity_probe(partitioned,
                    f'http://hub.r0-a.test:{shell.server_port}',
                    f'http://app.r0-a.test:{other.server_port}',
                    f'http://app.r0-b.test:{other.server_port}', partitioned=True)
            finally:
                partitioned.close()
                browser.close()
    finally:
        for server in (shell, other):
            server.shutdown()
            server.server_close()
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main()
