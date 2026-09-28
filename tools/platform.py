# -*- coding: utf-8 -*-
"""platform — проверка доработок в САМОЙ ПЛАТФОРМЕ 1С, без участия человека.

Четыре уровня, каждый ловит то, чего не видит предыдущий (knowledge/testing.md):
  load     EDT-проект → XML (1cedtcli export) → пустая файловая база → DESIGNER
           /LoadConfigFromFiles + /UpdateDBCfg. Ловит «Неверный путь к данным»,
           несовместимые свойства, ошибки реструктуризации. 5–20 мин.
  quick    как load, но без экспорта EDT: если менялись ТОЛЬКО модули .bsl, они
           переносятся в готовую XML-выгрузку, база создаётся заново. 1–2 мин.
  update   первый запуск: обновление ИБ (обработчики БСП) — через внешнее
           соединение (быстро, полный текст ошибки) или клиентом с чтением
           журнала регистрации.
  com      внешнее соединение (V8x.COMConnector) к базе: counts (объёмы своих
           объектов), reports (скомпоновать все варианты всех своих отчётов),
           query "<текст>" (любой запрос), call Модуль.Функция [аргументы].
           Серверный код исполняется по-настоящему; форм здесь нет.
  screens  снимки форм тонкого клиента: в XML-КОПИЮ (не в проект) добавляется
           запуск по /C, клиент открывает формы по списку, скрипт снимает окно
           процесса (PrintWindow) в PNG. Ловит раскладку, пустые формы, диалоги.
  forms    открыть в клиенте ВСЕ свои формы (ПолучитьФорму, без показа) и собрать
           ошибки ПриСозданииНаСервере/ПриОткрытии: «Поле объекта не обнаружено»,
           «Несоответствие типов», непроинициализированные реквизиты. Минуты.
  com fill аудит заполненности: доля пустых значений каждого реквизита своих
           справочников и документов (шапка и ТЧ) по ВСЕЙ таблице — где демо-посев
           или обработчики оставляют пробелы.

Настройки — platform.json рядом с папкой инструментов проекта (пример —
bootstrap/platform.json.example); путь к нему — первый аргумент или переменная
PLATFORM_JSON. Все пути внутри — абсолютные.

  python tools/platform.py <platform.json> load [git-ревизия]
  python tools/platform.py <platform.json> quick
  python tools/platform.py <platform.json> update [ib]
  python tools/platform.py <platform.json> com counts | reports [фильтр] | query "<текст>" | call Модуль.Функция [арг…]
  python tools/platform.py <platform.json> screens [шаг_с] [маска …]
  python tools/platform.py <platform.json> forms [префикс …]
  python tools/platform.py <platform.json> com fill [порог_пустых_%=100]
"""
import filecmp
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback

sys.stdout.reconfigure(encoding='utf-8')

# --------------------------------------------------------------- настройки
ПРИМЕР = {
    "v8": r"C:\Program Files\1cv8\8.3.27.2325\bin\1cv8.exe",
    "edt_cli": r"C:\Users\user\AppData\Local\1C\1cedtstart\installations\1C_EDT 2026.1\1cedt\1cedtcli.exe",
    "project": r"C:\...\projects\MVM\УАТ_МВМ",
    "work": r"C:\MVM\.platform",
    "prefix": "мвм",
    "com": "V83.COMConnector",
    "ib": r'File="C:\Users\user\Documents\InfoBase11";',
    "screens": {
        "server_call_module": "ОбщегоНазначенияВызовСервера",
        "global_client_module": "НапоминанияПользователяГлобальный",
        "after_start_module": "ОбщегоНазначенияКлиентПереопределяемый",
        "default_masks": ["Обработка.мвм*.Форма.*"]
    }
}


def load_cfg():
    path = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith('.json') else os.environ.get('PLATFORM_JSON')
    if not path or not os.path.exists(path):
        sys.exit(__doc__ + '\nНет platform.json. Пример:\n' + json.dumps(ПРИМЕР, ensure_ascii=False, indent=2))
    cfg = json.load(io.open(path, encoding='utf-8'))
    cfg['_args'] = sys.argv[2:] if sys.argv[1] == path else sys.argv[1:]
    return cfg


def step(title, args, log=None, enc='utf-8'):
    t0 = time.time()
    r = subprocess.run(args, capture_output=True, text=True, encoding=enc, errors='replace')
    print('%s: код %s, %.1f мин' % (title, r.returncode, (time.time() - t0) / 60))
    if log and os.path.exists(log):
        txt = open(log, encoding='utf-8-sig', errors='replace').read().strip()
        if txt:
            print(txt[-20000:])
    elif r.returncode:
        print((r.stdout or '')[-5000:], (r.stderr or '')[-5000:])
    return r.returncode


