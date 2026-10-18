# -*- coding: utf-8 -*-
"""Настоящие нажатия в тонком клиенте без вставок в конфигурацию (уровень 9, case 085/092).

Менеджер тестирования — внешняя обработка `reference/testing-ui/ТестUIМенеджер` (собирается в .epf на той же базе,
пересобирается, только если XML новее .epf): клиент `/TESTCLIENT -TPort <порт>` + клиент `/TESTMANAGER /Execute
<epf> /C "<сценарий>;<журнал>;<порт>"`. Сценарий — строки «шаг | арг1 | арг2 | арг3», `#` — комментарий, `?шаг` —
необязательный. Шаги и их аргументы — knowledge/testing.md §9 (таблицы). В журнале у каждого шага — `[N мс]`.

  python tools/ui_test.py <сценарий.txt> --ib <папка файловой базы> [--user Имя] [--cred учётка.json]
         [--v8 "C:/Program Files/1cv8/8.5.1.1529/bin"] [--work <папка>] [--port 48133] [--printwindow]

--cred — JSON {"пользователь": "...", "пароль": "..."} (пароль в командную строку не писать); --work — сборка
менеджера, журнал, снимки (по умолчанию `<сценарий>_ui/`). Снимки шагов «снимок | имя» — <work>/ui_<имя>.png.
Код возврата: 0 — все шаги ОК, 1 — ошибка шага, 2 — менеджер не отработал (диалог на старте — смотреть ui_итог.png).

Скорость (case 092): весь сценарий — один клиент, ожидание = 40 с × шагов (минимум 300); шаги ждут смены окна, а не
фиксированных пауз; снимок — копией экрана (tools/ui_capture.py), окно вперёд не выводится; нет экрана или окно
перекрыто — снимок пропускается и попадает в итоговую сводку. --printwindow — снимать любой ценой (тормозит клиент).
Закрываются только клиенты ЭТОЙ базы (по пути в командной строке процесса).
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import designer_lib as dl  # noqa: E402
import ui_capture  # noqa: E402

НАБОР = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
МЕНЕДЖЕР = os.path.join(НАБОР, 'reference', 'testing-ui', 'ТестUIМенеджер')
СЕКУНД_НА_ШАГ = 40


def close_clients(ib):
    """Закрыть только 1cv8c/1cv8 этой базы (по пути в командной строке) — чужие окна не трогать."""
    метка = ib.rstrip('\\/').replace("'", "''")
    ps = ("Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq '1cv8c.exe' -or $_.Name -eq '1cv8.exe') "
          "-and $_.CommandLine -like '*%s*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; $_.ProcessId }"
          % метка)
    r = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True)
    if r.stdout.strip():
        print('закрыты процессы:', ' '.join(r.stdout.split()))


def manager_outdated(epf, src=МЕНЕДЖЕР):
    if not os.path.exists(epf):
        return True
    t = os.path.getmtime(epf)
    return any(os.path.getmtime(os.path.join(к, и)) > t for к, _, имена in os.walk(src) for и in имена)


def steps(scenario):
    with io.open(scenario, encoding='utf-8-sig') as f:
        return sum(1 for с in f if с.strip() and not с.lstrip().startswith('#'))


def run(scenario, ib, v8, user='', pwd='', work=None, port=48133, printwindow=False, manager=МЕНЕДЖЕР):
    scenario = os.path.abspath(scenario)
    work = work or os.path.splitext(scenario)[0] + '_ui'
    os.makedirs(work, exist_ok=True)
    v8c, v8d = os.path.join(v8, '1cv8c.exe'), os.path.join(v8, '1cv8.exe')
    т = time.time()
    close_clients(ib)
    epf = os.path.join(work, 'ТестUIМенеджер.epf')
    if manager_outdated(epf, manager):
        код, текст, _ = dl.build_epf(v8d, ib, os.path.join(manager, 'ТестUIМенеджер.xml'), epf,
                                     os.path.join(work, 'сборка_менеджера.log'), user=user, pwd=pwd)
        if код:
            sys.exit('менеджер не собран:\n' + текст)
    print('[замер] подготовка: %.1f с' % (time.time() - т))
    журнал = os.path.join(work, 'ui_журнал.txt')
    запрос = журнал + '.снимок'
    for ф in (журнал, запрос):
        if os.path.exists(ф):
            os.remove(ф)
    cred = ' /N"%s" /P"%s"' % (user, pwd) if user else ''
    база = '"%s" ENTERPRISE /F"%s"%s /DisableStartupMessages' % (v8c, ib, cred)
    ожидание = max(300, СЕКУНД_НА_ШАГ * steps(scenario))
    клиент = subprocess.Popen(база + ' /TESTCLIENT -TPort %d' % port)
    time.sleep(3)
    subprocess.Popen(база + ' /TESTMANAGER /Execute "%s" /C "%s;%s;%d"' % (epf, scenario, журнал, port))
    t0, не_снято, экран = time.time(), [], True

    def снять(имя):
        nonlocal экран
        путь = os.path.join(work, 'ui_%s.png' % имя)
        ок, причина = ui_capture.grab(клиент.pid, путь, retries=6 if экран else 1, printwindow=printwindow)
        экран = ок                          # после неудачи — одна попытка на снимок, пока экран не вернётся
        if not ок:
            не_снято.append((имя, причина))
        return путь if ок else '— НЕ СНЯТ (%s)' % причина

    while not os.path.exists(журнал) and time.time() - t0 < ожидание:
        if os.path.exists(запрос):
            т_сн = time.time()
            time.sleep(0.1)                 # дорисовка (шаг уже дождался смены окна)
            with io.open(запрос, encoding='utf-8-sig') as f:
                имя = f.read().strip() or 'снимок'
            print('снимок', снять(имя), '[%.1f с]' % (time.time() - т_сн))
            os.remove(запрос)               # менеджер ждёт удаления файла запроса
        time.sleep(0.05)
    time.sleep(1)
    снять('итог')
    if не_снято and не_снято[-1][0] == 'итог':
        # после последнего шага клиенту тормозить уже нечего — итоговый кадр можно снять PrintWindow (case 095)
        ок, _ = ui_capture.grab(клиент.pid, os.path.join(work, 'ui_итог.png'), printwindow=True)
        if ок:
            не_снято.pop()
    close_clients(ib)
    if не_снято:
        print('\nНЕ СНЯТО снимков: %d (%s). Снимки — копией экрана: окно удалённого рабочего стола открыто, окно 1С '
              'не перекрыто; либо --printwindow (медленно).' % (len(не_снято), не_снято[0][1]))
    if not os.path.exists(журнал):
        print('журнала нет: менеджер не отработал за %d с (диалог на старте? — ui_итог.png)' % ожидание)
        return 2
    with io.open(журнал, encoding='utf-8-sig') as f:
        текст = f.read()
    print(текст)
    print('\n%.0f с' % (time.time() - t0))
    return 1 if 'ОШИБКА' in текст else 0


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('scenario')
    a.add_argument('--ib', required=True)
    a.add_argument('--v8', default=r'C:\Program Files\1cv8\8.5.1.1529\bin')
    a.add_argument('--user', default='')
    a.add_argument('--cred')
    a.add_argument('--work')
    a.add_argument('--port', type=int, default=48133)
    a.add_argument('--printwindow', action='store_true')
    о = a.parse_args()
    user, pwd = о.user, ''
    if о.cred:
        with io.open(о.cred, encoding='utf-8-sig') as f:
            у = json.load(f)
        user, pwd = у.get('пользователь', user), у.get('пароль', '')
    sys.exit(run(о.scenario, о.ib, о.v8, user, pwd, о.work, о.port, о.printwindow))


if __name__ == '__main__':
    main()
