import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]


@unittest.skipUnless(os.name=='nt' and (ROOT/'distribution').is_dir(),'Windows distribution source checks')
class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.bin=self.root/'bin';self.bin.mkdir()
        (self.bin/'codex.cmd').write_text('@echo off\nif "%FAKE_FAIL%"=="1" exit /b 7\necho {"version":"9.9.1","pluginId":"1codex@1codex"}\nexit /b 0\n',encoding='ascii')
        self.env={**os.environ,'USERPROFILE':str(self.root/'profile'),'LOCALAPPDATA':str(self.root/'local'),
                  'PATH':str(self.bin)+os.pathsep+os.environ['PATH'],'FAKE_FAIL':'0'}

    def run_script(self,name,*args):
        return subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','RemoteSigned','-File',str(ROOT/'distribution'/name),*args],
                              env=self.env,capture_output=True,text=True,timeout=30)

    def status(self):return json.loads((self.root/'profile/.codex/1codex-updater/status.json').read_text(encoding='utf-8-sig'))

    def test_update_success_and_failure_preserve_last_good_version(self):
        result=self.run_script('Update-1Codex.ps1','-Quiet');self.assertEqual(result.returncode,0,result.stderr)
        good=self.status();self.assertEqual(good['installed_version'],'9.9.1')
        self.env['FAKE_FAIL']='1'
        result=self.run_script('Update-1Codex.ps1','-Quiet');self.assertEqual(result.returncode,1)
        bad=self.status();self.assertEqual(bad['status'],'error')
        self.assertEqual(bad['last_success_at'],good['last_success_at'])
        self.assertEqual(bad['installed_version'],good['installed_version'])

    def test_status_only_does_not_create_profile_or_call_cli(self):
        self.env['FAKE_FAIL']='1'
        result=self.run_script('Update-1Codex.ps1','-StatusOnly')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['schema_version'],0)
        self.assertFalse((self.root/'profile/.codex/1codex-updater').exists())

    def test_install_without_schedule_copies_versioned_updater(self):
        result=self.run_script('Install-1Codex.ps1','-NoSchedule')
        self.assertEqual(result.returncode,0,result.stderr)
        folder=self.root/'profile/.codex/1codex-updater'
        data=json.loads((folder/'installation.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(data['schema_version'],2);self.assertFalse(data['scheduled'])
        self.assertEqual((folder/'Update-1Codex.ps1').read_bytes(),(ROOT/'distribution/Update-1Codex.ps1').read_bytes())
