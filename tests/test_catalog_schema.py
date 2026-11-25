"""Validate the published catalog shape, independently of launch policy."""
import copy
import json
import pathlib
import unittest
from jsonschema import Draft202012Validator, FormatChecker

ROOT=pathlib.Path(__file__).resolve().parents[1]
SCHEMA=json.loads((ROOT/'schemas/catalog-snapshot.v1.schema.json').read_text(encoding='utf-8'))
STAMP='2026-11-25T00:00:00Z'
SAMPLE={'schemaVersion':1,'generatedAt':STAMP,'validUntil':'2026-11-28T00:00:00Z','repositories':[{'id':'1','fullName':'kinoko34077/example','visibility':'public','archived':False,'observedAt':STAMP}],'applications':[{'id':'repo:1:main','repositoryId':'1','title':'Example','kind':'application','canonicalUrl':'https://kinoko34077.github.io/example/','iconUrl':'https://kinoko34077.github.io/example/icon.svg','publication':{'basis':'github-pages','observedAt':STAMP}},{'id':'site:example','repositoryId':None,'title':'Standalone','kind':'application','canonicalUrl':'https://example.org/','publication':{'basis':'owner-confirmed-public-site','observedAt':STAMP}}]}
class ShapeTests(unittest.TestCase):
    def test_schema_and_valid_snapshot(self):
        Draft202012Validator.check_schema(SCHEMA)
        Draft202012Validator(SCHEMA,format_checker=FormatChecker()).validate(SAMPLE)
    def test_invalid_shapes(self):
        cases=[
            (('repositories',0,'visibility'),'private'),
            (('repositories',0,'fullName'),'other/example'),
            (('repositories',0,'token'),'secret'),
            (('applications',0,'canonicalUrl'),'http://example.org/'),
            (('applications',0,'iconUrl'),'javascript:alert(1)'),
            (('applications',0,'id'),'site:example'),
            (('applications',1,'id'),'repo:1:main'),
            (('applications',1,'publication','basis'),'github-pages'),
            (('generatedAt',),'not-a-date'),
            (('schemaVersion',),2)]
        for path,value in cases:
            with self.subTest(path=path):
                data=copy.deepcopy(SAMPLE)
                obj=data
                for key in path[:-1]: obj=obj[key]
                obj[path[-1]]=value
                self.assertFalse(Draft202012Validator(SCHEMA,format_checker=FormatChecker()).is_valid(data))
if __name__=='__main__': unittest.main()
