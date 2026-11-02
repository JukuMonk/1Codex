# -*- coding: utf-8 -*-
"""Общие помощники COM-тестов (18.10.2026): не писать в каждом тесте заново (ДиЗ-05: сравнение ссылок через «==»).

    from помощники import Проверки, первая, равно, com
    cn = com()                                  # ПЕСОЧНИЦА
    п = Проверки()
    п('5', равно(cn, ссылка.Проект, проект), 'проект записан')
    sys.exit(п.итог())
"""
import datetime
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(КОРЕНЬ, 'инструменты'))
import платформа as пл  # noqa: E402


def com(база='песочница'):
    return пл.com(база)


def равно(cn, а, б):
    """Ссылки и значения перечислений через COM — разные Python-объекты: «==» всегда ложь (ЛОВУШКИ У-29)."""
    return cn.XMLString(а) == cn.XMLString(б)


def первая(cn, текст, **параметры):
    """Поле «Ссылка» первой строки запроса или None. Параметр-дата — datetime (ТекущаяДата через COM нет)."""
    q = cn.NewObject('Запрос')
    q.Text = текст
    for к, з in параметры.items():
        q.SetParameter(к, з)
    в = q.Execute().Select()
    return в.Ссылка if в.Next() else None


def все(cn, текст, поля, **параметры):
    """Строки запроса списком словарей (значения — строковое представление 1С)."""
    q = cn.NewObject('Запрос')
    q.Text = текст
    for к, з in параметры.items():
        q.SetParameter(к, з)
    в = q.Execute().Select()
    итог = []
    while в.Next():
        итог.append({п: cn.String(getattr(в, п)) for п in поля})
    return итог


def сейчас():
    return datetime.datetime.now()


class Проверки:
    """Счётчик проверок: п(пункт, условие, что) печатает ОК / ОШИБКА; итог() — код возврата."""

    def __init__(self):
        self.список = []

    def __call__(self, пункт, условие, что):
        self.список.append((пункт, bool(условие), что))
        print('%s п.%s %s' % ('ОК  ' if условие else 'ОШИБКА', пункт, что), flush=True)
        return bool(условие)

    def итог(self):
        ошибок = sum(1 for _, ок, _ in self.список if not ок)
        print('\nпроверок %d, ошибок %d' % (len(self.список), ошибок))
        return 1 if ошибок else 0
