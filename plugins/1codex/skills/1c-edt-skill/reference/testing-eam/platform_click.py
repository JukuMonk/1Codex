# -*- coding: utf-8 -*-
"""Проверка переходов панели показателей (клики по графикам) в тонком клиенте тестовой базы.
В XML-копию (не в проект) добавляется запуск по /C ТестКликовПанели: клиент открывает форму панели и вызывает ее
обработчик ПолеПанелиПриНажатии с адресами «#eam-<действие>» — теми же, что формирует страница (go/hexs в
dashboard.html; hex-параметры кодируются здесь так же, 4 цифры на символ). Ошибка каждого действия (или «ок»)
записывается в ХранилищеОбщихНастроек, скрипт читает итог через COM и снимает окно клиента.
python platform_click.py
Результат: вывод по действиям и scratchpad\\screens\\click_panel.png"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
V8 = r"C:\Program Files\1cv8\8.5.1.1529\bin\1cv8.exe"
W = r"C:\Users\user\AppData\Local\Temp\claude\C--EAM\9bd8956d-7057-4d18-953c-62bdd34cda99\scratchpad\platform"
IB, XML = os.path.join(W, "ib"), os.path.join(W, "xml")
OUT = os.path.join(os.path.dirname(W), "screens")
MARK = "// ТЕСТ-КЛИКИ"


def patch(rel, anchor, add):
    p = os.path.join(XML, rel)
    t = io.open(p, encoding="utf-8-sig", newline="").read()
    t = re.sub(re.escape(MARK) + r" begin.*?" + re.escape(MARK) + r" end\r?\n", "", t, flags=re.S)
    block = MARK + " begin\r\n" + add.replace("\n", "\r\n") + "\r\n" + MARK + " end\r\n"
    if anchor is None:
        t = t.rstrip() + "\r\n\r\n" + block
    else:
        i = t.index(anchor) + len(anchor)
        t = t[:i] + block + t[i:]
    io.open(p, "w", encoding="utf-8-sig", newline="").write(t)


patch(os.path.join("CommonModules", "eamЗатратыВызовСервера", "Ext", "Module.bsl"), None, """
Функция ТестДействияПанели() Экспорт
	Действия = СтрРазделить("oe,defects,orders,schedule,costs,oee", ",");
	Для Каждого Статус Из Метаданные.Перечисления.eamСтатусыЗаказовНаРемонт.ЗначенияПеречисления Цикл
		Действия.Добавить("orders-" + ТестHex(Статус.Имя));
	КонецЦикла;
	Действия.Добавить("orders-" + ТестHex("Неизвестный"));
	Выборка = Справочники.eamОбъектыЭксплуатации.Выбрать();
	Если Выборка.Следующий() Тогда
		Действия.Добавить("nav-" + ТестHex(ПолучитьНавигационнуюСсылку(Выборка.Ссылка)));
	КонецЕсли;
	Действия.Добавить("nav-" + ТестHex("e1cib/list/Справочник.Пользователи"));
	Возврат Действия;
КонецФункции

Функция ТестHex(Строка)
	Цифры = "0123456789abcdef";
	Результат = "";
	Для Номер = 1 По СтрДлина(Строка) Цикл
		Код = КодСимвола(Строка, Номер);
		Часть = "";
		Для Разряд = 1 По 4 Цикл
			Часть = Сред(Цифры, Код % 16 + 1, 1) + Часть;
			Код = Цел(Код / 16);
		КонецЦикла;
		Результат = Результат + Часть;
	КонецЦикла;
	Возврат Результат;
КонецФункции

Процедура ТестЗаписатьКлики(Итог) Экспорт
	ХранилищеОбщихНастроек.Сохранить("ТестКлики", "Итог", Итог);
КонецПроцедуры
""")
patch(os.path.join("DataProcessors", "eamПанельПоказателейEAM", "Forms", "Форма", "Ext", "Form", "Module.bsl"), None, """
&НаКлиенте
Функция ТестКликов(Действия) Экспорт
	Итог = Новый Массив;
	Для Каждого Действие Из Действия Цикл
		Попытка
			ПолеПанелиПриНажатии(Элементы.ПолеПанели, Новый Структура("href", "about:blank#eam-" + Действие), Истина);
			Итог.Добавить(Действие + " => ок");
		Исключение
			Итог.Добавить(Действие + " => ОШИБКА: " + КраткоеПредставлениеОшибки(ИнформацияОбОшибке()));
		КонецПопытки;
	КонецЦикла;
	Возврат СтрСоединить(Итог, Символы.ПС);
