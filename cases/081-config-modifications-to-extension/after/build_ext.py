# -*- coding: utf-8 -*-
"""Расширение «НПЦАП_Доработки»: все доработки ПРОД относительно поставки ТОИР КОРП 3.0.8.1 — генератор XML.

Источники: src/vendor (выгрузка поставки из ParentConfigurations ПРОД) и src/cf (выгрузка ПРОД);
список различий — logs/diff.json (tools/diff_cf.py). Результат — src/ext/НПЦАП_Доработки (формат выгрузки
Конфигуратора 8.3.27), грузится ЦЕЛИКОМ: /LoadConfigFromFiles -Extension.

Правила переноса:
  * новые объекты (41, дс_*) — как есть, своими объектами расширения (uuid ПРОД сохраняются);
  * новые реквизиты/ТЧ/ресурсы/измерения/макеты типовых — в заимствованный объект (uuid ПРОД сохраняются);
  * изменённые макеты типовых (СКД отчётов) — заимствованный макет с замещённым содержимым;
  * модули: новые методы — как есть; изменённые — &ИзменениеИКонтроль с #Вставка/#Удаление по diff;
  * формы: заимствуются минимально (без элементов) только ради модуля; новая кнопка «Заказ-наряд» общего
    плана работ создаётся в коде (&После ПриСозданииНаСервере);
  * типовые объекты, на которые ссылаются типы/права/состав новых объектов, — заимствуются пустыми.

  python tools/build_ext.py                # собрать src/ext/НПЦАП_Доработки
  python tools/build_ext.py --only X,Y     # только перечисленные типовые объекты (пробы), напр. Catalogs/торо_РемонтныеБригады
"""
import copy
import difflib
import io
import json
import os
import re
import shutil
import sys

from lxml import etree

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\1c-edt-skill\tools')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import designer_lib as dl  # noqa: E402
import bsl_methods as bm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(ROOT, 'src', 'vendor')          # поставка, на которой сделаны доработки ПРОД (3.0.8.1)
PROD = os.path.join(ROOT, 'src', 'cf')
EXT_NAME = 'НПЦАП_Доработки'
PREFIX = 'дс_'
# Профиль — поставка, ПОД КОТОРУЮ собирается расширение (env NPCAP_TARGET):
#   3.0.8.1  — та же, что у ПРОД; совместимость 8.3.21: поля типовых регистров — в регистры-спутники;
#   3.0.25.3 — новая поставка; совместимость 8.3.25: поля добавляются в заимствованные регистры как в ПРОД;
#              изменённые поставщиком методы — трёхстороннее слияние (git merge-file).
TARGET_VERSION = os.environ.get('NPCAP_TARGET', '3.0.8.1')
PROFILES = {'3.0.8.1': ('vendor', 'Version8_3_21', 'ext'), '3.0.25.3': ('vendor_new', 'Version8_3_25', 'ext_3.0.25')}
_t = PROFILES[TARGET_VERSION]
TARGET = os.path.join(ROOT, 'src', _t[0])
COMPAT = _t[1]
OUT = os.path.join(ROOT, 'src', _t[2], EXT_NAME)
# 8.3.25 тоже не позволяет добавлять поля в заимствованные регистры (проверено загрузкой) — спутники в обоих профилях
SHADOW_MODE = True
RES_NEW = os.path.join(ROOT, 'tools', 'resolutions_new')        # перехваты методов новой поставки
RES_EXTRA = os.path.join(ROOT, 'tools', 'resolutions_extra')    # доп. методы модулей (целиком)
RES_TPL = os.path.join(ROOT, 'tools', 'resolutions_templates')  # макеты (схемы СКД) целиком
OVERLAY = os.path.join(ROOT, 'tools', 'overlay', TARGET_VERSION)  # свои объекты (файлы) и новые методы Деснол под поставку

MD = 'http://v8.1c.ru/8.3/MDClasses'
XR = 'http://v8.1c.ru/8.3/xcf/readable'
N = '{%s}' % MD
DIR_KIND = {v: k for k, v in dl.KIND_DIRS.items()}
DIR_KIND.update({'FunctionalOptions': 'FunctionalOption', 'FunctionalOptionsParameters': 'FunctionalOptionsParameter',
                 'ExchangePlans': 'ExchangePlan', 'ChartsOfCharacteristicTypes': 'ChartOfCharacteristicTypes',
                 'StyleItems': 'StyleItem', 'CommandGroups': 'CommandGroup', 'DocumentJournals': 'DocumentJournal',
                 'BusinessProcesses': 'BusinessProcess', 'Tasks': 'Task', 'FilterCriteria': 'FilterCriterion',
                 'CommonAttributes': 'CommonAttribute', 'XDTOPackages': 'XDTOPackage', 'WebServices': 'WebService',
                 'SettingsStorages': 'SettingsStorage'})
KIND_DIR = {k: v for v, k in DIR_KIND.items()}
t = dl.t


def uid(*parts):
    return dl.uid(EXT_NAME, *parts)


def rd(path):
    with io.open(path, encoding='utf-8-sig', newline='') as f:
        return f.read()


def wr(rel, text):
    dl.write(os.path.join(OUT, rel), text)


def md_header():
    return '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject %s version="%s">\n' % (dl.MD_NS, dl.VERSION)


def obj_path(base, rel_obj):
    """rel_obj: 'Catalogs/Имя' или 'Subsystems/A/Subsystems/B' → путь к .xml"""
    return os.path.join(base, rel_obj.replace('/', os.sep) + '.xml')


def root_elem(path):
    return list(etree.parse(path).getroot())[0]


def ser(e, level):
    """Элемент lxml → текст с отступом level (табуляции), без объявлений пространств имён."""
    s = etree.tostring(e, encoding='unicode')
    s = re.sub(r'\s+xmlns(:\w+)?="[^"]+"', '', s, count=0) if False else s
    # убрать xmlns, которые lxml добавляет в корень вырезанного фрагмента
    s = re.sub(r' xmlns(?::\w+)?="[^"]*"', '', s)
    s = s.rstrip()
    first_indent = t(level)
    lines = s.split('\n')
    # отступ исходного фрагмента: у последующих строк уже есть табуляции исходного уровня
    src_level = None
    for l in lines[1:]:
        m = re.match(r'^(\t*)</', l)
        if m and l.strip().startswith('</' + etree.QName(e).localname):
            src_level = len(m.group(1))
    if src_level is None:
        src_level = level
    out = [first_indent + lines[0]]
    for l in lines[1:]:
        tabs = len(l) - len(l.lstrip('\t'))
        out.append(t(max(0, tabs - src_level + level)) + l.lstrip('\t'))
    return '\n'.join(out)


# ---------------------------------------------------------------- заимствование
def internal_info(vendor_elem, key, states=(), level=2):
    """InternalInfo заимствованного объекта: GeneratedType поставщика с новыми id + PropertyState."""
    ii = vendor_elem.find(N + 'InternalInfo')
    p = []
    if ii is not None:
        if ii.find('{%s}ThisNode' % XR) is not None:          # план обмена
            p.append(t(level + 1) + '<xr:ThisNode>%s</xr:ThisNode>' % uid(key, 'ThisNode'))
        for g in ii.findall('{%s}GeneratedType' % XR):
            name, cat = g.get('name'), g.get('category')
            p += [t(level + 1) + '<xr:GeneratedType name="%s" category="%s">' % (name, cat),
                  t(level + 2) + '<xr:TypeId>%s</xr:TypeId>' % uid(key, name, 'type'),
                  t(level + 2) + '<xr:ValueId>%s</xr:ValueId>' % uid(key, name, 'value'),
                  t(level + 1) + '</xr:GeneratedType>']
    for s in states:
        p += [t(level + 1) + '<xr:PropertyState>', t(level + 2) + '<xr:Property>%s</xr:Property>' % s,
              t(level + 2) + '<xr:State>Extended</xr:State>', t(level + 1) + '</xr:PropertyState>']
    if not p:
        return t(level) + '<InternalInfo/>'
    return '\n'.join([t(level) + '<InternalInfo>'] + p + [t(level) + '</InternalInfo>'])


