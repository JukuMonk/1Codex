import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from form_contract import inspect_form


class FormContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def form(self, main, commands, posting='Allow'):
        path = self.root/'Documents/Demo/Forms/Main/Ext/Form.xml'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('<Form xmlns="urn:form" xmlns:v8="urn:v8"><Attributes><Attribute name="Object"><Type><v8:Type>'+main+'</v8:Type></Type><MainAttribute>true</MainAttribute></Attribute></Attributes><CommandSet>'+''.join('<ExcludedCommand>'+c+'</ExcludedCommand>' for c in commands)+'</CommandSet></Form>', encoding='utf-8')
        md = self.root/'Documents/Demo.xml'
        md.write_text('<MetaDataObject xmlns="urn:md"><Document><Properties><Posting>'+posting+'</Posting></Properties></Document></MetaDataObject>',encoding='utf-8')
        return path

    def test_catalog_write_and_close(self):
        result = inspect_form(self.form('cfg:CatalogObject.Demo', ['Write','WriteAndClose']))
        self.assertEqual(result['status'], 'ready')

    def test_document_rejects_catalog_close_before_platform_launch(self):
        result = inspect_form(self.form('cfg:DocumentObject.Demo', ['WriteAndClose']))
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['errors'][0]['code'], 'catalog_command_on_document')

    def test_document_posting_requires_allow(self):
        path = self.form('cfg:DocumentObject.Demo', ['Post','PostAndClose'])
        self.assertEqual(inspect_form(path)['status'], 'ready')
        path = self.form('cfg:DocumentObject.Demo', ['Post'], posting='Deny')
        self.assertEqual(inspect_form(path)['errors'][0]['code'], 'posting_disabled')

    def test_catalog_rejects_posting(self):
        result = inspect_form(self.form('cfg:CatalogObject.Demo', ['Post']))
        self.assertEqual(result['errors'][0]['code'], 'document_command_on_catalog')

    def test_unknown_command_is_not_declared_invalid(self):
        result = inspect_form(self.form('cfg:DocumentObject.Demo', ['PlatformFutureCommand']))
        self.assertFalse(result['errors'])
        self.assertEqual(result['status'], 'needs_probe')

    def test_unknown_platform_does_not_apply_unverified_rules(self):
        path = self.form('cfg:DocumentObject.Demo', ['WriteAndClose'])
        result = inspect_form(path, platform_version='9.0')
        self.assertEqual(result['status'], 'needs_probe')
        self.assertFalse(result['errors'])

    def test_bindings_are_checked_too(self):
        path = self.form('cfg:DocumentObject.Demo', [])
        content = path.read_text().replace('<CommandSet></CommandSet>','<ChildItems><Button name="Save"><CommandName>Form.StandardCommand.WriteAndClose</CommandName></Button></ChildItems>')
        path.write_text(content)
        self.assertEqual(inspect_form(path)['status'], 'blocked')

    def test_missing_posting_metadata_needs_probe(self):
        path = self.form('cfg:DocumentObject.Demo', ['Post'])
        (self.root/'Documents/Demo.xml').unlink()
        self.assertEqual(inspect_form(path)['status'], 'needs_probe')


if __name__ == '__main__': unittest.main()
