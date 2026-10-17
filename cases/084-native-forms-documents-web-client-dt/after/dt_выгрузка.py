# -*- coding: utf-8 -*-
"""Выгрузка .dt для показа на другом сервере и обязательная проверка разворачиванием (case 084).

  python dt_выгрузка.py "C:\\Базы\\Demo" "C:\\out\\Demo.dt" [пользователь=Администратор]

1) /DumpIB пакетным Конфигуратором — базу не должны держать клиенты, COM и процесс веб-публикации (Apache держит
   файловую базу, пока жив сеанс: остановить службу/процесс публикации на время выгрузки);
2) CREATEINFOBASE во временную папку + /RestoreIB;
3) подключение через COM и вызов проверки (здесь — число элементов каждого справочника; в проекте — данные
   главной страницы «на сейчас», константы режима показа).
Перед выгрузкой: всё, что база досчитывает «до текущего момента» (регистры состояний, итоги), досчитать на ВЕСЬ
период показа — иначе через час после выгрузки картина «сейчас» пропадает (так было в ZHDRM).
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, r'C:\1c-edt-skill\tools')
import designer_lib as dl  # noqa: E402

V8 = r'C:\Program Files\1cv8\8.3.27.2342\bin\1cv8.exe'


def выгрузить(база, dt, пользователь='Администратор', пароль=''):
    if os.path.exists(dt):
        os.remove(dt)
    лог = os.path.join(tempfile.gettempdir(), 'dumpib.log')
    код, текст, сек = dl.designer(V8, база, ['/DumpIB', dt], лог, user=пользователь, pwd=пароль)
    if код or not os.path.exists(dt):
        sys.exit('DumpIB: код %s\n%s' % (код, текст))
    print('выгружено: %s, %d МБ, %.0f с' % (dt, os.path.getsize(dt) // 2 ** 20, сек))


def проверить(dt, пользователь='Администратор', пароль=''):
    папка = os.path.join(tempfile.gettempdir(), 'проверка_dt')
    shutil.rmtree(папка, ignore_errors=True)
    # CREATEINFOBASE: строку соединения — одним аргументом через dl/shell, кавычки внутри File="…" (ошибка «код 1»
    # при передаче списком аргументов — см. lessons.md)
    r = subprocess.run('"%s" CREATEINFOBASE File="%s"' % (V8, папка), shell=True, timeout=300)
    if r.returncode:
        sys.exit('CREATEINFOBASE: код %s' % r.returncode)
    лог = os.path.join(tempfile.gettempdir(), 'restoreib.log')
    # в пустой базе пользователей нет: /N не передавать (иначе «Пользователь ИБ не идентифицирован»)
    код, текст, _ = dl.designer(V8, папка, ['/RestoreIB', dt], лог, user=None)
    if код:
        sys.exit('RestoreIB: код %s\n%s' % (код, текст))
    import win32com.client
    cn = win32com.client.Dispatch('V83.COMConnector').Connect(
        'File="%s";Usr="%s";Pwd="%s";' % (папка, пользователь, пароль))
    q = cn.NewObject('Запрос')
    for i in range(cn.Метаданные.Справочники.Количество()):
        имя = cn.Метаданные.Справочники.Получить(i).Имя
        q.Text = 'ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК К ИЗ Справочник.%s' % имя
        print('%-40s %d' % (имя, q.Execute().Unload().Get(0).К))
    del cn
    shutil.rmtree(папка, ignore_errors=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    а = sys.argv[1:]
    выгрузить(а[0], а[1], *(а[2:3] or []))
    проверить(а[1], *(а[2:3] or []))
