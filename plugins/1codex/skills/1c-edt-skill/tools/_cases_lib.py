# -*- coding: utf-8 -*-
"""Служебный помощник для скриптов, которые раскладывают cases/. Не часть
skill pack как инструмента; оставлен, чтобы кейсы можно было пересобрать."""
import io
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(HERE, 'cases')


def write(rel, text):
    path = os.path.join(CASES, rel.replace('/', os.sep))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, 'w', encoding='utf-8', newline='\n').write(text.strip('\n') + '\n')


def case(num, slug, task, lessons, before=(), after=(), attempts=()):
    """before/after — [(имя файла, текст)]; attempts — [(имя папки, [(файл, текст)])]."""
    d = '%03d-%s' % (num, slug)
    write(d + '/task.md', task)
    write(d + '/lessons.md', lessons)
    for name, text in before:
        write('%s/before/%s' % (d, name), text)
    for name, text in after:
        write('%s/after/%s' % (d, name), text)
    for folder, files in attempts:
        for name, text in files:
            write('%s/%s/%s' % (d, folder, name), text)
    return d