def auth(cfg):
    """После обновления ИБ у тестовой базы есть пользователи типовой — без
    /N Конфигуратор и клиент отвечают «Пользователь ИБ не идентифицирован».
    И наоборот: база БЕЗ пользователей (своя конфигурация, ФРЕГАТ EAM) на /N несуществующего
    отвечает тем же — там в platform.json "test_usr": "" (без /N /P)."""
    usr = cfg.get('test_usr', 'Администратор')
    return ['/N' + usr, '/P' + cfg.get('test_pwd', '')] if usr else []


def designer(cfg, ib, args, log):
    # Строкой, как client_cmd: со списком пустой пароль /P"" терял кавычки, и Конфигуратор
    # показывал окно авторизации даже с /DisableStartupDialogs — загрузка стояла, пока
    # пользователь не нажмёт «Войти».
    usr = cfg.get('test_usr', 'Администратор')
    cred = ' /N"%s" /P"%s"' % (usr, cfg.get('test_pwd', '')) if usr else ''
    cmd = '"%s" DESIGNER /F"%s"%s /DisableStartupDialogs /DisableStartupMessages %s /Out "%s"' % (
        cfg['v8'], ib, cred, ' '.join('"%s"' % a if ' ' in a else a for a in args), log)
    return step(args[0], cmd, log)


def stop_clients(ib):
    """Остановить клиентов ТОЛЬКО этой базы (по командной строке процесса)."""
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -like '1cv8*' -and $_.CommandLine -like '*%s*' }"
          " | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % ib)   # в -like обратный слэш не экранируется
    subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True)


# --------------------------------------------------------------- load / quick
def paths(cfg):
    w = cfg['work']
    return w, os.path.join(w, 'xml'), os.path.join(w, 'ib'), os.path.join(w, 'ws'), os.path.join(w, 'project')


def cmd_load(cfg):
    w, xml, ib, ws, prj = paths(cfg)
    rev = cfg['_args'][1] if len(cfg['_args']) > 1 else ''
    if os.path.exists(w):
        stop_clients(ib)
        shutil.rmtree(w)
    os.makedirs(w)
    if rev:   # ревизия git вместо рабочего каталога
        os.makedirs(prj)
        arch = subprocess.run(['git', '-C', cfg['project'], 'archive', rev], capture_output=True).stdout
        subprocess.run(['tar', '-x', '-C', prj], input=arch)
    else:
        shutil.copytree(cfg['project'], prj, ignore=shutil.ignore_patterns('.git'))
    # EDT CLI пишет в консоль в cp866; отдельное рабочее пространство, чтобы не мешать открытому EDT
    if step('выгрузка XML (EDT)', [cfg['edt_cli'], '-data', ws, '-command', 'export', '--project', prj,
                                   '--configuration-files', xml], enc='cp866'):
        return 1
    return create_and_load(cfg, xml, ib)


def create_and_load(cfg, xml, ib):
    w = cfg['work']
    step('создание базы', [cfg['v8'], 'CREATEINFOBASE', 'File=' + ib, '/DisableStartupDialogs'])
    if designer(cfg, ib, ['/LoadConfigFromFiles', xml], os.path.join(w, 'load.log')):
        return 2
    return 3 if designer(cfg, ib, ['/UpdateDBCfg'], os.path.join(w, 'update.log')) else 0


def xml_path(xml, rel):
    """src-путь модуля EDT → путь в выгрузке Конфигуратора."""
    p = rel.split(os.sep)
    if p[0] == 'Configuration':
        return os.path.join(xml, 'Ext', p[1])
    if len(p) == 3 and p[2].endswith('.bsl'):
        return os.path.join(xml, p[0], p[1], 'Ext', p[2])
    if len(p) == 5 and p[2] == 'Forms' and p[4] == 'Module.bsl':
        return os.path.join(xml, p[0], p[1], 'Forms', p[3], 'Ext', 'Form', 'Module.bsl')
    if len(p) == 5 and p[2] == 'Commands' and p[4] == 'CommandModule.bsl':
        return os.path.join(xml, p[0], p[1], 'Commands', p[3], 'Ext', 'CommandModule.bsl')
    if len(p) == 4 and p[0] == 'CommonForms' and p[3] == 'Module.bsl':
        return os.path.join(xml, 'CommonForms', p[1], 'Ext', 'Form', 'Module.bsl')
    return None


