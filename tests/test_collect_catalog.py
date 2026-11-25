import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from devflow_mapped_read import MappedReadError
from tools import collect_catalog as c

NOW=datetime(2026,11,25,tzinfo=timezone.utc)
def repo(ident=1,name='example',pages=True):
    return {'id':ident,'name':name,'full_name':'kinoko34077/'+name,'owner':{'login':'kinoko34077'},'private':False,'visibility':'public','archived':False,'has_pages':pages,'description':'must not project raw fields','token':'DO NOT OUTPUT'}
def one_page(rows):
    return lambda path:(rows,'')
def app_get(base):
    def get(url,kind):
        if url==base and kind=='html':return b'<link rel="manifest" href="manifest.json">'
        if url==base+'manifest.json' and kind=='manifest':return json.dumps({'name':'App','start_url':'./','display':'standalone','icons':[{'src':'icon.svg'}]}).encode()
        if url==base+'icon.svg' and kind=='image':return b'<svg/>'
        return None
    return get
class CatalogTests(unittest.TestCase):
    def test_public_only_and_manifest_discovery(self):
        base=c.PAGES+'/example/'
        data=c.collect([],one_page([repo()]),app_get(base),NOW)
        self.assertEqual(data['repositories'][0]['id'],'1')
        self.assertNotIn('description',data['repositories'][0])
        self.assertNotIn('token',json.dumps(data))
        app=data['applications'][0]
        self.assertEqual((app['id'],app['canonicalUrl'],app['iconUrl']),('repo:1:main',base,base+'icon.svg'))
    def test_rename_identity_and_add_without_ui(self):
        a=c.collect([],one_page([repo(name='new')]),app_get(c.PAGES+'/new/'),NOW)
        self.assertEqual(a['applications'][0]['id'],'repo:1:main')
        self.assertEqual(a['applications'][0]['canonicalUrl'],c.PAGES+'/new/')
    def test_shared_pagination_and_failure(self):
        calls=[]
        def get(path):
            calls.append(path)
            return ([repo(1)],'<https://evil.example>; rel="next"') if len(calls)==1 else ([repo(2,'other',False)],'')
        self.assertEqual(len(c.collect([],get,lambda *_:None,NOW)['repositories']),2)
        self.assertEqual(calls,[c.repository_path(1),c.repository_path(2)])
        def failure(path):
            if path==c.repository_path(1):return [repo()],'<https://evil.example>; rel="next"'
            raise c.CatalogError('NETWORK')
        with self.assertRaises(c.CatalogError):c.collect([],failure,lambda *_:None,NOW)
        with self.assertRaisesRegex(MappedReadError,'PAGE_LIMIT'):
            c.collect([],lambda path:([repo()],'<https://evil.example>; rel="next"'),lambda *_:None,NOW)
    def test_reject_private_wrong_owner_and_duplicates(self):
        for rows in ([dict(repo(),private=True)],[dict(repo(),visibility='private')],[dict(repo(),owner={'login':'other'})],[repo(),repo()]):
            with self.subTest(rows=rows),self.assertRaises(c.CatalogError):c.collect([],one_page(rows),lambda *_:None,NOW)
    def test_unknown_and_archived_excluded(self):
        data=c.collect([],one_page([repo(),repo(2,'archived')|{'archived':True},repo(3,'kinotch-hub'),repo(4,'not-pages',False)]),lambda *_:None,NOW)
        self.assertEqual(len(data['repositories']),4)
        self.assertEqual(data['applications'],[])
    def test_url_scope_and_untrusted_manifest(self):
        base=c.PAGES+'/example/'
        for u in ('https://evil.example/a','../other/','https://kinoko34077.github.io/other/','/example/%2e%2e/','https://user@kinoko34077.github.io/example/','/example/?token=x','/example/#x'):
            self.assertIsNone(c.safe_url(u,base))
        calls=[]
        def get(url,kind):
            calls.append(url)
            return b'<link rel="manifest" href="https://evil.example/manifest.json">'
        data=c.collect([],one_page([repo()]),get,NOW)
        self.assertEqual(data['applications'],[])
        self.assertEqual(calls,[base])
    def test_curated_multi_and_non_public_removed(self):
        defs=[{'repositoryId':'1','key':'main','title':'App','kind':'application','target':'pages','path':''},{'repositoryId':'1','key':'demo','title':'Demo','kind':'demo','target':'pages','path':'demo/'}]
        a=c.collect(defs,one_page([repo()]),lambda *_:b'html',NOW)
        self.assertEqual({x['id'] for x in a['applications']},{'repo:1:main','repo:1:demo'})
        self.assertEqual(c.collect(defs,one_page([]),lambda *_:b'html',NOW)['applications'],[])
        self.assertEqual(c.collect(defs,one_page([repo(pages=False)]),lambda *_:b'html',NOW)['applications'],[])
    def test_external_worker_and_icon_fallback(self):
        entry={'repositoryId':'969335914','key':'main','title':'Clock','kind':'application','target':'worker','url':c.WORKER+'/','icon':c.PAGES+'/standby-display/icon-192.png'}
        data=c.collect([entry],one_page([repo(969335914,'standby-display',False)]),lambda url,kind:b'html' if kind=='html' else None,NOW)
        app=data['applications'][0]
        self.assertEqual(app['canonicalUrl'],c.WORKER+'/')
        self.assertNotIn('iconUrl',app)
    def test_optional_icon_failure_and_malformed_manifest_urls_are_local(self):
        base=c.PAGES+'/example/'
        def get(url,kind):
            if kind=='html':return b'<link rel="manifest" href="manifest.json">'
            if kind=='manifest':return json.dumps({'name':'App','start_url':'./','display':'standalone','icons':[{'src':'https://['},{'src':'icon.svg'}]}).encode()
            if kind=='image':raise c.CatalogError('UPSTREAM_HTTP_FAILURE')
        data=c.collect([],one_page([repo()]),get,NOW)
        self.assertEqual(len(data['applications']),1)
        self.assertNotIn('iconUrl',data['applications'][0])
        def malformed(url,kind):
            if kind=='html':return b'<link rel="manifest" href="manifest.json">'
            if kind=='manifest':return json.dumps({'name':'App','start_url':'https://[','display':'standalone'}).encode()
            raise AssertionError('unexpected request')
        self.assertEqual(c.collect([],one_page([repo()]),malformed,NOW)['applications'],[])
    def test_complete_list_revokes_removed_app_despite_other_probe_failure(self):
        base=c.PAGES+'/example/'
        old=c.collect([],one_page([repo()]),app_get(base),NOW)
        self.assertEqual(len(old['applications']),1)
        def unavailable(url,kind):
            if url.startswith(c.PAGES+'/other/'):
                raise c.ProbeUnavailable('NETWORK')
            return app_get(c.PAGES+'/still/')(url,kind)
        new=c.collect([],one_page([repo(2,'other'),repo(3,'still')]),unavailable,NOW)
        self.assertEqual([a['id'] for a in new['applications']],['repo:3:main'])
        self.assertNotIn('repo:1:main',json.dumps(new))
    def test_transient_failure_retains_only_current_public_app(self):
        old=c.collect([],one_page([repo(),repo(2,'removed'),repo(3,'disabled')]),lambda url,kind: next((v for name in ('example','removed','disabled') if (v:=app_get(c.PAGES+'/'+name+'/')(url,kind)) is not None),None),NOW)
        self.assertEqual(len(old['applications']),3)
        def unavailable(url,kind):
            raise c.ProbeUnavailable('NETWORK')
        later=NOW+c.timedelta(days=5)
        new=c.collect([],one_page([repo(),repo(3,'disabled',False)]),unavailable,later,previous=old)
        self.assertEqual([a['id'] for a in new['applications']],['repo:1:main'])
        self.assertEqual(new['applications'][0],old['applications'][0])
        self.assertNotEqual(new['generatedAt'],old['generatedAt'])
        moved=c.collect([],one_page([repo(name='renamed')]),unavailable,later,previous=old)
        self.assertEqual(moved['applications'],[])
        gone=c.collect([],one_page([repo()]),lambda *_:None,later,previous=old)
        self.assertEqual(gone['applications'],[])
        non_pwa=c.collect([],one_page([repo()]),lambda url,kind:b'<html><title>App</title></html>' if kind=='html' else None,later,previous=old)
        self.assertEqual(non_pwa['applications'],[old['applications'][0]])
    def test_curated_failure_is_local_and_does_not_renew_observation(self):
        defs=[{'repositoryId':'1','key':'main','title':'App','kind':'application','target':'pages','path':''},{'repositoryId':'1','key':'demo','title':'Demo','kind':'demo','target':'pages','path':'demo/'}]
        old=c.collect(defs,one_page([repo()]),lambda *_:b'html',NOW)
        def partial(url,kind):
            if url.endswith('/demo/'):
                raise c.ProbeUnavailable('NETWORK')
            return b'html'
        new=c.collect(defs,one_page([repo()]),partial,NOW+c.timedelta(days=1),previous=old)
        self.assertEqual(len(new['applications']),2)
        byid={a['id']:a for a in new['applications']}
        self.assertEqual(byid['repo:1:demo']['publication']['observedAt'],old['generatedAt'])
        self.assertEqual(byid['repo:1:main']['publication']['observedAt'],new['generatedAt'])
        new=c.collect(defs[:1],one_page([repo()]),partial,NOW+c.timedelta(days=1),previous=old)
        self.assertEqual([a['id'] for a in new['applications']],['repo:1:main'])
    def test_semantic_validation_and_atomic_write(self):
        base=c.PAGES+'/example/'
        valid=c.collect([],one_page([repo()]),app_get(base),NOW)
        for change in ('wrong-id','bad-url','duplicate','future'):
            data=copy.deepcopy(valid)
            if change=='wrong-id':data['applications'][0]['id']='repo:99:main'
            elif change=='bad-url':data['applications'][0]['canonicalUrl']='https://example.org/'
            elif change=='duplicate':data['applications'].append(copy.deepcopy(data['applications'][0]))
            else:data['applications'][0]['publication']['observedAt']='2030-01-01T00:00:00Z'
            with self.subTest(change=change),self.assertRaises(c.CatalogError):c.validate_snapshot(data)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'catalog.json'
            c.write_atomic(path,valid)
            before=path.read_bytes()
            with self.assertRaises(c.CatalogError):c.write_atomic(path,{})
            self.assertEqual(path.read_bytes(),before)
if __name__=='__main__':unittest.main()
