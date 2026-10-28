"""Measure command wall time without Claude/Codex transcript dependencies.

python tools/run_timed.py --label lint --output timing.jsonl -- python tools/lint_dump.py dump
Arguments are passed directly to the process. The log records only the label,
executable, dates, elapsed seconds and exit code, not command arguments.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', default='command')
    parser.add_argument('--output', type=Path)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        parser.error('укажите команду после --')
    started = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    try:
        code = subprocess.run(command).returncode
    except OSError as error:
        print('Cannot start command: %s' % error)
        code = 127
    result = {'label': args.label, 'executable': command[0], 'started_at_utc': started,
              'ended_at_utc': datetime.now(timezone.utc).isoformat(),
              'elapsed_seconds': round(time.perf_counter() - start, 6), 'exit_code': code}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