def cmd_quick(cfg):
    w, xml, ib, ws, prj = paths(cfg)
    src, copy = os.path.join(cfg['project'], 'src'), os.path.join(prj, 'src')
    if not os.path.isdir(xml) or not os.path.isdir(copy):
        sys.exit('Сначала полный load: нет XML-выгрузки или копии проекта в %s' % w)
    changed, other = 0, []
    for root, _d, files in os.walk(src):
        for f in files:
            s = os.path.join(root, f)
            rel = os.path.relpath(s, src)
            old = os.path.join(copy, rel)
            if os.path.exists(old) and filecmp.cmp(s, old, shallow=False):
                continue
            if not f.endswith('.bsl'):
                other.append(rel)
                continue
            dst = xml_path(xml, rel)
            if not dst or not os.path.exists(dst):
                other.append(rel)
                continue
            # выгрузка Конфигуратора хранит модули С BOM, проект EDT — без
            text = io.open(s, encoding='utf-8-sig', newline='').read()
            io.open(dst, 'w', encoding='utf-8-sig', newline='').write(text)
            shutil.copy2(s, old)
            changed += 1
    if other:
        print('менялось не только .bsl — нужен полный load:\n  ' + '\n  '.join(other[:20]))
        return 1
    print('перенесено модулей: %d' % changed)
    stop_clients(ib)
    if os.path.exists(ib):
        shutil.rmtree(ib)
    return create_and_load(cfg, xml, ib)


# --------------------------------------------------------------- update
LGP = re.compile(r'\{(\d{14}),\w,\s*\{[^}]*\},\d+,\d+,\d+,\d+,\d+,(\w),"((?:[^"]|"")*)"')


def journal_errors(ib):
    t = ''
    for lgp in sorted(glob.glob(os.path.join(ib, '1Cv8Log', '*.lgp'))):
        t += open(lgp, encoding='utf-8-sig', errors='replace').read()
    return [c.replace('""', '"') for _d, lvl, c in LGP.findall(t) if lvl == 'E' and 'заблокирована' not in c]


def cmd_update(cfg):
    ib = cfg['_args'][1] if len(cfg['_args']) > 1 else paths(cfg)[2]
    # 1) внешним соединением — быстрее и с полным текстом ошибки
    try:
        cn = connect(cfg, ib)
        t0 = time.time()
        r = cn.ОбновлениеИнформационнойБазы.ВыполнитьОбновлениеИнформационнойБазы()
        print('обновление ИБ (COM): %s, %.1f мин' % (r, (time.time() - t0) / 60))
        return 0
    except Exception as e:
        print('COM не справился, пробую клиентом: %s' % err_text(e)[:300])
    # 2) клиентом с параметром БСП; ошибки — из журнала регистрации
    t0 = time.time()
    proc = subprocess.Popen(client_cmd(cfg, ib, 'ЗапуститьОбновлениеИнформационнойБазы;ЗавершитьРаботуСистемы'))
    while proc.poll() is None:
        if any('При вызове обработчика обновления' in e for e in journal_errors(ib)):
            time.sleep(5)
            stop_clients(ib)   # иначе висит на окне «Не удалось выполнить обновление»
            break
        if time.time() - t0 > 1800:
            stop_clients(ib)
            print('таймаут')
            break
        time.sleep(3)
    errs = journal_errors(ib)
    print('обновление ИБ (клиент): %.1f мин, ошибок в журнале %d' % ((time.time() - t0) / 60, len(errs)))
    for e in errs[:10]:
        print('  ' + e[:1500])
    return 1 if errs else 0


# --------------------------------------------------------------- com
def connect(cfg, ib=None):
    """ib — путь к ТЕСТОВОЙ базе (после update у неё есть пользователи типовой:
    имя — cfg['test_usr'], по умолчанию «Администратор», без пароля); без ib —
    строка соединения cfg['ib'] как есть."""
    import win32com.client
    c = win32com.client.Dispatch(cfg.get('com', 'V83.COMConnector'))
    if ib and not ib.startswith(('File=', 'Srvr=')):
        usr = cfg.get('test_usr', 'Администратор')
        ib = ('File="%s";Usr="%s";Pwd="%s";' % (ib, usr, cfg.get('test_pwd', ''))) if usr else 'File="%s";' % ib
    return c.Connect(ib or cfg['ib'])


def client_cmd(cfg, ib, launch):
    """Командная строка тонкого клиента СТРОКОЙ, а не списком: пустой пароль платформа
    ждёт как /P"" — список subprocess экранирует кавычки, остаётся голое /P, и вместо
    входа открывается окно авторизации (пользователь жмёт «Войти» на каждом прогоне)."""
    usr = cfg.get('test_usr', 'Администратор')
    cred = ' /N"%s" /P"%s"' % (usr, cfg.get('test_pwd', '')) if usr else ''
    return '"%s" ENTERPRISE /F"%s"%s /DisableStartupDialogs /DisableStartupMessages /C "%s"' % (cfg['v8'], ib, cred, launch)


def err_text(e):
    try:
        import pythoncom
        if isinstance(e, pythoncom.com_error) and e.excepinfo and e.excepinfo[2]:
            return e.excepinfo[2]
    except ImportError:
        pass
    return ''.join(traceback.format_exception_only(type(e), e)).strip()


def own(cfg, name):
    p = cfg.get('prefix', '')
    return (not p) or name.startswith(p)


