# -*- coding: utf-8 -*-
"""Снимок страницы панели показателей с реальными данными тестовой базы (проверка вкладок Asset Intelligence).
В XML-копию (не в проект) в ПостроитьСтраницу формы панели добавляется запись собранной страницы в файл
и пакета карточки актива (объект с наибольшим числом дефектов) — клиент открывает панель на начальной странице,
сервер пишет файлы, скрипт ждёт отметку через COM и закрывает клиент этой базы.
python platform_dash.py
Результат: scratchpad\\dash\\page.html, scratchpad\\dash\\asset.json (открывать в браузере для проверки JS)."""
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
OUT = os.path.join(os.path.dirname(W), "dash")
MARK = "// ТЕСТ-ПАНЕЛЬ"


def patch(rel, anchor, add):
    p = os.path.join(XML, rel)
    t = io.open(p, encoding="utf-8-sig", newline="").read()
    t = re.sub(re.escape(MARK) + r" begin.*?" + re.escape(MARK) + r" end\r?\n", "", t, flags=re.S)
    block = MARK + " begin\r\n" + add.replace("\n", "\r\n") + "\r\n" + MARK + " end\r\n"
    i = t.index(anchor) + len(anchor)
    t = t[:i] + block + t[i:]
    io.open(p, "w", encoding="utf-8-sig", newline="").write(t)


os.makedirs(OUT, exist_ok=True)
for f in ("page.html", "asset.json"):
    if os.path.exists(os.path.join(OUT, f)):
        os.remove(os.path.join(OUT, f))
patch(os.path.join("DataProcessors", "eamПанельПоказателейEAM", "Forms", "Форма", "Ext", "Form", "Module.bsl"),
      "\tHTMLСтраницы = Страница;\r\n", """	Каталог = ХранилищеОбщихНастроек.Загрузить("ТестПанель", "Каталог");
	Если ЗначениеЗаполнено(Каталог) Тогда
		ГраницыТеста = ГраницыПериода();
		Запись = Новый ЗаписьТекста(Каталог + "\\page.html", КодировкаТекста.UTF8);
		Запись.Записать(СтрЗаменить(Страница, "/*EAM_DATA*/null",
			eamПанельПоказателейСервер.ТекстДанныхПанели(ГраницыТеста.Начало, ГраницыТеста.Конец, Подразделение)));
		Запись.Закрыть();
		ЗапросТеста = Новый Запрос("ВЫБРАТЬ ПЕРВЫЕ 1 Д.ОбъектЭксплуатации КАК ОЭ, КОЛИЧЕСТВО(*) КАК К
		|ИЗ Документ.eamВыявленныйДефект КАК Д ГДЕ Д.Проведен СГРУППИРОВАТЬ ПО Д.ОбъектЭксплуатации УПОРЯДОЧИТЬ ПО К УБЫВ");
		ВыборкаТеста = ЗапросТеста.Выполнить().Выбрать();
		Если ВыборкаТеста.Следующий() Тогда
			Запись = Новый ЗаписьТекста(Каталог + "\\asset.json", КодировкаТекста.UTF8);
			Запись.Записать(eamПанельПоказателейСервер.ТекстПакетаАктива(Строка(ВыборкаТеста.ОЭ.УникальныйИдентификатор()), ГраницыТеста.Конец));
			Запись.Закрыть();
		КонецЕсли;
		ХранилищеОбщихНастроек.Сохранить("ТестПанель", "Готово", Истина);
	КонецЕсли;
	ВкладкаТеста = ХранилищеОбщихНастроек.Загрузить("ТестПанель", "Вкладка");
	Если ЗначениеЗаполнено(ВкладкаТеста) Тогда
		ПозицияТеста = СтрНайти(HTMLСтраницы, "</body>", НаправлениеПоиска.СКонца);
		HTMLСтраницы = Лев(HTMLСтраницы, ПозицияТеста - 1) + "<script>var tt = setInterval(function () { if (document.body.className.indexOf('is-loading') >= 0) { return; } clearInterval(tt); var n = document.querySelector('[data-tab=" + ВкладкаТеста + "]'); if (n) { n.click(); } }, 500);</script>" + Сред(HTMLСтраницы, ПозицияТеста);
	КонецЕсли;""")

for args, log in ((["/LoadConfigFromFiles", XML], "d1.log"), (["/UpdateDBCfg"], "d2.log")):
    lp = os.path.join(W, log)
    rc = subprocess.run([V8, "DESIGNER", "/F", IB, "/DisableStartupDialogs", "/DisableStartupMessages"] + args
                        + ["/Out", lp]).returncode
    print(args[0], "код", rc)
    if rc:
        print(open(lp, encoding="utf-8-sig", errors="replace").read()[-2000:])
        sys.exit(1)

import win32com.client  # noqa: E402
cn = win32com.client.Dispatch("V85.COMConnector").Connect('File="%s";' % IB)
cn.ХранилищеОбщихНастроек.Сохранить("ТестПанель", "Каталог", OUT)
cn.ХранилищеОбщихНастроек.Удалить("ТестПанель", "Готово", "")
subprocess.Popen([V8, "ENTERPRISE", "/F", IB, "/DisableStartupDialogs", "/DisableStartupMessages"])
ok, t0 = False, time.time()
while time.time() - t0 < 300:
    time.sleep(3)
    try:
        ok = bool(cn.ХранилищеОбщихНастроек.Загрузить("ТестПанель", "Готово"))
    except Exception:
        ok = False
    if ok:
        break
time.sleep(3)
cn.ХранилищеОбщихНастроек.Удалить("ТестПанель", "Каталог", "")
ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -like '1cv8*' } | Where-Object { $_.CommandLine -like '*%s*' }"
      " | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % IB)
subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
for f in ("page.html", "asset.json"):
    p = os.path.join(OUT, f)
    print(f, os.path.getsize(p) if os.path.exists(p) else "НЕТ")
print("готово" if ok else "клиент не открыл панель за 5 минут")

SHOT = r"""
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class W { [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
public struct R { public int L, T, Rr, B; } }
"@
[W]::SetProcessDPIAware() | Out-Null
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
for tab in sys.argv[1:]:
    cn.ХранилищеОбщихНастроек.Сохранить("ТестПанель", "Вкладка", tab)
    subprocess.Popen([V8, "ENTERPRISE", "/F", IB, "/DisableStartupDialogs", "/DisableStartupMessages"])
    time.sleep(45)
    shot = os.path.join(OUT, "client_%s.png" % tab)
    if os.path.exists(shot):
        os.remove(shot)
    r = subprocess.run(["powershell", "-NoProfile", "-Command", SHOT % (IB, shot)], capture_output=True, text=True,
                       encoding="cp866", errors="replace")
    if r.returncode:
        print("  снимок: код", r.returncode, (r.stderr or "")[-400:])
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    print("снимок клиента:", tab, "ok" if os.path.exists(shot) else "НЕТ")
    time.sleep(15)   # после принудительного закрытия клиенту нужна пауза, иначе следующий запуск не открывает окно
cn.ХранилищеОбщихНастроек.Удалить("ТестПанель", "Вкладка", "")
