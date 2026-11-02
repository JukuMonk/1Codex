# -*- coding: utf-8 -*-
"""Отделить правки пользователя, сделанные в EDT, от вывода генераторов.

Пользователь правит форму прямо в EDT; чтобы правка пережила пересборку,
её надо перенести в генератор. Скрипт берёт версию файлов из HEAD проекта
EDT, прогоняет по ней указанные генераторы, кладёт результат в scratchpad
рядом с текущим (пользовательским) файлом и пишет разницу. Файлы проекта
после прогона возвращаются к пользовательской версии.

Запуск:
  python инструменты/выделить_правки.py "Documents/уатЗаказГрузоотправителя/Forms/ФормаДокумента"          "Form.form,Module.bsl" "расчёт_времени_заказа.py,время_заказа_на_форме.py" заказ
Аргументы: папка объекта в src, файлы через запятую, генераторы по порядку,
метка для имён файлов разницы. Цель — «строк разницы 0» по каждому файлу:
тогда генератор воспроизводит правку пользователя байт в байт.

Что уже известно о том, как пишет сам EDT (иначе разница на каждом поле):
  · <title> поля — сразу за <id>, <handlers> — сразу за </dataPath>;
  · значения по умолчанию не пишутся: visible=false, autoMaxWidth=false,
    representation=None, showTitle=false, group=Horizontal у групп.
"""

import io, os, shutil, subprocess, sys, difflib
ПРОЕКТ = r'C:\Users\user\AppData\Local\1C\1cedtstart\projects\MVM\УАТ_МВМ'
ПАПКА = os.path.join(ПРОЕКТ, "src", *sys.argv[1].split("/"))
СКРАТЧ = os.environ.get('CLAUDE_SCRATCHPAD') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dist', 'правки')
os.makedirs(СКРАТЧ, exist_ok=True)
ФАЙЛЫ = sys.argv[2].split(",")
рел = "src/" + sys.argv[1] + "/"
def чит(п): return io.open(p := п, 'rb').read()
пользователь = {ф: чит(os.path.join(ПАПКА, ф)) for ф in ФАЙЛЫ}
for ф in ФАЙЛЫ:
    io.open(os.path.join(СКРАТЧ, "пользователь_" + sys.argv[4] + "_" + ф), 'wb').write(пользователь[ф])
try:
    for ф in ФАЙЛЫ:
        head = subprocess.run(['git', '-C', ПРОЕКТ, 'show', 'HEAD:' + рел + ф], capture_output=True, check=True).stdout
        io.open(os.path.join(ПАПКА, ф), 'wb').write(head)
    for скрипт in sys.argv[3].split(","):
        r = subprocess.run([sys.executable, os.path.join('инструменты', скрипт)], capture_output=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        print(скрипт, 'код', r.returncode, (r.stdout.decode('utf-8', 'replace').strip().splitlines() or [''])[-1])
        if r.returncode: print(r.stderr.decode('utf-8', 'replace')[-800:])
    генератор = {ф: чит(os.path.join(ПАПКА, ф)) for ф in ФАЙЛЫ}
    for ф in ФАЙЛЫ:
        io.open(os.path.join(СКРАТЧ, "генератор_" + sys.argv[4] + "_" + ф), 'wb').write(генератор[ф])
finally:
    for ф in ФАЙЛЫ:
        io.open(os.path.join(ПАПКА, ф), 'wb').write(пользователь[ф])
for ф in ФАЙЛЫ:
    a = генератор[ф].decode('utf-8-sig').split('\r\n'); b = пользователь[ф].decode('utf-8-sig').split('\r\n')
    д = list(difflib.unified_diff(a, b, 'генератор', 'пользователь', lineterm='', n=2))
    io.open(os.path.join(СКРАТЧ, 'разница_' + sys.argv[4] + '_' + ф + '.diff'), 'w', encoding='utf-8', newline='').write(chr(10).join(д))
    print(ф, ': строк разницы', len(д), '| генератор', len(a), 'пользователь', len(b))