def com_counts(cfg, cn):
    for coll, kind in (('Справочники', 'Справочник'), ('Документы', 'Документ'), ('РегистрыСведений', 'РегистрСведений')):
        for m in cn.Метаданные.__getattr__(coll):
            if not own(cfg, m.Имя):
                continue
            q = cn.NewObject('Запрос', 'ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК К ИЗ %s.%s КАК Т' % (kind, m.Имя))
            print('%s.%s: %d' % (kind, m.Имя, q.Выполнить().Выгрузить().Получить(0).К))


def set_default_params(cn, settings):
    """Пустые параметры-даты и стандартные периоды варианта — последние 12 месяцев."""
    from datetime import datetime
    now = datetime.now()
    start = datetime(now.year - 1, now.month, 1)
    end = datetime(now.year + (now.month == 12), now.month % 12 + 1, 1)
    for p in settings.ПараметрыДанных.Элементы:
        name, v = str(p.Параметр), p.Значение
        if type(v).__name__ in ('datetime', 'Time'):
            if getattr(v, 'year', 1) <= 1:
                p.Значение = end if ('Конец' in name or name.endswith('По') or 'Окончан' in name) else start
                p.Использование = True
        else:
            try:
                d_end = v.ДатаОкончания
            except Exception:
                continue
            if d_end is None or getattr(d_end, 'year', 1) <= 1:
                p.Значение = cn.NewObject('СтандартныйПериод', start, end)
                p.Использование = True


def com_reports(cfg, cn, flt=''):
    ok = bad = 0
    for m in cn.Метаданные.Отчеты:
        n = m.Имя
        if not own(cfg, n) or (flt and flt not in n) or m.ОсновнаяСхемаКомпоновкиДанных is None:
            continue
        try:
            rep = cn.Отчеты.__getattr__(n).Создать()
            dcs = rep.ПолучитьМакет(m.ОсновнаяСхемаКомпоновкиДанных.Имя)
        except Exception as e:
            print('ОШИБКА %s: %s' % (n, err_text(e)))
            bad += 1
            continue
        for var in dcs.ВариантыНастроек:
            try:
                src = cn.NewObject('ИсточникДоступныхНастроекКомпоновкиДанных', dcs)
                rep.КомпоновщикНастроек.Инициализировать(src)
                rep.КомпоновщикНастроек.ЗагрузитьНастройки(var.Настройки)
                set_default_params(cn, rep.КомпоновщикНастроек.Настройки)
                td = cn.NewObject('ТабличныйДокумент')
                dd = cn.NewObject('ДанныеРасшифровкиКомпоновкиДанных')
                t0 = time.time()
                rep.СкомпоноватьРезультат(td, dd)
                print('ОК %s.%s: строк %d, %.1f с' % (n, var.Имя, td.ВысотаТаблицы, time.time() - t0))
                ok += 1
            except Exception as e:
                print('ОШИБКА %s.%s:\n%s' % (n, var.Имя, err_text(e)))
                bad += 1
    print('отчёты: ОК %d, ошибок %d' % (ok, bad))
    return bad == 0


def com_query(cn, text):
    q = cn.NewObject('Запрос', text)
    t = q.Выполнить().Выгрузить()
    cols = [t.Колонки.Получить(i).Имя for i in range(t.Колонки.Количество())]
    print(' | '.join(cols))
    for i in range(min(t.Количество(), 50)):
        row = t.Получить(i)
        print(' | '.join(str(row.__getattr__(c)) for c in cols))
    print('строк: %d' % t.Количество())


