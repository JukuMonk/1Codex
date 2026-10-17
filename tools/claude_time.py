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
