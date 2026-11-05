"""Create an isolated disposable 1C base and a minimal Designer fixture. Never opens a user base."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import designer_lib as dl


def create(v8,output):
    output=Path(output).resolve()
    if output.exists() and any(output.iterdir()):raise ValueError('Output must be a new/empty directory')
    output.mkdir(parents=True,exist_ok=True);base=output/'base';base.mkdir()
    r=subprocess.run('"%s" CREATEINFOBASE File="%s" /DisableStartupDialogs /Out "%s"' % (v8,base,output/'create.log'),timeout=90)
    if r.returncode or not (base/'1Cv8.1CD').is_file():raise RuntimeError('Empty test base creation failed')
    source=output/'source'
    code,log,_=dl.dump(str(v8),str(base),str(source),str(output/'empty-dump.log'),user='',timeout=90)
    if code:raise RuntimeError(log)
    config=source/'Configuration.xml';text=dl.read_lf(str(config));tree=ET.fromstring(text)
    version=tree.get('version');compat=tree.findtext('{*}Configuration/{*}Properties/{*}CompatibilityMode')
    children=tree.find('{*}Configuration/{*}ChildObjects');objects={}
    if children is not None:
        for child in children:
            objects.setdefault(child.tag.rsplit('}',1)[-1],[]).append(child.text)
    objects.update(Catalog=['тстТовары'],CommonModule=['тстСервис'],Role=['тстПолныеПрава'])
    with dl.generation_context(version):
        block=dl.configuration_child_objects(objects)
        text=re.sub(r'\t\t<ChildObjects\s*/>|\t\t<ChildObjects>.*?</ChildObjects>',lambda m:block,text,count=1,flags=re.S)
        text=text.replace('<DefaultRoles/>','<DefaultRoles>\n\t\t\t\t<xr:Item xsi:type="xr:MDObjectRef">Role.тстПолныеПрава</xr:Item>\n\t\t\t</DefaultRoles>')
        dl.write(str(config),text)
        dl.write(str(source/'Catalogs/тстТовары.xml'),dl.catalog_xml('тстТовары','Тестовые товары',attributes=[('Артикул','string:40','Артикул')]))
        dl.write(str(source/'CommonModules/тстСервис.xml'),dl.common_module_xml('тстСервис','Сервис проверки'))
        dl.write(str(source/'CommonModules/тстСервис/Ext/Module.bsl'),'Функция Проверка() Экспорт\n\tВозврат "1Codex OK";\nКонецФункции\n')
        dl.write(str(source/'Roles/тстПолныеПрава.xml'),dl.role_xml('тстПолныеПрава','Полные права теста'))
        dl.write(str(source/'Roles/тстПолныеПрава/Ext/Rights.xml'),dl.rights_xml(set_for_new_objects=True))
    cfg={'format':'designer','configuration_kind':'own','metadata_version':version,'compatibility_mode':compat,
         'v8':str(Path(v8).resolve()),'test_ib':str(base),'dump':str(source),'work':str(output/'.platform'),
         'test_usr':'','ui_port':49183,'timeout':180,'com_test':str(ROOT/'tests/designer/com_acceptance.py'),
         'ui_scenario':str(ROOT/'tests/designer/ui_acceptance.txt'),'release_target':str(output/'release/fixture.cf'),
         'platform_version':Path(v8).parents[1].name,'dataset':'minimal-designer-v1','skill_revision':'local-review'}
    cfg['com']='V85.COMConnector' if version=='2.21' else 'V83.COMConnector'
    (output/'platform.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    return cfg


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--v8',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();print(json.dumps(create(args.v8,args.output),ensure_ascii=False,indent=2))
