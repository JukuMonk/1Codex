# -*- coding: utf-8 -*-
"""make_sandbox — собирает из examples/ маленький «проект» tests/sandbox/
с Configuration.mdo, чтобы прогонять инструменты и тестовые задачи без
настоящей конфигурации.

Это НЕ проект EDT (нет .project/DT-INF и типовых объектов): в EDT его не
импортировать. Он нужен для tools/check_project.py, tools/scaffold.py и
проверки решений из tests/tasks.md.

Пересобрать: python tools/make_sandbox.py
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edt_lib as L  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(HERE, 'examples')
SB = os.path.join(HERE, 'tests', 'sandbox')
SRC = os.path.join(SB, 'src')

# что откуда копировать: (папка примера, вид, имя)
OBJECTS = [
    ('metadata/enum/ПримерПеречисление', 'Enum', 'ПримерПеречисление'),
    ('metadata/catalog/ПримерСправочник', 'Catalog', 'ПримерСправочник'),
    ('metadata/constant/ПримерУпрощённыйРежим', 'Constant', 'ПримерУпрощённыйРежим'),
    ('metadata/information-register/ПримерНедоступность', 'InformationRegister', 'ПримерНедоступность'),
    ('metadata/accumulation-register/ПримерОстатки', 'AccumulationRegister', 'ПримерОстатки'),
    ('metadata/document/ПримерДокумент', 'Document', 'ПримерДокумент'),
    ('metadata/common-module/ПримерОбщийМодуль', 'CommonModule', 'ПримерОбщийМодуль'),
    ('metadata/data-processor/ПримерОбработка', 'DataProcessor', 'ПримерОбработка'),
    ('metadata/report/ПримерОтчет', 'Report', 'ПримерОтчет'),
    ('reports/report-with-parameters-and-grouping/ПримерОтчетПоПериоду', 'Report', 'ПримерОтчетПоПериоду'),
    ('metadata/role/ПримерРоль', 'Role', 'ПримерРоль'),
    ('metadata/subsystem/ПримерРаздел', 'Subsystem', 'ПримерРаздел'),
    ('metadata/subsystem/CommonPictures/ПримерРаздел', 'CommonPicture', 'ПримерРаздел'),
    ('mobile/mobile-form/ПримерМобильная', 'DataProcessor', 'ПримерМобильная'),
    ('forms/html-field-form/ПримерКарта', 'DataProcessor', 'ПримерКарта'),
]

CONFIG_HEAD = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<mdclass:Configuration xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass" uuid="%s">'
               % L.stable_uid('sandbox/configuration'),
               '  <name>Песочница</name>', '  <synonym>', '    <key>ru</key>',
               '    <value>Песочница skill pack</value>', '  </synonym>',
               '  <usePurposes>PersonalComputer</usePurposes>',
               '  <usePurposes>MobileDevice</usePurposes>',
               '  <scriptVariant>Russian</scriptVariant>',
               '  <compatibilityMode>8.3.24</compatibilityMode>']


def main():
    if os.path.isdir(SB):
        shutil.rmtree(SB)
    os.makedirs(SRC)
    entries = {}
    for rel, kind, name in OBJECTS:
        src = os.path.join(EX, rel.replace('/', os.sep))
        dst = os.path.join(SRC, L.FOLDERS[kind], name)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns('README.md'))
        entries.setdefault(kind, []).append(name)
    lines = list(CONFIG_HEAD)
    # порядок групп — как в настоящем Configuration.mdo
    for kind in ('Subsystem', 'CommonModule', 'CommonPicture', 'Role', 'Constant', 'Catalog',
                 'Document', 'Enum', 'Report', 'DataProcessor', 'InformationRegister',
                 'AccumulationRegister'):
        for name in entries.get(kind, []):
            tag = L.CONFIG_GROUPS[kind]
            lines.append('  <%s>%s.%s</%s>' % (tag, kind, name, tag))
    lines += ['</mdclass:Configuration>', '']
    L.write_text(os.path.join(SRC, 'Configuration', 'Configuration.mdo'), L.join(lines))
    L.write_text(os.path.join(SB, 'README.md'), L.join([
        '# Песочница', '',
        'Собрана из `examples/` скриптом `tools/make_sandbox.py`. Это не проект EDT',
        '(в EDT не импортируется), а площадка для `tools/check_project.py`,',
        '`tools/scaffold.py` и тестовых задач из `tests/tasks.md`.', '',
        'Пересобрать с нуля: `python tools/make_sandbox.py`.', '']), xml=False)
    print('песочница: %s, объектов %d' % (SB, len(OBJECTS)))


if __name__ == '__main__':
    main()
