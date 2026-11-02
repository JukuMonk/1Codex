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
Закрываются только процессы, созданные текущим запуском. Артефакты — ui-runs/<run_id>; итог — ui-last.json.
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
import socket
import tempfile
from pathlib import Path
from contextlib import ExitStack
from workflow.ui_session import ProjectLock, RunArtifacts, stop_owned
from workflow.resource_lock import base_lease

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import designer_lib as dl  # noqa: E402

НАБОР = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
МЕНЕДЖЕР = os.path.join(НАБОР, 'reference', 'testing-ui', 'ТестUIМенеджер')
СЕКУНД_НА_ШАГ = 40


def close_clients(ib):
    """Deprecated: path-based process termination is forbidden."""
    raise RuntimeError('Use stop_owned(Popen handles); never terminate clients by database path')


def port_available(port):
    if not 1 <= port <= 65535: raise ValueError('Invalid UI port')
    with socket.socket() as probe:
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(('127.0.0.1', port))


def capture(*args, **kwargs):
    import ui_capture
    return ui_capture.grab(*args, **kwargs)


def manager_outdated(epf, src=МЕНЕДЖЕР):
    if not os.path.exists(epf):
        return True
    t = os.path.getmtime(epf)
    return any(os.path.getmtime(os.path.join(к, и)) > t for к, _, имена in os.walk(src) for и in имена)


def steps(scenario):
    with io.open(scenario, encoding='utf-8-sig') as f:
        return sum(1 for с in f if с.strip() and not с.lstrip().startswith('#'))


def run(scenario, ib, v8, user='', pwd='', work=None, port=48133, printwindow=False, manager=МЕНЕДЖЕР):
    scenario = str(Path(scenario).resolve())
    if not Path(scenario).is_file() or steps(scenario) == 0:
        raise ValueError('Scenario is absent or empty')
    work = Path(work or os.path.splitext(scenario)[0] + '_ui').resolve()
    owned, artifacts = [], None
    began = time.monotonic()
    result = 2
    with ExitStack() as locks:
        locks.enter_context(ProjectLock(work))
        locks.enter_context(ProjectLock(Path(tempfile.gettempdir())/'1codex-ui-ports'/str(port)))
        locks.enter_context(base_lease(work, ib))
        port_available(port)
        artifacts = RunArtifacts(work, str(Path(ib).resolve()), port, 'functional')
        v8c, v8d = str(Path(v8)/'1cv8c.exe'), str(Path(v8)/'1cv8.exe')
        try:
            epf = work/'ТестUIМенеджер.epf'
            if manager_outdated(str(epf), manager):
                pending = artifacts.root/'ТестUIМенеджер.epf'
                code, log, _ = dl.build_epf(v8d, ib, str(Path(manager)/'ТестUIМенеджер.xml'), str(pending),
                    str(artifacts.root/'build.log'), user=user, pwd=pwd)
                if code or not pending.is_file() or re.search(r'\b(?:Ошибка|Error|Exception|Исключение)(?=\s|:|\()', log, re.I):
                    raise RuntimeError('Test manager build failed; see build.log')
                os.replace(pending, epf)
            cred = ' /N"%s" /P"%s"' % (user, pwd) if user else ''
            command = '"%s" ENTERPRISE /F"%s"%s /DisableStartupMessages' % (v8c, ib, cred)
            client = subprocess.Popen(command + ' /TESTCLIENT -TPort %d' % port)
            owned.append(client)
            time.sleep(3)
            manager_process = subprocess.Popen(command + ' /TESTMANAGER /Execute "%s" /C "%s;%s;%d"' %
                (epf, scenario, artifacts.journal, port))
            owned.append(manager_process)
            artifacts.manifest['owned_pids'] = [p.pid for p in owned]
            artifacts.save()
            until = time.monotonic() + max(300, СЕКУНД_НА_ШАГ * steps(scenario))
            def shot(name):
                target = artifacts.frame(name)  # validates traversal and reserved Windows names
                ok, reason = capture(client.pid, str(target), printwindow=printwindow)
                if ok: artifacts.manifest['frames'].append(name)
                else: artifacts.manifest.setdefault('missed_frames', []).append({'name': name, 'reason': reason})
                return ok
            while not artifacts.journal.exists() and time.monotonic() < until:
                if artifacts.request.exists():
                    name = artifacts.request.read_text(encoding='utf-8-sig').strip() or 'снимок'
                    time.sleep(0.1)
                    shot(name)
                    artifacts.request.unlink()
                if client.poll() is not None or manager_process.poll() is not None:
                    break
                time.sleep(0.05)
            time.sleep(0.3)
            shot('итог')
            if artifacts.journal.is_file():
                log = artifacts.journal.read_text(encoding='utf-8-sig')
                result = 1 if 'ОШИБКА' in log else (0 if log.strip() else 2)
                print(log)
            return result
        finally:
            stop_owned(owned)
            artifacts.manifest.update(status='succeeded' if result == 0 else 'failed', exit_code=result,
                elapsed_seconds=round(time.monotonic()-began, 6))
            artifacts.save()
            artifacts.publish()
            print('UI artifacts:', artifacts.root)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('scenario')
    a.add_argument('--ib', required=True)
    a.add_argument('--v8', required=True, help='Каталог bin выбранной платформы')
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