def com_fill(cfg, cn, limit=100.0):
    """Доля пустых значений каждого реквизита своих справочников и документов (шапка и ТЧ) по ВСЕЙ
    таблице: запрос считает заполненные значения на стороне базы (выборка «первые N» обманывает —
    заполненное часто только у части строк). Печатает реквизиты с долей пустых >= limit %."""
    prefixes = tuple(cfg.get('fill_prefixes') or [cfg.get('prefix', '')])
    skip = {'Ссылка', 'ПометкаУдаления', 'Предопределенный', 'ИмяПредопределенныхДанных', 'ВерсияДанных',
            'НомерСтроки', 'Проведен', 'Родитель', 'Владелец', 'ЭтоГруппа', 'Код', 'Номер', 'Дата', 'Наименование'}
    q = cn.NewObject('Запрос')
    found = 0
    for coll, ru in ((cn.Метаданные.Справочники, 'Справочник'), (cn.Метаданные.Документы, 'Документ')):
        for i in range(coll.Количество()):
            md = coll.Получить(i)
            if not md.Имя.startswith(prefixes):
                continue
            tables = [(ru + '.' + md.Имя, md.Реквизиты, md.Имя)]
            for j in range(md.ТабличныеЧасти.Количество()):
                ts = md.ТабличныеЧасти.Получить(j)
                tables.append((ru + '.' + md.Имя + '.' + ts.Имя, ts.Реквизиты, md.Имя + '.' + ts.Имя))
            for table, attrs, title in tables:
                # выражение «заполнено» — по типу реквизита из метаданных: язык запросов проверяет типы
                # статически, одно выражение на все типы (ТИПЗНАЧЕНИЯ + ВЫРАЗИТЬ) не компилируется
                names, cols = [], []
                for k in range(attrs.Количество()):
                    at = attrs.Получить(k)
                    if at.Имя in skip:
                        continue
                    kinds = []
                    for j in range(at.Тип.Типы().Количество()):
                        x = cn.XMLТип(at.Тип.Типы().Получить(j))
                        kinds.append(x.ИмяТипа if x is not None else '?')
                    n = at.Имя
                    if kinds == ['string']:
                        cond = 'ВЫРАЗИТЬ(Т.%s КАК СТРОКА(10)) <> ""' % n
                    elif kinds == ['decimal']:
                        cond = 'Т.%s <> 0' % n
                    elif kinds == ['dateTime']:
                        cond = 'Т.%s <> ДАТАВРЕМЯ(1, 1, 1)' % n
                    elif kinds and all('Ref.' in x for x in kinds):
                        cond = 'НЕ Т.%s.Ссылка ЕСТЬ NULL' % n   # пустая ссылка не разыменовывается — NULL
                    else:
                        continue   # булево, хранилище значения, составной с примитивами — «пусто» не определено
                    names.append(n)
                    cols.append('СУММА(ВЫБОР КОГДА %s ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Р%d' % (cond, len(cols)))
                if not names:
                    continue
                q.Текст = 'ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Всего, ' + ', '.join(cols) + ' ИЗ ' + table + ' КАК Т'
                filled_by = {}
                try:
                    s = q.Выполнить().Выбрать()
                    s.Следующий()
                    total = s.Всего or 0
                    for k in range(len(names)):
                        filled_by[k] = getattr(s, 'Р%d' % k) or 0
                except Exception:
                    # реквизит, недопустимый в запросе (ХранилищеЗначения и т.п.), — считаем по одному, его пропускаем
                    total = None
                    for k, col in enumerate(cols):
                        q.Текст = 'ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Всего, ' + col.replace(' КАК Р%d' % k, ' КАК Р0') + ' ИЗ ' + table + ' КАК Т'
                        try:
                            s = q.Выполнить().Выбрать()
                            s.Следующий()
                            total = s.Всего or 0
                            filled_by[k] = s.Р0 or 0
                        except Exception:
                            pass
                if not total:
                    continue
                shown = False
                for k, n in enumerate(names):
                    if k not in filled_by:
                        continue
                    filled = filled_by[k]
                    pct = round((total - filled) * 100.0 / total, 1)
                    if pct >= limit:
                        if not shown:
                            print('%s (%d)' % (title, total))
                            shown = True
                        print('   %-42s пусто %5.1f%%' % (n, pct))
                        found += 1
    print('реквизитов с долей пустых >= %s%%: %d' % (limit, found))
    return 0


def cmd_com(cfg):
    a = cfg['_args']
    sub = a[1] if len(a) > 1 else 'counts'
    cn = connect(cfg)
    print('соединение: ок (%s)' % cfg['ib'])
    if sub == 'counts':
        com_counts(cfg, cn)
    elif sub == 'reports':
        return 0 if com_reports(cfg, cn, a[2] if len(a) > 2 else '') else 1
    elif sub == 'query':
        com_query(cn, a[2])
    elif sub == 'fill':
        return com_fill(cfg, cn, float(a[2]) if len(a) > 2 else 100.0)
    elif sub == 'call':
        mod, fn = a[2].split('.')
        try:
            print(getattr(getattr(cn, mod), fn)(*a[3:]))
        except Exception as e:
            print('ОШИБКА: ' + err_text(e))
            return 1
    return 0


