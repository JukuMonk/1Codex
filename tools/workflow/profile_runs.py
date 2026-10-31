"""Сводка длительности конвейеров и UI. Не измеряет время размышлений модели."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path.cwd()


def read_runs(platform):
    records = []
    paths = list((platform/'runs').glob('*/run.json')) + list((platform/'ui-runs').glob('*/manifest.json'))
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        kind = 'UI' if path.name == 'manifest.json' else 'Платформа'
        total = data.get('elapsed_seconds', data.get('duration_seconds'))
        if total is None:
            continue
        stages = data.get('stages', [])
        # Platform depth 0 is the entire operation, not an additional duration.
        if kind == 'Платформа':
            stages = [s for s in stages if s.get('depth') == 1]
        records.append({'run_id': data['run_id'], 'kind': kind,
                        'operation': data.get('mode', data.get('operation', '?')),
                        'status': data['status'], 'started_at': data.get('started_at', ''),
                        'seconds': float(total), 'journal': str(path),
                        'preparation_seconds': data.get('preparation_seconds'),
                        'source_check_seconds': data.get('source_check_seconds'),
                        'stages': [{'name': s['name'], 'seconds': s.get('seconds', s.get('duration_seconds', 0)),
                                    'status': s['status']} for s in stages]})
    return sorted(records, key=lambda r: r['started_at'])


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=ROOT)
    parser.add_argument('--last', type=int, default=20)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    if args.last <= 0:
        parser.error('--last должен быть положительным')
    records = read_runs(args.project/'.platform')[-args.last:]
    print('Время процессов, включая ожидания. Параллельные прогоны могут пересекаться; сумма не равна времени работы Codex.')
    print('Запуск | Вид | Операция | Статус | Секунды')
    for row in records:
        print('%s | %s | %s | %s | %.2f' % tuple(row[k] for k in ('run_id', 'kind', 'operation', 'status', 'seconds')))
        for stage in row['stages']:
            print('  %s: %.2f с (%s)' % (stage['name'], stage['seconds'] or 0, stage['status']))
        if row['preparation_seconds'] is not None:
            print('  Подготовка защищённой копии: %.2f с' % row['preparation_seconds'])
        if row['source_check_seconds'] is not None:
            print('  Контроль исходников: %.2f с (уже входит в полное время)' % row['source_check_seconds'])
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
