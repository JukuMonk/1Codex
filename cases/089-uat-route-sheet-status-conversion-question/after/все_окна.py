# Снимок КАЖДОГО окна процесса тест-клиента — шагом сценария (ЗапуститьПриложение на клиенте менеджера):
#   python все_окна.py <папка>
# Окно ошибки или вопроса (ErrorWindow, ~550–670 × 220–270, заголовок «1С:Предприятие») — отдельное окно 1cv8c,
# в видео и в снимок «главного окна» не попадает. Чужие окна 1cv8c (другие базы пользователя) не сохранять:
# фильтровать по заголовку своей копии / по PID своего клиента.
import ctypes
import os
import subprocess
import sys
from ctypes import wintypes as wt

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
FFMPEG = 'ffmpeg'
PW_RENDERFULLCONTENT = 2


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG), ('biPlanes', wt.WORD),
                ('biBitCount', wt.WORD), ('biCompression', wt.DWORD), ('biSizeImage', wt.DWORD),
                ('biXPelsPerMeter', wt.LONG), ('biYPelsPerMeter', wt.LONG), ('biClrUsed', wt.DWORD),
                ('biClrImportant', wt.DWORD)]


def процесс(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return ''
    б = ctypes.create_unicode_buffer(1024)
    n = wt.DWORD(1024)
    ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, б, ctypes.byref(n))
    ctypes.windll.kernel32.CloseHandle(h)
    return os.path.basename(б.value).lower()


def окна(exe='1cv8c.exe'):
    итог = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def обход(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                б = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, б, n + 1)
                if процесс(hwnd) == exe:
                    итог.append((hwnd, б.value))
        return True
    user32.EnumWindows(обход, 0)
    return итог


def кадр(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, PW_RENDERFULLCONTENT)
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth, bi.biHeight, bi.biPlanes, bi.biBitCount = w, -h, 1, 32
    буфер = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, буфер, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    return буфер.raw, w, h


if __name__ == '__main__':
    ctypes.windll.user32.SetProcessDPIAware()
    папка = sys.argv[1]
    os.makedirs(папка, exist_ok=True)
    with open(os.path.join(папка, 'окна.txt'), 'w', encoding='utf-8') as ф:
        for и, (hwnd, имя) in enumerate(окна()):
            д, w, h = кадр(hwnd)
            ф.write('%d %s %dx%d\n' % (и, имя, w, h))
            # своя копия — «[КОПИЯ] …» и безымянные окна «1С:Предприятие» (вопросы, ошибки); прочие базы — мимо
            if w < 50 or h < 50 or not ('КОПИЯ' in имя or имя == '1С:Предприятие'):
                continue
            subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra',
                            '-s', '%dx%d' % (w, h), '-i', '-', '-frames:v', '1',
                            os.path.join(папка, 'окно%d.png' % и)], input=д)
