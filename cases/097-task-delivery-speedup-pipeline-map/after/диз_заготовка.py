# -*- coding: utf-8 -*-
"""Заготовка по новому ДиЗ (18.10.2026): docx → текст и рисунки в документы\\ДиЗ-NN\\, пункты (номер, справочник,
замечание, число рисунков) — на экран и в каркас отчёта инструменты\\отчёт_дизNN.py (ПУНКТЫ с пустыми «сделано» и
«как пользоваться» — их вписывают по ходу работы, отчёт собирается тем же скриптом). Пустой шаблон (пункты без
текста) — сразу сообщение: ДиЗ-05 сначала пришёл пустым.

  python инструменты/диз_заготовка.py "<путь к docx>" 05
"""
import io
import os
import re
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding='utf-8')
КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'


def прочитать(docx, папка_рисунков):
    """Строки документа: абзацы и строки таблиц (« / » между абзацами ячейки), [РИС NN] на месте рисунков."""
    z = zipfile.ZipFile(docx)
    цели = {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read('word/_rels/document.xml.rels'))}
    doc = ET.fromstring(z.read('word/document.xml'))
    os.makedirs(папка_рисунков, exist_ok=True)
    н = [0]

    def абзац(p):
        части = []
        for эл in p.iter():
            if эл.tag == W + 't' and эл.text:
                части.append(эл.text)
            elif эл.tag == A + 'blip' and эл.get(R + 'embed') in цели:
                н[0] += 1
                цель = цели[эл.get(R + 'embed')]
                данные = z.read('word/' + цель.lstrip('/').replace('word/', ''))
                open(os.path.join(папка_рисунков, '%02d%s' % (н[0], os.path.splitext(цель)[1] or '.png')), 'wb').write(данные)
                части.append(' [РИС %02d] ' % н[0])
        return ''.join(части).strip()
    строки = []
    for эл in doc.find(W + 'body'):
        if эл.tag == W + 'p' and абзац(эл):
            строки.append(абзац(эл))
        elif эл.tag == W + 'tbl':
            for tr in эл.iter(W + 'tr'):
                ячейки = [' / '.join(filter(None, (абзац(p) for p in tc.iter(W + 'p')))) for tc in tr.iter(W + 'tc')]
                строки.append('| ' + ' | '.join(ячейки) + ' |')
    return строки, н[0]


def пункты(строки, номер_диз):
    итог = []
    for с in строки:
        м = re.match(r'\|\s*(\d+)\.\s*([А-ЯЁA-Zа-яё].*?)\s*\|\s*$', с)     # «18.10.2026 г.» — не пункт
        if not м:
            continue
        части = [ч.strip() for ч in м.group(2).split(' / ')]
        справочник = части[0]
        замечание = ' '.join(ч for ч in части[1:] if ч and not ч.startswith('Рисунок') and not ч.startswith('[РИС'))
        рисунки = re.findall(r'\[РИС (\d+)\]', м.group(2))
        итог.append(('%s.%s' % (номер_диз, м.group(1)), справочник, замечание, рисунки))
    return итог


def каркас(номер_диз, п, источник):
    строки_п = []
    for номер, справочник, замечание, рисунки in п:
        строки_п.append("    ('%s', %r,\n     %r,\n     'TODO: что сделано',\n     'TODO: как пользоваться',\n"
                        "     []),  # рисунки ДиЗ: %s\n" % (номер, 'Справочник «%s»' % справочник.replace('Справочник ', ''),
                                                          замечание, ', '.join(рисунки) or '—'))
    return '''# -*- coding: utf-8 -*-
"""Отчёт о выполнении ДиЗ-%(н)s к ТЗ-01 (каркас — инструменты/диз_заготовка.py из %(и)s).

  python инструменты/отчёт_диз%(н)s.py
Кадры — итоговые снимки сценариев (ui_*.png): [(кадр без «ui_», подпись)] в последнем поле пункта.
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import отчёт_диз as од  # noqa: E402
from отчёт_диз03_04 import обрезать_по_форме, в_pdf  # noqa: E402

СНИМКИ = os.path.join(од.КОРЕНЬ, '.platform', 'снимки')
КАДРЫ = os.path.join(од.ПАПКА, 'диз%(н)s')
ИТОГ = os.path.join(од.ПАПКА, 'ДиЗ-%(н)s_отчёт.docx')

ПУНКТЫ = [
%(п)s]


def main():
    os.makedirs(КАДРЫ, exist_ok=True)
    for *_, рисунки in ПУНКТЫ:
        for кадр, _ in рисунки:
            if os.path.exists(os.path.join(СНИМКИ, 'ui_%%s.png' %% кадр)):
                обрезать_по_форме(os.path.join(СНИМКИ, 'ui_%%s.png' %% кадр), os.path.join(КАДРЫ, кадр + '.png'))
    сделано = sum(1 for п in ПУНКТЫ if not п[3].startswith('TODO'))
    од.собрать(ПУНКТЫ, КАДРЫ, ИТОГ,
               'Отчёт о выполнении ДиЗ-%(н)s к ТЗ-01 «АРМ Методолог в 1С:УП»\\nКонфигурация: ФРЕГАТ: управление проектами',
               'Выполнено: %%d из %%d пунктов' %% (сделано, len(ПУНКТЫ)),
               ['Обновить конфигурацию рабочей базы из файла .cf (Конфигуратор → Загрузить конфигурацию из файла → '
                'Обновить конфигурацию БД).'],
               'TODO: дата')
    в_pdf(ИТОГ)


if __name__ == '__main__':
    main()
''' % {'н': номер_диз, 'и': os.path.basename(источник), 'п': ''.join(строки_п)}


def main(docx, номер_диз):
    номер_диз = '%02d' % int(номер_диз)
    док = os.path.join(КОРЕНЬ, 'документы')
    копия = os.path.join(док, os.path.basename(docx))
    if os.path.abspath(docx) != os.path.abspath(копия):
        shutil.copy2(docx, копия)
    папка = os.path.join(док, 'ДиЗ-' + номер_диз)
    if os.path.isdir(папка):
        shutil.rmtree(папка)
    строки, рисунков = прочитать(копия, папка)
    io.open(os.path.splitext(копия)[0] + '.txt', 'w', encoding='utf-8').write('\n'.join(строки))
    п = пункты(строки, номер_диз)
    пустых = sum(1 for _, _, замечание, _ in п if len(замечание) < 5)
    print('ДиЗ-%s: строк %d, рисунков %d (%s), пунктов %d' % (номер_диз, len(строки), рисунков, папка, len(п)))
    for номер, справочник, замечание, рисунки in п:
        print('  %s %s — %s [рис. %s]' % (номер, справочник, замечание[:120], ', '.join(рисунки) or '—'))
    пустые_строки = [с for с in строки if re.match(r'\|\s*\d+\.\s*(/|\|)', с)]      # «| 1. / 1 / Рисунок 1.А |»
    if (п and пустых == len(п)) or (not п and пустые_строки):
        print('ВНИМАНИЕ: пункты без текста и рисунков — похоже, пустой шаблон; попросить заполненный файл')
        return 2
    отчёт = os.path.join(КОРЕНЬ, 'инструменты', 'отчёт_диз%s.py' % номер_диз)
    if not os.path.exists(отчёт):
        io.open(отчёт, 'w', encoding='utf-8', newline='\n').write(каркас(номер_диз, п, копия))
        print('каркас отчёта:', отчёт)
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
