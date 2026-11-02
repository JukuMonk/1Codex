import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

TOOLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS))
import designer_lib as dl
import lint_dump
import check_designer
import check_links
from workflow.source_guard import cosmetic_equivalent


class DesignerTests(unittest.TestCase):
    def test_empty_external_children_use_canonical_empty_element(self):
        text=dl.external_data_processor_xml('Example','Example')
        self.assertIn('<ChildObjects/>',text)
        self.assertNotIn('<ChildObjects>\n',text)
    def test_context_nested_and_restored_on_exception(self):
        original = dl.metadata_version()
        with dl.generation_context('2.21'):
            self.assertIn('version="2.21"', dl.catalog_xml('Example', 'Example'))
            self.assertIn('xmlns:pal=', dl.catalog_xml('Example', 'Example'))
            with self.assertRaises(RuntimeError):
                with dl.generation_context('2.20'):
                    self.assertEqual(dl.metadata_version(), '2.20')
                    raise RuntimeError()
            self.assertEqual(dl.metadata_version(), '2.21')
        self.assertEqual(dl.metadata_version(), original)
        with self.assertRaises(ValueError):
            with dl.generation_context('unknown'): pass

    def test_hide_replaces_visible_and_is_idempotent(self):
        for property in ('<Visible>true</Visible>', '<Visible>false</Visible>', ''):
            text = '<Form>\n\t<InputField name="Поле" id="1">\n\t\t<DataPath>X</DataPath>\n\t\t' + property + '\n\t</InputField>\n</Form>'
            result = dl.form_hide(text, 'Поле')
            self.assertEqual([n.text for n in ET.fromstring(result).findall('.//Visible')], ['false'])
            self.assertEqual(dl.form_hide(result, 'Поле'), result)

    def test_hide_rejects_ambiguous_field(self):
        with self.assertRaises(ValueError): dl.form_hide('<Form/>', 'Absent')
        with self.assertRaises(ValueError): dl.form_hide('<Form><InputField name="A"/><InputField name="A"/></Form>', 'A')

    def test_reorder_retains_unknown_columns_and_nested_group(self):
        text = '<Form>\n\t<Table name="Rows">\n\t\t<ChildItems>\n\t\t\t<InputField name="A"/>\n\t\t\t<PictureField name="Картинка"/>\n\t\t\t<ColumnGroup name="G"><ChildItems><InputField name="Nested"/></ChildItems></ColumnGroup>\n\t\t\t<FutureField name="B" value="&gt;"/>\n\t\t</ChildItems>\n\t</Table>\n</Form>'
        result = dl.form_reorder_columns(text, 'Rows', ['B', 'A'])
        self.assertEqual([n.get('name') for n in ET.fromstring(result).findall('.//Table/ChildItems/*')], ['B', 'A', 'Картинка', 'G'])
        self.assertIn('<ColumnGroup name="G"><ChildItems><InputField name="Nested"/></ChildItems></ColumnGroup>', result)
        self.assertEqual(dl.form_reorder_columns(result, 'Rows', ['B', 'A']), result)
        with self.assertRaises(ValueError): dl.form_reorder_columns(text, 'Rows', ['Missing'])
        with self.assertRaises(ValueError): dl.form_reorder_columns(text, 'Rows', ['A', 'A'])

    def test_git_error_is_not_empty_diff(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(subprocess.CalledProcessError): dl.changed_objects(temp)

    def test_git_changed_objects_cyrillic_and_space_in_path(self):
        with tempfile.TemporaryDirectory(prefix='skill with space ') as temp:
            p = Path(temp)
            subprocess.run(['git', 'init', '-q', temp], check=True)
            subprocess.run(['git', '-C', temp, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'initial'], check=True)
            target = p/'Catalogs/Пример/Forms/Моя форма/Ext/Module.bsl'
            target.parent.mkdir(parents=True)
            target.write_text('test', encoding='utf-8')
            self.assertEqual(dl.changed_objects(temp), {('Catalog', 'Пример')})

    def test_structural_input_missing_empty_and_bad_xml(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            self.assertTrue(check_designer.check(p/'missing'))
            self.assertTrue(check_designer.check(p))
            (p/'Configuration.xml').write_text('<broken', encoding='utf-8')
            self.assertTrue(check_designer.check(p))
            with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(lint_dump.lint(temp), 2)

    def test_metadata_references_and_form_property_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p/'Configuration.xml').write_text('<MetaDataObject><Configuration><ChildObjects><Catalog>Missing</Catalog></ChildObjects></Configuration></MetaDataObject>')
            (p/'Form.xml').write_text('<Form><ChildItems><InputField id="1"><Visible>true</Visible><Visible>false</Visible></InputField><InputField id="1"/></ChildItems></Form>')
            errors = check_designer.check(p)
            self.assertTrue(any('Missing' in x for x in errors))
            self.assertTrue(any('duplicate IDs' in x for x in errors))
            self.assertTrue(any('duplicate Visible' in x for x in errors))

    def test_baseline_counts_duplicates_and_survives_line_shifts(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            p = Path(temp); mod = p/'Module.bsl'; baseline = p/'baseline.json'
            line = 'А = Справочники.Пример.ПустаяСсылка;\n'
            mod.write_text(line, encoding='utf-8')
            self.assertEqual(lint_dump.lint(temp, str(baseline), True), 0)
            self.assertEqual(json.loads(baseline.read_text(encoding='utf-8'))['schema_version'], 2)
            mod.write_text('// moved\n' + line, encoding='utf-8')
            self.assertEqual(lint_dump.lint(temp, str(baseline)), 0)
            mod.write_text('// moved\n' + line*2, encoding='utf-8')
            self.assertEqual(lint_dump.lint(temp, str(baseline)), 1)

    def test_legacy_baseline_is_not_unbounded_suppression(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            p = Path(temp); mod=p/'Module.bsl'; baseline=p/'baseline.txt'
            line = 'А = Справочники.Пример.ПустаяСсылка;\n'
            mod.write_text(line, encoding='utf-8')
            baseline.write_text(lint_dump.key(lint_dump.problems(temp)[0]), encoding='utf-8')
            mod.write_text(line*2, encoding='utf-8')
            self.assertEqual(lint_dump.lint(temp, str(baseline)), 1)

    def test_link_does_not_accept_case_parent_for_missing_file(self):
        self.assertIsNotNone(check_links.resolve('cases/001-form-number-qualifiers/absent.md', str(TOOLS.parent)))
        self.assertIsNone(check_links.resolve('cases/001', str(TOOLS.parent)))
        self.assertIsNone(check_links.resolve('../SKILL.md', str(TOOLS.parent/'knowledge')))

    def test_comparison_preserves_leaf_spaces_and_qname_context(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=Path(temp)/'a.xml',Path(temp)/'b.xml'
            for left,right in [('<r><v> </v></r>','<r><v>  </v></r>'),
                ('<r xmlns:q="one"><v>q:Type</v></r>','<r xmlns:q="two"><v>q:Type</v></r>')]:
                a.write_text(left);b.write_text(right)
                self.assertFalse(cosmetic_equivalent(a,b))
            a.write_text('<r><v>x</v></r>');b.write_text('<r>\n <v>x</v>\n</r>')
            self.assertTrue(cosmetic_equivalent(a,b))
            a.write_text('<r xml:space="preserve"><g><v>x</v></g></r>')
            b.write_text('<r xml:space="preserve"><g> <v>x</v></g></r>')
            self.assertFalse(cosmetic_equivalent(a,b))
