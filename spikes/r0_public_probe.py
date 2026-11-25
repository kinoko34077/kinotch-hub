"""Read-only observation of published applications, never a launch permission list.
Fresh browser contexts; no logins, persistent user data, submissions or production writes.
"""
import json
from playwright.sync_api import sync_playwright
HUB='https://kinoko34077.github.io/kinotch-hub/'
# Controls identified in current public source. Exercise local UI state only.
CASES=[
 ('repo:1408820750:main','https://kinoko34077.github.io/tarot-draw/','#helpButton','#helpDialog'),
 ('repo:1235346464:main','https://kinoko34077.github.io/Micro-Chordbot/','button[data-view="settings"]','#view-settings'),
 ('repo:1416615773:main','https://kinoko34077.github.io/frequency-warp-vst/',None,None),
 ('repo:969335914:main','https://standby-display.kinotch.workers.dev/',None,None),
]
def observe(browser,case,embedded):
    ident,url,control,result=case
    context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    page=context.new_page()
    errors=[]
    def note(message):
        s=message.lower()
        if 'cors' in s:errors.append('CORS')
        elif 'sandbox' in s:errors.append('SANDBOX')
        elif 'securityerror' in s or 'localstorage' in s:errors.append('STORAGE')
        elif 'frame-ancestors' in s or 'x-frame-options' in s:errors.append('FRAME_POLICY')
        else:errors.append('OTHER')
    page.on('pageerror',lambda error:note(str(error)))
    page.on('console',lambda msg:note(msg.text) if msg.type=='error' else None)
    report={'mode':'hub' if embedded else 'direct','status':'UNVERIFIED'}
    try:
        if embedded:
            response=page.goto(HUB,wait_until='domcontentloaded',timeout=20000)
            page.locator('[data-app-id="'+ident+'"]').click(timeout=10000)
            target=page.frame_locator('#surface iframe')
        else:
            response=page.goto(url,wait_until='domcontentloaded',timeout=20000)
            target=page
        report['entryHttp']=response.status if response else None
        target.locator('body').wait_for(timeout=10000)
        if control and result:
            target.locator(control).click(timeout=10000)
            target.locator(result).wait_for(state='visible',timeout=5000)
            report['status']='PASS'
        else:
            report['status']='BODY_ONLY'
        if embedded:
            report['topUrlUnchanged']=page.url==HUB
            report['viewport']=page.locator('#surface iframe').bounding_box()
    except Exception as e:
        report['status']='FAIL'
        report['exceptionType']=type(e).__name__
    finally:
        report['errors']=dict((k,errors.count(k)) for k in sorted(set(errors)))
        context.close()
    return report
if __name__=='__main__':
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for case in CASES:
            print(json.dumps({'appId':case[0],'direct':observe(browser,case,False),'hub':observe(browser,case,True)}),flush=True)
        browser.close()
    # Findings are observations, not a gate disabling normal launch.
