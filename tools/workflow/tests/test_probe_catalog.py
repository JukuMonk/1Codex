from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/workflow'))
sys.path.insert(0,str(ROOT/'tools'))
from form_contract import inspect_form
import designer_lib as dl
spec=importlib.util.spec_from_file_location('save_probe',ROOT/'reference/probes/save_probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


class ProbeCatalog(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_three_probes_valid_xml_and_profile(self):
        for kind in ('catalog','document','close'):
            with self.subTest(kind=kind):
                folder=self.root/kind
                metadata=probe.generate(folder,kind,'TestObject','distinct-sandbox')
                for xml in folder.rglob('*.xml'):ET.parse(xml)
                form=next(folder.glob('*/Forms/Форма/Ext/Form.xml'))
                result=inspect_form(form)
                self.assertFalse(result['errors'])
                self.assertEqual(ET.parse(form).getroot().get('version'),'2.21')
                module=next(folder.glob('*/Forms/Форма/Ext/Form/Module.bsl')).read_text(encoding='utf-8-sig')
                self.assertIn('distinct-sandbox',module)
                self.assertIn('СтрокаСоединенияИнформационнойБазы()',module)
                self.assertNotIn('C:/gold',module)
                self.assertTrue(metadata.is_file())
                if kind=='document':self.assertIn('РежимЗаписиДокумента.Проведение',module)
                if kind=='close':self.assertIn('ЗавершениеРаботы',module)

    def test_probe_is_deterministic_and_preserves_context(self):
        old=dl.metadata_version()
        probe.generate(self.root/'one','catalog','Demo','distinct-sandbox')
        probe.generate(self.root/'two','catalog','Demo','distinct-sandbox')
        files={p.relative_to(self.root/'one'):p.read_bytes() for p in (self.root/'one').rglob('*') if p.is_file()}
        self.assertEqual(files,{p.relative_to(self.root/'two'):p.read_bytes() for p in (self.root/'two').rglob('*') if p.is_file()})
        self.assertEqual(dl.metadata_version(),old)

    def test_existing_output_is_never_overwritten(self):
        self.root.joinpath('keep.txt').write_text('keep')
        with self.assertRaises(ValueError):probe.generate(self.root,'catalog','Demo','distinct-sandbox')
        self.assertEqual(self.root.joinpath('keep.txt').read_text(),'keep')

    def test_identifiers_and_markers_cannot_inject_bsl(self):
        for obj,marker in [('Bad;Object','distinct-sandbox'),('Demo','short'),('Demo','x\ny-sandbox'),('Demo','Pwd=should-not-be-embedded')]:
            with self.assertRaises(ValueError):probe.generate(self.root/'unused','catalog',obj,marker)
        probe.generate(self.root/'safe','catalog','SAVE','CREATE_MARKER_INITIAL_SAVE')
        module=next((self.root/'safe').glob('*/Forms/Форма/Ext/Form/Module.bsl')).read_text(encoding='utf-8-sig')
        self.assertIn('Справочники.SAVE.СоздатьЭлемент()',module)
        self.assertIn('CREATE_MARKER_INITIAL_SAVE',module)

    def test_catalog_evidence_is_scoped_and_files_exist(self):
        entries=json.loads((ROOT/'reference/probes/catalog.json').read_text(encoding='utf-8'))['probes']
        self.assertEqual(len({entry['id'] for entry in entries}),5)
        for entry in entries:
            self.assertEqual(entry['platform'],'8.5.1.1529')
            self.assertTrue(entry['acceptance'])
            self.assertTrue((ROOT/'reference/probes'/entry.get('generator',entry.get('fragment'))).is_file())


if __name__=='__main__':unittest.main()
