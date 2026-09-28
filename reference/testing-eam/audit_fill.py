# -*- coding: utf-8 -*-
"""Аудит заполненности демо-данных: доля пустых значений каждого реквизита eam-справочников и документов
(шапка и табличные части) в тестовой базе через COM. Выборка — до 300 элементов/строк на объект.
python audit_fill.py [порог_пустых_%=100]   — вывод: реквизиты, пустые в >= порога % записей (по умолчанию — всегда пустые)
Результат также в scratchpad\\audit_fill.tsv (все реквизиты с долей пустых)."""
import os
import sys
import time

import win32com.client

sys.stdout.reconfigure(encoding="utf-8")
IB = r"C:\Users\user\AppData\Local\Temp\claude\C--EAM\9bd8956d-7057-4d18-953c-62bdd34cda99\scratchpad\platform\ib"
OUT = r"C:\Users\user\AppData\Local\Temp\claude\C--EAM\9bd8956d-7057-4d18-953c-62bdd34cda99\scratchpad\audit_fill.tsv"
LIMIT = float(sys.argv[1]) if len(sys.argv) > 1 else 100.0
SKIP = {"Ссылка", "ПометкаУдаления", "Предопределенный", "ИмяПредопределенныхДанных", "ВерсияДанных", "НомерСтроки",
        "Проведен", "Родитель", "Владелец", "ЭтоГруппа", "Код", "Номер", "Дата", "Наименование"}

cn = win32com.client.Dispatch("V85.COMConnector").Connect('File="%s";' % IB)
q = cn.NewObject("Запрос")


def audit(table, kind, name, part=""):
    q.Текст = "ВЫБРАТЬ ПЕРВЫЕ 300 * ИЗ %s КАК Т" % table
    try:
        vt = q.Выполнить().Выгрузить()
    except Exception as e:  # noqa: BLE001
        return [(kind, name, part, "(ошибка запроса)", -1, 0)]
    n = vt.Количество()
    if not n:
        return []
    rows = []
    for ci in range(vt.Колонки.Количество()):
        col = vt.Колонки.Получить(ci)
        cname = col.Имя
        if cname in SKIP:
            continue
        empty = 0
        for ri in range(n):
            v = vt.Получить(ri).Получить(ci)
            if not cn.ЗначениеЗаполнено(v):
                empty += 1
        rows.append((kind, name, part, cname, round(empty * 100.0 / n, 1), n))
    return rows


res = []
t0 = time.time()
for coll, kind, prefix in ((cn.Метаданные.Справочники, "Справочник", "Справочник."),
                           (cn.Метаданные.Документы, "Документ", "Документ.")):
    for i in range(coll.Количество()):
        md = coll.Получить(i)
        name = md.Имя
        if not name.startswith("eam"):
            continue
        res += audit(prefix + name, kind, name)
        for j in range(md.ТабличныеЧасти.Количество()):
            ts = md.ТабличныеЧасти.Получить(j).Имя
            res += audit(prefix + name + "." + ts, kind, name, ts)
with open(OUT, "w", encoding="utf-8") as f:
    for r in res:
        f.write("\t".join(str(x) for x in r) + "\n")
cur = None
for kind, name, part, attr, pct, n in res:
    if pct >= LIMIT or pct < 0:
        key = "%s.%s%s (%d)" % (kind, name, "." + part if part else "", n)
        if key != cur:
            print(key)
            cur = key
        print("   %-40s %s%%" % (attr, pct))
print("объектов/таблиц проверено, реквизитов:", len(res), "за %.0f с" % (time.time() - t0))
