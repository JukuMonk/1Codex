# -*- coding: utf-8 -*-
"""check_project — структурные проверки проекта 1C:EDT без самого EDT.

Проверяет то, что EDT и платформа показывают поздно или молча:
  * кодировка и переводы строк (.mdo/.form/.dcs/.cmi/.bsl: без BOM, CRLF);
  * каждый объект на диске прописан в Configuration.mdo (case 021);
  * каждый объект из Configuration.mdo есть на диске;
  * у дочерней подсистемы есть <parentSubsystem> (case 019);
  * состав подсистем ссылается на существующие объекты;
  * ссылки defaultObjectForm/defaultListForm/… ведут к папкам Forms;
  * у папки формы есть Form.form; форма проходит check_form (+ модуль);
  * .mdo проходит check_mdo (длина строк, дубли uuid и имён);
  * uuid объектов не повторяются по проекту;
  * форма с MobileDevice есть → у корня включено назначение MobileDevice (case 005);
  * модули форм и общих модулей проходят check_bsl.

Запуск:  python tools/check_project.py <корень проекта EDT> [--prefix мвм] [--quiet]
  --prefix  проверять только объекты с этим префиксом имени (свои, а не типовые);
            без него проверяется всё, что есть (на большой конфигурации долго).
Код выхода 1 — есть ошибки. Предупреждения кода не меняют.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edt_lib as lib  # noqa: E402

KINDS = {v: k for k, v in lib.FOLDERS.items()}


def read(path):
    return io.open(path, 'rb').read().decode('utf-8', 'replace')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        sys.exit(__doc__)
    root = args[0]
    src = os.path.join(root, 'src') if os.path.isdir(os.path.join(root, 'src')) else root
    prefix = ''
    for i, a in enumerate(sys.argv):
        if a == '--prefix' and i + 1 < len(sys.argv):
            prefix = sys.argv[i + 1]
    quiet = '--quiet' in sys.argv
    errors, warnings = [], []

    config_path = os.path.join(src, 'Configuration', 'Configuration.mdo')
    if not os.path.exists(config_path):
        sys.exit('ОШИБКА: нет %s' % config_path)
    config = read(config_path)
    registered = set(re.findall(r'<(\w+)>((?:\w+)\.[^<]+)</\1>', config))
    registered = {fq for _t, fq in registered if '.' in fq and fq.split('.')[0] in lib.FOLDERS}
    mobile_root = '<usePurposes>MobileDevice</usePurposes>' in config

    objects = []          # (kind, name, folder)
    for folder, kind in KINDS.items():
        d = os.path.join(src, folder)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if prefix and not name.startswith(prefix):
                continue
            if os.path.isdir(os.path.join(d, name)):
                objects.append((kind, name, os.path.join(d, name)))

    seen_uuid = {}
    for kind, name, folder in objects:
        fq = '%s.%s' % (kind, name)
        mdo = os.path.join(folder, name + '.mdo')
        if not os.path.exists(mdo):
            errors.append('%s: нет файла %s.mdo' % (fq, name))
            continue
        if lib.has_bom(mdo):
            errors.append('%s: у .mdo BOM — файлы EDT без BOM' % fq)
        text = read(mdo)
        for p in lib.check_mdo(text):
            (warnings if p.startswith('предупреждение') else errors).append('%s: %s' % (fq, p))
        if kind != 'Subsystem' and fq not in registered:
            # дочерние подсистемы регистрируются у родителя, остальные — в корне
            errors.append('%s: не прописан в Configuration.mdo (case 021)' % fq)
        m = re.search(r'<mdclass:\w+ [^>]*uuid="([^"]+)"', text)
        if m:
            if m.group(1) in seen_uuid:
                errors.append('%s: uuid объекта повторяет %s' % (fq, seen_uuid[m.group(1)]))
            seen_uuid[m.group(1)] = fq
        # формы
        forms_dir = os.path.join(folder, 'Forms')
        declared = re.findall(r'<forms uuid="[^"]+">\s*<name>([^<]+)</name>(.*?)</forms>', text, re.S)
        for fname, fbody in declared:
            fdir = os.path.join(forms_dir, fname)
            ff = os.path.join(fdir, 'Form.form')
            if not os.path.exists(ff):
                errors.append('%s: форма «%s» объявлена в .mdo, а Forms/%s/Form.form нет' % (fq, fname, fname))
                continue
            if 'MobileDevice' in fbody and not mobile_root:
                errors.append('%s: форма «%s» для MobileDevice, а у корня конфигурации назначение '
                              'не включено (case 005)' % (fq, fname))
            ftext = read(ff)
            mpath = os.path.join(fdir, 'Module.bsl')
            mtext = read(mpath) if os.path.exists(mpath) else None
            for p in lib.check_form(ftext, mtext):
                (warnings if p.startswith('предупреждение') else errors).append('%s/%s: %s' % (fq, fname, p))
            if mtext is not None:
                if lib.has_bom(mpath):
                    warnings.append('%s/%s: у Module.bsl BOM (EDT терпит, но исходники без BOM)' % (fq, fname))
                for p in lib.check_bsl(mtext, is_form_module=True):
                    (warnings if p.startswith('предупреждение') else errors).append('%s/%s/Module.bsl: %s' % (fq, fname, p))
        if os.path.isdir(forms_dir):
            for fname in os.listdir(forms_dir):
                if fname not in [d for d, _ in declared]:
                    errors.append('%s: папка Forms/%s есть, а в .mdo форма не объявлена' % (fq, fname))
        for m in re.finditer(r'<(default\w+Form)>([^<]+)</\1>', text):
            ref = m.group(2)
            if ref.startswith(fq + '.Form.'):
                fname = ref.split('.Form.')[1]
                if not os.path.exists(os.path.join(forms_dir, fname, 'Form.form')):
                    errors.append('%s: %s ссылается на несуществующую форму %s' % (fq, m.group(1), fname))
        # общий модуль
        if kind == 'CommonModule':
            mpath = os.path.join(folder, 'Module.bsl')
            if not os.path.exists(mpath):
                errors.append('%s: нет Module.bsl' % fq)
            else:
                for p in lib.check_bsl(read(mpath), is_form_module=False):
                    (warnings if p.startswith('предупреждение') else errors).append('%s/Module.bsl: %s' % (fq, p))
        # подсистемы: состав и дочерние
        if kind == 'Subsystem':
            check_subsystem(src, folder, name, None, errors)
        # отчёты: схема
        if kind == 'Report':
            m = re.search(r'<mainDataCompositionSchema>Report\.\w+\.Template\.(\w+)</mainDataCompositionSchema>', text)
            if m and not os.path.exists(os.path.join(folder, 'Templates', m.group(1), 'Template.dcs')):
                errors.append('%s: нет Templates/%s/Template.dcs' % (fq, m.group(1)))

    # объекты из Configuration.mdo, которых нет на диске
    for fq in sorted(registered):
        kind, name = fq.split('.', 1)
        if prefix and not name.startswith(prefix):
            continue
        if kind in lib.FOLDERS and not os.path.isdir(os.path.join(src, lib.FOLDERS[kind], name)):
            errors.append('%s: прописан в Configuration.mdo, а папки нет' % fq)

    if not quiet:
        for w in warnings:
            print('  предупреждение: ' + w)
    for e in errors:
        print('ОШИБКА: ' + e)
    print('Проверено объектов: %d, ошибок %d, предупреждений %d' % (len(objects), len(errors), len(warnings)))
    sys.exit(1 if errors else 0)


def check_subsystem(src, folder, name, parent, errors):
    fq = 'Subsystem.' + name
    text = read(os.path.join(folder, name + '.mdo'))
    if parent and ('<parentSubsystem>Subsystem.%s</parentSubsystem>' % parent) not in text:
        errors.append('%s: дочерняя подсистема без <parentSubsystem>Subsystem.%s</parentSubsystem> (case 019)'
                      % (fq, parent))
    for obj in re.findall(r'<content>([^<]+)</content>', text):
        kind, oname = obj.split('.', 1)
        if kind in lib.FOLDERS and not os.path.isdir(os.path.join(src, lib.FOLDERS[kind], oname)):
            errors.append('%s: в составе %s, а такого объекта нет' % (fq, obj))
    children = re.findall(r'<subsystems>([^<]+)</subsystems>', text)
    for ch in children:
        chdir = os.path.join(folder, 'Subsystems', ch)
        if not os.path.isdir(chdir):
            errors.append('%s: дочерняя %s объявлена, а папки Subsystems/%s нет' % (fq, ch, ch))
            continue
        check_subsystem(src, chdir, ch, name, errors)


if __name__ == '__main__':
    main()
