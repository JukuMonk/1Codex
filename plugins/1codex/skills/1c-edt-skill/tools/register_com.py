# -*- coding: utf-8 -*-
"""register_com — регистрация COM-коннектора 1С (comcntr.dll) НА ПОЛЬЗОВАТЕЛЯ, без прав администратора.

  python tools/register_com.py "C:\\Program Files\\1cv8\\8.3.27.2325\\bin\\comcntr.dll" [V83.COMConnector]

Зачем: `regsvr32 comcntr.dll` пишет в HKLM и без прав администратора падает
(DllRegisterServer = 0x80070005). Без регистрации `Dispatch("V83.COMConnector")`
создаётся, но `Connect` не находится: «Библиотека не зарегистрирована»
(TYPE_E_LIBNOTREGISTERED) — не зарегистрирована БИБЛИОТЕКА ТИПОВ, а не класс.
Скрипт пишет в HKCU\\Software\\Classes: CLSID → InprocServer32 (путь к dll),
ProgID V83.COMConnector(.1) и библиотеку типов через oleaut32
RegisterTypeLibForUser. HKCU перекрывает HKLM для этого пользователя.

Версия коннектора должна совпадать с версией платформы базы: V83.* для 8.3.x,
V85.* для 8.5.x; dll — той же разрядности, что Python (64-бит → bin\\comcntr.dll
64-битной платформы). Проверка: python -c "import win32com.client as w;
print(w.Dispatch('V83.COMConnector')._oleobj_.GetIDsOfNames('Connect'))".
"""
import ctypes
import os
import sys
import winreg

import pythoncom


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    dll = sys.argv[1]
    progid = sys.argv[2] if len(sys.argv) > 2 else 'V83.COMConnector'
    if not os.path.exists(dll):
        sys.exit('нет файла %s' % dll)
    # CLSID берём из библиотеки типов самой dll: там описан coclass коннектора
    tlb = pythoncom.LoadTypeLib(dll)
    clsid = None
    for i in range(tlb.GetTypeInfoCount()):
        ti = tlb.GetTypeInfo(i)
        attr = ti.GetTypeAttr()
        if attr.typekind == pythoncom.TKIND_COCLASS:
            clsid = str(attr.iid)
            break
    if not clsid:
        sys.exit('в библиотеке типов нет coclass')
    name = '1C COM Connector Class (%s)' % progid

    def put(path, value_name, value):
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, path)
        winreg.SetValueEx(k, value_name, 0, winreg.REG_SZ, value)
        winreg.CloseKey(k)

    put(r'Software\Classes\CLSID\%s' % clsid, None, name)
    put(r'Software\Classes\CLSID\%s\InprocServer32' % clsid, None, dll)
    put(r'Software\Classes\CLSID\%s\InprocServer32' % clsid, 'ThreadingModel', 'Both')
    put(r'Software\Classes\CLSID\%s\ProgID' % clsid, None, progid + '.1')
    for pid in (progid, progid + '.1'):
        put(r'Software\Classes\%s' % pid, None, name)
        put(r'Software\Classes\%s\CLSID' % pid, None, clsid)
    ole = ctypes.OleDLL('oleaut32')
    ptl = ctypes.c_void_p()
    ole.LoadTypeLibEx(ctypes.c_wchar_p(dll), 2, ctypes.byref(ptl))       # REGKIND_NONE
    ole.RegisterTypeLibForUser(ptl, ctypes.c_wchar_p(dll), None)
    print('зарегистрировано на пользователя: %s → %s (%s)' % (progid, dll, clsid))
    import win32com.client
    o = win32com.client.Dispatch(progid)
    print('проверка Connect:', 'ok' if o._oleobj_.GetIDsOfNames('Connect') else 'нет')


if __name__ == '__main__':
    main()
