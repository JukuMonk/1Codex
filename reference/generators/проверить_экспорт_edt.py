# -*- coding: utf-8 -*-
"""Проверить файлы проекта EDT выгрузкой в формат платформы БЕЗ самого EDT.

Консольный `1cedtcli export` в отдельном (чистом) рабочем пространстве
собирает модель с диска и выгружает конфигурацию. Если выгрузка прошла, а
обновление базы из EDT падает при экспорте — сломаны не файлы, а модель
рабочего пространства EDT: «Проект → Очистить…». Ловили на
«NullPointerException … "formItem" is null».

Занимает 10–15 минут. Запуск: python инструменты/проверить_экспорт_edt.py
"""
import glob
import os
import subprocess
import sys
import tempfile

ПРОЕКТ = 'C:/Users/user/AppData/Local/1C/1cedtstart/projects/MVM/УАТ_МВМ'
CLI = sorted(glob.glob('C:/Users/user/AppData/Local/1C/1cedtstart/installations/1C_EDT */1cedt/1cedtcli.exe'))


def main():
    if not CLI:
        sys.exit('ОШИБКА: 1cedtcli.exe не найден')
    корень = os.path.join(tempfile.gettempdir(), 'мвм_проверка_edt')
    ws, выгрузка = os.path.join(корень, 'ws'), os.path.join(корень, 'экспорт')
    os.makedirs(выгрузка, exist_ok=True)
    print('EDT:', CLI[-1])
    print('рабочее пространство:', ws)
    р = subprocess.run([CLI[-1], '-data', ws, '-command', 'export', '--project', ПРОЕКТ,
                        '--configuration-files', выгрузка], capture_output=True)
    вывод = (р.stdout + р.stderr).decode('utf-8', 'replace')
    ошибки = [с for с in вывод.splitlines() if 'Exception' in с or 'ERROR' in с]
    файлов = sum(len(ф) for _, _, ф in os.walk(выгрузка))
    print('код выхода %d, файлов в выгрузке %d' % (р.returncode, файлов))
    for с in ошибки[:20]:
        print('  ' + с[:200])
    if р.returncode or ошибки or файлов < 1000:
        sys.exit('ОШИБКА: выгрузка не прошла — дефект в файлах проекта')
    print('Выгрузка прошла: файлы проекта целы.')


if __name__ == '__main__':
    main()
