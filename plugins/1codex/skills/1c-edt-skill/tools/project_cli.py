"""Explicit Designer project workflow. All database operations target test_ib only."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

import check_designer
import designer_lib as dl
import lint_dump
from workflow.resource_lock import base_lease
from workflow.source_guard import FrozenRun, project_lock, cosmetic_equivalent
from workflow import timing


def read_config(path):
    path=Path(path).resolve()
    cfg=json.loads(path.read_text(encoding='utf-8-sig'))
    cfg['_project']=str(path.parent)
    for key in ('dump','work','v8','test_ib','production_ib','release_target','ui_scenario','manager_source'):
        if cfg.get(key): cfg[key]=str((path.parent/Path(cfg[key])).resolve())
    cfg.setdefault('work',str(path.parent/'.platform'))
    return cfg


def doctor(cfg):
    missing=[]
    for key in ('dump','configuration_kind','metadata_version'):
        if not cfg.get(key): missing.append(key)
    source=Path(cfg.get('dump') or '__absent__')
    v8=Path(cfg.get('v8') or '__absent__')
    test=Path(cfg.get('test_ib') or '__absent__')
    ready=not missing and source.is_dir() and v8.is_file() and (test/'1Cv8.1CD').is_file() and os.name=='nt'
    result={'python':sys.version.split()[0],'python_bits':struct.calcsize('P')*8,'os':os.name,
        'missing_settings':missing,'source_exists':source.is_dir(),'platform_executable_exists':v8.is_file(),
        'test_base_exists':(test/'1Cv8.1CD').is_file(),'ready_for_platform':ready,
        'dependencies':{name:importlib.util.find_spec(name) is not None for name in ('win32com','PIL')},
        'com_registered':False,'interactive_screen':False,'platform_version':None}
    if os.name=='nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,(cfg.get('com') or 'V83.COMConnector')+'\\CLSID') as k:
                clsid=winreg.QueryValueEx(k,None)[0]
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,'CLSID\\'+clsid+'\\InprocServer32') as k:
                com_path=Path(winreg.QueryValueEx(k,None)[0])
                result['com_registered']=com_path.is_file()
                result['com_matches_selected_platform']=com_path.parent==v8.parent
                result['com_platform_version']=com_path.parent.parent.name
        except OSError:pass
        import ctypes
        result['interactive_screen']=ctypes.windll.user32.GetSystemMetrics(0)>0
        if v8.is_file():
            script="(Get-Item -LiteralPath '"+str(v8).replace("'","''")+"').VersionInfo.ProductVersion"
            r=subprocess.run(['powershell','-NoProfile','-Command',script],capture_output=True,text=True,timeout=15)
            if r.returncode==0:result['platform_version']=r.stdout.strip()
    return result


def validate_settings(cfg):
    for key in ('dump','v8','test_ib','configuration_kind','metadata_version'):
        if not cfg.get(key):raise ValueError('Missing setting: '+key)
    kind=cfg['configuration_kind']
    if kind not in ('own','vendor','extension','external'):raise ValueError('Unsupported configuration kind')
    if kind=='vendor' and not cfg.get('load_files'):raise ValueError('Vendor configuration requires an explicit delta file list')
    if kind=='extension' and not cfg.get('extension'):raise ValueError('Extension name is required')
    for path in cfg.get('load_files',[]):
        if Path(path).is_absolute() or '..' in Path(path).parts:raise ValueError('Delta path must stay inside dump')
        if not (Path(cfg['dump'])/path).is_file():raise ValueError('Delta file does not exist: '+path)
    source=Path(cfg['dump']).resolve();work=Path(cfg['work']).resolve();test=Path(cfg['test_ib']).resolve()
    if work.is_relative_to(source) or test.is_relative_to(source):raise ValueError('Work and test base must be outside source')
    if Path(cfg.get('_project',work.parent)).resolve().is_relative_to(source):raise ValueError('Project JSON must be outside source')
    if cfg.get('production_ib') and test==Path(cfg['production_ib']).resolve():raise ValueError('Test base is the production base')
    if not (test/'1Cv8.1CD').is_file():raise ValueError('A separate existing test base is required')
    if not Path(cfg['v8']).is_file():raise ValueError('Platform executable not found')
    with dl.generation_context(cfg['metadata_version']): pass
    roots=list(source.glob('*.xml'))
    for path in roots:
        tree=ET.parse(path).getroot()
        if check_designer.local(tree.tag)=='MetaDataObject':
            if tree.get('version')!=cfg['metadata_version']:raise ValueError('Configured XML format differs from source')
            compatibility=tree.findtext('{*}Configuration/{*}Properties/{*}CompatibilityMode')
            if cfg.get('compatibility_mode') and compatibility and compatibility!=cfg['compatibility_mode']:
                raise ValueError('Configured compatibility differs from source')


def compare(source,exported):
    def files(path):
        # Bootstrap instructions are protected as inputs but are not 1C deployment files.
        ancillary={'ConfigDumpInfo.xml','AGENTS.md','.gitignore'}
        return {p.relative_to(path).as_posix():p for p in path.rglob('*')
                if p.is_file() and p.relative_to(path).as_posix() not in ancillary}
    a,b=files(Path(source)),files(Path(exported))
    errors=['File set differs: '+name for name in sorted(a.keys()^b.keys())]
    cosmetic=[]
    for name in sorted(a.keys()&b.keys()):
        if a[name].read_bytes()==b[name].read_bytes():continue
        if cosmetic_equivalent(a[name],b[name]):cosmetic.append(name)
        else:errors.append('Content differs: '+name)
    return {'errors':errors,'cosmetic':cosmetic,'compared_files':len(a.keys()&b.keys())}


def execute(cfg,action):
    validate_settings(cfg)
    project=Path(cfg['_project']);source=Path(cfg['dump']);kind=cfg['configuration_kind']
    if action=='release':
        if not cfg.get('release_target'):raise ValueError('release_target is required')
        target=Path(cfg['release_target'])
        if target.is_relative_to(source) or target.is_relative_to(Path(cfg['test_ib'])):raise ValueError('Unsafe release target')
        if target.suffix.lower()!=('.epf' if kind=='external' else '.cf'):raise ValueError('Unexpected release extension')
        for level in cfg.get('required_test_levels',['com','ui']):
            if level=='com' and not cfg.get('com_test'):raise ValueError('Release requires COM acceptance hook')
            if level=='ui' and not cfg.get('ui_scenario'):raise ValueError('Release requires UI scenario')
    run=None;status='failed'
    with project_lock(project,cfg['work']):
        journal=timing.create(project,action,scenario='project-'+action,environment=cfg.get('platform_version'),
                             dataset=cfg.get('dataset'),revision=cfg.get('skill_revision'))
        try:
            run=FrozenRun(project,source,action,platform=cfg['work'])
            def stage(name,callback):
                with timing.stage(journal,name):
                    code=run.stage(name,callback)
                    if code:raise RuntimeError('Stage failed: '+name)
            stage('structure',lambda:bool(check_designer.check(run.snapshot)))
            baseline=cfg.get('lint_baseline') or str(source.parent/'lint_baseline.txt')
            stage('lint',lambda:lint_dump.lint(str(run.snapshot),baseline))
            kw={'user':cfg.get('test_usr',''),'timeout':cfg.get('timeout',300)}
            v8,ib=cfg['v8'],cfg['test_ib']
            def platform(name,args):
                with base_lease(project,ib):
                    code,text,seconds=dl.designer(v8,ib,args,str(run.folder/(name+'.log')),**kw)
                if code or re.search(r'\b(?:Ошибка|Error|Exception|Исключение)(?=\s|:|\()',text,re.I):return code or 1
                return 0
            stage('backup',lambda:platform('backup',['/DumpIB "'+str(run.folder/'before.dt')+'"']))
            extension=['-Extension "'+cfg['extension']+'"'] if kind=='extension' else []
            if kind=='external':
                roots=[p for p in run.snapshot.glob('*.xml') if check_designer.local(ET.parse(p).getroot().tag)=='MetaDataObject']
                artifact=run.folder/'processor.epf'
                stage('build',lambda:platform('build',['/LoadExternalDataProcessorOrReportFromFiles "'+str(roots[0])+'" "'+str(artifact)+'"']))
            else:
                args=['/LoadConfigFromFiles "'+str(run.snapshot)+'"']+extension
                if kind=='vendor':
                    names=list(dict.fromkeys(['Configuration.xml']+cfg['load_files']))
                    listing=run.folder/'delta.txt';listing.write_text('\n'.join(str(run.snapshot/n) for n in names),encoding='utf-8-sig')
                    args+=['-listFile "'+str(listing)+'"']
                stage('load',lambda:platform('load',args))
                stage('update',lambda:platform('update',['/UpdateDBCfg']+extension))
                stage('modules',lambda:platform('modules',['/CheckModules']+cfg.get('check_modes',['-ThinClient','-Server','-ExternalConnection'])+extension))
            exported=run.folder/'exported';exported.mkdir()
            dump_args=['/DumpExternalDataProcessorOrReportToFiles "'+str(exported)+'" "'+str(artifact)+'"'] if kind=='external' else ['/DumpConfigToFiles "'+str(exported)+'"','-Format Hierarchical']+extension
            stage('dump',lambda:platform('dump',dump_args))
            comparison=compare(run.snapshot,exported)
            (run.folder/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding='utf-8')
            stage('compare',lambda:bool(comparison['errors']))
            if action in ('test','release'):
                if cfg.get('com_test'):
                    hook=project/cfg['com_test']
                    def com():
                        # Hook receives only explicit test-base and artifact environment.
                        r=subprocess.run([sys.executable,str(hook)],env={**os.environ,'ONECODEX_TEST_IB':ib,
                            'ONECODEX_COM_PROGID':cfg.get('com') or 'V83.COMConnector',
                            'ONECODEX_ARTIFACT':str(artifact) if kind=='external' else '', 'PYTHONUTF8':'1'},
                            capture_output=True,text=True,encoding='utf-8',timeout=cfg.get('timeout',300))
                        (run.folder/'com.log').write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
                        return r.returncode
                    stage('com',com)
                if cfg.get('ui_scenario'):
                    import ui_test
                    # Child runner owns the base lease; parent does not hold it here.
                    options={}
                    if cfg.get('manager_source'):options['manager']=cfg['manager_source']
                    stage('ui',lambda:ui_test.run(cfg['ui_scenario'],ib,str(Path(v8).parent),user=cfg.get('test_usr',''),
                        work=str(run.folder/'ui'),port=cfg.get('ui_port',48133),printwindow=cfg.get('ui_printwindow',False),**options))
            if action=='release':
                if kind!='external':
                    artifact=run.folder/'release.cf'
                    stage('export',lambda:platform('export',['/DumpCfg "'+str(artifact)+'"']+extension))
                target=Path(cfg['release_target']);target.parent.mkdir(parents=True,exist_ok=True)
                run.pending.append((str(artifact),str(target)))
                stage('publish-local',lambda:run.publish() or 0)
            status='ok'
            return {'status':'ok','run_id':run.id,'artifacts':str(run.folder),'timing':str(journal),
                    'performed':[s['name'] for s in run.record['stages']]}
        finally:
            try:
                if run:run.finish('succeeded' if status=='ok' else 'failed')
            finally:timing.finish(journal,status)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['doctor','lint','check','test','release'])
    p.add_argument('--config',required=True,type=Path)
    args=p.parse_args()
    try:
        cfg=read_config(args.config)
        if args.action=='doctor':result=doctor(cfg)
        elif args.action=='lint':return lint_dump.lint(cfg['dump'],cfg.get('lint_baseline'))
        else:result=execute(cfg,args.action)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,RuntimeError,ET.ParseError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
