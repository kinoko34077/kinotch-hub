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


def main():
    shell, other = start_server(), start_server()
    base = f'http://127.0.0.1:{shell.server_port}'
    cross = f'http://127.0.0.1:{other.server_port}'
    reports = []
    try:
        with sync_playwright() as p:
            executable = os.environ.get('CHROMIUM_EXECUTABLE')
            browser = p.chromium.launch(executable_path=executable)
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
            browser.close()
    finally:
        for server in (shell, other):
            server.shutdown()
            server.server_close()
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main()
