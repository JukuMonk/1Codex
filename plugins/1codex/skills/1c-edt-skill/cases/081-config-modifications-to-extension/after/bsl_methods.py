# -*- coding: utf-8 -*-
"""Разбор модуля BSL на методы и сравнение модулей поставщика и ПРОД по методам."""
import difflib
import io
import re

RX_START = re.compile(r'^\s*(Асинх\s+)?(Процедура|Функция)\s+([\wА-Яа-яЁё]+)\s*\(', re.I)
RX_END = re.compile(r'^\s*(КонецПроцедуры|КонецФункции)\b', re.I)
RX_ANN = re.compile(r'^\s*&')


def read(path):
    with io.open(path, encoding='utf-8-sig', newline='') as f:
        return f.read().replace('\r\n', '\n').split('\n')


class Method:
    def __init__(self, name, kind, ann, lines, start):
        self.name, self.kind, self.ann, self.lines, self.start = name, kind, ann, lines, start

    @property
    def header(self):
        return self.lines[0]

    @property
    def body(self):
        return self.lines[1:-1]

    @property
    def export(self):
        head = []
        for l in self.lines:
            head.append(l)
            if ')' in l:
                break
        return bool(re.search(r'\)\s*Экспорт', ' '.join(head), re.I))

    @property
    def directives(self):
        return [a.strip() for a in self.ann]


def parse(lines):
    """-> (методы по порядку, строки вне методов с номерами)."""
    methods, outside = [], []
    i, n = 0, len(lines)
    pending = []        # строки аннотаций перед методом
    while i < n:
        l = lines[i]
        m = RX_START.match(l)
        if m:
            j = i
            while j < n and not RX_END.match(lines[j]):
                j += 1
            ann = []
            while outside and RX_ANN.match(outside[-1][1]):
                ann.insert(0, outside.pop()[1])
            methods.append(Method(m.group(3), m.group(2), ann, lines[i:j + 1], i))
            i = j + 1
            continue
        outside.append((i, l))
        i += 1
    return methods, outside


def compare(vendor_path, prod_path):
    a_lines, b_lines = read(vendor_path), read(prod_path)
    am, ao = parse(a_lines)
    bm, bo = parse(b_lines)
    ad = {m.name.lower(): m for m in am}
    bd = {m.name.lower(): m for m in bm}
    added = [m for m in bm if m.name.lower() not in ad]
    removed = [m for m in am if m.name.lower() not in bd]
    changed = [(ad[m.name.lower()], m) for m in bm if m.name.lower() in ad and ad[m.name.lower()].lines != m.lines]
    out_a = [l for _, l in ao]
    out_b = [l for _, l in bo]
    outside_diff = [d for d in difflib.unified_diff(out_a, out_b, lineterm='', n=0) if d[:1] in '+-' and d[:3] not in ('+++', '---')]
    return dict(added=added, removed=removed, changed=changed, outside=outside_diff, vendor=am, prod=bm)