КонецФункции
""")
patch(os.path.join("CommonModules", "eamОЕЕГлобальный", "Ext", "Module.bsl"), None, """
Процедура ТестКликовПанели() Экспорт
	Попытка
		Форма = ПолучитьФорму("Обработка.eamПанельПоказателейEAM.Форма.Форма");
		Форма.Открыть();
		Итог = Форма.ТестКликов(eamЗатратыВызовСервера.ТестДействияПанели());
	Исключение
		Итог = "ТЕСТ: " + ПодробноеПредставлениеОшибки(ИнформацияОбОшибке());
	КонецПопытки;
	eamЗатратыВызовСервера.ТестЗаписатьКлики(Итог);
КонецПроцедуры
""")
patch(os.path.join("CommonModules", "ОбщегоНазначенияКлиентПереопределяемый", "Ext", "Module.bsl"),
      "Процедура ПослеНачалаРаботыСистемы() Экспорт\r\n", """	Если СтрНайти(ПараметрЗапуска, "ТестКликовПанели") > 0 Тогда
		ПодключитьОбработчикОжидания("ТестКликовПанели", 10, Истина);
		Возврат;
	КонецЕсли;""")

for args, log in ((["/LoadConfigFromFiles", XML], "k1.log"), (["/UpdateDBCfg"], "k2.log")):
    lp = os.path.join(W, log)
    rc = subprocess.run([V8, "DESIGNER", "/F", IB, "/DisableStartupDialogs", "/DisableStartupMessages"] + args
                        + ["/Out", lp]).returncode
    print(args[0], "код", rc)
    if rc:
        print(open(lp, encoding="utf-8-sig", errors="replace").read()[-2000:])
        sys.exit(1)

import win32com.client
cn = win32com.client.Dispatch("V85.COMConnector").Connect('File="%s";' % IB)
cn.ХранилищеОбщихНастроек.Удалить("ТестКлики", "Итог", "")
subprocess.Popen([V8, "ENTERPRISE", "/F", IB, "/DisableStartupDialogs", "/DisableStartupMessages",
                  "/C", "ТестКликовПанели"])
SHOT = r"""
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class W { [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
public struct R { public int L, T, Rr, B; } }
"@
$c = Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq '1cv8c.exe' -or $_.Name -eq '1cv8.exe') -and $_.CommandLine -like '*%s*' }
$p = $null
foreach ($x in $c) { $q = Get-Process -Id $x.ProcessId -ErrorAction SilentlyContinue; if ($q -and $q.MainWindowHandle -ne 0) { $p = $q } }
if (-not $p) { exit 1 }
$h = $p.MainWindowHandle
[W]::ShowWindow($h, 3) | Out-Null
$r = New-Object W+R; [W]::GetWindowRect($h, [ref]$r) | Out-Null
$bmp = New-Object System.Drawing.Bitmap ($r.Rr - $r.L), ($r.B - $r.T)
$g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
[W]::PrintWindow($h, $dc, 2) | Out-Null
$g.ReleaseHdc($dc); $bmp.Save('%s'); $g.Dispose(); $bmp.Dispose()
"""
os.makedirs(OUT, exist_ok=True)
shot = os.path.join(OUT, "click_panel.png")
итог, t0 = None, time.time()
while time.time() - t0 < 240:
    time.sleep(3)
    try:
        итог = cn.ХранилищеОбщихНастроек.Загрузить("ТестКлики", "Итог")
    except Exception:
        итог = None
    if итог:
        break
time.sleep(8)
subprocess.run(["powershell", "-NoProfile", "-Command", SHOT % (IB, shot)], capture_output=True)
ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -like '1cv8*' } | Where-Object { $_.CommandLine -like '*%s*' }"
      " | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % IB)
subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
print(итог or "итога нет (клиент не дошел до теста) — см. снимок")
print("снимок:", shot if os.path.exists(shot) else "нет")
