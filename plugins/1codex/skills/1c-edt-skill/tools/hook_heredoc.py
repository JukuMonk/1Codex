# -*- coding: utf-8 -*-
"""Хук Claude Code (PreToolUse, Bash): не пускать heredoc с обратной косой чертой в теле.

Такие команды ломались в Git Bash раз за разом (case 092; проект UP, ЛОВУШКИ У-15, У-21): `\\n`, `\\t`, `\\d` в Python-коде внутри
`python - <<'EOF'` или `cat > файл <<EOF`. Одни разворачивает оболочка (heredoc без кавычек), в других
путается экранирование, когда в тексте вперемешку кавычки и обратные косые; упавшая команда потом повторяется
с новой ошибкой. Надёжный путь — записать скрипт или фрагмент инструментом Write и запустить файл.

Код 2 — команда отклонена, текст stderr уходит Claude как причина. Остальные команды пропускаются (код 0).
Подключение: python tools/new_project.py --hook <папка проекта>. Отключить разово нельзя и не нужно: тот же результат даёт Write + `python файл.py`.
"""
import json
import re
import sys

try:
    команда = json.load(sys.stdin).get('tool_input', {}).get('command', '')
except Exception:              # noqa: BLE001 — хук не должен мешать работе при неожиданном вводе
    sys.exit(0)

м = re.search(r"<<-?\s*(['\"]?)(\w+)\1", команда)
if м:
    тело = команда[м.end():]
    конец = re.search(r'^\s*%s\s*$' % re.escape(м.group(2)), тело, re.M)
    if конец:
        тело = тело[:конец.start()]
    if '\\' in тело:
        sys.stderr.buffer.write((               # байтами в UTF-8: иначе Python на Windows пишет в cp1251
            'Отклонено хуком проекта (1c-edt-skill tools/hook_heredoc.py, case 092): heredoc с обратной косой чертой '
            'в теле ломается в Git Bash. Запиши текст инструментом Write (скрипт — в scratchpad) и запусти файл: '
            'python <файл>.py. Heredoc без обратных косых (например, сообщение коммита) — можно.\n').encode('utf-8'))
        sys.exit(2)
sys.exit(0)
