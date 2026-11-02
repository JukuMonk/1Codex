# -*- coding: utf-8 -*-
"""Сборка внешней компоненты «опрос ЧПУ» (Native API) и подставной библиотеки FOCAS — zig (pip install ziglang),
без Visual Studio и прав администратора.

  python инструменты/компонента.py            собрать всё → инструменты/компонента/сборка/
  python инструменты/компонента.py проверить  подставная Fwlib64.dll через ctypes (без 1С)

Результат:
  сборка/ФрегатЧПУ.zip        — компонента для макета пульс_КомпонентаЧПУ (MANIFEST.XML + Windows x64 + Linux x64);
                                конфигурация.py кладёт её в CommonTemplates/…/Ext/Template.bin
  сборка/win64/Fwlib64.dll    — ПОДСТАВНАЯ библиотека FOCAS (тесты, демо); настоящая — у заказчика, в поставку не входит
  сборка/linux64/libfwlib32.so — то же под Linux
ABI: компонента под Windows собирается clang в режиме MinGW (Itanium C++ ABI), платформа — MSVC: разница в ячейках
виртуального деструктора снята в include/addin_abi.h (ЛОВУШКИ.md).
"""
import ctypes
import os
import subprocess
import sys
import zipfile

КОРЕНЬ = os.path.dirname(os.path.abspath(__file__))
ИСХ = os.path.join(КОРЕНЬ, 'компонента')
СБОРКА = os.path.join(ИСХ, 'сборка')
ZIP = os.path.join(СБОРКА, 'ФрегатЧПУ.zip')

ЦЕЛИ = {
    'win64': dict(target='x86_64-windows-gnu', dll='FregatCNC_win64.dll', stub='Fwlib64.dll',
                  флаги=['-D_WINDOWS', '-DUNICODE', '-D_UNICODE'], ссылки=[]),
    'linux64': dict(target='x86_64-linux-gnu.2.17', dll='libFregatCNC_linux64.so', stub='libfwlib32.so',
                    флаги=['-fPIC', '-fvisibility=hidden'], ссылки=['-ldl', '-lpthread']),
}

МАНИФЕСТ = '''<?xml version="1.0" encoding="UTF-8"?>
<bundle xmlns="http://v8.1c.ru/8.2/addin/bundle">
\t<component os="Windows" path="FregatCNC_win64.dll" type="native" arch="x86_64"/>
\t<component os="Linux" path="libFregatCNC_linux64.so" type="native" arch="x86_64"/>
</bundle>
'''


def zig(*арг):
    к = [sys.executable, '-m', 'ziglang', 'c++'] + list(арг)
    r = subprocess.run(к, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        sys.exit('zig: код %s\n%s\n%s' % (r.returncode, ' '.join(к[3:]), r.stderr[-4000:]))
    if r.stderr.strip():
        print(r.stderr.strip()[-2000:])


def собрать():
    общие = ['-std=c++17', '-O2', '-shared', '-Wall', '-Wno-unused-parameter',
             # экспорт объявленных в ComponentBase.h функций; удаление — через конкретный тип (addin_abi.h)
             '-Wno-dll-attribute-on-redeclaration', '-Wno-delete-non-abstract-non-virtual-dtor']
    for имя, ц in ЦЕЛИ.items():
        папка = os.path.join(СБОРКА, имя)
        os.makedirs(папка, exist_ok=True)
        print('сборка', имя, '…')
        zig('-target', ц['target'], *общие, *ц['флаги'], '-I', os.path.join(ИСХ, 'include'),
            os.path.join(ИСХ, 'компонента.cpp'), '-o', os.path.join(папка, ц['dll']), *ц['ссылки'])
        zig('-target', ц['target'], *общие, *ц['флаги'],
            os.path.join(ИСХ, 'fwlib_подставная.cpp'), '-o', os.path.join(папка, ц['stub']), *ц['ссылки'])
        for лишний in os.listdir(папка):            # zig оставляет .lib/.pdb рядом — в zip не нужны
            if лишний.endswith(('.lib', '.pdb', '.a')):
                os.remove(os.path.join(папка, лишний))
    with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('MANIFEST.XML', МАНИФЕСТ)
        for имя, ц in ЦЕЛИ.items():
            z.write(os.path.join(СБОРКА, имя, ц['dll']), ц['dll'])
    print('собрано: %s (%d КБ)' % (ZIP, os.path.getsize(ZIP) // 1024))


def проверить():
    """Подставная Fwlib64.dll напрямую (ctypes): соединение, состояние, программа, нет связи."""
    путь = os.path.join(СБОРКА, 'win64', 'Fwlib64.dll')
    сценарий = os.path.join(СБОРКА, 'win64', 'focas_stub_проверка.txt')
    with open(сценарий, 'w', encoding='utf-8') as f:
        f.write('10.0.0.1 run=3 aut=1 prog=O1234 onum=1234 speed=1500 feed=320 load=47 parts=12 total=900\n'
                '10.0.0.2 offline=1 delay=300\n')
    os.environ['FREGAT_FOCAS_STUB'] = сценарий
    lib = ctypes.WinDLL(путь)
    for ф in ('cnc_allclibhndl3', 'cnc_statinfo', 'cnc_exeprgname', 'cnc_freelibhndl'):
        getattr(lib, ф).restype = ctypes.c_short             # FOCAS возвращает short
    h = ctypes.c_ushort()
    assert lib.cnc_allclibhndl3(b'10.0.0.1', 8193, 2, ctypes.byref(h)) == 0
    st = (ctypes.c_short * 9)()
    assert lib.cnc_statinfo(h, st) == 0 and st[3] == 3, list(st)
    class EXE(ctypes.Structure):
        _pack_ = 4
        _fields_ = [('name', ctypes.c_char * 36), ('o_num', ctypes.c_int32)]
    e = EXE()
    assert lib.cnc_exeprgname(h, ctypes.byref(e)) == 0 and e.name == b'O1234' and e.o_num == 1234
    assert lib.cnc_freelibhndl(h) == 0
    assert lib.cnc_statinfo(h, st) == -8                     # закрытый дескриптор — EW_HANDLE
    r = lib.cnc_allclibhndl3(b'10.0.0.2', 8193, 1, ctypes.byref(h))
    assert r == -16, r                                       # нет связи — EW_SOCKET
    os.remove(сценарий)
    print('подставная FOCAS: ok')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if 'проверить' in sys.argv[1:]:
        проверить()
    else:
        собрать()
        проверить()
