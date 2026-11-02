# -*- coding: utf-8 -*-
"""Снимки вкладок панели показателей в headless Edge по странице, снятой platform_dash.py (реальные данные).
Для каждой вкладки создаётся вариант страницы с добавленным скриптом: переключить вкладку, выбрать фокус/объект,
подать пакет карточки актива (asset.json) через поля обмена in_package — как это делает 1С.
python dash_shots.py [вкладка ...]      (по умолчанию все: sum map risk deg causes links costs + варианты с объектом)
Результат: scratchpad\\dash\\shot_<имя>.png; ошибки страницы — в строке js_errors (видны на снимке) и в выводе."""
import io
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DASH = r"C:\Users\user\AppData\Local\Temp\claude\C--EAM\9bd8956d-7057-4d18-953c-62bdd34cda99\scratchpad\dash"
page = io.open(os.path.join(DASH, "page.html"), encoding="utf-8").read().lstrip("\ufeff")
asset = io.open(os.path.join(DASH, "asset.json"), encoding="utf-8").read().lstrip("\ufeff")
if "--fresh" in sys.argv:
    # \u0441\u0432\u0435\u0436\u0438\u0439 G9_assets\dashboard.html + \u0434\u0430\u043d\u043d\u044b\u0435 \u0438 \u0431\u0438\u0431\u043b\u0438\u043e\u0442\u0435\u043a\u0430 \u0438\u0437 \u0441\u043d\u044f\u0442\u043e\u0439 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u044b (\u0431\u0435\u0437 \u043f\u043e\u0432\u0442\u043e\u0440\u043d\u043e\u0433\u043e \u043f\u0440\u043e\u0433\u043e\u043d\u0430 1\u0421)
    sys.argv.remove("--fresh")
    tpl = io.open(r"C:\EAM\gen\tz\G9_assets\dashboard.html", encoding="utf-8").read().lstrip("\ufeff")
    head = "window.EAM_DATA = "
    i = page.rindex(head) + len(head)
    data = page[i:page.index("</script>", i)].rstrip().rstrip(";")
    lib_js = io.open(r"C:\EAM\gen\tz\G9_assets\echarts.min.js", encoding="utf-8").read()
    page = tpl.replace("/*EAM_DATA*/null", data, 1).replace("/*EAM_LIB*/", lib_js, 1)
uid = json.loads(asset)["u"]

# сценарий: вкладка, выбрать ли объект из asset.json, фокус на цех (индекс техместа первого уровня с объектами)
CASES = {
    "sum": ("sum", False, False), "map": ("map", False, False), "risk": ("risk", False, False),
    "deg": ("deg", False, False), "causes": ("causes", False, False), "links": ("links", False, False),
    "costs": ("costs", False, False), "map_asset": ("map", True, False), "deg_asset": ("deg", True, False),
    "links_asset": ("links", True, False), "map_shop": ("map", False, True), "costs_shop": ("costs", False, True),
    "risk_shop": ("risk", False, True), "map_fs": ("map", False, False), "map_shop_fs": ("map", False, True),
}
names = sys.argv[1:] or list(CASES)
for name in names:
    tab, sel, shop = CASES[name]
    hook = """
<script>
(function () {
  function click(sel) { var n = document.querySelector(sel); if (n) { n.click(); } }
  click('[data-tab="%(tab)s"]');
  if (%(fs)s) { setTimeout(function () { click('[data-fs="card-sun"]'); }, 200); }
  if (%(shop)s) {
    var c = document.querySelector('#crumbs'); // фокус на цех с наибольшим числом объектов — через клик по строке сравнения недоступен, берём данные
    var P = window.EAM_DATA.ai.places, A = window.EAM_DATA.ai.assets, cnt = {}, best = -1;
    for (var i = 0; i < A.length; i++) { if (A[i].shop >= 0) { cnt[A[i].shop] = (cnt[A[i].shop] || 0) + 1; } }
    for (var k in cnt) { if (best < 0 || cnt[k] > cnt[best]) { best = +k; } }
    var tmp = document.createElement('span'); tmp.setAttribute('data-place', best); document.body.appendChild(tmp); tmp.click();
  }
  if (%(sel)s) {
    var A2 = window.EAM_DATA.ai.assets;
    for (var j = 0; j < A2.length; j++) {
      if (A2[j].u === '%(uid)s') { var s = document.createElement('span'); s.setAttribute('data-asset', A2[j].unit); document.body.appendChild(s); s.click(); }
    }
    setTimeout(function () {
      var txt = %(asset)s;
      document.getElementById('in_package').value = txt;
      document.getElementById('in_package_sig').value = txt.length + '|99';
    }, 300);
  }
})();
</script>
</body>""" % {"tab": tab, "sel": "true" if sel else "false", "fs": "true" if name.endswith("_fs") else "false", "shop": "true" if shop else "false", "uid": uid,
              "asset": json.dumps(asset, ensure_ascii=False).replace("</", "<\\/")}
    cut = page.rfind("</body>")   # «</body>» встречается и внутри текста библиотеки ECharts — берём последний
    html = page[:cut] + hook + page[cut + len("</body>"):]
    p = os.path.join(DASH, "t_%s.html" % name)
    io.open(p, "w", encoding="utf-8").write(html)
    out = os.path.join(DASH, "shot_%s.png" % name)
    if os.path.exists(out):
        os.remove(out)
    subprocess.run([EDGE, "--headless", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--window-size=1600,1500",
                    "--user-data-dir=" + os.path.join(DASH, "edgeprof"), "--virtual-time-budget=8000",
                    "--screenshot=" + out, "file:///" + p.replace("\\", "/")], capture_output=True, timeout=120)
    t0 = time.time()   # msedge.exe возвращается раньше, чем headless-процесс запишет снимок
    while not os.path.exists(out) and time.time() - t0 < 60:
        time.sleep(1)
    time.sleep(1)
    print(name, "ok" if os.path.exists(out) else "НЕТ СНИМКА")