# свойства, которые выгрузка повторяет у заимствованного объекта (по образцам АЗОТ)
KEEP_PROPS = {
    'CommonModule': ('Global', 'ClientManagedApplication', 'Server', 'ExternalConnection', 'ClientOrdinaryApplication',
                     'ServerCall'),
    'Form': ('FormType',),
    'Template': ('TemplateType',),
    'Language': ('LanguageCode',),
    'Attribute': ('Type',), 'Dimension': ('Type',), 'Resource': ('Type',),
}
HAS_CHILDREN = {'Catalog', 'Document', 'Enum', 'InformationRegister', 'AccumulationRegister', 'ChartOfCharacteristicTypes',
                'ExchangePlan', 'DataProcessor', 'Report', 'Subsystem', 'BusinessProcess', 'Task', 'DocumentJournal',
                'ChartOfAccounts', 'ChartOfCalculationTypes', 'FilterCriterion', 'SettingsStorage',
                'AccountingRegister', 'CalculationRegister', 'Configuration'}


def adopted_props(kind, vendor_elem, level, extra=()):
    vp = vendor_elem.find(N + 'Properties')
    p = [t(level) + '<Properties>',
         t(level + 1) + '<ObjectBelonging>Adopted</ObjectBelonging>',
         t(level + 1) + '<Name>%s</Name>' % vp.find(N + 'Name').text,
         t(level + 1) + '<Comment/>',
         t(level + 1) + '<ExtendedConfigurationObject>%s</ExtendedConfigurationObject>' % vendor_elem.get('uuid')]
    for name in KEEP_PROPS.get(kind, ()):
        e = vp.find(N + name)
        if e is not None:
            p.append(ser(e, level + 1))
    p += list(extra)
    if kind == 'Subsystem' and not any('<Content' in x for x in extra):
        p.append(t(level + 1) + '<Content/>')
    p.append(t(level) + '</Properties>')
    return p


