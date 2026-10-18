# -*- coding: utf-8 -*-
"""Раскладка чистого времени Claude по этапам задачи и видам работы — по транскрипту сессии Claude Code.

Чем отличается от claude_time.py: тот даёт итог по запросам; этот делит один запрос на этапы (анализ, разработка,
проверка, выпуск…) и внутри этапа — на виды работы: модель думает / пишет код / ждёт инструмент (нажатия в 1С,
Конфигуратор, COM, Word, чтение). Так видно, ЧТО ускорять (Case 097: 70 % — время модели, а не 1С).

  python <skill>/tools/claude_stages.py --с "ДиЗ-07 к ТЗ-01" --до "приведи по нему" --этапы этапы.json --json итог.json
  python <skill>/tools/claude_stages.py --сравнить было.json стало.json        # таблица: группы и виды работы

этапы.json — [[группа, этап, признак], …] по порядку; признак — подстрока во входе вызова инструмента, с которого
начинается этап (у первого — null). Признаки проверяются строго по порядку: следующий этап начинается только после
предыдущего, поэтому признак, мелькнувший раньше (при чтении кода), не сбивает раскладку. Признаки удобно брать
из ленты вызовов: --лента печатает время и начало каждого вызова в границах запроса.

Не считается (как в claude_time.py): ожидание пользователя, уведомления фоновых задач, разрывы длиннее 15 минут.
Запускать из каталога проекта (или --проект / --файл). Проект UP (C:\\gold\\UP), 18.10.2026: ДиЗ-05 26 мин →
ДиЗ-07 15 мин (Case 097).
"""
import argparse
import datetime as дт
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claude_time import папка_транскриптов  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
РАЗРЫВ = дт.timedelta(minutes=15)


def вид_инструмента(имя, вход):
    т = json.dumps(вход, ensure_ascii=False)
    if имя in ('Write', 'Edit'):
        return 'запись файлов'
    if any(к in т for к in ('тест_ui', 'ui_test', 'ui_диз', 'ui_')):
        return 'нажатия в 1С'
    if any(к in т for к in ('выпуск', 'загрузить', 'проверить', 'сверить', 'принять', ' cf', 'цикл', 'DESIGNER')):
        return 'Конфигуратор: загрузка, проверка'
    if any(к in т for к in ('тест_', 'запрос', 'вызов', 'COMConnector', 'com()')):
        return 'COM: данные и тесты'
    if 'отчёт' in т or '.docx' in т or '.pdf' in т:
        return 'Word: отчёт'
    if имя in ('Read', 'Grep', 'Glob') or any(к in т for к in ('grep', 'sed -n', 'cat ', 'head', 'tail')):
        return 'чтение и поиск'
    return 'прочие команды'


def события(файл):
    """[(время, роль, [tool_use], есть_tool_result, текст)]."""
    итог = []
    for с in open(файл, encoding='utf-8'):
        д = json.loads(с)
        if д.get('type') not in ('user', 'assistant') or 'timestamp' not in д:
            continue
        время = дт.datetime.fromisoformat(д['timestamp'].replace('Z', '+00:00'))
        сод = д.get('message', {}).get('content')
        вызовы, результат, текст = [], False, ''
        if isinstance(сод, list):
            for ч in сод:
                if not isinstance(ч, dict):
                    continue
                if ч.get('type') == 'tool_use':
                    вызовы.append(ч)
                elif ч.get('type') == 'tool_result':
                    результат = True
                elif ч.get('type') == 'text':
                    текст += ч.get('text', '')
        elif isinstance(сод, str):
            текст = сод
        итог.append((время, д['type'], вызовы, результат, текст))
    return итог


def человек(с):
    return с[1] == 'user' and not с[3] and с[4] and 'task-notification' not in с[4] and '<system-reminder>' not in с[4][:20]


def границы(ев, с_, до):
    старт = next(i for i, с in enumerate(ев) if человек(с) and с_ in с[4])
    конец = len(ев)
    if до:
        конец = next((i for i in range(старт + 1, len(ев)) if человек(ев[i]) and до in ев[i][4]), len(ев))
    return старт, конец


