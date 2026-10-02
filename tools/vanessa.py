# -*- coding: utf-8 -*-
"""vanessa — прогон сценариев Vanessa Automation (Gherkin, .feature) в ТЕСТОВОЙ базе platform.py.

  python tools/vanessa.py <platform.json> <каталог или файл .feature> [тег] [--video [файл.mp4]]

--video — запись экрана (ffmpeg gdigrab, весь рабочий стол): начинается, когда запущен тестируемый клиент
(процесс с /TESTCLIENT), кончается с прогоном; в копию сценариев после шага подключения добавляется
«И я активизирую главное окно сеанса TESTCLIENT» — иначе клиент под окном менеджера Vanessa. ffmpeg —
"ffmpeg" в platform.json или в PATH. Файл по умолчанию — <va_video_dir или work/va_out>/va_<дата-время>.mp4.

Берёт из platform.json: v8, work (тестовая база work/ib — после platform.py load/update; другая файловая
база — «va_ib»), test_usr/test_pwd,
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


CONNECT = 'Я открыл новый сеанс TestClient или подключил уже существующий'
ACTIVATE = 'И я активизирую главное окно сеанса TESTCLIENT'
TESTCLIENT_PS = ("if (Get-CimInstance Win32_Process | Where-Object { $_.Name -like '1cv8*' -and "
                 "$_.CommandLine -like '*TESTCLIENT*' }) { exit 0 }; exit 1")


def video_features(src, dst):
    """Копия сценариев для видео: после шага подключения — активизация окна тестируемого клиента."""
    shutil.rmtree(dst, ignore_errors=True)
    if os.path.isdir(src):
        shutil.copytree(src, dst)
    else:
        os.makedirs(dst)
        shutil.copy(src, dst)
    for f in glob.glob(os.path.join(dst, '**', '*.feature'), recursive=True):
        lines = io.open(f, encoding='utf-8-sig').read().split('\n')
        res = []
        for i, line in enumerate(lines):
            res.append(line)
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''
            if CONNECT in line and ACTIVATE.lower() not in nxt.lower():
                res.append(line[:len(line) - len(line.lstrip())] + ACTIVATE)
        io.open(f, 'w', encoding='utf-8').write('\n'.join(res))
    return dst


def thin_pids():
    """PID тонких клиентов (1cv8c.exe) через tasklist: WMI (Get-CimInstance) без прав
    администратора процессов не отдаёт вовсе — так на сервере МВМ, и запись не начиналась."""
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq 1cv8c.exe', '/FO', 'CSV', '/NH'],
                       capture_output=True, text=True, encoding='cp866', errors='replace')
    return {int(m.group(1)) for m in re.finditer(r'"1cv8c\.exe","(\d+)"', r.stdout, re.I)}


def start_video(cfg, path, runner, before=None):
    """Ждать тестируемый клиент (или конец прогона) и начать запись рабочего стола.
    Клиент узнаём по /TESTCLIENT в командной строке (WMI), а если WMI пуст — по новому
    тонкому клиенту, которого не было до старта менеджера (`before`)."""
    ffmpeg = cfg.get('ffmpeg') or shutil.which('ffmpeg')
    if not ffmpeg:
        print('видео: ffmpeg не найден (ключ "ffmpeg" в platform.json или PATH) — прогон без записи')
        return None
    t0 = time.time()
    while runner.poll() is None and time.time() - t0 < 300:
        found = subprocess.run(['powershell', '-NoProfile', '-Command', TESTCLIENT_PS],
                               capture_output=True).returncode == 0
        if not found and before is not None:
            found = bool(thin_pids() - before)
        if found:
            # весь рабочий стол: главное окно тонкого клиента по заголовку в перечислении окон не находится
            print('видео: запись началась', flush=True)
            return subprocess.Popen([ffmpeg, '-y', '-loglevel', 'error', '-f', 'gdigrab', '-framerate', '15',
                                     '-i', 'desktop', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264',
                                     '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p', path],
                                    stdin=subprocess.PIPE)
        time.sleep(1)
    return None


def stop_video(rec, path):
    if not rec:
        return
    try:
        rec.communicate(b'q', timeout=30)  # «q» — ffmpeg дописывает индекс mp4
    except subprocess.TimeoutExpired:
        rec.kill()
    if os.path.exists(path):
        print('видео: %s (%.1f МБ)' % (path, os.path.getsize(path) / 1e6))


def main():
    args = sys.argv[1:]
    video = None
    if '--video' in args:
        i = args.index('--video')
        video = args[i + 1] if i + 1 < len(args) and args[i + 1].lower().endswith('.mp4') else ''
        del args[i:i + (2 if video else 1)]
    if len(args) < 2:
        sys.exit(__doc__)
    cfg = json.load(io.open(args[0], encoding='utf-8-sig'))
    features = os.path.abspath(args[1])
    tag = args[2] if len(args) > 2 else ''
    epf = cfg.get('va_epf')
    if not epf or not os.path.exists(epf):
        sys.exit('В platform.json нет va_epf (путь к vanessa-automation-single.epf) или файла нет: %s' % epf)
    w = cfg['work']
    # тестовая база platform.py (work\ib) или другая файловая база — «va_ib» (например, копия рабочей для сдачи)
    ib = cfg.get('va_ib') or os.path.join(w, 'ib')
    out = os.path.join(w, 'va_out')
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    usr = cfg.get('test_usr', 'Администратор')
    cred = ' /N"%s" /P"%s"' % (usr, cfg.get('test_pwd', '')) if usr else ''
    if video is not None:
        vdir = cfg.get('va_video_dir') or out  # va_out очищается каждым прогоном — видео лучше хранить отдельно
        os.makedirs(vdir, exist_ok=True)
        video = os.path.abspath(video) if video else os.path.join(vdir, time.strftime('va_%Y%m%d_%H%M%S.mp4'))
        features = video_features(features, os.path.join(out, 'features_video'))
    root = features if os.path.isdir(features) else os.path.dirname(features)
    params = {
        "КаталогФич": features,
        # первый сеанс тонкого клиента на большой конфигурации стартует дольше умолчания VA —
        # шаг подключения падал «Не получилось подключить TestClient» (МВМ: до полутора минут)
        "ТаймаутЗапуска1С": int(cfg.get('va_start_timeout', 180)),
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
    before = thin_pids()
    p = subprocess.Popen(cmd)
    rec = start_video(cfg, video, p, before) if video else None
    try:
        p.wait(timeout=int(cfg.get('va_timeout', 1800)))
    except subprocess.TimeoutExpired:
        print('таймаут: менеджер тестирования не завершился (диалог? см. снимок screens)')
    stop_video(rec, video)
    subprocess.run(['powershell', '-NoProfile', '-Command', stop], capture_output=True)
    print('Vanessa: %.1f мин' % ((time.time() - t0) / 60))

    # Прошло — только если прошли ВСЕ фичи: раньше итог брался по последней, и прогон
    # нескольких фич печатал «пройден» при падении в середине (МВМ, 02.10.2026).
    suites = []
    for f in glob.glob(os.path.join(out, 'junit', '*.xml')):
        x = io.open(f, encoding='utf-8-sig').read()
        for m in re.finditer(r'<testsuite name="([^"]*)" errors="(\d+)" skipped="(\d+)" tests="(\d+)" failures="(\d+)" time="([^"]*)"', x):
            print('фича «%s»: сценариев %s, ошибок %s, падений %s, пропущено %s, %s с' % (
                m.group(1), m.group(4), m.group(2), m.group(5), m.group(3), m.group(6)))
            suites.append(m.group(2) == '0' and m.group(5) == '0' and int(m.group(4)) > 0)
        for m in re.finditer(r'<failure[^>]*message="([^"]*)"', x):
            print('  ПАДЕНИЕ:', m.group(1)[:600])
    ok = bool(suites) and all(suites)
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