class Ext:
    def __init__(self, only=None):
        self.diff = json.load(open(os.path.join(ROOT, 'logs', 'diff.json'), encoding='utf-8'))
        self.only = only
        self.children = {}          # вид → [имена] для Configuration.xml
        self.adopted = {}           # 'Catalogs/Имя' → спецификация
        self.native = []            # 'Catalogs/Имя' своих объектов
        self.log = []
        self.conflicts = []
        self.res_files = set()

    # -------------------------------------------------------------- план
    def plan(self):
        for o in self.diff['new_objects']:
            d, name = o.split('.', 1)
            self.native.append(d + '/' + name)
        files = self.diff['added'] + self.diff['changed']
        for p in files:
            parts = p.split('/')
            if len(parts) == 1 or parts[0] == 'Ext':
                continue                                    # Configuration.xml — состав строится заново
            rel_obj = self._owner(parts)
            if rel_obj in self.native:
                continue
            if self.only and rel_obj not in self.only:
                continue
            spec = self.adopted.setdefault(rel_obj, dict(files=[]))
            spec['files'].append(p)
        # объекты, которых касаются ручные решения переноса на новую поставку (tools/resolutions_*)
        if TARGET != VENDOR:
            for base, kind in ((RES_NEW, 'new'), (RES_EXTRA, 'extra'), (RES_TPL, 'tpl')):
                for d, _, fs in os.walk(base):
                    for f in fs:
                        rf = os.path.relpath(os.path.join(d, f), base).replace(os.sep, '/')
                        if kind == 'new':
                            rf = os.path.dirname(rf)                  # <модуль>/<метод>.bsl → модуль
                        spec = self.adopted.setdefault(self._owner(rf.split('/')), dict(files=[]))
                        if rf not in spec['files']:
                            spec['files'].append(rf)
                        self.res_files.add(rf)
        # родители заимствованных вложенных подсистем — тоже заимствованные
        for rel_obj in list(self.adopted):
            op = rel_obj.split('/')
            while len(op) > 2:
                op = op[:-2]
                self.adopted.setdefault('/'.join(op), dict(files=[]))

    def _owner(self, parts):
        """Объект-владелец файла: подсистемы вложенные (Subsystems/A/Subsystems/B…)."""
        if parts[0] == 'Subsystems':
            i, owner = 0, []
            while i + 1 < len(parts) and parts[i] == 'Subsystems':
                owner += [parts[i], parts[i + 1].replace('.xml', '')]
                i += 2
                if i >= len(parts) or parts[i] != 'Subsystems':
                    break
            return '/'.join(owner)
        return parts[0] + '/' + parts[1].replace('.xml', '')

    # -------------------------------------------------------------- сборка
    def build(self):
        if os.path.isdir(OUT):
            shutil.rmtree(OUT)
        self.plan()
        for rel in self.native:
            self.copy_native(rel)
        for name, spec in SHADOW.items():
            self.shadow_register(name, *spec)
        for rel in sorted(self.adopted):
            if rel in ACCEPTED_BY_VENDOR.get(TARGET_VERSION, ()):
                self.log.append('%s: доработку включил поставщик %s — не переносится' % (rel, TARGET_VERSION))
                continue
            if not os.path.exists(obj_path(TARGET, rel)):
                self.conflicts.append((rel, '(объект)', 'нет в поставке %s — удалён или переименован' % TARGET_VERSION))
                continue
            self.build_adopted(rel)
        self.text_rewrites()
        self.adopt_references()
        self.language()
        self.configuration()
        print('поставка %s: своих объектов %d, заимствованных %d, конфликтов %d' % (
            TARGET_VERSION, len(self.native), len(self.adopted), len(self.conflicts)))
        for c in self.conflicts:
            print('  КОНФЛИКТ %s: %s — %s' % c)
        for l in self.log:
            print(' ', l)

    def add_child(self, kind, name):
        lst = self.children.setdefault(kind, [])
        if name not in lst:
            lst.append(name)

    # своё: копия файлов ПРОД ------------------------------------------------
    def copy_native(self, rel):
        d, name = rel.split('/')
        src_xml = obj_path(PROD, rel)
        dst = os.path.join(OUT, d)
        os.makedirs(dst, exist_ok=True)
        shutil.copy2(src_xml, os.path.join(dst, name + '.xml'))
        if os.path.isdir(os.path.join(PROD, d, name)):
            shutil.copytree(os.path.join(PROD, d, name), os.path.join(dst, name))
        ov = os.path.join(OVERLAY, d, name)
        if TARGET != VENDOR and os.path.isdir(ov):              # свои объекты, исправленные под новую поставку
            for dd, _, fs in os.walk(ov):
                for f in fs:
                    rf = os.path.relpath(os.path.join(dd, f), ov)
                    shutil.copy2(os.path.join(dd, f), ensure_dir(os.path.join(dst, name, rf)))
                    self.log.append('%s: %s — версия под %s' % (rel, rf, TARGET_VERSION))
        if d == 'Roles':
            rp = os.path.join(dst, name, 'Ext', 'Rights.xml')
            txt = rd(rp).replace('<name>Configuration.ТехническоеОбслуживаниеИРемонты3</name>',
                                 '<name>Configuration.%s</name>' % EXT_NAME)
            dl.write(rp, txt)
        self.add_child(DIR_KIND[d], name)

    # заимствованное с изменениями -----------------------------------------
    def build_adopted(self, rel):
        spec = self.adopted[rel]
        parts = rel.split('/')
        d, name = parts[-2], parts[-1]
        kind = DIR_KIND[d]
        if kind == 'CommonForm':
            self.adopted_form(rel, None)
            self.add_child(kind, name)
            return
        vpath, ppath = obj_path(TARGET, rel), obj_path(PROD, rel)
        ve = root_elem(vpath)
        pe = root_elem(ppath) if os.path.exists(ppath) else ve           # объект новой поставки — правки только решениями
        vo = root_elem(obj_path(VENDOR, rel)) if os.path.exists(obj_path(VENDOR, rel)) else ve
        files = spec['files']
        states, extra, child_lines = [], [], []
        obj_dir = rel                                                    # папка объекта в выгрузке

        # модули объекта
        for mod, state in (('ObjectModule', 'ObjectModule'), ('ManagerModule', 'ManagerModule'),
                           ('RecordSetModule', 'RecordSetModule'), ('Module', 'Module'),
                           ('CommandInterface', 'CommandInterface')):
            ext = '.xml' if mod == 'CommandInterface' else '.bsl'
            f = obj_dir + '/Ext/' + mod + ext
            if f in files:
                if mod == 'CommandInterface':
                    self.command_interface(f)
                    states.append(state)
                elif self.module(f, f):
                    states.append(state)
        if obj_dir + '/Ext/Rights.xml' in files:
            self.role_rights(rel)
            states.append('Rights')

        # изменённые свойства самого объекта
        meta = self.meta_diff(rel) if (rel + '.xml') in files else dict(added=[], props=[], changed=[], removed=[])
        for prop in meta['props']:
            extra += self.extended_prop(kind, prop, vo, pe)
        if rel in EXTRA_REGISTER_RECORDS:
            items = [t(4) + '<xr:Item xsi:type="xr:MDObjectRef">%s</xr:Item>' % x for x in EXTRA_REGISTER_RECORDS[rel]]
            for i, x in enumerate(extra):
                if '<RegisterRecords>' in x:
                    extra[i] = x.replace('</RegisterRecords>', '\n'.join(items).lstrip('\t') + '\n' + t(3) + '</RegisterRecords>')
                    break
            else:
                extra.append('\n'.join([t(3) + '<RegisterRecords>'] + items + [t(3) + '</RegisterRecords>']))

        # дочерние: новые элементы ПРОД, заимствованные ТЧ, формы, макеты
        added = set(meta['added'])
        forms = sorted({f.split('/')[len(parts) + 1] for f in files if f.startswith(obj_dir + '/Forms/')})
        tmpl_changed = sorted({f.split('/')[len(parts) + 1] for f in files
                               if f.startswith(obj_dir + '/Templates/') and (f in self.diff['changed'] or f in self.res_files)})
        pco = pe.find(N + 'ChildObjects')
        vco = ve.find(N + 'ChildObjects')
        vchild = {}
        if vco is not None:
            for ch in vco:
                if len(ch):
                    vchild[(etree.QName(ch).localname, ch.find(N + 'Properties').find(N + 'Name').text)] = ch
        if pco is not None:
            for ch in pco:
                k = etree.QName(ch).localname
                if len(ch) == 0:                                       # Form/Template ссылкой
                    nm = ch.text
                    if k == 'Form' and nm in forms:
                        child_lines.append(t(3) + '<Form>%s</Form>' % nm)
                        self.adopted_form(rel, nm)
                    elif k == 'Template' and ('Template.' + nm in added):
                        child_lines.append(t(3) + '<Template>%s</Template>' % nm)
                        for f in files:
                            if f.startswith(obj_dir + '/Templates/%s.xml' % nm) or f.startswith(obj_dir + '/Templates/%s/' % nm):
                                ovf = os.path.join(OVERLAY, 'templates', f.replace('/', os.sep))
                                if TARGET != VENDOR and os.path.exists(ovf):   # макет Деснол под новую поставку
                                    shutil.copy2(ovf, ensure_dir(os.path.join(OUT, f.replace('/', os.sep))))
                                    self.log.append('%s — версия под %s' % (f, TARGET_VERSION))
                                else:
                                    shutil_copy(PROD, OUT, f)
                    elif k == 'Template' and nm in tmpl_changed:
                        child_lines.append(t(3) + '<Template>%s</Template>' % nm)
                        self.adopted_template(rel, nm)
                    continue
                nm = ch.find(N + 'Properties').find(N + 'Name').text
                key = '%s.%s' % (k, nm)
                if '%s.%s' % (rel, key) in MOVED_TO_SHADOW:
                    self.log.append('%s: %s → регистр-спутник' % (rel, key))
                elif key in added and k in ('Resource', 'Dimension') and RESOURCE_AS_ATTRIBUTE:
                    # 8.3.21: в заимствованный регистр нельзя добавить ресурс/измерение — переносим реквизитом
                    e = copy.deepcopy(ch)
                    e.tag = N + 'Attribute'
                    for x in ('Balance', 'AccountingFlag', 'ExtDimensionAccountingFlag', 'MainFilter',
                              'DenyIncompleteValues', 'Master', 'BaseDimension', 'UseInTotals', 'TypeReductionMode'):
                        y = e.find(N + 'Properties').find(N + x)
                        if y is not None:
                            e.find(N + 'Properties').remove(y)
                    child_lines.append(ser(e, 3))
                    self.log.append('%s: %s %s → реквизит' % (rel, k, nm))
                elif key in added:
                    child_lines.append(ser(ch, 3))
                elif k == 'TabularSection' and any(a.startswith(key + '.') for a in added):
                    child_lines.append(self.adopted_ts(rel, ch, vchild[(k, nm)], added, key))
                elif k == 'Command' and any(f.startswith(obj_dir + '/Commands/%s/' % nm) for f in files):
                    raise SystemExit('изменена команда %s %s — не предусмотрено' % (rel, nm))
        # вложенные подсистемы: заимствованная дочерняя
        if kind == 'Subsystem':
            for other in self.adopted:
                op = other.split('/')
                if len(op) == len(parts) + 2 and other.startswith(rel + '/Subsystems/'):
                    child_lines.append(t(3) + '<Subsystem>%s</Subsystem>' % op[-1])

        p = [t(1) + '<%s uuid="%s">' % (kind, uid(rel)), internal_info(ve, rel, states)]
        p += adopted_props(kind, ve, 2, extra)
        if child_lines:
            p += [t(2) + '<ChildObjects>'] + child_lines + [t(2) + '</ChildObjects>']
        elif kind in HAS_CHILDREN:
            p.append(t(2) + '<ChildObjects/>')
        p.append(t(1) + '</%s>' % kind)
        wr(rel.replace('/', os.sep) + '.xml', md_header() + '\n'.join(p) + '\n</MetaDataObject>')
        if len(parts) == 2:
            self.add_child(kind, name)

    def meta_diff(self, rel):
        import diff_meta
        a, ap = diff_meta.children(obj_path(VENDOR, rel))
        b, bp = diff_meta.children(obj_path(PROD, rel))
        return {'added': sorted(set(b) - set(a)), 'removed': sorted(set(a) - set(b)),
                'changed': sorted(k for k in set(a) & set(b) if a[k] != b[k]),
                'props': sorted(k for k in set(ap) | set(bp) if ap.get(k) != bp.get(k))}

    def extended_prop(self, kind, prop, ve, pe):
        """Изменённое свойство объекта → строки Properties заимствованного (только добавленное)."""
        vp, pp = ve.find(N + 'Properties').find(N + prop), pe.find(N + 'Properties').find(N + prop)
        if prop in ('RegisterRecords', 'Content'):
            old = {i.text for i in vp} if vp is not None else set()
            new = [i for i in pp if i.text not in old]
            e = copy.deepcopy(pp)
            for i in list(e):
                if i.text in old:
                    e.remove(i)
                elif RESOURCE_AS_ATTRIBUTE and re.search(r'^(InformationRegister|AccumulationRegister)\.[^.]+\.(Dimension|Resource)\.', i.text):
                    i.text = re.sub(r'\.(Dimension|Resource)\.', '.Attribute.', i.text)
            self.log.append('%s %s: +%s' % (pe.find(N + 'Properties').find(N + 'Name').text, prop, ', '.join(i.text for i in new)))
            return [ser(e, 3)]
        if prop == 'MainDataCompositionSchema':
            return [ser(pp, 3)]
        raise SystemExit('не предусмотрено изменение свойства %s у %s' % (prop, kind))

    def adopted_ts(self, rel, pch, vch, added, key):
        nm = vch.find(N + 'Properties').find(N + 'Name').text
        p = [t(3) + '<TabularSection uuid="%s">' % uid(rel, key), internal_info(vch, rel + '/' + key, (), 4)]
        p += adopted_props('TabularSection', vch, 4)
        p.append(t(4) + '<ChildObjects>')
        for a in pch.find(N + 'ChildObjects'):
            an = a.find(N + 'Properties').find(N + 'Name').text
            if '%s.Attribute.%s' % (key, an) in added:
                p.append(ser(a, 5))
        p += [t(4) + '</ChildObjects>', t(3) + '</TabularSection>']
        return '\n'.join(p)

    def adopted_template(self, rel, nm):
        vt = root_elem(os.path.join(TARGET, rel.replace('/', os.sep), 'Templates', nm + '.xml'))
        p = [t(1) + '<Template uuid="%s">' % uid(rel, 'Template', nm), internal_info(vt, rel, ('Template',))]
        p += adopted_props('Template', vt, 2)
        p.append(t(1) + '</Template>')
        wr(os.path.join(rel.replace('/', os.sep), 'Templates', nm + '.xml'), md_header() + '\n'.join(p) + '\n</MetaDataObject>')
        sub = os.path.join(rel.replace('/', os.sep), 'Templates', nm, 'Ext')
        dst = os.path.join(OUT, sub)
        res_dir = os.path.join(RES_TPL, sub)
        if os.path.isdir(res_dir):
            for f in os.listdir(res_dir):
                shutil.copy2(os.path.join(res_dir, f), ensure_dir(os.path.join(dst, f)))
            self.log.append('%s: макет %s — ручное решение' % (rel, nm))
            return
        for f in os.listdir(os.path.join(PROD, sub)):
            src = os.path.join(PROD, sub, f)
            old, new = os.path.join(VENDOR, sub, f), os.path.join(TARGET, sub, f)
            if TARGET != VENDOR and os.path.exists(new) and open(old, 'rb').read() != open(new, 'rb').read():
                lines = lambda x: rd(x).replace(CR + NL, NL).split(NL)
                merged = merge3(lines(old), lines(src), lines(new))
                if merged is None:
                    self.conflicts.append((rel, 'макет ' + nm, 'поставщик изменил схему, конфликт слияния'))
                    continue
                dl.write(ensure_dir(os.path.join(dst, f)), NL.join(merged) + NL)
                self.log.append('%s: макет %s — слит с изменениями поставщика' % (rel, nm))
                continue
            shutil.copy2(src, ensure_dir(os.path.join(dst, f)))
        self.log.append('%s: макет %s замещён' % (rel, nm))

    def adopted_form(self, rel, nm):
        """Заимствованная форма объекта (nm) или общая форма (nm=None)."""
        if nm is None:
            base, kind, key = rel.replace('/', os.sep), 'CommonForm', rel
            mod = rel + '/Ext/Form/Module.bsl'
        else:
            base, kind, key = os.path.join(rel.replace('/', os.sep), 'Forms', nm), 'Form', rel + '/Form/' + nm
            mod = rel + '/Forms/%s/Ext/Form/Module.bsl' % nm
        vf = root_elem(os.path.join(TARGET, base + '.xml'))
        p = [t(1) + '<%s uuid="%s">' % (kind, uid(key)), internal_info(vf, key, ('Form',))]
        p += adopted_props('Form', vf, 2)
        p.append(t(1) + '</%s>' % kind)
        wr(base + '.xml', md_header() + '\n'.join(p) + '\n</MetaDataObject>')
        # Form.xml: минимальная заимствованная форма — состав не меняется, только модуль
        vform = etree.parse(os.path.join(TARGET, base, 'Ext', 'Form.xml')).getroot()
        acb = vform.find('{http://v8.1c.ru/8.3/xcf/logform}AutoCommandBar')
        acb_line = '<AutoCommandBar name="%s" id="-1"/>' % acb.get('name') if acb is not None else ''
        events = FORM_EVENTS.get(key, [])
        body = [t(1) + acb_line] if acb_line else []
        if events:
            body += [t(1) + '<Events>'] + [t(2) + '<Event name="%s" callType="%s">%s</Event>' % e for e in events] + [t(1) + '</Events>']
        body += [t(1) + '<Attributes/>', t(1) + '<BaseForm version="%s">' % dl.VERSION]
        body += ([t(2) + acb_line] if acb_line else []) + [t(2) + '<Attributes/>', t(1) + '</BaseForm>']
        wr(os.path.join(base, 'Ext', 'Form.xml'),
           '<?xml version="1.0" encoding="UTF-8"?>\n<Form %s version="%s">\n%s\n</Form>' % (dl.FORM_NS, dl.VERSION, '\n'.join(body)))
        if mod in self.diff['changed']:
            self.module(mod, mod, extra=FORM_EXTRA_CODE.get(key, ''))

    def shadow_register(self, name, src, title, keep=None):
        """Свой регистр-спутник: копия структуры типового регистра ПРОД (измерения + ресурсы/реквизиты из keep,
        все — если keep не задан) под новым именем и с новыми uuid."""
        kind_dir, src_name = src.split('/')
        txt = rd(os.path.join(PROD, kind_dir, src_name + '.xml'))
        txt = re.sub(r'(name="\w+)\.%s"' % re.escape(src_name), lambda m: '%s.%s"' % (m.group(1), name), txt)
        txt = txt.replace('<Name>%s</Name>' % src_name, '<Name>%s</Name>' % name)
        txt = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', lambda m: uid('shadow', name, m.group(0)), txt)
        root = etree.fromstring(txt.encode('utf-8'))
        obj = list(root)[0]
        pr = obj.find(N + 'Properties')
        syn = pr.find(N + 'Synonym')
        for c in syn.iter('{http://v8.1c.ru/8.1/data/core}content'):
            c.text = title
        co = obj.find(N + 'ChildObjects')
        for ch in list(co):
            k = etree.QName(ch).localname
            if k not in ('Dimension', 'Resource', 'Attribute'):
                co.remove(ch)
            elif keep is not None and k != 'Dimension' and ch.find(N + 'Properties').find(N + 'Name').text not in keep:
                co.remove(ch)
        body = ser(obj, 1)
        wr(os.path.join(kind_dir, name + '.xml'), md_header() + body + '\n</MetaDataObject>')
        self.add_child(DIR_KIND[kind_dir], name)
        self.native.append(kind_dir + '/' + name)
        self.log.append('регистр-спутник %s (по %s)' % (name, src))

    def text_rewrites(self):
        for rel, pairs in TEXT_REWRITES.items():
            path = os.path.join(OUT, rel.replace('/', os.sep))
            txt = rd(path).replace('\r\n', '\n')
            for old, new in pairs:
                if old not in txt:
                    raise SystemExit('нет текста для замены в %s: %s' % (rel, old))
                txt = txt.replace(old, new)
            dl.write(path, txt)
            self.log.append('%s: замен %d' % (rel, len(pairs)))

    def command_interface(self, f):
        """Командный интерфейс заимствованной подсистемы: только команды объектов расширения."""
        own = {DIR_KIND[r.split('/')[0]] + '.' + r.split('/')[1] for r in self.native}
        tree = etree.parse(os.path.join(PROD, f.replace('/', os.sep)))
        root = tree.getroot()
        for sec in list(root):
            for cmd in list(sec):
                name = cmd.get('name') or ''
                if '.'.join(name.split('.')[:2]) not in own:
                    sec.remove(cmd)
            if len(sec) == 0:
                root.remove(sec)
        txt = etree.tostring(root, encoding='unicode')
        dl.write(os.path.join(OUT, f.replace('/', os.sep)), '<?xml version="1.0" encoding="UTF-8"?>\n' + txt)

    def role_rights(self, rel):
        """Права заимствованной роли: только объекты расширения (новые объекты и новые реквизиты)."""
        src = rd(os.path.join(PROD, rel.replace('/', os.sep), 'Ext', 'Rights.xml'))
        ven = rd(os.path.join(VENDOR, rel.replace('/', os.sep), 'Ext', 'Rights.xml'))
        objs = re.findall(r'\t<object>.*?\n\t</object>', src, re.S)
        vobjs = set(re.findall(r'\t<object>.*?\n\t</object>', ven, re.S))
        new = [o for o in objs if o not in vobjs]
        head = src[:src.index('\t<object>')]
        head = head.replace('<setForNewObjects>true', '<setForNewObjects>false')
        dl.write(os.path.join(OUT, rel.replace('/', os.sep), 'Ext', 'Rights.xml'), head + '\n'.join(new) + '\n</Rights>')
        self.log.append('%s: прав на объекты +%d' % (rel, len(new)))

    # модули ------------------------------------------------------------------
    def module(self, rel_vendor, rel_out, extra=''):
        if os.path.exists(os.path.join(VENDOR, rel_vendor)) and os.path.exists(os.path.join(PROD, rel_vendor)):
            r = bm.compare(os.path.join(VENDOR, rel_vendor), os.path.join(PROD, rel_vendor))
        else:
            r = dict(changed=[], added=[], vendor=[], prod=[], outside=[])
        names = {m.name.lower() for m in r['vendor']} | {m.name.lower() for m in r['prod']}
        extra = (extra + '\n\n' + MODULE_EXTRA_CODE.get(rel_vendor, '')).strip('\n')
        out = []
        tgt = {}
        if TARGET != VENDOR:
            tpath = os.path.join(TARGET, rel_vendor)
            if os.path.exists(tpath):
                tm, _ = bm.parse(bm.read(tpath))
                tgt = {m.name.lower(): m for m in tm}
                names |= set(tgt)
        for a, b in r['changed']:
            if TARGET != VENDOR:
                t_ = tgt.get(a.name.lower())
                if t_ is None and (rel_vendor, a.name) in REPLACED_IN_TARGET:
                    self.log.append('%s: %s → перехват преемника %s' % (rel_vendor, a.name, REPLACED_IN_TARGET[(rel_vendor, a.name)]))
                    continue
                if t_ is None:
                    self.conflict(rel_vendor, a.name, 'метода нет в новой поставке', a, b, None)
                    continue                                       # решение — новым методом в RESOLUTIONS_NEW
                if [x.rstrip() for x in t_.lines] != [x.rstrip() for x in a.lines]:
                    merged = merge3(a.lines, b.lines, t_.lines)
                    if merged is None:
                        merged = self.conflict(rel_vendor, a.name, 'конфликт слияния', a, b, t_)
                        if merged is None:
                            continue
                    b = bm.Method(b.name, b.kind, b.ann, merged, b.start)
                    self.log.append('%s: %s — слито с изменениями поставщика' % (rel_vendor, a.name))
                a = bm.Method(t_.name, t_.kind, t_.ann, t_.lines, t_.start)
                if [x.rstrip() for x in a.lines] == [x.rstrip() for x in b.lines]:
                    self.log.append('%s: %s — в новой поставке доработка не нужна' % (rel_vendor, a.name))
                    continue
            txt = self.intercept(a, b, names)
            for patch in METHOD_PATCHES.get((rel_vendor, a.name), ()):
                txt = patch_method(txt, *patch)
            out.append(txt)
        # перехваты методов новой поставки по ручным решениям (tools/resolutions_new/<модуль>/<метод>.bsl)
        rdir = os.path.join(RES_NEW, rel_vendor.replace('/', os.sep))
        if TARGET != VENDOR and os.path.isdir(rdir):
            for f in sorted(os.listdir(rdir)):
                t_ = tgt.get(f[:-4].lower())
                if t_ is None:
                    self.conflicts.append((rel_vendor, f[:-4], 'решение для метода, которого нет в новой поставке'))
                    continue
                lines = bm.read(os.path.join(rdir, f))
                while lines and (lines[0].startswith('//') or not lines[0].strip()):
                    lines.pop(0)
                while lines and not lines[-1].strip():
                    lines.pop()
                out.append(self.intercept(t_, bm.Method(t_.name, t_.kind, t_.ann, lines, 0), names))
                self.log.append('%s: %s — перехват по ручному решению' % (rel_vendor, t_.name))
        for m in r['added']:
            txt = '\n'.join(m.ann + m.lines)
            mo = os.path.join(OVERLAY, 'methods', rel_vendor.replace('/', os.sep), m.name + '.bsl')
            if TARGET != VENDOR and os.path.exists(mo):           # новый метод Деснол, исправленный под новую поставку
                txt = rd(mo).replace(CR + NL, NL).strip(NL)
                self.log.append('%s: %s — версия под %s' % (rel_vendor, m.name, TARGET_VERSION))
            if TARGET != VENDOR:
                for old, new in ADDED_PATCHES_NEW.get(rel_vendor, ()):
                    txt = txt.replace(old, new)
            out.append(txt)
        xf = os.path.join(RES_EXTRA, rel_vendor.replace('/', os.sep))
        if TARGET != VENDOR and os.path.exists(xf):
            out.append(rd(xf).replace(CR + NL, NL).strip(NL))
        if extra:
            out.append(extra.strip('\n'))
        if not out:
            self.log.append('%s: изменены только комментарии — модуль не переносится' % rel_vendor)
            return False
        text = '\n\n'.join(out) + '\n'
        wrap = server_wrap(os.path.join(TARGET, rel_vendor))
        if wrap:
            text = wrap + '\n\n' + text + '\n#КонецЕсли\n'
        wr(rel_out.replace('/', os.sep), text)
        self.log.append('%s: перехват %d, новых %d' % (rel_vendor, len(r['changed']), len(r['added'])))
        return True

    def conflict(self, rel, name, why, a, b, t_):
        """Метод, который поставщик изменил там же, где Деснол. Ручное решение — полный текст метода (новая
        поставка + доработка) в tools/resolutions/<модуль>/<метод>.bsl; без него метод в расширение не попадает,
        все три версии кладутся в src/<профиль>/conflicts для разбора."""
        res = os.path.join(ROOT, 'tools', 'resolutions', rel.replace('/', os.sep), name + '.bsl')
        if os.path.exists(res):
            self.log.append('%s: %s — %s, ручное решение' % (rel, name, why))
            lines = bm.read(res)
            while lines and (lines[0].startswith('//') or not lines[0].strip()):      # комментарий-обоснование
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            return lines
        self.conflicts.append((rel, name, why))
        d = os.path.join(os.path.dirname(os.path.dirname(OUT)), 'conflicts', rel.replace('/', os.sep), name)
        os.makedirs(d, exist_ok=True)
        for suf, m in (('1_поставка_3.0.8.1', a), ('2_ПРОД', b), ('3_поставка_новая', t_)):
            if m is not None:
                io.open(os.path.join(d, suf + '.bsl'), 'w', encoding='utf-8').write(NL.join(m.ann + m.lines) + NL)
        return None

    def intercept(self, a, b, names):
        hl = header_len(a.lines)
        if [x.rstrip() for x in a.lines[:hl]] != [x.rstrip() for x in b.lines[:hl]]:
            raise SystemExit('изменён заголовок метода %s — не предусмотрено' % a.name)
        new = PREFIX + a.name
        if new.lower() in names:
            new = PREFIX + 'Изм_' + a.name
        directives = [x for x in a.ann if re.match(r'\s*&На', x)]
        head = list(a.lines[:hl])
        head[0] = re.sub(r'(Процедура|Функция)(\s+)' + re.escape(a.name) + r'(\s*)\(', r'\1\g<2>%s\3(' % new, head[0], count=1, flags=re.I)
        va, vb = a.lines[hl:-1], b.lines[hl:-1]
        body = []
        sm = difflib.SequenceMatcher(a=[x.rstrip() for x in va], b=[x.rstrip() for x in vb], autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == 'equal':
                body += va[i1:i2]
                continue
            if op in ('delete', 'replace'):
                body += ['#Удаление'] + va[i1:i2] + ['#КонецУдаления']
            if op in ('insert', 'replace'):
                body += ['#Вставка'] + vb[j1:j2] + ['#КонецВставки']
        return '\n'.join(directives + ['&ИзменениеИКонтроль("%s")' % a.name] + head + body + [a.lines[-1]])

    # пустые заимствованные по ссылкам ------------------------------------
    def adopt_references(self):
        refs = set()
        rx = re.compile(r'(?<![\w.])(Catalog|Document|Enum|InformationRegister|AccumulationRegister|ChartOfCharacteristicTypes|'
                        r'ExchangePlan|DataProcessor|Report|CommonPicture|CommonCommand|CommonForm|CommonModule|'
                        r'DefinedType|StyleItem|FunctionalOption|FunctionalOptionsParameter|Subsystem|Role|Constant|'
                        r'DocumentJournal|BusinessProcess|Task|SessionParameter|CommandGroup|FilterCriterion)'
                        r'(Ref|Object|Manager|Selection|List|RecordSet|RecordKey|RecordManager|Record)?\.([\wЁё]+)')
        for d, _, fs in os.walk(OUT):
            for f in fs:
                if not f.endswith('.xml') or f in ('Template.xml', 'Configuration.xml'):
                    continue
                txt = rd(os.path.join(d, f))
                for m in rx.finditer(txt):
                    refs.add((m.group(1), m.group(3)))
                for m in re.finditer(r'style:([\wЁё]+)', txt):
                    refs.add(('StyleItem', m.group(1)))
        have = {(k, n) for k, ns in self.children.items() for n in ns}
        n = 0
        for kind, name in sorted(refs):
            if (kind, name) in have or kind not in KIND_DIR:
                continue
            vpath = os.path.join(TARGET, KIND_DIR[kind], name + '.xml')
            if not os.path.exists(vpath):
                continue                                                 # платформенное / своё
            ve = root_elem(vpath)
            p = [t(1) + '<%s uuid="%s">' % (kind, uid(KIND_DIR[kind] + '/' + name)), internal_info(ve, KIND_DIR[kind] + '/' + name)]
            p += adopted_props(kind, ve, 2)
            if kind in HAS_CHILDREN:
                p.append(t(2) + '<ChildObjects/>')
            p.append(t(1) + '</%s>' % kind)
            wr(os.path.join(KIND_DIR[kind], name + '.xml'), md_header() + '\n'.join(p) + '\n</MetaDataObject>')
            self.add_child(kind, name)
            n += 1
        self.log.append('заимствовано по ссылкам: %d' % n)

    def language(self):
        ve = root_elem(os.path.join(TARGET, 'Languages', 'Русский.xml'))
        p = [t(1) + '<Language uuid="%s">' % uid('Language'), t(2) + '<InternalInfo/>']
        p += adopted_props('Language', ve, 2)
        p.append(t(1) + '</Language>')
        wr(os.path.join('Languages', 'Русский.xml'), md_header() + '\n'.join(p) + '\n</MetaDataObject>')
        self.add_child('Language', 'Русский')

    def configuration(self):
        p = [t(1) + '<Configuration uuid="%s">' % uid('Configuration'), t(2) + '<InternalInfo>']
        for k in ROOT_CLASSES:
            p += [t(3) + '<xr:ContainedObject>', t(4) + '<xr:ClassId>%s</xr:ClassId>' % k,
                  t(4) + '<xr:ObjectId>%s</xr:ObjectId>' % uid('Configuration', k), t(3) + '</xr:ContainedObject>']
        p += [t(2) + '</InternalInfo>', t(2) + '<Properties>',
              t(3) + '<ObjectBelonging>Adopted</ObjectBelonging>',
              t(3) + '<Name>%s</Name>' % EXT_NAME,
              dl.ml_tag('Synonym', 'НПЦАП: доработки ТОИР (Деснол)', 3),
              t(3) + '<Comment>Перенос доработок ПРОД относительно поставки 3.0.8.1 (tools/build_ext.py)</Comment>',
              t(3) + '<ConfigurationExtensionPurpose>Customization</ConfigurationExtensionPurpose>',
              t(3) + '<KeepMappingToExtendedConfigurationObjectsByIDs>true</KeepMappingToExtendedConfigurationObjectsByIDs>',
              t(3) + '<NamePrefix>%s</NamePrefix>' % PREFIX,
              t(3) + '<ConfigurationExtensionCompatibilityMode>%s</ConfigurationExtensionCompatibilityMode>' % COMPAT,
              t(3) + '<DefaultRunMode>ManagedApplication</DefaultRunMode>',
              t(3) + '<UsePurposes>',
              t(4) + '<v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value>',
              t(3) + '</UsePurposes>',
              t(3) + '<ScriptVariant>Russian</ScriptVariant>',
              t(3) + '<DefaultRoles/>',
              t(3) + '<Vendor>ООО "Деснол Софт Проджект"</Vendor>',
              t(3) + '<Version>1.0.0.1</Version>',
              t(3) + '<DefaultLanguage>Language.Русский</DefaultLanguage>',
              t(3) + '<BriefInformation/>', t(3) + '<DetailedInformation/>', t(3) + '<Copyright/>',
              t(3) + '<VendorInformationAddress/>', t(3) + '<ConfigurationInformationAddress/>',
              t(3) + '<InterfaceCompatibilityMode>Taxi</InterfaceCompatibilityMode>',
              t(2) + '</Properties>',
              dl.configuration_child_objects(self.children),
              t(1) + '</Configuration>']
        wr('Configuration.xml', md_header() + '\n'.join(p) + '\n</MetaDataObject>')


RESOURCE_AS_ATTRIBUTE = False      # 8.3.21: и реквизит в заимствованный регистр добавить нельзя — проверено

# ---------------------------------------------------------------- регистры-спутники
# Платформа (режим совместимости расширения ≤ основной конфигурации = 8.3.21) не позволяет добавлять
# измерения, ресурсы и реквизиты в заимствованные регистры. Пять полей ПРОД уходят в свои регистры:
#   ЦеныНоменклатуры.дс_Серия (измерение = ключ цены) → дс_ЦеныНоменклатурыСерий (копия регистра + серия);
#   торо_ФактическиеТрудовыеЗатратыРемонтныхРабот.торо_*Сверх* (3 ресурса) → дс_СверхурочныеТрудозатраты
#       (те же измерения + 3 ресурса; пишется из АВЭР той же таблицей, связь по Регистратор + НомерСтроки);
#   торо_ИзмеряемыеПоказателиОбъектовРемонта.дс_Длинна → дс_ДлиныИзмеряемыхПоказателей (те же измерения + длина).
SHADOW = {
    'дс_ЦеныНоменклатурыСерий': ('InformationRegisters/ЦеныНоменклатуры', 'Цены номенклатуры по сериям'),
    'дс_СверхурочныеТрудозатраты': ('AccumulationRegisters/торо_ФактическиеТрудовыеЗатратыРемонтныхРабот',
                                    'Сверхурочные трудозатраты ремонтных работ',
                                    ('торо_ВремяРаботыСверхМенееДвухЧасов', 'торо_ВремяРаботыСверхБолееДвухЧасов',
                                     'торо_ОбщееВремяРаботыСверхГрафика')),
    'дс_ДлиныИзмеряемыхПоказателей': ('InformationRegisters/торо_ИзмеряемыеПоказателиОбъектовРемонта',
                                      'Длины измеряемых показателей', ('дс_Длинна',)),
}
MOVED_TO_SHADOW = {'InformationRegisters/ЦеныНоменклатуры.Dimension.дс_Серия',
                   'InformationRegisters/торо_ИзмеряемыеПоказателиОбъектовРемонта.Resource.дс_Длинна',
                   'AccumulationRegisters/торо_ФактическиеТрудовыеЗатратыРемонтныхРабот.Resource.торо_ВремяРаботыСверхМенееДвухЧасов',
                   'AccumulationRegisters/торо_ФактическиеТрудовыеЗатратыРемонтныхРабот.Resource.торо_ВремяРаботыСверхБолееДвухЧасов',
                   'AccumulationRegisters/торо_ФактическиеТрудовыеЗатратыРемонтныхРабот.Resource.торо_ОбщееВремяРаботыСверхГрафика'}
ФТЗ = 'торо_ФактическиеТрудовыеЗатратыРемонтныхРабот'
TEXT_REWRITES = {
    'FunctionalOptions/ИспользоватьСерииНоменклатуры.xml': [
        ('InformationRegister.ЦеныНоменклатуры.Dimension.дс_Серия', 'InformationRegister.дс_ЦеныНоменклатурыСерий.Dimension.дс_Серия')],
    'Reports/торо_ОстаткиНоменклатурыНаСкладах/Templates/дс_ОсновнаяСхемаКомпоновкиДанных/Ext/Template.xml': [
        ('РегистрСведений.ЦеныНоменклатуры.СрезПоследних', 'РегистрСведений.дс_ЦеныНоменклатурыСерий.СрезПоследних')],
    'Reports/дс_АнализИспользованияПерсонала/Ext/ObjectModule.bsl': [
        ('|\t%s.%s КАК' % (ФТЗ, f), '|\tЕСТЬNULL(дс_Сверхурочные.%s, 0) КАК' % f)
        for f in ('торо_ОбщееВремяРаботыСверхГрафика', 'торо_ВремяРаботыСверхМенееДвухЧасов', 'торо_ВремяРаботыСверхБолееДвухЧасов')] + [
        ('|\tРегистрНакопления.%s КАК %s\n' % (ФТЗ, ФТЗ),
         '|\tРегистрНакопления.%s КАК %s\n\t|\t\tЛЕВОЕ СОЕДИНЕНИЕ РегистрНакопления.дс_СверхурочныеТрудозатраты КАК дс_Сверхурочные\n'
         '\t|\t\tПО дс_Сверхурочные.Регистратор = %s.Регистратор\n\t|\t\t\tИ дс_Сверхурочные.НомерСтроки = %s.НомерСтроки\n' % (ФТЗ, ФТЗ, ФТЗ, ФТЗ))],
}
# дополнительные движения заимствованных документов (регистры-спутники)
EXTRA_REGISTER_RECORDS = {'Documents/УстановкаЦенНоменклатуры': ['InformationRegister.дс_ЦеныНоменклатурыСерий'],
                          'Documents/торо_АктОВыполненииЭтапаРабот': ['AccumulationRegister.дс_СверхурочныеТрудозатраты']}
# код модулей расширения, которого нет в ПРОД (запись регистров-спутников)
MODULE_EXTRA_CODE = {
    'Documents/торо_АктОВыполненииЭтапаРабот/Ext/ObjectModule.bsl': '''// Сверхурочные (доработка Деснол) — в регистр-спутник той же таблицей, что и типовые трудозатраты:
// строки совпадают по номеру, отчёт дс_АнализИспользованияПерсонала связывает их по Регистратор + НомерСтроки.
&После("ДвиженияПоРегистру_торо_ФактическиеТрудовыеЗатратыРемонтныхРабот")
Процедура дс_ДвиженияПоРегистру_СверхурочныеТрудозатраты(РежимПроведения, ТаблицаТрудовыхЗатрат, Отказ)

	Движения.дс_СверхурочныеТрудозатраты.Записывать = Истина;
	Для Каждого ЗаписьТрудовыеЗатраты Из ТаблицаТрудовыхЗатрат Цикл
		Движение = Движения.дс_СверхурочныеТрудозатраты.Добавить();
		ЗаполнитьЗначенияСвойств(Движение, ЗаписьТрудовыеЗатраты);
	КонецЦикла;

КонецПроцедуры''',
}
ИПОР = 'торо_ИзмеряемыеПоказателиОбъектовРемонта'
ДЛИНА_СОЕДИНЕНИЕ = ['\t\t|\t\tЛЕВОЕ СОЕДИНЕНИЕ РегистрСведений.дс_ДлиныИзмеряемыхПоказателей КАК дс_Длины',
                    '\t\t|\t\tПО дс_Длины.ОбъектРемонта = %s.ОбъектРемонта' % ИПОР,
                    '\t\t|\t\t\tИ дс_Длины.Показатель = %s.Показатель' % ИПОР]
# (модуль, метод) → [(строка исходника — подстрока, новые строки)]; строка поставщика уходит в #Удаление
METHOD_PATCHES = {
    ('Documents/УстановкаЦенНоменклатуры/Ext/ObjectModule.bsl', 'ОбработкаПроведения'): [
        ('	Движения.ЦеныНоменклатуры.Очистить();', [
            '	Движения.ЦеныНоменклатуры.Очистить();',
            '	// дс_Серия: все строки — в регистр-спутник с измерением серии, в типовой — только строки без серии',
            '	Движения.дс_ЦеныНоменклатурыСерий.Записывать = Истина;',
            '	Движения.дс_ЦеныНоменклатурыСерий.Очистить();']),
        ('		Движение = Движения.ЦеныНоменклатуры.Добавить();', [
            '		ДвижениеСерии = Движения.дс_ЦеныНоменклатурыСерий.Добавить();',
            '		ЗаполнитьЗначенияСвойств(ДвижениеСерии, Выборка);',
            '		Если Выборка.ЕдиницаИзмерения <> Выборка.ДокЕдиницаИзмерения Тогда',
            '			ДвижениеСерии.Цена = ?(Выборка.Коэффициент = 0, 0, ДвижениеСерии.Цена / Выборка.Коэффициент);',
            '		КонецЕсли;',
            '		Если ЗначениеЗаполнено(Выборка.дс_Серия) Тогда',
            '			Продолжить;',
            '		КонецЕсли;',
            '		Движение = Движения.ЦеныНоменклатуры.Добавить();']),
        ('		|		ВНУТРЕННЕЕ СОЕДИНЕНИЕ РегистрСведений.ЦеныНоменклатуры КАК ЦеныНоменклатуры', [
            '		|		ВНУТРЕННЕЕ СОЕДИНЕНИЕ РегистрСведений.дс_ЦеныНоменклатурыСерий КАК ЦеныНоменклатуры']),
    ],
    # дс_Длинна: из регистра-спутника левым соединением (4 запроса в функции)
    ('ChartsOfCharacteristicTypes/торо_ИзмеряемыеПоказателиОбъектовРемонта/Ext/ManagerModule.bsl',
     'ПолучитьСтруктуруИзмеряемыхПоказателейОбъектовРемонта'): [
        ('ЕСТЬNULL(%s.дс_Длинна, 0)' % ИПОР, ['\t\t|\t,ЕСТЬNULL(дс_Длины.дс_Длинна, 0) КАК дс_Длинна'], 4),
        ('|\tРегистрСведений.%s КАК %s' % (ИПОР, ИПОР), ['\t\t|\tРегистрСведений.%s КАК %s' % (ИПОР, ИПОР)] + ДЛИНА_СОЕДИНЕНИЕ, 4),
    ],
    ('Catalogs/торо_ТиповыеОР/Forms/ФормаЭлемента/Ext/Form/Module.bsl', 'ПолучитьИзмеряемыеПоказатели'): [
        ('ЕСТЬNULL(%s.дс_Длинна, 0)' % ИПОР, ['\t\t|\t,ЕСТЬNULL(дс_Длины.дс_Длинна, 0) КАК дс_Длинна']),
        ('ВНУТРЕННЕЕ СОЕДИНЕНИЕ РегистрСведений.%s КАК %s' % (ИПОР, ИПОР),
         ['\t\t|\t\tВНУТРЕННЕЕ СОЕДИНЕНИЕ РегистрСведений.%s КАК %s' % (ИПОР, ИПОР)] + ДЛИНА_СОЕДИНЕНИЕ),
    ],
}

# события, добавленные формам расширением (callType), и код, которого нет в ПРОД, но нужен расширению
FORM_EVENTS = {}
FORM_EXTRA_CODE = {
    # кнопка «Заказ - наряд» (в ПРОД — в Form.xml): заимствованная форма минимальная, команда и кнопка — кодом
    'DataProcessors/торо_ОбщийПланРабот/Form/Форма': '''&НаСервере
&После("ПриСозданииНаСервере")
Процедура дс_ПриСозданииНаСервереПосле(Отказ, СтандартнаяОбработка)

	Если Команды.Найти("дс_ПечатьЗаказНаряд") <> Неопределено Тогда
		Возврат;
	КонецЕсли;
	Команда = Команды.Добавить("дс_ПечатьЗаказНаряд");
	Команда.Заголовок = НСтр("ru = 'Заказ - наряд'");
	Команда.Подсказка = НСтр("ru = 'Печать плана работ'");
	Команда.Картинка = БиблиотекаКартинок.Печать;
	Команда.Отображение = ОтображениеКнопки.КартинкаИТекст;
	Команда.Действие = "дс_ПечатьЗаказНаряд";
	Кнопка = Элементы.Вставить("ПечатьЗаказНаряд", Тип("КнопкаФормы"), Элементы.ФормаКоманднаяПанель,
		Элементы.ФормаОтчетПланМТО);
	Кнопка.Вид = ВидКнопкиФормы.КнопкаКоманднойПанели;
	Кнопка.ИмяКоманды = "дс_ПечатьЗаказНаряд";

КонецПроцедуры''',
    # дс_Длинна типового ОР — в регистр-спутник после типовой записи измеряемых показателей
    'Catalogs/торо_ТиповыеОР/Form/ФормаЭлемента': '''&НаСервере
&После("ПриЗаписиНаСервере")
Процедура дс_ПриЗаписиНаСервереПосле(Отказ, ТекущийОбъект, ПараметрыЗаписи)

	Если Отказ Тогда
		Возврат;
	КонецЕсли;
	НаборЗаписей = РегистрыСведений.дс_ДлиныИзмеряемыхПоказателей.СоздатьНаборЗаписей();
	НаборЗаписей.Отбор.ОбъектРемонта.Установить(ТекущийОбъект.Ссылка);
	Для Каждого СтрокаПоказателя Из СписокИзмеряемыхПоказателей Цикл
		Если СтрокаПоказателя.ОбъектРемонта = ТекущийОбъект.Ссылка И ЗначениеЗаполнено(СтрокаПоказателя.дс_Длинна) Тогда
			Запись = НаборЗаписей.Добавить();
			Запись.ОбъектРемонта = ТекущийОбъект.Ссылка;
			Запись.Показатель = СтрокаПоказателя.Показатель;
			Запись.дс_Длинна = СтрокаПоказателя.дс_Длинна;
		КонецЕсли;
	КонецЦикла;
	НаборЗаписей.Записать();

КонецПроцедуры''',
}

# Правки новых методов Деснол под новую поставку (3.0.25.3): форма ввода периода ППР передаёт ДатаОкончания вместо
# ДатаКонца и не передаёт ВыводитьВсеРемонты; печать без параметров даёт 2 строки отбора, а не 3.
ADDED_PATCHES_NEW = {
    'Documents/торо_ПланГрафикРемонта/Ext/ManagerModule.bsl': [
        ('СтруктураПараметровПечати.ДатаКонца',
         '?(СтруктураПараметровПечати.Свойство("ДатаОкончания"), СтруктураПараметровПечати.ДатаОкончания, СтруктураПараметровПечати.ДатаКонца)'),
        ('Если Не СтруктураПараметровПечати.ВыводитьВсеРемонты Тогда',
         'Если Не (СтруктураПараметровПечати.Свойство("ВыводитьВсеРемонты") И СтруктураПараметровПечати.ВыводитьВсеРемонты) Тогда'),
        ('ОтборПечатнойФормы[2].Имя = "ПодразделениеВладелец";',
         'Если ОтборПечатнойФормы.Количество() > 2 Тогда ОтборПечатнойФормы[2].Имя = "ПодразделениеВладелец"; КонецЕсли;'),
    ],
}
# 3.0.25.3: движения трудозатрат получают выборку запроса (не таблицу) — спутник заполняется той же выборкой
if TARGET_VERSION != '3.0.8.1':
    MODULE_EXTRA_CODE['Documents/торо_АктОВыполненииЭтапаРабот/Ext/ObjectModule.bsl'] = '''// Сверхурочные (доработка Деснол) — в регистр-спутник той же выборкой, что и типовые трудозатраты:
// строки совпадают по номеру, отчёт дс_АнализИспользованияПерсонала связывает их по Регистратор + НомерСтроки.
&После("ДвиженияПоРегистру_торо_ФактическиеТрудовыеЗатратыРемонтныхРабот")
Процедура дс_ДвиженияПоРегистру_СверхурочныеТрудозатраты(ВыборкаТрудовыеЗатраты, РежимПроведения, Отказ)

	Если Отказ Тогда
		Возврат;
	КонецЕсли;
	Движения.дс_СверхурочныеТрудозатраты.Записывать = Истина;
	ВыборкаТрудовыеЗатраты.Сбросить();
	Пока ВыборкаТрудовыеЗатраты.Следующий() Цикл
		Движение = Движения.дс_СверхурочныеТрудозатраты.Добавить();
		ЗаполнитьЗначенияСвойств(Движение, ВыборкаТрудовыеЗатраты);
	КонецЦикла;

КонецПроцедуры'''
# Методы ПРОД, которых нет в новой поставке, — доработка перенесена перехватом метода-преемника (resolutions_new)
REPLACED_IN_TARGET = {('Documents/торо_АктОВыполненииЭтапаРабот/Ext/ObjectModule.bsl', 'ПодготовитьТаблицуТрудовыхЗатрат'):
                      'ПодготовитьПроведениеТрудовыхЗатрат'}

# Объекты, доработку которых поставщик уже включил в новую поставку (разбор — ПЕРЕНОС-В-РАСШИРЕНИЕ.md)
ACCEPTED_BY_VENDOR = {'3.0.25.3': {'Reports/торо_КТГОборудования'}}

if not SHADOW_MODE:
    # 8.3.25: измерения/ресурсы добавляются в заимствованные регистры — спутники и правки под них не нужны
    SHADOW, MOVED_TO_SHADOW, TEXT_REWRITES, EXTRA_REGISTER_RECORDS, MODULE_EXTRA_CODE, METHOD_PATCHES = {}, set(), {}, {}, {}, {}
    FORM_EXTRA_CODE.pop('Catalogs/торо_ТиповыеОР/Form/ФормаЭлемента')

ROOT_CLASSES = ('9cd510cd-abfc-11d4-9434-004095e12fc7', '9fcd25a0-4822-11d4-9414-008048da11f9',
                'e3687481-0a87-462c-a166-9f34594f9bba', '9de14907-ec23-4a07-96f0-85521cb6b53b',
                '51f2d5d8-ea4d-4064-8892-82951750031e', 'e68182ea-4237-4383-967f-90c1e3370bc7',
                'fb282519-d103-4dd3-bc12-cb271d631dfc')


def merge3(base, ours, theirs):
    """Трёхстороннее слияние строк метода (git merge-file): None — конфликт."""
    import subprocess
    import tempfile
    d = tempfile.mkdtemp()
    paths = []
    for nm, lines in (('ours', ours), ('base', base), ('theirs', theirs)):
        pth = os.path.join(d, nm)
        io.open(pth, 'w', encoding='utf-8', newline=NL).write(NL.join(x.rstrip() for x in lines) + NL)
        paths.append(pth)
    r = subprocess.run(['git', 'merge-file', '-p', '--diff3'] + paths, capture_output=True)
    shutil.rmtree(d, ignore_errors=True)
    lines = r.stdout.decode('utf-8').rstrip(NL).split(NL)
    if r.returncode == 0:
        return lines
    # конфликт «обе стороны вставили в одно место» (общая часть пуста) — сначала поставщик, затем Деснол:
    # доработка всегда шла после типовой логики. Иначе — настоящий конфликт (None).
    out, i = [], 0
    while i < len(lines):
        if not lines[i].startswith('<<<<<<< '):
            out.append(lines[i])
            i += 1
            continue
        j = next(k for k in range(i, len(lines)) if lines[k].startswith('||||||| '))
        m = next(k for k in range(j, len(lines)) if lines[k] == '=======')
        e = next(k for k in range(m, len(lines)) if lines[k].startswith('>>>>>>> '))
        ours_, base_, theirs_ = lines[i + 1:j], lines[j + 1:m], lines[m + 1:e]
        if any(x.strip() for x in base_):
            return None
        out += theirs_ + ours_
        i = e + 1
    return out


def patch_method(txt, old, new, count=1):
    """Заменить в тексте перехватчика строки, содержащие old (ровно count штук), на строки new. Строка поставщика
    (вне #Вставка) уходит в #Удаление, новые — в #Вставка; строка внутри #Вставка заменяется на месте."""
    lines = txt.split(NL)
    inside, deleted, hits = False, False, []
    for i, l in enumerate(lines):
        st = l.strip()
        if st.startswith('#Вставка'):
            inside = True
        elif st.startswith('#КонецВставки'):
            inside = False
        elif st.startswith('#Удаление'):
            deleted = True
        elif st.startswith('#КонецУдаления'):
            deleted = False
        elif old in l and not st.startswith('#') and not deleted:
            hits.append((i, inside))
    if len(hits) != count:
        raise SystemExit('правка перехватчика: строк «%s» найдено %d, ждали %d' % (old, len(hits), count))
    for i, inside in reversed(hits):
        rep = list(new) if inside else ['#Удаление', lines[i], '#КонецУдаления', '#Вставка'] + list(new) + ['#КонецВставки']
        lines[i:i + 1] = rep
    return NL.join(lines)


NL = chr(10)
CR = chr(13)


def header_len(lines):
    depth = 0
    for i, l in enumerate(lines):
        code = re.sub(r'"[^"]*"', '', l.split('//')[0])
        depth += code.count('(') - code.count(')')
        if '(' in ''.join(lines[:i + 1]) and depth <= 0:
            return i + 1
    return 1


def server_wrap(path):
    """Первая инструкция модуля поставщика #Если Сервер … Тогда — обернуть модуль расширения так же."""
    for l in bm.read(path):
        s = l.strip()
        if not s or s.startswith('//'):
            continue
        if s.startswith('#Если') and 'Сервер' in s:
            return s
        return ''
    return ''


def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def shutil_copy(src_root, dst_root, rel):
    shutil.copy2(os.path.join(src_root, rel.replace('/', os.sep)), ensure_dir(os.path.join(dst_root, rel.replace('/', os.sep))))


if __name__ == '__main__':
    a = sys.argv[1:]
    only = None
    if '--only' in a:
        only = set(a[a.index('--only') + 1].split(','))
    Ext(only).build()
