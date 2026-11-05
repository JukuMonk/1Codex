from pathlib import Path
import tempfile
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui_contract import load_inventory, validate_scenario, parse_runtime_tree

FORM='''<Form xmlns="urn:form" xmlns:v8="urn:v8"><Title><v8:item><v8:content>Demo form</v8:content></v8:item></Title><ChildItems>
<Button name="SaveExact"><Title><v8:item><v8:content>Save</v8:content></v8:item></Title></Button>
<Table name="Rows"><ChildItems><InputField name="RowsName"><Title><v8:item><v8:content>Name</v8:content></v8:item></Title></InputField><InputField name="RowsNumber"><ReadOnly>true</ReadOnly></InputField></ChildItems></Table>
<Table name="Other"><ChildItems><InputField name="OtherName"/></ChildItems></Table>
<InputField name="Header"/><UsualPage name="MainPage"/>
</ChildItems></Form>'''


class UiContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'Form.xml'; self.path.write_text(FORM,encoding='utf-8')
        self.inventory = load_inventory([self.path])

    def check(self, *lines): return validate_scenario(lines, self.inventory)

    def test_verified_table_edit_and_sort(self):
        result = self.check('форма | Demo','строка | Rows | первая','изменить | Rows | RowsName',
                            'ссылка | RowsName | Value','завершить | Rows','сортировать | Rows | Name')
        self.assertEqual(result['status'], 'ready')

    def test_button_name_is_exact_not_title_guess(self):
        self.assertEqual(self.check('кнопка-точно | Save')['status'], 'blocked')
        self.assertEqual(self.check('кнопка-точно | SaveExact')['status'], 'ready')
        self.assertEqual(self.check('кнопка | Save')['status'], 'ready')

    def test_unknown_standard_generated_button_requires_inventory(self):
        self.assertEqual(self.check('кнопка-точно | RowsAdd')['status'], 'blocked')
        runtime = {'forms':[{'id':str(self.path.resolve()),'elements':[{'name':'RowsAdd','kind':'Button','title':'Add'}]}]}
        result = validate_scenario(['кнопка-точно | RowsAdd'], load_inventory([self.path],runtime))
        self.assertEqual(result['status'], 'ready')

    def test_missing_table_edit_precondition(self):
        self.assertIn('table_not_editing_column',[x['code'] for x in self.check('ссылка | RowsName | Value')['errors']])

    def test_read_only_column_cannot_be_edited(self):
        self.assertIn('read_only_edit',[x['code'] for x in self.check('изменить | Rows | RowsNumber')['errors']])

    def test_column_from_another_table_rejected(self):
        self.assertIn('column_wrong_table',[x['code'] for x in self.check('ячейка | Rows | OtherName | Value')['errors']])

    def test_sort_requires_visible_title_not_element_name(self):
        self.assertEqual(self.check('сортировать | Rows | RowsName')['status'], 'blocked')

    def test_row_movement_clears_edit_state(self):
        result = self.check('изменить | Rows | RowsName','строка | Rows | следующая','поле | RowsName | Value')
        self.assertIn('table_not_editing_column',[x['code'] for x in result['errors']])

    def test_unknown_form_does_not_reuse_previous_form_evidence(self):
        result = self.check('форма | Unknown chooser','кнопка-точно | SaveExact')
        self.assertEqual(result['status'], 'needs_probe')
        self.assertFalse(result['errors'])

    def test_runtime_tree_keeps_table_parent(self):
        data = parse_runtime_tree('активная форма: Runtime\n  Тестируемая таблица формы Rows «Rows»\n    Тестируемое поле формы RuntimeField «Field»')
        self.assertEqual(data['forms'][0]['elements'][1]['table'],'Rows')

    def test_stale_inventory_fails_closed(self):
        self.path.write_text(FORM.replace('SaveExact','NewSave'),encoding='utf-8')
        self.assertIn('stale_inventory',[x['code'] for x in self.check('кнопка-точно | SaveExact')['errors']])

    def test_unsupported_action_is_explicit(self):
        self.assertEqual(self.check('press-key | F4')['status'],'needs_probe')

    def test_runtime_title_binding_preserves_xml_read_only(self):
        runtime={'forms':[{'id':str(self.path.resolve()),'title':'Dynamic title','elements':[
            {'name':'RowsNumber','kind':'InputField','table':'Rows','read_only':None}]}]}
        inventory=load_inventory([self.path],runtime)
        result=validate_scenario(['форма | Dynamic title','изменить | Rows | RowsNumber'],inventory)
        self.assertIn('read_only_edit',[x['code'] for x in result['errors']])


if __name__ == '__main__': unittest.main()
