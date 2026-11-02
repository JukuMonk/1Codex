# -*- coding: utf-8 -*-
"""Собирает сломанные фикстуры из рабочих примеров — чтобы дефекты были
ровно те, что описаны в tests/tasks.md, а остальное совпадало с образцом.

  python tests/expected/fixtures/make_fixtures.py

broken-form/Form.form  ← examples/metadata/data-processor/…/Forms/Форма/Form.form + 4 дефекта:
  1. удалён <saveWindowSettings>              (case 002)
  2. добавлен числовой реквизит «Лимит» без <numberQualifiers>   (case 001)
  3. колонке «Отметка» дан номер 1 — как у реквизита «Объект»   (case 003)
  4. у таблицы «Строки» удалён спутник searchStringAddition      (case 004)
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import edt_lib as L  # noqa: E402

CRLF = '\r\n'
SRC = os.path.join(ROOT, 'examples', 'metadata', 'data-processor', 'ПримерОбработка',
                   'Forms', 'Форма', 'Form.form')


def broken_form():
    text = L.read_text(SRC)
    # 1. saveWindowSettings
    text, n = re.subn(r'\r\n  <saveWindowSettings>true</saveWindowSettings>', '', text)
    assert n == 1, 'saveWindowSettings'
    # 2. числовой реквизит без квалификаторов
    # у реквизитов и колонок между <name> и <id> может стоять <title>
    num = r'\r\n\s*<name>[^<]+</name>\r\n(?:[^\r]*\r\n)*?\s*<id>(\d+)</id>'
    last_id = max(int(x) for x in re.findall(r'<attributes>' + num, text))
    last_col = max([int(x) for x in re.findall(r'<columns>' + num, text)] + [0])
    attr = CRLF.join(L.form_attribute(L.Ids(max(last_id, last_col) + 1), 'Лимит', 'Лимит', 'Number'))
    attr = re.sub(r'\r\n\s*<numberQualifiers>.*?</numberQualifiers>', '', attr, flags=re.S)
    assert 'numberQualifiers' not in attr
    pos = text.index(CRLF + '  <formCommands>')
    text = text[:pos] + CRLF + attr + text[pos:]
    # 3. колонка с номером реквизита «Объект»
    text, n = re.subn(r'(<columns>\r\n\s*<name>Отметка</name>\r\n(?:[^\r]*\r\n)*?\s*<id>)\d+(</id>)',
                      r'\g<1>1\g<2>', text)
    assert n == 1, 'column'
    # 4. спутник таблицы
    text, n = re.subn(r'\r\n    <searchStringAddition>.*?</searchStringAddition>', '', text, flags=re.S)
    assert n == 1, 'companion'
    dst = os.path.join(HERE, 'broken-form', 'Form.form')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    io.open(dst, 'w', encoding='utf-8', newline='').write(text)
    print('ok  broken-form/Form.form')


if __name__ == '__main__':
    broken_form()