# --------------------------------------------------------------- screens
МЕТКА = '// ТЕСТ-СКРИНШОТЫ'
SHOT_PS = r'''
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Collections.Generic; using System.Runtime.InteropServices;
public class W {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc p, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  public struct R { public int L, T, Rr, B; }
  public static List<IntPtr> Of(uint pid) {
    var res = new List<IntPtr>();
    EnumWindows((h, l) => { uint q; GetWindowThreadProcessId(h, out q); if (q == pid && IsWindowVisible(h)) res.Add(h); return true; }, IntPtr.Zero);
    return res; }
}
"@
# масштаб экрана не 100%: без DPI-awareness GetWindowRect отдаёт логические размеры, а PrintWindow рисует
# физические — снимок обрезан справа и снизу (ФРЕГАТ EAM, экран 125–150 %)
[W]::SetProcessDPIAware() | Out-Null
$c = Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq '1cv8c.exe' -or $_.Name -eq '1cv8.exe') -and $_.CommandLine -like '*%s*' -and $_.CommandLine -like '*ENTERPRISE*' }
if (-not $c) { exit 1 }
$pid1 = ($c | Select-Object -First 1).ProcessId
# окно в фокусе, если оно этого клиента (формы элементов открываются отдельными окнами и получают фокус);
# иначе — самое большое видимое окно процесса (уведомления платформы маленькие)
$fg = [W]::GetForegroundWindow(); $fgpid = [uint32]0; [W]::GetWindowThreadProcessId($fg, [ref]$fgpid) | Out-Null
$h = [IntPtr]::Zero
if ($fgpid -eq $pid1) { $h = $fg } else {
  $best = 0
  foreach ($w in [W]::Of([uint32]$pid1)) { $r = New-Object W+R; [W]::GetWindowRect($w, [ref]$r) | Out-Null
    $a = ($r.Rr - $r.L) * ($r.B - $r.T); if ($a -gt $best) { $best = $a; $h = $w } }
}
if ($h -eq [IntPtr]::Zero) { exit 1 }
$r = New-Object W+R; [W]::GetWindowRect($h, [ref]$r) | Out-Null
$w = $r.Rr - $r.L; $hh = $r.B - $r.T
if ($w -lt 50 -or $hh -lt 50) { exit 1 }
$bmp = New-Object System.Drawing.Bitmap $w, $hh
$g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
[W]::PrintWindow($h, $dc, 2) | Out-Null
$g.ReleaseHdc($dc); $bmp.Save('%s'); $g.Dispose(); $bmp.Dispose()
'''


def patch_xml_module(xml, rel, anchor, add):
    p = os.path.join(xml, rel)
    t = io.open(p, encoding='utf-8-sig', newline='').read()
    t = re.sub(re.escape(МЕТКА) + r' begin.*?' + re.escape(МЕТКА) + r' end\r?\n', '', t, flags=re.S)
    block = МЕТКА + ' begin\r\n' + add.replace('\n', '\r\n') + '\r\n' + МЕТКА + ' end\r\n'
    if anchor is None:
        t = t.rstrip() + '\r\n\r\n' + block
    else:
        i = t.index(anchor) + len(anchor)
        t = t[:i] + block + t[i:]
    io.open(p, 'w', encoding='utf-8-sig', newline='').write(t)


def form_names(xml, masks):
    names = ['НАЧАЛЬНАЯ']
    kinds = {'Documents': 'Документ', 'Catalogs': 'Справочник', 'DataProcessors': 'Обработка', 'Reports': 'Отчет'}
    for folder, ru in kinds.items():
        for f in sorted(glob.glob(os.path.join(xml, folder, '*', 'Forms', '*.xml'))):
            obj = os.path.basename(os.path.dirname(os.path.dirname(f)))
            full = '%s.%s.Форма.%s' % (ru, obj, os.path.splitext(os.path.basename(f))[0])
            if any(re.fullmatch(m.replace('.', r'\.').replace('*', '.*'), full) for m in masks):
                names.append(full)
    return names


