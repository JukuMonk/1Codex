# -*- coding: utf-8 -*-
"""Временное расширение «НПЦАП_ИсправленияОбновления» — обход ошибок обработчиков обновления поставщика
при прямом переходе 3.0.8.1 → 3.0.25.3 (без промежуточных релизов).

Причина: обработчики старых версий (напр. 3.0.13.1 ЗаменитьШаблоныУведомленийНаБСППрочиеМеста) в коде
3.0.25.3 ссылаются на объекты, которые поставщик потом переименовал в «Удалить…». При обновлении через
промежуточные релизы они выполнились бы на своей версии; при скачке падают на любых данных.
Расширение перехватывает такие методы (&ИзменениеИКонтроль) с заменой имён. Подключается ТОЛЬКО на время
обновления ИБ и удаляется после него (роли не меняет — БСП обновляет ИБ с ним).

  python tools/update_fix_ext.py <база>          # собрать, загрузить, обновить БД расширения
  python tools/update_fix_ext.py <база> удалить
"""
import os
import re
import sys

os.environ.setdefault('NPCAP_TARGET', '3.0.25.3')
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ext as be  # noqa: E402
import bsl_methods as bm  # noqa: E402
import com  # noqa: E402
import v8  # noqa: E402

dl, t = be.dl, be.t
NAME = 'НПЦАП_ИсправленияОбновления'
OUT = os.path.join(be.ROOT, 'src', 'update_fix', NAME)
ОИБ = 'CommonModules/торо_ОбновлениеИнформационнойБазы/Ext/Module.bsl'
УВ = ('торо_НастройкиУведомлений', 'Удалитьторо_НастройкиУведомлений')
# (модуль, метод) → [(было, стало)] — замены во всём тексте метода
FIXES = {
    (ОИБ, 'ЗаменитьШаблоныУведомленийНаБСП_УведомленияПоДокументам'): [
        ('РегистрСведений.торо_НастройкиУведомлений', 'РегистрСведений.Удалитьторо_НастройкиУведомлений'),
        ('РегистрыСведений.торо_НастройкиУведомлений', 'РегистрыСведений.Удалитьторо_НастройкиУведомлений')],
    (ОИБ, 'ЗаменитьШаблоныУведомленийНаБСППрочиеМеста'): [
        ('Метаданные.РегистрыСведений.торо_НастройкиУведомлений', 'Метаданные.РегистрыСведений.Удалитьторо_НастройкиУведомлений')],
}


def build():
    import shutil
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    w = lambda rel, txt: dl.write(os.path.join(OUT, rel), txt)
    modules = {}
    for (mod, meth), reps in FIXES.items():
        ms, _ = bm.parse(bm.read(os.path.join(be.TARGET, mod)))
        m = next(x for x in ms if x.name == meth)
        lines = list(m.lines)
        for old, new in reps:
            n = sum(l.count(old) for l in lines)
            if not n:
                raise SystemExit('нет «%s» в %s' % (old, meth))
            lines = [l.replace(old, new) for l in lines]
        txt = be.Ext.intercept(None, m, bm.Method(m.name, m.kind, m.ann, lines, 0), set()).replace(
            be.PREFIX + m.name + '(', 'иоб_' + m.name + '(', 1)
        modules.setdefault(mod, []).append(txt)
    children = {'Language': ['Русский'], 'CommonModule': []}
    for mod, texts in modules.items():
        name = mod.split('/')[1]
        ve = be.root_elem(os.path.join(be.TARGET, 'CommonModules', name + '.xml'))
        p = [t(1) + '<CommonModule uuid="%s">' % dl.uid(NAME, name), be.internal_info(ve, NAME + name, ('Module',))]
        p += be.adopted_props('CommonModule', ve, 2) + [t(1) + '</CommonModule>']
        w(os.path.join('CommonModules', name + '.xml'), be.md_header() + '\n'.join(p) + '\n</MetaDataObject>')
        w(mod.replace('/', os.sep), '\n\n'.join(texts) + '\n')
        children['CommonModule'].append(name)
    ve = be.root_elem(os.path.join(be.TARGET, 'Languages', 'Русский.xml'))
    p = [t(1) + '<Language uuid="%s">' % dl.uid(NAME, 'Language'), t(2) + '<InternalInfo/>']
    p += be.adopted_props('Language', ve, 2) + [t(1) + '</Language>']
    w(os.path.join('Languages', 'Русский.xml'), be.md_header() + '\n'.join(p) + '\n</MetaDataObject>')
    cfg = be.rd(os.path.join(be.OUT, 'Configuration.xml'))
    head = cfg[:cfg.index('<ChildObjects>')]
    head = head.replace('<Name>%s</Name>' % be.EXT_NAME, '<Name>%s</Name>' % NAME).replace('<NamePrefix>дс_</NamePrefix>', '<NamePrefix>иоб_</NamePrefix>')
    head = re.sub(r'(<xr:ObjectId>|Configuration uuid=")([0-9a-f-]{36})', lambda m: m.group(1) + dl.uid(NAME, m.group(2)), head)
    w('Configuration.xml', head + dl.configuration_child_objects(children).lstrip('\t') + '\n\t</Configuration>\n</MetaDataObject>')


def install(base):
    ib = os.path.join(be.ROOT, base)
    build()
    if v8.run('DESIGNER', '/LoadConfigFromFiles "%s" -Extension "%s"' % (OUT, NAME), 'fix_load.log', ib=ib) or \
       v8.run('DESIGNER', '/UpdateDBCfg -Extension "%s"' % NAME, 'fix_update.log', ib=ib):
        return 1
    cn = com.connect(base)
    for e in cn.РасширенияКонфигурации.Получить():
        if e.Имя == NAME:
            защита = cn.NewObject('ОписаниеЗащитыОтОпасныхДействий')
            защита.ПредупреждатьОбОпасныхДействиях = False
            e.ЗащитаОтОпасныхДействий = защита
            e.БезопасныйРежим = False
            e.Записать()
    return 0


def remove(base):
    return v8.run('DESIGNER', '/DeleteCfg -Extension "%s"' % NAME, 'fix_delete.log', ib=os.path.join(be.ROOT, base))


if __name__ == '__main__':
    a = sys.argv[1:]
    sys.exit(remove(a[0]) if a[1:2] == ['удалить'] else install(a[0]))
