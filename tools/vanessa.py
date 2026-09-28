# -*- coding: utf-8 -*-
"""vanessa — прогон сценариев Vanessa Automation (Gherkin, .feature) в ТЕСТОВОЙ базе platform.py.

  python tools/vanessa.py <platform.json> <каталог или файл .feature> [тег]

Берёт из platform.json: v8, work (тестовая база — после platform.py load/update), test_usr/test_pwd,
va_epf — путь к vanessa-automation-single.epf (скачивается с github.com/Pr-Mex/vanessa-automation, релиз
«single»; в проект не кладётся). Собирает VAParams.json (плоский формат, ключи — как в tools/JSON
репозитория VA), запускает менеджер тестирования:
  1cv8 ENTERPRISE /F<база> /TESTMANAGER /Execute <epf> /C"StartFeaturePlayer;VAParams=<json>"
Vanessa сама стартует тестируемый клиент (первый шаг сценария — «Дано Я открыл новый сеанс TestClient или
подключил уже существующий»). Итог — JUnit (сценарии/ошибки), лог ошибок, снимки при ошибке — в <work>/va_out.
Код возврата: 0 — все сценарии прошли. Подробно — knowledge/testing.md §9, кейс 072.
"""
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cfg = json.load(io.open(sys.argv[1], encoding='utf-8-sig'))
    features = os.path.abspath(sys.argv[2])
    tag = sys.argv[3] if len(sys.argv) > 3 else ''
    epf = cfg.get('va_epf')
    if not epf or not os.path.exists(epf):
        sys.exit('В platform.json нет va_epf (путь к vanessa-automation-single.epf) или файла нет: %s' % epf)
    w = cfg['work']
    ib = os.path.join(w, 'ib')
    out = os.path.join(w, 'va_out')
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    usr = cfg.get('test_usr', 'Администратор')
    cred = ' /N"%s" /P"%s"' % (usr, cfg.get('test_pwd', '')) if usr else ''
    root = features if os.path.isdir(features) else os.path.dirname(features)
    params = {
        "КаталогФич": features,
        "КаталогОтносительноКоторогоНадоСтроитьИерархию": root,
        "ВыполнитьСценарии": "Истина",
        "ЗавершитьРаботуСистемы": "Истина",
        "ЗакрытьTestClientПослеЗапускаСценариев": "Истина",
        "ДелатьОтчетВФорматеjUnit": "Истина",
        "КаталогOutputjUnit": os.path.join(out, 'junit'),
        "ДелатьЛогВыполненияСценариевВТекстовыйФайл": "Истина",
        "ВыводитьВЛогВыполнениеШагов": "Истина",
        "ИмяФайлаЛогВыполненияСценариев": os.path.join(out, 'log.txt'),
        "ВыгружатьСтатусВыполненияСценариевВФайл": "Истина",
        "ПутьКФайлуДляВыгрузкиСтатусаВыполненияСценариев": os.path.join(out, 'status.log'),
        "ДелатьСкриншотПриВозникновенииОшибки": "Истина",
        "КаталогВыгрузкиСкриншотов": os.path.join(out, 'screens'),
        "СобиратьДанныеОСостоянииАктивнойФормыПриОшибке": "Истина",
        "ИскатьЭлементыФормыПоИмени": "Истина",
        "ТегTreeВключенПоУмолчанию": "Истина",
        "КлиентыТестирования": [{
            "Имя": "Этот клиент", "ПутьКИнфобазе": '/F"%s"' % ib,
            "ДопПараметры": (cred + " /DisableStartupDialogs /DisableStartupMessages").strip(),
            "ТипКлиента": "Тонкий", "ИмяКомпьютера": "localhost",
            "ПортЗапускаТестКлиента": str(cfg.get('va_port', 48000))}],
    }
    if tag:
        params["СписокТеговОтбор"] = [tag]
    pj = os.path.join(out, 'VAParams.json')
    io.open(pj, 'w', encoding='utf-8').write(json.dumps(params, ensure_ascii=False, indent=1))

    # клиенты только тестовой базы: занятый порт / висящий менеджер ломают запуск
    stop = ("Get-CimInstance Win32_Process -Filter \"Name='1cv8.exe' or Name='1cv8c.exe'\" | Where-Object "
            "{ $_.CommandLine -like '*%s*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % ib)
    subprocess.run(['powershell', '-NoProfile', '-Command', stop], capture_output=True)
    cmd = '"%s" ENTERPRISE /F"%s"%s /DisableStartupDialogs /DisableStartupMessages /TESTMANAGER /Execute "%s" ' \
          '/C"StartFeaturePlayer;VAParams=%s"' % (cfg['v8'], ib, cred, epf, pj)
    t0 = time.time()
    p = subprocess.Popen(cmd)
    try:
        p.wait(timeout=int(cfg.get('va_timeout', 1800)))
    except subprocess.TimeoutExpired:
        print('таймаут: менеджер тестирования не завершился (диалог? см. снимок screens)')
    subprocess.run(['powershell', '-NoProfile', '-Command', stop], capture_output=True)
    print('Vanessa: %.1f мин' % ((time.time() - t0) / 60))

    ok = False
    for f in glob.glob(os.path.join(out, 'junit', '*.xml')):
        x = io.open(f, encoding='utf-8-sig').read()
        for m in re.finditer(r'<testsuite name="([^"]*)" errors="(\d+)" skipped="(\d+)" tests="(\d+)" failures="(\d+)" time="([^"]*)"', x):
            print('фича «%s»: сценариев %s, ошибок %s, падений %s, пропущено %s, %s с' % (
                m.group(1), m.group(4), m.group(2), m.group(5), m.group(3), m.group(6)))
            ok = m.group(2) == '0' and m.group(5) == '0' and int(m.group(4)) > 0
        for m in re.finditer(r'<failure[^>]*message="([^"]*)"', x):
            print('  ПАДЕНИЕ:', m.group(1)[:600])
    log = os.path.join(out, 'log.txt')
    if not ok and os.path.exists(log):
        print(io.open(log, encoding='utf-8-sig', errors='replace').read()[-4000:])
    for f in glob.glob(os.path.join(out, 'screens', '*')):
        print('снимок:', f)
    if not glob.glob(os.path.join(out, 'junit', '*.xml')):
        print('отчёта JUnit нет: Vanessa не дошла до сценариев (см. log.txt, журнал регистрации)')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
