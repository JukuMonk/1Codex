# -*- coding: utf-8 -*-
"""Снимок окна тонкого клиента 1С без торможения клиента (case 092).

Почему не PrintWindow: он просит окно перерисоваться через поток клиента, и следующая загрузка динамического списка
в этом клиенте идёт десятки секунд — минуты (UP 8.5.1: 70–280 с после одного снимка, с любым флагом, 0 и 2).
Здесь — копия области экрана под главным окном процесса (BitBlt с экрана, окну ничего не посылается), 0,1–0,3 с.

Условия копии экрана — и почему иногда снимка нет:
- рабочий стол должен рисоваться: окно удалённого рабочего стола открыто, не свёрнуто, сеанс не отключён — иначе
  «screen grab failed» (у копии экрана, BitBlt по окну и ffmpeg gdigrab одинаково);
- окно 1С не перекрыто: копия снимет то, что сверху, — поэтому видимость проверяется WindowFromPoint в сетке 3×3;
- окно вперёд НЕ выводится (Alt + SetForegroundWindow навязчив — пользователь работает за тем же экраном);
- Windows Graphics Capture (ffmpeg gfxcapture) снимал бы и перекрытое окно, но требует D3D11: на сервере без
  видеокарты (базовый адаптер + адаптер RDP) — «Failed to create D3D11VA device».
Не вышло — grab() возвращает (False, причина): снимок пропускается, тест идёт дальше. printwindow=True — снять
любой ценой через window_shots.frame (медленно для клиента).

  python tools/ui_capture.py <pid> <файл.png>      # проверка: снять главное окно процесса
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import window_shots  # noqa: E402 — windows_of (окна процесса, DPI-aware), frame (PrintWindow)


def main_window(pid):
    """(hwnd, прямоугольник) самого большого видимого окна процесса или None."""
    import win32gui
    окна = window_shots.windows_of([pid])
    if not окна:
        return None
    h = max(окна, key=lambda x: (x[1][2] - x[1][0]) * (x[1][3] - x[1][1]))[0]
    return h, win32gui.GetWindowRect(h)


def visible(pid, rect):
    """В точках сетки 3×3 внутри окна сверху — окна этого процесса (диалоги 1С тоже его)."""
    import win32gui
    import win32process
    л, в, п, н = rect
    for дх in (0.15, 0.5, 0.85):
        for ду in (0.15, 0.5, 0.85):
            окно = win32gui.WindowFromPoint((int(л + (п - л) * дх), int(в + (н - в) * ду)))
            if not окно or win32process.GetWindowThreadProcessId(окно)[1] != pid:
                return False
    return True


def screen_available():
    """Рисуется ли рабочий стол сейчас (окно RDP открыто)."""
    from PIL import ImageGrab
    try:
        ImageGrab.grab(bbox=(0, 0, 8, 8))
        return True
    except OSError:
        return False


def grab(pid, path, retries=6, printwindow=False):
    """Снять главное окно процесса pid в path. → (True, '') или (False, причина). retries — попыток копии экрана
    с паузой 0,5 с (мгновенные «screen grab failed» бывают); перекрытое окно не повторяется."""
    if printwindow:
        кадр = window_shots.frame([pid], resize=False)   # ужатое окно не успевает перестроиться (ДиЗ-06)
        if кадр is None:
            return False, 'нет окон процесса'
        кадр.save(path)
        return True, ''
    from PIL import ImageGrab
    причина = ''
    for попытка in range(max(1, retries)):
        if попытка:
            time.sleep(0.5)
        окно = main_window(pid)
        if окно is None:
            причина = 'нет окон процесса'
            continue
        if not visible(pid, окно[1]):
            return False, 'окно 1С перекрыто другим окном'
        try:
            кадр = ImageGrab.grab(bbox=окно[1], all_screens=True)
        except OSError as ошибка:              # screen grab failed — рабочий стол не рисуется
            причина = 'рабочий стол не рисуется (%s): окно RDP свёрнуто или отключено' % ошибка
            continue
        if кадр.getbbox() is None:
            причина = 'чёрный кадр'
            continue
        кадр.save(path)
        return True, ''
    return False, причина


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    ок, причина = grab(int(sys.argv[1]), sys.argv[2])
    print(sys.argv[2] if ок else 'НЕ СНЯТ: ' + причина)
    sys.exit(0 if ок else 1)
