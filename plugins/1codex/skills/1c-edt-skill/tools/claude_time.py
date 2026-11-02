# -*- coding: utf-8 -*-
"""Чистое время работы Claude по транскрипту сессии Claude Code — для отчёта после каждой большой работы.

Считается сумма интервалов между событиями транскрипта, пока Claude работает: мысли, ответы, вызовы инструментов и
их выполнение на переднем плане. НЕ считается: ожидание сообщения пользователя (интервал перед его сообщением),
ожидание фоновых задач (интервал перед уведомлением task-notification), разрывы длиннее 15 минут.

  python <skill>/tools/claude_time.py                         # вся текущая сессия, по запросам пользователя
  python <skill>/tools/claude_time.py --с "фрагмент запроса"  # с запроса пользователя, содержащего фрагмент
  python <skill>/tools/claude_time.py --с 2026-10-17T16:49    # с момента (местное время)

Запускать из каталога проекта: транскрипт — самый свежий ~/.claude/projects/<каталог, где «:», «\\», «/» → «-»>/*.jsonl
(или --проект каталог, --файл путь). Проект UP (C:\\gold\\UP), 17.10.2026; правило — CLAUDE.md набора, шаг 10.
"""
import datetime as дт
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
РАЗРЫВ = дт.timedelta(minutes=15)


def папка_транскриптов(каталог):
    """~/.claude/projects/<каталог проекта с «:», «\\», «/», заменёнными на «-»> — так называет папки Claude Code."""
    имя = os.path.abspath(каталог).replace(':', '-').replace('\\', '-').replace('/', '-')
    return os.path.join(os.path.expanduser('~'), '.claude', 'projects', имя)


def события(файл):
    """[(время UTC, вид, текст)]: вид — human | notification | work."""
    итог = []
    for стр in open(файл, encoding='utf-8'):
        д = json.loads(стр)
        т = д.get('type')
        if т not in ('user', 'assistant') or 'timestamp' not in д:
            continue
        время = дт.datetime.fromisoformat(д['timestamp'].replace('Z', '+00:00'))
        вид, текст = 'work', ''
        источник = (д.get('origin') or {}).get('kind')
        if т == 'user' and источник == 'human':
            вид = 'human'
            с = д['message']['content']
            текст = с if isinstance(с, str) else ' '.join(x.get('text', '') for x in с if isinstance(x, dict))
        elif т == 'user' and источник == 'task-notification':
            вид = 'notification'
        итог.append((время, вид, текст))
    итог.sort(key=lambda x: x[0])
    return итог


def активное(события_, с=None, по=None):
    всего = дт.timedelta()
    for (т0, _, _), (т1, вид, _) in zip(события_, события_[1:]):
        if с and т1 <= с or по and т1 > по:
            continue
        if вид in ('human', 'notification'):
            continue
        if т1 - т0 <= РАЗРЫВ:
            всего += т1 - т0
    return всего


ВИДЫ = [   # (вид работы, условие по инструменту и тексту вызова) — первое совпадение
    ('Загрузка в базу, проверка, сверка', lambda и, т: и in ('Bash', 'PowerShell') and any(
        с in т for с in ('платформа.py загрузить', 'платформа.py проверить', 'платформа.py сверить', 'платформа.py принять',
                         'платформа.py cf', '/RestoreIB', 'CREATEINFOBASE', 'DumpConfigToFiles', 'платформа.py песочница'))),
    ('UI-прогоны (передний план)', lambda и, т: и in ('Bash', 'PowerShell') and ('тест_ui' in т or 'ui_' in т and '.py' in т)),
    ('COM: запросы и тесты', lambda и, т: и in ('Bash', 'PowerShell') and any(с in т for с in ('пл.com', 'платформа.py запрос',
                                                                                              'тест_диз', 'заполненность.py'))),
    ('Отчёты docx / pdf', lambda и, т: и in ('Bash', 'PowerShell') and any(с in т for с in ('отчёт_', 'редизайн_методолог',
                                                                                          'pymupdf', 'docx'))),
    ('Генераторы XML (скрипты правок)', lambda и, т: и in ('Bash', 'PowerShell') and any(с in т for с in ('диз03_04.py',
                                                                                                       'редизайн.py'))),
    ('Git и набор знаний', lambda и, т: и in ('Bash', 'PowerShell') and ('git ' in т or 'cases_sync' in т)),
    ('Просмотр снимков', lambda и, т: и == 'Read' and т.lower().endswith(('.png', '.jpg'))),
    ('Чтение кода и поиск', lambda и, т: и in ('Read', 'Grep', 'Glob') or и in ('Bash', 'PowerShell') and any(
        т.lstrip().startswith(с) or (' ' + с) in т for с in ('cat ', 'grep ', 'sed -n', 'head ', 'ls ', 'find ', 'diff '))),
    ('Запись кода (Write / Edit)', lambda и, т: и in ('Write', 'Edit')),
    ('Браузер, сеть, документация', lambda и, т: и.startswith('mcp__Claude_Browser') or 'web_' in и),
    ('План и служебное', lambda и, т: и.startswith('mcp__ccd') or и in ('ToolSearch', 'SendUserFile', 'AskUserQuestion')),
]