def лента(ев, старт, конец):
    for с in ев[старт:конец]:
        for в in с[2]:
            print(с[0].astimezone().strftime('%H:%M:%S'), в['name'], json.dumps(в.get('input', {}), ensure_ascii=False)[:110])


def разложить(ев, старт, конец, этапы):
    этап, итог, последний = 0, {}, None
    for i in range(старт + 1, конец):
        пред, тек = ев[i - 1], ев[i]
        интервал = тек[0] - пред[0]
        if человек(тек) or (тек[1] == 'user' and 'task-notification' in тек[4]) or интервал > РАЗРЫВ:
            continue
        for в in тек[2]:
            вход = json.dumps(в.get('input', {}), ensure_ascii=False)
            if этап + 1 < len(этапы) and этапы[этап + 1][2] in вход:
                этап += 1
        if тек[1] == 'assistant':
            вид = 'модель: пишет код и тексты' if any(в['name'] in ('Write', 'Edit') for в in тек[2]) else 'модель: думает, решает'
            if тек[2]:
                последний = вид_инструмента(тек[2][-1]['name'], тек[2][-1].get('input', {}))
        elif тек[3]:
            вид = 'инструмент: ' + (последний or 'прочие команды')
        else:
            вид = 'модель: думает, решает'
        итог.setdefault(этап, {})
        итог[этап][вид] = итог[этап].get(вид, 0) + интервал.total_seconds()
    данные = []
    for н, (группа, имя, _) in enumerate(этапы):
        виды = итог.get(н, {})
        данные.append({'группа': группа, 'этап': имя, 'виды': {к: round(v / 60, 2) for к, v in виды.items()}})
    return данные


def печать(данные):
    всего = sum(sum(д['виды'].values()) for д in данные)
    print('ВСЕГО %.1f мин' % всего)
    for д in данные:
        print('%-11s %-42s %5.1f мин  %s' % (д['группа'], д['этап'], sum(д['виды'].values()),
              ', '.join('%s %.1f' % (к, v) for к, v in sorted(д['виды'].items(), key=lambda x: -x[1]) if v >= 0.05)))


def свод(данные):
    группы, виды = {}, {}
    for д in данные:
        группы[д['группа']] = группы.get(д['группа'], 0) + sum(д['виды'].values())
        for к, v in д['виды'].items():
            виды[к] = виды.get(к, 0) + v
    return группы, виды


def сравнить(было, стало):
    а, б = свод(было), свод(стало)
    for заголовок, x, y in (('группа', а[0], б[0]), ('вид работы', а[1], б[1])):
        print('\n%-46s %7s %7s' % (заголовок, 'было', 'стало'))
        for к in sorted(set(x) | set(y), key=lambda к: -x.get(к, 0)):
            print('%-46s %7.1f %7.1f' % (к, x.get(к, 0), y.get(к, 0)))
    print('%-46s %7.1f %7.1f' % ('ВСЕГО', sum(а[0].values()), sum(б[0].values())))


if __name__ == '__main__':
    п = argparse.ArgumentParser()
    п.add_argument('--с', help='фрагмент сообщения пользователя, с которого начата задача')
    п.add_argument('--до', help='фрагмент следующего сообщения пользователя (конец задачи)')
    п.add_argument('--этапы', help='JSON [[группа, этап, признак], …]')
    п.add_argument('--json', help='куда записать раскладку')
    п.add_argument('--лента', action='store_true', help='вызовы инструментов в границах задачи')
    п.add_argument('--сравнить', nargs=2, metavar=('БЫЛО', 'СТАЛО'))
    п.add_argument('--проект', default='.')
    п.add_argument('--файл')
    а = п.parse_args()
    if а.сравнить:
        сравнить(*(json.load(open(ф, encoding='utf-8')) for ф in а.сравнить))
        sys.exit(0)
    файл = а.файл or max(glob.glob(os.path.join(папка_транскриптов(а.проект), '*.jsonl')), key=os.path.getmtime)
    ев = события(файл)
    старт, конец = границы(ев, а.с, а.до)
    if а.лента or not а.этапы:
        лента(ев, старт, конец)
        sys.exit(0)
    этапы = json.load(open(а.этапы, encoding='utf-8'))
    данные = разложить(ев, старт, конец, этапы)
    печать(данные)
    if а.json:
        json.dump(данные, open(а.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
