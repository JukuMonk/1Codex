# -*- coding: utf-8 -*-
"""Ссылки кода и схем расширения на объекты метаданных, которых нет в целевой поставке (и в самом расширении).

  NPCAP_TARGET=3.0.25.3 python tools/check_refs.py
Ловит: «Таблица не найдена», «Неизвестное имя типа», обращения к удалённым менеджерам — то, что CheckModules
не видит (тексты запросов и схемы СКД компилируются только при выполнении). Поля объектов не проверяются.
"""
import collections
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ext as be  # noqa: E402

RU = {'Справочник': 'Catalogs', 'Справочники': 'Catalogs', 'Документ': 'Documents', 'Документы': 'Documents',
      'РегистрСведений': 'InformationRegisters', 'РегистрыСведений': 'InformationRegisters',
      'РегистрНакопления': 'AccumulationRegisters', 'РегистрыНакопления': 'AccumulationRegisters',
      'Перечисление': 'Enums', 'Перечисления': 'Enums', 'ПланВидовХарактеристик': 'ChartsOfCharacteristicTypes',
      'ПланыВидовХарактеристик': 'ChartsOfCharacteristicTypes', 'Константы': 'Constants', 'Обработки': 'DataProcessors',
      'Обработка': 'DataProcessors', 'Отчеты': 'Reports', 'Отчет': 'Reports', 'БизнесПроцесс': 'BusinessProcesses',
      'Задача': 'Tasks', 'ПланОбмена': 'ExchangePlans', 'ЖурналДокументов': 'DocumentJournals',
      'РегламентныеЗадания': 'ScheduledJobs'}
RX = re.compile(r'(?<![\wЁё.])(%s)\.([А-Яа-яЁёA-Za-z_][\wЁё]*)' % '|'.join(sorted(RU, key=len, reverse=True)))
RX_MOD = re.compile(r'(?<![\wЁё.])(торо_[\wЁё]+|дс_[\wЁё]+|ОбщегоНазначения[\wЁё]*|[А-Я][\wЁё]*Сервер[\wЁё]*|[А-Я][\wЁё]*Клиент[\wЁё]*)\.([А-Яа-яЁё_][\wЁё]*)\s*\(')


def exists(root, d, name):
    return os.path.exists(os.path.join(root, d, name + '.xml'))


def module_methods(root, name):
    p = os.path.join(root, 'CommonModules', name, 'Ext', 'Module.bsl')
    if not os.path.exists(p):
        return None
    return set(m.group(1).lower() for m in re.finditer(r'^\s*(?:Процедура|Функция)\s+([\wЁё]+)\s*\([^)]*\)?[^\n]*Экспорт',
                                                       be.rd(p), re.M | re.I))


def main():
    found = collections.defaultdict(set)
    for d, _, fs in os.walk(be.OUT):
        for f in fs:
            if not (f.endswith('.bsl') or f == 'Template.xml'):
                continue
            path = os.path.join(d, f)
            rel = os.path.relpath(path, be.OUT).replace(os.sep, '/')
            txt = be.rd(path)
            for m in RX.finditer(txt):
                kind, name = m.group(1), m.group(2)
                dd = RU[kind]
                if name in ('ПустаяСсылка', 'Ссылка') or exists(be.TARGET, dd, name) or exists(be.OUT, dd, name):
                    continue
                found['%s.%s' % (kind, name)].add(rel)
            for m in RX_MOD.finditer(txt):
                mod, meth = m.group(1), m.group(2)
                if exists(be.OUT, 'CommonModules', mod) and not exists(be.TARGET, 'CommonModules', mod):
                    continue
                ms = module_methods(be.TARGET, mod)
                if ms is None:
                    continue                      # не общий модуль (переменная, объект)
                ext_ms = module_methods(be.OUT, mod) or set()
                if meth.lower() not in ms and meth.lower() not in ext_ms:
                    found['%s.%s()' % (mod, meth)].add(rel)
    for k in sorted(found):
        print('%-70s %s' % (k, ', '.join(sorted(found[k]))[:300]))
    print('не найдено в поставке %s: %d' % (be.TARGET_VERSION, len(found)))


if __name__ == '__main__':
    main()