def cmd_screens(cfg):
    w, xml, ib, ws, prj = paths(cfg)
    sc = cfg.get('screens', {})
    a = cfg['_args']
    stepsec = int(a[1]) if len(a) > 1 else 6
    masks = a[2:] or sc.get('default_masks', ['Обработка.%s*.Форма.*' % cfg.get('prefix', '')])
    if not os.path.isdir(xml):
        sys.exit('Сначала load: нет XML-выгрузки в %s' % w)
    names = form_names(xml, masks)
    print('форм к показу: %d' % (len(names) - 1))
    srv, glob_cl, after = sc['server_call_module'], sc['global_client_module'], sc['after_start_module']
    cm = lambda name: os.path.join('CommonModules', name, 'Ext', 'Module.bsl')
    # состояние обхода — на сервере: у глобального клиентского модуля нет своих переменных между вызовами
    patch_xml_module(xml, cm(srv), None, '''
Процедура ТестНачатьСкриншоты(Список) Экспорт
	ХранилищеОбщихНастроек.Сохранить("ТестСкриншоты", "Имена", СтрРазделить(Список, ";"));
	ХранилищеОбщихНастроек.Сохранить("ТестСкриншоты", "Индекс", 0);
КонецПроцедуры

Функция ТестСледующаяФорма() Экспорт
	Имена = ХранилищеОбщихНастроек.Загрузить("ТестСкриншоты", "Имена");
	Индекс = ХранилищеОбщихНастроек.Загрузить("ТестСкриншоты", "Индекс");
	Если Имена = Неопределено Или Индекс = Неопределено Или Индекс >= Имена.Количество() Тогда
		Возврат "";
	КонецЕсли;
	ХранилищеОбщихНастроек.Сохранить("ТестСкриншоты", "Индекс", Индекс + 1);
	Возврат Имена[Индекс];
КонецФункции
''')
    patch_xml_module(xml, cm(glob_cl), None, '''
Процедура ТестСкриншотСледующаяФорма() Экспорт
	Имя = %s.ТестСледующаяФорма();
	Если Имя = "" Тогда
		ОтключитьОбработчикОжидания("ТестСкриншотСледующаяФорма");
		ЗавершитьРаботуСистемы(Ложь);
		Возврат;
	КонецЕсли;
	Если Имя <> "НАЧАЛЬНАЯ" Тогда
		Попытка
			ОткрытьФорму(Имя);
		Исключение
		КонецПопытки;
	КонецЕсли;
КонецПроцедуры
''' % srv)
    patch_xml_module(xml, cm(after), 'Процедура ПослеНачалаРаботыСистемы() Экспорт\r\n', '''	Если СтрНайти(ПараметрЗапуска, "СкриншотыФорм") > 0 Тогда
		%s.ТестНачатьСкриншоты("%s");
		ПодключитьОбработчикОжидания("ТестСкриншотСледующаяФорма", %d);
		Возврат;
	КонецЕсли;''' % (srv, ';'.join(names), stepsec * 2))
    stop_clients(ib)
    # Полная загрузка типовой — десять минут; после load с -updateConfigDumpInfo
    # Конфигуратор умеет грузить ТОЛЬКО перечисленные файлы (-files).
    if os.path.exists(os.path.join(xml, 'ConfigDumpInfo.xml')):
        files = ','.join(os.path.join(xml, cm(m)) for m in (srv, glob_cl, after))
        load_args = ['/LoadConfigFromFiles', xml, '-files', files, '-updateConfigDumpInfo']
    else:
        load_args = ['/LoadConfigFromFiles', xml, '-updateConfigDumpInfo']
    if designer(cfg, ib, load_args, os.path.join(w, 's1.log')) or \
       designer(cfg, ib, ['/UpdateDBCfg'], os.path.join(w, 's2.log')):
        return 1
    out = os.path.join(w, 'screens')
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, '*.png')):
        os.remove(f)
    # Индекс прошлого прогона лежит в хранилище — сбросить ДО запуска клиента,
    # иначе скрипт примет его за свежий и «снимет» последнюю форму сразу.
    cn = connect(cfg, ib)
    cn.ХранилищеОбщихНастроек.Сохранить('ТестСкриншоты', 'Индекс', -1)
    # Клиент запускать с явным SW_SHOWNORMAL: если сам скрипт стартовал из
    # скрытого окна (Start-Process -WindowStyle Hidden), дочерний 1cv8
    # наследует «скрытость», и окна для PrintWindow не будет.
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 1   # SW_SHOWNORMAL
    subprocess.Popen(client_cmd(cfg, ib, 'СкриншотыФорм'), startupinfo=si)
    done, t_last = -1, time.time()
    ib_ps = ib   # в PowerShell -like обратный слэш — обычный символ, удвоение ломало поиск окна
    while time.time() - t_last < 180:
        try:
            idx = cn.ХранилищеОбщихНастроек.Загрузить('ТестСкриншоты', 'Индекс')
        except Exception:
            idx = None
        if idx is not None and int(idx) - 1 >= len(names):
            idx = None          # индекс прошлого прогона — клиент ещё не сбросил
        if idx is not None and int(idx) - 1 > done:
            k = int(idx) - 1
            time.sleep(stepsec)
            path = os.path.join(out, '%02d_%s.png' % (k, re.sub(r'[\\/:*?"<>|]', '_', names[k])[:120]))
            subprocess.run(['powershell', '-NoProfile', '-Command', SHOT_PS % (ib_ps, path.replace("'", "''"))],
                           capture_output=True)
            print('снимок:', os.path.basename(path) if os.path.exists(path) else '(нет окна) ' + names[k])
            done, t_last = k, time.time()
            if k >= len(names) - 1:
                break
        elif time.time() - t_last > 60 and not os.path.exists(os.path.join(out, 'stall_%02d.png' % (done + 1))):
            stall = os.path.join(out, 'stall_%02d.png' % (done + 1))   # что блокирует: диалог, вопрос, ошибка
            subprocess.run(['powershell', '-NoProfile', '-Command', SHOT_PS % (ib_ps, stall.replace("'", "''"))],
                           capture_output=True)
            print('зависание после', names[done] if done >= 0 else '-', '→', os.path.basename(stall))
        time.sleep(1)
    time.sleep(stepsec + 5)
    stop_clients(ib)
    print('готово:', out)
    return 0


