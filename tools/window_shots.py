# -*- coding: utf-8 -*-
"""Снимки ТОЛЬКО окон тестируемого клиента 1С (без рабочего стола) — для пользовательских инструкций.

Запись рабочего стола (vanessa.py --video) снимает всё, что сверху: если пользователь в это время работает,
в кадр попадает его мессенджер, а не 1С (UP, 2026-10). Здесь каждое окно процесса тонкого клиента снимается
PrintWindow(PW_RENDERFULLCONTENT) — содержимое окна, даже если его закрывают другие окна, — и окна-диалоги
накладываются на главное окно по их экранным координатам.

Кадр сохраняется, когда картинка устоялась (два кадра подряд через 2 с одинаковы — паузы сценария делать от 5 с; PrintWindow идёт через поток окна клиента: при частых снимках большого окна динамические списки грузятся минутами, UP 2026-10) и отличается от прошлого сохранённого: паузы
сценария Vanessa («И Пауза 3») становятся кадрами. Файлы — <dir>/NNN.png по порядку.

Использование из vanessa.py: --shots <каталог>. Отдельно (для проверки):
  python tools/window_shots.py <каталог> <pid> [секунд]
"""
import ctypes
import os
import sys
import threading
import time

import win32con
import win32gui
import win32process
import win32ui
from PIL import Image, ImageChops, ImageStat

PW_RENDERFULLCONTENT = 2


def windows_of(pids):
    """Видимые окна процессов, сверху вниз по Z-порядку."""
    res = []

    def cb(h, _):
        if not win32gui.IsWindowVisible(h) or win32gui.IsIconic(h):
            return True
        if win32process.GetWindowThreadProcessId(h)[1] not in pids:
            return True
        l, t, r, b = win32gui.GetWindowRect(h)
        if r - l > 80 and b - t > 60:
            res.append((h, (l, t, r, b)))
        return True
    win32gui.EnumWindows(cb, None)
    return res


def grab(h, rect):
    l, t, r, b = rect
    w, hgt = r - l, b - t
    hdc = win32gui.GetWindowDC(h)
    src = win32ui.CreateDCFromHandle(hdc)
    mem = src.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(src, w, hgt)
    mem.SelectObject(bmp)
    ctypes.windll.user32.PrintWindow(h, mem.GetSafeHdc(), PW_RENDERFULLCONTENT)
    info = bmp.GetInfo()
    img = Image.frombuffer('RGB', (info['bmWidth'], info['bmHeight']), bmp.GetBitmapBits(True), 'raw', 'BGRX', 0, 1)
    win32gui.DeleteObject(bmp.GetHandle())
    mem.DeleteDC()
    src.DeleteDC()
    win32gui.ReleaseDC(h, hdc)
    return img


SIZE = (1600, 1000)  # кадр для документа: на широком мониторе окно во весь экран — мелкий нечитаемый текст


def maximize_quietly(h, size=SIZE):
    """Окно — размера size в левом верхнем углу рабочей области (не больше её), без активации: не отнимать
    фокус у пользователя. Развёрнутое окно сперва восстанавливается, иначе размер не меняется."""
    import win32api
    mon = win32api.MonitorFromWindow(h, win32con.MONITOR_DEFAULTTONEAREST)
    l, t, r, b = win32api.GetMonitorInfo(mon)['Work']
    if win32gui.GetWindowPlacement(h)[1] == win32con.SW_SHOWMAXIMIZED:
        win32gui.ShowWindow(h, win32con.SW_SHOWNOACTIVATE)
    win32gui.SetWindowPos(h, 0, l, t, min(size[0], r - l), min(size[1], b - t),
                          win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER)


def frame(pids):
    wins = windows_of(pids)
    if not wins:
        return None
    main = max(wins, key=lambda x: (x[1][2] - x[1][0]) * (x[1][3] - x[1][1]))
    l, t, r, b = main[1]
    # размер проверяется на каждом кадре: первым находится окно-заставка, главное окно появляется позже
    if r - l > SIZE[0] + 20 or b - t > SIZE[1] + 20:
        maximize_quietly(main[0])
        wins = windows_of(pids)
        main = max(wins, key=lambda x: (x[1][2] - x[1][0]) * (x[1][3] - x[1][1]))
    ml, mt, mr, mb = main[1]
    canvas = grab(*main)
    for h, rect in reversed(wins):
        if h == main[0]:
            continue
        canvas.paste(grab(h, rect), (rect[0] - ml, rect[1] - mt))
    return canvas


def differs(a, b, level):
    if a is None or b is None or a.size != b.size:
        return True
    d = ImageChops.difference(a.convert('L').resize((240, 135)), b.convert('L').resize((240, 135)))
    return ImageStat.Stat(d).mean[0] > level


def record(out, get_pids, alive, step=2.0, stable=1):
    """Снимать, пока alive(); get_pids() — множество PID тестируемого клиента (пустое — ещё нет)."""
    os.makedirs(out, exist_ok=True)
    prev, saved, calm, n = None, None, 0, 0
    while alive():
        pids = get_pids()
        if not pids:
            time.sleep(1)
            continue
        try:
            img = frame(pids)
        except Exception:
            img = None
        if img is None:
            time.sleep(step)
            continue
        calm = calm + 1 if not differs(img, prev, 0.4) else 0
        prev = img
        # порог нового кадра: средняя разница миниатюр; изменение одной ячейки таблицы (тип строки, загрузка строки)
        # меньше 1,5 — для таких снимков SHOTS_MIN_DIFF=0.2 (UP, отчёт по ДиЗ-02)
        if calm == stable and differs(img, saved, float(os.environ.get('SHOTS_MIN_DIFF', '1.5'))):
            n += 1
            img.save(os.path.join(out, '%03d.png' % n))
            saved = img
        time.sleep(step)
    return n


def start(out, get_pids, alive):
    t = threading.Thread(target=record, args=(out, get_pids, alive), daemon=True)
    t.start()
    return t


if __name__ == '__main__':
    d, pid = sys.argv[1], int(sys.argv[2])
    sec = float(sys.argv[3]) if len(sys.argv) > 3 else 20
    t0 = time.time()
    print('кадров:', record(d, lambda: {pid}, lambda: time.time() - t0 < sec))
