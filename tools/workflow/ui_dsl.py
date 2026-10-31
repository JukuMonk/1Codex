# -*- coding: utf-8 -*-
"""Составление проверяемых макросов UI DSL. Ни один helper не запускает 1С.

Имена кнопок и колонок берутся из выгрузки/дампа формы; автоматического подбора нет.
Снимки добавляет вызывающий код явно: диагностика по умолчанию текстовая.
"""
from dataclasses import dataclass


def step(action, *args):
    values = [str(value) for value in (action, *args)]
    for value in values:
        if any(char in value for char in ('|', '\r', '\n', '\x00')):
            raise ValueError('UI DSL argument cannot contain |, newline or NUL')
    return ' | '.join(values)


def exact_button(name):
    if not name or not name.strip():
        raise ValueError('Exact button name is required')
    return step('кнопка-точно', name)


@dataclass(frozen=True)
class Table:
    name: str

    def add(self, *, button):
        exact_button(button)
        return [step('добавить-строку', self.name, button)]

    def copy(self, *, button):
        exact_button(button)
        return [step('скопировать-строку', self.name, button)]

    def edit_choice(self, column):
        if not column:
            raise ValueError('Exact column name is required')
        return [step('редактировать-выбор', self.name, column)]

    def current(self, expected=''):
        return [step('текущаястрока', self.name, expected)]

    def order(self, column, *, rows):
        if isinstance(rows, bool) or not isinstance(rows, int) or not 1 <= rows <= 200:
            raise ValueError('rows must be an integer from 1 to 200')
        return [step('видимыйпорядок', self.name, column, rows)]


def advanced_search(*, button, field_label, pattern, dialog='Поиск',
                    field_selector='FieldSelector', pattern_field='Pattern', find_button='Find'):
    """Штатный расширенный поиск: открытие точной кнопкой, выбор поля, ввод, поиск.

Заданные по умолчанию имена диалога подтверждены сценарием UP 8.5.1.1529;
на другой форме их нужно передать по дампу. Нет «попробовать Найти/Поиск/Search».
"""
    return [exact_button(button), step('форма', dialog), step('поле', field_selector, field_label),
            step('поле', pattern_field, pattern), exact_button(find_button)]


def context(*, screenshot=None):
    lines = [step('контекст')]
    if screenshot is not None:
        if not screenshot:
            raise ValueError('Screenshot label must not be empty')
        lines.append(step('снимок', screenshot))
    return lines