def cmd_forms(cfg):
    """Все свои формы — ПолучитьФорму в клиенте (без показа): падения ПриСозданииНаСервере / ПриОткрытии
    видны только так (внешнему соединению формы недоступны). В XML-КОПИЮ добавляются две вставки (серверный
    модуль — список форм и запись итога в ХранилищеОбщихНастроек, переопределяемый БСП — обход по /C
    ПроверкаФорм), клиент завершается сам. Формы, которым нужен контекст (параметры, ключ, владелец), падают
    ожидаемо — их список сверять с прошлым прогоном, а не чинить «вслепую»."""
    w, xml, ib, ws, prj = paths(cfg)
    sc = cfg.get('screens', {})
    a = cfg['_args']
    prefixes = a[1:] or cfg.get('fill_prefixes') or [cfg.get('prefix', '')]
    if not os.path.isdir(xml):
        sys.exit('Сначала load: нет XML-выгрузки в %s' % w)
    srv, after = sc['server_call_module'], sc['after_start_module']
    cm = lambda name: os.path.join('CommonModules', name, 'Ext', 'Module.bsl')
    patch_xml_module(xml, cm(srv), None, '''
Функция ТестИменаФорм(Префиксы) Экспорт
	Имена = Новый Массив;
	Виды = Новый Структура("Справочник, Документ, РегистрСведений, РегистрНакопления, ПланВидовХарактеристик, Отчет, Обработка",
		Метаданные.Справочники, Метаданные.Документы, Метаданные.РегистрыСведений, Метаданные.РегистрыНакопления,
		Метаданные.ПланыВидовХарактеристик, Метаданные.Отчеты, Метаданные.Обработки);
	Для Каждого Вид Из Виды Цикл
		Для Каждого М Из Вид.Значение Цикл
			Свой = Ложь;
			Для Каждого П Из СтрРазделить(Префиксы, ",") Цикл
				Свой = Свой Или СтрНачинаетсяС(М.Имя, П);
			КонецЦикла;
			Если Свой Тогда
				Для Каждого Ф Из М.Формы Цикл
					Имена.Добавить(Вид.Ключ + "." + М.Имя + ".Форма." + Ф.Имя);
				КонецЦикла;
			КонецЕсли;
		КонецЦикла;
	КонецЦикла;
	Возврат Имена;
КонецФункции

Процедура ТестЗаписатьФормы(Текст) Экспорт
	ХранилищеОбщихНастроек.Сохранить("ТестФормы", "Итог", Текст);
КонецПроцедуры
''')
    patch_xml_module(xml, cm(after), 'Процедура ПослеНачалаРаботыСистемы() Экспорт\r\n', '''	Если СтрНайти(ПараметрЗапуска, "ПроверкаФорм") > 0 Тогда
		ОшибкиФорм = Новый Массив;
		ИменаФорм = %s.ТестИменаФорм("%s");
		Для Каждого ИмяФормы Из ИменаФорм Цикл
			Попытка
				ПолучитьФорму(ИмяФормы, , , Новый УникальныйИдентификатор);
			Исключение
				ОшибкиФорм.Добавить(ИмяФормы + ": " + КраткоеПредставлениеОшибки(ИнформацияОбОшибке()));
			КонецПопытки;
		КонецЦикла;
		%s.ТестЗаписатьФормы("ФОРМЫ: проверено " + ИменаФорм.Количество() + ", ошибок " + ОшибкиФорм.Количество()
			+ Символы.ПС + СтрСоединить(ОшибкиФорм, Символы.ПС));
		ЗавершитьРаботуСистемы(Ложь);
		Возврат;
	КонецЕсли;''' % (srv, ','.join(prefixes), srv))
    stop_clients(ib)
    if os.path.exists(os.path.join(xml, 'ConfigDumpInfo.xml')):
        files = ','.join(os.path.join(xml, cm(m)) for m in (srv, after))
        load_args = ['/LoadConfigFromFiles', xml, '-files', files, '-updateConfigDumpInfo']
    else:
        load_args = ['/LoadConfigFromFiles', xml, '-updateConfigDumpInfo']
    if designer(cfg, ib, load_args, os.path.join(w, 'f1.log')) or \
       designer(cfg, ib, ['/UpdateDBCfg'], os.path.join(w, 'f2.log')):
        return 1
    cn = connect(cfg, ib)
    cn.ХранилищеОбщихНастроек.Удалить('ТестФормы', 'Итог', '')
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 1
    subprocess.Popen(client_cmd(cfg, ib, 'ПроверкаФорм'), startupinfo=si)
    итог, t0 = None, time.time()
    while time.time() - t0 < 900:
        time.sleep(3)
        try:
            итог = cn.ХранилищеОбщихНастроек.Загрузить('ТестФормы', 'Итог')
        except Exception:
            итог = None
        if итог:
            break
    time.sleep(3)
    stop_clients(ib)
    if not итог:
        print('итога нет: клиент не дошёл до проверки (диалог при запуске?) — снимите screens')
        return 1
    print(итог)
    return 0


def main():
    cfg = load_cfg()
    cmd = cfg['_args'][0] if cfg['_args'] else ''
    fn = {'load': cmd_load, 'quick': cmd_quick, 'update': cmd_update, 'com': cmd_com, 'screens': cmd_screens, 'forms': cmd_forms}.get(cmd)
    if not fn:
        sys.exit(__doc__)
    sys.exit(fn(cfg) or 0)


if __name__ == '__main__':
    main()