def разбор(файл, с=None):
    """Время по видам работы: длительность вызова = от tool_use до его tool_result; модель — от предыдущего события до
    tool_use / ответа; фон — от запуска фоновой задачи до её уведомления (стена, не «чистое» время)."""
    вызовы, события_ = {}, []
    for стр in open(файл, encoding='utf-8'):
        д = json.loads(стр)
        if д.get('type') not in ('user', 'assistant') or 'timestamp' not in д:
            continue
        время = дт.datetime.fromisoformat(д['timestamp'].replace('Z', '+00:00'))
        if с and время < с:
            continue
        содержимое = д.get('message', {}).get('content')
        события_.append((время, д))
        if not isinstance(содержимое, list):
            continue
        for ч in содержимое:
            if not isinstance(ч, dict):
                continue
            if ч.get('type') == 'tool_use':
                вход = ч.get('input', {})
                текст = вход.get('command') or вход.get('file_path') or вход.get('pattern') or json.dumps(вход, ensure_ascii=False)[:300]
                вызовы[ч['id']] = {'инструмент': ч['name'], 'текст': текст, 'начало': время,
                                   'фон': bool(вход.get('run_in_background')), 'конец': None, 'ошибка': False}
            elif ч.get('type') == 'tool_result' and ч.get('tool_use_id') in вызовы:
                в = вызовы[ч['tool_use_id']]
                в['конец'] = время
                тело = json.dumps(ч.get('content'), ensure_ascii=False)
                в['ошибка'] = bool(ч.get('is_error')) or any(м in тело for м in (
                    'Traceback', 'AssertionError', 'SyntaxError', 'код 101', 'ОШИБКА ', 'Exit code 1', 'не определена'))
    итог, ошибки, всего = {}, {}, дт.timedelta()
    for в in вызовы.values():
        if not в['конец']:
            continue
        длит = в['конец'] - в['начало']
        if длит > РАЗРЫВ:
            continue
        вид = next((н for н, у in ВИДЫ if у(в['инструмент'], в['текст'])), 'Прочие команды')
        итог[вид] = итог.get(вид, дт.timedelta()) + длит
        ошибки[вид] = ошибки.get(вид, 0) + (1 if в['ошибка'] else 0)
        всего += длит
    # время модели: активное время сессии минус выполнение инструментов
    сб = [(т, ('human' if (д.get('origin') or {}).get('kind') == 'human' else
                'notification' if (д.get('origin') or {}).get('kind') == 'task-notification' else 'work'), '')
          for т, д in события_]
    активно = активное(сб)
    print('Чистое время Claude: %s, из них:' % мин(активно))
    print('  %-38s %10s' % ('модель (думает, пишет код и тексты)', мин(max(активно - всего, дт.timedelta()))))
    for вид, т in sorted(итог.items(), key=lambda x: -x[1]):
        print('  %-38s %10s   вызовов с ошибкой: %d' % (вид, мин(т), ошибки.get(вид, 0)))
    фон = [в for в in вызовы.values() if в['фон']]
    print('Фоновых задач: %d (их ожидание в чистое время не входит)' % len(фон))


def мин(т):
    м = int(т.total_seconds() // 60)
    return '%d ч %02d мин' % (м // 60, м % 60) if м >= 60 else '%d мин' % м


def main():
    а = sys.argv[1:]
    каталог = а[а.index('--проект') + 1] if '--проект' in а else os.getcwd()
    if '--файл' in а:
        файл = а[а.index('--файл') + 1]
    else:
        файлы = glob.glob(os.path.join(папка_транскриптов(каталог), '*.jsonl'))
        if not файлы:
            sys.exit('нет транскриптов в ' + папка_транскриптов(каталог))
        файл = max(файлы, key=os.path.getmtime)
    с_ = а[а.index('--с') + 1] if '--с' in а else None
    сб = события(файл)
    if '--разбор' in а:
        начало = None
        if с_:
            for т, вид, текст in сб:
                if вид == 'human' and с_.lower() in текст.lower():
                    начало = т - дт.timedelta(seconds=1)
                    break
        разбор(файл, начало)
        return
    if с_:
        начало = None
        try:
            начало = дт.datetime.fromisoformat(с_).astimezone(дт.timezone.utc)
        except ValueError:
            for т, вид, текст in сб:
                if вид == 'human' and с_.lower() in текст.lower():
                    начало = т - дт.timedelta(seconds=1)
                    break
            if начало is None:
                sys.exit('запрос с «%s» не найден' % с_)
        print('чистое время Claude с %s: %s' % (начало.astimezone().strftime('%d.%m %H:%M'), мин(активное(сб, начало))))
        return
    запросы = [(т, текст) for т, вид, текст in сб if вид == 'human']
    for н, (т, текст) in enumerate(запросы):
        до = запросы[н + 1][0] if н + 1 < len(запросы) else None
        print('%s  %8s  %s' % (т.astimezone().strftime('%d.%m %H:%M'), мин(активное(сб, т - дт.timedelta(seconds=1), до)),
                               ' '.join(текст.split())[:80]))
    print('итого чистое время Claude в сессии: %s (сессия %s — %s)' % (
        мин(активное(сб)), сб[0][0].astimezone().strftime('%d.%m %H:%M'), сб[-1][0].astimezone().strftime('%H:%M')))


if __name__ == '__main__':
    main()
