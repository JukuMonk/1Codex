"""Обработка выгрузки данных в конфигурации ЛОКАЛЬНОЙ копии базы (кейс 080).

Внешняя обработка через /Execute ждёт ответа на «Предупреждение безопасности», внешнее соединение может быть
запрещено ролью — поэтому обработка добавляется в конфигурацию копии и открывается навигационной ссылкой.
Исходная выгрузка конфигурации (config/) не меняется — правка в копии каталога (config_work/). Загрузка частичная
(Configuration.xml + новые файлы), затем обновление конфигурации БД.

    python make_export_dp.py platform.json

platform.json (вне git): {"v8": "…\\8.5.1.1529\\bin\\1cv8.exe", "ib_path": "C:\\Базы\\Копия", "user": "…",
"pwd": "…", "config": "…\\config", "work": "…\\config_work", "out": "…\\data"}
"""

import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, r"C:\1c-edt-skill\tools")
import designer_lib as dl  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "ВыгрузкаДляНоды"


def main(settings_path: str) -> int:
    cfg = json.load(open(settings_path, encoding="utf-8"))
    dl.VERSION = "2.21"  # формат выгрузки 8.5.1; по умолчанию designer_lib пишет 2.20 (8.3.27)
    if not os.path.isdir(cfg["work"]):
        shutil.copytree(cfg["config"], cfg["work"])
    module = open(os.path.join(HERE, "ВыгрузкаВJSON.bsl"), encoding="utf-8-sig").read()
    key = "DataProcessor." + NAME
    files = {
        f"DataProcessors/{NAME}.xml": dl.data_processor_xml(NAME, "Выгрузка данных", forms=["Форма"]),
        f"DataProcessors/{NAME}/Forms/Форма.xml": dl.form_meta_xml(key, "Форма", "Выгрузка данных"),
    }
    form = dl.Form("Выгрузка данных")
    form.attr("Объект", "cfg:DataProcessorObject." + NAME, main=True)
    # Работа — при создании формы на сервере, закрытие сеанса — при открытии: клиент завершается сам.
    files[f"DataProcessors/{NAME}/Forms/Форма/Ext/Form.xml"] = form.xml(
        events={"OnCreateAtServer": "ПриСозданииНаСервере", "OnOpen": "ПриОткрытии"}
    )
    files[f"DataProcessors/{NAME}/Forms/Форма/Ext/Form/Module.bsl"] = module.replace("%OUT%", cfg["out"])
    for rel, text in files.items():
        dl.write(os.path.join(cfg["work"], *rel.split("/")), text)
    dl.register_in_configuration(cfg["work"], "DataProcessor", NAME)
    cred = {"user": cfg["user"], "pwd": cfg["pwd"]}
    log = os.path.join(HERE, "load_dp.log")
    code, text, seconds = dl.load_files(cfg["v8"], cfg["ib_path"], cfg["work"], list(files), log, **cred)
    print("загрузка в копию:", code, round(seconds, 1), "с", text[-600:])
    if code:
        return code
    # Применит и отложенные изменения рабочей базы, если они были (урок 5): журнал прочитать.
    code, text, seconds = dl.update_db(cfg["v8"], cfg["ib_path"], log, **cred)
    print("обновление БД:", code, round(seconds, 1), "с", text[-600:])
    if code:
        return code
    client = cfg["v8"].replace("1cv8.exe", "1cv8c.exe")
    command = (
        f'"{client}" ENTERPRISE /F"{cfg["ib_path"]}" /N"{cfg["user"]}" /P"{cfg["pwd"]}" '
        f'/DisableStartupDialogs /DisableStartupMessages /URL "e1cib/app/Обработка.{NAME}"'
    )
    started = time.time()
    proc = subprocess.Popen(command)
    try:
        code = proc.wait(timeout=1200)
        print("клиент завершился:", code, round(time.time() - started, 1), "с")
    except subprocess.TimeoutExpired:
        print("клиент не завершился за 20 минут — останавливаю")
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        return 1
    journal = os.path.join(cfg["out"], "_журнал.json")
    if os.path.exists(journal):
        for item in json.load(open(journal, encoding="utf-8-sig")):
            if item["count"]:
                print(f"  {item['object']}: {item['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
