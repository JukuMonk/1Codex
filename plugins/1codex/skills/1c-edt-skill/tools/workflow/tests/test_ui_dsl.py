# -*- coding: utf-8 -*-
"""Unit/static: построение DSL без 1С. Реальные команды проверяет sandbox smoke."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ui_dsl import Table, advanced_search, context, exact_button, step


class DslTests(unittest.TestCase):
    def test_exact_actions(self):
        table = Table('Шаги')
        self.assertEqual(table.add(button='ШагиДобавить'), ['добавить-строку | Шаги | ШагиДобавить'])
        self.assertEqual(table.copy(button='ШагиСкопировать'), ['скопировать-строку | Шаги | ШагиСкопировать'])
        self.assertEqual(table.edit_choice('ШагиРеквизит'), ['редактировать-выбор | Шаги | ШагиРеквизит'])
        self.assertEqual(table.current('№=1'), ['текущаястрока | Шаги | №=1'])

    def test_no_guessed_button(self):
        for button in ('', ' '):
            with self.assertRaises(ValueError):
                exact_button(button)

    def test_no_dsl_injection(self):
        for bad in ('abc|def', 'a\nb', 'a\rb', 'a\0b'):
            with self.assertRaises(ValueError):
                step('поле', 'Текст', bad)

    def test_order_bounds(self):
        self.assertEqual(Table('Шаги').order('ШагиШаг', rows=3), ['видимыйпорядок | Шаги | ШагиШаг | 3'])
        for bad in (0, 201, 1.5, '3', True):
            with self.assertRaises(ValueError):
                Table('Шаги').order('ШагиШаг', rows=bad)

    def test_search_matches_tested_platform_dialog(self):
        self.assertEqual(advanced_search(button='СписокНайти', field_label='Объект BPMN', pattern='ТЕСТ'), [
            'кнопка-точно | СписокНайти', 'форма | Поиск', 'поле | FieldSelector | Объект BPMN',
            'поле | Pattern | ТЕСТ', 'кнопка-точно | Find'])

    def test_screenshot_opt_in(self):
        self.assertEqual(context(), ['контекст'])
        self.assertEqual(context(screenshot='контекст_1'), ['контекст', 'снимок | контекст_1'])

    def test_manager_contract(self):
        bsl = (ROOT/'reference/manager.bsl').read_text(encoding='utf-8-sig')
        for marker in ('ПутьЖурнала + ".progress"', 'ПодробноеПредставлениеОшибки(ИнформацияОбОшибке())',
                       'ErrorInfo', 'AdditionalInfo', 'ServerText', 'Функция ТочнаяКнопка_',
                       'Шаг = "редактировать-выбор"', 'Шаг = "видимыйпорядок"'):
            self.assertIn(marker, bsl)
        # Для точной кнопки не должно быть fallback по заголовку.
        block = bsl.split('Функция ТочнаяКнопка_', 1)[1].split('КонецФункции', 1)[0]
        self.assertEqual(block.count('.НайтиОбъект('), 1)
        self.assertIn(', , ИмяКомандыТаблицы)', block)

    def test_error_probe_has_no_implicit_waiting_search(self):
        bsl = (ROOT/'reference/manager.bsl').read_text(encoding='utf-8-sig')
        block = bsl.split('Функция ОшибкаКлиента_()', 1)[1].split('Процедура ПроверитьОшибкуКлиента_()', 1)[0]
        self.assertNotIn('.НайтиОбъект(', block)
        self.assertNotIn('ТП.НайтиОбъекты(', block)
        self.assertIn('ТП.ПолучитьАктивноеОкно()', block)
        self.assertIn('.ПолучитьПодчиненныеОбъекты()', block)


if __name__ == '__main__':
    unittest.main()
